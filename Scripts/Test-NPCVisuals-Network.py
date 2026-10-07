"""Check new visual selections on host, client and both replicated pawn views."""
from pathlib import Path
import unreal as u

npc_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
exec(compile((npc_root/'Scripts/Test-VisualOverrides-Network.py').read_text(),'Test-VisualOverrides-Network.py','exec'),globals())
visual_net['index']=7
visual_net_out=npc_root/'Artifacts/NPCCharacters/network-validation.json'
