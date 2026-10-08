"""Throw gameplay and armed roll regression with editor preference restoration."""
from pathlib import Path
import unreal as u
tts_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
source=(tts_root/'Scripts/Test-RollNetworkSuite.py').read_text().replace('Artifacts/Roll/network-suite.json','Artifacts/Throw/suite.json')
exec(compile(source,'Test-RollNetworkSuite.py','exec'),globals())
addition_steps=[('Test-Throw.py','tt_test','Throw/standalone.json','PIE_Standalone',1),
                ('Test-ThrowNetwork.py','tn_test','Throw/network.json','PIE_ListenServer',2),
                ('Test-Roll.py','rt_test','Roll/standalone.json','PIE_Standalone',1),
                ('Test-RollNetwork.py','rn_test','Roll/network.json','PIE_ListenServer',2)]
addition_test['deadline']=time.monotonic()+300
