"""Record measured moving-throw, animation and replication checks."""
import datetime,hashlib,json
from pathlib import Path
import unreal as u

tmv_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
tmv_reports={}
for name,count in [('movement',10),('movement-network',10),('shoulders',9),('standalone',11)]:
    data=json.loads((tmv_root/f'Artifacts/Throw/{name}.json').read_text())
    assert data['passed'] and len(data['results'])==count,(name,data.get('error'))
    tmv_reports[name]=data['results']
assert json.loads((tmv_root/'Artifacts/Throw/movement-suite.json').read_text())['passed']
tmv_build=(tmv_root/'Artifacts/Throw/movement-build.log').read_bytes()
assert 'Result: Succeeded' in tmv_build.decode('utf-16' if tmv_build.startswith(b'\xff\xfe') else 'utf-8-sig')
tmv_paths=['src/Source/LyraGame/Crusader/CRThrowable.h','src/Source/LyraGame/Crusader/CRThrowable.cpp',
           'src/Source/LyraGame/Baseline/BaselineCharacterMovement.cpp','src/Source/LyraGame/Baseline/BaselineEquipment.cpp',
           'src/Source/LyraEditor/Crusader/CRBlueprintTools.cpp','Scripts/Configure-Throw.py',
           'src/Content/Blueprints/SandboxCharacter_CMC_ABP.uasset']
tmv_result=dict(passed=True,validated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=tmv_reports,
    build='Artifacts/Throw/movement-build.log',
    scope='Standalone and owning multiplayer client: eight movement directions, moving feet, aim hand, live trajectory, turning/hand swap, release without stopping and current-position launch. Existing stationary shoulder, throw, smoke, damage, interruption and armed-roll checks.',
    captures=['Artifacts/Throw/ThrowWalkingRight.png','Artifacts/Throw/ThrowWalkingLeft.png'],
    hashes={p:hashlib.sha256((tmv_root/p).read_bytes()).hexdigest() for p in tmv_paths})
(tmv_root/'resources/ThrowMovementValidation.json').write_text(json.dumps(tmv_result,indent=2)+'\n')
tmv_previous=json.loads((tmv_root/'resources/ThrowValidation.json').read_text())
tmv_previous['movement_update']='resources/ThrowMovementValidation.json'
(tmv_root/'resources/ThrowValidation.json').write_text(json.dumps(tmv_previous,indent=2)+'\n')
print('THROW_MOVEMENT_VALIDATED',sum(len(v) for v in tmv_reports.values()),'checks')
