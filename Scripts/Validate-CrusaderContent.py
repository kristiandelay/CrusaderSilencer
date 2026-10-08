"""Validate imported NPCs, retarget catalog and authored effects dependencies."""
import json
from pathlib import Path
import unreal as u

assert not u.EditorLevelLibrary.get_pie_worlds(False)
root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
names=['ObsidianSentinel','RegalCommander','TheSteadfastOfficer','UrbanTrailblazer']
names += [r['name'] for r in json.loads((root/'resources/NPCAdditions.json').read_text()) if r.get('imported')]
paths=[];characters=[]
for name in names:
    folder='/Game/Crusader/Characters/'+name
    assets=u.EditorAssetLibrary.list_assets(folder,True,False)
    assert len(assets)>=10,(name,len(assets))
    paths+=assets
    mesh=u.load_asset(folder+'/'+name)
    assert u.SkeletalMeshEditorSubsystem.get_lod_count(mesh)==3
    pose=mesh.get_editor_property('skeleton').get_reference_pose()
    bones=list(pose.get_bone_names())
    for side in ['l','r']:
        for digit in ['thumb','index','middle','ring','pinky']:
            for i in range(1,4):assert u.Name(f'{digit}_{i:02}_{side}') in bones
    for bone in bones:
        assert abs(pose.get_ref_bone_pose(bone,u.AnimPoseSpaces.LOCAL).scale3d.x-1)<.001
    characters.append(dict(name=name,bones=len(bones),lods=3,assets=len(assets)))
paths+=u.EditorAssetLibrary.list_assets('/Game/Crusader/Effects',True,False)
paths+=['/Game/Blueprints/GM_Sandbox','/Game/Baseline/Animations/ABP_BaselineVisualRetarget','/Game/Weapons/B_Weapon','/Game/GameplayCueNotifies/GCN_CrusaderImpact','/Game/Maps/L_TraversalGym']
for kind in ['Rifle','Pistol','Shotgun']:
    paths+=[f'/Game/Baseline/Weapons/{kind}/B_WeaponInstance_{kind}',f'/Game/Baseline/Weapons/{kind}/GA_Weapon_Fire_{kind}'+('_Auto' if kind=='Rifle' else '')]
catalog=u.get_default_object(u.load_asset('/Game/Blueprints/GM_Sandbox').generated_class()).get_editor_property('VisualOverrides_Soft')
assert len(catalog)==7+len(names) and 'CrimsonSentinel' in catalog[6].get_name()
for i,name in enumerate(names,7):assert name in catalog[i].get_name()
settings=u.ValidateAssetsSettings();settings.set_editor_property('load_assets_for_validation',True);settings.set_editor_property('collect_per_asset_details',True);settings.set_editor_property('show_if_no_failures',False)
asset_data=[u.EditorAssetLibrary.find_asset_data(p) for p in sorted(set(paths))]
failed,result=u.get_editor_subsystem(u.EditorValidatorSubsystem).validate_assets_with_settings(asset_data,settings)
report=dict(passed=failed==0,assets=len(asset_data),failures=failed,characters=characters,validation=result.export_text())
(root/'Artifacts/WeaponFX/asset-validation.json').write_text(json.dumps(report,indent=2))
print('CRUSADER_ASSETS_VALIDATED',json.dumps(report))
assert failed==0,report
