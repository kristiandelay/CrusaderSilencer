"""Headless load/compile smoke test, run from the exported project's own editor."""
from pathlib import Path
import json
import unreal as u

root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
export=json.loads((root/'BaselineExport.json').read_text())
assert u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/Maps/L_TraversalGym')
pawn=u.load_asset('/Game/Crusader/Characters/B_CRTraversalPawn')
movement=u.get_default_object(pawn.generated_class()).character_movement
assert isinstance(movement,u.BaselineCharacterMovement)
assert movement.slide_gravity_scale==1.5
paths=['/Game/Blueprints/SandboxCharacter_CMC',
       '/Game/Crusader/Characters/B_CRTraversalPawn',
       '/Game/Crusader/Characters/B_CRMannequin',
       '/Game/Baseline/Animations/ABP_BaselineManny',
       '/Game/Characters/Heroes/Mannequin/Animations/AnimNotifies/AN_PlayWeaponMontage',
       '/Game/Characters/Heroes/Abilities/AN_Reload']
for kind in ['Rifle','Pistol','Shotgun']:
    paths += [path for path in u.EditorAssetLibrary.list_assets('/Game/Baseline/Weapons/'+kind,recursive=True)
              if isinstance(u.load_asset(path),u.Blueprint)]
for path in paths:
    asset=u.load_asset(path)
    assert asset,path
    u.BlueprintEditorLibrary.compile_blueprint(asset)
    assert not u.CRBlueprintTools.has_blueprint_errors(asset),path
world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
pickups=u.GameplayStatics.get_all_actors_of_class(world,u.BaselineWeaponPickup)
assert sorted(str(p.get_item_name()) for p in pickups)==['Black Iron Rifle','Futuristic Pistol','Titan Breaker']
assert all(p.display_mesh.get_skinned_asset() for p in pickups)
report={'passed':True,'project_root':str(root),'project_id':export['project_id'],
        'map':world.get_path_name(),'blueprints_compiled':len(paths),
        'pickup_names':sorted(str(p.get_item_name()) for p in pickups),
        'movement_class':movement.get_class().get_name(),'slide_gravity_scale':movement.slide_gravity_scale}
(root/'Artifacts').mkdir(exist_ok=True)
(root/'Artifacts/export-smoke.json').write_text(json.dumps(report,indent=2))
u.log('BASELINE_EXPORT_SMOKE_PASSED '+json.dumps(report))
