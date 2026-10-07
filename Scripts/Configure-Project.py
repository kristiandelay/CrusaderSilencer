"""Enable the audited sample dependencies while retaining Lyra's project settings."""
import json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
project = root / 'src/CrusaderSilencer.uproject'
data = json.loads(project.read_text())
sample = json.loads(Path(r'C:/Development/Game/GameAnimationSample/GameAnimationSample.uproject').read_text())
plugins = {p['Name']: p for p in data['Plugins']}
for plugin in sample['Plugins']:
    if plugin.get('Enabled'):
        plugins[plugin['Name']] = plugin
for name in ['PythonScriptPlugin', 'EditorScriptingUtilities']:
    plugins[name] = {'Name': name, 'Enabled': True, 'TargetAllowList': ['Editor']}
data['Plugins'] = list(plugins.values())
data['Description'] = 'Crusader Silencer - Lyra and GASP traversal integration'
project.write_text(json.dumps(data, indent=2) + '\n')
source = Path(r'C:/Development/Game/GameAnimationSample/Config/DefaultGameplayTags.ini').read_text()
target = root / 'src/Config/DefaultGameplayTags.ini'
text = target.read_text()
for line in source.splitlines():
    if line.startswith(('+GameplayTagList=', '+GameplayTagRedirects=')) and line not in text:
        text += '\n' + line
target.write_text(text + '\n')
print('Configured project plugins and GASP gameplay tags')

engine_file = root / 'src/Config/DefaultEngine.ini'
engine = engine_file.read_text()
if '; CR GASP integration settings' not in engine:
    sample_engine = Path(r'C:/Development/Game/GameAnimationSample/Config/DefaultEngine.ini').read_text()
    engine += '\n; CR GASP integration settings\n[/Script/Engine.CollisionProfile]\n'
    for line in sample_engine.splitlines():
        if line.startswith('+DefaultChannelResponses='):
            for old, new in [(1, 6), (2, 7), (3, 8)]:
                line = line.replace(f'ECC_GameTraceChannel{old},', f'ECC_GameTraceChannel{new},')
            engine += line + '\n'
        elif line.startswith('+Profiles=') and any(f'Name="{name}"' in line for name in ['ObstaclePreset', 'TraversalObjectPreset', 'CharacterCapsule']):
            engine += line + '\n'
    engine += '\n[/Script/Engine.DataDrivenConsoleVariableSettings]\n'
    engine += '\n'.join(line.replace('DefaultValueBool=True', 'DefaultValueBool=False') if 'NewGameplayCameraSystem.Enable' in line else line for line in sample_engine.splitlines() if line.startswith('+CVarsArray=')) + '\n'
    engine_file.write_text(engine)
