"""Validate persisted furniture, original appearance, collision and play reports."""
import json
from pathlib import Path
import unreal as u
assert not u.EditorLevelLibrary.get_pie_worlds(False)
bv_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
bv_manifest=json.loads((bv_root/'resources/BuildingDestruction.json').read_text())
bv_all=u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
bv_actors={a.get_actor_label():a for a in bv_all}
bv_owned=[a for a in bv_all if a.actor_has_tag('CrusaderBuildingDestruction')]
assert len(bv_owned)==27 and len({a.get_actor_label() for a in bv_owned})==27
bv_errors=[];bv_sources=set()
for bv_row in bv_manifest['targets']:
    bv_a=bv_actors[bv_row['actor']];bv_gc=bv_a.get_destructible_geometry()
    assert bv_gc.rest_collection==u.load_asset(bv_row['geometry'])
    assert (bv_a.get_actor_scale3d()-u.Vector(1,1,1)).length()<.001
    assert bv_a.get_editor_property('block_navigation_until_broken') and bv_a.get_editor_property('replicates')
    assert bv_a.get_editor_property('weapon_contact_strain')==2000000.
    bv_desc=u.CRBlueprintTools.describe_object(bv_gc)
    for bv_flag in ['bEnableReplication = True','bEnableDamageFromCollision = False','bCanEverAffectNavigation = False','CollisionProfilePerLevel = ("CRDestructible","IgnoreCharChaos"']:
        assert bv_flag in bv_desc,(bv_row['actor'],bv_flag)
    assert u.CRDestructionTools.get_rigid_piece_count(bv_gc.rest_collection)==bv_row['pieces']
    assert u.EditorAssetLibrary.get_metadata_tag(bv_gc.rest_collection,'CrusaderCollisionVersion')=='1'
    bv_min=[float('inf')]*3;bv_max=[float('-inf')]*3
    for bv_label in bv_row['sources']:
        bv_s=bv_actors[bv_label];bv_sources.add(bv_label)
        assert bv_s.get_editor_property('is_editor_only_actor')
        assert str(bv_s.static_mesh_component.get_collision_profile_name())=='NoCollision'
        assert bv_s.get_editor_property('hidden')
        bv_c,bv_e=bv_s.get_actor_bounds(False)
        for i,axis in enumerate(['x','y','z']):
            bv_min[i]=min(bv_min[i],getattr(bv_c,axis)-getattr(bv_e,axis))
            bv_max[i]=max(bv_max[i],getattr(bv_c,axis)+getattr(bv_e,axis))
        for bv_m in bv_s.static_mesh_component.get_materials():
            assert bv_m in bv_gc.rest_collection.get_editor_property('materials'),('Missing original material',bv_label)
    bv_c,bv_e=bv_a.get_actor_bounds(False)
    bv_error=max(abs(value-reference) for i,axis in enumerate(['x','y','z']) for value,reference in
                 [(getattr(bv_c,axis)-getattr(bv_e,axis),bv_min[i]),(getattr(bv_c,axis)+getattr(bv_e,axis),bv_max[i])])
    assert bv_error<1.,(bv_row['actor'],'Appearance bounds changed',bv_error)
    bv_errors.append(bv_error)
bv_bp=u.load_asset(bv_manifest['blueprint'])
assert not u.CRBlueprintTools.has_blueprint_errors(bv_bp)
for bv_nav in u.GameplayStatics.get_all_actors_of_class(u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world(),u.RecastNavMesh):
    assert 'RuntimeGeneration = Dynamic\n' in u.CRBlueprintTools.describe_object(bv_nav)
bv_reports={}
for bv_name in ['standalone','network','suite']:
    bv_report=json.loads((bv_root/f'Artifacts/BuildingDestruction/{bv_name}.json').read_text())
    assert bv_report['passed'],(bv_name,bv_report['error'])
    bv_reports[bv_name]=bv_report
assert len(bv_reports['standalone']['results'])==15
assert len(bv_reports['network']['results'])==8
bv_result=dict(passed=True,map=bv_manifest['map'],placements=len(bv_owned),source_mesh_actors=len(bv_sources),
    collections=len(bv_manifest['collections']),maximum_bounds_difference_cm=max(bv_errors),
    native_build='Artifacts/BuildingDestruction/build.log',reports=bv_reports)
(bv_root/'resources/BuildingDestructionValidation.json').write_text(json.dumps(bv_result,indent=2)+'\n')
print('BUILDING_DESTRUCTION_VALIDATED',len(bv_owned),'placements',len(bv_sources),'original meshes')
