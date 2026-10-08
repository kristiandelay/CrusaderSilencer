"""Targeted roll interruptions, armed sliding and armed GASP traversal."""
from pathlib import Path
import unreal as u

rrs_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
source=(rrs_root/'Scripts/Test-RollNetworkSuite.py').read_text().replace('Artifacts/Roll/network-suite.json','Artifacts/Roll/regression-suite.json')
exec(compile(source,'Test-RollNetworkSuite.py','exec'),globals())
addition_steps=[('Test-RollInteractions.py','ri_test','Roll/interactions.json','PIE_Standalone',1),
                ('Test-SlideCombat.py','ss_test','SlideCadence/combat.json','PIE_Standalone',1),
                ('Test-RollTraversal.py','gym_test','Roll/Traversal/result.json','PIE_Standalone',1)]
addition_test['deadline']=time.monotonic()+300
