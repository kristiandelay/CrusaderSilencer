"""Bind the licensed footstep library to GASP contact events and physical surfaces."""
import json
import unreal as u
from pathlib import Path

ROOT=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
lib=u.EditorAssetLibrary;tools=u.AssetToolsHelpers.get_asset_tools()
assert not u.EditorLevelLibrary.get_pie_worlds(False)
folder='/Game/Crusader/Audio'
def asset(name,cls,factory):
    return u.load_asset(folder+'/'+name) if lib.does_asset_exist(folder+'/'+name) else tools.create_asset(name,folder,cls,factory)
def save(obj):assert lib.save_loaded_asset(obj,only_if_is_dirty=False)

groups={
0:['Concrete1','Concrete2'],2:['Concrete1','Concrete2'],3:['Glass1'],4:['Metal1','Metal2'],5:['Wood1','Wood2'],6:['Concrete2'],
7:['Dirt1','Dirt2'],8:['Sand1'],9:['ShallowWater-WetSurface1'],10:['CarpetHard1'],11:['CarpetWood1'],12:['Gravel1','Gravel2'],
13:['Snow1'],14:['Ice1'],15:['Mud1'],16:['Concrete1'],17:['Concrete2'],18:['Grass1','Grass2'],19:['Gravel1','Gravel2'],
20:['Undergrowth-Leaves1'],21:['CarpetHard1','CarpetWood1'],22:['BrokenGlass-GlassShards1','GlassShardsConcrete1','GlassShardsConcrete2'],
23:['WetSand1'],24:['DeepWater1'],25:['GlassShardsMetal1','GlassShardsMetal2'],26:['GlassShardsWood1','GlassShardsWood2'],27:['HighGrass1']}
surfaces=json.loads((ROOT/'resources/WeaponSurfaces.json').read_text())
rows=[];report=[];all_waves=set()
for index,folders in groups.items():
    row=u.CRFootstepSurface();assert row.import_text('(Surface='+('SurfaceType_Default' if index==0 else 'SurfaceType'+str(index))+')')
    names=[]
    for group in folders:names+=lib.list_assets('/Game/TWSFX_FS_Ultimate1/'+group+'/WAV',recursive=False)
    counts={}
    for gait in ['sneak','walk','run','sprint','jump','land']:
        matching=sorted(p for p in names if '_'+gait+'_' in p.lower() or (gait=='land' and '_landing_' in p.lower()))
        sounds=[u.load_asset(p) for p in matching];assert sounds and all(isinstance(s,u.SoundWave) for s in sounds),(index,gait)
        row.set_editor_property(gait,sounds);counts[gait]=len(sounds);all_waves.update(matching)
    rows.append(row)
    report.append(dict(id=index,name=next(s['name'] for s in surfaces if s['id']==index),groups=folders,samples=counts))
attenuation=asset('SA_Footsteps',u.SoundAttenuation,u.SoundAttenuationFactory())
settings=attenuation.get_editor_property('attenuation');settings.attenuate=True;settings.spatialize=True
settings.attenuation_shape_extents=u.Vector(120,0,0);settings.falloff_distance=2400.0
attenuation.set_editor_property('attenuation',settings);save(attenuation)
concurrency=asset('SC_Footsteps',u.SoundConcurrency,u.SoundConcurrencyFactory())
settings=concurrency.get_editor_property('concurrency');settings.set_editor_property('max_count',4);settings.set_editor_property('limit_to_owner',True)
concurrency.set_editor_property('concurrency',settings);save(concurrency)
factory=u.DataAssetFactory();factory.set_editor_property('data_asset_class',u.CRFootstepProfile)
profile=asset('DA_Footsteps',u.CRFootstepProfile,factory)
profile.set_editor_property('surfaces',rows);profile.set_editor_property('attenuation',attenuation);profile.set_editor_property('concurrency',concurrency);save(profile)
bp=u.load_asset('/Game/Blueprints/SandboxCharacter_CMC')
cdo=u.get_default_object(bp.generated_class());cdo.footsteps.set_editor_property('profile',profile)
u.BlueprintEditorLibrary.compile_blueprint(bp);assert not u.CRBlueprintTools.has_blueprint_errors(bp);save(bp)
foley=u.load_asset('/Game/Audio/Foley/AC_FoleyEvents')
assert u.CRBlueprintTools.configure_footstep_events(foley)
u.BlueprintEditorLibrary.compile_blueprint(foley);assert not u.CRBlueprintTools.has_blueprint_errors(foley);save(foley)
(ROOT/'resources/FootstepSurfaces.json').write_text(json.dumps(dict(profile=profile.get_path_name(),unique_samples=len(all_waves),surfaces=report),indent=2))
print('FOOTSTEPS_CONFIGURED',len(rows),'surfaces',len(all_waves),'unique samples')
