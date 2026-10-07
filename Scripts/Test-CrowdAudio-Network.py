"""Run after the two-player weapon test: NPC state/loadouts and local foot audio."""
import json,time,traceback
from pathlib import Path
import unreal as u
cn_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
cn_expected=sum(len(json.loads((cn_root/f'resources/{name}.json').read_text())['spawns']) for name in ['CrowdDistrict','FacilityCrowd'] if (cn_root/f'resources/{name}.json').exists())
cn_test=dict(phase='spawn',next=0,busy=False,results=[],deadline=time.monotonic()+120)
def cn_finish(error=None):
    u.unregister_slate_post_tick_callback(cn_test['handle']);cn_test.update(finished=True,error=error)
    (cn_root/'Artifacts/Environment/network.json').write_text(json.dumps(dict(passed=not error,error=error,results=cn_test['results']),indent=2))
def cn_tick(dt):
    if cn_test['busy']:return
    cn_test['busy']=True
    try:
        assert time.monotonic()<cn_test['deadline'],'Crowd/audio replication timed out'
        host,server_client,client,observer=vn_context();now=u.GameplayStatics.get_time_seconds(host)
        if cn_test['phase']=='walk':
            host.add_movement_input(u.Vector(0,-1,0),1,True)
            for p in [host,observer]:
                if p.footsteps.steps_played>cn_test['seen_counts'][p.get_path_name()]:
                    cn_test['surfaces'][p.get_path_name()].append(p.footsteps.last_surface)
                    cn_test['seen_counts'][p.get_path_name()]=p.footsteps.steps_played
        if now<cn_test['next']:return
        if cn_test['phase']=='spawn':
            ws=u.EditorLevelLibrary.get_pie_worlds(False);groups=[]
            for w in ws:
                npcs=[p for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if p.crowd_agent.enabled]
                assert len(npcs)==cn_expected and all(p.crowd_agent.initialized for p in npcs)
                rows={}
                for p in npcs:
                    data=p.crowd_agent;visual=p.selected_visual_override.child_actor.get_class().get_name()
                    weapon=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
                    assert bool(weapon)==data.guard,(p.get_name(),weapon)
                    assert ('UrbanTrailblazer' in visual)==(not data.guard)
                    assert data.current_area is not None
                    rows[p.get_name()]=dict(visual=visual,guard=data.guard,weapon=weapon.get_class().get_name() if weapon else None)
                groups.append(rows)
            assert groups[0]==groups[1],groups
            cn_test['results'].append(dict(case='replicated_npc_roles_visuals_loadouts',npcs=groups[0]))
            host.character_movement.stop_movement_immediately();host.set_actor_location(u.Vector(7100,-4480,100),False,True)
            host.set_actor_rotation(u.Rotator(yaw=-90),False);host.get_controller().set_control_rotation(u.Rotator(yaw=-90));host.force_net_update()
            cn_test.update(phase='settle',next=now+1.2)
        elif cn_test['phase']=='settle':
            walking='WantsToWalk_3_78963B154975E3BDE244A3BE438473E3=True' in host.get_editor_property('CharacterInputState').export_text()
            if not walking:
                sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==host.get_controller())
                sub.inject_input_vector_for_action(u.load_asset('/Game/Input/IA_Walk'),u.Vector(1,0,0),[],[])
            cn_test.update(phase='walk',next=now+3.5,before=[p.footsteps.steps_played for p in [host,observer]],seen_counts={p.get_path_name():p.footsteps.steps_played for p in [host,observer]},surfaces={p.get_path_name():[] for p in [host,observer]})
        else:
            host.character_movement.stop_movement_immediately()
            counts=[p.footsteps.steps_played-n for p,n in zip([host,observer],cn_test['before'])]
            assert min(counts)>=3 and abs(counts[0]-counts[1])<=2,counts
            assert max(counts)<=9,('Duplicate footstep contacts',counts)
            assert all(v and all(s==4 for s in v) for v in cn_test['surfaces'].values()),cn_test['surfaces']
            cn_test['results'].append(dict(case='owner_and_observer_foot_contacts',counts=counts,surface='Metal',no_audio_multicast=True));cn_finish()
    except Exception:cn_finish(traceback.format_exc())
    finally:cn_test['busy']=False
cn_test['handle']=u.register_slate_post_tick_callback(cn_tick)
