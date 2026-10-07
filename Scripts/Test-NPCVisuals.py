"""Exercise all four new entries through actual widget clicks and both shoulders."""
from pathlib import Path
import unreal as u

npc_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
source=(npc_root/'Scripts/Test-VisualOverrides.py').read_text()
source=source.replace("visual_test['capture']=u.AutomationLibrary.take_high_res_screenshot(1280,800,str(visual_out/(visual_names[visual_test['index']]+suffix+'.png')),delay=0)","npc_capture(pawn,visual_names[visual_test['index']]+suffix)")
exec(compile(source,'Test-VisualOverrides.py','exec'),globals())
visual_test['index']=7
visual_out=npc_root/'Artifacts/NPCCharacters'

def npc_capture(pawn,name):
    world=u.EditorLevelLibrary.get_pie_worlds(False)[0]
    feet=pawn.get_actor_location()-u.Vector(0,0,94)
    forward=pawn.get_actor_forward_vector();right=pawn.get_actor_right_vector()
    location=feet+forward*300+right*220+u.Vector(0,0,160)
    actor=u.CRBlueprintTools.spawn_pie_test_actor(world,u.SceneCapture2D,u.Transform(location=location))
    actor.set_actor_rotation(u.MathLibrary.find_look_at_rotation(location,feet+u.Vector(0,0,105)),False)
    component=actor.get_component_by_class(u.SceneCaptureComponent2D)
    component.set_editor_property('capture_every_frame',False);component.set_editor_property('capture_on_movement',False)
    component.set_editor_property('fov_angle',43);component.set_editor_property('capture_source',u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    target=u.RenderingLibrary.create_render_target2d(world,1200,1200,u.TextureRenderTargetFormat.RTF_RGBA8)
    component.set_editor_property('texture_target',target);component.capture_scene()
    u.RenderingLibrary.export_render_target(world,target,str(visual_out),name+'.png');actor.destroy_actor()
