"""Verify persisted range assets and the completed gameplay reports."""
import json
from pathlib import Path
import unreal as u

vd_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
vd_manifest=json.loads((vd_root/'resources/DestructionRange.json').read_text())
vd_actors={a.get_actor_label():a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()}
vd_geometries=set()
for row in vd_manifest['targets']:
    a=vd_actors[row['actor']]
    assert isinstance(a,u.CRDestructibleActor) and a.get_editor_property('replicates')
    gc=a.get_destructible_geometry()
    assert gc and gc.rest_collection and str(gc.get_collision_profile_name())=='CRDestructible'
    desc=u.CRBlueprintTools.describe_object(gc)
    assert 'bEnableReplication = True' in desc and 'bEnableAbandonAfterLevel = False' in desc
    assert 'bCanEverAffectNavigation = False' in desc
    assert not gc.get_editor_property('receives_decals')
    vd_geometries.add(gc.rest_collection.get_path_name())
assert len(vd_manifest['targets'])==19 and len(vd_geometries)==14
vd_bp=u.load_asset(vd_manifest['blueprint']);u.BlueprintEditorLibrary.compile_blueprint(vd_bp)
assert not u.CRBlueprintTools.has_blueprint_errors(vd_bp)
for name,index in {'Concrete':2,'Glass':3,'Metal':4,'Wood':5,'Brick':6,'Plaster':17,'Generic':16}.items():
    mat=u.load_asset('/Game/NextGenDestruction/GeometryCollections/PhysMat/PM_'+name)
    assert mat.get_editor_property('surface_type').value==index,(name,mat.get_editor_property('surface_type'))
vd_reports={}
for name in ['standalone','network','suite']:
    report=json.loads((vd_root/f'Artifacts/Destruction/{name}.json').read_text())
    assert report['passed'],(name,report['error'])
    vd_reports[name]=report
vd_result=dict(passed=True,map=vd_manifest['map'],targets=19,geometry_collections=14,
    native_build='Artifacts/Destruction/build.log',reports=vd_reports,
    controls='E pickup; LMB fire; H hold/release grenade; X type; restart Play to reset targets')
(vd_root/'resources/DestructionValidation.json').write_text(json.dumps(vd_result,indent=2)+'\n')
print('DESTRUCTION_VALIDATED',len(vd_reports['standalone']['results']),len(vd_reports['network']['results']))
