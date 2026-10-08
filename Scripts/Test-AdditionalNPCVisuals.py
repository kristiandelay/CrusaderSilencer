"""Exercise each Level2 arrival through real widget clicks and weapon poses."""
from pathlib import Path
import unreal as u

an_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
exec(compile((an_root/'Scripts/Test-NPCVisuals.py').read_text(),'Test-NPCVisuals.py','exec'),globals())
visual_test['index']=11
visual_out=an_root/'Artifacts/NPCCharacters/Additions'
visual_out.mkdir(exist_ok=True)
