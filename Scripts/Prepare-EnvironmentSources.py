"""Preserve source archives while normalizing Meshy environment filenames."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PROFILES={
 '1007065151':('BlackIndustrialDoor',280,'Metal'),
 '1007065040':('HazardStripeBarrier',220,'Metal'),
 '1007065213':('IndustrialShutterPanel',300,'Metal'),
 '1007065115':('IndustrialStargate',500,'Metal'),
 '1007064810':('IndustrialStonePanel',300,'Rock'),
 '1007065050':('MarbledSteelTile',300,'Metal'),
 '1007064752':('ObsidianPillar',350,'Rock'),
 '1007065141':('SciFiArchway',400,'Metal'),
 '1007065125':('SmokyMetalPanel',300,'Metal'),
 '1007065007':('WeatheredDoubleSwitch',60,'Metal'),
 '1007065550':('AlertSignal',70,'Metal'),
 '1007065404':('GeometricPrismInterface',80,'Metal'),
 '1007065346':('Hero',180,'Metal'),
 '1007065354':('HeroMonitor',90,'Metal'),
 '1007065709':('IndustrialCargoCrate01',150,'Metal'),
 '1007065753':('IndustrialCargoCrate02',180,'Metal'),
 '1007065531':('IndustrialEnergyCell',120,'Metal'),
 '1007065541':('IndustrialLandingPlatform',450,'Metal'),
 '1007065635':('IndustrialLEDWorkLight',160,'Metal'),
 '1007065624':('IndustrialMetalBookshelf',200,'Metal'),
 '1007065456':('IndustrialMetalNightstand',70,'Metal'),
 '1007065643':('IndustrialPowerBox',120,'Metal'),
 '1007065447':('IndustrialStorageCrate',100,'Metal'),
 '1007065503':('OliveExecutiveOfficeChair',120,'Fabric'),
 '1007065700':('RedBeacon',45,'Metal'),
 '1007065559':('RedHandStopSign',70,'Metal'),
 '1007065523':('RedIndustrialHatch',150,'Metal'),
 '1007065412':('RuggedCommandKeyboard',60,'Metal'),
 '1007065514':('RuggedControlModule',80,'Metal'),
 '1007065607':('RuggedDataCore',70,'Metal'),
 '1007065652':('SilverCylinder',100,'Metal'),
 '1007065437':('VintageMilitaryDesk',160,'Metal'),
 '1007065616':('WeatheredMetalVent',100,'Metal'),
}

if __name__=='__main__':
    old=json.loads((ROOT/'mockups/AssetSources.json').read_text())
    records=[]
    for identifier,(name,size,surface) in PROFILES.items():
        matches=list((ROOT/'mockups/Environment').rglob('*'+identifier+'*.zip'))
        previous=next((x for x in old if x['name']==name),None)
        source=matches[0] if matches else ROOT/previous['archive']
        category=source.parent.name
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        destination=source.with_name(name+'.zip')
        # Rename only the explicitly selected file; never overwrite an archive.
        if source!=destination:
            assert not destination.exists(),destination
            source.rename(destination)
        folder=ROOT/'Art/Environment'/category/name/'Source'
        folder.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(destination) as archive:
            for entry in archive.namelist():
                suffix=Path(entry).suffix.lower()
                if suffix=='.fbx':target=name+'.fbx'
                elif suffix=='.png':
                    kind=next((t for t in ['Normal','Metallic','Roughness'] if '_'+t.lower()+'.png' in entry),'BaseColor')
                    target=name+'_'+kind+'.png'
                else:continue
                (folder/target).write_bytes(archive.read(entry))
        record=dict(name=name,category=category,archive=destination.relative_to(ROOT).as_posix(),original_archive_name=previous['original_archive_name'] if previous else source.name,sha256=digest,imported=False,longest_dimension_cm=size,surface=surface)
        records.append(record)
        (folder/'SourceManifest.json').write_text(json.dumps(record,indent=2))
    (ROOT/'resources/EnvironmentModels.json').write_text(json.dumps(records,indent=2))
    names={r['name'] for r in records}
    (ROOT/'mockups/AssetSources.json').write_text(json.dumps([r for r in old if r['name'] not in names]+records,indent=2))
    print('Prepared',len(records),'environment sources')
