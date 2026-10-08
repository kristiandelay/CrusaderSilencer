"""Exercise actual W/A/S/D+Alt mappings, including same-frame presses and turns."""
import json,math,time,traceback
from pathlib import Path
import unreal as u

rdx_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
rdx_pairs=[('W','D',1),('S','D',3),('S','A',5),('W','A',7)]
rdx_cases=[dict(mode=mode,keys=[a,b],direction=d,yaw=yaw,aim=mode!='unarmed_stance')
           for mode,yaw in [('held',0),('simultaneous',37),('reverse',-63),('unarmed_stance',112),('analog',19)] for a,b,d in rdx_pairs]
rdx_cases += [dict(mode='cardinal',keys=keys,direction=d,yaw=0,aim=True) for keys,d in [(['W'],0),(['D'],2),(['S'],4),(['A'],6),([],0)]]
rdx_test=dict(phase='setup',index=0,next=0,busy=False,results=[],deadline=time.monotonic()+240)

def rdx_key(name):
    key=u.Key();assert key.import_text(name);return key

def rdx_press(p,key,down):
    # InputKey may return unhandled before processing Enhanced Input next tick.
    u.CRBlueprintTools.inject_pie_key(p,rdx_key(key),down)

def rdx_release(p):
    for key in ['W','A','S','D','LeftAlt','Gamepad_DPad_Right','RightMouseButton']:rdx_press(p,key,False)

def rdx_context():
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    pawns=[p for w in worlds for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if not p.crowd_agent.enabled and isinstance(p.get_controller(),u.PlayerController)]
    owner=next(p for p in pawns if p.is_locally_controlled() and (not p.has_authority() if len(worlds)>1 else True))
    authority=next(p for p in pawns if p.has_authority() and not p.is_locally_controlled()) if len(worlds)>1 else owner
    return owner,authority

def rdx_analog(p,case,value=.25):
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==p.get_controller())
    angle=math.radians(case['direction']*45)
    sub.inject_input_vector_for_action(u.load_asset('/Game/Input/IA_Move'),u.Vector(value*math.sin(angle),value*math.cos(angle),0),[],[])

def rdx_finish(error=None):
    u.unregister_slate_post_tick_callback(rdx_test['handle']);rdx_test.update(finished=True,error=error)
    try:p,_=rdx_context();rdx_release(p);rdx_analog(p,rdx_cases[rdx_test.get('index',0)%len(rdx_cases)],0)
    except Exception:pass
    (rdx_root/'Artifacts/Roll/Diagonal'/rdx_test.get('report','standalone.json')).write_text(json.dumps(dict(passed=error is None,error=error,results=rdx_test['results']),indent=2)+'\n')
    print('ROLL_DIRECTIONS',error)

def rdx_tick(dt):
    if rdx_test['busy']:return
    rdx_test['busy']=True
    try:
        assert time.monotonic()<rdx_test['deadline'],'Mapped diagonal roll checks timed out'
        try:p,server=rdx_context()
        except StopIteration:return
        if not p.physical_interaction.controls_created or not server.physical_interaction.controls_created:return
        now=u.GameplayStatics.get_time_seconds(p);phase=rdx_test['phase'];case=rdx_cases[rdx_test['index']]
        if phase=='prepare' and case['mode']=='analog':rdx_analog(p,case)
        if phase=='observe':
            if p.roll.is_rolling() and not rdx_test['seen']:
                rdx_test['seen']=True;rdx_test['selected']=p.roll.active_direction
                # Release the controls once the roll commits, without forcing facing.
                for key in ['W','A','S','D','LeftAlt','Gamepad_DPad_Right']:rdx_press(p,key,False)
                rdx_analog(p,case,0)
            if server.roll.is_rolling():rdx_test['server_selected']=server.roll.active_direction
        if now<rdx_test['next']:return
        if phase=='setup':
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(server.get_world(),u.BaselineWeaponPickup) if 'Rifle' in a.item_definition.get_name())
            pos=pickup.get_actor_location();server.set_actor_location(pos+u.Vector(-110,0,94-pos.z),False,True);server.baseline_equipment.server_pickup(pickup);server.force_net_update()
            rdx_test.update(phase='place',next=now+1.5)
        elif phase=='place':
            rdx_release(p);assert p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance),'Rifle not replicated'
            server.character_movement.stop_movement_immediately();server.un_crouch()
            server.set_actor_location(u.Vector(5000,2500,94),False,True);server.set_actor_rotation(u.Rotator(yaw=case['yaw']),False);server.force_net_update()
            p.get_controller().set_control_rotation(u.Rotator(yaw=case['yaw']))
            rdx_press(p,'RightMouseButton',case['aim'])
            rdx_test.update(phase='start_move',next=now+.65)
        elif phase=='start_move':
            if case['mode']=='reverse':rdx_press(p,'D',True)
            elif case['mode'] not in ['simultaneous','analog']:
                for key in case['keys']:rdx_press(p,key,True)
            rdx_test.update(phase='prepare',next=now+.35)
        elif phase=='prepare':
            if case['mode']=='reverse':rdx_press(p,'D',False)
            if case['mode'] in ['simultaneous','reverse']:
                for key in case['keys']:rdx_press(p,key,True)
            v=p.get_last_movement_input_vector()
            rdx_test.update(start=p.get_actor_location(),before=p.roll.rolls_started,server_before=server.roll.rolls_started,seen=False,selected=None,server_selected=None,input_before=[v.x,v.y],input_length_squared=v.x*v.x+v.y*v.y,facing_before=p.get_actor_rotation().yaw)
            rdx_press(p,'Gamepad_DPad_Right' if case['mode']=='analog' else 'LeftAlt',True)
            rdx_test.update(phase='observe',next=now+1.3)
        elif phase=='observe':
            assert rdx_test['seen'],('Roll did not activate through key mapping',case)
            assert p.roll.rolls_started-rdx_test['before']==1 and server.roll.rolls_started-rdx_test['server_before']==1
            selected=rdx_test['selected'];assert selected==rdx_test['server_selected'],('Direction replication',case,rdx_test)
            if case['aim']:assert selected==case['direction'],('Wrong directional montage',case,selected,rdx_test['input_before'],rdx_test['facing_before'])
            delta=p.get_actor_location()-rdx_test['start'];distance=math.hypot(delta.x,delta.y)
            angle=math.radians(case['yaw']+case['direction']*45)
            dot=(delta.x*math.cos(angle)+delta.y*math.sin(angle))/max(distance,1)
            assert 280<distance<560 and dot>.91,('Roll missed requested world direction',case,distance,dot)
            assert not p.roll.is_rolling() and p.can_use_movement_actions()
            rdx_test['results'].append(dict(**case,selected=selected,server_selected=rdx_test['server_selected'],distance_cm=distance,direction_agreement=dot,input_before=rdx_test['input_before'],input_length_squared=rdx_test['input_length_squared']))
            rdx_release(p);rdx_test['index']+=1
            if rdx_test['index']==len(rdx_cases):rdx_finish();return
            rdx_test.update(phase='place',next=now+.4)
    except Exception:rdx_finish(traceback.format_exc())
    finally:rdx_test['busy']=False
rdx_test['handle']=u.register_slate_post_tick_callback(rdx_tick)
print('MAPPED_ROLL_DIRECTION_CHECKS_STARTED')
