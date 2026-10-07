"""Fresh sessions for skin changes, upright weapons, selected-skin recovery and baseline regressions."""
import json
import time
import traceback
from pathlib import Path
import unreal as u

visual_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
visual_steps=[
    ('Test-VisualOverrides.py','visual_test','VisualOverride/visual-overrides.json','VisualOverride/visual-overrides.json','PIE_Standalone',1,-1),
    ('Test-GetUpContinuity.py','getup_test','PhysicalTests/getup-continuity.json','VisualOverride/kellan-recovery.json','PIE_Standalone',1,2),
    ('Test-VisualOverrides-Network.py','visual_net','VisualOverride/network.json','VisualOverride/network.json','PIE_ListenServer',2,1),
    ('Test-PhysicalInteractions-Network.py','net_physical','PhysicalTests/network-physical.json','VisualOverride/twinblast-network-physical.json','PIE_ListenServer',2,1),
    ('Test-CombatShoulder-Regressions.py','combat_pipeline','CombatTests/combat-regressions.json','VisualOverride/baseline-regressions.json',None,1,-1),
]
visual_pipeline={'phase':'start','index':0,'next':0,'busy':False,'results':[],'deadline':time.monotonic()+1100}


def vp_finish(error=None):
    u.unregister_slate_post_tick_callback(visual_pipeline['handle'])
    visual_pipeline.update(finished=True,error=error)
    output=visual_root/'Artifacts/VisualOverride/regressions.json'
    output.write_text(json.dumps({'passed':error is None,'error':error,'results':visual_pipeline['results']},indent=2))
    print('VISUAL_REGRESSIONS_COMPLETE',error)


def vp_tick(dt):
    if visual_pipeline['busy']:return
    visual_pipeline['busy']=True
    try:
        now=time.monotonic()
        assert now<visual_pipeline['deadline'],'Visual regression pipeline timed out'
        if now<visual_pipeline['next']:return
        script,state,report,copy,mode,clients,skin=visual_steps[visual_pipeline['index']]
        phase=visual_pipeline['phase']
        if phase=='start':
            assert not u.EditorLevelLibrary.get_pie_worlds(False),'Start with Play stopped'
            u.SystemLibrary.execute_console_command(None,'t.IdleWhenNotForeground 0')
            u.SystemLibrary.execute_console_command(None,'DDCvar.VisualOverride '+str(skin))
            if mode:
                settings=u.load_object(None,'/Script/UnrealEd.Default__LevelEditorPlaySettings')
                for key,value in [('PlayNetMode',mode),('PlayNumberOfClients',str(clients)),('RunUnderOneProcess','True')]:
                    assert u.CRBlueprintTools.set_property_text(settings,key,value)
                u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_begin_play()
            visual_pipeline.update(phase='ready',next=now+2)
        elif phase=='ready':
            if mode:
                worlds=u.EditorLevelLibrary.get_pie_worlds(False)
                if len(worlds)<clients:return
                pawn=u.GameplayStatics.get_player_pawn(worlds[0],0)
                if not pawn or not pawn.physical_interaction.controls_created:return
                if skin>=0 and not pawn.selected_visual_override.get_editor_property('child_actor'):return
            visual_pipeline['report_after']=time.time()
            exec((visual_root/'Scripts'/script).read_text(),globals())
            visual_pipeline.update(phase='running')
        elif phase=='running':
            if not globals().get(state,{}).get('finished'):return
            path=visual_root/'Artifacts'/report
            assert path.stat().st_mtime>=visual_pipeline['report_after'],'Stale report'
            result=json.loads(path.read_text())
            assert result['passed'],result.get('error')
            if report!=copy:(visual_root/'Artifacts'/copy).write_text(path.read_text())
            count=sum(c['cases'] for c in result['results']) if state in ['combat_pipeline','recovery_pipeline'] else len(result['results'])
            visual_pipeline['results'].append({'script':script,'report':'Artifacts/'+copy,'skin':skin,'cases':count,'passed':True})
            for name in ['test_world','test_pawn','test_input','test_subsystems','test_traversal']:
                globals().pop(name,None)
            if u.EditorLevelLibrary.get_pie_worlds(False):u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play()
            visual_pipeline['index']+=1
            if visual_pipeline['index']==len(visual_steps):vp_finish()
            else:visual_pipeline.update(phase='start',next=now+1)
    except Exception:vp_finish(traceback.format_exc())
    finally:visual_pipeline['busy']=False


visual_pipeline['handle']=u.register_slate_post_tick_callback(vp_tick)
print('Queued visual override and shoulder orientation regressions')
