"""Switch the real widget in two-player PIE and inspect all four pawn views."""
import json
import math
import time
import traceback
from pathlib import Path
import unreal as u

visual_net={'phase':'setup','index':0,'next':0,'busy':False,'results':[],'deadline':time.monotonic()+180}
visual_net_out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/VisualOverride/network.json'
visual_net_widget=u.get_editor_subsystem(u.EditorUtilitySubsystem).spawn_and_register_tab(u.load_asset('/Game/Widgets/GameAnimationWidget'))
visual_net_names=['Echo','Twinblast','Kellan','Manny','Quinn','UE4_Mannequin','CrimsonSentinel', 'ObsidianSentinel', 'RegalCommander', 'TheSteadfastOfficer', 'UrbanTrailblazer']


def vn_context():
    pawns=[p for w in u.EditorLevelLibrary.get_pie_worlds(False) for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter)
           if 'TrainingPartner' not in p.get_class().get_name()]
    return (next(p for p in pawns if p.has_authority() and p.is_locally_controlled()),
            next(p for p in pawns if p.has_authority() and not p.is_locally_controlled()),
            next(p for p in pawns if not p.has_authority() and p.is_locally_controlled()),
            next(p for p in pawns if not p.has_authority() and not p.is_locally_controlled()))


def vn_input(pawn,name,value):
    path='/Game/Input/IA_Aim' if name=='Aim' else '/Game/Baseline/Input/IA_'+name
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
             if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pawn.get_controller())
    sub.inject_input_vector_for_action(u.load_asset(path),u.Vector(value,0,0),[],[])


def vn_click(index):
    visual_net_widget.get_editor_property('VisualOverrideListWrapBox').get_child_at(index).call_method(
        'BndEvt__EUW_CharacterSelectButton_EditorUtilityButton_K2Node_ComponentBoundEvent_3_OnButtonClickedEvent__DelegateSignature')


def vn_finish(error=None):
    u.unregister_slate_post_tick_callback(visual_net['handle'])
    visual_net.update(finished=True,error=error)
    visual_net_out.write_text(json.dumps({'passed':error is None,'error':error,'results':visual_net['results']},indent=2))
    print('VISUAL_NETWORK_COMPLETE',error)


def vn_tick(dt):
    if visual_net['busy']:return
    visual_net['busy']=True
    try:
        assert time.monotonic()<visual_net['deadline'],'Network visuals timed out'
        try:host,server_client,client,observer=vn_context()
        except StopIteration:return
        pawns=[host,server_client,client,observer]
        now=u.GameplayStatics.get_time_seconds(u.EditorLevelLibrary.get_pie_worlds(False)[0])
        if not all(p.physical_interaction.controls_created for p in pawns):return
        if visual_net.pop('release',False):
            for p in [host,client]:
                for name in ['Interact','Shoulder']:vn_input(p,name,0)
        if visual_net['phase'] not in ['setup','pickup','equip']:
            for p in [host,client]:
                p.get_controller().set_control_rotation(u.Rotator(pitch=25,yaw=90))
                vn_input(p,'Aim',1)
        if now<visual_net['next']:return
        phase=visual_net['phase']
        index=visual_net['index']
        if phase=='setup':
            world=next(w for w in u.EditorLevelLibrary.get_pie_worlds(False) if host in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter))
            for p,kind in [(host,'Pistol'),(server_client,'Rifle')]:
                pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.BaselineWeaponPickup) if kind in a.item_definition.get_name())
                loc=pickup.get_actor_location()
                p.set_actor_location(u.Vector(loc.x-110,loc.y,94),False,True)
                p.set_actor_rotation(u.Rotator(yaw=0),False)
                p.force_net_update()
            for p in [host,client]:
                p.get_controller().set_ignore_move_input(True);p.get_controller().set_ignore_look_input(True)
                p.get_controller().set_control_rotation(u.Rotator(yaw=0))
            visual_net['drivers']=[p.baseline_equipment.get_weapon_animation_mesh().get_path_name() for p in pawns]
            visual_net.update(phase='pickup',next=now+1)
        elif phase=='pickup':
            for p in [host,client]:vn_input(p,'Interact',1)
            visual_net.update(phase='equip',next=now+1.5,release=True)
        elif phase=='equip':
            for p in [host,client]:
                assert p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance),'Pickup failed'
                if not p.baseline_equipment.is_left_shoulder():vn_input(p,'Shoulder',1)
                p.get_controller().set_control_rotation(u.Rotator(pitch=25,yaw=90))
            visual_net.update(phase='select',next=now+1,release=True)
        elif phase=='select':
            current=u.SystemLibrary.get_console_variable_int_value('DDCvar.VisualOverride')
            if current==index:vn_click(index)
            vn_click(index)
            visual_net.update(phase='check',next=now+3,load_deadline=now+45)
        elif phase=='check':
            for p in pawns:
                actor=p.selected_visual_override.get_editor_property('child_actor')
                if not actor or visual_net_names[index].lower() not in actor.get_class().get_name().lower():
                    assert now<visual_net['load_deadline'],'Selection failed to replicate'
                    return
            errors=[]
            rolls=[]
            for role,p in enumerate(pawns):
                eq=p.baseline_equipment
                mesh=eq.get_presentation_mesh()
                driver=eq.get_weapon_animation_mesh()
                assert driver.get_path_name()==visual_net['drivers'][role]
                assert mesh!=driver and mesh.is_visible() and not driver.is_visible()
                assert eq.is_left_shoulder() and driver.get_anim_instance().weapon_left_hand
                assert abs(driver.get_anim_instance().aim_pitch-25)<2,(role,driver.get_anim_instance().aim_pitch,eq.is_weapon_ready())
                weapon=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).get_spawned_actors()[0]
                assert weapon.root_component.get_attach_parent()==mesh
                assert str(weapon.root_component.get_attach_socket_name()) in ['hand_l','weapon_l']
                muzzle=weapon.get_component_by_class(u.SkeletalMeshComponent).get_socket_rotation('Muzzle')
                aim=eq.get_weapon_aim_rotation()
                def direction(rot):
                    a,b=math.radians(rot.pitch),math.radians(rot.yaw)
                    return [math.cos(a)*math.cos(b),math.cos(a)*math.sin(b),math.sin(a)]
                error=math.degrees(math.acos(max(-1,min(1,sum(a*b for a,b in zip(direction(muzzle),direction(aim)))))))
                assert error<18,f'{visual_net_names[index]} role {role}: {error}'
                assert abs(muzzle.roll)<45,f'Weapon rolled over on role {role}: {muzzle.roll}'
                errors.append(error)
                rolls.append(muzzle.roll)
            visual_net['results'].append({'visual':visual_net_names[index],'roles':4,'left_muzzle_error_degrees':errors,'left_weapon_roll_degrees':rolls})
            visual_net['index']+=1
            if visual_net['index']==visual_net.get('last_index',len(visual_net_names)):
                vn_click(index)
                visual_net.update(phase='clear',next=now+2)
            else:visual_net.update(phase='select',next=now+.1)
        elif phase=='clear':
            for p in pawns:
                assert p.selected_visual_override.get_editor_property('child_actor') is None
                assert p.baseline_equipment.get_presentation_mesh()==p.baseline_equipment.get_weapon_animation_mesh()
                assert p.baseline_equipment.get_presentation_mesh().is_visible()
            visual_net['results'].append({'case':'clear_override','roles':4})
            for p in [host,client]:vn_input(p,'Aim',0)
            vn_finish()
    except Exception:vn_finish(traceback.format_exc())
    finally:visual_net['busy']=False


visual_net['handle']=u.register_slate_post_tick_callback(vn_tick)
print('Started multiplayer visual override checks')
