"""Validate new humanoid rigs, selectable entries, Level2 assets and map."""
import json
from pathlib import Path
import unreal as u

vc_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
vc_names=[r['name'] for r in json.loads((vc_root/'resources/NPCAdditions.json').read_text())]
vc_catalog=list(u.get_default_object(u.load_asset('/Game/Blueprints/GM_Sandbox').generated_class()).get_editor_property('VisualOverrides_Soft'))
assert len(vc_catalog)==21 and 'CrimsonSentinel' in vc_catalog[6].get_name()
vc_paths=[];vc_characters=[]
for name in vc_names:
    folder='/Game/Crusader/Characters/'+name
    mesh=u.load_asset(folder+'/'+name);visual=u.load_asset(folder+'/BP_'+name)
    assert u.get_editor_subsystem(u.SkeletalMeshEditorSubsystem).get_lod_count(mesh)==3
    pose=mesh.get_editor_property('skeleton').get_reference_pose();bones=list(pose.get_bone_names())
    assert len(bones)==64
    for side in ['l','r']:
        for digit in ['thumb','index','middle','ring','pinky']:
            for i in range(1,4):assert u.Name(f'{digit}_{i:02}_{side}') in bones
    for bone in bones:
        factor=pose.get_ref_bone_pose(bone,u.AnimPoseSpaces.LOCAL).scale3d
        assert all(abs(v-1)<.001 for v in [factor.x,factor.y,factor.z])
    assert visual.generated_class() in vc_catalog and not u.CRBlueprintTools.has_blueprint_errors(visual)
    assert len(u.IKRigController.get_controller(u.load_asset(folder+'/IK_'+name)).get_retarget_chains())==29
    vc_paths+=u.EditorAssetLibrary.list_assets(folder,True,False)
    vc_characters.append(dict(name=name,bones=len(bones),lods=3,retarget_chains=29,catalog_index=vc_catalog.index(visual.generated_class())))
for row in json.loads((vc_root/'resources/EnvironmentModels.json').read_text()):
    if row['category']!='Level2':continue
    mesh=u.load_asset(row['asset']);assert isinstance(mesh,u.StaticMesh)
    assert u.get_editor_subsystem(u.StaticMeshEditorSubsystem).get_nanite_settings(mesh).enabled
    assert mesh.get_material(0).get_editor_property('phys_material').get_name()=='PM_Metal'
    assert mesh.get_editor_property('body_setup').get_editor_property('collision_trace_flag')==u.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE
    folder=row['asset'].split('.')[0].rsplit('/',1)[0]
    for kind in ['BaseColor','Normal','Metallic','Roughness']:
        tex=u.load_asset(folder+'/Textures/'+row['name']+'_'+kind)
        assert tex and tex.get_editor_property('srgb')==(kind=='BaseColor')
    vc_paths+=u.EditorAssetLibrary.list_assets(folder,True,False)
vc_paths+=['/Game/Baseline/Animations/ABP_BaselineVisualRetarget','/Game/Blueprints/GM_Sandbox','/Game/Maps/L_TraversalGym']
vc_settings=u.ValidateAssetsSettings();vc_settings.set_editor_property('load_assets_for_validation',True)
vc_settings.set_editor_property('collect_per_asset_details',True);vc_settings.set_editor_property('show_if_no_failures',False)
vc_failed,vc_result=u.get_editor_subsystem(u.EditorValidatorSubsystem).validate_assets_with_settings([u.EditorAssetLibrary.find_asset_data(p) for p in sorted(set(vc_paths))],vc_settings)
vc_report=dict(passed=vc_failed==0,assets=len(set(vc_paths)),failures=vc_failed,characters=vc_characters,catalog_size=len(vc_catalog),default_visual=vc_catalog[6].get_name(),validation=vc_result.export_text())
(vc_root/'Artifacts/ControlRoom/asset-validation.json').write_text(json.dumps(vc_report,indent=2)+'\n')
print('CONTROL_ROOM_CONTENT_VALIDATION',len(set(vc_paths)),vc_failed)
assert vc_failed==0
