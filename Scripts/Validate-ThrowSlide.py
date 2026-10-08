"""Record slide-throw integration and regression results from real PIE input."""
import datetime,hashlib,json
from pathlib import Path
import unreal as u

tsv_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
tsv_reports={}
for path,count in [('Throw/slide.json',10),('Throw/slide-network.json',10),('SlideCadence/standalone.json',6),
                   ('SlideCadence/network.json',5),('SlideCadence/combat.json',6),('Throw/movement.json',10),('Throw/standalone.json',11)]:
    data=json.loads((tsv_root/'Artifacts'/path).read_text())
    assert data['passed'] and len(data['results'])==count,(path,data.get('error'))
    tsv_reports[path]=data['results']
assert json.loads((tsv_root/'Artifacts/Throw/slide-suite.json').read_text())['passed']
tsv_build=(tsv_root/'Artifacts/Throw/slide-build.log').read_bytes()
assert 'Result: Succeeded' in tsv_build.decode('utf-16' if tsv_build.startswith(b'\xff\xfe') else 'utf-8-sig')
tsv_paths=['src/Source/LyraGame/Crusader/CRThrowable.cpp','src/Source/LyraGame/Crusader/CRTraversalCharacter.cpp',
           'src/Source/LyraGame/Baseline/BaselineCharacterMovement.cpp','src/Source/LyraGame/Baseline/BaselinePhysicalInteraction.cpp',
           'src/Source/LyraEditor/Crusader/CRBlueprintTools.cpp','Scripts/Configure-Throw.py',
           'src/Content/Blueprints/SandboxCharacter_CMC_ABP.uasset']
tsv_result=dict(passed=True,validated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=tsv_reports,
    build='Artifacts/Throw/slide-build.log',
    scope='Standalone and owning network client: aim before/during slide, grenade/smoke, both hands, shoulder swap, sideways torso aim, slide leg pose, one replicated release, cancel while sliding and aim through slide exit. Slide cadence/prediction, firearm sliding, walking throws and interruption regression checks.',
    hashes={p:hashlib.sha256((tsv_root/p).read_bytes()).hexdigest() for p in tsv_paths})
(tsv_root/'resources/ThrowSlideValidation.json').write_text(json.dumps(tsv_result,indent=2)+'\n')
tsv_previous=json.loads((tsv_root/'resources/ThrowValidation.json').read_text());tsv_previous['slide_update']='resources/ThrowSlideValidation.json'
(tsv_root/'resources/ThrowValidation.json').write_text(json.dumps(tsv_previous,indent=2)+'\n')
print('SLIDE_THROWS_VALIDATED',sum(len(v) for v in tsv_reports.values()),'checks')
