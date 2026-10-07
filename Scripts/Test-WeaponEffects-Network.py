"""One predicted cosmetic burst per shot on owner, server and observing clients.

Run after Test-NPCVisuals-Network in the same two-player PIE session.
"""
import json
import time
import traceback
from pathlib import Path
import unreal as u

net_fx=dict(phase='position',next=0,busy=False,results=[],deadline=time.monotonic()+90)
def nfx_input(pawn,name,value):
    paths={'Aim':'/Game/Input/IA_Aim','Fire':'/Game/Input/Actions/IA_Weapon_Fire','FireAuto':'/Game/Input/Actions/IA_Weapon_Fire_Auto'}
    subsystem=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pawn.get_controller())
    subsystem.inject_input_vector_for_action(u.load_asset(paths[name]),u.Vector(value,0,0),[],[])
def nfx_finish(error=None):
    u.unregister_slate_post_tick_callback(net_fx['handle']);net_fx.update(finished=True,error=error)
    output=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/WeaponFX/network-validation.json'
    output.write_text(json.dumps(dict(passed=not error,error=error,results=net_fx['results']),indent=2))
    print('NETWORK_EFFECTS_COMPLETE',error)
def nfx_tick(dt):
    if net_fx['busy']:return
    net_fx['busy']=True
    try:
        assert time.monotonic()<net_fx['deadline'],'Network effects timed out'
        host,server_client,client,observer=vn_context();pawns=[host,server_client,client,observer]
        now=u.GameplayStatics.get_time_seconds(host)
        if net_fx.pop('release',False):
            for pawn in [host,client]:
                for action in ['Fire','FireAuto']:nfx_input(pawn,action,0)
        for pawn,target in [(host,(-290,-6920,170)),(client,(370,-6920,170))]:
            camera=u.GameplayStatics.get_player_camera_manager(pawn,0).get_camera_location()
            pawn.get_controller().set_control_rotation(u.MathLibrary.find_look_at_rotation(camera,u.Vector(*target)))
            nfx_input(pawn,'Aim',1)
        if now<net_fx['next']:return
        phase=net_fx['phase']
        if phase=='position':
            for pawn,x in [(host,-290),(server_client,370)]:
                pawn.character_movement.stop_movement_immediately();pawn.set_actor_location(u.Vector(x,-5710,94),False,True);pawn.force_net_update()
            net_fx.update(phase='fire_host',next=now+2)
        elif phase in ['fire_host','fire_client']:
            net_fx['before']=[p.weapon_effects.shots_played for p in pawns]
            net_fx['before_holes']=[p.weapon_effects.decals_spawned for p in pawns]
            shooter=host if phase=='fire_host' else client
            for action in ['Fire','FireAuto']:nfx_input(shooter,action,1)
            net_fx.update(phase='check_host' if phase=='fire_host' else 'check_client',next=now+.7,release=True)
        elif phase in ['check_host','check_client']:
            expected=[1,0,0,1] if phase=='check_host' else [0,1,1,0]
            deltas=[p.weapon_effects.shots_played-before for p,before in zip(pawns,net_fx['before'])]
            assert deltas==expected,(phase,deltas,expected)
            holes=[p.weapon_effects.decals_spawned-before for p,before in zip(pawns,net_fx['before_holes'])]
            assert holes==expected,('Bullet holes duplicated or missing',phase,holes,expected)
            surface=2 if phase=='check_host' else 4
            for role,count in enumerate(expected):
                if count:
                    hits=pawns[role].weapon_effects.last_impacts
                    assert hits and all(h.blocking_hit and h.surface==surface for h in hits),(role,[(h.blocking_hit,h.surface) for h in hits])
            net_fx['results'].append(dict(shooter='host' if phase=='check_host' else 'client',shot_bursts_by_role=deltas,bullet_holes_by_role=holes,surface=surface,passed=True))
            if phase=='check_host':net_fx.update(phase='fire_client',next=now+.4)
            else:
                for pawn in [host,client]:nfx_input(pawn,'Aim',0)
                nfx_finish()
    except Exception:nfx_finish(traceback.format_exc())
    finally:net_fx['busy']=False
net_fx['handle']=u.register_slate_post_tick_callback(nfx_tick)
