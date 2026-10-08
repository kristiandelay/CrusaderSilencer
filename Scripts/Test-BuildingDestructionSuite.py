"""Check furniture in standalone and two-player PIE, restoring editor preferences."""
from pathlib import Path
import unreal as u
bs_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
exec(compile((bs_root/'Scripts/Test-RollNetworkSuite.py').read_text().replace('Artifacts/Roll/network-suite.json','Artifacts/BuildingDestruction/suite.json'),'Test-RollNetworkSuite.py','exec'),globals())
addition_steps=[('Test-BuildingDestruction.py','bt_test','BuildingDestruction/standalone.json','PIE_Standalone',1),
                ('Test-BuildingDestruction.py','bt_test','BuildingDestruction/network.json','PIE_ListenServer',2)]
addition_test['deadline']=time.monotonic()+1500
