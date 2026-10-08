"""Run the roll replication fixture while checking the evaluated knees on every view."""
from pathlib import Path
import unreal as u
rln_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
# Load the shared pose evaluator, without starting the standalone capture fixture.
exec((rln_root/'Scripts/Test-RollLegs.py').read_text().split('rlv_test=dict(')[0],globals())
exec((rln_root/'Scripts/Test-RollNetwork.py').read_text(),globals())
rln_samples={}
rln_original_finish=rn_finish
def rln_tick(dt):
    if rn_test.get('finished'):return
    try:
        roles=rn_context()
        for role,p in enumerate(roles):
            if not p.roll.is_rolling():continue
            anim=p.mesh.get_anim_instance();montage=anim.get_current_active_montage()
            if montage and .34<anim.montage_get_position(montage)<.66:
                sample=rlv_measure(p);key=str(role)+'_'+str(p.roll.active_direction)
                entry=rln_samples.setdefault(key,dict(role=role,direction=p.roll.active_direction,samples=0,maximum_source_error=0,maximum_visible_error=0))
                entry['samples']+=1
                entry['maximum_source_error']=max(entry['maximum_source_error'],sample['source_error'])
                entry['maximum_visible_error']=max(entry['maximum_visible_error'],sample['visible_error'])
    except StopIteration:pass
    except Exception:rn_finish(traceback.format_exc())
rln_handle=u.register_slate_post_tick_callback(rln_tick)
def rn_finish(error=None):
    u.unregister_slate_post_tick_callback(rln_handle)
    if error is None and len(rln_samples)!=32:error='Missing network leg poses: '+str(sorted(rln_samples))
    (rln_root/'Artifacts/Roll/Legs/network.json').write_text(json.dumps(dict(passed=error is None,error=error,results=list(rln_samples.values())),indent=2)+'\n')
    rln_original_finish(error)
