# SPDX-FileCopyrightText: 2026 Chiken_Monster
# SPDX-License-Identifier: GPL-3.0-or-later
"""Blender UE5 Interaction - UE 5.8 Level Viewport style interaction for Blender.

Lifecycle only.  Business logic lives in the sibling modules:

* :mod:`preferences` - opt-in switches and bounded tuning values
* :mod:`keymaps`     - owned ``KeyMapItem`` lifecycle
* :mod:`operators`   - single shot tool / focus / overlay operators
* :mod:`navigation`  - modal Alt+mouse navigation and RMB look/WASD fly
* :mod:`diagnostics` - read-only conflict audit
* :mod:`ui`          - N panel
"""
import bpy

from . import diagnostics, keymaps, navigation, operators, preferences, ui

__version__ = "0.2.6"

MIN_BLENDER_VERSION = (5, 2, 0)

_CLASSES = (
    preferences.UEI_AddonPreferences,
    *operators.CLASSES,
    navigation.UEI_OT_AltNavigate,
    navigation.UEI_OT_RMBLook,
    navigation.UEI_OT_EditMeshLook,
    *ui.CLASSES,
)


def _deferred_sync():
    """One-shot re-sync for hosts that create the window manager late."""
    try:
        prefs = preferences.get()
        if prefs is not None:
            keymaps.sync(prefs)
    except Exception as exc:  # pragma: no cover - defensive
        print("[uei] deferred keymap sync failed:", exc)
    return None


def register():
    version = getattr(bpy.app, "version", (0, 0, 0))
    if tuple(version[:3]) < MIN_BLENDER_VERSION:
        print("[uei] warning: Blender %s is older than the supported 5.2 LTS" % bpy.app.version_string)
    for klass in _CLASSES:
        bpy.utils.register_class(klass)
    try:
        prefs = preferences.get()
        if prefs is not None:
            keymaps.sync(prefs)
    except Exception as exc:  # pragma: no cover - startup ordering
        print("[uei] initial keymap sync failed (will retry):", exc)
    try:
        bpy.app.timers.register(_deferred_sync, first_interval=0.25)
    except (ValueError, RuntimeError):
        pass


def unregister():
    # 1) stop modal owners first, 2) drop our keymap items, 3) unregister RNA.
    try:
        navigation.cancel_all()
    except Exception as exc:  # pragma: no cover
        print("[uei] cancel_all failed:", exc)
    keymaps.remove()
    for klass in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(klass)
        except (RuntimeError, ValueError) as exc:
            print("[uei] unregister_class failed:", exc)
