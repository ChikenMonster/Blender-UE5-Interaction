# SPDX-FileCopyrightText: 2026 Chiken_Monster
# SPDX-License-Identifier: GPL-3.0-or-later
"""Add-on preferences.

Every UE-style behaviour is opt-in.  Preferences are intentionally flat and
bounded so that a bad value can never produce an unbounded fly speed, a NaN
quaternion or an infinite loop.  Changing any switch triggers
:func:`keymaps.sync` through ``update`` callbacks, which is idempotent.
"""
import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty


def _refresh_keymaps(self, context):
    """Idempotent keymap re-sync; never let a failure break the UI."""
    from . import keymaps

    try:
        keymaps.sync(self)
    except Exception as exc:  # pragma: no cover - defensive
        print("[uei] keymap refresh failed:", exc)


class UEI_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    # --- Object mode tool keys -------------------------------------------
    enable_object_mode_hotkeys: BoolProperty(
        name="Q/W/E/R tool keys (Object Mode)",
        description=(
            "Map Q=Select, W=Move, E=Rotate, R=Scale to Blender's active tools. "
            "Only active in Object Mode of a 3D Viewport; Edit Mode keeps native keys"
        ),
        default=False,
        update=_refresh_keymaps,
    )
    enable_focus_f: BoolProperty(
        name="F focus selected",
        description="Map F to frame the selection (no selection: keep view and report)",
        default=True,
        update=_refresh_keymaps,
    )
    enable_overlay_g: BoolProperty(
        name="G overlay toggle (UE Game View approximation)",
        description=(
            "Map G to toggling viewport overlays. This only hides Blender overlays; "
            "it is NOT UE Game View and does not change visibility or rendering"
        ),
        default=True,
        update=_refresh_keymaps,
    )

    # --- Navigation ------------------------------------------------------
    enable_alt_navigation: BoolProperty(
        name="Alt + mouse navigation",
        description="Alt+LMB orbit, Alt+MMB pan, Alt+RMB dolly (perspective and ortho)",
        default=False,
        update=_refresh_keymaps,
    )
    enable_rmb_fly: BoolProperty(
        name="RMB look + WASD fly",
        description=(
            "Hold RMB in the Object Mode perspective viewport to look around and fly "
            "with W/A/S/D and Q/E. A quick RMB click is forwarded to Blender's context menu"
        ),
        default=False,
        update=_refresh_keymaps,
    )
    enable_edit_mesh_wasd_fly: BoolProperty(
        name="Edit Mesh RMB + WASD/QE fly",
        description=(
            "In Mesh Edit Mode only: hold RMB to steer the view and fly with W/A/S/D, "
            "plus Q/E for world-Z down/up (same logic as Object Mode, combined keys are "
            "speed-normalized). Outside the RMB flight session Q/E keep their Edit Mesh "
            "tool mappings. Alt+mouse navigation is NOT adapted in Edit Mode; the mouse "
            "wheel adjusts the shared flight-speed multiplier (same value as Object Mode)"
        ),
        default=False,
        update=_refresh_keymaps,
    )
    enable_edit_mesh_industry_keys: BoolProperty(
        name="Edit Mesh industry keys (Q/W/E/R + Ctrl+E)",
        description=(
            "Mesh Edit Mode only, opt-in: Q/W/E/R switch the Select/Move/Rotate/Scale tools and "
            "Ctrl+E activates the context sensitive Extrude Region tool (direction defaults "
            "to XYZ each activation; the tool header keeps the manual Normal/XYZ switch). "
            "Ctrl+Shift+E opens Blender's native Edge Menu. It overrides the native "
            "Edit Mode E=extrude and Ctrl+E=Edge Menu; Ctrl+B, 1/2/3, F, G and S keep their "
            "Blender defaults"
        ),
        default=False,
        update=_refresh_keymaps,
    )

    # --- Tuning ----------------------------------------------------------
    fly_base_speed: FloatProperty(
        name="Fly base speed",
        description="World units per second at 1.0x speed multiplier",
        default=5.0,
        min=0.05,
        max=100.0,
        subtype='UNSIGNED',
    )
    fly_speed_multiplier: FloatProperty(
        name="Fly speed multiplier",
        description="Runtime multiplier changed by RMB + mouse wheel (1.0x to 20.0x)",
        default=1.0,
        min=1.0,
        max=20.0,
        subtype='UNSIGNED',
    )
    look_sensitivity: FloatProperty(
        name="Look sensitivity",
        description="Degrees of rotation per mouse pixel while holding RMB",
        default=0.25,
        min=0.01,
        max=3.0,
        subtype='UNSIGNED',
    )
    invert_look_y: BoolProperty(
        name="Invert vertical look",
        description="Invert the vertical look direction",
        default=False,
    )
    drag_threshold_px: IntProperty(
        name="Drag threshold (px)",
        description="RMB movement below this distance is treated as a click (context menu)",
        default=5,
        min=0,
        max=50,
    )
    click_timeout_ms: IntProperty(
        name="Click timeout (ms)",
        description="RMB released within this time and under the drag threshold counts as a click",
        default=250,
        min=50,
        max=1000,
    )

    # ---------------------------------------------------------------------
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = False
        col = layout.column()

        box = col.box()
        box.label(text="Object Mode tools (3D View only)", icon='TOOL_SETTINGS')
        box.column().prop(self, "enable_object_mode_hotkeys")
        sub = box.column()
        sub.enabled = self.enable_object_mode_hotkeys
        sub.prop(self, "enable_focus_f")
        sub.prop(self, "enable_overlay_g")

        box = col.box()
        box.label(text="Viewport navigation", icon='VIEW3D')
        box.prop(self, "enable_alt_navigation")
        box.prop(self, "enable_rmb_fly")

        box = col.box()
        box.label(text="Mesh Edit Mode (opt-in)", icon='EDITMODE_HLT')
        box.prop(self, "enable_edit_mesh_wasd_fly")
        box.label(text="  RMB flight: W/A/S/D + Q/E (down/up) + mouse look, wheel = speed")
        box.prop(self, "enable_edit_mesh_industry_keys")
        sub = box.column()
        sub.enabled = self.enable_edit_mesh_industry_keys
        sub.label(text="  Q/W/E/R = Select/Move/Rotate/Scale tool")
        sub.label(text="  Ctrl+E = context sensitive Extrude Region tool (direction defaults to XYZ)")
        sub.label(text="  Ctrl+Shift+E = native Edge Menu (conflict-free)")
        sub.label(text="  Overrides native E=extrude / Ctrl+E=Edge Menu (reversible)")
        sub.label(text="  Ctrl+B, 1/2/3, F, G, S keep Blender defaults")

        box = col.box()
        box.label(text="Tuning", icon='PREFERENCES')
        box.prop(self, "fly_base_speed")
        box.prop(self, "fly_speed_multiplier")
        box.prop(self, "look_sensitivity")
        box.prop(self, "invert_look_y")
        box.prop(self, "drag_threshold_px")
        box.prop(self, "click_timeout_ms")

        box = col.box()
        box.label(text="Safety", icon='LOCKED')
        box.label(text="Hotkeys are opt-in; disabling removes only this add-on's items.")
        box.label(text="Edit Mode: only the optional RMB fly and industry key subset are added;")
        box.label(text="closing the switches restores native E/G/F/Q/W/R/Ctrl+E/Edge Menu.")
        box.label(text="All non-3D-View editors are never touched.")
        row = box.row()
        row.operator("uei.audit_keymaps", icon='ZOOM_ALL')
        row.operator("uei.self_test", icon='CHECKMARK')


def get(context=None):
    """Return the preferences instance or ``None`` (never raise)."""
    context = context or bpy.context
    for pkg in (__package__,):
        addon = context.preferences.addons.get(pkg)
        if addon is not None:
            return addon.preferences
    return None
