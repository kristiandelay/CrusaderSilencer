"""Verify the real widget, new rig, rifle sockets, both hands and ammo in PIE."""
import json
import math
import time
import traceback
from pathlib import Path
import unreal as u

cs_out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/CrimsonSentinel'
cs_widget=u.get_editor_subsystem(u.EditorUtilitySubsystem).spawn_and_register_tab(u.load_asset('/Game/Widgets/GameAnimationWidget'))
cs_test={'phase':'ready','next':0,'busy':False,'deadline':time.monotonic()+240,'results':[],'angle':0}
cs_angles=[(False,0,0),(False,40,35),(False,-40,-35),(True,0,0),(True,40,35),(True,-40,-35)]

def cs_input(pawn,name,value):
    paths={'Aim':'/Game/Input/IA_Aim','Fire':'/Game/Input/Actions/IA_Weapon_Fire_Auto','Reload':'/Game/Input/Actions/IA_Weapon_Reload','Move':'/Game/Input/IA_Move','Sprint':'/Game/Input/IA_Sprint','Crouch':'/Game/Input/IA_Crouch'}
    subsystem=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pawn.get_controller())
    subsystem.inject_input_vector_for_action(u.load_asset(paths.get(name,'/Game/Baseline/Input/IA_'+name)),u.Vector(*value) if isinstance(value,tuple) else u.Vector(value,0,0),[],[])

def cs_ammo(pawn,name='MagazineAmmo'):
    tag=u.GameplayTag();tag.import_text('(TagName="Lyra.ShooterGame.Weapon.'+name+'")')
    return pawn.baseline_equipment.get_active_item().get_stat_tag_stack_count(tag)

def cs_click(index):
    cs_widget.get_editor_property('VisualOverrideListWrapBox').get_child_at(index).call_method('BndEvt__EUW_CharacterSelectButton_EditorUtilityButton_K2Node_ComponentBoundEvent_3_OnButtonClickedEvent__DelegateSignature')

def cs_finish(error=None):
    u.unregister_slate_post_tick_callback(cs_test['handle'])
    cs_test.update(finished=True,error=error)
    cs_test.pop('capture',None)
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    if worlds:
        pawn=u.GameplayStatics.get_player_pawn(worlds[0],0)
        if pawn:
            for name in ['Aim','Fire','Reload','Interact','Shoulder','Move','Sprint','Crouch']:cs_input(pawn,name,0)
            pawn.get_controller().set_view_target_with_blend(pawn,0)
    if cs_test.get('camera'):cs_test.pop('camera').destroy_actor()
    (cs_out/'gameplay-validation.json').write_text(json.dumps({'passed':error is None,'error':error,'results':cs_test['results']},indent=2))
    print('CRIMSON_GAMEPLAY_COMPLETE',error)

def cs_tick(dt):
    if cs_test['busy']:return
    cs_test['busy']=True
    try:
        assert time.monotonic()<cs_test['deadline'],'Crimson validation timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        pawn=u.GameplayStatics.get_player_pawn(worlds[0],0)
        if not pawn or not pawn.physical_interaction.controls_created:return
        now=u.GameplayStatics.get_time_seconds(worlds[0]);eq=pawn.baseline_equipment
        phase=cs_test['phase']
        if cs_test.pop('release',False):
            for name in ['Interact','Shoulder','Reload','Fire']:cs_input(pawn,name,0)
        if phase in ['angle','measure','fire','fired']:cs_input(pawn,'Aim',1)
        if now<cs_test['next']:return
        if phase=='ready':
            visual=pawn.selected_visual_override.get_editor_property('child_actor')
            if not visual:return
            assert 'CrimsonSentinel' in visual.get_class().get_name()
            assert u.SystemLibrary.get_console_variable_int_value('DDCvar.VisualOverride')==6
            assert cs_widget.get_editor_property('VisualOverrideListWrapBox').get_children_count()>=7
            mesh=eq.get_presentation_mesh()
            for side in ['l','r']:
                for finger in ['thumb','index','middle','ring','pinky']:
                    for i in range(1,4):assert mesh.get_bone_index(f'{finger}_{i:02d}_{side}')>=0
            assert 120<mesh.get_socket_location('head').z<200
            cs_test['driver']=eq.get_weapon_animation_mesh().get_path_name()
            cs_test['pawn']=pawn.get_name()
            cs_test['results'].append({'case':'default_skin_and_30_finger_joints','widget_entries':cs_widget.get_editor_property('VisualOverrideListWrapBox').get_children_count()})
            cs_click(3);cs_test.update(phase='manny',next=now+1)
        elif phase=='manny':
            assert 'Manny' in pawn.selected_visual_override.get_editor_property('child_actor').get_class().get_name()
            cs_click(6);cs_test.update(phase='pickup',next=now+1)
        elif phase=='pickup':
            assert 'CrimsonSentinel' in pawn.selected_visual_override.get_editor_property('child_actor').get_class().get_name()
            assert eq.get_weapon_animation_mesh().get_path_name()==cs_test['driver'] and pawn.get_name()==cs_test['pawn']
            cs_test['results'].append({'case':'widget_switch_away_and_back'})
            pawn.set_actor_location(u.Vector(2100,-1100,94),False,True)
            pawn.set_actor_rotation(u.Rotator(yaw=0),False);pawn.get_controller().set_control_rotation(u.Rotator(yaw=0))
            if not eq.get_active_item():cs_input(pawn,'Interact',1)
            cs_test.update(phase='equipped',next=now+1,release=True)
        elif phase=='equipped':
            assert eq.get_active_item()
            weapon=pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).get_spawned_actors()[0]
            mesh=weapon.get_component_by_class(u.SkeletalMeshComponent)
            assert mesh.get_editor_property('skeletal_mesh_asset').get_name()=='BlackIronRifle'
            assert mesh.get_material(0).get_name()=='M_BlackIronRifle'
            assert abs(mesh.get_socket_transform('Grip').scale3d.x-1)<.01
            assert (mesh.get_socket_location('Muzzle')-weapon.get_actor_location()).length()<110
            cs_test['results'].append({'case':'rifle_pickup_material_and_unit_scale_sockets'})
            cs_test.update(phase='angle',next=now+.3)
        elif phase=='angle':
            left,pitch,yaw=cs_angles[cs_test['angle']]
            if eq.is_left_shoulder()!=left:cs_input(pawn,'Shoulder',1)
            pawn.get_controller().set_control_rotation(u.Rotator(pitch=pitch,yaw=yaw))
            cs_test.update(phase='measure',next=now+1.5,release=True)
        elif phase=='measure':
            left,pitch,yaw=cs_angles[cs_test['angle']]
            mesh=eq.get_presentation_mesh();driver=eq.get_weapon_animation_mesh()
            weapon=pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).get_spawned_actors()[0]
            wm=weapon.get_component_by_class(u.SkeletalMeshComponent);muzzle=wm.get_socket_rotation('Muzzle')
            def direction(r):
                p,y=math.radians(r.pitch),math.radians(r.yaw)
                return [math.cos(p)*math.cos(y),math.cos(p)*math.sin(y),math.sin(p)]
            error=math.degrees(math.acos(max(-1,min(1,sum(a*b for a,b in zip(direction(muzzle),direction(pawn.get_control_rotation())))))))
            hand_error=max((mesh.get_socket_location(n)-driver.get_socket_location(n)).length() for n in ['hand_l','hand_r'])
            result={'case':'aim_and_hand','left':left,'pitch':pitch,'yaw':yaw,'muzzle_error_degrees':error,'roll_degrees':muzzle.roll,'hand_target_error_cm':hand_error}
            cs_test['results'].append(result)
            assert eq.is_left_shoulder()==left and driver.get_anim_instance().weapon_left_hand==left
            assert str(weapon.root_component.get_attach_socket_name())==('hand_l' if left else 'hand_r')
            assert error<18 and abs(muzzle.roll)<45,result
            assert hand_error<5,result
            assert (wm.get_socket_location('Muzzle')-weapon.get_actor_location()).length()<110
            if pitch==0:
                cs_test['capture']=u.AutomationLibrary.take_high_res_screenshot(1440,1000,str(cs_out/('LeftShoulder.png' if left else 'RightShoulder.png')),delay=0)
                cs_test.update(phase='fire',next=now+.5)
            else:
                cs_test['angle']+=1
                cs_test.update(phase='angle' if cs_test['angle']<len(cs_angles) else 'done',next=now+.2)
        elif phase=='fire':
            cs_test['ammo_before']=cs_ammo(pawn);cs_test['total_before']=cs_ammo(pawn)+cs_ammo(pawn,'SpareAmmo')
            cs_input(pawn,'Fire',1);cs_test.update(phase='fired',next=now+.35,release=True)
        elif phase=='fired':
            cs_test['spent']=cs_test['ammo_before']-cs_ammo(pawn)
            assert cs_test['spent']>0,'Rifle did not fire'
            cs_input(pawn,'Aim',0);cs_input(pawn,'Reload',1)
            cs_test.update(phase='reloaded',next=now+3.5,release=True)
        elif phase=='reloaded':
            assert cs_ammo(pawn)==30,'Rifle reload did not finish'
            assert cs_ammo(pawn)+cs_ammo(pawn,'SpareAmmo')==cs_test['total_before']-cs_test['spent']
            cs_test['results'].append({'case':'fire_and_reload','left':eq.is_left_shoulder(),'rounds_fired':cs_test['spent']})
            cs_test['angle']+=1;cs_test.update(phase='angle',next=now+.2)
        elif phase=='done':cs_finish()
    except Exception:cs_finish(traceback.format_exc())
    finally:cs_test['busy']=False

cs_test['handle']=u.register_slate_post_tick_callback(cs_tick)
print('Started Crimson Sentinel widget, rig and rifle validation')
