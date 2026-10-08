"""Slide throws on owner/client, existing slide cadence, firearm and walking checks."""
from pathlib import Path
import unreal as u
tsls_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
source=(tsls_root/'Scripts/Test-RollNetworkSuite.py').read_text().replace('Artifacts/Roll/network-suite.json','Artifacts/Throw/slide-suite.json')
exec(compile(source,'Test-RollNetworkSuite.py','exec'),globals())
addition_steps=[('Test-ThrowSlide.py','tsl_test','Throw/slide.json','PIE_Standalone',1),
                ('Test-ThrowSlide.py','tsl_test','Throw/slide-network.json','PIE_ListenServer',2),
                ('Test-SlideCadence.py','sc_test','SlideCadence/standalone.json','PIE_Standalone',1),
                ('Test-SlideCadence.py','sc_test','SlideCadence/network.json','PIE_ListenServer',2),
                ('Test-SlideCombat.py','ss_test','SlideCadence/combat.json','PIE_Standalone',1),
                ('Test-ThrowMovement.py','tm_test','Throw/movement.json','PIE_Standalone',1),
                ('Test-Throw.py','tt_test','Throw/standalone.json','PIE_Standalone',1)]
addition_test['deadline']=time.monotonic()+600
