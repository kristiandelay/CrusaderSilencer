"""Run laser player, NPC and multiplayer checks in the traversal map."""
from pathlib import Path
import unreal as u

ls_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
ls_source=(ls_root/'Scripts/Test-SlideRegressions.py').read_text().replace('Artifacts/SlideCadence/regressions.json','Artifacts/LaserTracer/regressions.json')
exec(compile(ls_source,'Test-SlideRegressions.py','exec'),globals())
addition_steps=[
    ('Test-LaserTracers.py','fx_test','LaserTracer/player.json','PIE_Standalone',1),
    ('Test-LaserTracers-Guards.py','lg_test','LaserTracer/guards.json','PIE_Standalone',1),
    ('Test-LaserTracers-Network.py','net_fx','LaserTracer/network.json','PIE_ListenServer',2)]
