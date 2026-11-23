# SPDX-FileCopyrightText: 2026 Chiken_Monster
# SPDX-License-Identifier: GPL-3.0-or-later
"""Keymap lifecycle for this add-on.

Design rules (see docs/05_keymap_safety.md):

* only ``keyconfigs.addon`` is written - never ``user`` / ``default``;
* every created ``KeyMapItem`` is tracked in ``_ITEMS`` and removed on
  disable/unregister (idempotent, also removes items that were re-added by a
  previous failed install);
* the module never touches keymaps of other editors (Node/Text/UV/...).

Keymap scopes used here:

===================  ====================  ===================
Blender keymap       space / region        items
===================  ====================  ===================
``Object Mode``      EMPTY / WINDOW        Q W E R F G
``3D View``          VIEW_3D / WINDOW      Alt+LMB/MMB/RMB
``Object Mode``      EMPTY / WINDOW        RMB look / fly (Object Mode)
``Mesh``             EMPTY / WINDOW        RMB fly (Edit Mesh, W/A/S/D + Q/E)
===================  ====================  ===================

The ``Mesh`` item exists only when the separate ``enable_edit_mesh_wasd_fly``
switch is on and is owned by ``uei.edit_mesh_look`` (WASD + Q/E world-Z
vertical flight + mouse look; wheel adjusts the shared flight-speed
multiplier; no Alt navigation in Edit Mode).
"""
import bpy

# (keymap, keymap_item, human readable label)
_ITEMS = []

OWN_ID_PREFIX = "uei."

# Blender keymap names are official, stable names (verified in 5.2 GUI).
_KM_OBJECT = "Object Mode"
_KM_3DVIEW = "3D View"
_KM_MESH = "Mesh"
_OWNED_KEYMAPS = (_KM_OBJECT, _KM_3DVIEW, _KM_MESH)


# ---------------------------------------------------------------------------
# low level helpers
# ---------------------------------------------------------------------------
def _addon_kc():
    wm = getattr(bpy.context, "window_manager", None)
    if wm is None:
        return None
    return wm.keyconfigs.addon


def _keymap(kc, name, space_type, region_type='WINDOW'):
    km = kc.keymaps.get(name)
    if km is not None:
        return km
    return kc.keymaps.new(name=name, space_type=space_type, region_type=region_type)


def _items_of(km):
    try:
        return [kmi for kmi in km.keymap_items if kmi.idname.startswith(OWN_ID_PREFIX)]
    except (ReferenceError, RuntimeError):
        return []


def _remove_item(km, kmi):
    try:
        if kmi in km.keymap_items.values():
            km.keymap_items.remove(kmi)
    except (ReferenceError, RuntimeError, ValueError, TypeError):
        # The host can invalidate RNA items while a keymap is rebuilt.
        pass


def remove():
    """Remove every KeyMapItem this add-on created. Safe to call repeatedly."""
    while _ITEMS:
        km, kmi, _label = _ITEMS.pop()
        _remove_item(km, kmi)
    # Defensive sweep: pick up leftovers from an interrupted previous install.
    kc = _addon_kc()
    if kc is None:
        return
    for km in kc.keymaps:
        if km.name not in _OWNED_KEYMAPS:
            continue
        for kmi in _items_of(km):
            _remove_item(km, kmi)


def _new(km, label, idname, **kwargs):
    kmi = km.keymap_items.new(idname, **kwargs)
    _ITEMS.append((km, kmi, label))
    return kmi


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def sync(prefs=None):
    """Idempotent (re)installation of all enabled mappings."""
    if prefs is None:
        from . import preferences

        prefs = preferences.get()
    remove()
    if prefs is None:
        return 0

    kc = _addon_kc()
    if kc is None:  # background mode before a window manager exists
        return 0

    try:
        if prefs.enable_object_mode_hotkeys or prefs.enable_focus_f or prefs.enable_overlay_g:
            km_obj = _keymap(kc, _KM_OBJECT, 'EMPTY')
            if prefs.enable_object_mode_hotkeys:
                for key, tool in (
                    ('Q', 'SELECT'),
                    ('W', 'MOVE'),
                    ('E', 'ROTATE'),
                    ('R', 'SCALE'),
                ):
                    kmi = _new(
                        km_obj,
                        "Q/W/E/R tools",
                        "uei.switch_tool",
                        type=key,
                        value='PRESS',
                    )
                    kmi.properties.tool = tool
            if prefs.enable_focus_f:
                _new(km_obj, "F focus", "uei.focus_selected", type='F', value='PRESS')
            if prefs.enable_overlay_g:
                _new(km_obj, "G overlays", "uei.toggle_overlays", type='G', value='PRESS')

        if prefs.enable_alt_navigation or prefs.enable_rmb_fly:
            # 3D View keymap handles MMB/RMB chords (verified to win there in 5.2).
            km_view = _keymap(kc, _KM_3DVIEW, 'VIEW_3D')
            # Object Mode keymap is dispatched before the 3D View keymap for LMB
            # and plain RMB, so those two chords must live there to be reachable.
            km_obj_nav = _keymap(kc, _KM_OBJECT, 'EMPTY')
            if prefs.enable_alt_navigation:
                for keymap, button, nav, trigger in (
                    (km_obj_nav, 'LEFTMOUSE', 'ORBIT', 'CLICK_DRAG'),
                    (km_view, 'MIDDLEMOUSE', 'PAN', 'PRESS'),
                    (km_view, 'RIGHTMOUSE', 'DOLLY', 'PRESS'),
                ):
                    kmi = _new(
                        keymap,
                        "Alt %s nav" % button,
                        "uei.alt_navigate",
                        type=button,
                        value=trigger,
                        alt=True,
                    )
                    kmi.properties.nav = nav
            if prefs.enable_rmb_fly:
                _new(km_obj_nav, "RMB look/fly", "uei.rmb_look", type='RIGHTMOUSE', value='PRESS')

        # Separate, opt-in Edit Mesh entry: mode keymap "Mesh" dispatches before
        # the region context menu, exactly like "Object Mode" does for RMB.
        if prefs.enable_edit_mesh_wasd_fly:
            km_mesh = _keymap(kc, _KM_MESH, 'EMPTY')
            _new(km_mesh, "Edit Mesh RMB fly", "uei.edit_mesh_look", type='RIGHTMOUSE', value='PRESS')

        # Opt-in "industry partial" Edit Mesh tools: Q/W/E/R + Ctrl+E.
        # Mirrors Blender 5.2 Industry Compatible (wm.tool_set_by_id(cycle=True));
        # Ctrl+B / 1-2-3 / F / G / S are intentionally NOT registered.
        if prefs.enable_edit_mesh_industry_keys:
            km_mesh_tools = _keymap(kc, _KM_MESH, 'EMPTY')
            for key, tool, ctrl in (
                ('Q', 'SELECT', False),
                ('W', 'MOVE', False),
                ('E', 'ROTATE', False),
                ('R', 'SCALE', False),
                ('E', 'EXTRUDE', True),
            ):
                label = "Edit Mesh %s%s -> %s" % ('Ctrl+' if ctrl else '', key, tool)
                kmi = _new(
                    km_mesh_tools,
                    label,
                    "uei.edit_mesh_tool",
                    type=key,
                    value='PRESS',
                    ctrl=ctrl,
                )
                kmi.properties.tool = tool

            # Ctrl+Shift+E keeps the native Edge Menu reachable in Edit Mode, since
            # the industry mapping above moves Edge Menu off Ctrl+E. Blender 5.2 has
            # no Ctrl+Shift+E binding in Mesh / 3D View (runtime audited 2026-11-23;
            # only Text Editor "text.move" and Grease Pencil interpolate use it), so
            # this is a conflict-free addition. The operator opens Blender's own
            # VIEW3D_MT_edit_mesh_edges popup and only logs the invocation.
            kmi = _new(km_mesh_tools, "Edit Mesh Ctrl+Shift+E -> Edge Menu",
                       "uei.edit_mesh_edge_menu", type='E', value='PRESS', ctrl=True, shift=True)
    except Exception:
        remove()
        raise
    return count()


def count():
    return len(_ITEMS)


def describe():
    """Machine readable list of installed items (used by UI, audit, tests)."""
    rows = []
    for km, kmi, label in list(_ITEMS):
        try:
            rows.append(
                {
                    'label': label,
                    'keymap': km.name,
                    'type': kmi.type,
                    'value': kmi.value,
                    'idname': kmi.idname,
                    'alt': bool(kmi.alt),
                    'ctrl': bool(kmi.ctrl),
                    'shift': bool(kmi.shift),
                    'active': bool(kmi.active),
                }
            )
        except ReferenceError:
            continue
    return rows


def duplicates():
    """Return duplicated (keymap, type, value, modifiers) tuples, if any."""
    seen = {}
    dups = []
    for row in describe():
        key = (row['keymap'], row['type'], row['value'], row['alt'], row['ctrl'], row['shift'])
        if key in seen:
            dups.append(key)
        seen[key] = True
    return dups


# ---------------------------------------------------------------------------
# baseline helpers (read-only; used by diagnostics / tests)
# ---------------------------------------------------------------------------
def snapshot_user_bindings():
    """Hashable snapshot of the *non add-on* bindings that we must not change."""
    wm = getattr(bpy.context, "window_manager", None)
    if wm is None:
        return {}
    snap = {}
    for cfg_name in ('user', 'default'):
        kc = getattr(wm.keyconfigs, cfg_name, None)
        if kc is None:
            continue
        for km in kc.keymaps:
            if km.name not in _OWNED_KEYMAPS:
                continue
            rows = []
            for kmi in km.keymap_items:
                rows.append(
                    (kmi.type, kmi.value, kmi.idname, bool(kmi.alt), bool(kmi.ctrl), bool(kmi.shift))
                )
            snap[(cfg_name, km.name)] = sorted(rows)
    return snap
