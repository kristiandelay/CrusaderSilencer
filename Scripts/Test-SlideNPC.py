"""Run the existing shared-player movement fixture for both NPC slide roles."""
from pathlib import Path
import unreal as u

sn_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
sn_source=(sn_root/'Scripts/Test-CrowdTraversal.py').read_text().replace('Artifacts/Environment/crowd-traversal.json','Artifacts/SlideCadence/npc.json')
exec(compile(sn_source,'Test-CrowdTraversal.py','exec'),globals())
ct_cases=[case for case in ct_cases if case['name']=='Slide']
