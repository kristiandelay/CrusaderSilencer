"""Rebuild selected mechanical robots (or all six) with Blender validation."""
import json,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BLENDER='C:/Program Files/Blender Foundation/Blender 5.2/blender.exe'
names=sys.argv[1:] or list(json.loads((ROOT/'resources/RobotRigs.json').read_text()))
for name in names:
    folder=ROOT/'Artifacts/Robots'/name;folder.mkdir(parents=True,exist_ok=True)
    if not (ROOT/'Artifacts/Robots'/(name+'_Working.blend')).exists():
        with (folder/'inspection.log').open('w') as log:
            subprocess.run([BLENDER,'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'Scripts/Inspect-RobotSources.py'),'--',name],stdout=log,stderr=subprocess.STDOUT,check=True)
    for script in ['Rig-Robot.py','Validate-RobotRig.py']:
        with (folder/(script+'.log')).open('w') as log:
            subprocess.run([BLENDER,'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'Scripts'/script),'--',name],stdout=log,stderr=subprocess.STDOUT,check=True)
    print('ROBOT_READY',name,flush=True)
