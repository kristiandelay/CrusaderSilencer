"""Real owner prediction and observer multicast, with laser profiles on both weapons."""
from pathlib import Path
import unreal as u

ln_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
ln_source=(ln_root/'Scripts/Test-WeaponEffects-Network.py').read_text().replace('Artifacts/WeaponFX/network-validation.json','Artifacts/LaserTracer/network.json')
exec(compile(ln_source,'Test-WeaponEffects-Network.py','exec'),globals())
ln_tick_original=nfx_tick;ln_finish_original=nfx_finish
net_fx['phase']='laser_setup'

def vn_context():
    pawns=[p for w in u.EditorLevelLibrary.get_pie_worlds(False) for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if isinstance(p.get_controller(),u.PlayerController)]
    host=next(p for p in pawns if p.has_authority() and p.is_locally_controlled())
    server_client=next(p for p in pawns if p.has_authority() and not p.is_locally_controlled())
    client=next(p for p in pawns if not p.has_authority() and p.is_locally_controlled())
    client_world=next(w for w in u.EditorLevelLibrary.get_pie_worlds(False) if client in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter))
    observer=next(p for p in u.GameplayStatics.get_all_actors_of_class(client_world,u.CRTraversalCharacter) if not p.crowd_agent.enabled and not p.is_locally_controlled() and p.get_class()==host.get_class())
    return host,server_client,client,observer

def nfx_finish(error=None):
    if not error:
        for p in vn_context():
            assert p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).effects_profile.bullet_trail.get_name()=='NS_Laser_Trace_Red_2'
    ln_finish_original(error)

def ln_tick(dt):
    if net_fx['phase'].startswith('laser_'):
        try:
            assert time.monotonic()<net_fx['deadline'],'Network setup timed out'
            try:host,server_client,client,observer=vn_context()
            except StopIteration:return
            now=u.GameplayStatics.get_time_seconds(host)
            if net_fx['phase']=='laser_setup':
                server_world=next(w for w in u.EditorLevelLibrary.get_pie_worlds(False) if host in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter))
                for p,kind in [(host,'Pistol'),(server_client,'Rifle')]:
                    pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(server_world,u.BaselineWeaponPickup) if kind in a.item_definition.get_name())
                    p.set_actor_location(pickup.get_actor_location()+u.Vector(-100,0,40),False,True)
                    p.baseline_equipment.server_pickup(pickup)
                for p in [host,client]:
                    p.get_controller().set_ignore_move_input(True);p.get_controller().set_ignore_look_input(True)
                net_fx.update(phase='laser_equip',next=now+2)
            elif now>=net_fx['next'] and all(p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance) for p in [host,server_client,client,observer]):net_fx.update(phase='position',next=0)
        except Exception:ln_finish_original(traceback.format_exc())
    else:ln_tick_original(dt)

u.unregister_slate_post_tick_callback(net_fx['handle'])
net_fx['handle']=u.register_slate_post_tick_callback(ln_tick)
