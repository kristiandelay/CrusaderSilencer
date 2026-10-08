"""Preserve and normalize the October character and Level2 source deliveries."""
import contextlib,hashlib,importlib.util,io,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('meshy_source',ROOT/'Scripts/Prepare-MeshySource.py')
source_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(source_module)
CHARACTERS=[
 ('1007191946','ArmoredSentinel','Guards'),('1007183706','AstronautSentinel','Guards'),('1007202501','CrimsonVanguard','Guards'),
 ('1007185253','MaintenanceWorker','NPC'),('1007185205','RuggedMiner','NPC'),('1007183713','RustboundExplorer','NPC'),
 ('1007202431','CrimsonAuthority','NPC'),('1007203010','CrusaderOperative','NPC'),('1007202451','GraySentinel','NPC'),('1007202441','RuggedSurvivor','NPC')]
ENVIRONMENT=[
 ('1007205201','BlackEquipmentCase',110),('1007204907','BlueSlateShowcase',300),('1007205140','BlueSteelVault',125),
 ('1007204952','BronzeVentilationPanel',300),('1007204828','CommandNexus',550),('1007205241','IndustrialAirlockDoor',400),
 ('1007205121','IndustrialCargoCrate',125),('1007205313','IndustrialVentWall',300),('1007205102','IndustrialWallPanel',300),
 ('1007205217','IronboundBastion',300),('1007205047','MidnightCircuitSlab',300),('1007205008','OldBattery',120),
 ('1007204922','RetroCyberConsole',180),('1007204853','RetroServerTerminal',200),('1007205300','RuneChocolateBar',300),
 ('1007205025','RustyRadioactiveBarrel',130),('1007205230','TriangularBastion',300),('1007205325','WallCControlPanel',300),('1007204937','WallG',400)]

def prepare(identifier,name,relative,folder):
    directory=ROOT/relative;matches=list(directory.glob('*'+identifier+'*.zip'));destination=directory/(name+'.zip')
    assert len(matches)<=1,(name,matches)
    archive=matches[0] if matches else destination
    assert archive.is_file(),archive
    original=archive.name;digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    if archive!=destination:
        assert not destination.exists(),destination
        archive.rename(destination)
    with contextlib.redirect_stdout(io.StringIO()):source_module.prepare(destination,name,folder)
    manifest_path=folder/'SourceManifest.json';manifest=json.loads(manifest_path.read_text())
    manifest['original_archive_name']=manifest.get('original_archive_name',original)
    manifest['archive_path']=destination.relative_to(ROOT).as_posix()
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    return dict(name=name,archive=manifest['archive_path'],original_archive_name=manifest['original_archive_name'],sha256=digest,imported=False)

if __name__=='__main__':
    old=json.loads((ROOT/'mockups/AssetSources.json').read_text());new=[];characters=[]
    for identifier,name,category in CHARACTERS:
        record=prepare(identifier,name,'mockups/'+category,ROOT/'Art/Characters'/name/'Source')
        previous=next((x for x in old if x['name']==name),{})
        if previous.get('imported'):record.update(imported=True,asset=previous.get('asset','/Game/Crusader/Characters/'+name+'/'+name))
        record.update(category=category,role='Guard' if category=='Guards' else 'Civilian');new.append(record);characters.append(record)
    environment=json.loads((ROOT/'resources/EnvironmentModels.json').read_text())
    for identifier,name,size in ENVIRONMENT:
        record=prepare(identifier,name,'mockups/Environment/Level2',ROOT/'Art/Environment/Level2'/name/'Source')
        record.update(category='Level2',longest_dimension_cm=size,surface='Metal')
        previous=next((x for x in environment if x['name']==name),{})
        if previous.get('imported'):record.update(imported=True,asset=previous['asset'])
        environment=[x for x in environment if x['name']!=name]+[record];new.append(record)
    names={r['name'] for r in new}
    (ROOT/'mockups/AssetSources.json').write_text(json.dumps([r for r in old if r['name'] not in names]+new,indent=2)+'\n')
    (ROOT/'resources/NPCAdditions.json').write_text(json.dumps(characters,indent=2)+'\n')
    (ROOT/'resources/EnvironmentModels.json').write_text(json.dumps(environment,indent=2)+'\n')
    print('ADDITIONAL_SOURCES_PREPARED',len(characters),'characters and',len(ENVIRONMENT),'Level2 models')
