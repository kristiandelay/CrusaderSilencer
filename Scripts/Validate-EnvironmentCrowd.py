"""Validate project-authored assets and the imported environment dependencies."""
import json
from pathlib import Path
import unreal as u
assert not u.EditorLevelLibrary.get_pie_worlds(False)
v_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
v_paths=[];v_models=[]
for row in json.loads((v_root/'resources/EnvironmentModels.json').read_text()):
    mesh=u.load_asset(row['asset']);assert isinstance(mesh,u.StaticMesh)
    assert u.get_editor_subsystem(u.StaticMeshEditorSubsystem).get_nanite_settings(mesh).enabled
    assert mesh.get_editor_property('body_setup').get_editor_property('collision_trace_flag')==u.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE
    folder=row['asset'].split('.')[0].rsplit('/',1)[0]
    assets=u.EditorAssetLibrary.list_assets(folder,True,False);assert len(assets)==6,(row['name'],assets)
    for kind in ['BaseColor','Normal','Metallic','Roughness']:
        tex=u.load_asset(folder+'/Textures/'+row['name']+'_'+kind)
        assert tex.get_editor_property('srgb')==(kind=='BaseColor')
        if kind=='Normal':assert tex.get_editor_property('compression_settings')==u.TextureCompressionSettings.TC_NORMALMAP
    assert mesh.get_material(0).get_editor_property('phys_material')
    v_paths+=assets;v_models.append(row['name'])
for folder in ['AI','Audio','Effects']:v_paths+=u.EditorAssetLibrary.list_assets('/Game/Crusader/'+folder,True,False)
v_paths+=['/Game/Audio/Foley/AC_FoleyEvents','/Game/Blueprints/AC_VisualOverrideManager','/Game/Blueprints/SandboxCharacter_CMC','/Game/Crusader/Characters/B_CRTraversalPawn','/Game/Maps/L_TraversalGym']
profile=u.load_asset('/Game/Crusader/Audio/DA_Footsteps');assert len(profile.surfaces)==27
for row in profile.surfaces:
    for gait in ['sneak','walk','run','sprint','jump','land']:assert getattr(row,gait),(row.surface,gait)
for role in ['GuardRifle','GuardPistol','GuardShotgun','Civilian']:
    bp=u.load_asset('/Game/Crusader/AI/B_'+role);assert not u.CRBlueprintTools.has_blueprint_errors(bp)
    cdo=u.get_default_object(bp.generated_class())
    assert cdo.crowd_agent.enabled and bool(cdo.crowd_agent.weapons)==role.startswith('Guard')
    assert cdo.footsteps.profile==profile
for kind in ['Rifle','Pistol','Shotgun']:
    fx=u.load_asset('/Game/Crusader/Effects/FX_'+kind)
    assert fx.decal_lifetime==120 and fx.max_bullet_holes==96
settings=u.ValidateAssetsSettings();settings.set_editor_property('load_assets_for_validation',True);settings.set_editor_property('collect_per_asset_details',True);settings.set_editor_property('show_if_no_failures',False)
asset_data=[u.EditorAssetLibrary.find_asset_data(p) for p in sorted(set(v_paths))]
failed,result=u.get_editor_subsystem(u.EditorValidatorSubsystem).validate_assets_with_settings(asset_data,settings)
report=dict(passed=failed==0,assets=len(asset_data),failures=failed,models=v_models,footstep_surfaces=27,validation=result.export_text())
(v_root/'Artifacts/Environment/asset-validation.json').write_text(json.dumps(report,indent=2))
print('ENVIRONMENT_CROWD_VALIDATION',len(asset_data),failed)
assert failed==0,result.export_text()
