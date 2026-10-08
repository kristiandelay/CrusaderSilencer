"""Validate the six authored pawns, mounted weapons and traversal placements."""
import json
from pathlib import Path
import unreal as u

va_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
va_config=json.loads((va_root/'resources/RobotGameplay.json').read_text())
va_actors={a.get_actor_label():a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()}
va_paths=['/Game/Crusader/Robots/FX_RobotLaser','/Game/Crusader/Robots/PawnData_Robot','/Game/Maps/L_TraversalGym']
va_rows=[]
for row in va_config['robots']:
    name=row['name'];path='/Game/Crusader/Robots/'+name+'/B_Robot_'+name
    bp=u.load_asset(path);assert bp and not u.CRBlueprintTools.has_blueprint_errors(bp)
    actor=va_actors['CR_Robot_'+name];cdo=u.get_default_object(bp.generated_class())
    assert isinstance(actor,u.CRRobotCharacter) and actor.get_class()==bp.generated_class()
    assert actor.crowd_agent.home_area.get_actor_label()==row['home']
    for pawn in [cdo,actor]:
        assert pawn.crowd_agent.enabled and pawn.crowd_agent.guard and pawn.crowd_agent.return_fire_only
        assert pawn.armor_health==row['health'] and not pawn.crowd_agent.weapons
        assert [[v.x,v.y,v.z] for v in pawn.muzzle_positions]==row['muzzles']
        assert pawn.mesh.anim_class==u.CRRobotAnimInstance.static_class()
        assert pawn.laser_effects.bullet_trail.get_name()=='NS_Laser_Trace_Red_2'
        assert pawn.laser_effects.fire_sound and not pawn.laser_effects.shell_ejection
    va_paths.append(path);v=actor.get_actor_location()
    va_rows.append(dict(name=name,home=row['home'],blueprint=path,position=[v.x,v.y,v.z],barrels=len(row['muzzles']),health=row['health']))
va_settings=u.ValidateAssetsSettings();va_settings.set_editor_property('load_assets_for_validation',True);va_settings.set_editor_property('show_if_no_failures',False)
va_failed,va_result=u.get_editor_subsystem(u.EditorValidatorSubsystem).validate_assets_with_settings([u.EditorAssetLibrary.find_asset_data(p) for p in va_paths],va_settings)
va_report=dict(passed=va_failed==0,assets=len(va_paths),failures=va_failed,robots=va_rows)
(va_root/'Artifacts/RobotGameplay/asset-validation.json').write_text(json.dumps(va_report,indent=2)+'\n')
assert va_failed==0,va_result.export_text()
print('ROBOT_GAMEPLAY_ASSETS_VALID',len(va_paths))
