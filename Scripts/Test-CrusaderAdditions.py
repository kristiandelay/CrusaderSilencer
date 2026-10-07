"""Final effects test plus guard/NPC and shot replication checks."""
import json
import time
import traceback
from pathlib import Path
import unreal as u

addition_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
addition_steps=[('Test-WeaponEffects.py','fx_test','WeaponFX/gameplay-validation.json','PIE_Standalone',1),
 ('Test-NPCVisuals-Network.py','visual_net','NPCCharacters/network-validation.json','PIE_ListenServer',2),
 ('Test-WeaponEffects-Network.py','net_fx','WeaponFX/network-validation.json',None,2)]
addition_test=dict(phase='start',index=0,next=0,busy=False,results=[],deadline=time.monotonic()+500)
def addition_finish(error=None):
    u.unregister_slate_post_tick_callback(addition_test['handle']);addition_test.update(finished=True,error=error)
    (addition_root/'Artifacts/WeaponFX/final-checks.json').write_text(json.dumps(dict(passed=not error,error=error,results=addition_test['results']),indent=2))
    print('CRUSADER_ADDITIONS_COMPLETE',error)
def addition_tick(dt):
    if addition_test['busy']:return
    addition_test['busy']=True
    try:
        now=time.monotonic()
        assert now<addition_test['deadline'],'Addition tests timed out'
        if now<addition_test['next']:return
        script,state,report,mode,players=addition_steps[addition_test['index']]
        phase=addition_test['phase']
        if phase=='start':
            if mode:
                assert not u.EditorLevelLibrary.get_pie_worlds(False)
                settings=u.load_object(None,'/Script/UnrealEd.Default__LevelEditorPlaySettings')
                for key,value in [('PlayNetMode',mode),('PlayNumberOfClients',str(players)),('RunUnderOneProcess','True')]:assert u.CRBlueprintTools.set_property_text(settings,key,value)
                u.SystemLibrary.execute_console_command(None,'t.IdleWhenNotForeground 0')
                u.SystemLibrary.execute_console_command(None,'DDCvar.VisualOverride 6')
                u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_begin_play()
            addition_test.update(phase='ready',next=now+2)
        elif phase=='ready':
            worlds=u.EditorLevelLibrary.get_pie_worlds(False)
            if len(worlds)<players:return
            pawn=u.GameplayStatics.get_player_pawn(worlds[0],0)
            if not pawn or not pawn.physical_interaction.controls_created:return
            addition_test['report_after']=time.time()
            exec((addition_root/'Scripts'/script).read_text(),globals())
            addition_test.update(phase='running')
        elif phase=='running':
            if not globals().get(state,{}).get('finished'):return
            path=addition_root/'Artifacts'/report
            assert path.stat().st_mtime>=addition_test['report_after'],'Stale result'
            result=json.loads(path.read_text());assert result['passed'],result['error']
            addition_test['results'].append(dict(script=script,report=report,cases=len(result['results']),passed=True))
            addition_test['index']+=1
            last=addition_test['index']==len(addition_steps)
            if last or addition_steps[addition_test['index']][3]:u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play()
            if last:
                u.SystemLibrary.execute_console_command(None,'DDCvar.VisualOverride 6');addition_finish()
            else:addition_test.update(phase='start',next=now+1)
    except Exception:addition_finish(traceback.format_exc())
    finally:addition_test['busy']=False
addition_test['handle']=u.register_slate_post_tick_callback(addition_tick)
print('Queued final Crusader additions checks')
