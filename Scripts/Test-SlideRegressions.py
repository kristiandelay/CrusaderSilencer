"""Slide cadence, armed sliding, shared NPC movement and client prediction."""
from pathlib import Path
import unreal as u

sr_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
(sr_root/'Artifacts/SlideCadence').mkdir(parents=True,exist_ok=True)
sr_quality={name:u.SystemLibrary.get_console_variable_int_value(name) for name in ['sg.ShadowQuality','sg.GlobalIlluminationQuality','sg.ReflectionQuality','sg.PostProcessQuality','sg.EffectsQuality','sg.TextureQuality']}
sr_quality['r.ScreenPercentage']=u.SystemLibrary.get_console_variable_float_value('r.ScreenPercentage')
sr_settings=u.load_object(None,'/Script/UnrealEd.Default__LevelEditorPlaySettings')
sr_previous={}
for line in u.CRBlueprintTools.describe_object(sr_settings).splitlines():
    if ' = ' in line:
        name,value=line.split(' = ',1)
        if name in ['PlayNetMode','PlayNumberOfClients','RunUnderOneProcess']:sr_previous[name]=value
for name in sr_quality:u.SystemLibrary.execute_console_command(None,name+' '+('50' if name=='r.ScreenPercentage' else '1'))
sr_source=(sr_root/'Scripts/Test-CrusaderAdditions.py').read_text().replace('Artifacts/WeaponFX/final-checks.json','Artifacts/SlideCadence/regressions.json')
exec(compile(sr_source,'Test-CrusaderAdditions.py','exec'),globals())
addition_steps=[
    ('Test-SlideCadence.py','sc_test','SlideCadence/standalone.json','PIE_Standalone',1),
    ('Test-SlideCombat.py','ss_test','SlideCadence/combat.json','PIE_Standalone',1),
    ('Test-SlideNPC.py','ct_test','SlideCadence/npc.json','PIE_Standalone',1),
    ('Test-SlideCadence.py','sc_test','SlideCadence/network.json','PIE_ListenServer',2)]
addition_test['deadline']=time.monotonic()+400
sr_original_finish=addition_finish

def addition_finish(error=None):
    u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play()
    for name,value in sr_quality.items():u.SystemLibrary.execute_console_command(None,name+' '+str(value))
    for name,value in sr_previous.items():u.CRBlueprintTools.set_property_text(sr_settings,name,value)
    sr_original_finish(error)
