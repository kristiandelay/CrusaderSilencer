"""NPC pose/speed regression with navigation, traversal and observer playback."""
from pathlib import Path
import unreal as u

ls_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
ls_quality={name:u.SystemLibrary.get_console_variable_int_value(name) for name in ['sg.ShadowQuality','sg.GlobalIlluminationQuality','sg.ReflectionQuality','sg.PostProcessQuality','sg.EffectsQuality','sg.TextureQuality']}
ls_quality['r.ScreenPercentage']=u.SystemLibrary.get_console_variable_float_value('r.ScreenPercentage')
ls_settings=u.load_object(None,'/Script/UnrealEd.Default__LevelEditorPlaySettings')
ls_previous={}
for line in u.CRBlueprintTools.describe_object(ls_settings).splitlines():
    if ' = ' in line:
        name,value=line.split(' = ',1)
        if name in ['PlayNetMode','PlayNumberOfClients','RunUnderOneProcess']:ls_previous[name]=value
for name in ls_quality:u.SystemLibrary.execute_console_command(None,name+' '+('50' if name=='r.ScreenPercentage' else '1'))
source=(ls_root/'Scripts/Test-CrusaderAdditions.py').read_text().replace('Artifacts/WeaponFX/final-checks.json','Artifacts/Locomotion/suite.json')
exec(compile(source,'Test-CrusaderAdditions.py','exec'),globals())
addition_steps=[
 ('Test-CrowdLocomotion.py','cl_test','Locomotion/standalone.json','PIE_Standalone',1),
 ('Test-CrowdAvoidance.py','av_test','Environment/crowd-avoidance.json','PIE_Standalone',1),
 ('Test-CrowdTraversal.py','ct_test','Environment/crowd-traversal.json','PIE_Standalone',1),
 ('Test-CrowdLocomotion.py','cl_test','Locomotion/network.json','PIE_ListenServer',2)]
addition_test['deadline']=time.monotonic()+360
ls_original_finish=addition_finish
def addition_finish(error=None):
    u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play()
    for name,value in ls_quality.items():u.SystemLibrary.execute_console_command(None,name+' '+str(value))
    for name,value in ls_previous.items():u.CRBlueprintTools.set_property_text(ls_settings,name,value)
    ls_original_finish(error)
