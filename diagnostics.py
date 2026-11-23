# SPDX-FileCopyrightText: 2026 Chiken_Monster
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only keymap / context diagnostics.

Nothing in this module mutates user configuration: it only reads the
keyconfigs and reports what *would* conflict with this add-on's bindings, so
the user can decide per key (docs/05_keymap_safety.md rule 3/4).
"""
import bpy

from . import keymaps

# The mappings the add-on can install, and the base keymaps they live in.
WATCHED = (
    ('Object Mode', 'Q', 'PRESS', False, 'select tool'),
    ('Object Mode', 'W', 'PRESS', False, 'move tool'),
    ('Object Mode', 'E', 'PRESS', False, 'rotate tool'),
    ('Object Mode', 'R', 'PRESS', False, 'scale tool'),
    ('Object Mode', 'F', 'PRESS', False, 'focus selected'),
    ('Object Mode', 'G', 'PRESS', False, 'overlay toggle'),
    ('3D View', 'LEFTMOUSE', 'PRESS', True, 'orbit'),
    ('3D View', 'MIDDLEMOUSE', 'PRESS', True, 'pan'),
    ('3D View', 'RIGHTMOUSE', 'PRESS', True, 'dolly'),
    ('3D View', 'RIGHTMOUSE', 'PRESS', False, 'look / fly'),
    ('Mesh', 'RIGHTMOUSE', 'PRESS', False, 'Edit Mesh RMB fly (W/A/S/D + Q/E, opt-in)'),
    ('Mesh', 'Q', 'PRESS', False, 'Edit Mesh Select tool (industry subset, opt-in)'),
    ('Mesh', 'W', 'PRESS', False, 'Edit Mesh Move tool (industry subset, opt-in)'),
    ('Mesh', 'E', 'PRESS', False, 'Edit Mesh Rotate tool (industry subset, opt-in; native E is extrude)'),
    ('Mesh', 'R', 'PRESS', False, 'Edit Mesh Scale tool (industry subset, opt-in; native R is rotate)'),
)


def _rows_of(km, key_type, value, alt):
    out = []
    try:
        items = list(km.keymap_items)
    except (ReferenceError, RuntimeError):
        return out
    for kmi in items:
        if kmi.type != key_type:
            continue
        if value and kmi.value != value:
            continue
        if bool(kmi.alt) != bool(alt):
            continue
        if kmi.ctrl or kmi.shift:
            continue
        out.append(
            {
                'idname': kmi.idname,
                'value': kmi.value,
                'active': bool(kmi.active),
                'own': kmi.idname.startswith(keymaps.OWN_ID_PREFIX),
            }
        )
    return out


def audit(context=None):
    """Return a JSON-serialisable conflict report (no side effects)."""
    context = context or bpy.context
    wm = getattr(context, 'window_manager', None)
    report = {
        'blender_version': bpy.app.version_string,
        'mode': getattr(context, 'mode', None),
        'area': getattr(getattr(context, 'area', None), 'type', None),
        'view_perspective': None,
        'installed_items': keymaps.describe(),
        'installed_count': keymaps.count(),
        'duplicates': keymaps.duplicates(),
        'conflicts': [],
        'notes': [],
    }
    space = getattr(context, 'space_data', None)
    rv3d = getattr(space, 'region_3d', None) if space is not None else None
    if rv3d is not None:
        report['view_perspective'] = rv3d.view_perspective

    for km_name, key_type, value, alt, meaning in WATCHED:
        entry = {'keymap': km_name, 'key': key_type, 'alt': alt, 'meaning': meaning, 'found': []}
        for cfg_name in ('active', 'user', 'default', 'addon'):
            kc = getattr(wm.keyconfigs, cfg_name, None) if wm is not None else None
            if kc is None:
                continue
            km = kc.keymaps.get(km_name)
            if km is None:
                continue
            for row in _rows_of(km, key_type, value, alt):
                row['config'] = cfg_name
                entry['found'].append(row)
        # Report only foreign (non add-on) bindings as conflicts.
        foreign = [r for r in entry['found'] if not r['own'] and r['config'] in ('active', 'user')]
        entry['conflict'] = sorted({r['idname'] for r in foreign})
        report['conflicts'].append(entry)

    if report['duplicates']:
        report['notes'].append('Duplicate add-on keymap items detected')
    if wm is not None and wm.keyconfigs.addon is None:
        report['notes'].append('keyconfigs.addon unavailable (background mode?)')
    return report


def format_text(report):
    lines = [
        "Blender UE5 Interaction - keymap audit",
        "Blender %s | mode=%s | area=%s | perspective=%s"
        % (
            report.get('blender_version'),
            report.get('mode'),
            report.get('area'),
            report.get('view_perspective'),
        ),
        "Installed add-on keymap items: %s" % report.get('installed_count'),
    ]
    for row in report.get('installed_items', []):
        lines.append(
            "  + %-22s %-10s %-9s %-12s alt=%s ctrl=%s shift=%s"
            % (
                row['keymap'],
                row['type'],
                row['value'],
                row['idname'],
                int(row['alt']),
                int(row['ctrl']),
                int(row['shift']),
            )
        )
    if report.get('duplicates'):
        lines.append("DUPLICATES: %s" % (report['duplicates'],))
    lines.append("Foreign bindings on the same chords:")
    for entry in report.get('conflicts', []):
        chord = ('Alt+' if entry['alt'] else '') + entry['key']
        found = ', '.join(entry['conflict']) if entry['conflict'] else '-'
        lines.append("  %-12s %-14s -> %s" % (entry['keymap'], chord, found))
    for note in report.get('notes', []):
        lines.append("NOTE: " + note)
    return "\n".join(lines)
