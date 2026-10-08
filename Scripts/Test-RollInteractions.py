"""Validate recovery cadence, shooting gates, crouch, NPC parity and interruptions."""
import json,time,traceback
from pathlib import Path
import unreal as u

ri_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
ri_test=dict(phase='setup',next=0,busy=False,results=[],deadline=time.monotonic()+100)

def ri_input(p,name,value):
    paths={'Aim':'/Game/Input/IA_Aim','Fire':'/Game/Input/Actions/IA_Weapon_Fire_Auto'}
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==p.get_controller())
    sub.inject_input_vector_for_action(u.load_asset(paths[name]),u.Vector(value,0,0),[],[])

def ri_ammo(p):
    tag=u.GameplayTag();tag.import_text('(TagName="Lyra.ShooterGame.Weapon.MagazineAmmo")')
    return p.baseline_equipment.get_active_item().get_stat_tag_stack_count(tag)

def ri_finish(error=None):
    u.unregister_slate_post_tick_callback(ri_test['handle']);ri_test.update(finished=True,error=error)
    (ri_root/'Artifacts/Roll/interactions.json').write_text(json.dumps(dict(passed=error is None,error=error,results=ri_test['results']),indent=2)+'\n')
    print('ROLL_INTERACTIONS',error)

def ri_tick(dt):
    if ri_test['busy']:return
    ri_test['busy']=True
    try:
        assert time.monotonic()<ri_test['deadline'],'Roll interactions timed out'
        ws=u.EditorLevelLibrary.get_pie_worlds(False)
        if not ws:return
        w=ws[0];p=u.GameplayStatics.get_player_pawn(w,0)
        if not p or not p.physical_interaction.controls_created:return
        now=u.GameplayStatics.get_time_seconds(w);phase=ri_test['phase']
        if phase=='fire_blocked':ri_input(p,'Fire',1)
        if phase=='fire_restored':ri_input(p,'Fire',1)
        if now<ri_test['next']:return
        if phase=='setup':
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(w,u.BaselineWeaponPickup) if 'Rifle' in a.item_definition.get_name())
            pos=pickup.get_actor_location();p.set_actor_location(pos+u.Vector(-110,0,94-pos.z),False,True);p.baseline_equipment.server_pickup(pickup)
            ri_test.update(phase='place',next=now+1)
        elif phase=='place':
            p.set_actor_location(u.Vector(5000,2500,94),False,True);p.set_actor_rotation(u.Rotator(),False);p.get_controller().set_control_rotation(u.Rotator())
            ri_input(p,'Aim',1);ri_test.update(phase='roll',next=now+.5)
        elif phase=='roll':
            assert p.roll.request_roll(u.Vector(1,0,0))
            ri_test.update(ammo=ri_ammo(p),phase='fire_blocked',next=now+.5,began=now)
        elif phase=='fire_blocked':
            assert p.roll.is_rolling() and ri_ammo(p)==ri_test['ammo'],'Fired during roll'
            ri_input(p,'Fire',0);ri_test.update(phase='cooldown',next=ri_test['began']+1.04)
        elif phase=='cooldown':
            assert not p.roll.is_rolling(),'Roll has not finished'
            assert not p.roll.request_roll(u.Vector(1,0,0)),'Recovery cooldown bypassed'
            ri_test.update(phase='repeat',next=ri_test['began']+1.65)
        elif phase=='repeat':
            assert p.roll.request_roll(u.Vector(1,0,0)),'Roll stayed on cooldown'
            ri_test['results'].append(dict(case='cooldown',blocked_after_animation=True,reusable_after_1_65_seconds=True))
            ri_test.update(phase='fire_start',next=now+1.3)
        elif phase=='fire_start':
            assert not p.roll.is_rolling();ri_test.update(phase='fire_restored',next=now+.35)
        elif phase=='fire_restored':
            ri_input(p,'Fire',0);assert ri_ammo(p)<ri_test['ammo'],'Shooting stayed blocked'
            ri_test['results'].append(dict(case='shooting',blocked_during_roll=True,restored_after=True))
            ri_input(p,'Aim',0);p.crouch();ri_test.update(phase='crouch_roll',next=now+.7)
        elif phase=='crouch_roll':
            assert p.is_crouched;assert p.roll.request_roll(u.Vector(0,1,0))
            ri_test.update(phase='crouch_check',next=now+1.4)
        elif phase=='crouch_check':
            assert p.is_crouched and not p.roll.is_rolling(),'Crouch state lost'
            p.un_crouch();ri_test['results'].append(dict(case='crouch_preserved',passed=True))
            ri_test.update(phase='npc_place',next=now+.5,role='Guard')
        elif phase=='npc_place':
            guard=ri_test['role']=='Guard'
            npc=next(a for a in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if a.crowd_agent.enabled and not isinstance(a,u.CRRobotCharacter) and a.crowd_agent.initialized and a.crowd_agent.guard==guard)
            ctrl=npc.get_controller();ctrl.stop_movement();ctrl.set_actor_tick_enabled(False)
            npc.character_movement.stop_movement_immediately();npc.un_crouch()
            npc.set_actor_location(u.Vector(8000,-1850,94),False,True);npc.set_actor_rotation(u.Rotator(),False)
            for key,value in [('CurrentArea','None'),('Threat','None')]:u.CRBlueprintTools.set_property_text(npc.crowd_agent,key,value)
            ri_test.update(npc=npc,phase='npc_roll',next=now+.7)
        elif phase=='npc_roll':
            npc=ri_test['npc'];assert npc.get_controller().request_movement_action('Roll',npc.get_actor_location()+u.Vector(700,0,0)),ri_test['role']+' roll rejected'
            ri_test.update(start=npc.get_actor_location(),phase='npc_check',next=now+1.1)
        elif phase=='npc_check':
            npc=ri_test['npc'];distance=(npc.get_actor_location()-ri_test['start']).length()
            assert 300<distance<560 and not npc.roll.is_rolling(),(ri_test['role'],distance)
            assert npc.can_use_movement_actions()
            ri_test['results'].append(dict(case='npc_roll',role=ri_test['role'],distance_cm=distance))
            if ri_test['role']=='Guard':
                ri_test['guard']=npc;ri_test.update(role='Civilian',phase='npc_place',next=now+.1)
            else:
                npc.get_controller().set_actor_tick_enabled(True)
                ri_test.update(phase='death_roll',next=now+.5)
        elif phase=='death_roll':
            npc=ri_test['guard'];assert npc.roll.request_roll(u.Vector(1,0,0))
            ri_test.update(phase='kill',next=now+.2)
        elif phase=='kill':
            npc=ri_test['guard'];assert npc.roll.is_rolling()
            asc=u.AbilitySystemLibrary.get_ability_system_component(p)
            effect=u.load_asset('/Game/GameplayEffects/Damage/GE_Damage_Basic_SetByCaller').generated_class()
            spec=asc.make_outgoing_spec(effect,1,asc.make_effect_context())
            tag=u.GameplayTag();tag.import_text('(TagName="SetByCaller.Damage")')
            spec=u.AbilitySystemLibrary.assign_tag_set_by_caller_magnitude(spec,tag,500)
            u.AbilitySystemLibrary.get_ability_system_component(npc).apply_gameplay_effect_spec_to_self(spec)
            ri_test.update(phase='death_check',next=now+.2)
        elif phase=='death_check':
            npc=ri_test['guard'];assert npc.get_component_by_class(u.LyraHealthComponent).is_dead_or_dying()
            assert not npc.roll.is_rolling() and not npc.roll.request_roll(u.Vector(1,0,0))
            ri_test['results'].append(dict(case='death_interrupt',passed=True))
            assert p.roll.request_roll(u.Vector(1,0,0));ri_test.update(phase='ragdoll',next=now+.2)
        elif phase=='ragdoll':
            # The debug toggle deliberately rejects busy hands; simulate an external knockdown.
            assert p.roll.is_rolling();p.physical_interaction.start_ragdoll(u.Vector());ri_test.update(phase='ragdoll_check',next=now+.25)
        elif phase=='ragdoll_check':
            assert not p.roll.is_rolling() and p.physical_interaction.is_busy()
            ri_test.update(phase='get_up',next=now+3)
        elif phase=='get_up':
            p.physical_interaction.request_recovery();ri_test.update(phase='recover',next=now+4)
        elif phase=='recover':
            assert p.can_use_movement_actions() and p.roll.request_roll(u.Vector(1,0,0)),'Roll unavailable after get-up'
            ri_test['results'].append(dict(case='ragdoll_interrupt_and_recovery',passed=True));ri_finish()
    except Exception:ri_finish(traceback.format_exc())
    finally:ri_test['busy']=False
ri_test['handle']=u.register_slate_post_tick_callback(ri_tick)
print('ROLL_INTERACTIONS_STARTED')
