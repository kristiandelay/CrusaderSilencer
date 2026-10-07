#include "CRTraversalCharacter.h"
#include "CRWeaponEffects.h"
#include "CRFootsteps.h"
#include "CRCrowdAI.h"
#include "UObject/StructOnScope.h"
#include "UObject/UnrealType.h"
#include "InputMappingContext.h"
#include "Kismet/GameplayStatics.h"
#include "Camera/CameraComponent.h"
#include "Camera/LyraCameraComponent.h"
#include "Baseline/BaselineCharacterMovement.h"
#include "Baseline/BaselineEquipment.h"
#include "Equipment/LyraEquipmentManagerComponent.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/ChildActorComponent.h"
#include "EnhancedInputComponent.h"
#include "InputAction.h"
#include "Baseline/BaselinePhysicalInteraction.h"
#include "PhysicsControlComponent.h"
#include "Character/LyraHealthComponent.h"
#include "Player/LyraPlayerState.h"
#include "AbilitySystem/LyraAbilitySystemComponent.h"
#include "TimerManager.h"

ACRTraversalCharacter::ACRTraversalCharacter(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer.SetDefaultSubobjectClass<UBaselineCharacterMovement>(ACharacter::CharacterMovementComponentName))
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bStartWithTickEnabled = true;
    bUseControllerRotationYaw = false;
    HeroComponent = CreateDefaultSubobject<UCRTraversalHeroComponent>(TEXT("HeroComponent"));
    EquipmentManager = CreateDefaultSubobject<ULyraEquipmentManagerComponent>(TEXT("EquipmentManager"));
    BaselineEquipment = CreateDefaultSubobject<UBaselineEquipmentComponent>(TEXT("BaselineEquipment"));
    WeaponEffects = CreateDefaultSubobject<UCRWeaponEffectsComponent>(TEXT("WeaponEffects"));
    Footsteps = CreateDefaultSubobject<UCRFootstepComponent>(TEXT("Footsteps"));
    CrowdAgent = CreateDefaultSubobject<UCRCrowdAgentComponent>(TEXT("CrowdAgent"));
    PhysicsControl = CreateDefaultSubobject<UPhysicsControlComponent>(TEXT("PhysicsControl"));
    PhysicalInteraction = CreateDefaultSubobject<UBaselinePhysicalInteractionComponent>(TEXT("PhysicalInteraction"));
    SelectedVisualOverride = CreateDefaultSubobject<UChildActorComponent>(TEXT("SelectedVisualOverride"));
    SelectedVisualOverride->SetupAttachment(GetMesh());
    SelectedVisualOverride->ComponentTags.Add(TEXT("VisualOverride"));
}

FPoseSearchBlueprintResult ACRTraversalCharacter::GetPhysicalInteractionResult() const
{
    return PhysicalInteraction->GetInteractionResult();
}

void ACRTraversalCharacter::OnMovementModeChanged(EMovementMode PreviousMovementMode, uint8 PreviousCustomMode)
{
    Super::OnMovementModeChanged(PreviousMovementMode, PreviousCustomMode);
    if (PreviousMovementMode == MOVE_Falling && GetCharacterMovement()->IsMovingOnGround() && Footsteps)
        Footsteps->GroundContact();
}

bool ACRTraversalCharacter::CanUseMovementActions() const
{
    const auto* Health = ULyraHealthComponent::FindHealthComponent(this);
    return !PhysicalInteraction->IsBusy() && (!Health || !Health->IsDeadOrDying());
}

void ACRTraversalCharacter::OnAbilitySystemInitialized()
{
    Super::OnAbilitySystemInitialized();
    if (HasAuthority())
        if (auto* State = GetLyraPlayerState(); State && State->GetGenericTeamId() == FGenericTeamId::NoTeam)
            State->SetGenericTeamId(FGenericTeamId(PhysicalInteraction->bAutoRecover ? 1 : 0));
}

void ACRTraversalCharacter::OnDeathStarted(AActor* OwningActor)
{
    const FVector Momentum = GetVelocity();
    Super::OnDeathStarted(OwningActor);
    if (auto* ASC = GetLyraAbilitySystemComponent()) ASC->ClearAbilityInput();
    BaselineEquipment->HandleDeath();
    PhysicalInteraction->StartDeathRagdoll(Momentum);
}

void ACRTraversalCharacter::OnDeathFinished(AActor* OwningActor)
{
    // End the death ability before tearing down its avatar. Keep cleanup and
    // restart sequential: independent next-tick timers can run in either order.
    GetWorld()->GetTimerManager().SetTimerForNextTick(this, &ThisClass::FinishCombatDeath);
}

bool ACRTraversalCharacter::RequestAITraversal()
{
    if (!HasAuthority() || !CanUseMovementActions() || BaselineEquipment->AreHandsBusy()) return false;
    // Call the same GASP check/selection path as Space. Its input struct is a
    // content-defined type, so copy reflected parameters without duplicating it.
    auto Find = [](UObject* Object, const TCHAR* Name) -> UFunction*
    {
        for (TFieldIterator<UFunction> It(Object->GetClass()); It; ++It)
            if (It->GetName().Replace(TEXT("_"),TEXT("")).Replace(TEXT(" "),TEXT("")) == Name) return *It;
        return nullptr;
    };
    UFunction* InputsFunction = Find(this,TEXT("GetTraversalCheckInputs"));
    if (!InputsFunction) return false;
    FStructOnScope InputParams(InputsFunction);
    ProcessEvent(InputsFunction, InputParams.GetStructMemory());
    FStructProperty* Output = nullptr;
    for (TFieldIterator<FStructProperty> It(InputsFunction); It; ++It)
        if (It->HasAnyPropertyFlags(CPF_OutParm|CPF_ReturnParm)) { Output=*It; break; }
    if (!Output) return false;
    for (UActorComponent* Component : GetComponents())
    {
        UFunction* Action = Find(Component,TEXT("TryTraversalAction"));
        if (!Action) continue;
        FStructOnScope Params(Action);
        auto* Inputs = FindFProperty<FStructProperty>(Action,TEXT("Inputs"));
        if (!Inputs || Inputs->Struct != Output->Struct) return false;
        Inputs->CopyCompleteValue(Inputs->ContainerPtrToValuePtr<void>(Params.GetStructMemory()),Output->ContainerPtrToValuePtr<void>(InputParams.GetStructMemory()));
        Component->ProcessEvent(Action,Params.GetStructMemory());
        auto* CheckFailed=FindFProperty<FBoolProperty>(Action,TEXT("TraversalCheckFailed"));
        auto* MontageFailed=FindFProperty<FBoolProperty>(Action,TEXT("MontageSelectionFailed"));
        return CheckFailed && MontageFailed && !CheckFailed->GetPropertyValue_InContainer(Params.GetStructMemory())
            && !MontageFailed->GetPropertyValue_InContainer(Params.GetStructMemory());
    }
    return false;
}

void ACRTraversalCharacter::FinishCombatDeath()
{
    AController* DeathController = GetController();
    DestroyDueToDeath();
    if (!HasAuthority()) return;
    if (PhysicalInteraction->bAutoRecover)
    {
        // Practice targets return at their original station with a new health
        // component and AI controller, never reviving the old physical corpse.
        FActorSpawnParameters Params;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;
        GetWorld()->SpawnActor<AActor>(GetClass(), InitialSpawnTransform, Params);
        if (DeathController) DeathController->Destroy();
    }
    else if (auto* Mode = GetWorld()->GetAuthGameMode<ALyraGameMode>())
    {
        // The old pawn is detached and its ASC uninitialized before the restart
        // request can run, including after repeated deaths in the same session.
        if (DeathController) Mode->RequestPlayerRestartNextFrame(DeathController, false);
    }
}

void ACRTraversalCharacter::BeginPlay()
{
    Super::BeginPlay();
    InitialSpawnTransform = GetActorTransform();
    CastChecked<UBaselineCharacterMovement>(GetCharacterMovement())->OnSlideChanged.AddDynamic(this, &ThisClass::OnSlideChanged);
    // GASP's inactive GameplayCamera still creates an active output camera on register.
    // Keep the Lyra stack as the sole active camera, including on pawn respawn.
    TInlineComponentArray<UCameraComponent*> Cameras(this);
    for (UCameraComponent* Camera : Cameras)
        if (!Camera->IsA<ULyraCameraComponent>()) Camera->Deactivate();
}

void ACRTraversalCharacter::ToggleSlideCrouch()
{
    if (!CanUseMovementActions()) return;
    auto* Movement = CastChecked<UBaselineCharacterMovement>(GetCharacterMovement());
    // Ignore rapid toggle presses during the entry animation. Physical exits
    // (jump, ledge, impact, ragdoll) still end the slide through movement itself.
    if (Movement->IsSliding() && !Movement->CanCancelSlide()) return;
    if (Movement->IsSliding() || Movement->bWantsToSlide || bIsCrouched)
    {
        Movement->SetSlideRequested(false);
        UnCrouch();
    }
    else
    {
        // A rejected repeat slide should not flicker into a crouch or queue up
        // another entry boost. Slow movement retains the normal crouch toggle.
        if (Movement->GetSlideRecoveryRemaining() > 0.f
            && Movement->Velocity.SizeSquared2D() >= FMath::Square(Movement->SlideMinimumStartSpeed)) return;
        if (Movement->CanStartSlide()) Movement->SetSlideRequested(true);
        Crouch();
    }
}

void ACRTraversalCharacter::OnSlideChanged(bool bSliding)
{
    if (UAnimInstance* Anim = GetMesh()->GetAnimInstance())
    {
        if (bSliding && SlideAnimation)
            SlideMontage = Anim->PlaySlotAnimationAsDynamicMontage(SlideAnimation, TEXT("DefaultSlot"), .15f, .2f, 1.f, 9999);
        else if (SlideMontage)
        {
            Anim->Montage_Stop(.2f, SlideMontage);
            // Retain its identity through blend-out so equipment does not mistake
            // the end of a slide for a hands-busy traversal montage.
        }
    }
}

UCRTraversalHeroComponent::UCRTraversalHeroComponent(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    FInputMappingContextAndPriority Mapping;
    Mapping.InputMapping = TSoftObjectPtr<UInputMappingContext>(FSoftObjectPath(TEXT("/Game/Baseline/Input/IMC_Baseline.IMC_Baseline")));
    Mapping.Priority = 0;
    Mapping.bRegisterWithSettings = true;
    DefaultInputMappings.Add(Mapping);
}

void UCRTraversalHeroComponent::InitializePlayerInput(UInputComponent* PlayerInputComponent)
{
    Super::InitializePlayerInput(PlayerInputComponent);
    auto* Input = CastChecked<UEnhancedInputComponent>(PlayerInputComponent);
    if (auto* Character = GetPawn<ACRTraversalCharacter>())
    {
        const auto BindPhysical = [Input, Character](const TCHAR* Name, auto Method)
        {
            const FString Path = FString::Printf(TEXT("/Game/Baseline/Input/IA_%s.IA_%s"), Name, Name);
            if (auto* Action = LoadObject<UInputAction>(nullptr, *Path))
                Input->BindAction(Action, ETriggerEvent::Started, Character->PhysicalInteraction.Get(), Method);
        };
        BindPhysical(TEXT("Ragdoll"), &UBaselinePhysicalInteractionComponent::ToggleRagdoll);
        BindPhysical(TEXT("Shove"), &UBaselinePhysicalInteractionComponent::Shove);
        BindPhysical(TEXT("Tackle"), &UBaselinePhysicalInteractionComponent::Tackle);
        BindPhysical(TEXT("Takedown"), &UBaselinePhysicalInteractionComponent::Takedown);
        if (auto* Action = LoadObject<UInputAction>(nullptr, TEXT("/Game/Input/IA_Jump.IA_Jump")))
            Input->BindAction(Action, ETriggerEvent::Started, Character->PhysicalInteraction.Get(), &UBaselinePhysicalInteractionComponent::RequestRecovery);
        if (auto* Action = LoadObject<UInputAction>(nullptr, TEXT("/Game/Input/IA_Aim.IA_Aim")))
        {
            Input->BindAction(Action, ETriggerEvent::Started, Character->BaselineEquipment.Get(), &UBaselineEquipmentComponent::BeginAim);
            Input->BindAction(Action, ETriggerEvent::Completed, Character->BaselineEquipment.Get(), &UBaselineEquipmentComponent::EndAim);
            Input->BindAction(Action, ETriggerEvent::Canceled, Character->BaselineEquipment.Get(), &UBaselineEquipmentComponent::EndAim);
        }
        // This action has no press-only trigger and shares the fire button with
        // the semi-automatic action, so it also tracks a held pistol trigger.
        if (auto* Action = LoadObject<UInputAction>(nullptr, TEXT("/Game/Input/Actions/IA_Weapon_Fire_Auto.IA_Weapon_Fire_Auto")))
        {
            Input->BindAction(Action, ETriggerEvent::Started, Character->BaselineEquipment.Get(), &UBaselineEquipmentComponent::BeginFire);
            Input->BindAction(Action, ETriggerEvent::Completed, Character->BaselineEquipment.Get(), &UBaselineEquipmentComponent::EndFire);
            Input->BindAction(Action, ETriggerEvent::Canceled, Character->BaselineEquipment.Get(), &UBaselineEquipmentComponent::EndFire);
        }
        if (auto* Action = LoadObject<UInputAction>(nullptr, TEXT("/Game/Input/IA_Crouch.IA_Crouch")))
            Input->BindAction(Action, ETriggerEvent::Started, Character, &ACRTraversalCharacter::ToggleSlideCrouch);
        if (auto* Action = LoadObject<UInputAction>(nullptr, TEXT("/Game/Baseline/Input/IA_Interact.IA_Interact")))
            Input->BindAction(Action, ETriggerEvent::Started, Character->BaselineEquipment.Get(), &UBaselineEquipmentComponent::Interact);
        if (auto* Action = LoadObject<UInputAction>(nullptr, TEXT("/Game/Baseline/Input/IA_Drop.IA_Drop")))
            Input->BindAction(Action, ETriggerEvent::Started, Character->BaselineEquipment.Get(), &UBaselineEquipmentComponent::DropActiveWeapon);
        if (auto* Action = LoadObject<UInputAction>(nullptr, TEXT("/Game/Baseline/Input/IA_Cycle.IA_Cycle")))
            Input->BindAction(Action, ETriggerEvent::Started, Character->BaselineEquipment.Get(), &UBaselineEquipmentComponent::CycleWeapon);
        if (auto* Action = LoadObject<UInputAction>(nullptr, TEXT("/Game/Baseline/Input/IA_Shoulder.IA_Shoulder")))
            Input->BindAction(Action, ETriggerEvent::Started, Character->BaselineEquipment.Get(), &UBaselineEquipmentComponent::ToggleShoulder);
    }
}

UCRTraversalCameraMode::UCRTraversalCameraMode()
{
    FieldOfView = 85.0f;
    ViewPitchMin = -70.0f;
    ViewPitchMax = 60.0f;
    bUseRuntimeFloatCurves = true;
    TargetOffsetX.GetRichCurve()->AddKey(0.0f, -300.0f);
    TargetOffsetY.GetRichCurve()->AddKey(0.0f, 50.0f);
    // GASP's base eye height is 100 cm above its 86 cm capsule center.
    // This puts the standing follow pivot near the GDD's 155 cm target.
    TargetOffsetZ.GetRichCurve()->AddKey(0.0f, -30.0f);
}

void UCRTraversalCameraMode::UpdateView(float DeltaTime)
{
    const auto* Character = Cast<ACRTraversalCharacter>(GetTargetActor());
    const float Target = Character && Character->BaselineEquipment->IsLeftShoulder() ? -50.f : 50.f;
    ShoulderOffset = FMath::FInterpConstantTo(ShoulderOffset, Target, DeltaTime, 100.f / .35f);
    TargetOffsetY.GetRichCurve()->UpdateOrAddKey(0.f, ShoulderOffset);
    // Use the normal Lyra camera sweep for the whole transition, on either side.
    Super::UpdateView(DeltaTime);
}

ACRTraversalGameMode::ACRTraversalGameMode(const FObjectInitializer& ObjectInitializer) : Super(ObjectInitializer)
{
    PlayerControllerClass = ABaselinePlayerController::StaticClass();
    HUDClass = ABaselineHUD::StaticClass();
}

void ACRTraversalGameMode::InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage)
{
    const FString GymOptions = UGameplayStatics::HasOption(Options, TEXT("Experience"))
        ? Options : Options + TEXT("?Experience=B_CRTraversal");
    Super::InitGame(MapName, GymOptions, ErrorMessage);
}
