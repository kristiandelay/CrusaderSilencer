"""Run the roll replication test with two clients and restore editor preferences."""
from pathlib import Path
import unreal as u

rns_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
rns_quality={name:u.SystemLibrary.get_console_variable_int_value(name) for name in ['sg.ShadowQuality','sg.GlobalIlluminationQuality','sg.ReflectionQuality','sg.PostProcessQuality','sg.EffectsQuality','sg.TextureQuality']}
rns_quality['r.ScreenPercentage']=u.SystemLibrary.get_console_variable_float_value('r.ScreenPercentage')
rns_settings=u.load_object(None,'/Script/UnrealEd.Default__LevelEditorPlaySettings')
rns_performance=u.load_object(None,'/Script/UnrealEd.Default__EditorPerformanceSettings')
rns_throttling=dict(line.split(' = ',1) for line in u.CRBlueprintTools.describe_object(rns_performance).splitlines() if line.startswith(('bThrottleCPUWhenNotForeground = ','bAllowSlateThrottling = ')))
for key in rns_throttling:assert u.CRBlueprintTools.set_property_text(rns_performance,key,'False')
rns_previous={}
for line in u.CRBlueprintTools.describe_object(rns_settings).splitlines():
    if ' = ' in line:
        key,value=line.split(' = ',1)
        if key in ['PlayNetMode','PlayNumberOfClients','RunUnderOneProcess']:rns_previous[key]=value
for key in rns_quality:u.SystemLibrary.execute_console_command(None,key+' '+('50' if key=='r.ScreenPercentage' else '1'))
exec(compile((rns_root/'Scripts/Test-CrusaderAdditions.py').read_text().replace('Artifacts/WeaponFX/final-checks.json','Artifacts/Roll/network-suite.json'),'Test-CrusaderAdditions.py','exec'),globals())
addition_steps=[('Test-RollNetwork.py','rn_test','Roll/network.json','PIE_ListenServer',2)]
addition_test['deadline']=time.monotonic()+240
rns_original_finish=addition_finish

def addition_finish(error=None):
    u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play()
    for key,value in rns_quality.items():u.SystemLibrary.execute_console_command(None,key+' '+str(value))
    for key,value in rns_previous.items():u.CRBlueprintTools.set_property_text(rns_settings,key,value)
    for key,value in rns_throttling.items():u.CRBlueprintTools.set_property_text(rns_performance,key,value)
    u.SystemLibrary.execute_console_command(None,'DDCvar.VisualOverride 6')
    rns_original_finish(error)
