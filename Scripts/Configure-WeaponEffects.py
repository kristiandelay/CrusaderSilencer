"""Connect licensed Fab VFX, surface sounds and decals to committed Lyra shots."""
import json
from pathlib import Path
import unreal as u

assert not u.EditorLevelLibrary.get_pie_worlds(False)
ROOT=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
lib=u.EditorAssetLibrary;tools=u.AssetToolsHelpers.get_asset_tools()
folder='/Game/Crusader/Effects'

def load(path):
    obj=u.load_asset(path);assert obj,path
    return obj
def save(obj):
    if isinstance(obj,u.Blueprint):
        u.BlueprintEditorLibrary.compile_blueprint(obj)
        assert not u.CRBlueprintTools.has_blueprint_errors(obj),obj.get_path_name()
    assert lib.save_loaded_asset(obj,only_if_is_dirty=False)
def asset(name,cls,factory,where=folder):
    return load(where+'/'+name) if lib.does_asset_exist(where+'/'+name) else tools.create_asset(name,where,cls,factory)

# ID, display name, Hivemind impact, Bullet Impact VFX sound, decal suffix.
SURFACES=[
 (0,'Default','Concrete','Concrete','Concrete'),
 (1,'Character','Flesh/Blood','Flesh',None),
 (2,'Concrete','Concrete','Concrete','Concrete'),
 (3,'Glass','Glass','Glass_Small','Glass_Common'),
 (4,'Metal','Metal','MetalSolid','Metal_Solid'),
 (5,'Wood','Plank','Wood','Wood'),
 (6,'Brick','Brickwall','Brickwall','Brick_Wall'),
 (7,'Dirt','Dirt','Ground',None),
 (8,'Sand','Sand','Sand',None),
 (9,'Water','Water','Water',None),
 (10,'Rubber','Plastic','PlasticRubber','Rubber'),
 (11,'Fabric','Fabric','Soft_Materials','Sandbag'),
 (12,'Rock','Rock','Rock','Rock'),
 (13,'Snow','Snow','Snow','Snow'),
 (14,'Ice','Ice','Glass_Medium',None),
 (15,'Mud','Mud','MudWet',None),
 (16,'Ceramic','Ceramic','Glass_Pottery','Concrete'),
 (17,'Drywall','Drywall','Sheetrock','Sheetrock'),
 (18,'Grass','Dirt','Ground',None),(19,'Gravel','Rock','Rock',None),
 (20,'Leaves','Dirt','Ground',None),(21,'Carpet','Fabric','Soft_Materials','Sandbag'),
 (22,'BrokenGlass','Glass','Glass_Small',None),(23,'WetSand','Sand','Sand',None),
 (24,'DeepWater','Water','Water',None),(25,'GlassOnMetal','Metal','MetalSolid','Metal_Solid'),
 (26,'GlassOnWood','Plank','Wood','Wood'),(27,'HighGrass','Dirt','Ground',None)]

attenuation=asset('SA_BulletImpact',u.SoundAttenuation,u.SoundAttenuationFactory())
settings=attenuation.get_editor_property('attenuation')
settings.set_editor_property('attenuation_shape_extents',u.Vector(120,0,0))
settings.set_editor_property('falloff_distance',3500.0)
settings.set_editor_property('attenuate',True);settings.set_editor_property('spatialize',True)
attenuation.set_editor_property('attenuation',settings);save(attenuation)
entries=[];manifest=[]
for index,name,effect,sound,decal in SURFACES:
    physical=asset('PM_'+name,u.PhysicalMaterial,u.PhysicalMaterialFactoryNew(),folder+'/Surfaces')
    assert u.CRBlueprintTools.set_property_text(physical,'SurfaceType','SurfaceType_Default' if index==0 else 'SurfaceType'+str(index))
    save(physical)
    effect_folder,effect_name=effect.split('/') if '/' in effect else (effect,effect)
    niagara=load(f'/Game/GunFX/NiagaraSystem/ImpactFX/{effect_folder}/NS_Impact_{effect_name}_Low')
    cue=load('/Game/BulletImpactVFX/BulletHitVFX_SFX/ESounds/Cue/Cue_Bullet_Impact_'+sound)
    decal_obj=None
    if decal:
        prefix='M_BulletDecal_Wood_01_Inst' if decal=='Wood' else 'Inst_BulletDecal_'+decal+'_01'
        decal_obj=load('/Game/BulletImpactVFX/BulletHoleDecals/Material_Instances/'+prefix)
    entry=u.CRSurfaceImpact()
    assert entry.import_text('(Surface='+('SurfaceType_Default' if index==0 else 'SurfaceType'+str(index))+')')
    entry.set_editor_property('effect',niagara);entry.set_editor_property('sound',cue);entry.set_editor_property('decal',decal_obj)
    variants=[]
    if decal_obj:
        for path in lib.list_assets('/Game/BulletImpactVFX/BulletHoleDecals/Material_Instances',recursive=False):
            asset_name=path.rsplit('/',1)[-1].split('.')[0]
            if (decal=='Wood' and asset_name.startswith('M_BulletDecal_Wood_') and asset_name.endswith('_Inst')) or (decal!='Wood' and asset_name.startswith('Inst_BulletDecal_'+decal+'_')):
                variants.append(load(path))
    entry.set_editor_property('decal_variants',variants or ([decal_obj] if decal_obj else []))
    entry.set_editor_property('scale',.7 if name=='Character' else .65)
    entries.append(entry)
    manifest.append(dict(id=index,name=name,physical_material=physical.get_path_name(),effect=niagara.get_path_name(),sound=cue.get_path_name(),decal=decal_obj.get_path_name() if decal_obj else None))

for kind,muzzle,scale in [('Rifle','AR/NS_Muzzle_AR_01',.55),('Pistol','Pistol/NS_Muzzle_Pistol_01',.5),('Shotgun','Shotgun/NS_Muzzle_Shotgun_01',.65)]:
    factory=u.DataAssetFactory();factory.set_editor_property('data_asset_class',u.CRWeaponEffectsProfile)
    profile=asset('FX_'+kind,u.CRWeaponEffectsProfile,factory)
    profile.set_editor_property('muzzle_flash',load('/Game/GunFX/NiagaraSystem/MuzzleFlashes/'+muzzle))
    profile.set_editor_property('shell_ejection',None)
    profile.set_editor_property('bullet_trail',load('/Game/Bullet_Tracers_Fx/VFX/Lasers/NS_Laser_Trace_Red_2'))
    profile.set_editor_property('movement_driven_trail',True)
    profile.set_editor_property('trail_speed',18000.0)
    profile.set_editor_property('trail_particle_lifetime',.035)
    profile.set_editor_property('impact_attenuation',attenuation)
    profile.set_editor_property('surfaces',entries);profile.set_editor_property('muzzle_scale',scale)
    profile.set_editor_property('decal_size',4 if kind=='Shotgun' else 3)
    profile.set_editor_property('decal_lifetime',120.0);profile.set_editor_property('max_bullet_holes',96)
    save(profile)
    instance=load(f'/Game/Baseline/Weapons/{kind}/B_WeaponInstance_{kind}')
    u.get_default_object(instance.generated_class()).set_editor_property('effects_profile',profile);save(instance)

# The original cue remains available to non-Crusader weapons. Our empty impact
# cue avoids stacking Lyra impact audio over the surface sound in the component.
path='/Game/GameplayCueNotifies/GCN_CrusaderImpact'
if lib.does_asset_exist(path):cue=load(path)
else:
    factory=u.BlueprintFactory();factory.set_editor_property('parent_class',u.GameplayCueNotify_Burst)
    cue=tools.create_asset('GCN_CrusaderImpact','/Game/GameplayCueNotifies',u.Blueprint,factory)
cdo=u.get_default_object(cue.generated_class())
assert u.CRBlueprintTools.set_property_text(cdo,'GameplayCueTag','(TagName="GameplayCue.Weapon.Crusader.Impact")')
assert u.CRBlueprintTools.set_property_text(cdo,'GameplayCueName','GameplayCue.Weapon.Crusader.Impact')
save(cue)
for kind in ['Rifle','Pistol','Shotgun']:
    ability=load(f'/Game/Baseline/Weapons/{kind}/GA_Weapon_Fire_{kind}'+('_Auto' if kind=='Rifle' else ''))
    assert u.CRBlueprintTools.set_property_text(u.get_default_object(ability.generated_class()),'GameplayCue_Impact','(TagName="GameplayCue.Weapon.Crusader.Impact")')
    save(ability)
weapon=load('/Game/Weapons/B_Weapon')
assert u.CRBlueprintTools.configure_weapon_effects_gate(weapon)
save(weapon)
for name in ['BlackIronRifle','FuturisticPistol','TitanBreaker']:save(load(f'/Game/Crusader/Weapons/{name}/B_{name}'))
(ROOT/'resources/WeaponSurfaces.json').write_text(json.dumps(manifest,indent=2))
print('WEAPON_EFFECTS_CONFIGURED',len(entries),'surface profiles')
