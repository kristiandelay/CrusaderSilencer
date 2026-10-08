"""Robot gameplay, existing human crowd regression, and two-player replication."""
from pathlib import Path
import unreal as u

rs_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False),'Stop PIE before the suite'
rs_quality={name:u.SystemLibrary.get_console_variable_int_value(name) for name in ['sg.ShadowQuality','sg.GlobalIlluminationQuality','sg.ReflectionQuality','sg.PostProcessQuality','sg.EffectsQuality','sg.TextureQuality','t.IdleWhenNotForeground','DDCvar.VisualOverride']}
rs_quality['r.ScreenPercentage']=u.SystemLibrary.get_console_variable_float_value('r.ScreenPercentage')
rs_settings=u.load_object(None,'/Script/UnrealEd.Default__LevelEditorPlaySettings')
rs_previous={}
for line in u.CRBlueprintTools.describe_object(rs_settings).splitlines():
    if ' = ' in line:
        name,value=line.split(' = ',1)
        if name in ['PlayNetMode','PlayNumberOfClients','RunUnderOneProcess']:rs_previous[name]=value
for name in rs_quality:
    if name.startswith('sg.') or name=='r.ScreenPercentage':u.SystemLibrary.execute_console_command(None,name+' '+('50' if name=='r.ScreenPercentage' else '1'))
source=(rs_root/'Scripts/Test-CrusaderAdditions.py').read_text().replace('Artifacts/WeaponFX/final-checks.json','Artifacts/RobotGameplay/suite.json')
source=source.replace('DDCvar.VisualOverride 6','DDCvar.VisualOverride '+str(rs_quality['DDCvar.VisualOverride']))
exec(compile(source,'Test-CrusaderAdditions.py','exec'),globals())
addition_steps=[
    ('Test-RobotGameplay.py','ra_test','RobotGameplay/standalone.json','PIE_Standalone',1),
    ('Test-CrowdAI.py','ai_test','Environment/crowd-ai.json','PIE_Standalone',1),
    ('Test-RobotGameplay-Network.py','rn_test','RobotGameplay/network.json','PIE_ListenServer',2)]
rs_original_finish=addition_finish

def addition_finish(error=None):
    u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play()
    for name,value in rs_quality.items():u.SystemLibrary.execute_console_command(None,name+' '+str(value))
    for name,value in rs_previous.items():u.CRBlueprintTools.set_property_text(rs_settings,name,value)
    rs_original_finish(error)
