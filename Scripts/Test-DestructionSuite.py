"""Standalone and two-player destruction integration checks; restore preferences."""
from pathlib import Path
import unreal as u
dsuite_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
exec(compile((dsuite_root/'Scripts/Test-RollNetworkSuite.py').read_text().replace('Artifacts/Roll/network-suite.json','Artifacts/Destruction/suite.json'),'Test-RollNetworkSuite.py','exec'),globals())
addition_steps=[('Test-Destruction.py','dt_test','Destruction/standalone.json','PIE_Standalone',1),
                ('Test-Destruction.py','dt_test','Destruction/network.json','PIE_ListenServer',2)]
addition_test['deadline']=time.monotonic()+1500
