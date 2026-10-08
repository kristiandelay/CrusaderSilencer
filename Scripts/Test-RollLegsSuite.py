"""Roll pose/correction restoration, network poses and existing get-up continuity."""
from pathlib import Path
import unreal as u
rls_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
source=(rls_root/'Scripts/Test-RollNetworkSuite.py').read_text().replace('Artifacts/Roll/network-suite.json','Artifacts/Roll/Legs/suite.json')
exec(compile(source,'Test-RollNetworkSuite.py','exec'),globals())
addition_steps=[('Test-RollLegs.py','rlv_test','Roll/Legs/validation.json','PIE_Standalone',1),
                ('Test-RollLegsNetwork.py','rn_test','Roll/Legs/network.json','PIE_ListenServer',2),
                ('Test-GetUpContinuity.py','getup_test','PhysicalTests/getup-continuity.json','PIE_Standalone',1)]
addition_test['deadline']=time.monotonic()+420
