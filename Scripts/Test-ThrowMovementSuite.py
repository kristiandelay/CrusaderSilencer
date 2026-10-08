"""Throw locomotion on standalone and a client, plus existing shoulder/regression cases."""
from pathlib import Path
import unreal as u

tms_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
source=(tms_root/'Scripts/Test-RollNetworkSuite.py').read_text().replace('Artifacts/Roll/network-suite.json','Artifacts/Throw/movement-suite.json')
exec(compile(source,'Test-RollNetworkSuite.py','exec'),globals())
addition_steps=[('Test-ThrowMovement.py','tm_test','Throw/movement.json','PIE_Standalone',1),
                ('Test-ThrowMovement.py','tm_test','Throw/movement-network.json','PIE_ListenServer',2),
                ('Test-ThrowShoulders.py','tsh_test','Throw/shoulders.json','PIE_Standalone',1),
                ('Test-Throw.py','tt_test','Throw/standalone.json','PIE_Standalone',1)]
addition_test['deadline']=time.monotonic()+500
