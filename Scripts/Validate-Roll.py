"""Validate the authored roll assets and record current gameplay evidence."""
import json,hashlib,datetime
from pathlib import Path
import unreal as u

rv_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
rv_animations=json.loads((rv_root/'resources/RollAnimations.json').read_text())
assert len(rv_animations)==8
rv_skeleton=u.load_asset('/Game/Characters/UEFN_Mannequin/Meshes/SKM_UEFN_Mannequin').get_editor_property('skeleton')
rv_assets=[]
for row in rv_animations:
    seq=u.load_asset(row['animation']);montage=u.load_asset(row['montage'])
    assert seq and montage and seq.get_editor_property('skeleton')==rv_skeleton
    assert seq.get_editor_property('enable_root_motion')
    assert montage.get_editor_property('skeleton')==rv_skeleton
    assert len(montage.get_editor_property('slot_anim_tracks'))==1
    rv_assets.extend([seq.get_path_name(),montage.get_path_name()])
for path in ['/Game/Blueprints/SandboxCharacter_CMC','/Game/Crusader/Characters/B_CRTraversalPawn']+['/Game/Crusader/AI/B_'+role for role in ['GuardRifle','GuardPistol','GuardShotgun','Civilian']]:
    bp=u.load_asset(path);assert bp and not u.CRBlueprintTools.has_blueprint_errors(bp),path
    roll=u.get_default_object(bp.generated_class()).roll
    assert [m.get_path_name() for m in roll.get_editor_property('montages')]==[r['montage'] for r in rv_animations]
    assert abs(roll.get_editor_property('play_rate')-1.15)<.001
    assert abs(roll.get_editor_property('recovery_time')-.55)<.001
    rv_assets.append(bp.get_path_name())
rv_action=u.load_asset('/Game/Baseline/Input/IA_Roll')
assert len(rv_action.get_editor_property('triggers'))==1 and isinstance(rv_action.get_editor_property('triggers')[0],u.InputTriggerPressed)
rv_mapping=u.load_asset('/Game/Baseline/Input/IMC_Baseline')
rv_keys=[e.get_editor_property('key').export_text() for e in rv_mapping.get_editor_property('default_key_mappings').get_editor_property('mappings') if e.get_editor_property('action')==rv_action]
assert set(rv_keys)=={'LeftAlt','Gamepad_DPad_Right'},rv_keys
rv_abilities=u.load_asset('/Game/Crusader/System/AbilitySet_CRTraversal').get_editor_property('granted_gameplay_abilities')
assert sum(e.get_editor_property('ability')==u.CRRollAbility.static_class() for e in rv_abilities)==1
rv_inputs=u.load_asset('/Game/Crusader/System/InputConfig_CRTraversal').get_editor_property('ability_input_actions')
assert sum(e.get_editor_property('input_action')==rv_action for e in rv_inputs)==1
for path in ['/Game/Crusader/Movement/Roll/IK_RollPack','/Game/Crusader/Movement/Roll/RTG_RollPack_to_GASP','/Game/Baseline/Input/IA_Roll','/Game/Baseline/Input/IMC_Baseline','/Game/Crusader/System/AbilitySet_CRTraversal','/Game/Crusader/System/InputConfig_CRTraversal']:
    asset=u.load_asset(path);assert asset,path
    rv_assets.append(asset.get_path_name())
rv_reports={}
for name,relative in [('standalone','Roll/standalone.json'),('network','Roll/network.json'),('interactions','Roll/interactions.json'),('slide_combat','SlideCadence/combat.json'),('traversal','Roll/Traversal/result.json')]:
    report=json.loads((rv_root/'Artifacts'/relative).read_text());assert report['passed'],(name,report.get('error'))
    rv_reports[name]=dict(path='Artifacts/'+relative,cases=len(report['results']),results=report['results'])
rv_build=(rv_root/'Artifacts/Roll/build.log').read_bytes()
assert 'Result: Succeeded' in rv_build.decode('utf-16' if rv_build.startswith(b'\xff\xfe') else 'utf-8-sig')
rv_hashes={str(p.relative_to(rv_root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in [rv_root/'src/Source/LyraGame/Crusader/CRRoll.h',rv_root/'src/Source/LyraGame/Crusader/CRRoll.cpp']}
rv_report=dict(passed=True,validated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),pack='https://www.fab.com/listings/8e1f3fc0-fee5-44f8-963e-f13e2fb572cf',bindings=rv_keys,play_rate=1.15,recovery_seconds=.55,assets=rv_assets,native_hashes=rv_hashes,editor_build='Artifacts/Roll/build.log',visual_capture='Artifacts/Roll/RollForward.png',checks=rv_reports,scope='Editor standalone and two-player listen server; packaged/dedicated-server and adverse-network qualification not run.')
(rv_root/'resources/RollValidation.json').write_text(json.dumps(rv_report,indent=2)+'\n')
print('ROLL_VALIDATED',len(rv_assets),'assets',sum(r['cases'] for r in rv_reports.values()),'gameplay cases')
