"""Actual release leg animation in standalone and a two-player listen server."""
from pathlib import Path
import unreal as u
trls_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
source=(trls_root/'Scripts/Test-RollNetworkSuite.py').read_text().replace('Artifacts/Roll/network-suite.json','Artifacts/Throw/release-legs-suite.json')
exec(compile(source,'Test-RollNetworkSuite.py','exec'),globals())
addition_steps=[('Test-ThrowReleaseLegs.py','trl_test','Throw/release-legs.json','PIE_Standalone',1),
                ('Test-ThrowReleaseLegs.py','trl_test','Throw/release-legs-network.json','PIE_ListenServer',2)]
addition_test['deadline']=time.monotonic()+400
