"""Two-player regression for visual ownership, shot/decal prediction and feet."""
from pathlib import Path
import unreal as u
network_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
network_quality={name:u.SystemLibrary.get_console_variable_int_value(name) for name in ['sg.ShadowQuality','sg.GlobalIlluminationQuality','sg.ReflectionQuality','sg.PostProcessQuality','sg.EffectsQuality','sg.TextureQuality']}
network_quality['r.ScreenPercentage']=u.SystemLibrary.get_console_variable_float_value('r.ScreenPercentage')
for name in network_quality:u.SystemLibrary.execute_console_command(None,name+' '+('50' if name=='r.ScreenPercentage' else '1'))
source=(network_root/'Scripts/Test-CrusaderAdditions.py').read_text().replace('Artifacts/WeaponFX/final-checks.json','Artifacts/Environment/network-suite.json')
exec(compile(source,'Test-CrusaderAdditions.py','exec'),globals())
addition_steps=[
 ('Test-NPCVisuals-Network.py','visual_net','NPCCharacters/network-validation.json','PIE_ListenServer',2),
 ('Test-WeaponEffects-Network.py','net_fx','WeaponFX/network-validation.json',None,2),
 ('Test-CrowdAudio-Network.py','cn_test','Environment/network.json',None,2)]
addition_test['deadline']=time.monotonic()+450
network_original_finish=addition_finish
def addition_finish(error=None):
    for name,value in network_quality.items():u.SystemLibrary.execute_console_command(None,name+' '+str(value))
    network_original_finish(error)
