from pathlib import Path
import unreal as u
rdn_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
exec((rdn_root/'Scripts/Test-RollDirections.py').read_text(),globals())
rdx_cases=[case for case in rdx_cases if case['mode'] in ['held','simultaneous']]
rdx_test['report']='network.json'
