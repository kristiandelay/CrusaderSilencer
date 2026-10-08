"""Record the leg-pose regression and the source/animation assets that fixed it."""
import datetime,hashlib,json
from pathlib import Path
import unreal as u

rlf_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
rlf_bp=u.load_asset('/Game/Blueprints/SandboxCharacter_CMC_ABP')
assert not u.CRBlueprintTools.has_blueprint_errors(rlf_bp)
assert 'OUT LocomotionCorrectionBypassWeight' in u.CRBlueprintTools.describe_blueprint(rlf_bp)
rlf_animations=json.loads((rlf_root/'resources/RollAnimations.json').read_text())
assert len(rlf_animations)==8 and max(row['maximum_baked_foot_ik_error_cm'] for row in rlf_animations)<.01
rlf_checks={}
for name,path,count in [('standalone_poses','Roll/Legs/validation.json',24),('network_poses','Roll/Legs/network.json',32),('getup_continuity','PhysicalTests/getup-continuity.json',4)]:
    result=json.loads((rlf_root/'Artifacts'/path).read_text())
    assert result['passed'] and len(result['results'])==count,(name,result.get('error'))
    rlf_checks[name]=dict(path='Artifacts/'+path,results=result['results'])
rlf_build=(rlf_root/'Artifacts/Roll/Legs/build.log').read_bytes()
assert 'Result: Succeeded' in rlf_build.decode('utf-16' if rlf_build.startswith(b'\xff\xfe') else 'utf-8-sig')
rlf_paths=['src/Source/LyraGame/Baseline/BaselinePhysicalInteraction.cpp','src/Source/LyraGame/Baseline/BaselinePhysicalInteraction.h','src/Source/LyraEditor/Crusader/CRBlueprintTools.cpp','src/Content/Blueprints/SandboxCharacter_CMC_ABP.uasset']
rlf_paths += [str(p.relative_to(rlf_root)).replace('\\','/') for p in (rlf_root/'src/Content/Crusader/Movement/Roll').rglob('*.uasset')]
rlf_hashes={path:hashlib.sha256((rlf_root/path).read_bytes()).hexdigest() for path in rlf_paths}
rlf_before=json.loads((rlf_root/'Artifacts/Roll/Legs/comparison.json').read_text())
rlf_result=dict(passed=True,validated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),cause='Unretargeted IK foot bones were far from the animated feet; standing leg IK straightened the knees during a full-body roll.',fix='Bake IK feet from FK feet and use the existing full-body pre-correction pose for rolls and get-ups. Restore locomotion corrections after rolling.',maximum_baked_ik_error_cm=max(row['maximum_baked_foot_ik_error_cm'] for row in rlf_animations),maximum_source_knee_error_degrees=max(row['source_error'] for row in rlf_checks['standalone_poses']['results']),checks=rlf_checks,before_after_comparison=rlf_before,build='Artifacts/Roll/Legs/build.log',screenshots='Artifacts/Roll/Legs',hashes=rlf_hashes)
(rlf_root/'resources/RollLegValidation.json').write_text(json.dumps(rlf_result,indent=2)+'\n')
rlf_previous=json.loads((rlf_root/'resources/RollValidation.json').read_text())
rlf_previous['leg_pose_fix_validation']='resources/RollLegValidation.json'
(rlf_root/'resources/RollValidation.json').write_text(json.dumps(rlf_previous,indent=2)+'\n')
print('ROLL_LEG_FIX_VALIDATED',60,'pose/network/get-up cases')
