# Runs inside Unreal. Diagnose the dashed sky lines: capture the player shot with scatter hidden,
# then with the terrain hidden too, then restore visibility.
import unreal
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
OUT = "C:/Users/nickl/Documents/env-lab/build/snaps/e1"
acts = eas.get_all_level_actors()
scatter = [a for a in acts if a.get_actor_label().startswith("Scatter_")]
terrain = [a for a in acts if a.get_actor_label() == "Terrain_E1"]

def cap(name):
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1600, 900, unreal.TextureRenderTargetFormat.RTF_RGBA8, unreal.LinearColor(0,0,0,1), False)
    c = eas.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(0, 700, 1150))
    c.set_actor_rotation(unreal.Rotator(pitch=-1, yaw=90, roll=0), False)
    comp = c.get_component_by_class(unreal.SceneCaptureComponent2D)
    comp.set_editor_property("texture_target", rt)
    comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    comp.set_editor_property("fov_angle", 75.0)
    comp.capture_scene()
    unreal.RenderingLibrary.export_render_target(world, rt, OUT, name + ".png")
    c.destroy_actor()
    print("DIAG_WRITTEN " + name)

for a in scatter: a.set_is_temporarily_hidden_in_editor(True)
cap("_diag_noscatter")
for a in terrain: a.set_is_temporarily_hidden_in_editor(True)
cap("_diag_noscatter_noterrain")
for a in scatter + terrain: a.set_is_temporarily_hidden_in_editor(False)
print("DIAG_DONE")
