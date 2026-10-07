worlds = u.EditorLevelLibrary.get_pie_worlds(False)
print('PIE worlds', len(worlds))
for world in worlds:
    pawn = u.GameplayStatics.get_player_pawn(world, 0)
    print('game mode', u.GameplayStatics.get_game_mode(world))
    print('pawn', pawn)
    if not pawn:
        continue
    print('Lyra character', isinstance(pawn, u.LyraCharacter))
    print('location', pawn.get_actor_location(), 'velocity', pawn.get_velocity())
    print('movement', pawn.character_movement.get_class().get_path_name())
    print('controller', pawn.get_controller().get_class().get_path_name())
    asc = pawn.get_controller().player_state.get_component_by_class(u.LyraAbilitySystemComponent)
    print('ability system', asc, 'owner', asc.get_owner() if asc else None)
    print('source animation', pawn.mesh.get_anim_instance())
    print('source mesh', pawn.mesh.get_skinned_asset(), 'visible', pawn.mesh.is_visible())
    for component in pawn.get_components_by_class(u.ActorComponent):
        print('component', component.get_name(), component.get_class().get_name())
    for child in pawn.get_attached_actors():
        for mesh in child.get_components_by_class(u.SkeletalMeshComponent):
            print('visual', child, mesh.get_skinned_asset(), mesh.get_anim_instance(), 'visible', mesh.is_visible())
    for sub in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem):
        if not isinstance(sub.get_outer(), u.LocalPlayer):
            continue
        for name in ['IA_Move', 'IA_Jump', 'IA_Traverse', 'IA_Crouch', 'IA_Sprint']:
            action = u.load_asset('/Game/Input/' + name)
            print('input', name, [str(key) for key in sub.query_keys_mapped_to_action(action)])
