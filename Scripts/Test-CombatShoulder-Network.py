"""Two-player PIE: replicated hand swaps, real opposing-player kills and respawns."""
import json
import time
import traceback
from pathlib import Path
import unreal as u

combat_net={'phase':'position_pickups','next':0,'busy':False,'index':0,'results':[], 'deadline':time.monotonic()+120}
combat_net_out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/CombatTests/combat-shoulder-network.json'


def cn_context():
    pawns=[p for w in u.EditorLevelLibrary.get_pie_worlds(False) for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter)
           if 'TrainingPartner' not in p.get_class().get_name()]
    return (next(p for p in pawns if p.has_authority() and p.is_locally_controlled()),
            next(p for p in pawns if p.has_authority() and not p.is_locally_controlled()),
            next(p for p in pawns if not p.has_authority() and p.is_locally_controlled()),
            next(p for p in pawns if not p.has_authority() and not p.is_locally_controlled()))


def cn_input(pawn,name,value):
    paths={'Fire':'/Game/Input/Actions/IA_Weapon_Fire_Auto','FireSemi':'/Game/Input/Actions/IA_Weapon_Fire','Aim':'/Game/Input/IA_Aim'}
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
             if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pawn.get_controller())
    sub.inject_input_vector_for_action(u.load_asset(paths.get(name,'/Game/Baseline/Input/IA_'+name)),u.Vector(value,0,0),[],[])


def cn_finish(error=None):
    u.unregister_slate_post_tick_callback(combat_net['handle'])
    combat_net['finished']=True
    combat_net_out.write_text(json.dumps({'passed':error is None,'error':error,'results':combat_net['results']},indent=2))
    print('COMBAT_NETWORK_COMPLETE',error)


def cn_tick(dt):
    if combat_net['busy']:return
    combat_net['busy']=True
    try:
        assert time.monotonic()<combat_net['deadline'],'Network combat timeout'
        try:host,server_client,client,observer=cn_context()
        except StopIteration:return
        if not all(p.physical_interaction.controls_created for p in [host,server_client,client,observer]):return
        now=time.monotonic()
        if combat_net.pop('release',False):
            for p in [host,client]:
                for name in ['Interact','Shoulder','Fire','FireSemi']:cn_input(p,name,0)
        phase=combat_net['phase']
        if phase=='check_shoulders':
            for p in [host,client]:cn_input(p,'Aim',1)
        if now<combat_net['next']:return
        world=next(w for w in u.EditorLevelLibrary.get_pie_worlds(False) if host in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter))
        if phase=='position_pickups':
            # Opposing teams for this PvP test; the gym normally puts players
            # together and the practice characters on the other team.
            for actor in [host.player_state,host]:
                assert u.CRBlueprintTools.set_property_text(actor,'MyTeamID','(TeamID=1)')
                actor.force_net_update()
            assert u.LyraTeamStatics.find_team_from_object(host)[1]==1
            for pawn,kind in [(server_client,'Rifle'),(host,'Pistol')]:
                pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.BaselineWeaponPickup) if kind in a.item_definition.get_name())
                loc=pickup.get_actor_location()
                pawn.set_actor_location(u.Vector(loc.x-110,loc.y,94),False,True)
                pawn.set_actor_rotation(u.Rotator(yaw=0),False)
                pawn.force_net_update()
            for p in [host,client]:p.get_controller().set_control_rotation(u.Rotator(yaw=0))
            combat_net.update(phase='pickups',next=now+1)
        elif phase=='pickups':
            for p in [host,client]:cn_input(p,'Interact',1)
            combat_net.update(phase='swap',next=now+1.5,release=True)
        elif phase=='swap':
            for p in [host,client]:
                assert p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance),'Network weapon pickup failed'
                cn_input(p,'Shoulder',1)
                p.get_controller().set_control_rotation(u.Rotator(pitch=25,yaw=0))
            combat_net.update(phase='check_shoulders',next=now+1,release=True)
        elif phase=='check_shoulders':
            for i,p in enumerate([host,server_client,client,observer]):
                eq=p.baseline_equipment
                weapon=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).get_spawned_actors()[0]
                assert eq.is_left_shoulder() and eq.get_presentation_mesh().get_anim_instance().weapon_left_hand, 'Remote hand state not mirrored'
                assert str(weapon.root_component.get_attach_socket_name())=='weapon_l', 'Remote weapon on wrong hand'
                assert abs(eq.get_presentation_mesh().get_anim_instance().aim_pitch-25)<2, 'Remote left aim pitch wrong'
            combat_net['results'].append({'case':'host_and_client_left_hand_replication','roles':4})
            combat_net.update(phase='position_fight',next=now+.2)
        elif phase=='position_fight':
            for p in [host,client]:
                for name in ['Aim','Fire','FireSemi']:cn_input(p,name,0)
            source=server_client if combat_net['index']==0 else host
            target=host if combat_net['index']==0 else server_client
            for p,x,yaw in [(source,1500,0),(target,2200,180)]:
                p.character_movement.stop_movement_immediately()
                p.set_actor_location(u.Vector(x,-3200,94),False,True)
                p.set_actor_rotation(u.Rotator(yaw=yaw),False)
                p.force_net_update()
            combat_net.update(phase='shoot',next=now+1,started=now+1,old_target=target.get_name(),saw_death=set(),last_pulse=-1)
        elif phase=='shoot':
            owner=client if combat_net['index']==0 else host
            target=observer if combat_net['index']==0 else server_client
            server_target=host if combat_net['index']==0 else server_client
            victim_roles=[host,observer] if combat_net['index']==0 else [server_client,client]
            for i,p in enumerate(victim_roles):
                if 'DEAD' in str(p.physical_interaction.get_phase()):
                    combat_net['saw_death'].add(i)
                    assert p.mesh.is_simulating_physics('pelvis') and p.baseline_equipment.are_hands_busy()
            if len(combat_net['saw_death'])==2:
                for name in ['Fire','FireSemi','Aim']:cn_input(owner,name,0)
                combat_net['results'].append({'case':'client_kills_host' if combat_net['index']==0 else 'host_kills_client','fatal_ragdoll_views':2})
                combat_net.update(phase='respawn',next=now+3.8)
            else:
                assert now-combat_net['started']<12,'Network weapon never killed target'
                camera=owner.get_controller().player_camera_manager.get_camera_location()
                owner.get_controller().set_control_rotation(u.MathLibrary.find_look_at_rotation(camera,target.mesh.get_socket_location('spine_03')))
                cn_input(owner,'Aim',1)
                if combat_net['index']==0:cn_input(owner,'Fire',1)
                else:
                    pulse=int((now-combat_net['started'])/.25)%2
                    cn_input(owner,'Fire',pulse)
                    cn_input(owner,'FireSemi',pulse)
        elif phase=='respawn':
            victim=host if combat_net['index']==0 else server_client
            views=[host,observer] if combat_net['index']==0 else [server_client,client]
            assert victim.get_name()!=combat_net['old_target'],'Network player did not respawn'
            for p in views:
                h=p.get_component_by_class(u.LyraHealthComponent)
                assert h.get_health()==100 and not h.is_dead_or_dying()
                assert p.can_use_movement_actions() and not p.physical_interaction.is_busy()
                tag=u.GameplayTag(); tag.import_text('(TagName="Baseline.State.HandsBusy")')
                assert not u.AbilitySystemLibrary.get_ability_system_component(p).has_matching_gameplay_tag(tag), 'Old avatar left weapon abilities blocked'
            combat_net['results'].append({'case':'replicated_clean_respawn','victim':'host' if combat_net['index']==0 else 'client'})
            if combat_net['index']==1:cn_finish()
            else:
                pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.BaselineWeaponPickup) if a.item_definition.get_name()=='ID_Pistol_C')
                loc=pickup.get_actor_location()
                host.set_actor_location(u.Vector(loc.x-100,loc.y,94),False,True)
                host.set_actor_rotation(u.Rotator(yaw=0),False)
                host.get_controller().set_control_rotation(u.Rotator(yaw=0))
                combat_net.update(phase='rearm',next=now+.5)
        elif phase=='rearm':
            cn_input(host,'Interact',1)
            cn_input(host,'Shoulder',1)
            combat_net.update(phase='position_fight',index=1,next=now+1,release=True)
    except Exception:cn_finish(traceback.format_exc())
    finally:combat_net['busy']=False


combat_net['handle']=u.register_slate_post_tick_callback(cn_tick)
print('Started multiplayer hand swap and combat death checks')
