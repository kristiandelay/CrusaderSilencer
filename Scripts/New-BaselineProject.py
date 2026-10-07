"""Copy the verified baseline into an independent project without caches or game-specific root documents."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import uuid

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--name',default='Lyra GASP Baseline',help='Displayed project name; native Lyra module names are preserved.')
    args=parser.parse_args()
    source=Path(__file__).resolve().parents[1]
    destination=args.destination.resolve()
    if destination==source or destination in source.parents:
        parser.error('Destination must be a new directory, not this project or one of its parents.')
    for folder in ['src','Scripts','resources','docs']:
        selected=source/folder
        if destination==selected or selected in destination.parents:
            parser.error('Destination cannot be inside a source directory being copied.')
    if destination.exists() and any(destination.iterdir()):
        parser.error('Destination is not empty. Existing projects are never overwritten.')
    required=[source/'src/Content/Baseline',source/'src/Content/Maps/L_TraversalGym.umap',source/'src/Source/LyraGame/Baseline']
    if not all(p.exists() for p in required):
        parser.error('Baseline assets have not been authored. Run the setup before exporting.')
    destination.mkdir(parents=True,exist_ok=True)
    excluded={'Binaries','Intermediate','Saved','DerivedDataCache','.vs','.git','__pycache__','obj','bin'}
    def ignore(directory,names):
        return [n for n in names if n in excluded or n.endswith(('.sln','.slnx','.suo'))]
    shutil.copytree(source/'src',destination/'src',ignore=ignore,dirs_exist_ok=True)
    (destination/'Scripts').mkdir(exist_ok=True)
    scripts={'Build-Editor.ps1','Open-Traversal.ps1','EditorBridge.py','Send-Editor.py',
             'New-BaselineProject.py'}
    for pattern in ['Extend-*.py','Test-*.py']:
        scripts.update(p.name for p in (source/'Scripts').glob(pattern))
    for name in sorted(scripts):
        shutil.copy2(source/'Scripts'/name,destination/'Scripts'/name)
    (destination/'docs').mkdir(exist_ok=True)
    for name in ['BaselineTemplate.txt','TraversalSetup.txt']:
        if (source/'docs'/name).exists(): shutil.copy2(source/'docs'/name,destination/'docs'/name)
    (destination/'resources').mkdir(exist_ok=True)
    records={'IntegrationLock.json'}
    records.update(p.name for p in (source/'resources').glob('*Validation.json'))
    for name in sorted(records):
        if (source/'resources'/name).exists(): shutil.copy2(source/'resources'/name,destination/'resources'/name)
    for name in ['.gitignore','.gitattributes','Open-Traversal.cmd']:
        shutil.copy2(source/name,destination/name)
    project_id=uuid.uuid4().hex.upper()
    game_config=destination/'src/Config/DefaultGame.ini'
    text=game_config.read_text(encoding='utf-8-sig')
    text=re.sub(r'(?m)^ProjectID=.*$', 'ProjectID='+project_id,text)
    text=re.sub(r'(?m)^ProjectName=.*$', 'ProjectName='+args.name.replace('\n',' ').replace('\r',' '),text)
    game_config.write_text(text,encoding='utf-8')
    files=[p for p in destination.rglob('*') if p.is_file()]
    record={'exported_utc':datetime.now(timezone.utc).isoformat(),'name':args.name,'project_id':project_id,
            'project':'src/CrusaderSilencer.uproject','startup_map':'/Game/Maps/L_TraversalGym',
            'native_modules':['LyraGame','LyraEditor'],'file_count':len(files),'bytes':sum(p.stat().st_size for p in files),
            'excluded':sorted(excluded),'independent_files':True}
    (destination/'BaselineExport.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Created independent baseline:',destination)
    print('Files:',record['file_count'],'Bytes:',record['bytes'])
    print('Build with Scripts/Build-Editor.ps1, then open Open-Traversal.cmd.')

if __name__=='__main__':
    main()
