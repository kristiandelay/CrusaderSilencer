"""Normalize the Level3 Meshy delivery without altering the source archive bytes."""
import importlib.util,json,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('additional_sources',ROOT/'Scripts/Prepare-AdditionalAssets.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
# Stable semantic names resolve truncated export titles and avoid previous kit names.
PROFILES='''
1008201536 ArcanePowerCell 300
1008201857 BlastDoor 450
1008201908 BlueTanIndustrialWall 330
1008201734 CeilingA 300
1008201357 CylindricalGlassCapsule 380
1008201547 ExtendedMagazine 300
1008201713 FortressGate 450
1008202022 GoldenStasisPillar 330
1008201447 HazardPlate 300
1008201917 HazardWallPanel 330
1008201409 IndustrialBatteryPanel 330
1008201755 MarsIndustrialCargoCrate 150
1008201807 IndustrialCargoPanel 330
1008201430 IndustrialFloorPanel 300
1008204420 IndustrialLightBarrier 300
1008201301 IndustrialMetalPanel 330
1008201513 IndustrialPortalFrame 450
1008202041 IndustrialPowerCore 450
1008201724 IndustrialPowerShutter 450
1008201819 IndustrialReactorPanel 330
1008201500 IndustrialSciFiBlastDoor 450
1008204457 IndustrialStaircase 1100
1008204442 IndustrialTriadFrame 330
1008201325 IndustrialVentPanel01 330
1008201559 IndustrialVentPanel02 330
1008204432 LuminousIronPillar 330
1008202051 ModularSlatePlatform 300
1008201744 ModularSteelFloorPanel 300
1008201939 NeonGateway 450
1008201951 PerforatedMetalColumn 330
1008201926 PlainWall 330
1008201313 PowerCell 330
1008201831 QuantumVaultDoor 450
1008201342 QuantumViewport 330
1008201609 ReinforcedPanel 330
1008201843 SlidingDoorOpen 450
1008201420 SolarPanel 300
1008202031 WallCVentPanel 330
1008202003 WallDControlPanel 330
1008201933 MarsWallG 450
1008201252 WallPanel 330
1008202011 YellowSafetyRailing 300
1008205039 BlueCrate 130
1008204909 CompactMachineBlock 180
1008204726 CRTComputerDesk 240
1008204816 CyberneticMedbayRecliner 220
1008205310 DangerHighVoltageSign 110
1008205144 EmergencyCallBox 70
1008205224 IndustrialAccessPanel 130
1008205327 IndustrialCabinet 220
1008205236 IndustrialHazardFloor 300
1008205254 IndustrialPipeManifold 380
1008204756 IndustrialPowerCabinet 240
1008204831 MarsIndustrialPowerCell 180
1008205131 IndustrialVentGrate 130
1008205121 IndustrialVentGrille 120
1008205003 IndustrialWallLight 180
1008205025 IroncladCargoCrate 150
1008205336 MarsCompactGenerator 280
1008204857 MarsFuelCanister 110
1008205112 MarsPathfinderConsole 220
1008205014 MarsRedCrate 130
1008204952 MarsResearchDivisionSign 160
1008205403 MarsToolLocker 240
1008204740 ObsidianServerRack 260
1008204922 PowerCoreColumn 430
1008205051 RadioactiveBarrel 130
1008204937 ReactorModule 320
1008204640 RetroCommandConsole 500
1008204653 RetroCommandWorkbench 300
1008204709 SwivelChair 120
1008205354 UtilityTurretFloor 250
1008204844 WallControlBox 100
1008205101 WeatheredBlueOilDrum 130
'''

if __name__=='__main__':
    models=json.loads((ROOT/'resources/EnvironmentModels.json').read_text())
    sources=json.loads((ROOT/'mockups/AssetSources.json').read_text())
    folder=ROOT/'mockups/Environment/Level3'
    profiles=[(i,n,int(s)) for i,n,s in (row.split() for row in PROFILES.strip().splitlines())]
    assert len({n for _,n,_ in profiles})==len(profiles)==74
    jobs=[]
    for identifier,name,size in profiles:
        matches=list(folder.rglob('*'+identifier+'*.zip')) or list(folder.rglob(name+'.zip'))
        assert len(matches)==1,(name,matches)
        archive=matches[0]
        with zipfile.ZipFile(archive) as z:
            members=[m for m in z.namelist() if not m.endswith('/')]
            assert len(members)==5 and sum(m.lower().endswith('.fbx') for m in members)==1,archive
            for suffix in ['_texture.png','_metallic.png','_normal.png','_roughness.png']:
                assert sum(m.lower().endswith(suffix) for m in members)==1,(archive,suffix)
        assert not any(r['name']==name and r['category']!='Level3' for r in models),name
        jobs.append((identifier,name,size,archive.parent))
    new=[]
    for identifier,name,size,parent in jobs:
        record=helper.prepare(identifier,name,parent.relative_to(ROOT),ROOT/'Art/Environment/Level3'/name/'Source')
        record.update(category='Level3',longest_dimension_cm=size,surface='Metal',kit_group='Props' if parent.name=='props' else 'Modular')
        previous=next((r for r in models if r['name']==name),{})
        if previous.get('imported'):record.update(imported=True,asset=previous['asset'])
        new.append(record)
        print('LEVEL3_SOURCE',name,flush=True)
    names={r['name'] for r in new}
    for path,old in [('resources/EnvironmentModels.json',models),('mockups/AssetSources.json',sources)]:
        (ROOT/path).write_text(json.dumps([r for r in old if r['name'] not in names]+new,indent=2)+'\n')
    (ROOT/'resources/Level3Sources.json').write_text(json.dumps(new,indent=2)+'\n')
    print('LEVEL3_SOURCES_PREPARED',len(new))
