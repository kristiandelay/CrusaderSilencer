"""Install ThrowSystem assets on the existing GASP pawn, without demo input/game modes."""
import json
from pathlib import Path
import unreal as u
th_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
th_lib=u.EditorAssetLibrary;th_tools=u.AssetToolsHelpers.get_asset_tools()
th_folder='/Game/Crusader/Equipment/Throw'
def th_save(a):
    if isinstance(a,u.Blueprint):
        u.BlueprintEditorLibrary.compile_blueprint(a);assert not u.CRBlueprintTools.has_blueprint_errors(a),a.get_path_name()
    assert th_lib.save_loaded_asset(a,only_if_is_dirty=False)
def th_key(name):
    k=u.Key();assert k.import_text(name);return k
# Keep the throw above the full-body slot so walking and slide legs continue.
th_animation=u.load_asset('/Game/Blueprints/SandboxCharacter_CMC_ABP')
assert u.CRBlueprintTools.configure_throw_upper_body(th_animation)
th_save(th_animation)
th_save(th_animation.get_editor_property('target_skeleton'))
for name in ['AM_Aim','AM_Throw','AM_Left_Aim','AM_Left_Throw']:
    montage=u.load_asset(th_folder+'/'+name)
    tracks=montage.get_editor_property('slot_anim_tracks')
    assert len(tracks)==1,name
    # Unreal returns struct array elements by value. Write the edited element
    # back into the array, otherwise saving silently retains DefaultSlot.
    track=tracks[0];track.set_editor_property('slot_name','ThrowUpperBody');tracks[0]=track
    montage.set_editor_property('slot_anim_tracks',tracks)
    assert str(montage.get_editor_property('slot_anim_tracks')[0].get_editor_property('slot_name'))=='ThrowUpperBody',name
    th_save(montage)
th_arc_path=th_folder+'/M_ThrowTrajectory'
th_arc=u.load_asset(th_arc_path) if th_lib.does_asset_exist(th_arc_path) else th_lib.duplicate_asset('/Game/ThrowSystem/Materials/M_Projectile',th_arc_path)
u.MaterialEditingLibrary.set_material_usage(th_arc,u.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
u.MaterialEditingLibrary.recompile_material(th_arc);th_save(th_arc)
th_smoke_path=th_folder+'/P_GameplaySmoke'
th_smoke=u.load_asset(th_smoke_path) if th_lib.does_asset_exist(th_smoke_path) else th_lib.duplicate_asset('/Game/ThrowSystem/Demo/Particles/P_Steam_Lit',th_smoke_path)
# Smoke affects sight, so low effects settings must not remove the visible cloud.
for suffix in ['0','10']:
    spawn=u.load_object(None,th_smoke.get_path_name()+':ParticleModuleSpawn_'+suffix)
    assert u.CRBlueprintTools.set_property_text(spawn,'bApplyGlobalSpawnRateScale','False')
    distribution=u.load_object(None,spawn.get_path_name()+'.RequiredDistributionSpawnRate')
    assert u.CRBlueprintTools.set_property_text(distribution,'Constant','8.0')
    rate='(MinValue=8.0,MaxValue=8.0,Distribution="'+distribution.get_path_name()+'",Table=(TimeScale=0,TimeBias=0,Values=(8.0),Op=1,EntryCount=1,EntryStride=1,SubEntryStride=0,LockFlag=0))'
    assert u.CRBlueprintTools.set_property_text(spawn,'Rate',rate)
th_save(th_smoke)
path=th_folder+'/B_ThrownObject'
if th_lib.does_asset_exist(path):th_projectile=u.load_asset(path)
else:
    f=u.BlueprintFactory();f.set_editor_property('parent_class',u.CRThrownObject.static_class())
    th_projectile=th_tools.create_asset('B_ThrownObject',th_folder,u.Blueprint,f)
th_defaults=u.get_default_object(th_projectile.generated_class())
th_defaults.set_editor_properties(dict(
    grenade_mesh=u.load_asset('/Game/ThrowSystem/Meshes/SM_Grenade'),smoke_mesh=u.load_asset('/Game/ThrowSystem/Meshes/SM_Smoke'),
    explosion_effect=u.load_asset('/Game/ThrowSystem/Demo/Particles/P_Explosion'),smoke_effect=th_smoke,
    explosion_sound=u.load_asset('/Game/Audio/Sounds/Explosions/Explosions_Grenade_SFX_01'),
    bounce_sound=u.load_asset('/Game/Audio/Sounds/Explosions/Explosions_Grenade_Ricochet_01'),
    damage_effect=u.load_asset('/Game/GameplayEffects/Damage/GE_Damage_Basic_SetByCaller').generated_class()))
th_save(th_projectile)
for path in ['/Game/Blueprints/SandboxCharacter_CMC','/Game/Crusader/Characters/B_CRTraversalPawn']:
    bp=u.load_asset(path);c=u.get_default_object(bp.generated_class()).throwable
    grip=u.Transform();assert grip.import_text(json.loads((th_root/'resources/ThrowShoulderAnimations.json').read_text())['left_grip'])
    c.set_editor_properties(dict(projectile_class=th_projectile.generated_class(),aim_animation=u.load_asset(th_folder+'/Animations/GASP_AS_Aim'),
        left_aim_animation=u.load_asset(th_folder+'/Animations/GASP_Left_AS_Aim'),left_throw_montage=u.load_asset(th_folder+'/AM_Left_Throw'),left_hand_grip=grip,
        throw_montage=u.load_asset(th_folder+'/AM_Throw'),trajectory_material=th_arc,
        landing_material=u.load_asset('/Game/ThrowSystem/Materials/M_Decale'),trajectory_mesh=u.load_asset('/Engine/BasicShapes/Cylinder')))
    th_save(bp)
for role in ['GuardRifle','GuardPistol','GuardShotgun','Civilian']:th_save(u.load_asset('/Game/Crusader/AI/B_'+role))
mapping=u.load_asset('/Game/Baseline/Input/IMC_Baseline')
for name,keys in [('Throw',['H']),('ThrowType',['X']),('ThrowCancel',['Z'])]:
    path='/Game/Baseline/Input/IA_'+name
    a=u.load_asset(path) if th_lib.does_asset_exist(path) else th_tools.create_asset('IA_'+name,'/Game/Baseline/Input',u.InputAction,u.InputAction_Factory())
    a.set_editor_property('value_type',u.InputActionValueType.BOOLEAN);a.set_editor_property('triggers',[]);th_save(a)
    mapping.unmap_all_keys_from_action(a)
    for key in keys:mapping.map_key(a,th_key(key))
th_save(mapping)
th_report=dict(pack='https://www.fab.com/listings/c0bb75a3-c87b-436b-b965-b74632cca916',projectile=th_projectile.get_path_name(),
    controls={'hold_release':'H','type':'X','cancel':'Z','shoulder_hand':'Q (also while aiming)'},grenades=6,smoke_grenades=6,
    throw_hand='Selected shoulder: mirrored aim/release/grip and launch origin; hand locked during release.',
    movement='Walk, strafe or slide while aiming and releasing; upper-body throw over GASP locomotion/slide. Release origin follows current position.',
    grenade_fuse_seconds=3,smoke_fuse_seconds=1.3,smoke_duration_seconds=12,blast_radius_cm=550,smoke_radius_cm=450,
    preview='Predicted first impact using projectile gravity and collision radius; released objects bounce.',release_notify_seconds=.168179)
(th_root/'resources/ThrowSystem.json').write_text(json.dumps(th_report,indent=2)+'\n')
print('THROW_CONFIGURED',th_report)
