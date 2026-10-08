"""Reusable, labeled Chaos destruction fixtures west of the surface firing range."""
import json
from pathlib import Path
import unreal as u

assert not u.EditorLevelLibrary.get_pie_worlds(False)
dr_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
dr_actors=u.get_editor_subsystem(u.EditorActorSubsystem)
assert u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world().get_name()=='L_TraversalGym'
dr_old={a.get_actor_label():a for a in dr_actors.get_all_level_actors() if a.get_actor_label().startswith('CR_Destruction_')}
dr_used=set()
dr_cube=u.load_asset('/Engine/BasicShapes/Cube')
dr_mats={n:u.load_asset('/Game/Crusader/Effects/Range/M_'+n) for n in ['RangeFloor','RangeFrame','FiringLine']}
dr_class=u.load_class(None,'/Game/Crusader/Destruction/B_CRDestructible.B_CRDestructible_C')
assert dr_class and all(dr_mats.values())
dr_records=[]

def dr_actor(cls,name,position,rotation=None):
    label='CR_Destruction_'+name
    a=dr_old.get(label) or dr_actors.spawn_actor_from_class(cls,u.Vector(*position),rotation or u.Rotator())
    a.set_actor_label(label);a.set_folder_path('Crusader/Destruction Range')
    a.tags=['CrusaderDestructionRange'];a.set_actor_location(u.Vector(*position),False,True)
    a.set_actor_rotation(rotation or u.Rotator(),False);dr_used.add(label)
    return a

def dr_box(name,pos,size,material='RangeFrame'):
    a=dr_actor(u.StaticMeshActor,name,pos);c=a.static_mesh_component
    c.set_static_mesh(dr_cube);c.set_material(0,dr_mats[material]);c.set_collision_profile_name('BlockAll')
    a.set_actor_scale3d(u.Vector(*(v/100 for v in size)))
    return a

def dr_sign(name,text,pos,size=30):
    a=dr_actor(u.TextRenderActor,name,pos,u.Rotator(yaw=90))
    a.text_render.set_text(text);a.text_render.set_world_size(size)
    a.text_render.set_horizontal_alignment(u.HorizTextAligment.EHTA_CENTER)
    a.text_render.set_text_render_color(u.Color(235,230,205,255))
    return a

def dr_target(name,preset,x,y,lift=0,scale=1.,section='Targets'):
    data=u.load_asset('/Game/NextGenDestruction/Blueprints/DataAssets/Destructible/'+preset)
    assert data,preset
    a=dr_actor(dr_class,name,(x,y,lift))
    a.set_editor_property('DataAsset',data)
    a.set_actor_scale3d(u.Vector(scale,scale,scale))
    if preset in ['DA_Wall_Wood','DA_Wall_Plaster','DA_Wall_WoodenBeams']:
        a.set_actor_rotation(u.Rotator(yaw=90),False)
    gc=a.get_destructible_geometry();assert gc and gc.rest_collection,name
    # These fixtures are outside the crowd district. Do not export hundreds
    # of thousands of fracture triangles to the dynamic navigation mesh.
    assert u.CRBlueprintTools.set_property_text(gc,'bCanEverAffectNavigation','False')
    center,extent=a.get_actor_bounds(False)
    # Source kit pivots vary. Put the bottom on the slab/pedestal, and centre
    # the complete object including its optional non-breakable metal frame.
    loc=a.get_actor_location()+u.Vector(x-center.x,y-center.y,lift-(center.z-extent.z)+7)
    a.set_actor_location(loc,False,True)
    a.set_folder_path('Crusader/Destruction Range/'+section)
    center,extent=a.get_actor_bounds(False)
    dr_sign(name+'_Label',name.replace('_',' ').upper(),(x,y+260,max(95,center.z+extent.z+45)),25)
    box=gc.get_local_bounds()
    local_aim=(box.min+box.max)*.5
    if preset in ['DA_CoffeeTable_Wood','DA_DiningTable_Wood']:
        local_aim.z=box.max.z-2. # aim at the tabletop, not empty space between its legs
    aim=u.MathLibrary.transform_location(gc.get_world_transform(),local_aim)
    dr_records.append(dict(name=name,actor=a.get_actor_label(),preset=preset,section=section,
                           position=[loc.x,loc.y,loc.z],target=[aim.x,aim.y,aim.z],standing=[x,y+(350 if 'Mug' in name else 1000),100],
                           geometry=gc.rest_collection.get_path_name()))
    return a

dr_box('Floor',(-4300,-6650,-15),(6500,5900,40),'RangeFloor')
dr_box('Backstop',(-4300,-9550,310),(6500,45,620))
dr_sign('Title','DESTRUCTION TEST RANGE',(-4300,-9480,690),62)
dr_sign('Instructions','FIRE TO FRACTURE  /  H: GRENADE  /  X: TYPE\nRestart Play to restore all targets',(-4300,-9440,585),30)
dr_sign('Entry','DESTRUCTION RANGE\nConcrete / wood / glass / ceramics',(-4300,-3810,300),44)
dr_sign('Directions','DESTRUCTION RANGE\nWest of surface range',(-350,-4330,240),31)
for name,y in [('Front',-4240),('Middle',-6860),('Blast',-8280)]:
    dr_box(name+'_Line',(-4300,y,6),(6200,7,2),'FiringLine')

dr_front=[('Concrete_Pillar','DA_Pillar_Small_Concrete'),('Concrete_5m','DA_Pillar_Large_Concrete_Square'),
          ('Concrete_LowCost','DA_Pillar_Small_Concrete_Simplified'),('Wood_Wall','DA_Wall_Wood'),
          ('Plaster_Wall','DA_Wall_Plaster'),('Wood_Beams','DA_Wall_WoodenBeams'),
          ('Tall_Window','DA_Window_Large'),('Small_Window','DA_Window_Small')]
for i,(name,preset) in enumerate(dr_front):dr_target(name,preset,-7100+i*800,-5400)
dr_rear=[('Wood_Chair','DA_Chair_Wood'),('Coffee_Table','DA_CoffeeTable_Wood'),('Wood_Desk','DA_Desk_Wood'),
         ('Dining_Table','DA_DiningTable_Wood'),('Ceramic_Vase','DA_Vase'),('Ceramic_Mug_1','DA_Mug01'),('Ceramic_Mug_2','DA_Mug02')]
for i,(name,preset) in enumerate(dr_rear):
    x=-6900+i*870;lift=90 if i>=4 else 0
    if lift:dr_box(name+'_Pedestal',(x,-7720,45),(180,180,90))
    dr_target(name,preset,x,-7720,lift=lift,scale=2. if 'Mug' in name else 1.)
for i,(name,preset,x,y) in enumerate([('Blast_Chair','DA_Chair_Wood',-4850,-8930),
                                    ('Blast_Table','DA_CoffeeTable_Wood',-4530,-8850),
                                    ('Blast_Vase','DA_Vase',-4230,-8930),
                                    ('Blast_Pillar','DA_Pillar_Small_Concrete',-3900,-8930)]):
    dr_target(name,preset,x,y,section='Grenade Bay')
dr_sign('Blast_Label','GRENADE BAY',(-4500,-8570,340),36)

for kind,model,x in [('Rifle','BlackIronRifle',-5100),('Pistol','FuturisticPistol',-4600),('Shotgun','TitanBreaker',-4100)]:
    path='/Game/Crusader/Weapons/BlackIronRifle/ID_BlackIronRifle' if kind=='Rifle' else f'/Game/Baseline/Weapons/{kind}/ID_{kind}'
    a=dr_actor(u.BaselineWeaponPickup,'Pickup_'+kind,(x,-3960,55))
    a.set_editor_property('item_definition',u.load_asset(path).generated_class())
    a.display_mesh.set_skeletal_mesh_asset(u.load_asset(f'/Game/Crusader/Weapons/{model}/{model}'))
    a.display_mesh.set_material(0,u.load_asset(f'/Game/Crusader/Weapons/{model}/M_{model}'))
    dr_sign('PickupLabel_'+kind,kind.upper()+' / E',(x,-3960,120),25)

for name in ['Concrete','Wood']:
    a=dr_actor(u.NiagaraActor,'DebrisFX_'+name,(-4300,-6650,100))
    c=a.get_component_by_class(u.NiagaraComponent)
    c.set_asset(u.load_asset('/Game/NextGenDestruction/FX/Destruction/GlobalDI/NS_Chaos_DI_'+name))

for label,a in dr_old.items():
    if label not in dr_used:dr_actors.destroy_actor(a)
assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
(dr_root/'resources/DestructionRange.json').write_text(json.dumps(dict(map='/Game/Maps/L_TraversalGym',
    blueprint='/Game/Crusader/Destruction/B_CRDestructible',origin=[-4300,-6650,0],targets=dr_records,
    source='https://www.fab.com/listings/9990252b-cfef-4b64-b99e-89e489e5b16b'),indent=2))
print('DESTRUCTION_RANGE_BUILT',len(dr_records),'targets')
