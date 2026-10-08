"""Record completed, current reports and preserved source hashes for this batch."""
import datetime,hashlib,json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
reports={}
for name,rel in [('walkthrough','ControlRoom/walkthrough.json'),('patrols','ControlRoom/crowd.json'),
                 ('visuals','NPCCharacters/Additions/visual-overrides.json'),('network','NPCCharacters/Additions/network.json'),
                 ('assets','ControlRoom/asset-validation.json')]:
    result=json.loads((root/'Artifacts'/rel).read_text());assert result['passed'],(name,result.get('error'))
    reports[name]=result
characters=[]
for row in json.loads((root/'resources/NPCAdditions.json').read_text()):
    name=row['name'];rig=json.loads((root/'Artifacts/NPCCharacters'/name/'rig-report.json').read_text())
    fingers=json.loads((root/'Artifacts/NPCCharacters'/name/'finger-deformation.json').read_text())
    assert rig['unweighted_vertices']==0 and rig['max_influences']==4 and rig['bones']==64 and fingers['passed']
    assert hashlib.sha256((root/row['archive']).read_bytes()).hexdigest()==row['sha256']
    characters.append(dict(name=name,role=row['role'],rig=rig,fingers=fingers,archive_sha256=row['sha256'],export_sha256=hashlib.sha256((root/'Art/Characters'/name/'Export'/(name+'.fbx')).read_bytes()).hexdigest()))
models=[]
for row in json.loads((root/'resources/EnvironmentModels.json').read_text()):
    if row['category']!='Level2':continue
    assert row['imported'] and hashlib.sha256((root/row['archive']).read_bytes()).hexdigest()==row['sha256']
    models.append(dict(name=row['name'],asset=row['asset'],archive_sha256=row['sha256']))
assert len(characters)==10 and len(models)==19
assert len([r for r in reports['visuals']['results'] if r.get('case')=='widget_select'])==10
report=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,
            scope='Ten humanoid additions, nineteen Level2 assets and the roofed traversal control room',
            map='/Game/Maps/L_TraversalGym',catalog_size=21,default_visual='CrimsonSentinel',
            characters=characters,environment=models,checks=reports)
(root/'resources/ControlRoomValidation.json').write_text(json.dumps(report,indent=2)+'\n')
print('CONTROL_ROOM_VALIDATION_RECORDED',len(characters),'rigs',len(models),'models',len(reports),'passed reports')
