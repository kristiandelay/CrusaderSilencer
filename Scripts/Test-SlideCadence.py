"""Exercise mapped slide spam, recovery and fresh presses on the local player.

Runs unchanged in standalone or two-player PIE (the client owns the test there).
"""
import json,time,traceback
from pathlib import Path
import unreal as u

sc_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
sc_out=sc_root/'Artifacts/SlideCadence';sc_out.mkdir(parents=True,exist_ok=True)
sc_test=dict(phase='place',next=0,busy=False,results=[],deadline=time.monotonic()+100,entries=0,was_sliding=False)

def sc_context():
    worlds=u.EditorLevelLibrary.get_pie_worlds(False)
    pawns=[p for w in worlds for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if isinstance(p.get_controller(),u.PlayerController) and p.is_locally_controlled()]
    # The host becomes ready before the client. Wait for client possession so
    # the fixture cannot switch owners halfway through the run-up.
    pawn=next(p for p in pawns if not p.has_authority()) if len(worlds)>1 else pawns[0]
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pawn.get_controller())
    return pawn,sub

def sc_input(sub,name,value):
    sub.inject_input_vector_for_action(u.load_asset('/Game/Input/IA_'+name),u.Vector(*value) if isinstance(value,tuple) else u.Vector(value,0,0),[],[])

def sc_finish(error=None):
    u.unregister_slate_post_tick_callback(sc_test['handle'])
    sc_test.update(finished=True,error=error)
    try:
        pawn,sub=sc_context()
        if error:
            authority=sc_test.get('authority')
            sc_test['failure_state']=dict(position=str(pawn.get_actor_location()),velocity=str(pawn.get_velocity()),movement_mode=str(pawn.character_movement.movement_mode),crouched=pawn.is_crouched,can_use_actions=pawn.can_use_movement_actions(),input_state=pawn.get_editor_property('CharacterInputState').export_text(),authority_position=str(authority.get_actor_location()) if authority else None,authority_crouched=authority.is_crouched if authority else None)
        for name in ['Move','Sprint','Crouch','Jump']:sc_input(sub,name,0)
        pawn.character_movement.set_slide_requested(False);pawn.un_crouch()
    except Exception:pass
    report=dict(passed=error is None,error=error,results=sc_test['results'],slide_entries=sc_test['entries'])
    if error:report['failure_state']=sc_test.get('failure_state')
    (sc_out/('network.json' if sc_test.get('network') else 'standalone.json')).write_text(json.dumps(report,indent=2)+'\n')
    print('SLIDE_CADENCE_COMPLETE',json.dumps(report))

def sc_tick(dt):
    if sc_test['busy']:return
    sc_test['busy']=True
    sub=None;crouch_input=0
    try:
        assert time.monotonic()<sc_test['deadline'],'Slide cadence check timed out'
        try:pawn,sub=sc_context()
        except (IndexError,StopIteration):return
        move=pawn.character_movement
        if not pawn.physical_interaction.controls_created:return
        now=u.GameplayStatics.get_time_seconds(pawn)
        sliding=move.is_sliding()
        if sliding and not sc_test['was_sliding']:sc_test['entries']+=1
        sc_test['was_sliding']=sliding
        phase=sc_test['phase']
        if phase not in ['place','settle','crouched','standing','interrupt_check']:
            sc_input(sub,'Move',(0,1,0));sc_input(sub,'Sprint',1)
        if now<sc_test['next']:return
        if phase=='place':
            sc_test['network']=not pawn.has_authority()
            authority=pawn if pawn.has_authority() else next(p for w in u.EditorLevelLibrary.get_pie_worlds(False) for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if p.has_authority() and isinstance(p.get_controller(),u.PlayerController) and not p.is_locally_controlled())
            sc_test['authority']=authority
            authority.character_movement.stop_movement_immediately()
            authority.set_actor_location(u.Vector(-1400,-3200,94),False,True)
            pawn.get_controller().set_control_rotation(u.Rotator(yaw=0))
            sc_test.update(phase='settle',next=now+2)
        elif phase=='settle':
            assert abs(move.slide_minimum_duration-.35)<.01 and abs(move.slide_recovery_duration-.65)<.01
            crouch_input=1;sc_test.update(phase='crouched',next=now+.4)
        elif phase=='crouched':
            assert pawn.is_crouched and not sliding,'Normal stationary crouch failed'
            crouch_input=1;sc_test.update(phase='standing',next=now+.4)
        elif phase=='standing':
            assert not pawn.is_crouched,'Standing toggle did not release crouch: '+str(pawn.get_actor_location())
            sc_test['results'].append(dict(case='stationary_crouch_toggle',passed=True))
            sc_test.update(phase='run',started=now)
        elif phase=='run':
            assert now-sc_test['started']<6,'Failed to reach slide speed'
            if pawn.get_velocity().length()>660:
                crouch_input=1;sc_test.update(phase='enter',started=now)
        elif phase=='enter':
            assert now-sc_test['started']<.5,'Slide did not start'
            if sliding:sc_test.update(phase='commit_spam',started=now,spam_at=now+.04,pressed=False,initial_speed=pawn.get_velocity().length())
        elif phase=='commit_spam':
            elapsed=now-sc_test['started']
            assert sliding,'Rapid tap cancelled the slide entry'
            assert sc_test['entries']==1,'Rapid taps reapplied the entry boost'
            if elapsed<.27 and now>=sc_test['spam_at']:
                crouch_input=1;sc_test['spam_at']=now+.07
            if elapsed>=.4:
                assert move.can_cancel_slide()
                assert sc_test['authority'].character_movement.is_sliding(),'Server rejected the predicted slide'
                sc_test['results'].append(dict(case='entry_spam_ignored',slide_entries=sc_test['entries'],initial_speed=sc_test['initial_speed'],speed_after=pawn.get_velocity().length()))
                crouch_input=1;sc_test.update(phase='cancel',started=now)
        elif phase=='cancel':
            assert now-sc_test['started']<.5,'Slide cancel failed after commitment'
            if not sliding:
                assert move.get_slide_recovery_remaining()>.45
                sc_test.update(phase='recovery_spam',started=now,spam_at=now+.03)
        elif phase=='recovery_spam':
            assert not sliding and sc_test['entries']==1,'Slide restarted during recovery'
            assert not pawn.is_crouched,'Rejected slide press flickered into crouch'
            if move.get_slide_recovery_remaining()>.12:
                if now-sc_test['started']>.2:assert not sc_test['authority'].character_movement.is_sliding(),'Server did not end slide'
                if now>=sc_test['spam_at']:crouch_input=1;sc_test['spam_at']=now+.07
            elif move.get_slide_recovery_remaining()<=0:
                sc_test['results'].append(dict(case='recovery_spam_ignored',elapsed_seconds=now-sc_test['started']))
                sc_test.update(phase='no_buffer',next=now+.3)
        elif phase=='no_buffer':
            assert not sliding and sc_test['entries']==1,'Rejected input buffered an automatic slide'
            assert move.can_start_slide()
            sc_test['results'].append(dict(case='no_buffered_restart',passed=True))
            crouch_input=1;sc_test.update(phase='restart',started=now)
        elif phase=='restart':
            assert now-sc_test['started']<.5,'Fresh slide press did not work after recovery'
            if sliding:
                assert sc_test['entries']==2
                sc_test['results'].append(dict(case='fresh_press_after_recovery',passed=True))
                # Physical interruption must bypass the input commitment. Run
                # this only in standalone; replication is tested above via input.
                if sc_test['network']:sc_finish();return
                pawn.un_crouch();pawn.jump()
                sc_test.update(phase='interrupt_check',next=now+.12)
        elif phase=='interrupt_check':
            assert not sliding,'Physical exit was blocked by slide commitment'
            assert move.get_slide_recovery_remaining()>0
            sc_test['results'].append(dict(case='physical_interrupt_during_entry',falling=move.is_falling(),passed=True))
            sc_finish()
    except Exception:sc_finish(traceback.format_exc())
    finally:
        if sub:sc_input(sub,'Crouch',crouch_input)
        sc_test['busy']=False

sc_test['handle']=u.register_slate_post_tick_callback(sc_tick)
print('SLIDE_CADENCE_STARTED')
