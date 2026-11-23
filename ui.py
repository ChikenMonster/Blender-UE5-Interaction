# SPDX-FileCopyrightText: 2026 Chiken_Monster
# SPDX-License-Identifier: GPL-3.0-or-later
"""N panel: runtime state, conflict summary and one-click disable."""
import bpy

from . import keymaps


class UEI_PT_Interaction(bpy.types.Panel):
    bl_label = 'UE5 Interaction'
    bl_idname = 'UEI_PT_interaction'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'UE Interaction'

    def draw(self, context):
        layout = self.layout
        addon = context.preferences.addons.get(__package__)
        if addon is None:
            layout.label(text='Add-on preferences unavailable', icon='ERROR')
            return
        prefs = addon.preferences

        box = layout.box()
        box.label(text='Object Mode tools', icon='TOOL_SETTINGS')
        row = box.row()
        row.prop(prefs, 'enable_object_mode_hotkeys', text='Q/W/E/R')
        box.label(text='  Q Select | W Move | E Rotate | R Scale')
        row = box.row()
        row.enabled = prefs.enable_object_mode_hotkeys
        row.prop(prefs, 'enable_focus_f', text='F Focus')
        row.prop(prefs, 'enable_overlay_g', text='G Overlay (approx.)')

        box = layout.box()
        box.label(text='Navigation', icon='VIEW3D')
        box.prop(prefs, 'enable_alt_navigation', text='Alt + mouse')
        box.prop(prefs, 'enable_rmb_fly', text='RMB look + WASD fly (Object Mode)')
        if prefs.enable_rmb_fly:
            box.label(text='  Wheel = speed, ESC = cancel, quick click = menu')
        sub = box.column()
        sub.prop(prefs, 'enable_edit_mesh_wasd_fly', text='Edit Mesh RMB + W/A/S/D + Q/E fly')
        if prefs.enable_edit_mesh_wasd_fly:
            sub.label(text='  Edit Mode: W/A/S/D + Q/E (down/up) + mouse look; wheel = speed')
            sub.label(text='  Combined keys are speed-normalized (diagonal not faster)')
            sub.label(text='  No Alt nav in Edit Mode; Q/E tools outside flight')
        sub.prop(prefs, 'enable_edit_mesh_industry_keys', text='Edit Mesh Q/W/E/R + Ctrl+E')
        if prefs.enable_edit_mesh_industry_keys:
            sub.label(text='  Q/W/E/R = tools, Ctrl+E = Extrude Region (default XYZ)')
            sub.label(text='  Ctrl+Shift+E = native Edge Menu')
            sub.label(text='  Overrides E=extrude / Ctrl+E=Edge Menu (reversible)')
            sub.label(text='  Ctrl+B / 1-2-3 / F / G / S stay native')
        box.prop(prefs, 'fly_speed_multiplier')

        info = layout.box()
        info.label(text='Runtime state', icon='INFO')
        info.label(text='Owned keymap items: %d' % keymaps.count())
        dupes = len(keymaps.duplicates())
        if dupes:
            info.label(text='Duplicate bindings: %d' % dupes, icon='ERROR')
        else:
            info.label(text='No duplicate bindings', icon='CHECKMARK')
        area = context.area
        if area is not None and area.type == 'VIEW_3D':
            space = context.space_data
            rv3d = getattr(space, 'region_3d', None)
            if rv3d is not None:
                info.label(text='Perspective: %s' % rv3d.view_perspective)
        info.label(text='Scope: 3D View / Object Mode + optional Mesh Edit fly')

        row = layout.row(align=True)
        row.operator('uei.self_test', icon='CHECKMARK')
        row.operator('uei.audit_keymaps', icon='ZOOM_ALL')
        layout.operator('uei.open_preferences', icon='PREFERENCES')


CLASSES = (UEI_PT_Interaction,)
