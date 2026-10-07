"""Measure actual NPC gait selection and posture in standalone or two-player PIE."""
import json, math, time, traceback
from pathlib import Path
import unreal as u

cl_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
cl_out=cl_root/'Artifacts/Locomotion'
cl_out.mkdir(exist_ok=True)
cl_test=dict(phase='setup',index=0,next=0,busy=False,results=[],deadline=time.monotonic()+180)
cl_cases=[('patrol',None,'WALK'),('jog',450.,'RUN'),('escape',700.,'SPRINT'),('turn',None,'WALK'),('stop',None,'WALK')]
def cl_set(obj,name,value):
    # PostEditChange on a PIE component reconstructs the pawn's SCS components,
    # silently dropping GASP's BeginPlay tick bindings. Set runtime values only.
    assert u.CRBlueprintTools.set_property_text(obj,name,str(value))
def cl_finish(error=None):
    u.unregister_slate_post_tick_callback(cl_test['handle']);cl_test.update(finished=True,error=error)
    (cl_out/('network.json' if cl_test.get('network') else 'standalone.json')).write_text(json.dumps(dict(passed=not error,error=error,results=cl_test['results']),indent=2))
    print('CROWD_LOCOMOTION_COMPLETE',error)
def cl_lean(mesh):
    d=mesh.get_socket_location('head')-mesh.get_socket_location('pelvis')
    return math.degrees(math.atan2(math.hypot(d.x,d.y),d.z))
def cl_tick(dt):
    if cl_test['busy']:return
    cl_test['busy']=True
    try:
        assert time.monotonic()<cl_test['deadline'],'Locomotion test timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        groups=[[p for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if p.crowd_agent.enabled] for w in worlds]
        if not all(len(ps)==12 and all(p.crowd_agent.initialized for p in ps) for ps in groups):return
        server=next(ps for ps in groups if ps[0].get_controller())
        w=server[0].get_world();now=u.GameplayStatics.get_time_seconds(w)
        case,speed,gait=cl_cases[cl_test['index']]
        if cl_test['phase']=='setup':
            cl_test['network']=len(worlds)>1
            for actor in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter):
                if not actor.crowd_agent.enabled and actor.get_controller():actor.set_actor_location(u.Vector(1100,-5700,94),False,True)
            for p in server:
                p.get_controller().stop_movement();cl_set(p.crowd_agent,'CurrentArea','None');cl_set(p.crowd_agent,'Threat','None')
            names=[next(p.get_name() for p in server if p.get_class().get_name()=='B_'+role+'_C') for role in ['GuardRifle','GuardPistol','GuardShotgun','Civilian']]
            cl_test.update(names=names,phase='place')
        selected=[next(p for p in server if p.get_name()==n) for n in cl_test['names']]
        if cl_test['phase']=='sample' and now>=cl_test['next']:
            for gi,ps in enumerate(groups):
                for name in cl_test['names']:
                    p=next(p for p in ps if p.get_name()==name);a=p.mesh.get_anim_instance();visual=p.baseline_equipment.get_presentation_mesh()
                    if not visual:return
                    key=str(gi)+'/'+name
                    row=cl_test['samples'].setdefault(key,dict(speed=[],source_lean=[],visual_lean=[],gaits=[],databases=[],desired_speed=[]))
                    row['speed'].append(p.get_velocity().length());row['source_lean'].append(cl_lean(p.mesh));row['visual_lean'].append(cl_lean(visual))
                    row['gaits'].append(str(a.get_editor_property('Gait')));db=a.get_editor_property('CurrentSelectedDatabase')
                    row['databases'].append(db.get_name() if db else 'None');row['desired_speed'].append(p.crowd_agent.desired_speed)
            if now<cl_test['end']:return
            for key,rows in cl_test['samples'].items():
                name=key.split('/')[1];p=next(p for p in selected if p.get_name()==name)
                intended=speed or p.crowd_agent.patrol_speed
                mean=lambda field:sum(rows[field])/len(rows[field])
                assert all(gait in g for g in rows['gaits']),(case,key,'gait',set(rows['gaits']))
                assert all(abs(v-intended)<1 for v in rows['desired_speed']),(case,key,'replicated speed',rows['desired_speed'])
                if case in ['patrol','jog','escape']:
                    assert .80*intended<mean('speed')<=1.07*intended,(case,key,'speed',mean('speed'),intended)
                if gait=='WALK':
                    assert mean('source_lean')<22 and mean('visual_lean')<24,(case,key,'hunched',mean('source_lean'),mean('visual_lean'))
                    if case!='stop':assert sum('Walk' in db for db in rows['databases'])/len(rows['databases'])>.8,(case,key,set(rows['databases']))
                if case=='stop':assert max(rows['speed'])<5,(case,key,'failed stop')
                cl_test['results'].append(dict(case=case,pawn=name,world=key.split('/')[0],samples=len(rows['speed']),speed=mean('speed'),source_lean=mean('source_lean'),visual_lean=mean('visual_lean'),gaits=sorted(set(rows['gaits'])),databases=sorted(set(rows['databases']))))
            if case=='patrol' and not cl_test['network']:
                exec((cl_root/'Scripts/Capture-WeaponEffects.py').read_text().split('def cfx_tick')[0],globals())
                globals()['capture_folder']=cl_out
                for p in selected:cfx_image(w,p.get_class().get_name(),p.get_actor_location()+u.Vector(210,370,55),p.get_actor_location(),38)
            cl_test['index']+=1
            if cl_test['index']==len(cl_cases):cl_finish();return
            cl_test.update(phase='place');return
        if cl_test['phase']=='place':
            cl_test['samples']={}
            for i,p in enumerate(selected):
                ctrl=p.get_controller();ctrl.stop_movement();p.character_movement.stop_movement_immediately();p.un_crouch()
                p.set_actor_location(u.Vector(10500,-1800+i*370,94),False,True);p.set_actor_rotation(u.Rotator(yaw=0),False);ctrl.set_control_rotation(u.Rotator(yaw=0))
                cl_set(p.crowd_agent,'DesiredSpeed',speed or p.crowd_agent.patrol_speed)
                p.force_net_update()
            cl_test.update(phase='move',next=now+.6)
        elif cl_test['phase']=='move' and now>=cl_test['next']:
            if case!='stop':
                for i,p in enumerate(selected):
                    # The last walking case starts facing east and turns north.
                    goal=p.get_actor_location()+(u.Vector(0,1600,0) if case=='turn' else u.Vector(5000,0,0))
                    assert p.get_controller().move_to_location(goal,30)==u.PathFollowingRequestResult.REQUEST_SUCCESSFUL
            cl_test.update(phase='sample',next=now+2,end=now+3.5)
    except Exception:cl_finish(traceback.format_exc())
    finally:cl_test['busy']=False
cl_test['handle']=u.register_slate_post_tick_callback(cl_tick)
