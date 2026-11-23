# SPDX-FileCopyrightText: 2026 Chiken_Monster
# SPDX-License-Identifier: GPL-3.0-or-later
"""Viewport navigation: Alt+mouse orbit/pan/dolly and RMB look/WASD fly.

The modal operators here are the only long lived owners of viewport state.
Rules implemented (docs/04_architecture.md, docs/02):

* ``PERSP`` only for look/fly; camera view is never touched (poll fails ->
  event passes through to Blender).
* ``ESC`` / window deactivate / invalid area / RMB release / add-on disable all
  end the modal through one idempotent ``_end()`` path; the timer never leaks.
* movement uses ``time.monotonic()`` with a dt clamp, so a frozen window does
  not teleport the camera.
* a quick RMB click (below the drag threshold and click timeout) is forwarded
  to Blender's own context menu, so N09 has a real fallback.
* the math is exposed as module level functions so it is unit testable
  without a GUI.
"""
import math
import time

import bpy
from bpy.props import EnumProperty
from mathutils import Quaternion, Vector

OWN_PREFIX = "uei."

MIN_DT = 1.0 / 240.0
MAX_DT = 0.1
# 120 Hz timer: movement stays smooth on high refresh displays (60 Hz felt stepped).
TIMER_INTERVAL = 1.0 / 120.0
SPEED_MULT_MIN = 1.0
SPEED_MULT_MAX = 20.0
SPEED_WHEEL_STEP = 1.15
BOOST_FACTOR = 4.0
PITCH_LIMIT = math.radians(89.0)

# Modal operators currently alive (used to cancel cleanly on unregister).
_ACTIVE = []

# Diagnostics counter: quick RMB clicks forwarded to Blender's context menu.
CONTEXT_MENU_FORWARDS = 0

# Compact trace of finished modal sessions (GUI test evidence, capped).
_TRACE = []
TRACE_LIMIT = 200


def trace_events():
    return list(_TRACE)


def _record_trace(payload):
    _TRACE.append(payload)
    if len(_TRACE) > TRACE_LIMIT:
        del _TRACE[: len(_TRACE) - TRACE_LIMIT]


# ---------------------------------------------------------------------------
# view math (pure helpers, unit tested headless)
# ---------------------------------------------------------------------------
def view_forward(rv3d):
    return (rv3d.view_rotation @ Vector((0.0, 0.0, -1.0))).normalized()


def view_right(rv3d):
    return (rv3d.view_rotation @ Vector((1.0, 0.0, 0.0))).normalized()


def view_up(rv3d):
    return (rv3d.view_rotation @ Vector((0.0, 1.0, 0.0))).normalized()


def orbit(rv3d, dx, dy, deg_per_px=0.35):
    """Orbit around the current pivot (``view_location``); keeps distance."""
    if not dx and not dy:
        return
    yaw = Quaternion(Vector((0.0, 0.0, 1.0)), math.radians(-dx * deg_per_px))
    q = yaw @ rv3d.view_rotation
    right_axis = (q @ Vector((1.0, 0.0, 0.0))).normalized()
    pitch = Quaternion(right_axis, math.radians(dy * deg_per_px))
    rv3d.view_rotation = (pitch @ q).normalized()


def pan(rv3d, dx, dy, region_width, region_height):
    """Pan the view; content follows the cursor (Blender convention)."""
    height = max(1.0, float(region_height))
    scale = 2.0 * float(rv3d.view_distance) / height
    offset = view_right(rv3d) * (-dx * scale) + view_up(rv3d) * (dy * scale)
    rv3d.view_location = rv3d.view_location + offset
    try:
        rv3d.update()
    except (AttributeError, RuntimeError):
        pass


def dolly(rv3d, dx, dy=0.0, strength=0.004):
    """Dolly along the view axis: drag right = move camera forward (UE-ish)."""
    delta = dx if abs(dx) >= abs(dy) else dy
    if not delta:
        return
    factor = math.exp(-delta * strength)
    distance = float(rv3d.view_distance) * factor
    rv3d.view_distance = max(1e-3, min(1e6, distance))
    try:
        rv3d.update()
    except (AttributeError, RuntimeError):
        pass


def look(rv3d, dx, dy, deg_per_px=0.25, invert_y=False):
    """FPS style look: yaw around world Z, pitch clamped, no roll."""
    if not dx and not dy:
        return
    forward = view_forward(rv3d)
    yaw = math.atan2(forward.y, forward.x)
    pitch = math.asin(max(-1.0, min(1.0, forward.z)))
    yaw -= math.radians(dx * deg_per_px)
    # Default: mouse up looks up (FPS / UE convention); invert_y flips it.
    if invert_y:
        pitch -= math.radians(dy * deg_per_px)
    else:
        pitch += math.radians(dy * deg_per_px)
    pitch = max(-PITCH_LIMIT, min(PITCH_LIMIT, pitch))
    cos_p = math.cos(pitch)
    direction = Vector((cos_p * math.cos(yaw), cos_p * math.sin(yaw), math.sin(pitch)))
    rv3d.view_rotation = direction.to_track_quat('-Z', 'Y')
    try:
        rv3d.update()
    except (AttributeError, RuntimeError):
        pass


def fly_velocity(rv3d, keys, speed=1.0, boost=False, normalize=False):
    """World space velocity vector for the currently held flight keys.

    ``Q``/``E`` move along world -Z/+Z (down/up) in every mode. ``normalize`` is
    only used by the Edit Mesh session so that combining keys (e.g. W+Q) keeps a
    constant speed; Object Mode keeps its original (non-normalized) behaviour.
    """
    velocity = Vector((0.0, 0.0, 0.0))
    if not keys:
        return velocity
    forward = view_forward(rv3d)
    right = view_right(rv3d)
    local_up = view_up(rv3d)
    if 'W' in keys:
        velocity += forward
    if 'S' in keys:
        velocity -= forward
    if 'D' in keys:
        velocity += right
    if 'A' in keys:
        velocity -= right
    if 'E' in keys:
        velocity += Vector((0.0, 0.0, 1.0))
    if 'Q' in keys:
        velocity -= Vector((0.0, 0.0, 1.0))
    if 'R' in keys:
        velocity += local_up
    if 'F' in keys:
        velocity -= local_up
    if normalize and velocity.length > 1.0:
        velocity.normalize()
    if speed != 1.0 or boost:
        velocity *= speed * (BOOST_FACTOR if boost else 1.0)
    return velocity


def move_view(rv3d, velocity, dt):
    if dt <= 0.0 or velocity.length_squared == 0.0:
        return
    rv3d.view_location = rv3d.view_location + velocity * dt
    try:
        rv3d.update()
    except (AttributeError, RuntimeError):
        pass


# ---------------------------------------------------------------------------
# context guards
# ---------------------------------------------------------------------------
def _space_ok(context):
    area = getattr(context, 'area', None)
    region = getattr(context, 'region', None)
    if area is None or region is None:
        return False
    if area.type != 'VIEW_3D':
        return False
    if region.type != 'WINDOW':
        return False
    space = getattr(context, 'space_data', None)
    if space is None or getattr(space, 'region_3d', None) is None:
        return False
    return True


def _persp_ok(context):
    return _space_ok(context) and getattr(context.space_data.region_3d, 'view_perspective', '') == 'PERSP'


def _is_camera_view(context):
    if not _space_ok(context):
        return False
    return getattr(context.space_data.region_3d, 'view_perspective', '') == 'CAMERA'


def _object_mode(context):
    return getattr(context, 'mode', 'OBJECT') == 'OBJECT'


def _edit_mesh(context):
    """True only for the Mesh Edit Mode of a 3D View (P2C scope)."""
    return getattr(context, 'mode', '') == 'EDIT_MESH'


def _prefs_of(context):
    from . import preferences

    try:
        return preferences.get(context)
    except Exception:  # pragma: no cover - defensive
        return None


def _pref_on(context, name):
    prefs = _prefs_of(context)
    return bool(prefs is not None and getattr(prefs, name, False))


def cancel_all():
    """Ask every live modal operator to finish (called from unregister)."""
    for op in list(_ACTIVE):
        try:
            op._request_cancel()
        except ReferenceError:
            continue


# ---------------------------------------------------------------------------
# base operator: shared lifecycle, validation and cleanup
# ---------------------------------------------------------------------------
class _ModalBase(bpy.types.Operator):
    bl_options = {'INTERNAL'}

    _timer = None
    _window = None
    _area = None
    _region = None
    _rv3d = None
    _quit = False

    # -- lifecycle ---------------------------------------------------------
    def _start(self, context):
        self._window = context.window
        self._area = context.area
        self._region = context.region
        self._rv3d = context.space_data.region_3d
        self._quit = False
        self._started_wall = time.monotonic()
        self._start_view = (
            tuple(self._rv3d.view_rotation),
            tuple(self._rv3d.view_location),
            float(self._rv3d.view_distance),
        )
        self._end_reason = 'unknown'
        self._timer = context.window_manager.event_timer_add(TIMER_INTERVAL, window=context.window)
        context.window_manager.modal_handler_add(self)
        _ACTIVE.append(self)

    def _request_cancel(self):
        self._quit = True

    def _valid(self, context):
        if self._quit:
            return False
        try:
            if self._area is None or self._region is None or self._rv3d is None:
                return False
            if self._area.type != 'VIEW_3D':
                return False
            window = getattr(context, 'window', None)
            if window is None:
                return False
            # Never compare RNA wrappers with ``is`` (they are re-created per access).
            return window.as_pointer() == self._window.as_pointer()
        except (ReferenceError, AttributeError, RuntimeError):
            return False

    def _tag_redraw(self):
        try:
            self._area.tag_redraw()
        except (ReferenceError, AttributeError):
            pass

    def _end(self, context):
        if getattr(self, '_timer', None) is not None:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except (ReferenceError, RuntimeError, TypeError):
                pass
            self._timer = None
        # Recorded for GUI tests: a leaked timer is a blocker for N08/FW07.
        self.timer_cleared = self._timer is None
        if self in _ACTIVE:
            _ACTIVE.remove(self)
        self._record_session_trace()
        self._tag_redraw()

    def _record_session_trace(self):
        """Append a compact, machine readable record of this modal session."""
        try:
            rv3d = self._rv3d
            start = getattr(self, '_start_view', None)
            rot_changed = loc_moved = dist_changed = loc_delta = None
            if start is not None and rv3d is not None:
                rot_changed = max(abs(a - b) for a, b in zip(start[0], tuple(rv3d.view_rotation))) > 1e-5
                loc_moved = sum(abs(a - b) for a, b in zip(start[1], tuple(rv3d.view_location)))
                dist_changed = abs(start[2] - float(rv3d.view_distance)) > 1e-5
                # Signed per-axis view displacement (Q/E vertical flight evidence).
                loc_delta = [round(float(b) - float(a), 5)
                             for a, b in zip(start[1], tuple(rv3d.view_location))]
            payload = {
                'op': self.bl_idname,
                'reason': getattr(self, '_end_reason', 'unknown'),
                'duration': round(time.monotonic() - getattr(self, '_started_wall', 0.0), 3),
                'rotation_changed': rot_changed,
                'location_moved': None if loc_moved is None else round(loc_moved, 5),
                'location_delta': loc_delta,
                'distance_changed': dist_changed,
            }
            for attr in ('nav', 'keys_used', 'drag_pixels', 'speed_mult', 'mode', 'timer_cleared'):
                if hasattr(self, attr):
                    value = getattr(self, attr)
                    payload[attr] = sorted(value) if isinstance(value, set) else value
            _record_trace(payload)
        except (ReferenceError, AttributeError, TypeError, ValueError):
            pass

    def finish(self, context, result={'FINISHED'}, reason=None):
        if reason is None:
            reason = 'cancelled' if result and 'CANCELLED' in result else 'finished'
        self._end_reason = reason
        self._end(context)
        return result


# ---------------------------------------------------------------------------
# Alt + mouse orbit / pan / dolly
# ---------------------------------------------------------------------------
_ALT_MODE = {
    'ORBIT': "Alt Orbit",
    'PAN': "Alt Pan",
    'DOLLY': "Alt Dolly",
}


class UEI_OT_AltNavigate(_ModalBase):
    bl_idname = 'uei.alt_navigate'
    bl_label = 'UE: Alt Mouse Navigation'
    bl_description = 'Alt+middle/right/left drag orbit, pan and dolly the 3D viewport'

    nav: EnumProperty(
        name='Navigation',
        items=[
            ('ORBIT', 'Orbit', 'Orbit around the viewport pivot'),
            ('PAN', 'Pan', 'Pan the viewport'),
            ('DOLLY', 'Dolly', 'Dolly the viewport'),
        ],
        default='ORBIT',
    )

    @classmethod
    def poll(cls, context):
        # Alt navigation is Object Mode only (P2C §1.1: not adapted in Edit Mode).
        return _space_ok(context) and not _is_camera_view(context) and _object_mode(context)

    def invoke(self, context, event):
        if not _space_ok(context):
            return {'CANCELLED'}
        rv3d = context.space_data.region_3d
        if rv3d.view_perspective not in ('PERSP', 'ORTHO'):
            return {'CANCELLED'}
        self._last_x = event.mouse_region_x
        self._last_y = event.mouse_region_y
        self._start(context)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not self._valid(context):
            self._end_reason = 'context_invalid'
            self._end(context)
            return {'CANCELLED'}
        if event.type == 'TIMER':
            return {'RUNNING_MODAL'}
        if event.type == 'MOUSEMOVE':
            rv3d = self._rv3d
            try:
                dx = event.mouse_region_x - self._last_x
                dy = event.mouse_region_y - self._last_y
            except AttributeError:
                return {'RUNNING_MODAL'}
            self._last_x = event.mouse_region_x
            self._last_y = event.mouse_region_y
            if dx or dy:
                if self.nav == 'ORBIT':
                    orbit(rv3d, dx, dy)
                elif self.nav == 'PAN':
                    pan(rv3d, dx, dy, self._region.width, self._region.height)
                else:
                    dolly(rv3d, dx, dy)
                self._tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type in ('ESC', 'CANCEL'):
            return self.finish(context, {'CANCELLED'}, reason='esc')
        if event.type in ('LEFTMOUSE', 'MIDDLEMOUSE', 'RIGHTMOUSE') and event.value == 'RELEASE':
            return self.finish(context, {'FINISHED'}, reason='mouse_release')
        if event.type == 'WINDOW_DEACTIVATE':
            return self.finish(context, {'CANCELLED'}, reason='deactivate')
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        self._end(context)


# ---------------------------------------------------------------------------
# RMB look + WASD fly
# ---------------------------------------------------------------------------
_FLY_KEYS = {'W', 'A', 'S', 'D', 'Q', 'E', 'R', 'F'}
# Edit Mesh flight whitelist: W/A/S/D only (P2C §1.1 - no Q/E vertical, no R/F).
_EDIT_MESH_FLY_KEYS = {'W', 'A', 'S', 'D', 'Q', 'E'}
_MODIFIER_KEYS = {
    'LEFT_SHIFT',
    'RIGHT_SHIFT',
    'LEFT_CTRL',
    'RIGHT_CTRL',
    'LEFT_ALT',
    'RIGHT_ALT',
    'OSKEY',
}


def _open_context_menu(window, area, region):
    """Deferred: reopen Blender's own right click menu after a quick RMB click."""
    global CONTEXT_MENU_FORWARDS
    CONTEXT_MENU_FORWARDS += 1

    def _call():
        try:
            with bpy.context.temp_override(window=window, area=area, region=region):
                bpy.ops.screen.region_context_menu('INVOKE_DEFAULT')
        except Exception as exc:  # pragma: no cover - GUI only
            print("[uei] context menu fallback failed:", exc)
        return None

    try:
        bpy.app.timers.register(_call, first_interval=0.005)
    except (ValueError, RuntimeError) as exc:  # pragma: no cover
        print("[uei] cannot schedule context menu:", exc)


class _RMBFlyMixin:
    """Shared RMB look/fly implementation.

    Deliberately **not** a ``bpy.types.Operator`` subclass: the Object Mode and
    the Edit Mesh entry points are two concrete operators that mix this in, so
    Blender never has to register/unregister an operator parent/child pair
    (that pair makes ``register_class`` raise "already registered as a
    subclass" after an add-on reload and leaves a stale operator bound to the
    keymap item).
    """

    bl_options = {'INTERNAL'}

    # -- helpers -----------------------------------------------------------
    def _setup_state(self, context, event):
        from . import preferences

        prefs = preferences.get(context)
        self._keys = set()
        self._start_x = event.mouse_region_x
        self._start_y = event.mouse_region_y
        self._last_x = self._start_x
        self._last_y = self._start_y
        self._started_at = time.monotonic()
        self._last_tick = self._started_at
        self._looking = False
        self._dragged = False
        self._speed_mult = float(getattr(prefs, 'fly_speed_multiplier', 1.0)) if prefs else 1.0
        self._base_speed = float(getattr(prefs, 'fly_base_speed', 5.0)) if prefs else 5.0
        self._look_sens = float(getattr(prefs, 'look_sensitivity', 0.25)) if prefs else 0.25
        self._invert_y = bool(getattr(prefs, 'invert_look_y', False)) if prefs else False
        self._threshold = int(getattr(prefs, 'drag_threshold_px', 5)) if prefs else 5
        self._click_ms = int(getattr(prefs, 'click_timeout_ms', 250)) if prefs else 250
        self.keys_used = set()
        self.drag_pixels = 0.0
        self.speed_mult = float(self._speed_mult)
        self._cursor_saved = None
        self._status_active = False
        self._session_mode = getattr(context, 'mode', '')
        self._edit_mesh_session = self._session_mode == 'EDIT_MESH'
        self.mode = self._session_mode

    def _set_status(self, context, text):
        try:
            context.workspace.status_text_set(text)
            self._status_active = True
        except (AttributeError, ReferenceError):
            pass

    def _clear_status(self, context):
        if self._status_active:
            try:
                context.workspace.status_text_set(None)
            except (AttributeError, ReferenceError):
                pass
            self._status_active = False

    def _set_cursor_hidden(self, context, hidden):
        try:
            if hidden:
                context.window.cursor_modal_set('NONE')
                self._cursor_saved = 'DEFAULT'
            elif self._cursor_saved is not None:
                context.window.cursor_modal_restore()
                self._cursor_saved = None
        except (AttributeError, ReferenceError, RuntimeError):
            pass

    def _speed_text(self):
        # The speed multiplier is shared between Object Mode and Edit Mesh flight.
        if self._edit_mesh_session:
            return "Fly speed %.2fx  (Edit Mesh: W/A/S/D + Q/E, wheel = speed)" % (self._speed_mult,)
        return "Fly speed %.2fx  (wheel to change)" % (self._speed_mult,)

    def _apply_speed(self, context, factor):
        self._speed_mult = max(SPEED_MULT_MIN, min(SPEED_MULT_MAX, self._speed_mult * factor))
        from . import preferences

        prefs = preferences.get(context)
        if prefs is not None:
            prefs.fly_speed_multiplier = self._speed_mult
        self._set_status(context, self._speed_text())

    # -- operator ----------------------------------------------------------
    def invoke(self, context, event):
        if not self.poll(context):
            return {'CANCELLED'}
        self._setup_state(context, event)
        self._start(context)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not self._valid(context):
            return self.finish(context, {'CANCELLED'}, reason='context_invalid')
        if getattr(context, 'mode', '') != self._session_mode:
            # Mode changed under the modal (e.g. Tab): never keep flying.
            return self.finish(context, {'CANCELLED'}, reason='mode_changed')
        etype = event.type

        if etype == 'TIMER':
            if self._quit:
                return self.finish(context, {'CANCELLED'})
            now = time.monotonic()
            dt = max(0.0, min(MAX_DT, now - self._last_tick))
            self._last_tick = now
            if self._keys:
                velocity = fly_velocity(self._rv3d, self._keys,
                                        self._base_speed * self._speed_mult,
                                        normalize=self._edit_mesh_session)
                move_view(self._rv3d, velocity, dt)
                self._tag_redraw()
            return {'RUNNING_MODAL'}

        if etype in ('MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'):
            try:
                x, y = event.mouse_region_x, event.mouse_region_y
            except AttributeError:
                return {'RUNNING_MODAL'}
            dx = x - self._last_x
            dy = y - self._last_y
            self._last_x = x
            self._last_y = y
            if not self._looking:
                moved = max(abs(x - self._start_x), abs(y - self._start_y))
                if moved >= self._threshold:
                    self._looking = True
                    self._dragged = True
                    self._set_cursor_hidden(context, True)
                    self._set_status(context, self._speed_text())
            if self._looking and (dx or dy):
                self.drag_pixels += abs(dx) + abs(dy)
                look(self._rv3d, dx, dy, self._look_sens, self._invert_y)
                self._tag_redraw()
            return {'RUNNING_MODAL'}

        if etype == 'RIGHTMOUSE':
            if event.value == 'RELEASE':
                elapsed = (time.monotonic() - self._started_at) * 1000.0
                quick_click = (
                    not self._dragged
                    and not self._keys
                    and elapsed <= self._click_ms
                )
                self.speed_mult = round(float(self._speed_mult), 3)
                self._end_reason = 'quick_click' if quick_click else 'rmb_release'
                self._end(context)
                if quick_click:
                    _open_context_menu(self._window, self._area, self._region)
                return {'FINISHED'}
            return {'RUNNING_MODAL'}

        if etype in ('WHEELUPMOUSE', 'WHEELDOWNMOUSE'):
            # Wheel speed works in BOTH modes and writes the same
            # ``fly_speed_multiplier`` preference, so the speed is shared.
            if etype == 'WHEELUPMOUSE':
                self._apply_speed(context, SPEED_WHEEL_STEP)
            else:
                self._apply_speed(context, 1.0 / SPEED_WHEEL_STEP)
            return {'RUNNING_MODAL'}

        if etype in _FLY_KEYS:
            if self._edit_mesh_session and etype not in _EDIT_MESH_FLY_KEYS:
                # R/F stay untouched in Edit Mode; consume so no mesh op runs.
                # (Q/E are allowed here since 0.2.6: world -Z/+Z vertical flight.)
                return {'RUNNING_MODAL'}
            if event.value == 'PRESS':
                self._keys.add(etype)
                self.keys_used.add(etype)
                self._set_status(context, self._speed_text())
            elif event.value == 'RELEASE':
                self._keys.discard(etype)
            return {'RUNNING_MODAL'}

        if etype in _MODIFIER_KEYS:
            return {'RUNNING_MODAL'}

        if etype in ('ESC', 'CANCEL'):
            return self.finish(context, {'CANCELLED'}, reason='esc')

        if etype in ('WINDOW_DEACTIVATE', 'WINDOW'):
            return self.finish(context, {'CANCELLED'}, reason='deactivate')

        # Consume everything else while the modal owns the RMB button.
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        self._end(context)

    def _end(self, context):
        self._set_cursor_hidden(context, False)
        self._clear_status(context)
        self._keys = set()
        super()._end(context)


# ---------------------------------------------------------------------------
# concrete operators sharing the mixin (registered as unrelated operators)
# ---------------------------------------------------------------------------
class UEI_OT_RMBLook(_RMBFlyMixin, _ModalBase):
    """Object Mode RMB look + WASD/QE/RF fly + wheel speed."""

    bl_idname = 'uei.rmb_look'
    bl_label = 'UE: RMB Look / Fly'
    bl_description = 'Hold RMB to look around and fly with W/A/S/D, Q/E, R/F; wheel changes speed'

    @classmethod
    def poll(cls, context):
        return _persp_ok(context) and _object_mode(context)


class UEI_OT_EditMeshLook(_RMBFlyMixin, _ModalBase):
    """P2C: Mesh Edit Mode RMB fly, W/A/S/D + Q/E vertical + mouse look.

    The Edit Mesh item is installed by a separate opt-in switch
    (``enable_edit_mesh_wasd_fly``). Flight keys are W/A/S/D plus Q/E
    (Q = world -Z down, E = world +Z up, the same logic as Object Mode);
    R/F stay disabled for this session. Combining keys is normalized so the
    diagonal speed stays constant. Mouse wheel flight-speed adjustment IS
    available here and writes the same ``fly_speed_multiplier`` preference as
    Object Mode, so the speed is shared. Outside the RMB flight session Q/E keep
    their Edit Mesh industry mappings (Q = Select tool, E = Rotate tool).
    """

    bl_idname = 'uei.edit_mesh_look'
    bl_label = 'UE: Edit Mesh RMB Fly'
    bl_description = ('Hold RMB in Mesh Edit Mode to fly with W/A/S/D and Q/E (down/up), '
                      'steer with the mouse and wheel for speed')

    @classmethod
    def poll(cls, context):
        if not _pref_on(context, 'enable_edit_mesh_wasd_fly'):
            return False
        return _persp_ok(context) and _edit_mesh(context)
