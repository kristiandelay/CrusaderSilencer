"""Throw hand switching in standalone and on the owning network client."""
from pathlib import Path
import unreal as u
tss_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
source=(tss_root/'Scripts/Test-RollNetworkSuite.py').read_text().replace('Artifacts/Roll/network-suite.json','Artifacts/Throw/shoulders-suite.json')
exec(compile(source,'Test-RollNetworkSuite.py','exec'),globals())
addition_steps=[('Test-ThrowShoulders.py','tsh_test','Throw/shoulders.json','PIE_Standalone',1),
                ('Test-ThrowShoulders.py','tsh_test','Throw/shoulders-network.json','PIE_ListenServer',2)]
addition_test['deadline']=time.monotonic()+300
