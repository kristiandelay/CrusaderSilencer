"""Ten real PIE start/stop cycles, checking Lyra ownership and duplicate components."""
restart_state = {'phase': 'start', 'next': time.monotonic()+1, 'results': [], 'busy': False}
restart_out = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/GymTests/restarts.json'
restart_out.parent.mkdir(parents=True,exist_ok=True)

def restart_finish(error=None):
    u.unregister_slate_post_tick_callback(restart_state['handle'])
    report = {'passed': error is None and len(restart_state['results']) == 10,
              'error': error, 'cycles': restart_state['results']}
    restart_out.write_text(json.dumps(report, indent=2))
    u.log('CR_GYM_RESTART_RESULT '+json.dumps(report))

def restart_tick(dt):
    now = time.monotonic()
    if restart_state['busy'] or now < restart_state['next']:
        return
    restart_state['busy'] = True
    try:
        levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
        worlds = u.EditorLevelLibrary.get_pie_worlds(False)
        if restart_state['phase'] == 'start':
            assert not worlds
            levels.editor_request_begin_play()
            restart_state.update(phase='verify', next=now+3, deadline=now+45)
        elif restart_state['phase'] == 'verify':
            pawns = [u.GameplayStatics.get_player_pawn(w,0) for w in worlds]
            pawns = [p for p in pawns if p]
            if not pawns:
                assert now < restart_state['deadline'], 'No player spawned'
                return
            assert len(pawns) == 1
            pawn = pawns[0]
            assert isinstance(pawn, u.LyraCharacter)
            assert isinstance(pawn.character_movement, u.BaselineCharacterMovement)
            assert len(pawn.get_components_by_class(u.CharacterMovementComponent)) == 1
            assert len(pawn.get_components_by_class(u.LyraHeroComponent)) == 1
            assert len(pawn.get_components_by_class(u.LyraEquipmentManagerComponent)) == 1
            assert len(pawn.get_controller().get_components_by_class(u.LyraInventoryManagerComponent)) == 1
            assert len(pawn.get_controller().get_components_by_class(u.LyraQuickBarComponent)) == 1
            cameras = [c for c in pawn.get_components_by_class(u.CameraComponent) if c.is_active()]
            assert len(cameras) == 1 and isinstance(cameras[0],u.LyraCameraComponent), str(cameras)
            ps = pawn.get_controller().player_state
            systems = ps.get_components_by_class(u.LyraAbilitySystemComponent)
            assert len(systems) == 1
            extension = pawn.get_component_by_class(u.LyraPawnExtensionComponent)
            assert extension.get_lyra_ability_system_component() == systems[0]
            assert pawn.get_lyra_ability_system_component() == systems[0]
            assert not pawn.get_components_by_class(u.LyraAbilitySystemComponent)
            assert pawn.mesh.get_anim_instance().get_class().get_name() == 'SandboxCharacter_CMC_ABP_C'
            visual_meshes = [m for a in pawn.get_attached_actors() for m in a.get_components_by_class(u.SkeletalMeshComponent) if m.is_visible()]
            assert len(visual_meshes) == 1
            assert visual_meshes[0].get_skinned_asset().get_path_name() == '/Game/Characters/Heroes/Mannequin/Meshes/SKM_Manny.SKM_Manny'
            assert visual_meshes[0].get_anim_instance()
            assert pawn.character_movement.movement_mode == u.MovementMode.MOVE_WALKING
            subs = [s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0) == pawn.get_controller()]
            assert len(subs) == 1
            assert subs[0].query_keys_mapped_to_action(u.load_asset('/Game/Input/IA_Jump'))
            restart_state['results'].append({'cycle':len(restart_state['results'])+1,'pawn':pawn.get_class().get_path_name(), 'active_camera':cameras[0].get_class().get_name(), 'ability_owner':ps.get_class().get_name(), 'visual_mesh':visual_meshes[0].get_skinned_asset().get_path_name()})
            levels.editor_request_end_play()
            restart_state.update(phase='stopped',next=now+2,deadline=now+30)
        elif restart_state['phase'] == 'stopped':
            if worlds:
                assert now < restart_state['deadline'], 'Play world did not stop'
                return
            if len(restart_state['results']) == 10:
                restart_finish()
            else:
                restart_state.update(phase='start',next=now+.2)
    except Exception:
        restart_finish(traceback.format_exc())
    finally:
        restart_state['busy'] = False

restart_state['handle'] = u.register_slate_post_tick_callback(restart_tick)
print('Started ten Play start/stop cycles')
