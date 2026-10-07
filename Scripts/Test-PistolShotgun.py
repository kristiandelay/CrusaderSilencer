"""Check the replacement models, moving parts, both shoulders, fire and reload."""
import json
import math
import time
import traceback
from pathlib import Path
import unreal as u

wr_out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/WeaponReplacements'
wr_specs=[('Pistol','FuturisticPistol','Slide'),('Shotgun','TitanBreaker','Bolt')]
wr_angles=[(0,0),(40,35),(-40,-35)]
wr={'phase':'pickup','index':0,'side':0,'angle':0,'next':0,'busy':False,'results':[],
    'deadline':time.monotonic()+240}

def wr_input(pawn,name,value):
    paths={'Aim':'/Game/Input/IA_Aim','Fire':'/Game/Input/Actions/IA_Weapon_Fire',
           'FireAuto':'/Game/Input/Actions/IA_Weapon_Fire_Auto','Reload':'/Game/Input/Actions/IA_Weapon_Reload'}
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
             if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pawn.get_controller())
    sub.inject_input_vector_for_action(u.load_asset(paths.get(name,'/Game/Baseline/Input/IA_'+name)),u.Vector(value,0,0),[],[])

def wr_ammo(pawn,name='MagazineAmmo'):
    tag=u.GameplayTag();tag.import_text('(TagName="Lyra.ShooterGame.Weapon.'+name+'")')
    return pawn.baseline_equipment.get_active_item().get_stat_tag_stack_count(tag)

def wr_component(pawn):
    instance=pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
    return instance.get_spawned_actors()[0].get_component_by_class(u.SkeletalMeshComponent)

def wr_position(mesh,bone):
    return mesh.get_socket_transform(bone,u.RelativeTransformSpace.RTS_COMPONENT).translation

def wr_finish(error=None):
    u.unregister_slate_post_tick_callback(wr['handle'])
    wr.update(finished=True,error=error)
    wr.pop('capture',None)
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    if worlds:
        pawn=u.GameplayStatics.get_player_pawn(worlds[0],0)
        if pawn:
            for name in ['Aim','Fire','FireAuto','Reload','Interact','Shoulder']:wr_input(pawn,name,0)
    (wr_out/'gameplay-validation.json').write_text(json.dumps({'passed':error is None,'error':error,'results':wr['results']},indent=2))
    print('WEAPON_REPLACEMENTS_COMPLETE',error)

def wr_tick(dt):
    if wr['busy']:return
    wr['busy']=True
    try:
        assert time.monotonic()<wr['deadline'],'Weapon check timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        world=worlds[0];pawn=u.GameplayStatics.get_player_pawn(world,0)
        if not pawn or not pawn.physical_interaction.controls_created:return
        eq=pawn.baseline_equipment
        now=u.GameplayStatics.get_time_seconds(world)
        kind,name,moving_bone=wr_specs[wr['index']]
        phase=wr['phase']
        if wr.pop('release',False):
            for action in ['Fire','FireAuto','Reload','Interact','Shoulder']:wr_input(pawn,action,0)
        if phase in ['angle','measure','fire','fired']:wr_input(pawn,'Aim',1)
        if phase in ['fired','reloaded']:
            bone=moving_bone if phase=='fired' else 'Magazine'
            travel=(wr_position(wr_component(pawn),bone)-u.Vector(*wr['part_rest'])).length()
            wr['part_travel']=max(wr['part_travel'],travel)
        if now<wr['next']:return
        if phase=='pickup':
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.BaselineWeaponPickup)
                        if a.item_definition.get_name()=='ID_'+kind+'_C')
            assert pickup.display_mesh.get_editor_property('skeletal_mesh_asset').get_name()==name
            wr_input(pawn,'Aim',0)
            pawn.character_movement.stop_movement_immediately()
            loc=pickup.get_actor_location()
            pawn.set_actor_location(u.Vector(loc.x-110,loc.y,94),False,True)
            pawn.set_actor_rotation(u.Rotator(yaw=0),False)
            pawn.get_controller().set_control_rotation(u.Rotator(yaw=0))
            wr_input(pawn,'Interact',1)
            wr.update(phase='equipped',next=now+1.5,release=True,side=0,angle=0)
        elif phase=='equipped':
            mesh=wr_component(pawn)
            assert mesh.get_editor_property('skeletal_mesh_asset').get_name()==name
            assert mesh.get_material(0).get_name()=='M_'+name
            assert mesh.get_anim_instance(),'Weapon animation blueprint did not initialize'
            assert abs(mesh.get_socket_transform('Grip').scale3d.x-1)<.01
            assert 'CrimsonSentinel' in eq.get_presentation_mesh().get_editor_property('skeletal_mesh_asset').get_name()
            wr['results'].append({'case':'pickup_material_animation_scale','weapon':name})
            wr.update(phase='angle',next=now+.3)
        elif phase=='angle':
            if eq.is_left_shoulder()!=(wr['side']==1):wr_input(pawn,'Shoulder',1)
            pitch,yaw=wr_angles[wr['angle']]
            pawn.get_controller().set_control_rotation(u.Rotator(pitch=pitch,yaw=yaw))
            wr.update(phase='measure',next=now+1.4,release=True)
        elif phase=='measure':
            mesh=wr_component(pawn);actor=mesh.get_owner();muzzle=mesh.get_socket_rotation('Muzzle')
            def direction(r):
                p,y=math.radians(r.pitch),math.radians(r.yaw)
                return [math.cos(p)*math.cos(y),math.cos(p)*math.sin(y),math.sin(p)]
            error=math.degrees(math.acos(max(-1,min(1,sum(a*b for a,b in zip(direction(muzzle),direction(pawn.get_control_rotation())))))))
            hand_error=max((eq.get_presentation_mesh().get_socket_location(b)-eq.get_weapon_animation_mesh().get_socket_location(b)).length() for b in ['hand_l','hand_r'])
            left=wr['side']==1
            assert eq.is_left_shoulder()==left and eq.get_weapon_animation_mesh().get_anim_instance().weapon_left_hand==left
            assert actor.root_component.get_attach_parent()==eq.get_presentation_mesh()
            assert str(actor.root_component.get_attach_socket_name())==('hand_l' if left else 'hand_r')
            result={'case':'aim_and_grip','weapon':name,'left':left,'angle':wr_angles[wr['angle']],
                    'muzzle_error_degrees':error,'roll_degrees':muzzle.roll,'hand_target_error_cm':hand_error}
            wr['results'].append(result)
            assert error<18 and abs(muzzle.roll)<45 and hand_error<6,result
            if wr['angle']==0:
                wr['capture']=u.AutomationLibrary.take_high_res_screenshot(1440,1000,str(wr_out/(name+('-Left.png' if left else '-Right.png'))),delay=0)
            wr['angle']+=1
            wr.update(phase='angle' if wr['angle']<len(wr_angles) else 'fire',next=now+.2)
        elif phase=='fire':
            mesh=wr_component(pawn)
            wr.update(before=wr_ammo(pawn),total=wr_ammo(pawn)+wr_ammo(pawn,'SpareAmmo'),
                      part_rest=list(wr_position(mesh,moving_bone).to_tuple()),part_travel=0)
            for action in ['Fire','FireAuto']:wr_input(pawn,action,1)
            wr.update(phase='fired',next=now+.65,release=True)
        elif phase=='fired':
            spent=wr['before']-wr_ammo(pawn)
            assert spent>0,'Weapon did not fire'
            assert wr['part_travel']>.1,(name,moving_bone,wr['part_travel'])
            wr.update(spent=spent,fire_part_travel=wr['part_travel'],
                      part_rest=list(wr_position(wr_component(pawn),'Magazine').to_tuple()),part_travel=0)
            wr_input(pawn,'Aim',0);wr_input(pawn,'Reload',1)
            wr.update(phase='reloaded',next=now+4,release=True)
        elif phase=='reloaded':
            assert wr_ammo(pawn)==wr['before'],'Reload did not refill magazine'
            assert wr_ammo(pawn)+wr_ammo(pawn,'SpareAmmo')==wr['total']-wr['spent'],'Ammo was lost or duplicated'
            assert wr['part_travel']>1,(name,'Magazine',wr['part_travel'])
            wr['results'].append({'case':'fire_reload_moving_parts','weapon':name,'left':wr['side']==1,
                'rounds_fired':wr['spent'],'fire_part_travel_cm':wr['fire_part_travel'],'magazine_travel_cm':wr['part_travel']})
            wr['side']+=1
            if wr['side']<2:wr.update(phase='angle',angle=0,next=now+.3)
            else:
                if wr['index']+1==len(wr_specs):wr_finish()
                else:wr.update(index=wr['index']+1,phase='pickup',next=now+.5)
    except Exception:wr_finish(traceback.format_exc())
    finally:wr['busy']=False

wr['handle']=u.register_slate_post_tick_callback(wr_tick)
print('Started pistol and shotgun gameplay checks')
