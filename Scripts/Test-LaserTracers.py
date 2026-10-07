"""Fire every weapon from both shoulders, check laser travel, misses and cleanup."""
from pathlib import Path
import unreal as u

lt_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
(lt_root/'Artifacts/LaserTracer').mkdir(parents=True,exist_ok=True)
lt_source=(lt_root/'Scripts/Test-WeaponEffects.py').read_text().replace('Artifacts/WeaponFX/gameplay-validation.json','Artifacts/LaserTracer/player.json')
exec(compile(lt_source,'Test-WeaponEffects.py','exec'),globals())
fx_cases=[dict(weapon=kind,target=fx_targets[index],left=left) for kind,index in [('Pistol',0),('Rifle',2),('Shotgun',3)] for left in [False,True]]
fx_cases += [dict(weapon=kind,target=None,left=False) for kind in ['Pistol','Rifle','Shotgun']]
lt_asset=u.load_asset('/Game/Bullet_Tracers_Fx/VFX/Lasers/NS_Laser_Trace_Red_2')
lt_samples={};lt_original_tick=fx_tick;lt_original_finish=fx_finish

def lt_vector(value):return [value.x,value.y,value.z]

def fx_finish(error=None):
    if error:lt_original_finish(error)
    else:fx_test.update(phase='laser_cleanup',next=0)

def lt_tick(dt):
    try:
        w=u.EditorLevelLibrary.get_pie_worlds(False)[0]
        p=u.GameplayStatics.get_player_pawn(w,0)
        now=u.GameplayStatics.get_time_seconds(w)
        if fx_test['phase']=='laser_cleanup':
            if not fx_test['next']:fx_test['next']=now+2.5
            if now<fx_test['next']:return
            assert p.weapon_effects.get_active_trail_count()==0,'Laser components leaked after firing'
            assert lt_samples,'No moving laser components observed'
            assert any(row['distance']>50 for row in lt_samples.values()),'Lasers did not move'
            fx_test['results'].append(dict(case='moving_sources_stop_at_hit_and_cleanup',sources=len(lt_samples),moving_sources=sum(row['distance']>1 for row in lt_samples.values()),active_after_fade=0))
            lt_original_finish();return
        old_index=fx_test['index']
        lt_original_tick(dt)
        if fx_test.get('finished') or fx_test['phase']=='laser_cleanup':return
        if old_index!=fx_test['index']:
            assert p.weapon_effects.last_profile.bullet_trail==lt_asset
            assert p.weapon_effects.last_profile.movement_driven_trail
        if fx_test['phase']!='check' or p.weapon_effects.shots_played<=fx_test.get('before_shots',0):return
        hits=p.weapon_effects.last_impacts
        for c in u.ObjectIterator(u.NiagaraComponent):
            if c.get_asset()!=lt_asset or 'UEDPIE_' not in c.get_path_name():continue
            location=c.get_world_location();direction=c.get_forward_vector()
            # A ribbon source lies on exactly one pellet ray, even in a spread.
            def residual(hit):
                delta=hit.position-location
                dot=sum(a*b for a,b in zip(lt_vector(delta),lt_vector(direction)))
                return (delta-direction*dot).length()
            hit=min(hits,key=residual)
            if residual(hit)>3:continue
            delta=hit.position-location
            ahead=sum(a*b for a,b in zip(lt_vector(delta),lt_vector(direction)))
            assert ahead>=-1.5,('Laser source crossed its endpoint',ahead)
            key=c.get_path_name();row=lt_samples.get(key)
            if row:row['distance']+=(location-u.Vector(*row['last'])).length();row['last']=lt_vector(location)
            else:lt_samples[key]=dict(last=lt_vector(location),distance=0)
    except Exception:lt_original_finish(traceback.format_exc())

u.unregister_slate_post_tick_callback(fx_test['handle'])
fx_test['handle']=u.register_slate_post_tick_callback(lt_tick)
