# SPDX-FileCopyrightText: 2026 Chiken_Monster
# SPDX-License-Identifier: GPL-3.0-or-later
"""Single-shot viewport operators plus the read-only audit / self test.

None of the operators in this module keeps state between calls; the only
long lived viewport owner is :mod:`navigation`.
"""
import json
import math
import types

import bpy
from bpy.props import EnumProperty, StringProperty
from mathutils import Quaternion, Vector

from . import diagnostics, keymaps, navigation

TOOL_IDS = {
    'SELECT': 'builtin.select_box',
    'MOVE': 'builtin.move',
    'ROTATE': 'builtin.rotate',
    'SCALE': 'builtin.scale',
}

# Edit Mesh "industry partial" tool ids (mirrors Blender 5.2 Industry Compatible:
# Q/W/E/R use wm.tool_set_by_id(cycle=True); Ctrl+E activates the context sensitive
# Extrude Region *tool*, not a fixed one-shot extrude operator).
EDIT_MESH_TOOL_IDS = {
    'SELECT': 'builtin.select_box',
    'MOVE': 'builtin.move',
    'ROTATE': 'builtin.rotate',
    'SCALE': 'builtin.scale',
    'EXTRUDE': 'builtin.extrude_region',
}

# Extrude Region tool direction mode (tool header "Normal | XYZ" toggle).
# Public API: WorkSpaceTool.gizmo_group_properties("VIEW3D_GGT_xform_extrude").axis_type
# (enum {'NORMAL', 'XYZ'}), the exact property the tool header `draw_settings` draws
# (scripts/startup/bl_ui/space_toolsystem_toolbar.py: _template_widget.VIEW3D_GGT_xform_extrude).
# This is an official RNA property, no private-data access and no UI clicking.
EXTRUDE_GIZMO_GROUP = "VIEW3D_GGT_xform_extrude"
EXTRUDE_AXIS_DEFAULT = 'XYZ'


def set_extrude_axis_type(context, axis=EXTRUDE_AXIS_DEFAULT):
    """Set the Extrude Region tool direction (Normal/XYZ) via public API.

    Returns ``(ok, detail)``. ``detail`` is the resulting ``axis_type`` value or a
    short reason string. Never raises: if the gizmo group is not instantiated yet
    (rare ordering issue) the caller can retry once on a timer.
    """
    try:
        tool = context.workspace.tools.from_space_view3d_mode('EDIT_MESH')
        if tool is None:
            return False, 'no_edit_mesh_tool'
        props = tool.gizmo_group_properties(EXTRUDE_GIZMO_GROUP)
        if props is None or not hasattr(props, 'axis_type'):
            return False, 'no_gizmo_group_props'
        props.axis_type = axis
        return True, str(props.axis_type)
    except (AttributeError, TypeError, RuntimeError, KeyError) as exc:
        return False, '%s: %s' % (type(exc).__name__, exc)


def _deferred_extrude_axis(context, axis=EXTRUDE_AXIS_DEFAULT):
    """One-shot retry: the gizmo group may be created at the next UI tick."""

    def _retry():
        try:
            set_extrude_axis_type(bpy.context, axis)
        except Exception:  # pragma: no cover - defensive
            pass
        return None

    try:
        bpy.app.timers.register(_retry, first_interval=0.0)
    except (ValueError, RuntimeError):  # pragma: no cover
        pass


# Diagnostics: which operators actually executed (used by the GUI test suite).
_CALLS = []


def _log_call(bl_idname, detail='', **extra):
    entry = {'id': bl_idname, 'detail': str(detail)}
    entry.update(extra)
    _CALLS.append(entry)


def calls():
    return list(_CALLS)


def clear_calls():
    del _CALLS[:]


class _ObjectViewOnly:
    """Poll helper: 3D View + Object Mode + a real viewport context."""

    @classmethod
    def poll(cls, context):
        return bool(
            context.area
            and context.area.type == 'VIEW_3D'
            and context.mode == 'OBJECT'
            and context.space_data is not None
            and getattr(context, 'region', None) is not None
            and context.region.type == 'WINDOW'
        )


class UEI_OT_SwitchTool(_ObjectViewOnly, bpy.types.Operator):
    bl_idname = 'uei.switch_tool'
    bl_label = 'UE: Switch Active Tool'
    bl_description = 'Switch the active Blender viewport tool with UE-style hotkeys'
    bl_options = {'INTERNAL'}

    tool: EnumProperty(
        items=[
            ('SELECT', 'Select', ''),
            ('MOVE', 'Move', ''),
            ('ROTATE', 'Rotate', ''),
            ('SCALE', 'Scale', ''),
        ],
        name='Tool',
    )

    def execute(self, context):
        name = TOOL_IDS.get(self.tool)
        _log_call(self.bl_idname, self.tool)
        if not name:
            self.report({'WARNING'}, 'Unknown tool')
            return {'CANCELLED'}
        try:
            bpy.ops.wm.tool_set_by_id(name=name)
        except (RuntimeError, TypeError, ValueError) as exc:
            self.report({'WARNING'}, 'Unable to select tool %s: %s' % (name, exc))
            return {'CANCELLED'}
        _log_call(self.bl_idname, self.tool, result=[t.idname for t in context.workspace.tools])
        return {'FINISHED'}


class _EditMeshViewOnly:
    """Poll helper: 3D View + Mesh Edit Mode + the industry-keys switch."""

    @classmethod
    def poll(cls, context):
        from . import preferences

        prefs = preferences.get(context)
        if prefs is None or not getattr(prefs, 'enable_edit_mesh_industry_keys', False):
            return False
        return bool(
            context.area
            and context.area.type == 'VIEW_3D'
            and context.mode == 'EDIT_MESH'
            and context.space_data is not None
            and getattr(context, 'region', None) is not None
            and context.region.type == 'WINDOW'
        )


class UEI_OT_EditMeshTool(_EditMeshViewOnly, bpy.types.Operator):
    bl_idname = 'uei.edit_mesh_tool'
    bl_label = 'UE: Edit Mesh Industry Tool'
    bl_description = (
        'Industry-compatible Edit Mesh subset: Q/W/E/R switch the active tool, '
        'Ctrl+E activates the context sensitive Extrude Region tool'
    )
    bl_options = {'INTERNAL'}

    tool: EnumProperty(
        items=[
            ('SELECT', 'Select', ''),
            ('MOVE', 'Move', ''),
            ('ROTATE', 'Rotate', ''),
            ('SCALE', 'Scale', ''),
            ('EXTRUDE', 'Extrude Region', ''),
        ],
        name='Tool',
    )

    def execute(self, context):
        name = EDIT_MESH_TOOL_IDS.get(self.tool)
        _log_call(self.bl_idname, self.tool)
        if not name:
            self.report({'WARNING'}, 'Unknown edit tool')
            return {'CANCELLED'}
        # Ctrl+E must always activate exactly Extrude Region (its direction mode is
        # then forced to XYZ below); Q/W/E/R keep the industry `cycle=True` behaviour.
        cycle = self.tool != 'EXTRUDE'
        try:
            bpy.ops.wm.tool_set_by_id(name=name, cycle=cycle)
        except (RuntimeError, TypeError, ValueError) as exc:
            self.report({'WARNING'}, 'Unable to switch edit tool %s: %s' % (name, exc))
            return {'CANCELLED'}
        active = None
        try:
            active = context.workspace.tools.active.idname
        except (AttributeError, RuntimeError):
            pass
        extra = {}
        if self.tool == 'EXTRUDE':
            ok, detail = set_extrude_axis_type(context, EXTRUDE_AXIS_DEFAULT)
            extra['axis_type'] = detail
            extra['axis_set'] = bool(ok)
            if not ok:
                _deferred_extrude_axis(context, EXTRUDE_AXIS_DEFAULT)
        _log_call(
            self.bl_idname,
            self.tool,
            tool_id=name,
            cycle=cycle,
            active_tool=active,
            result=[t.idname for t in context.workspace.tools],
            mode=context.mode,
            **extra
        )
        return {'FINISHED'}


class UEI_OT_EditMeshEdgeMenu(_EditMeshViewOnly, bpy.types.Operator):
    bl_idname = 'uei.edit_mesh_edge_menu'
    bl_label = 'UE: Edit Mesh Edge Menu'
    bl_description = "Open Blender's own mesh Edge menu (native VIEW3D_MT_edit_mesh_edges)"
    bl_options = {'INTERNAL'}

    MENU = 'VIEW3D_MT_edit_mesh_edges'

    def execute(self, context):
        _log_call(self.bl_idname, 'EDGE_MENU', menu=self.MENU, mode=context.mode)
        try:
            # Native Blender menu operator - the menu itself is not reimplemented.
            bpy.ops.wm.call_menu('INVOKE_DEFAULT', name=self.MENU)
        except (RuntimeError, TypeError) as exc:
            self.report({'WARNING'}, 'Cannot open edge menu: %s' % exc)
            return {'CANCELLED'}
        _log_call(self.bl_idname, 'EDGE_MENU_OPENED', menu=self.MENU)
        return {'FINISHED'}


class UEI_OT_FocusSelected(_ObjectViewOnly, bpy.types.Operator):
    bl_idname = 'uei.focus_selected'
    bl_label = 'UE: Focus Selected'
    bl_description = 'Frame the selected objects in this 3D viewport'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        if not context.selected_objects:
            _log_call(self.bl_idname, 'nothing_selected')
            self.report({'INFO'}, 'Nothing selected - view kept')
            return {'CANCELLED'}
        rv3d = getattr(context.space_data, 'region_3d', None)
        before = None
        if rv3d is not None:
            before = [list(rv3d.view_location), float(rv3d.view_distance)]
        try:
            bpy.ops.view3d.view_selected(use_all_regions=False)
        except RuntimeError as exc:
            _log_call(self.bl_idname, 'failed')
            self.report({'WARNING'}, 'Cannot frame selection: %s' % exc)
            return {'CANCELLED'}
        after = None
        if rv3d is not None:
            after = [list(rv3d.view_location), float(rv3d.view_distance)]
        _log_call(self.bl_idname, 'framed', before=before, after=after)
        return {'FINISHED'}


class UEI_OT_ToggleOverlays(_ObjectViewOnly, bpy.types.Operator):
    bl_idname = 'uei.toggle_overlays'
    bl_label = 'UE: Toggle Overlays (Game View Approximation)'
    bl_description = (
        'Toggle Blender viewport overlays. This is a Game View approximation only: '
        'it does not change visibility, rendering or UE game view logic'
    )
    bl_options = {'INTERNAL'}

    def execute(self, context):
        space = context.space_data
        if not hasattr(space, 'overlay') or space.overlay is None:
            _log_call(self.bl_idname, 'unavailable')
            self.report({'WARNING'}, 'Overlay settings unavailable in this viewport')
            return {'CANCELLED'}
        space.overlay.show_overlays = not space.overlay.show_overlays
        _log_call(self.bl_idname, 'toggled', show_overlays=bool(space.overlay.show_overlays))
        if context.area is not None:
            context.area.tag_redraw()
        return {'FINISHED'}


class UEI_OT_AuditKeymaps(bpy.types.Operator):
    bl_idname = 'uei.audit_keymaps'
    bl_label = 'UE: Audit Keymaps'
    bl_description = 'Read-only report of this add-on bindings and conflicting Blender bindings'
    bl_options = {'INTERNAL'}

    filepath: StringProperty(
        name='Report file',
        description='Optional JSON path; empty means print to the console only',
        default='',
        subtype='FILE_PATH',
    )

    def execute(self, context):
        report = diagnostics.audit(context)
        text = diagnostics.format_text(report)
        print("[uei] " + json.dumps(report, ensure_ascii=False, sort_keys=True))
        print(text)
        if self.filepath:
            try:
                with open(bpy.path.abspath(self.filepath), 'w', encoding='utf-8') as handle:
                    json.dump(report, handle, ensure_ascii=False, indent=1)
                text = "Audit written to " + self.filepath
            except OSError as exc:
                self.report({'WARNING'}, 'Cannot write audit: %s' % exc)
        conflicts = sum(len(entry['conflict']) for entry in report['conflicts'])
        self.report({'INFO'}, 'Audit done: %d own items, %d conflicts' % (report['installed_count'], conflicts))
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# self test (K01 style lifecycle check, safe to run any time)
# ---------------------------------------------------------------------------
def _fake_rv3d(rotation=None, location=None, distance=10.0):
    return types.SimpleNamespace(
        view_rotation=rotation or Quaternion((1.0, 0.0, 0.0, 0.0)),
        view_location=location or Vector((0.0, 0.0, 0.0)),
        view_distance=distance,
        view_perspective='PERSP',
        update=lambda: None,
    )


def _math_tests():
    from . import preferences

    results = []
    mock = types.SimpleNamespace(
        enable_object_mode_hotkeys=True,
        enable_focus_f=True,
        enable_overlay_g=True,
        enable_alt_navigation=True,
        enable_rmb_fly=True,
    )
    rv3d = _fake_rv3d()
    navigation.look(rv3d, 200.0, 0.0, 0.25, False)
    ok = abs(rv3d.view_rotation.rotation_difference(_fake_rv3d().view_rotation).angle) > 0.0
    results.append(('look changes rotation', ok))

    rv3d = _fake_rv3d()
    navigation.look(rv3d, 0.0, -100000.0, 0.25, False)
    forward = navigation.view_forward(rv3d)
    results.append(('pitch clamped', forward.z <= math.sin(navigation.PITCH_LIMIT) + 1e-4))

    rv3d = _fake_rv3d()
    navigation.dolly(rv3d, 100.0)
    results.append(('dolly in reduces distance', rv3d.view_distance < 10.0))
    navigation.dolly(rv3d, -100000.0)
    results.append(('dolly bounded', rv3d.view_distance <= 1e6))

    rv3d = _fake_rv3d()
    navigation.pan(rv3d, 100.0, 0.0, 800, 600)
    results.append(('pan moves pivot', rv3d.view_location.length > 0.0))

    rv3d = _fake_rv3d()
    v = navigation.fly_velocity(rv3d, {'W'}, 2.0)
    results.append(('W flies toward -Z', v.z < 0.0 and abs(v.length - 2.0) < 1e-4))
    v = navigation.fly_velocity(rv3d, {'E'}, 1.0)
    results.append(('E flies up', v.z > 0.0))
    v = navigation.fly_velocity(rv3d, {'Q'}, 1.0)
    results.append(('Q flies down', v.z < 0.0))
    v = navigation.fly_velocity(rv3d, {'D'}, 1.0)
    results.append(('D strafes right', v.x > 0.0))
    v = navigation.fly_velocity(rv3d, {'W', 'E'}, 1.0)
    results.append(('diagonal velocity normalised?', v.length <= math.sqrt(2.0) + 1e-4))
    # 0.2.6: Edit Mesh sessions normalize combined keys (W+Q keeps unit speed).
    v = navigation.fly_velocity(rv3d, {'W', 'Q'}, 1.0, normalize=True)
    results.append(('edit mesh diagonal normalized (W+Q = 1.0)',
                    abs(v.length - 1.0) < 1e-4 and v.z < 0.0))
    v = navigation.fly_velocity(rv3d, {'D', 'Q'}, 1.0, normalize=True)
    results.append(('edit mesh diagonal normalized (D+Q)',
                    abs(v.length - 1.0) < 1e-4 and v.x > 0.0 and v.z < 0.0))
    return results, mock


def _keymap_cycle(prefs_like, cycles=20):
    """Enable/disable the keymap blocks repeatedly and verify cleanliness."""
    results = []
    observed = []
    for index in range(cycles):
        prefs_like.enable_object_mode_hotkeys = True
        prefs_like.enable_focus_f = True
        prefs_like.enable_overlay_g = True
        prefs_like.enable_alt_navigation = True
        prefs_like.enable_rmb_fly = True
        prefs_like.enable_edit_mesh_wasd_fly = True
        prefs_like.enable_edit_mesh_industry_keys = True
        count_on = keymaps.sync(prefs_like)
        observed.append(count_on)
        prefs_like.enable_object_mode_hotkeys = False
        prefs_like.enable_focus_f = False
        prefs_like.enable_overlay_g = False
        prefs_like.enable_alt_navigation = False
        prefs_like.enable_rmb_fly = False
        prefs_like.enable_edit_mesh_wasd_fly = False
        prefs_like.enable_edit_mesh_industry_keys = False
        count_off = keymaps.sync(prefs_like)
        observed.append(count_off)
    expected_on = 17  # 10 (0.2.0) + Mesh RMB + Q/W/E/R + Ctrl+E + Ctrl+Shift+E
    results.append(('installed item count == %d' % expected_on, all(v == expected_on for v in observed[0::2])))
    results.append(('all cycles clean', all(v == 0 for v in observed[1::2])))
    results.append(('no duplicate chords', not keymaps.duplicates()))
    return results, observed


class UEI_OT_SelfTest(bpy.types.Operator):
    bl_idname = 'uei.self_test'
    bl_label = 'UE: Self Test'
    bl_description = 'Run the built-in lifecycle/math self test and print a JSON result'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        from . import preferences

        prefs = preferences.get(context)
        snapshot_before = keymaps.snapshot_user_bindings()
        real_state = None
        if prefs is not None:
            real_state = (
                prefs.enable_object_mode_hotkeys,
                prefs.enable_focus_f,
                prefs.enable_overlay_g,
                prefs.enable_alt_navigation,
                prefs.enable_rmb_fly,
                prefs.enable_edit_mesh_wasd_fly,
                prefs.enable_edit_mesh_industry_keys,
            )
        math_results, mock = _math_tests()
        cycle_results, observed = _keymap_cycle(mock)
        keymaps.remove()
        if prefs is not None:
            keymaps.sync(prefs)
        snapshot_after = keymaps.snapshot_user_bindings()
        results = math_results + cycle_results
        results.append(('user/default keymaps unchanged', snapshot_before == snapshot_after))
        payload = {
            'blender': bpy.app.version_string,
            'results': [{'name': name, 'pass': bool(ok)} for name, ok in results],
            'cycle_counts': observed,
            'failed': [name for name, ok in results if not ok],
        }
        print("[uei] SELF TEST " + json.dumps(payload, ensure_ascii=False))
        self.report(
            {'INFO'},
            'Self test: %d/%d passed' % (len(results) - len(payload['failed']), len(results)),
        )
        return {'FINISHED'}


class UEI_OT_OpenPreferences(bpy.types.Operator):
    bl_idname = 'uei.open_preferences'
    bl_label = 'UE: Open Preferences'
    bl_description = 'Show this add-on in the Preferences editor'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        try:
            bpy.ops.preferences.addon_show(module=__package__)
        except (RuntimeError, TypeError, AttributeError) as exc:
            self.report({'WARNING'}, 'Cannot open preferences: %s' % exc)
            return {'CANCELLED'}
        return {'FINISHED'}


CLASSES = (
    UEI_OT_SwitchTool,
    UEI_OT_EditMeshTool,
    UEI_OT_EditMeshEdgeMenu,
    UEI_OT_FocusSelected,
    UEI_OT_ToggleOverlays,
    UEI_OT_AuditKeymaps,
    UEI_OT_SelfTest,
    UEI_OT_OpenPreferences,
)
