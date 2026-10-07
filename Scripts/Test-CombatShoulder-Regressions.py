"""Run independent fresh play sessions for combat, handed weapons and prior movement."""
import json
import time
import traceback
from pathlib import Path
import unreal as u

combat_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
combat_steps=[
    ('Test-CombatDeath.py','death_test','CombatTests/combat-death.json','PIE_Standalone',1),
    ('Test-CombatShoulder-Network.py','combat_net','CombatTests/combat-shoulder-network.json','PIE_ListenServer',2),
    ('Test-ShoulderSwap.py','shoulder_test','CombatTests/shoulder-swap.json','PIE_Standalone',1),
    ('Test-GetUpRegressions.py','recovery_pipeline','PhysicalTests/getup-regressions.json','PIE_Standalone',1),
    ('Test-Baseline-Aim.py','aim_test','AimTests/aim-and-slide.json','PIE_Standalone',1),
    ('Test-PhysicalInteractions-Network.py','net_physical','PhysicalTests/network-physical.json','PIE_ListenServer',2),
]
combat_pipeline={'index':0,'phase':'start','busy':False,'results':[],'next':0,'deadline':time.monotonic()+700}


def combat_pipeline_finish(error=None):
    u.unregister_slate_post_tick_callback(combat_pipeline['handle'])
    combat_pipeline.update(finished=True,error=error)
    output=combat_root/'Artifacts/CombatTests/combat-regressions.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({'passed':error is None,'error':error,'results':combat_pipeline['results']},indent=2))
    print('COMBAT_REGRESSIONS_COMPLETE',error)


def combat_pipeline_tick(dt):
    if combat_pipeline['busy']:return
    combat_pipeline['busy']=True
    try:
        now=time.monotonic()
        assert now<combat_pipeline['deadline'],'Combat regression pipeline timed out'
        if now<combat_pipeline['next']:return
        script,state,report,mode,clients=combat_steps[combat_pipeline['index']]
        phase=combat_pipeline['phase']
        if phase=='start':
            assert not u.EditorLevelLibrary.get_pie_worlds(False),'Start with PIE stopped'
            settings=u.load_object(None,'/Script/UnrealEd.Default__LevelEditorPlaySettings')
            for key,value in [('PlayNetMode',mode),('PlayNumberOfClients',str(clients)),('RunUnderOneProcess','True')]:
                assert u.CRBlueprintTools.set_property_text(settings,key,value)
            u.SystemLibrary.execute_console_command(None,'t.IdleWhenNotForeground 0')
            u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_begin_play()
            combat_pipeline.update(phase='ready',next=now+2)
        elif phase=='ready':
            worlds=u.EditorLevelLibrary.get_pie_worlds(False)
            if not worlds:return
            pawn=u.GameplayStatics.get_player_pawn(worlds[0],0)
            if not pawn or not pawn.physical_interaction.controls_created:return
            if state=='aim_test':
                combat_input(pawn,'Shoulder',1)
            combat_pipeline.update(phase='launch',next=now+.6)
        elif phase=='launch':
            if state=='aim_test':
                pawn=u.GameplayStatics.get_player_pawn(u.EditorLevelLibrary.get_pie_worlds(False)[0],0)
                assert pawn.baseline_equipment.is_left_shoulder(), 'Slide regressions must exercise the left weapon hand'
            combat_pipeline['report_after']=time.time()
            exec((combat_root/'Scripts'/script).read_text(),globals())
            combat_pipeline.update(phase='running')
        else:
            if not globals().get(state,{}).get('finished'):return
            path=combat_root/'Artifacts'/report
            assert path.stat().st_mtime>=combat_pipeline['report_after'],'Stale report'
            data=json.loads(path.read_text())
            assert data['passed'],data.get('error')
            cases=sum(r['cases'] for r in data['results']) if state=='recovery_pipeline' else len(data['results'])
            combat_pipeline['results'].append({'script':script,'report':'Artifacts/'+report,'cases':cases,'passed':True})
            for name in ['test_world','test_pawn','test_input','test_subsystems','test_traversal']:
                globals().pop(name,None)
            u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play()
            combat_pipeline['index']+=1
            if combat_pipeline['index']==len(combat_steps):combat_pipeline_finish()
            else:combat_pipeline.update(phase='start',next=now+1)
    except Exception:combat_pipeline_finish(traceback.format_exc())
    finally:combat_pipeline['busy']=False


combat_pipeline['handle']=u.register_slate_post_tick_callback(combat_pipeline_tick)
print('Queued combat/shoulder regressions in fresh play sessions')
