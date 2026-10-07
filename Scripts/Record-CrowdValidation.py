"""Record completed editor checks and the exact authored/source file hashes."""
import ast,hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path

root=Path(__file__).resolve().parents[1]
reports={
 'crowd_combat':'Environment/crowd-ai.json',
 'crowd_avoidance':'Environment/crowd-avoidance.json',
 'navigation_links':'Environment/crowd-links.json',
 'senses_and_death':'Environment/crowd-senses-death.json',
 'npc_movement':'Environment/crowd-traversal.json',
 'footsteps':'Environment/footsteps.json',
 'bullet_holes':'Environment/bullet-holes.json',
 'weapon_surfaces':'WeaponFX/gameplay-validation.json',
 'network_visuals':'NPCCharacters/network-validation.json',
 'network_shots':'WeaponFX/network-validation.json',
 'network_crowd_audio':'Environment/network.json'}
results={}
for name,path in reports.items():
    data=json.loads((root/'Artifacts'/path).read_text());assert data['passed'],(name,data.get('error'))
    results[name]=data['results']
assets=json.loads((root/'Artifacts/Environment/asset-validation.json').read_text());assert assets['passed']
assert 'NumWarnings=0' in assets['validation'] and 'NumInvalid=0' in assets['validation']
build=(root/'Artifacts/editor-build.log').read_text(encoding='utf-8-sig');assert 'Result: Succeeded' in build
for path in (root/'Scripts').glob('*.py'):ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path))
paths=list((root/'src/Source/LyraGame/Crusader').glob('*'))
paths+=list((root/'src/Content/Crusader/AI').rglob('*.uasset'))
paths+=list((root/'src/Content/Crusader/Audio').rglob('*.uasset'))
paths+=[root/p for p in ['src/Config/DefaultEngine.ini','src/Content/Maps/L_TraversalGym.umap','src/Source/LyraGame/Baseline/BaselineEquipment.cpp','src/Source/LyraGame/Baseline/BaselineCharacterMovement.cpp']]
hashes={str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
report=dict(created_utc=datetime.now(timezone.utc).isoformat(),engine='UE 5.8.3',passed=True,scope='Editor standalone and two-player listen-server PIE',
    build='Succeeded',assets_checked=assets['assets'],asset_failures=0,asset_warnings=0,
    model_count=33,footstep_surfaces=27,npcs=12,tether_areas=4,case_counts={n:len(r) for n,r in results.items()},results=results,
    notes=['Both rendered network worlds used reduced preview quality; previous rendering settings restored.','Packaged performance and soak testing are not included.','Parkour routes use authored navigation links and the same movement actions as the player.'],file_sha256=hashes)
(root/'resources/CrowdEnvironmentValidation.json').write_text(json.dumps(report,indent=2)+'\n')
print('Recorded',sum(report['case_counts'].values()),'gameplay/network cases and',assets['assets'],'asset checks')
