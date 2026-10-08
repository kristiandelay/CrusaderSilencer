"""Create six mechanical crowd pawns and place them in existing traversal tethers."""
import json
from pathlib import Path
import unreal as u

rg_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
rg_config=json.loads((rg_root/'resources/RobotGameplay.json').read_text())
assert not u.EditorLevelLibrary.get_pie_worlds(False)
rg_world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
assert rg_world.get_name()=='L_TraversalGym'
rg_lib=u.EditorAssetLibrary;rg_tools=u.AssetToolsHelpers.get_asset_tools()
rg_actors=u.get_editor_subsystem(u.EditorActorSubsystem)
rg_existing={a.get_actor_label():a for a in rg_actors.get_all_level_actors()}

def rg_save(asset):
    if isinstance(asset,u.Blueprint):
        u.BlueprintEditorLibrary.compile_blueprint(asset)
        assert not u.CRBlueprintTools.has_blueprint_errors(asset)
    assert rg_lib.save_loaded_asset(asset,only_if_is_dirty=False)

rg_fx_path='/Game/Crusader/Robots/FX_RobotLaser'
rg_fx=u.load_asset(rg_fx_path) if rg_lib.does_asset_exist(rg_fx_path) else rg_lib.duplicate_asset('/Game/Crusader/Effects/FX_Rifle',rg_fx_path)
assert rg_fx
rg_fx.set_editor_property('fire_sound',u.load_asset('/Game/Bullet_Tracers_Fx/Sources/Sounds/SW_LaserGun_BW_47473_Cue'))
rg_fx.set_editor_property('shell_ejection',None)
rg_save(rg_fx)
rg_pawn_path='/Game/Crusader/Robots/PawnData_Robot'
rg_pawn=u.load_asset(rg_pawn_path) if rg_lib.does_asset_exist(rg_pawn_path) else rg_lib.duplicate_asset('/Game/Crusader/System/PawnData_CRTraversal',rg_pawn_path)
rg_pawn.set_editor_property('pawn_class',u.CRRobotCharacter);rg_save(rg_pawn)
rg_damage=u.load_asset('/Game/GameplayEffects/Damage/GE_Damage_Basic_SetByCaller').generated_class()
rg_footsteps=u.load_asset('/Game/Crusader/Audio/DA_Footsteps')
rg_metal=u.load_asset('/Game/Crusader/Effects/Surfaces/PM_Metal')
rg_spawns=[]

for row in rg_config['robots']:
    name=row['name'];folder='/Game/Crusader/Robots/'+name;bp_name='B_Robot_'+name
    assert row['home'] in rg_existing,row['home']
    if rg_lib.does_asset_exist(folder+'/'+bp_name):bp=u.load_asset(folder+'/'+bp_name)
    else:
        factory=u.BlueprintFactory();factory.set_editor_property('parent_class',u.CRRobotCharacter)
        bp=rg_tools.create_asset(bp_name,folder,u.Blueprint,factory)
    cdo=u.get_default_object(bp.generated_class())
    cdo.mesh.set_skeletal_mesh_asset(u.load_asset(folder+'/'+name))
    cdo.mesh.set_anim_instance_class(u.CRRobotAnimInstance)
    cdo.mesh.set_relative_location(u.Vector(0,0,-90),False,False)
    cdo.mesh.set_relative_rotation(u.Rotator(yaw=-90),False,False)
    cdo.set_editor_property('armor_health',float(row['health']))
    cdo.set_editor_property('muzzle_positions',[u.Vector(*p) for p in row['muzzles']])
    cdo.set_editor_property('laser_effects',rg_fx);cdo.set_editor_property('damage_effect',rg_damage)
    cdo.footsteps.set_editor_property('profile',rg_footsteps)
    cdo.capsule_component.set_phys_material_override(rg_metal)
    cdo.capsule_component.set_editor_property('receives_decals',False)
    extension=cdo.get_component_by_class(u.LyraPawnExtensionComponent)
    assert u.CRBlueprintTools.set_property_text(extension,'PawnData',"/Script/LyraGame.LyraPawnData'"+rg_pawn_path+".PawnData_Robot'")
    rg_save(bp)
    label='CR_Robot_'+name
    actor=rg_existing.get(label)
    if actor:
        assert isinstance(actor,u.CRRobotCharacter),label
    else:
        actor=rg_actors.spawn_actor_from_class(bp.generated_class(),u.Vector(*row['position']),u.Rotator(yaw=row['yaw']))
        actor.set_actor_label(label)
    # Preserve hand-adjusted positions on subsequent runs.
    actor.set_folder_path('Crusader/Facility Mockup/Crowd/Robots' if 'Facility' in row['home'] else 'Crusader/Crowd District/Robots')
    actor.crowd_agent.set_editor_property('home_area',rg_existing[row['home']])
    actor.tags=['CrusaderRobotCrowd']
    rg_spawns.append(dict(name=name,actor=label,blueprint=bp.get_path_name(),home=row['home']))

assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
(rg_root/'Artifacts/RobotGameplay/placed-robots.json').write_text(json.dumps(rg_spawns,indent=2)+'\n')
print('ROBOT_GAMEPLAY_CONFIGURED',len(rg_spawns),'patrolling robots; direct provocation required')
