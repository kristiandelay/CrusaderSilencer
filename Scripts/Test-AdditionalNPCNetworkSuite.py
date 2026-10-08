"""Run new character replication checks and restore editor Play/quality settings."""
from pathlib import Path
import unreal as u

ans_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
ans_quality={name:u.SystemLibrary.get_console_variable_int_value(name) for name in ['sg.ShadowQuality','sg.GlobalIlluminationQuality','sg.ReflectionQuality','sg.PostProcessQuality','sg.EffectsQuality','sg.TextureQuality']}
ans_quality['r.ScreenPercentage']=u.SystemLibrary.get_console_variable_float_value('r.ScreenPercentage')
ans_settings=u.load_object(None,'/Script/UnrealEd.Default__LevelEditorPlaySettings')
ans_previous={}
for line in u.CRBlueprintTools.describe_object(ans_settings).splitlines():
    if ' = ' in line:
        key,value=line.split(' = ',1)
        if key in ['PlayNetMode','PlayNumberOfClients','RunUnderOneProcess']:ans_previous[key]=value
for key in ans_quality:u.SystemLibrary.execute_console_command(None,key+' '+('50' if key=='r.ScreenPercentage' else '1'))
exec(compile((ans_root/'Scripts/Test-CrusaderAdditions.py').read_text().replace('Artifacts/WeaponFX/final-checks.json','Artifacts/ControlRoom/network-suite.json'),'Test-CrusaderAdditions.py','exec'),globals())
addition_steps=[('Test-AdditionalNPCNetwork.py','visual_net','NPCCharacters/Additions/network.json','PIE_ListenServer',2)]
addition_test['deadline']=time.monotonic()+240
ans_original_finish=addition_finish

def addition_finish(error=None):
    u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play()
    for key,value in ans_quality.items():u.SystemLibrary.execute_console_command(None,key+' '+str(value))
    for key,value in ans_previous.items():u.CRBlueprintTools.set_property_text(ans_settings,key,value)
    u.SystemLibrary.execute_console_command(None,'DDCvar.VisualOverride 6')
    ans_original_finish(error)
