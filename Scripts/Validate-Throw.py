"""Persist measured throw gameplay, pose-height and armed-roll regression evidence."""
import datetime,hashlib,json
from pathlib import Path
import unreal as u
tv_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
# This records completed reports only; it can run while the user is playing.
tv_reports={}
for path,count in [('Throw/standalone.json',11),('Throw/network.json',3),('Roll/standalone.json',14),('Roll/network.json',8)]:
    data=json.loads((tv_root/'Artifacts'/path).read_text());assert data['passed'] and len(data['results'])==count,(path,data.get('error'))
    tv_reports[path]=data['results']
tv_build=(tv_root/'Artifacts/Throw/build.log').read_bytes()
assert 'Result: Succeeded' in tv_build.decode('utf-16' if tv_build.startswith(b'\xff\xfe') else 'utf-8-sig')
tv_sources=['src/Source/LyraGame/Crusader/CRThrowable.h','src/Source/LyraGame/Crusader/CRThrowable.cpp','src/Source/LyraGame/Baseline/BaselineEquipment.cpp','Scripts/Prepare-ThrowAnimations.py']
tv_result=dict(passed=True,validated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=tv_reports,
    build='Artifacts/Throw/build.log',animations=json.loads((tv_root/'resources/ThrowAnimations.json').read_text()),
    captures=['Artifacts/Throw/ThrowAimPose.png','Artifacts/Throw/GrenadeTrajectory.png','Artifacts/Throw/SmokeCloud.png'],
    weapon_during_roll='Visible and attached; fire/reload remain blocked',
    hashes={p:hashlib.sha256((tv_root/p).read_bytes()).hexdigest() for p in tv_sources})
(tv_root/'resources/ThrowValidation.json').write_text(json.dumps(tv_result,indent=2)+'\n')
tv_roll=json.loads((tv_root/'resources/RollValidation.json').read_text());tv_roll['weapon_visibility_update']='resources/ThrowValidation.json'
(tv_root/'resources/RollValidation.json').write_text(json.dumps(tv_roll,indent=2)+'\n')
print('THROW_VALIDATED',sum(len(v) for v in tv_reports.values()),'checks')
