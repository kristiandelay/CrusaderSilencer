"""Exercise the widget's real click handler and keep combat through every skin."""
import json
import math
import time
import traceback
from pathlib import Path
import unreal as u

visual_out = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent / 'Artifacts/VisualOverride'
visual_out.mkdir(parents=True, exist_ok=True)
visual_widget = u.get_editor_subsystem(u.EditorUtilitySubsystem).spawn_and_register_tab(u.load_asset('/Game/Widgets/GameAnimationWidget'))
visual_test = {'phase':'setup', 'index':0, 'angle':0, 'next':0, 'results':[], 'busy':False, 'deadline':time.monotonic()+240}
visual_names = ['Echo', 'Twinblast', 'Kellan', 'Manny', 'Quinn', 'UE4_Mannequin', 'CrimsonSentinel', 'ObsidianSentinel', 'RegalCommander', 'TheSteadfastOfficer', 'UrbanTrailblazer']


def visual_input(pawn, name, value):
    paths={'Aim':'/Game/Input/IA_Aim','Fire':'/Game/Input/Actions/IA_Weapon_Fire_Auto','Reload':'/Game/Input/Actions/IA_Weapon_Reload'}
    subsystem=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
                   if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pawn.get_controller())
    subsystem.inject_input_vector_for_action(u.load_asset(paths.get(name,'/Game/Baseline/Input/IA_'+name)),u.Vector(value,0,0),[],[])


def visual_click(index):
    button=visual_widget.get_editor_property('VisualOverrideListWrapBox').get_child_at(index)
    button.call_method('BndEvt__EUW_CharacterSelectButton_EditorUtilityButton_K2Node_ComponentBoundEvent_3_OnButtonClickedEvent__DelegateSignature')


def visual_ammo(pawn):
    tag=u.GameplayTag();tag.import_text('(TagName="Lyra.ShooterGame.Weapon.MagazineAmmo")')
    return pawn.baseline_equipment.get_active_item().get_stat_tag_stack_count(tag)


def visual_finish(error=None):
    u.unregister_slate_post_tick_callback(visual_test['handle'])
    visual_test.update(finished=True,error=error)
    visual_test.pop('capture',None)
    (visual_out/'visual-overrides.json').write_text(json.dumps({'passed':error is None,'error':error,'results':visual_test['results']},indent=2))
    print('VISUAL_OVERRIDES_COMPLETE',error)


def visual_tick(dt):
    if visual_test['busy']:return
    visual_test['busy']=True
    try:
        assert time.monotonic()<visual_test['deadline'],'Visual override checks timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        pawn=u.GameplayStatics.get_player_pawn(worlds[0],0)
        if not pawn:return
        eq=pawn.baseline_equipment
        # Screenshot/asset compilation stalls wall time without advancing the
        # animation. Settle poses using game time; keep the overall wall timeout.
        now=u.GameplayStatics.get_time_seconds(worlds[0])
        phase=visual_test['phase']
        if visual_test.pop('release',False):
            for name in ['Interact','Shoulder','Fire','Reload']:visual_input(pawn,name,0)
        if phase in ['aim','measure','fire','fire_check']:visual_input(pawn,'Aim',1)
        if now<visual_test['next']:return
        if phase=='setup':
            assert visual_widget.get_editor_property('VisualOverrideListWrapBox').get_children_count()==len(visual_names)
            current=u.SystemLibrary.get_console_variable_int_value('DDCvar.VisualOverride')
            if current>=0:visual_click(current)
            visual_test['pawn']=pawn.get_name()
            visual_test['driver']=eq.get_weapon_animation_mesh().get_path_name()
            if not eq.get_active_item():
                pawn.set_actor_location(u.Vector(2100,-1100,94),False,True)
                pawn.get_controller().set_control_rotation(u.Rotator(yaw=0))
                visual_input(pawn,'Interact',1)
            visual_test.update(phase='select',next=now+1,release=True,pickup_deadline=now+30)
        elif phase=='select':
            if not eq.get_active_item() and now<visual_test['pickup_deadline']:return
            assert eq.get_active_item(),'Pick up a rifle before running the test'
            visual_input(pawn,'Aim',0)
            visual_click(visual_test['index'])
            visual_test.update(phase='selected',next=now+2,load_deadline=now+45)
        elif phase=='selected':
            index=visual_test['index']
            assert u.SystemLibrary.get_console_variable_int_value('DDCvar.VisualOverride')==index
            actor=pawn.selected_visual_override.get_editor_property('child_actor')
            if not actor or visual_names[index].lower() not in actor.get_class().get_name().lower():
                assert now<visual_test['load_deadline'],f'Timed out loading {visual_names[index]}'
                return
            assert actor and visual_names[index].lower() in actor.get_class().get_name().lower(),str(actor)
            mesh=eq.get_presentation_mesh()
            assert mesh!=eq.get_weapon_animation_mesh() and mesh.is_visible()
            assert not eq.get_weapon_animation_mesh().is_visible() and not pawn.mesh.is_visible()
            assert pawn.get_name()==visual_test['pawn'] and eq.get_weapon_animation_mesh().get_path_name()==visual_test['driver']
            assert mesh.get_bone_index('foot_l')>=0 and mesh.get_bone_index('hand_r')>=0
            assert mesh.get_socket_location('head').z>100,'Visible body is not retargeting'
            visual_test['results'].append({'case':'widget_select','visual':visual_names[index],'mesh':mesh.get_name()})
            visual_test.update(phase='aim',angle=0,next=now+.1)
        elif phase=='aim':
            angle=visual_test['angle']
            left=angle>=3
            if eq.is_left_shoulder()!=left:visual_input(pawn,'Shoulder',1)
            pitch=[0,40,-40][angle%3]
            pawn.get_controller().set_control_rotation(u.Rotator(pitch=pitch,yaw=90))
            visual_test.update(phase='measure',next=now+1.2,release=True)
        elif phase=='measure':
            mesh=eq.get_presentation_mesh()
            weapon=pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).get_spawned_actors()[0]
            muzzle=weapon.get_component_by_class(u.SkeletalMeshComponent).get_socket_rotation('Muzzle')
            aim=pawn.get_control_rotation()
            def direction(rot):
                p,y=math.radians(rot.pitch),math.radians(rot.yaw)
                return [math.cos(p)*math.cos(y),math.cos(p)*math.sin(y),math.sin(p)]
            error=math.degrees(math.acos(max(-1,min(1,sum(a*b for a,b in zip(direction(muzzle),direction(aim)))))))
            visual_test['results'].append({'case':'aim','visual':visual_names[visual_test['index']],'left':eq.is_left_shoulder(),'pitch':aim.pitch,'muzzle_error_degrees':error,'weapon_roll_degrees':muzzle.roll})
            assert error<18,f'{visual_names[visual_test["index"]]} weapon aim differs by {error:.1f} degrees'
            assert abs(muzzle.roll)<45,f'Weapon is rolled over: {muzzle.roll:.1f} degrees'
            assert weapon.root_component.get_attach_parent()==mesh
            if visual_test['angle'] in [0,3]:
                suffix='-left' if eq.is_left_shoulder() else '-right'
                visual_test['capture']=u.AutomationLibrary.take_high_res_screenshot(1280,800,str(visual_out/(visual_names[visual_test['index']]+suffix+'.png')),delay=0)
            visual_test['angle']+=1
            visual_test.update(phase='aim' if visual_test['angle']<6 else 'fire',next=now+.1)
        elif phase=='fire':
            visual_test['ammo']=visual_ammo(pawn)
            visual_input(pawn,'Fire',1)
            visual_test.update(phase='fire_check',next=now+.3,release=True)
        elif phase=='fire_check':
            assert visual_ammo(pawn)<visual_test['ammo'],'Skin change broke firing'
            visual_input(pawn,'Aim',0)
            visual_input(pawn,'Reload',1)
            visual_test.update(phase='swap_during_reload',next=now+.35,release=True)
        elif phase=='swap_during_reload':
            visual_click(visual_test['index'])
            visual_test.update(phase='reload_check',next=now+4)
        elif phase=='reload_check':
            assert u.SystemLibrary.get_console_variable_int_value('DDCvar.VisualOverride')==-1
            assert eq.get_presentation_mesh()==eq.get_weapon_animation_mesh() and eq.get_presentation_mesh().is_visible()
            assert visual_ammo(pawn)==visual_test['ammo'],'Changing skin interrupted the reload'
            visual_test['results'].append({'case':'fire_reload_and_clear','visual':visual_names[visual_test['index']]})
            visual_test['index']+=1
            if visual_test['index']==len(visual_names):visual_finish()
            else:visual_test.update(phase='select',next=now+.1)
    except Exception:visual_finish(traceback.format_exc())
    finally:visual_test['busy']=False


visual_test['handle']=u.register_slate_post_tick_callback(visual_tick)
print('Started widget visual override checks for all catalog characters')
