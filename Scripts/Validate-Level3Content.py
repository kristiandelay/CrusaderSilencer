"""Verify Level3 imported materials, collision, saved structure and gameplay results."""
import hashlib,json
from pathlib import Path
import unreal as u

lv_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
lv_rows=[r for r in json.loads((lv_root/'resources/EnvironmentModels.json').read_text()) if r['category']=='Level3']
assert len(lv_rows)==74
lv_paths=[]
for row in lv_rows:
    name=row['name'];mesh=u.load_asset(row['asset'])
    assert row['imported'] and isinstance(mesh,u.StaticMesh)
    assert mesh.get_name()==name
    assert u.get_editor_subsystem(u.StaticMeshEditorSubsystem).get_nanite_settings(mesh).enabled
    mat=mesh.get_material(0);assert mat and mat.get_editor_property('phys_material').get_name()=='PM_Metal'
    assert mesh.get_editor_property('body_setup').get_editor_property('collision_trace_flag')==u.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE
    folder=f'/Game/Crusader/Environment/Level3/{name}'
    for kind in ['BaseColor','Normal','Metallic','Roughness']:
        tex=u.load_asset(folder+'/Textures/'+name+'_'+kind)
        assert isinstance(tex,u.Texture2D) and tex.get_editor_property('srgb')==(kind=='BaseColor')
        if kind=='Normal':assert tex.get_editor_property('flip_green_channel')
    lv_paths+=u.EditorAssetLibrary.list_assets(folder,True,False)
lv_manifest=json.loads((lv_root/'resources/Level3Facility.json').read_text())
lv_actors={a.get_actor_label():a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()}
assert len([n for n in lv_actors if n.startswith('CR_Level3_')])==lv_manifest['actor_count']
for row in lv_manifest['meshes']:
    actor=lv_actors[row['actor']]
    assert actor.static_mesh_component.static_mesh.get_name()==row['model']
    assert actor.actor_has_tag('CrusaderLevel3')
assert all(n in lv_actors for n in ['CR_Facility_OfficeDesk','CR_ControlRoom_MainEntrance','CR_Breakable_Facility_OfficeDesk'])
assert len([a for n,a in lv_actors.items() if n.startswith('CR_Level3Crowd_') and isinstance(a,u.CRTraversalCharacter)])==9
assert lv_manifest['storeys']==3 and lv_manifest['clear_height_cm']==660
lv_collision=lv_manifest['walking_collision']
assert len([r for r in lv_collision if 'StairRamp_' in r['actor']])==8
assert len([r for r in lv_collision if r['guard']])==16
for row in lv_collision:
    actor=lv_actors[row['actor']];component=actor.static_mesh_component
    assert component.get_collision_enabled()==u.CollisionEnabled.QUERY_ONLY
    assert component.get_collision_response_to_channel(u.CollisionChannel.ECC_PAWN)==u.CollisionResponseType.ECR_BLOCK
    assert component.get_collision_response_to_channel(u.CollisionChannel.ECC_CAMERA)==(u.CollisionResponseType.ECR_IGNORE if row['guard'] else u.CollisionResponseType.ECR_BLOCK)
    assert component.get_collision_response_to_channel(u.CollisionChannel.ECC_VISIBILITY)==u.CollisionResponseType.ECR_IGNORE
    assert component.get_collision_response_to_channel(u.CollisionChannel.ECC_LYRA_TRACE_CHANNEL_WEAPON)==u.CollisionResponseType.ECR_IGNORE
    assert not component.is_visible() and actor.get_editor_property('hidden')
for stair in lv_manifest['stairs']:
    component=lv_actors[stair['actor']].static_mesh_component
    assert component.get_collision_response_to_channel(u.CollisionChannel.ECC_PAWN)==u.CollisionResponseType.ECR_IGNORE
    assert component.get_collision_response_to_channel(u.CollisionChannel.ECC_VISIBILITY)==u.CollisionResponseType.ECR_BLOCK
lv_world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
lv_origin=u.Vector(*lv_manifest['origin'])
lv_band_checks=0
for z in [690,1410]:
    for start,end in [((5200,0,z),(5400,0,z)),((4300,1550,z),(4300,1750,z)),((4300,-1950,z),(4300,-2250,z))]:
        hit=u.SystemLibrary.line_trace_single(lv_world,lv_origin+u.Vector(*start),lv_origin+u.Vector(*end),u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[],u.DrawDebugTrace.NONE)
        assert hit and 'Band' in hit.to_dict()['hit_actor'].get_actor_label(),('Open stair tower storey band',start,end)
        lv_band_checks+=1
lv_settings=u.ValidateAssetsSettings()
lv_settings.set_editor_property('load_assets_for_validation',True)
lv_settings.set_editor_property('collect_per_asset_details',True)
lv_settings.set_editor_property('show_if_no_failures',False)
lv_failures,lv_validation=u.get_editor_subsystem(u.EditorValidatorSubsystem).validate_assets_with_settings(
    [u.EditorAssetLibrary.find_asset_data(p) for p in sorted(set(lv_paths))],lv_settings)
assert lv_failures==0,lv_validation.export_text()
lv_walk=json.loads((lv_root/'Artifacts/Level3/walkthrough.json').read_text())
assert lv_walk['passed'] and lv_walk['walkthrough_completed'],lv_walk.get('error')
assert len(lv_walk['smooth_stairs'])==16
lv_seams=json.loads((lv_root/'resources/Level3WallSeamValidation.json').read_text())
assert lv_seams['passed'] and lv_seams['open_probes_after']==0
lv_manifest_hash=hashlib.sha256((lv_root/'resources/Level3Facility.json').read_bytes()).hexdigest()
assert lv_walk['manifest_sha256']==lv_seams['manifest_sha256']==lv_manifest_hash,'Stale facility validation'
lv_source=json.loads((lv_root/'Artifacts/Level3/source-validation.json').read_text());assert lv_source['passed']
result=dict(passed=True,map='/Game/Maps/L_TraversalGym',models=len(lv_rows),assets=len(set(lv_paths)),
    actors=lv_manifest['actor_count'],models_placed=len(lv_manifest['models_used']),storeys=3,clear_height_cm=660,
    residents=9,checks=len(lv_walk['checks']),closed_stair_tower_band_checks=lv_band_checks,walkthrough_stops=len(lv_walk['walkthrough']),
    walking_collision_surfaces=len(lv_collision),smooth_stair_runs=8,
    wall_seam_probes=lv_seams['probes'],open_wall_seams=lv_seams['open_probes_after'],
    maximum_stair_bounce_cm=max(r['offset_range_cm'] for r in lv_walk['smooth_stairs']),
    source_validation='Artifacts/Level3/source-validation.json',gameplay_validation='Artifacts/Level3/walkthrough.json',
    skill='C:/Users/remote/.codex/skills/meshy-mockup-naming/SKILL.md')
(lv_root/'resources/Level3Validation.json').write_text(json.dumps(result,indent=2)+'\n')
print('LEVEL3_VALIDATED',result)
