"""Persist actual key-combination and client/server roll direction checks."""
import datetime,hashlib,json
from pathlib import Path
import unreal as u
rdv_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
rdv_checks={}
for name,count in [('standalone',25),('network',8)]:
    result=json.loads((rdv_root/f'Artifacts/Roll/Diagonal/{name}.json').read_text())
    assert result['passed'] and len(result['results'])==count,(name,result.get('error'))
    rdv_checks[name]=result['results']
rdv_build=(rdv_root/'Artifacts/Roll/Diagonal/build.log').read_bytes()
assert 'Result: Succeeded' in rdv_build.decode('utf-16' if rdv_build.startswith(b'\xff\xfe') else 'utf-8-sig')
rdv_paths=['src/Source/LyraGame/Crusader/CRRoll.cpp','src/Source/LyraEditor/Crusader/CRBlueprintTools.cpp','src/Source/LyraEditor/Crusader/CRBlueprintTools.h']
rdv_result=dict(passed=True,validated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),cause='GASP normalized diagonal input had squared length 0.9999999657714582; the old < 1 check incorrectly selected forward. Last-frame input also missed simultaneous presses.',fix='Use pending movement input before consumed input, and reject only effectively zero planar direction.',checks=rdv_checks,build='Artifacts/Roll/Diagonal/build.log',before='Artifacts/Roll/Diagonal/before.json',hashes={path:hashlib.sha256((rdv_root/path).read_bytes()).hexdigest() for path in rdv_paths})
(rdv_root/'resources/RollDirectionValidation.json').write_text(json.dumps(rdv_result,indent=2)+'\n')
rdv_original=json.loads((rdv_root/'resources/RollValidation.json').read_text());rdv_original['direction_fix_validation']='resources/RollDirectionValidation.json'
(rdv_root/'resources/RollValidation.json').write_text(json.dumps(rdv_original,indent=2)+'\n')
print('ROLL_DIRECTIONS_VALIDATED',33,'actual-input cases')
