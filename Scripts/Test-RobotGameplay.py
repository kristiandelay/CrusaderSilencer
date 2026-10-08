"""Real PIE robot patrol, rigid gait, passive sensing, retaliation, cover and death."""
import json,math,time,traceback
from pathlib import Path
import unreal as u

ra_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
ra_test=dict(phase='ready',next=0,busy=False,results=[],deadline=time.monotonic()+260,max_fps=u.SystemLibrary.get_console_variable_float_value('t.MaxFPS'))

def ra_set(obj,name,value):
    assert u.CRBlueprintTools.set_property_text(obj,name,str(value))

def ra_input(p,name,value):
    path={'Aim':'/Game/Input/IA_Aim','Fire':'/Game/Input/Actions/IA_Weapon_Fire','FireAuto':'/Game/Input/Actions/IA_Weapon_Fire_Auto'}[name]
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==p.get_controller())
    sub.inject_input_vector_for_action(u.load_asset(path),u.Vector(value,0,0),[],[])

def ra_health(p):return p.get_component_by_class(u.LyraHealthComponent).get_health()
def ra_vec(v):return [v.x,v.y,v.z]
def ra_god(p):u.SystemLibrary.execute_console_command(p.get_world(),'God',p.get_controller())

def ra_finish(error=None):
    u.SystemLibrary.execute_console_command(None,'t.MaxFPS '+str(ra_test['max_fps']))
    u.unregister_slate_post_tick_callback(ra_test['handle']);ra_test.update(finished=True,error=error)
    result=dict(passed=not error,error=error,results=ra_test['results'])
    (ra_root/'Artifacts/RobotGameplay/standalone.json').write_text(json.dumps(result,indent=2)+'\n')
    print('ROBOT_GAMEPLAY_TEST_COMPLETE',error)

def ra_place(p,r,near=False):
    r.get_controller().stop_movement();r.character_movement.stop_movement_immediately()
    ra_set(r.crowd_agent,'CurrentArea','None')
    r.set_actor_location(u.Vector(12900,-1750,94),False,True)
    r.set_actor_rotation(u.Rotator(yaw=180),False);r.get_controller().set_control_rotation(u.Rotator(yaw=180))
    p.set_actor_location(u.Vector(12150,-1750,94),False,True);p.character_movement.stop_movement_immediately()
    ra_test.update(hold_robot=True,near=near,health_before=ra_health(r),shots_before=r.mounted_shots)

def ra_tick(dt):
    if ra_test['busy']:return
    ra_test['busy']=True
    try:
        assert time.monotonic()<ra_test['deadline'],'Robot gameplay timed out: '+ra_test['phase']
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        w=worlds[0];p=u.GameplayStatics.get_player_pawn(w,0)
        robots=u.GameplayStatics.get_all_actors_of_class(w,u.CRRobotCharacter)
        if not p or len(robots)!=6 or not all(r.crowd_agent.initialized for r in robots):return
        now=u.GameplayStatics.get_time_seconds(w);phase=ra_test['phase'];r=ra_test.get('robot')
        if ra_test.pop('release',False):
            ra_input(p,'Fire',0);ra_input(p,'FireAuto',0)
        if r and ra_test.get('hold_robot'):r.get_controller().stop_movement();r.character_movement.stop_movement_immediately()
        if r and phase in ['aim','hit','near_aim','near_hit']:
            target=r.get_actor_location()+u.Vector(0,85 if ra_test.get('near') else 0,20)
            eye=u.GameplayStatics.get_player_camera_manager(w,0).get_camera_location()
            p.get_controller().set_control_rotation(u.MathLibrary.find_look_at_rotation(eye,target));ra_input(p,'Aim',1)
        if phase=='patrol':
            elapsed=now-ra_test['patrol_start'];slow=12<elapsed<18
            if slow!=ra_test.get('slow_frames',False):
                u.SystemLibrary.execute_console_command(None,'t.MaxFPS '+str(8 if slow else ra_test['max_fps']))
                ra_test['slow_frames']=slow
            for robot in robots:
                sample=ra_test['gait'][robot.get_name()];anim=robot.mesh.get_anim_instance();pos=ra_vec(robot.get_actor_location())
                sample['distance']+=math.dist(pos,sample['last']);sample['last']=pos
                if robot.get_velocity().length()>70:sample['errors'].append(anim.maximum_foot_error)
                if anim.maximum_foot_error>sample.get('worst',{}).get('error',0):
                    sample['worst']=dict(error=anim.maximum_foot_error,position=pos,phase=anim.gait_phase,speed=anim.ground_speed,delta=dt,movement=str(robot.character_movement.movement_mode))
                for side in ['l','r']:
                    bones=['upper_leg_','middle_leg_','lower_leg_','foot_']
                    positions=[robot.mesh.get_socket_location(b+side) for b in bones]
                    for joint in range(3):
                        length=(positions[joint+1]-positions[joint]).length();key=side+str(joint)
                        if key not in sample['lengths']:sample['lengths'][key]=length
                        assert abs(length-sample['lengths'][key])<.03,(robot.get_name(),'metal link changed length',key,length)
                        scale=robot.mesh.get_socket_transform(bones[joint]+side,u.RelativeTransformSpace.RTS_COMPONENT).scale3d
                        assert max(abs(v-1) for v in [scale.x,scale.y,scale.z])<.001
        if phase=='retaliate':
            if ra_health(p)<ra_test['player_health'] and not ra_test.get('damage_proved'):
                ra_test['damage_proved']=True;ra_test['health_after_return_fire']=ra_health(p);ra_god(p)
            if r.mounted_shots>ra_test['shots_before'] and r.crowd_agent.tactical_moves>0 and ra_test.get('damage_proved'):
                displacement=(r.get_actor_location()-u.Vector(*ra_test['combat_start'])).length()
                if displacement>150:
                    assert r.weapon_effects.trails_played>0 and r.weapon_effects.last_profile==r.laser_effects
                    ra_test['results'].append(dict(case='retaliation_damage_and_tactics',shots=r.mounted_shots-ra_test['shots_before'],player_health=ra_test['health_after_return_fire'],tactical_moves=r.crowd_agent.tactical_moves,displacement=displacement,laser=r.weapon_effects.last_profile.bullet_trail.get_path_name()))
                    ra_test.update(phase='cover_setup',next=now,hold_robot=True)
            elif now>=ra_test['next']:raise AssertionError(('No effective retaliation',r.mounted_shots,r.crowd_agent.state,ra_health(p),r.crowd_agent.tactical_moves))
        if now<ra_test['next']:return
        phase=ra_test['phase']
        if phase=='ready':
            p.get_controller().set_ignore_move_input(True);p.get_controller().set_ignore_look_input(True);ra_god(p)
            assert all(r.crowd_agent.guard and r.crowd_agent.return_fire_only and not r.crowd_agent.provoked and r.mounted_shots==0 for r in robots)
            assert all(ra_health(r)==r.armor_health and isinstance(r.mesh.get_anim_instance(),u.CRRobotAnimInstance) and not r.baseline_equipment.get_active_item() for r in robots)
            ra_test['results'].append(dict(case='six_robot_roles_and_health',robots=[dict(name=r.get_name(),health=ra_health(r),home=r.crowd_agent.home_area.get_actor_label()) for r in robots]))
            for area in u.GameplayStatics.get_all_actors_of_class(w,u.CRCrowdArea):ra_set(area,'WanderChance',1.)
            ra_test['gait']={r.get_name():dict(last=ra_vec(r.get_actor_location()),distance=0.,errors=[],lengths={},plants=r.mesh.get_anim_instance().foot_plants) for r in robots}
            ra_test.update(phase='patrol',next=now+35,patrol_start=now)
        elif phase=='patrol':
            summaries=[]
            for robot in robots:
                sample=ra_test['gait'][robot.get_name()];errors=sorted(sample['errors'])
                plants=robot.mesh.get_anim_instance().foot_plants-sample['plants']
                assert sample['distance']>150 and plants>4,(robot.get_name(),sample['distance'],plants)
                assert errors and errors[int(len(errors)*.95)]<8,(robot.get_name(),'foot placement',max(errors),errors[int(len(errors)*.95)])
                assert max(errors)<45,(robot.get_name(),'unreachable foot after movement discontinuity',sample.get('worst'))
                assert robot.mounted_shots==0 and not robot.crowd_agent.provoked
                summaries.append(dict(name=robot.get_name(),distance=sample['distance'],plants=plants,foot_error_95_cm=errors[int(len(errors)*.95)],foot_error_max_cm=max(errors),area_visits=robot.crowd_agent.area_visits))
            assert any(r.crowd_agent.area_visits>1 for r in robots)
            ra_test['results'].append(dict(case='grounded_rigid_patrol_and_area_visits',robots=summaries))
            r=robots[0];ra_test['robot']=r
            civilians=[a for a in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if a.crowd_agent.enabled and not a.crowd_agent.guard]
            ra_test['civilian']=civilians[0];ra_test['noise_actor']=civilians[1]
            for actor in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter):
                if actor.crowd_agent.enabled and actor!=r:
                    actor.get_controller().stop_movement();actor.get_controller().set_actor_tick_enabled(False);actor.character_movement.stop_movement_immediately()
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(w,u.BaselineWeaponPickup) if a.item_definition.get_name()=='ID_Pistol_C')
            p.set_actor_location(pickup.get_actor_location()+u.Vector(-100,0,40),False,True);p.baseline_equipment.server_pickup(pickup)
            ra_test.update(phase='peace_place',next=now+.7)
        elif phase=='peace_place':
            assert p.baseline_equipment.get_active_item()
            ra_place(p,r)
            ra_test['civilian'].set_actor_location(u.Vector(12500,-1200,94),False,True)
            ra_test['civilian'].get_controller().set_actor_tick_enabled(True)
            ra_test.update(phase='ambient',next=now+2,hearing_before=r.crowd_agent.hearing_detections)
        elif phase=='ambient':
            assert not r.crowd_agent.provoked and r.mounted_shots==0
            u.AISense_Hearing.report_noise_event(w,p.get_actor_location(),1,p,3000,'Gunfire')
            ra_test.update(phase='heard',next=now+2)
        elif phase=='heard':
            assert r.crowd_agent.hearing_detections>ra_test['hearing_before']
            assert not r.crowd_agent.provoked and r.mounted_shots==0
            ra_test['results'].append(dict(case='sight_and_ambient_gunfire_do_not_attack',heard=r.crowd_agent.hearing_detections-ra_test['hearing_before'],state=str(r.crowd_agent.state),shots=r.mounted_shots))
            ra_test.update(phase='aim',next=now+1.5)
        elif phase=='aim':
            ra_input(p,'Fire',1);ra_input(p,'FireAuto',1)
            ra_test.update(phase='hit',next=now+.7,release=True)
        elif phase=='hit':
            assert ra_health(r)<ra_test['health_before'],('Actual player shot missed',ra_health(r),r.get_actor_location())
            assert r.crowd_agent.provoked and r.crowd_agent.threat==p and r.crowd_agent.damage_reactions>0
            assert ra_test['civilian'].crowd_agent.state==u.CRCrowdState.FLEE
            ra_test['results'].append(dict(case='player_hit_provokes_robot_and_civilian_flight',health=ra_health(r),damage_reactions=r.crowd_agent.damage_reactions))
            ra_input(p,'Aim',0);ra_god(p)
            ra_test.update(phase='retaliate',next=now+22,hold_robot=False,combat_start=ra_vec(r.get_actor_location()),player_health=ra_health(p))
        elif phase=='cover_setup':
            r.character_movement.disable_movement()
            noise=ra_test['noise_actor'];ra_set(noise.crowd_agent,'bEnabled','False')
            noise.set_actor_location(r.get_actor_location()+u.Vector(0,600,0),False,True)
            u.AISense_Hearing.report_noise_event(w,noise.get_actor_location(),1,noise,3000,'Gunfire')
            middle=(r.get_actor_location()+p.get_actor_location())*.5
            wall=u.CRBlueprintTools.spawn_pie_test_actor(w,u.StaticMeshActor,u.Transform(location=u.Vector(middle.x,middle.y,200)))
            wall.static_mesh_component.set_mobility(u.ComponentMobility.MOVABLE)
            wall.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'))
            wall.set_actor_scale3d(u.Vector(3,12,4));wall.static_mesh_component.set_collision_profile_name('BlockAll')
            ra_test.update(wall=wall,phase='cover_settled',next=now+1)
        elif phase=='cover_settled':
            assert r.crowd_agent.threat==p,'Unrelated noise stole the aggressor'
            ra_test.update(phase='cover_check',next=now+2,cover_shots=r.mounted_shots)
        elif phase=='cover_check':
            assert r.mounted_shots==ra_test['cover_shots'],'Robot fired through cover'
            ra_test['results'].append(dict(case='cover_blocks_fire_and_noise_cannot_change_aggressor',shots=r.mounted_shots))
            ra_test['wall'].destroy_actor()
            civ=ra_test['civilian'];civ.get_controller().stop_movement();civ.get_controller().set_actor_tick_enabled(False)
            middle=(r.get_actor_location()+p.get_actor_location())*.5
            civ.set_actor_location(u.Vector(middle.x,middle.y,94),False,True);civ.character_movement.stop_movement_immediately()
            ra_test.update(phase='friendly_check',next=now+2,friendly_health=ra_health(civ),friendly_shots=r.mounted_shots)
        elif phase=='friendly_check':
            assert r.mounted_shots==ra_test['friendly_shots'] and ra_health(ra_test['civilian'])==ra_test['friendly_health'],('Unsafe shot past civilian',r.mounted_shots,ra_test['friendly_shots'],ra_health(ra_test['civilian']),ra_vec(r.get_actor_location()),ra_vec(ra_test['civilian'].get_actor_location()))
            ra_test['results'].append(dict(case='civilian_blocks_firing_lane',no_friendly_fire=True))
            p.set_actor_location(u.Vector(1200,-5500,94),False,True)
            ra_test['civilian'].set_actor_location(u.Vector(9500,4500,94),False,True)
            r.character_movement.set_movement_mode(u.MovementMode.MOVE_WALKING)
            ra_test.update(phase='calm',next=now+22,hold_robot=False,calm_shots=r.mounted_shots)
        elif phase=='calm':
            assert not r.crowd_agent.provoked and not r.crowd_agent.threat and r.mounted_shots==ra_test['calm_shots'],('Did not disengage',r.crowd_agent.state,r.crowd_agent.provoked)
            ra_test['results'].append(dict(case='losing_attacker_returns_to_peaceful_state',provoked=False))
            ra_place(p,r,True);ra_test.update(phase='near_aim',next=now+1.5)
        elif phase=='near_aim':
            ra_input(p,'Fire',1);ra_input(p,'FireAuto',1);ra_test.update(phase='near_hit',next=now+.65,release=True)
        elif phase=='near_hit':
            assert ra_health(r)==ra_test['health_before'],'Near-miss fixture hit the robot'
            assert r.crowd_agent.provoked and r.crowd_agent.threat==p,'Directed near miss did not provoke robot'
            ra_test['results'].append(dict(case='aimed_near_miss_provokes_without_damage',health=ra_health(r)))
            ra_input(p,'Aim',0)
            asc=u.AbilitySystemLibrary.get_ability_system_component(p)
            effect=u.load_asset('/Game/GameplayEffects/Damage/GE_Damage_Basic_SetByCaller').generated_class()
            spec=asc.make_outgoing_spec(effect,1,asc.make_effect_context());tag=u.GameplayTag();tag.import_text('(TagName="SetByCaller.Damage")')
            spec=u.AbilitySystemLibrary.assign_tag_set_by_caller_magnitude(spec,tag,1000)
            ra_test.update(old_name=r.get_name(),old_class=r.get_class(),old_home=r.crowd_agent.home_area,death_shots=r.mounted_shots)
            u.AbilitySystemLibrary.get_ability_system_component(r).apply_gameplay_effect_spec_to_self(spec)
            ra_test.update(phase='shutdown',next=now+1,hold_robot=False)
        elif phase=='shutdown':
            assert r.shutdown and r.get_component_by_class(u.LyraHealthComponent).is_dead_or_dying()
            assert r.mesh.get_anim_instance().shutdown_blend>.3 and not r.mesh.is_simulating_physics()
            assert r.mounted_shots==ra_test['death_shots']
            ra_test['results'].append(dict(case='mechanical_shutdown_stops_combat',blend=r.mesh.get_anim_instance().shutdown_blend))
            ra_test.update(phase='respawn',next=now+10)
        elif phase=='respawn':
            replacement=next(a for a in robots if a.get_class()==ra_test['old_class'] and a.get_name()!=ra_test['old_name'])
            assert not replacement.shutdown and not replacement.crowd_agent.provoked
            assert replacement.crowd_agent.home_area==ra_test['old_home'] and ra_health(replacement)==replacement.armor_health
            ra_test['results'].append(dict(case='robot_respawn_preserves_model_and_home',name=replacement.get_name(),health=ra_health(replacement)))
            ra_finish()
    except Exception:ra_finish(traceback.format_exc())
    finally:ra_test['busy']=False

ra_test['handle']=u.register_slate_post_tick_callback(ra_tick)
print('ROBOT_GAMEPLAY_TEST_STARTED')
