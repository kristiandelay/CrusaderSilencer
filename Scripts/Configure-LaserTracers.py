"""Apply the Fab demo's Laser Trace 5 to existing player and guard profiles."""
import unreal as u

assert not u.EditorLevelLibrary.get_pie_worlds(False)
# WP_Tracers_Items: Button_8 / TextBlock_11 ("Laser Trace 5") selects Red_2.
laser=u.load_asset('/Game/Bullet_Tracers_Fx/VFX/Lasers/NS_Laser_Trace_Red_2')
assert laser,'Add Bullet Tracers & Trails Fx Pack through Fab first'
for kind in ['Rifle','Pistol','Shotgun']:
    profile=u.load_asset('/Game/Crusader/Effects/FX_'+kind)
    assert profile,kind
    profile.set_editor_property('bullet_trail',laser)
    profile.set_editor_property('movement_driven_trail',True)
    profile.set_editor_property('trail_speed',18000.0)
    profile.set_editor_property('trail_particle_lifetime',.035)
    profile.set_editor_property('shell_ejection',None)
    assert u.EditorAssetLibrary.save_loaded_asset(profile,only_if_is_dirty=False)
    instance=u.load_asset(f'/Game/Baseline/Weapons/{kind}/B_WeaponInstance_{kind}')
    assert u.get_default_object(instance.generated_class()).effects_profile==profile
    print('LASER_TRACER_5_CONFIGURED',kind,laser.get_path_name())
