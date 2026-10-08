#include "CRCrowdAI.h"
#include "CRTraversalCharacter.h"
#include "CRWeaponEffects.h"
#include "CRRobotCharacter.h"
#include "CRRoll.h"
#include "CRThrowable.h"
#include "Baseline/BaselineEquipment.h"
#include "Baseline/BaselineCharacterMovement.h"
#include "Baseline/BaselinePhysicalInteraction.h"
#include "Character/LyraHealthComponent.h"
#include "Character/LyraPawnExtensionComponent.h"
#include "AbilitySystem/LyraAbilitySystemComponent.h"
#include "Inventory/LyraInventoryManagerComponent.h"
#include "Inventory/LyraInventoryItemInstance.h"
#include "Equipment/LyraQuickBarComponent.h"
#include "Equipment/LyraEquipmentManagerComponent.h"
#include "Weapons/LyraWeaponStateComponent.h"
#include "Player/LyraPlayerState.h"
#include "Components/SphereComponent.h"
#include "Components/ChildActorComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Navigation/CrowdFollowingComponent.h"
#include "Navigation/CrowdManager.h"
#include "NavigationSystem.h"
#include "NavigationPath.h"
#include "NavLinkCustomComponent.h"
#include "Perception/AIPerceptionComponent.h"
#include "Perception/AISenseConfig_Sight.h"
#include "Perception/AISenseConfig_Hearing.h"
#include "Perception/AISense_Sight.h"
#include "Perception/AISense_Hearing.h"
#include "EngineUtils.h"
#include "Net/UnrealNetwork.h"
#include "UObject/UnrealType.h"

namespace
{
FGameplayTag InputTag(const TCHAR* Name) { return FGameplayTag::RequestGameplayTag(FName(Name)); }
AActor* ResolvePawn(AActor* Actor)
{
    if (auto* Controller=Cast<AController>(Actor)) return Controller->GetPawn();
    if (auto* State=Cast<APlayerState>(Actor)) return State->GetPawn();
    return Actor;
}
bool IsAlive(const AActor* Actor)
{
    const auto* Health=ULyraHealthComponent::FindHealthComponent(Actor);
    return IsValid(Actor) && (!Health || !Health->IsDeadOrDying());
}
}

ACRCrowdArea::ACRCrowdArea()
{
    Bounds=CreateDefaultSubobject<USphereComponent>(TEXT("Tether"));
    SetRootComponent(Bounds);Bounds->SetSphereRadius(Radius);
    Bounds->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Bounds->SetCanEverAffectNavigation(false);
    Bounds->SetHiddenInGame(true);
}
void ACRCrowdArea::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);Bounds->SetSphereRadius(Radius);
}
bool ACRCrowdArea::SampleLocation(const APawn* ControlledCharacter, FVector& Out) const
{
    auto* Nav=FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
    if (!Nav || !ControlledCharacter) return false;
    for (int32 Attempt=0;Attempt<12;++Attempt)
    {
        FNavLocation Point;
        if (Nav->GetRandomReachablePointInRadius(GetActorLocation(),Radius,Point)
            && FVector::Dist2D(Point.Location,GetActorLocation()) <= Radius)
        {
            Out=Point.Location;return true;
        }
    }
    return false;
}

UCRCrowdAgentComponent::UCRCrowdAgentComponent()
{
    SetIsReplicatedByDefault(true);PrimaryComponentTick.bCanEverTick=false;
}
void UCRCrowdAgentComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ThisClass,State);DOREPLIFETIME(ThisClass,CurrentArea);DOREPLIFETIME(ThisClass,Threat);
    DOREPLIFETIME(ThisClass,LastKnownThreatLocation);DOREPLIFETIME(ThisClass,Destination);
    DOREPLIFETIME(ThisClass,AreaVisits);DOREPLIFETIME(ThisClass,TacticalMoves);DOREPLIFETIME(ThisClass,TraversalsStarted);
    DOREPLIFETIME(ThisClass,ShotsRequested);DOREPLIFETIME(ThisClass,SightDetections);DOREPLIFETIME(ThisClass,HearingDetections);
    DOREPLIFETIME(ThisClass,DamageReactions);DOREPLIFETIME(ThisClass,bInitialized);
    DOREPLIFETIME(ThisClass,SelectedVisual);
    DOREPLIFETIME(ThisClass,DesiredSpeed);
    DOREPLIFETIME(ThisClass,bProvoked);
}
void UCRCrowdAgentComponent::BeginPlay()
{
    Super::BeginPlay();
    // Players and practice partners are passive obstacles in the same crowd
    // simulation. AI pawns are registered by their CrowdFollowing component.
    if (GetOwner()->HasAuthority() && !bEnabled)
        if (auto* Manager=UCrowdManager::GetCurrent(this)) Manager->RegisterAgent(this);
}
void UCRCrowdAgentComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    if (auto* Manager=UCrowdManager::GetCurrent(this)) Manager->UnregisterAgent(this);
    Super::EndPlay(Reason);
}
FVector UCRCrowdAgentComponent::GetCrowdAgentLocation() const { return GetOwner()->GetActorLocation(); }
FVector UCRCrowdAgentComponent::GetCrowdAgentVelocity() const { return GetOwner()->GetVelocity(); }
void UCRCrowdAgentComponent::GetCrowdAgentCollisions(float& Radius, float& HalfHeight) const
{
    const auto* Capsule=GetOwner()->FindComponentByClass<UCapsuleComponent>();
    Radius=Capsule ? Capsule->GetScaledCapsuleRadius()+15.f : 45.f;
    HalfHeight=Capsule ? Capsule->GetScaledCapsuleHalfHeight() : 90.f;
}

void UCRCrowdAgentComponent::SetVisual(TSubclassOf<AActor> Visual)
{
    SelectedVisual=Visual;OnRep_Visual();
}
bool UCRCrowdAgentComponent::OwnsVisualOverride(UActorComponent* Source)
{
    const auto* Agent=Source && Source->GetOwner() ? Source->GetOwner()->FindComponentByClass<UCRCrowdAgentComponent>() : nullptr;
    return Agent && Agent->bEnabled;
}
void UCRCrowdAgentComponent::OnRep_Visual()
{
    if (auto* Character=Cast<ACRTraversalCharacter>(GetOwner()))
        Character->SelectedVisualOverride->SetChildActorClass(SelectedVisual);
}

void UCRCrowdAgentComponent::UpdateLocomotionIntent()
{
    auto* ControlledCharacter=Cast<ACRTraversalCharacter>(GetOwner());
    if (!bEnabled || !ControlledCharacter || !ControlledCharacter->HasAuthority()) return;
    // GASP chooses its motion-matching databases from input intent, not speed.
    // AI has no Enhanced Input actions: leaving the player defaults here selects
    // running/strafe poses for a 175 cm/s patrol and produces a hunched shuffle.
    // Use its existing replicated input struct, preserving equipment-owned aim.
    const auto* Input=FindFProperty<FStructProperty>(ControlledCharacter->GetClass(),TEXT("CharacterInputState"));
    if (!Input) return;
    void* Values=Input->ContainerPtrToValuePtr<void>(ControlledCharacter);
    const bool bReady=ControlledCharacter->BaselineEquipment->IsWeaponReady();
    for (TFieldIterator<FBoolProperty> It(Input->Struct);It;++It)
    {
        // User-defined struct members have generated GUID suffixes.
        const FString Name=It->GetName();
        if (Name.StartsWith(TEXT("WantsToWalk_"))) It->SetPropertyValue_InContainer(Values,DesiredSpeed<=300.f);
        else if (Name.StartsWith(TEXT("WantsToSprint_"))) It->SetPropertyValue_InContainer(Values,DesiredSpeed>550.f && !bReady);
        else if (Name.StartsWith(TEXT("WantsToStrafe_"))) It->SetPropertyValue_InContainer(Values,bReady);
    }
}

void UCRCrowdAgentComponent::ReportGunshot(APawn* Shooter, const FVector& Origin, const TArray<FCRShotImpact>& Hits)
{
    if (!Shooter || !Shooter->HasAuthority()) return;
    UAISense_Hearing::ReportNoiseEvent(Shooter,Origin,1.f,Shooter,5000.f,TEXT("Gunfire"));
    for (TActorIterator<ACRTraversalCharacter> It(Shooter->GetWorld());It;++It)
    {
        auto* Agent=It->CrowdAgent.Get();
        auto* Controller=Cast<ACRCrowdController>(It->GetController());
        if (!Controller || !Agent->bEnabled || *It==Shooter || !IsAlive(*It)) continue;
        const auto* ShooterAgent=Shooter->FindComponentByClass<UCRCrowdAgentComponent>();
        const bool bFriendlyGuard=ShooterAgent && ShooterAgent->bEnabled && ShooterAgent->bGuard;
        bool bNearMiss=false;
        for (const auto& Hit : Hits)
            if (FMath::PointDistToSegment(It->GetActorLocation(),Origin,Hit.Position)<
                (Agent->bReturnFireOnly ? It->GetCapsuleComponent()->GetScaledCapsuleRadius()+55.f : 190.f)) { bNearMiss=true;break; }
        if (bNearMiss && !bFriendlyGuard) Controller->ReactToThreat(Shooter,Origin,true);
        if (!Agent->bGuard && FVector::DistSquared(It->GetActorLocation(),Origin)<FMath::Square(4500.f))
            Controller->ReactToThreat(Shooter,Origin,true);
    }
}

ACRCrowdController::ACRCrowdController(const FObjectInitializer& Initializer)
    : Super(Initializer.SetDefaultSubobjectClass<UCrowdFollowingComponent>(TEXT("PathFollowingComponent")))
{
    PrimaryActorTick.bCanEverTick=true;
    Inventory=CreateDefaultSubobject<ULyraInventoryManagerComponent>(TEXT("Inventory"));
    QuickBar=CreateDefaultSubobject<ULyraQuickBarComponent>(TEXT("QuickBar"));
    WeaponState=CreateDefaultSubobject<ULyraWeaponStateComponent>(TEXT("WeaponState"));
    Senses=CreateDefaultSubobject<UAIPerceptionComponent>(TEXT("Senses"));
    SetPerceptionComponent(*Senses);
    auto* Sight=CreateDefaultSubobject<UAISenseConfig_Sight>(TEXT("Sight"));
    Sight->SightRadius=2800.f;Sight->LoseSightRadius=3200.f;Sight->PeripheralVisionAngleDegrees=65.f;Sight->SetMaxAge(5.f);
    Sight->DetectionByAffiliation.bDetectEnemies=Sight->DetectionByAffiliation.bDetectFriendlies=Sight->DetectionByAffiliation.bDetectNeutrals=true;
    auto* Hearing=CreateDefaultSubobject<UAISenseConfig_Hearing>(TEXT("Hearing"));
    Hearing->HearingRange=5000.f;Hearing->SetMaxAge(8.f);
    Hearing->DetectionByAffiliation.bDetectEnemies=Hearing->DetectionByAffiliation.bDetectFriendlies=Hearing->DetectionByAffiliation.bDetectNeutrals=true;
    Senses->ConfigureSense(*Sight);Senses->ConfigureSense(*Hearing);Senses->SetDominantSense(Sight->GetSenseImplementation());
    bAttachToPawn=true;
}
ACRTraversalCharacter* ACRCrowdController::Character() const { return Cast<ACRTraversalCharacter>(GetPawn()); }
UCRCrowdAgentComponent* ACRCrowdController::Agent() const { return Character() ? Character()->CrowdAgent.Get() : nullptr; }
void ACRCrowdController::OnPossess(APawn* ControlledCharacter)
{
    Super::OnPossess(ControlledCharacter);
    Senses->OnTargetPerceptionUpdated.AddUniqueDynamic(this,&ThisClass::PerceptionUpdated);
    if (auto* Health=ULyraHealthComponent::FindHealthComponent(ControlledCharacter)) Health->OnHealthChanged.AddUniqueDynamic(this,&ThisClass::HealthChanged);
    NextThink=GetWorld()->GetTimeSeconds()+.5;
    LastProgressPosition=ControlledCharacter->GetActorLocation();LastProgressTime=GetWorld()->GetTimeSeconds();
}
void ACRCrowdController::OnUnPossess()
{
    StopFiring();StopMovement();
    if (auto* Health=ULyraHealthComponent::FindHealthComponent(GetPawn())) Health->OnHealthChanged.RemoveAll(this);
    Senses->OnTargetPerceptionUpdated.RemoveAll(this);
    Super::OnUnPossess();
}
void ACRCrowdController::InitializeAgent()
{
    auto* ControlledCharacter=Character();auto* Data=Agent();
    if (!ControlledCharacter || !Data || !Data->bEnabled || !ControlledCharacter->GetLyraAbilitySystemComponent()) return;
    if (auto* State=ControlledCharacter->GetLyraPlayerState()) State->SetGenericTeamId(FGenericTeamId(Data->bGuard ? 2 : 3));
    if (!Data->HomeArea)
    {
        float Best=MAX_flt;
        for (TActorIterator<ACRCrowdArea> It(GetWorld());It;++It)
        {
            if ((Data->bGuard && !It->bAllowGuards) || (!Data->bGuard && !It->bAllowCivilians)) continue;
            const float Distance=FVector::DistSquared(It->GetActorLocation(),ControlledCharacter->GetActorLocation());
            if (Distance<Best) { Best=Distance;Data->HomeArea=*It; }
        }
    }
    Data->CurrentArea=Data->HomeArea;
    if (!Data->CurrentArea) return;
    if (!Data->Visuals.IsEmpty()) Data->SetVisual(Data->Visuals[FMath::RandRange(0,Data->Visuals.Num()-1)]);
    if (Data->bGuard && !Data->Weapons.IsEmpty())
    {
        auto* Item=Inventory->AddItemDefinition(Data->Weapons[FMath::RandRange(0,Data->Weapons.Num()-1)],1);
        if (Item) { QuickBar->AddItemToSlot(0,Item);QuickBar->SetActiveSlotIndex(0); }
    }
    auto* Movement=ControlledCharacter->GetCharacterMovement();
    Movement->bUseRVOAvoidance=false;
    ControlledCharacter->GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Pawn,ECR_Block);
    if (auto* Crowd=Cast<UCrowdFollowingComponent>(GetPathFollowingComponent()))
    {
        Crowd->SetCrowdAvoidanceQuality(ECrowdAvoidanceQuality::High);
        Crowd->SetCrowdObstacleAvoidance(true);Crowd->SetCrowdAnticipateTurns(true);
        Crowd->SetCrowdSeparation(true);Crowd->SetCrowdSeparationWeight(4.f);
        // This multiplier also expands avoidance velocity samples. At 2 it
        // selected ~35% speed even on clear paths, mismatching run animations.
        // Use the query distance below for lookahead, preserving full strides.
        Crowd->SetCrowdAvoidanceRangeMultiplier(1.f);
        Crowd->SetCrowdCollisionQueryRange(650.f);
        // The controller distinguishes traffic from geometry and can yield.
        // The generic blocked-path timer would abort before that recovery.
        Crowd->SetBlockDetectionState(false);
    }
    Data->bInitialized=true;Data->AreaVisits=1;
    NextPatrol=GetWorld()->GetTimeSeconds()+FMath::FRandRange(.1f,1.2f);
    NextAreaChange=GetWorld()->GetTimeSeconds()+FMath::FRandRange(10.f,20.f);
}

void ACRCrowdController::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    auto* ControlledCharacter=Character();auto* Data=Agent();
    if (!HasAuthority() || !ControlledCharacter || !Data || !Data->bEnabled) return;
    const double Now=GetWorld()->GetTimeSeconds();
    if (bTriggerHeld && Now>=StopFireAt) StopFiring();
    if (auto* ASC=ControlledCharacter->GetLyraAbilitySystemComponent()) ASC->ProcessAbilityInput(DeltaSeconds,false);
    if (Now>=NextThink) { NextThink=Now+.2;Think(); }
    if (ActionUntil>Now && (ActiveAction==TEXT("Jump") || ActiveAction==TEXT("Slide")))
    {
        if (Data->bGuard && Data->Threat && bAggressive && CanSee(Data->Threat)) FireBurst();
        ControlledCharacter->AddMovementInput((ActionGoal-ControlledCharacter->GetActorLocation()).GetSafeNormal2D(),1.f,true);
    }
    else if (ActionUntil>0.)
    {
        if (ActiveAction==TEXT("Slide")) { CastChecked<UBaselineCharacterMovement>(ControlledCharacter->GetCharacterMovement())->SetSlideRequested(false);ControlledCharacter->UnCrouch(); }
        ControlledCharacter->StopJumping();ActionUntil=0.;ActiveAction=NAME_None;NextPatrol=Now;
    }
    Data->UpdateLocomotionIntent();
    // Detour caches movement limits. Refresh when patrol/chase, crouch, slide
    // or recovery changes the limit, so the trajectory matches the chosen gait.
    const float MaxSpeed=ControlledCharacter->GetCharacterMovement()->GetMaxSpeed();
    if (!FMath::IsNearlyEqual(MaxSpeed,LastCrowdMaxSpeed))
    {
        if (auto* Crowd=Cast<UCrowdFollowingComponent>(GetPathFollowingComponent())) Crowd->UpdateCrowdAgentParams();
        LastCrowdMaxSpeed=MaxSpeed;
    }
}

void ACRCrowdController::UpdateControlRotation(float DeltaTime, bool bUpdatePawn)
{
    if (auto* Data=Agent(); Data && Data->bGuard && Data->Threat && bAggressive && CanSee(Data->Threat))
    {
        const FVector Aim=Data->Threat->GetActorLocation()+FVector(0,0,25);
        const FVector Origin=GetPawn()->GetActorLocation()+FVector(0,0,GetPawn()->BaseEyeHeight);
        SetControlRotation(FMath::RInterpTo(GetControlRotation(),(Aim-Origin).Rotation(),DeltaTime,8.f));
        return;
    }
    Super::UpdateControlRotation(DeltaTime,bUpdatePawn);
}

bool ACRCrowdController::CanSee(const AActor* Actor) const
{
    if (!GetPawn() || !Actor) return false;
    const FVector Delta=Actor->GetActorLocation()-GetPawn()->GetActorLocation();
    if (Delta.SizeSquared()>FMath::Square(3200.f)) return false;
    if (FVector::DotProduct(GetControlRotation().Vector().GetSafeNormal2D(),Delta.GetSafeNormal2D())<.25f) return false;
    if (ACRThrownObject::IsSightObscured(this,GetPawn()->GetPawnViewLocation(),Actor->GetActorLocation()+FVector(0,0,50))) return false;
    return LineOfSightTo(Actor);
}
bool ACRCrowdController::ClearShot(const AActor* Actor) const
{
    if (!GetPawn() || !Actor) return false;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(CrowdFireSafety),true,GetPawn());
    TArray<AActor*> Attached;GetPawn()->GetAttachedActors(Attached,true,true);Query.AddIgnoredActors(Attached);
    FHitResult Hit;
    const FVector Start=GetPawn()->GetActorLocation()+FVector(0,0,GetPawn()->BaseEyeHeight);
    if (ACRThrownObject::IsSightObscured(this,Start,Actor->GetActorLocation()+FVector(0,0,25))) return false;
    const bool Blocked=GetWorld()->LineTraceSingleByChannel(Hit,Start,Actor->GetActorLocation()+FVector(0,0,25),ECC_Visibility,Query);
    if (!Blocked) return true;
    return Hit.GetActor()==Actor || (Hit.GetActor() && Hit.GetActor()->GetAttachParentActor()==Actor);
}

void ACRCrowdController::ReactToThreat(AActor* Actor,const FVector& Location,bool bAggression)
{
    auto* Data=Agent();Actor=ResolvePawn(Actor);
    if (!Data || !Data->bEnabled || !IsAlive(GetPawn()) || Actor==GetPawn()) return;
    if (const auto* Other=Actor ? Actor->FindComponentByClass<UCRCrowdAgentComponent>() : nullptr)
        if (Data->bGuard && Other->bEnabled && Other->bGuard) return;
    if (!IsAlive(Actor)) return;
    // Unrelated noise must not replace a robot's aggressor and inherit its
    // permission to fire. A second actual attacker can start a new engagement.
    if (Data->bReturnFireOnly && !bAggression && bAggressive && Actor!=Data->Threat) return;
    if (Data->bReturnFireOnly && Actor!=Data->Threat) bAggressive=false;
    const bool bNewEngagement=Data->Threat!=Actor || !bAggressive;
    const bool bStartingFlight=Data->State!=ECRCrowdState::Flee;
    Data->Threat=Actor;Data->LastKnownThreatLocation=Location;
    LastThreatTime=GetWorld()->GetTimeSeconds();
    bAggressive|=bAggression;
    Data->bProvoked=bAggressive;
    if (!Data->bGuard) { Data->State=ECRCrowdState::Flee;if (bStartingFlight) NextTactic=0.; }
    else if (bAggressive) { Data->State=ECRCrowdState::Pursue;if (bNewEngagement) NextTactic=0.; }
    else Data->State=ECRCrowdState::Investigate;
    NextThink=0.;
}
void ACRCrowdController::PerceptionUpdated(AActor* Actor,FAIStimulus Stimulus)
{
    auto* Data=Agent();if (!Data || !Data->bEnabled || !Stimulus.WasSuccessfullySensed() || Actor==GetPawn()) return;
    if (Stimulus.Type==UAISense::GetSenseID<UAISense_Hearing>())
    {
        if (Stimulus.Tag!=TEXT("Gunfire") && Stimulus.Tag!=TEXT("Footstep")) return;
        if (const auto* Other=Actor->FindComponentByClass<UCRCrowdAgentComponent>())
            if (Other->bEnabled && ((Data->bGuard && Other->bGuard) || Stimulus.Tag==TEXT("Footstep"))) return;
        ++Data->HearingDetections;
        if (Stimulus.Tag==TEXT("Gunfire")) { bHeardGunfire=true;ReactToThreat(Actor,Stimulus.StimulusLocation,(!Data->bReturnFireOnly && CanSee(Actor)) || !Data->bGuard); }
        else if (Data->bGuard && !Data->Threat) ReactToThreat(Actor,Stimulus.StimulusLocation,false);
    }
    else if (Stimulus.Type==UAISense::GetSenseID<UAISense_Sight>())
    {
        if (!Cast<APawn>(Actor) || !CanSee(Actor)) return;
        ++Data->SightDetections;
        if (Actor==Data->Threat) { Data->LastKnownThreatLocation=Actor->GetActorLocation();LastSeenTime=GetWorld()->GetTimeSeconds(); }
    }
}
void ACRCrowdController::HealthChanged(ULyraHealthComponent*,float OldValue,float NewValue,AActor* DamageInstigator)
{
    if (NewValue>=OldValue || !Agent()) return;
    ++Agent()->DamageReactions;
    DamageInstigator=ResolvePawn(DamageInstigator);
    if (DamageInstigator) ReactToThreat(DamageInstigator,DamageInstigator->GetActorLocation(),true);
}

void ACRCrowdController::StopFiring()
{
    if (auto* ControlledCharacter=Character())
    {
        if (auto* Robot=Cast<ACRRobotCharacter>(ControlledCharacter)) Robot->StopMountedBurst();
        ControlledCharacter->BaselineEquipment->EndFire();
        if (auto* ASC=ControlledCharacter->GetLyraAbilitySystemComponent())
        {
            ASC->AbilityInputTagReleased(InputTag(TEXT("InputTag.Weapon.Fire")));
            ASC->AbilityInputTagReleased(InputTag(TEXT("InputTag.Weapon.FireAuto")));
        }
    }
    bTriggerHeld=false;
}

void ACRCrowdController::MoveTowards(const FVector& Goal,ECRCrowdState NewState,float Speed)
{
    auto* ControlledCharacter=Character();auto* Data=Agent();if (!ControlledCharacter || !Data) return;
    if (Cast<ACRRobotCharacter>(ControlledCharacter)) Speed=FMath::Min(Speed,Data->RunSpeed);
    Data->Destination=Goal;Data->State=NewState;
    Data->DesiredSpeed=Speed;
    ControlledCharacter->GetCharacterMovement()->MaxWalkSpeed=Speed;
    FAIMoveRequest Request(Goal);Request.SetAcceptanceRadius(90.f);Request.SetUsePathfinding(true);Request.SetAllowPartialPath(true);Request.SetCanStrafe(NewState==ECRCrowdState::Reposition);
    MoveTo(Request);
}
void ACRCrowdController::Patrol()
{
    auto* ControlledCharacter=Character();auto* Data=Agent();const double Now=GetWorld()->GetTimeSeconds();
    ControlledCharacter->BaselineEquipment->EndAim();ControlledCharacter->UnCrouch();ClearFocus(EAIFocusPriority::Gameplay);
    if (GetMoveStatus()==EPathFollowingStatus::Moving) return;
    if (Now<NextPatrol) { Data->State=ECRCrowdState::Idle;return; }
    auto* Area=Data->CurrentArea.Get();if (!Area) return;
    if (Now>=NextAreaChange)
    {
        NextAreaChange=Now+FMath::FRandRange(12.f,25.f);
        if (FMath::FRand()<Area->WanderChance)
        {
            TArray<ACRCrowdArea*> Candidates;
            for (ACRCrowdArea* Other:Area->Neighbours)
                if (Other && (Data->bGuard ? Other->bAllowGuards : Other->bAllowCivilians)) Candidates.Add(Other);
            if (!Candidates.IsEmpty()) { Area=Candidates[FMath::RandRange(0,Candidates.Num()-1)];Data->CurrentArea=Area;++Data->AreaVisits; }
        }
    }
    FVector Goal;
    if (Area->SampleLocation(ControlledCharacter,Goal)) MoveTowards(Goal,ECRCrowdState::Patrol,Data->PatrolSpeed);
    NextPatrol=Now+FMath::FRandRange(3.f,6.f);
}

bool ACRCrowdController::SelectTacticalPosition(FVector& Out) const
{
    auto* ControlledCharacter=Character();auto* Data=Agent();auto* Nav=FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
    if (!ControlledCharacter || !Data || !Data->Threat || !Nav) return false;
    const FVector Enemy=Data->LastKnownThreatLocation;
    const FVector Away=(ControlledCharacter->GetActorLocation()-Enemy).GetSafeNormal2D();
    float Best=-MAX_flt;
    for (int32 Index=0;Index<16;++Index)
    {
        const float Angle=(Index%2 ? -1.f : 1.f)*(25.f+(Index/2)*16.f);
        const FVector Candidate=Enemy+Away.RotateAngleAxis(Angle,FVector::UpVector)*Data->CombatRange*FMath::FRandRange(.7f,1.2f);
        FNavLocation Projected;
        if (!Nav->ProjectPointToNavigation(Candidate,Projected,FVector(180,180,250))) continue;
        const float Travel=FVector::Dist2D(Projected.Location,ControlledCharacter->GetActorLocation());
        if (Travel<240.f || Travel>2200.f) continue;
        auto* Path=UNavigationSystemV1::FindPathToLocationSynchronously(GetWorld(),ControlledCharacter->GetActorLocation(),Projected.Location,ControlledCharacter);
        if (!Path || !Path->IsValid() || Path->IsPartial()) continue;
        FCollisionQueryParams Query(SCENE_QUERY_STAT(CrowdCover),true,ControlledCharacter);Query.AddIgnoredActor(Data->Threat);
        FHitResult Low,High;
        const bool bLow=GetWorld()->LineTraceSingleByChannel(Low,Projected.Location+FVector(0,0,65),Enemy+FVector(0,0,30),ECC_Visibility,Query);
        const bool bHigh=GetWorld()->LineTraceSingleByChannel(High,Projected.Location+FVector(0,0,160),Enemy+FVector(0,0,30),ECC_Visibility,Query);
        // Prefer cover that permits a standing peek, then lateral firing lanes.
        float Score=(bLow && !bHigh ? 900.f : !bHigh ? 350.f : -250.f)-Travel*.12f+FMath::FRandRange(0.f,120.f);
        for (TActorIterator<ACRTraversalCharacter> It(GetWorld());It;++It)
            if (*It!=ControlledCharacter && It->CrowdAgent->bEnabled && FVector::Dist2D(It->CrowdAgent->Destination,Projected.Location)<250.f) Score-=650.f;
        if (Score>Best) { Best=Score;Out=Projected.Location; }
    }
    return Best>-MAX_flt;
}

void ACRCrowdController::FireBurst()
{
    auto* ControlledCharacter=Character();auto* Data=Agent();auto* ASC=ControlledCharacter->GetLyraAbilitySystemComponent();
    const double Now=GetWorld()->GetTimeSeconds();
    if (!ASC || Now<NextShot || bTriggerHeld || ControlledCharacter->BaselineEquipment->AreHandsBusy() || !ClearShot(Data->Threat)) return;
    if (auto* Robot=Cast<ACRRobotCharacter>(ControlledCharacter))
    {
        if (bAggressive && Robot->StartMountedBurst(Data->Threat))
        { NextShot=Now+FMath::FRandRange(1.1f,1.7f);++Data->ShotsRequested; }
        return;
    }
    if (auto* Item=QuickBar->GetActiveSlotItem())
    {
        if (Item->GetStatTagStackCount(InputTag(TEXT("Lyra.ShooterGame.Weapon.MagazineAmmo")))<=0)
        {
            ASC->AbilityInputTagPressed(InputTag(TEXT("InputTag.Weapon.Reload")));
            ASC->ProcessAbilityInput(.01f,false);
            ASC->AbilityInputTagReleased(InputTag(TEXT("InputTag.Weapon.Reload")));
            NextShot=Now+1.f;return;
        }
    }
    ControlledCharacter->BaselineEquipment->BeginAim();ControlledCharacter->BaselineEquipment->BeginFire();
    ASC->AbilityInputTagPressed(InputTag(TEXT("InputTag.Weapon.Fire")));
    ASC->AbilityInputTagPressed(InputTag(TEXT("InputTag.Weapon.FireAuto")));
    bTriggerHeld=true;StopFireAt=Now+FMath::FRandRange(.16f,.38f);
    NextShot=Now+FMath::FRandRange(.8f,1.5f);++Data->ShotsRequested;
}

void ACRCrowdController::Combat()
{
    auto* ControlledCharacter=Character();auto* Data=Agent();const double Now=GetWorld()->GetTimeSeconds();
    const bool bVisible=CanSee(Data->Threat);
    if (bVisible) { Data->LastKnownThreatLocation=Data->Threat->GetActorLocation();LastSeenTime=Now; }
    if (!bVisible)
    {
        StopFiring();ControlledCharacter->BaselineEquipment->EndAim();ClearFocus(EAIFocusPriority::Gameplay);
        if (Now-LastSeenTime>18. && Now-LastThreatTime>18.)
        { Data->Threat=nullptr;bAggressive=false;Data->bProvoked=false;bHeardGunfire=false;StopMovement();NextPatrol=Now;return; }
        if (GetMoveStatus()!=EPathFollowingStatus::Moving || Now>=NextTactic)
        {
            MoveTowards(Data->LastKnownThreatLocation,ECRCrowdState::Pursue,Data->RunSpeed);
            NextTactic=Now+2.;
        }
        return;
    }
    ControlledCharacter->BaselineEquipment->BeginAim();SetFocus(Data->Threat);
    if (Now>=NextTactic)
    {
        FVector Goal;
        if (SelectTacticalPosition(Goal))
        {
            ControlledCharacter->UnCrouch();MoveTowards(Goal,ECRCrowdState::Reposition,450.f);++Data->TacticalMoves;
            if (Data->TacticalMoves%3==0 && !Cast<ACRRobotCharacter>(ControlledCharacter)) ControlledCharacter->BaselineEquipment->ToggleShoulder();
        }
        const float TravelTime=Cast<ACRRobotCharacter>(ControlledCharacter)
            ? FVector::Dist2D(Data->Destination,ControlledCharacter->GetActorLocation())/FMath::Max(Data->RunSpeed,1.f) : 0.f;
        NextTactic=Now+(TravelTime>0.f ? TravelTime+FMath::FRandRange(2.2f,3.f) : FMath::FRandRange(3.f,5.f));
    }
    if (GetMoveStatus()!=EPathFollowingStatus::Moving)
    {
        Data->State=ECRCrowdState::Attack;
        if (!Cast<ACRRobotCharacter>(ControlledCharacter))
        {
            if (Now>=NextShot && ControlledCharacter->bIsCrouched) ControlledCharacter->UnCrouch();
            else if (Now<NextShot-.25 && !bTriggerHeld) ControlledCharacter->Crouch();
        }
    }
    FireBurst();
}

void ACRCrowdController::Flee()
{
    auto* ControlledCharacter=Character();auto* Data=Agent();const double Now=GetWorld()->GetTimeSeconds();
    StopFiring();ControlledCharacter->BaselineEquipment->EndAim();ControlledCharacter->UnCrouch();ClearFocus(EAIFocusPriority::Gameplay);
    if (Now-LastThreatTime>14.) { Data->Threat=nullptr;bAggressive=false;NextPatrol=Now;StopMovement();return; }
    if (Now<NextTactic && GetMoveStatus()==EPathFollowingStatus::Moving) return;
    FVector BestGoal;float Best=-MAX_flt;
    for (TActorIterator<ACRCrowdArea> It(GetWorld());It;++It)
    {
        if (!It->bAllowCivilians) continue;
        for (int32 Try=0;Try<3;++Try)
        {
            FVector Goal;if (!It->SampleLocation(ControlledCharacter,Goal)) continue;
            const float Score=FVector::Dist2D(Goal,Data->LastKnownThreatLocation)-.2f*FVector::Dist2D(Goal,ControlledCharacter->GetActorLocation());
            if (Score>Best) { Best=Score;BestGoal=Goal;Data->CurrentArea=*It; }
        }
    }
    if (Best>-MAX_flt) MoveTowards(BestGoal,ECRCrowdState::Flee,Data->RunSpeed);
    NextTactic=Now+FMath::FRandRange(2.f,3.5f);
}

bool ACRCrowdController::RequestMovementAction(FName Action,FVector Goal)
{
    auto* ControlledCharacter=Character();auto* Data=Agent();const double Now=GetWorld()->GetTimeSeconds();
    if (!ControlledCharacter || !Data || !ControlledCharacter->CanUseMovementActions() || Now<NextTraversal || ControlledCharacter->BaselineEquipment->AreHandsBusy()) return false;
    // Mechanical rigs have their own grounded gait and jump pose. Do not play
    // humanoid slide/vault montages on their incompatible skeletons.
    if (Cast<ACRRobotCharacter>(ControlledCharacter) && Action!=TEXT("Jump")) return false;
    auto* Movement=CastChecked<UBaselineCharacterMovement>(ControlledCharacter->GetCharacterMovement());
    if (!Movement->IsMovingOnGround()) return false;
    const FRotator Facing=(Goal-ControlledCharacter->GetActorLocation()).GetSafeNormal2D().Rotation();
    if (Action==TEXT("Vault") || Action==TEXT("Climb"))
    {
        ControlledCharacter->SetActorRotation(Facing);SetControlRotation(Facing);
        if (!ControlledCharacter->RequestAITraversal()) { NextTraversal=Now+.6;return false; }
    }
    else if (Action==TEXT("Jump")) ControlledCharacter->Jump();
    else if (Action==TEXT("Roll"))
    {
        if (!ControlledCharacter->Roll->RequestRoll(Goal-ControlledCharacter->GetActorLocation())) return false;
    }
    else if (Action==TEXT("Slide"))
    {
        if (!Movement->CanStartSlide()) return false;
        Movement->SetSlideRequested(true);
    }
    else return false;
    const FVector EntryVelocity=Movement->Velocity;
    StopMovement();
    if (Action==TEXT("Slide")) Movement->Velocity=EntryVelocity;
    ActiveAction=Action;ActionGoal=Goal;
    ActionUntil=Now+(Action==TEXT("Slide") ? .85 : Action==TEXT("Jump") ? .8 : 2.0);
    NextTraversal=Now+2.5;++Data->TraversalsStarted;return true;
}

void ACRCrowdController::Think()
{
    auto* ControlledCharacter=Character();auto* Data=Agent();const double Now=GetWorld()->GetTimeSeconds();
    if (!Data->bInitialized) { InitializeAgent();return; }
    if (!IsAlive(ControlledCharacter)) { Data->State=ECRCrowdState::Dead;StopFiring();StopMovement();return; }
    if (ControlledCharacter->PhysicalInteraction->IsBusy()) { Data->State=ECRCrowdState::Recover;StopFiring();StopMovement();return; }
    if (bUsingTraversalLink || ControlledCharacter->BaselineEquipment->AreHandsBusy() || ActionUntil>Now) return;
    if (YieldUntil>0.)
    {
        if (Now>=YieldUntil || GetMoveStatus()!=EPathFollowingStatus::Moving)
        {
            YieldUntil=0.;MoveToLocation(YieldReturnGoal,90.f);
            LastProgressTime=Now;LastProgressPosition=ControlledCharacter->GetActorLocation();
        }
        return;
    }
    if (Data->Threat && !IsAlive(Data->Threat)) { Data->Threat=nullptr;bAggressive=false;Data->bProvoked=false;bHeardGunfire=false;StopFiring();StopMovement(); }
    if (Data->Threat)
    {
        if (Data->bGuard && !Data->bReturnFireOnly && bHeardGunfire && CanSee(Data->Threat)) bAggressive=true;
        if (!Data->bGuard) Flee();
        else if (bAggressive) Combat();
        else if (Now-LastThreatTime>7.) { Data->Threat=nullptr;bHeardGunfire=false;StopMovement();NextPatrol=Now; }
        else if (GetMoveStatus()!=EPathFollowingStatus::Moving)
            MoveTowards(Data->LastKnownThreatLocation,ECRCrowdState::Investigate,280.f);
    }
    else Patrol();
    // A blocked route may use the player's traversal checks. Never warp across
    // obstacles; if there is no valid traversal animation, replan the route.
    if (GetMoveStatus()==EPathFollowingStatus::Moving && Now>=NextTraversal)
    {
        if ((Data->State==ECRCrowdState::Flee || Data->State==ECRCrowdState::Pursue)
            && ControlledCharacter->GetVelocity().Size2D()>560.f && FVector::Dist2D(Data->Destination,ControlledCharacter->GetActorLocation())>850.f
            && FMath::FRand()<.035f && RequestMovementAction(TEXT("Slide"),Data->Destination)) return;
        const float Progress=FVector::Dist2D(ControlledCharacter->GetActorLocation(),LastProgressPosition);
        if (Progress>75.f) { LastProgressPosition=ControlledCharacter->GetActorLocation();LastProgressTime=Now; }
        else if (Now-LastProgressTime>3.5)
        {
            bool bWaitingForCrowd=false;
            for (TActorIterator<ACRTraversalCharacter> It(GetWorld());It;++It)
                if (*It!=ControlledCharacter && IsAlive(*It) && FVector::DistSquared(It->GetActorLocation(),ControlledCharacter->GetActorLocation())<FMath::Square(180.f))
                { bWaitingForCrowd=true;break; }
            if (bWaitingForCrowd)
            {
                const FVector Forward=(Data->Destination-ControlledCharacter->GetActorLocation()).GetSafeNormal2D();
                const FVector Right=FVector::CrossProduct(FVector::UpVector,Forward);
                if (auto* Nav=FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld()))
                {
                    FNavLocation Yield;
                    const FVector Candidate=ControlledCharacter->GetActorLocation()+Right*(250.f+float(GetUniqueID()%3)*65.f)-Forward*100.f;
                    if (Nav->ProjectPointToNavigation(Candidate,Yield,FVector(100,100,200)))
                    {
                        YieldReturnGoal=Data->Destination;YieldUntil=Now+3.;
                        MoveToLocation(Yield.Location,25.f);
                    }
                }
                LastProgressTime=Now;return;
            }
            if (!RequestMovementAction(TEXT("Vault"),Data->Destination))
            {
                StopMovement();NextPatrol=Now+.5;NextTactic=Now+.5;
            }
            LastProgressTime=Now;
        }
    }
}

ACRCrowdTraversalLink::ACRCrowdTraversalLink()
{
    bSmartLinkIsRelevant=true;PointLinks.Reset();
    PrimaryActorTick.bCanEverTick=true;
}
void ACRCrowdTraversalLink::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);PointLinks.Reset();
    GetSmartLinkComp()->SetLinkData(Start,End,bBidirectional ? ENavLinkDirection::BothWays : ENavLinkDirection::LeftToRight);
    SetSmartLinkEnabled(true);
}
void ACRCrowdTraversalLink::BeginPlay()
{
    Super::BeginPlay();OnSmartLinkReached.AddDynamic(this,&ThisClass::LinkReached);
}
void ACRCrowdTraversalLink::LinkReached(AActor* MovingActor,const FVector& DestinationPoint)
{
    auto* MovingPawn=Cast<APawn>(MovingActor);
    auto* Controller=MovingPawn ? Cast<ACRCrowdController>(MovingPawn->GetController()) : nullptr;
    if (Controller)
    {
        // Detour reports link entry before the capsule reaches its endpoint.
        // Approach that endpoint first so GASP's short obstacle checks succeed.
        Controller->StopMovement();Controller->bUsingTraversalLink=true;
        FPendingTraversal Pending;Pending.Time=GetWorld()->GetTimeSeconds();
        const FVector A=GetActorTransform().TransformPosition(Start);
        const FVector B=GetActorTransform().TransformPosition(End);
        Pending.Approach=FVector::DistSquared(A,MovingActor->GetActorLocation())<FVector::DistSquared(B,MovingActor->GetActorLocation()) ? A : B;
        Pending.Destination=DestinationPoint;
        PendingAgents.Add(MovingActor,Pending);
    }
    else ResumePathFollowing(MovingActor);
}
void ACRCrowdTraversalLink::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    for (auto It=PendingAgents.CreateIterator();It;++It)
    {
        auto* Character=Cast<ACRTraversalCharacter>(It.Key().Get());
        auto* Controller=Character ? Cast<ACRCrowdController>(Character->GetController()) : nullptr;
        auto& Pending=It.Value();
        const double Age=GetWorld()->GetTimeSeconds()-Pending.Time;
        if (Controller && !Pending.bStarted && Age<4.)
        {
            const FVector Direction=(Pending.Approach-Character->GetActorLocation()).GetSafeNormal2D();
            Character->CrowdAgent->DesiredSpeed=180.f;
            if (FVector::Dist2D(Pending.Approach,Character->GetActorLocation())>15.f)
            {
                Controller->SetControlRotation(Direction.Rotation());
                Character->AddMovementInput(Direction,1.f,true);
            }
            else if (Controller->RequestMovementAction(Action,Pending.Destination)) Pending.bStarted=true;
        }
        if (!Character || !Controller || Age>8. || (!Pending.bStarted && Age>=4.)
            || (Pending.bStarted && Age>1. && Character->GetCharacterMovement()->IsMovingOnGround() && !Character->BaselineEquipment->AreHandsBusy()))
        {
            if (Character)
            {
                ResumePathFollowing(Character);
                if (Controller)
                {
                    Controller->bUsingTraversalLink=false;
                    Controller->MoveToLocation(Character->CrowdAgent->Destination,90.f);
                }
            }
            It.RemoveCurrent();
        }
    }
}
