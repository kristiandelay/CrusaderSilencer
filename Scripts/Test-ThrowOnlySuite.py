"""Throw-specific checks after asset and trajectory refinements."""
from pathlib import Path
import unreal as u
ttos_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
source=(ttos_root/'Scripts/Test-RollNetworkSuite.py').read_text().replace('Artifacts/Roll/network-suite.json','Artifacts/Throw/throw-suite.json')
exec(compile(source,'Test-RollNetworkSuite.py','exec'),globals())
addition_steps=[('Test-Throw.py','tt_test','Throw/standalone.json','PIE_Standalone',1),
                ('Test-ThrowNetwork.py','tn_test','Throw/network.json','PIE_ListenServer',2)]
addition_test['deadline']=time.monotonic()+220
