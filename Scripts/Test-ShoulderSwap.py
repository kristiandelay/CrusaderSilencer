"""Mapped hand/camera swaps with all three weapons, aim angles and ammo transactions."""
import json
import math
import time
import traceback
from pathlib import Path
import unreal as u

shoulder_out = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent / 'Artifacts/CombatTests'
shoulder_out.mkdir(parents=True, exist_ok=True)
shoulder_test = {'phase': 'pickup', 'weapon': 0, 'side': 0, 'angle': 0, 'next': 0,
                 'results': [], 'busy': False, 'deadline': time.monotonic()+200}
shoulder_angles = [(0,0), (45,0), (-45,0), (20,55), (-20,-55)]


def combat_input(pawn, action, value):
    paths = {'Fire': '/Game/Input/Actions/IA_Weapon_Fire_Auto', 'FireSemi': '/Game/Input/Actions/IA_Weapon_Fire',
             'Reload': '/Game/Input/Actions/IA_Weapon_Reload', 'Aim': '/Game/Input/IA_Aim'}
    subsystem = next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
                     if isinstance(s.get_outer(), u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pawn.get_controller())
    subsystem.inject_input_vector_for_action(u.load_asset(paths.get(action, '/Game/Baseline/Input/IA_'+action)),
                                            u.Vector(value,0,0), [], [])


def combat_ammo(item, name='MagazineAmmo'):
    tag = u.GameplayTag()
    tag.import_text('(TagName="Lyra.ShooterGame.Weapon.'+name+'")')
    return item.get_stat_tag_stack_count(tag)


def combat_muzzle_error(pawn):
    weapon = pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).get_spawned_actors()[0]
    muzzle = weapon.get_component_by_class(u.SkeletalMeshComponent).get_socket_rotation('Muzzle')
    aim = pawn.get_control_rotation()
    def direction(r):
        p,y = math.radians(r.pitch),math.radians(r.yaw)
        return math.cos(p)*math.cos(y),math.cos(p)*math.sin(y),math.sin(p)
    return math.degrees(math.acos(max(-1,min(1,sum(a*b for a,b in zip(direction(muzzle),direction(aim)))))))


def shoulder_finish(error=None):
    u.unregister_slate_post_tick_callback(shoulder_test['handle'])
    shoulder_test['finished'] = True
    shoulder_test.pop('capture',None)
    (shoulder_out/'shoulder-swap.json').write_text(json.dumps({'passed':error is None,'error':error,
                                                            'results':shoulder_test['results']},indent=2))
    print('SHOULDER_TEST_COMPLETE',error)


def shoulder_tick(dt):
    if shoulder_test['busy']: return
    shoulder_test['busy']=True
    try:
        assert time.monotonic()<shoulder_test['deadline'], 'Shoulder test timeout'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds: return
        pawn=u.GameplayStatics.get_player_pawn(worlds[0],0)
        if not pawn or not pawn.physical_interaction.controls_created: return
        now=u.GameplayStatics.get_time_seconds(worlds[0])
        if shoulder_test['phase'] in ['angle','measure','fire']:
            combat_input(pawn,'Aim',1)
        if shoulder_test.pop('release',False):
            for name in ['Interact','Shoulder','Fire','FireSemi','Reload']: combat_input(pawn,name,0)
        if now<shoulder_test['next']: return
        eq=pawn.baseline_equipment
        kind=['Rifle','Pistol','Shotgun'][shoulder_test['weapon']]
        phase=shoulder_test['phase']
        if phase=='pickup':
            combat_input(pawn,'Aim',0)
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(worlds[0],u.BaselineWeaponPickup) if kind in a.item_definition.get_name())
            loc=pickup.get_actor_location()
            pawn.character_movement.stop_movement_immediately()
            pawn.set_actor_location(u.Vector(loc.x-110,loc.y,94),False,True)
            pawn.set_actor_rotation(u.Rotator(yaw=0),False)
            pawn.get_controller().set_control_rotation(u.Rotator(yaw=0))
            combat_input(pawn,'Interact',1)
            shoulder_test.update(phase='side',next=now+1.5,release=True,side=0,angle=0)
        elif phase=='side':
            assert kind in pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).get_class().get_name()
            desired=shoulder_test['side']==1
            if eq.is_left_shoulder()!=desired: combat_input(pawn,'Shoulder',1)
            combat_input(pawn,'Aim',1)
            shoulder_test.update(phase='angle',next=now+.7,release=True)
        elif phase=='angle':
            pitch,yaw=shoulder_angles[shoulder_test['angle']]
            pawn.set_actor_rotation(u.Rotator(yaw=0),False)
            pawn.get_controller().set_control_rotation(u.Rotator(pitch=pitch,yaw=yaw))
            shoulder_test.update(phase='measure',next=now+1.1)
        elif phase=='measure':
            left=shoulder_test['side']==1
            weapon=pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).get_spawned_actors()[0]
            mesh=eq.get_presentation_mesh()
            socket='weapon_l' if left else 'weapon_r'
            assert eq.is_left_shoulder()==left and mesh.get_anim_instance().weapon_left_hand==left
            assert str(weapon.root_component.get_attach_socket_name())==socket
            grip_error=(weapon.get_actor_location()-mesh.get_socket_location(socket)).length()
            error=combat_muzzle_error(pawn)
            roll=weapon.get_component_by_class(u.SkeletalMeshComponent).get_socket_rotation('Muzzle').roll
            assert error<18, f'{kind} {socket} muzzle error {error:.1f}'
            assert abs(roll)<45, f'{kind} {socket} upside-down weapon: {roll:.1f} degrees'
            assert grip_error<1, f'Weapon not seated in {socket}: {grip_error}'
            camera=pawn.get_controller().player_camera_manager.get_camera_location()
            yaw=math.radians(pawn.get_control_rotation().yaw)
            delta=camera-pawn.get_actor_location()
            lateral=-math.sin(yaw)*delta.x+math.cos(yaw)*delta.y
            assert lateral*(-1 if left else 1)>10, 'Camera on wrong shoulder'
            if shoulder_test['weapon']==0 and shoulder_test['angle']==0:
                shoulder_test['capture']=u.AutomationLibrary.take_high_res_screenshot(1280,800,
                    str(shoulder_out/('rifle-left.png' if left else 'rifle-right.png')),delay=0)
            shoulder_test['results'].append({'case':'aim_and_grip','weapon':kind,'left':left,
                'angle':shoulder_angles[shoulder_test['angle']],'muzzle_error_degrees':error,'weapon_roll_degrees':roll,'grip_error_cm':grip_error,'camera_lateral_cm':lateral})
            shoulder_test['angle']+=1
            shoulder_test.update(phase='angle' if shoulder_test['angle']<len(shoulder_angles) else 'fire',next=now+.1)
        elif phase=='fire':
            # Shoot an empty lane to keep the target/respawn checks independent.
            pawn.get_controller().set_control_rotation(u.Rotator(pitch=25,yaw=90))
            item=eq.get_active_item()
            shoulder_test['before']=combat_ammo(item)
            shoulder_test['total']=combat_ammo(item)+combat_ammo(item,'SpareAmmo')
            for name in ['Fire','FireSemi']: combat_input(pawn,name,1)
            shoulder_test.update(phase='reload',next=now+.3,release=True)
        elif phase=='reload':
            item=eq.get_active_item()
            after=combat_ammo(item)
            assert after<shoulder_test['before'],'No shot on selected shoulder'
            shoulder_test['spent']=shoulder_test['before']-after
            combat_input(pawn,'Aim',0)
            combat_input(pawn,'Reload',1)
            shoulder_test.update(phase='reload_check',next=now+4,release=True)
        elif phase=='reload_check':
            item=eq.get_active_item()
            assert combat_ammo(item)==shoulder_test['before'],'Reload did not refill magazine'
            assert combat_ammo(item)+combat_ammo(item,'SpareAmmo')==shoulder_test['total']-shoulder_test['spent'],'Reload duplicated/lost ammunition'
            shoulder_test['results'].append({'case':'fire_and_reload','weapon':kind,'left':shoulder_test['side']==1,'rounds_fired':shoulder_test['spent']})
            shoulder_test['side']+=1
            if shoulder_test['side']<2: shoulder_test.update(phase='side',angle=0,next=now+.2)
            else:
                shoulder_test['weapon']+=1
                if shoulder_test['weapon']==3: shoulder_finish()
                else: shoulder_test.update(phase='pickup',next=now+.3)
    except Exception: shoulder_finish(traceback.format_exc())
    finally: shoulder_test['busy']=False


shoulder_test['handle']=u.register_slate_post_tick_callback(shoulder_tick)
print('Started shoulder/hand/aim/reload checks')
