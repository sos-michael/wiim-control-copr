"""Show DNF update instructions in the upstream settings panel."""
from pathlib import Path
import re

panels = [p for p in Path('UI').glob('SettingsWindow*.cs')
          if 'var checkUpdates = new ToggleSwitch' in p.read_text()]
if len(panels) != 1:
    raise SystemExit('Expected one application update panel')
panel, = panels
text = panel.read_text()


def replace_once(pattern, replacement):
    global text
    text, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f'Unexpected update panel in {panel}: {pattern}')


# Remove just the old controls and their handler. Preserve adjacent controls
# for firmware checks and network updates on newer upstream releases.
replace_once(r'^([ ]*)var checkUpdates = new ToggleSwitch[^\n]*\n'
             r'(?:[^\n]*\n){0,12}?^\1    finally \{ checkNow\.IsEnabled = true; \}\n^\1\};\n', '')
replace_once(r'^([ ]*)ToggleRow\("Check for new versions of Wiim Control", checkUpdates\),\n'
             r'^\1LabeledRow\(\$"You have version \{AppVersion\}", checkNow\),\n'
             r'^\1Muted\("When a new version is out, Wiim Control asks whether to download and install it\."\)',
             r'\1Muted($"You have version {AppVersion}. Updates are managed by your system."),\n'
             r'\1Muted("Use Software or run: dnf upgrade wiim-control")')
panel.write_text(text)
