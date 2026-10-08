"""Measure the source and visible legs throughout release, not just pawn travel."""
import json,time,traceback
from pathlib import Path
import unreal as u

trl_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
trl_test=dict(next=0,busy=False,results=[],deadline=time.monotonic()+220,report='release-legs.json')

def trl_key(p,key,down):
    k=u.Key();assert k.import_text(key);u.CRBlueprintTools.inject_pie_key(p,k,down)

def trl_context():
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    pawns=[p for w in worlds for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if isinstance(p.get_controller(),u.PlayerController) and not p.crowd_agent.enabled]
    p=next(p for p in pawns if p.is_locally_controlled() and (not p.has_authority() if len(worlds)>1 else True))
    server=next(p for p in pawns if p.has_authority() and not p.is_locally_controlled()) if len(worlds)>1 else p
    return p,server

def trl_feet(p):
    return [mesh.get_socket_location('foot_'+side)-mesh.get_socket_location('pelvis')
            for mesh in [p.mesh,p.baseline_equipment.get_presentation_mesh()] for side in ['l','r']]

def trl_run():
    while True:
        try:p,server=trl_context();break
        except StopIteration:yield .2
    while not p.physical_interaction.controls_created or not server.physical_interaction.controls_created:yield .2
    if p!=server:trl_test['report']='release-legs-network.json'
    for name in ['throw_montage','left_throw_montage']:
        montage=p.throwable.get_editor_property(name)
        assert [str(track.get_editor_property('slot_name')) for track in montage.get_editor_property('slot_anim_tracks')]==['ThrowUpperBody'],('Release still assigned to full-body slot',name)
    cases=[dict(slide=False,kind=kind,left=left,keys=keys) for kind in [u.CRThrowableType.GRENADE,u.CRThrowableType.SMOKE] for left in [False,True] for keys in [['W'],['W','D']]]
    cases += [dict(slide=True,kind=kind,left=left,keys=['W']) for kind,left in [(u.CRThrowableType.GRENADE,False),(u.CRThrowableType.SMOKE,True)]]
    for case in cases:
        for key in ['W','A','S','D','LeftShift','C','H','Q','X']:trl_key(p,key,False)
        for a in u.GameplayStatics.get_all_actors_of_class(server.get_world(),u.CRThrownObject):a.destroy_actor()
        p.character_movement.set_slide_requested(False);p.un_crouch()
        server.character_movement.set_slide_requested(False);server.un_crouch();yield .3
        server.character_movement.stop_movement_immediately();server.set_actor_location(u.Vector(5000,2500,94),False,True)
        server.set_actor_rotation(u.Rotator(yaw=0),False);server.force_net_update();p.get_controller().set_control_rotation(u.Rotator(yaw=0));yield .7
        if p.baseline_equipment.is_left_shoulder()!=case['left']:
            trl_key(p,'Q',True);yield .08;trl_key(p,'Q',False);yield .4
        if p.throwable.selected_type!=case['kind']:
            trl_key(p,'X',True);yield .08;trl_key(p,'X',False);yield .15
        for key in case['keys']:trl_key(p,key,True)
        if case['slide']:
            trl_key(p,'LeftShift',True)
            deadline=u.GameplayStatics.get_time_seconds(p)+5
            while p.get_velocity().length()<680:
                assert u.GameplayStatics.get_time_seconds(p)<deadline
                yield .05
            trl_key(p,'C',True);yield .08;trl_key(p,'C',False);trl_key(p,'W',False);trl_key(p,'LeftShift',False)
            yield .2
            assert p.character_movement.is_sliding() and server.character_movement.is_sliding()
        trl_key(p,'H',True);yield .4
        assert p.throwable.phase==server.throwable.phase==u.CRThrowPhase.AIMING
        before=server.throwable.throws_released;count=server.throwable.get_remaining();start=p.get_actor_location()
        samples=[];server_samples=[];heights=[];slots=[]
        release_started=u.GameplayStatics.get_time_seconds(p)
        trl_key(p,'H',False)
        while u.GameplayStatics.get_time_seconds(p)-release_started<.55:
            yield .001
            assert p.throwable.phase==u.CRThrowPhase.THROWING
            anim=p.mesh.get_anim_instance();default=anim.is_slot_active('DefaultSlot')
            assert default==case['slide'],('Release overrode the full-body pose',case,default)
            assert server.mesh.get_anim_instance().is_slot_active('DefaultSlot')==case['slide']
            assert p.get_velocity().length()>80,'Throw stopped movement'
            samples.append(trl_feet(p));server_samples.append(trl_feet(server));slots.append(default)
            if case['slide']:
                assert p.character_movement.is_sliding() and server.character_movement.is_sliding()
                for mesh in [p.mesh,p.baseline_equipment.get_presentation_mesh()]:
                    floor=p.get_actor_location().z-p.capsule_component.get_scaled_capsule_half_height()
                    height=mesh.get_socket_location('pelvis').z-floor;heights.append(height)
                    assert 5<height<45,('Release replaced slide legs with standing legs',height)
        assert len(samples)>=4,'Insufficient release pose samples'
        assert (p.get_actor_location()-start).length()>100
        ranges=[max((a[i]-b[i]).length() for a in samples for b in samples) for i in range(4)]
        server_ranges=[max((a[i]-b[i]).length() for a in server_samples for b in server_samples) for i in range(4)]
        if not case['slide']:
            assert min(ranges)>25,('Frozen release legs on owner',case,ranges)
            assert min(server_ranges)>25,('Frozen release legs on server',case,server_ranges)
        assert server.throwable.throws_released==before+1 and server.throwable.get_remaining()==count-1
        trl_test['results'].append(dict(slide=case['slide'],type=str(case['kind']),left=case['left'],keys=case['keys'],
            owner_leg_motion_cm=ranges,server_leg_motion_cm=server_ranges,slide_pelvis_height_cm=heights,full_body_slot_active=slots,one_release=True))
        for key in case['keys']:trl_key(p,key,False)
        yield .5

def trl_finish(error=None):
    u.unregister_slate_post_tick_callback(trl_test['handle']);trl_test.update(finished=True,error=error)
    try:
        p,_=trl_context()
        for key in ['W','A','S','D','H','C','LeftShift','Q','X']:trl_key(p,key,False)
    except Exception:pass
    (trl_root/'Artifacts/Throw'/trl_test['report']).write_text(json.dumps(dict(passed=error is None,error=error,results=trl_test['results']),indent=2)+'\n')
    print('THROW_RELEASE_LEGS',error)

trl_generator=trl_run()
def trl_tick(dt):
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    if not worlds or trl_test['busy']:return
    now=u.GameplayStatics.get_time_seconds(worlds[0])
    if now<trl_test['next']:return
    trl_test['busy']=True
    try:
        assert time.monotonic()<trl_test['deadline']
        trl_test['next']=now+next(trl_generator)
    except StopIteration:trl_finish()
    except Exception:trl_finish(traceback.format_exc())
    finally:trl_test['busy']=False
trl_test['handle']=u.register_slate_post_tick_callback(trl_tick)
print('THROW_RELEASE_LEG_CHECKS_STARTED')
