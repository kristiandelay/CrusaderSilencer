"""Real keyboard combinations in standalone and on the owning network client."""
from pathlib import Path
import unreal as u
rds_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
source=(rds_root/'Scripts/Test-RollNetworkSuite.py').read_text().replace('Artifacts/Roll/network-suite.json','Artifacts/Roll/Diagonal/suite.json')
exec(compile(source,'Test-RollNetworkSuite.py','exec'),globals())
addition_steps=[('Test-RollDirections.py','rdx_test','Roll/Diagonal/standalone.json','PIE_Standalone',1),
                ('Test-RollDirectionsNetwork.py','rdx_test','Roll/Diagonal/network.json','PIE_ListenServer',2)]
addition_test['deadline']=time.monotonic()+280
