"""Focused follow-up for recovery timing under repeated network animation updates."""
from pathlib import Path
import unreal as u

root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
runner=(root/'Scripts/Test-VisualOverride-Regressions.py').read_text()
runner=runner.replace("'Artifacts/VisualOverride/regressions.json'", "'Artifacts/VisualOverride/recovery-clock-regressions.json'")
exec(runner,globals())
visual_steps=[
    ('Test-PhysicalInteractions-Network.py','net_physical','PhysicalTests/network-physical.json','VisualOverride/twinblast-network-physical.json','PIE_ListenServer',2,1),
    ('Test-GetUpContinuity.py','getup_test','PhysicalTests/getup-continuity.json','VisualOverride/kellan-recovery.json','PIE_Standalone',1,2),
    ('Test-GetUpRegressions.py','recovery_pipeline','PhysicalTests/getup-regressions.json','VisualOverride/recovery-clock-default.json','PIE_Standalone',1,-1),
    ('Test-CombatDeath.py','death_test','CombatTests/combat-death.json','VisualOverride/recovery-clock-death.json','PIE_Standalone',1,-1),
    ('Test-PhysicalInteractions-Network.py','net_physical','PhysicalTests/network-physical.json','VisualOverride/recovery-clock-network.json','PIE_ListenServer',2,-1),
]
