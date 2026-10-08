"""Record keyboard and network verification of shoulder-dependent throwing."""
import datetime,hashlib,json
from pathlib import Path
import unreal as u
tsv_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
tsv_reports={}
for name in ['shoulders','shoulders-network']:
    d=json.loads((tsv_root/f'Artifacts/Throw/{name}.json').read_text())
    assert d['passed'] and len(d['results'])==9,(name,d.get('error'))
    tsv_reports[name]=d['results']
tsv_build=(tsv_root/'Artifacts/Throw/shoulder-build.log').read_bytes()
assert 'Result: Succeeded' in tsv_build.decode('utf-16' if tsv_build.startswith(b'\xff\xfe') else 'utf-8-sig')
tsv_sources=['src/Source/LyraGame/Crusader/CRThrowable.cpp','src/Source/LyraGame/Baseline/BaselineEquipment.cpp','Scripts/Prepare-ThrowShoulders.py']
tsv_result=dict(passed=True,validated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=tsv_reports,
    animations=json.loads((tsv_root/'resources/ThrowShoulderAnimations.json').read_text()),build='Artifacts/Throw/shoulder-build.log',
    scope='Standalone and owning client on a two-player listen server; both objects, both hands, preset shoulder and Q during aim, release hand lock and cancellation.',
    hashes={p:hashlib.sha256((tsv_root/p).read_bytes()).hexdigest() for p in tsv_sources})
(tsv_root/'resources/ThrowShoulderValidation.json').write_text(json.dumps(tsv_result,indent=2)+'\n')
tsv_existing=json.loads((tsv_root/'resources/ThrowValidation.json').read_text());tsv_existing['shoulder_update']='resources/ThrowShoulderValidation.json'
(tsv_root/'resources/ThrowValidation.json').write_text(json.dumps(tsv_existing,indent=2)+'\n')
tsv_settings=json.loads((tsv_root/'resources/ThrowSystem.json').read_text());tsv_settings['controls']['shoulder_hand']='Q (also while aiming)'
tsv_settings['throw_hand']='Selected shoulder: mirrored aim/release/grip and launch origin; hand locked during release.'
(tsv_root/'resources/ThrowSystem.json').write_text(json.dumps(tsv_settings,indent=2)+'\n')
print('THROW_SHOULDERS_VALIDATED',18,'gameplay cases')
