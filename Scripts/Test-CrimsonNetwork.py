"""Run the new visual/weapon replication case in two-player listen-server PIE."""
from pathlib import Path
import unreal as u

crimson_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
exec(compile((crimson_root/'Scripts/Test-VisualOverrides-Network.py').read_text(),
             'Test-VisualOverrides-Network.py','exec'),globals())
visual_net['index']=6
visual_net_out=crimson_root/'Artifacts/CrimsonSentinel/network-validation.json'

visual_net['last_index']=7
