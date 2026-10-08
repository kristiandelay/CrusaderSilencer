#include "BaselinePhysicalInteraction.h"
#include "BaselineCharacterMovement.h"
#include "BaselineEquipment.h"
#include "Crusader/CRRoll.h"
#include "PhysicsControlComponent.h"
#include "PhysicsControlAsset.h"
#include "PoseSearch/PoseSearchDatabase.h"
#include "PoseSearch/PoseSearchLibrary.h"
#include "PoseSearch/PoseSearchInteractionLibrary.h"
#include "PoseSearch/PoseSearchInteractionAsset.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSequence.h"
#include "Animation/PoseSnapshot.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/GameStateBase.h"
#include "EngineUtils.h"
#include "Engine/SkeletalMesh.h"
#include "Net/UnrealNetwork.h"
#include "PhysicsEngine/BodyInstance.h"
#include "Character/LyraHealthComponent.h"
#include "Physics/LyraCollisionChannels.h"

namespace
{
// Sample the same sequence time/root lock that the selected montage will play.
bool SampleGetUpPelvis(const UAnimMontage* Montage, float MontageTime, FTransform& OutPelvis)
{
    if (!Montage || Montage->SlotAnimTracks.IsEmpty()) return false;
    const FAnimSegment* Segment = Montage->SlotAnimTracks[0].AnimTrack.GetSegmentAtTime(MontageTime);
    const UAnimSequence* Sequence = Segment ? Cast<UAnimSequence>(Segment->GetAnimReference()) : nullptr;
    if (!Sequence || !Sequence->GetSkeleton()) return false;
    const auto& Skeleton = Sequence->GetSkeleton()->GetReferenceSkeleton();
    int32 BoneIndex = Skeleton.FindBoneIndex(TEXT("pelvis"));
    if (BoneIndex == INDEX_NONE) return false;
    const float Time = Segment->ConvertTrackPosToAnimPos(MontageTime);
    OutPelvis = FTransform::Identity;
    while (BoneIndex != INDEX_NONE)
    {
        FTransform Local;
        Sequence->GetBoneTransform(Local, FSkeletonPoseBoneIndex(BoneIndex), FAnimExtractContext(Time, false), false);
        if (BoneIndex == 0 && Sequence->bEnableRootMotion)
        {
            if (Sequence->RootMotionRootLock == ERootMotionRootLock::RefPose) Local = Skeleton.GetRefBonePose()[0];
            else if (Sequence->RootMotionRootLock == ERootMotionRootLock::Zero) Local = FTransform::Identity;
            else Sequence->GetBoneTransform(Local, FSkeletonPoseBoneIndex(0), FAnimExtractContext(0.0, false), false);
        }
        OutPelvis *= Local;
        BoneIndex = Skeleton.GetParentIndex(BoneIndex);
    }
    return true;
}
}

UBaselinePhysicalInteractionComponent::UBaselinePhysicalInteractionComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.TickGroup = TG_PostPhysics;
    SetIsReplicatedByDefault(true);
}

void UBaselinePhysicalInteractionComponent::BeginPlay()
{
    Super::BeginPlay();
    Character = Cast<ACharacter>(GetOwner());
    if (!Character) return;
    Controls = Character->FindComponentByClass<UPhysicsControlComponent>();
    auto* Mesh = Character->GetMesh();
    MeshRelative = Mesh->GetRelativeTransform();
    MeshCollisionProfile = Mesh->GetCollisionProfileName();
    CapsuleCollisionProfile = Character->GetCapsuleComponent()->GetCollisionProfileName();
    CapsuleResponses = Character->GetCapsuleComponent()->GetCollisionResponseToChannels();
    bSavedOrientToMovement = Character->GetCharacterMovement()->bOrientRotationToMovement;
    if (Controls && ControlProfile)
    {
        // The retarget source was intentionally non-colliding. Physics Control
        // still needs real body instances even while its profile is kinematic.
        Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        Mesh->SetCollisionResponseToAllChannels(ECR_Ignore);
        Mesh->SetCollisionResponseToChannel(Lyra_TraceChannel_Weapon, ECR_Block);
        Controls->PhysicsControlAsset = ControlProfile;
        Controls->bAttemptToRecreateDisabledControls = true;
        Controls->AddTickPrerequisiteComponent(Mesh);
        bControlsCreated = Controls->CreateControlsAndBodyModifiersFromPhysicsControlAsset(Mesh, nullptr, NAME_None);
        Controls->UpdateTargetCaches(GetWorld()->GetDeltaSeconds());
        Controls->InvokeControlProfile(TEXT("Kinematic"));
    }
    ApplyState();
}

void UBaselinePhysicalInteractionComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    if (IgnoredPartner.IsValid() && Character)
        IgnoredPartner->GetCapsuleComponent()->IgnoreActorWhenMoving(Character, false);
    if (Controls) Controls->DestroyAllControlsAndBodyModifiers();
    Super::EndPlay(Reason);
}

void UBaselinePhysicalInteractionComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(UBaselinePhysicalInteractionComponent, State);
    DOREPLIFETIME(UBaselinePhysicalInteractionComponent, ReplicatedPelvis);
}

float UBaselinePhysicalInteractionComponent::ServerNow() const
{
    const auto* GS = GetWorld()->GetGameState();
    return GS ? GS->GetServerWorldTimeSeconds() : GetWorld()->GetTimeSeconds();
}

bool UBaselinePhysicalInteractionComponent::CanInteract() const
{
    if (!Character || !bControlsCreated || IsBusy() || !Character->GetMesh()->GetAnimInstance()
        || !Character->GetCharacterMovement()->IsMovingOnGround()) return false;
    if (const auto* Health = ULyraHealthComponent::FindHealthComponent(Character))
        if (Health->IsDeadOrDying()) return false;
    if (const auto* Equipment = Character->FindComponentByClass<UBaselineEquipmentComponent>())
        if (Equipment->AreHandsBusy()) return false;
    return !Character->GetMesh()->GetAnimInstance()->IsAnyMontagePlaying();
}

bool UBaselinePhysicalInteractionComponent::CanReach(const ACharacter* Other) const
{
    if (!Other || Other == Character || !Other->IsActorInitialized()) return false;
    const auto* Physical = Other->FindComponentByClass<UBaselinePhysicalInteractionComponent>();
    if (!Physical || !Physical->CanInteract()) return false;
    const FVector Delta = Other->GetActorLocation() - Character->GetActorLocation();
    if (Delta.SizeSquared() > FMath::Square(InteractionDistance) || FMath::Abs(Delta.Z) > 75.f
        || FVector::DotProduct(Character->GetActorForwardVector(), Delta.GetSafeNormal2D()) < .25f) return false;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(BaselineInteraction), false, Character);
    Params.AddIgnoredActor(Other);
    FHitResult Hit;
    return !GetWorld()->LineTraceSingleByChannel(Hit, Character->GetActorLocation(), Other->GetActorLocation(), ECC_Visibility, Params);
}

ACharacter* UBaselinePhysicalInteractionComponent::FindInteractionTarget() const
{
    if (!CanInteract()) return nullptr;
    ACharacter* Best = nullptr;
    float BestDistance = FLT_MAX;
    for (TActorIterator<ACharacter> It(GetWorld()); It; ++It)
        if (CanReach(*It))
        {
            const float Distance = Character->GetSquaredDistanceTo(*It);
            if (Distance < BestDistance) { Best = *It; BestDistance = Distance; }
        }
    return Best;
}

void UBaselinePhysicalInteractionComponent::Shove() { ServerInteract(EBaselineInteraction::Shove); }
void UBaselinePhysicalInteractionComponent::Tackle() { ServerInteract(EBaselineInteraction::Tackle); }
void UBaselinePhysicalInteractionComponent::Takedown() { ServerInteract(EBaselineInteraction::Takedown); }
void UBaselinePhysicalInteractionComponent::ToggleRagdoll() { ServerToggleRagdoll(); }
void UBaselinePhysicalInteractionComponent::RequestRecovery() { ServerRecover(); }

void UBaselinePhysicalInteractionComponent::ServerToggleRagdoll_Implementation()
{
    if (State.Phase == EBaselinePhysicalPhase::Ragdoll) { ServerRecover(); return; }
    if (!Character || IsBusy() || !bControlsCreated) return;
    if (auto* Equipment = Character->FindComponentByClass<UBaselineEquipmentComponent>())
        if (Equipment->AreHandsBusy()) return;
    StartRagdoll(Character->GetVelocity() + Character->GetActorForwardVector() * 180.f);
}

void UBaselinePhysicalInteractionComponent::CommitState(FBaselinePhysicalState NewState)
{
    check(GetOwner()->HasAuthority());
    NewState.Revision = State.Revision + 1;
    NewState.ServerTime = ServerNow();
    State = MoveTemp(NewState);
    ApplyState();
    GetOwner()->ForceNetUpdate();
}

void UBaselinePhysicalInteractionComponent::StartRagdoll(FVector Velocity)
{
    if (!Character || !Character->HasAuthority() || !bControlsCreated || State.Phase == EBaselinePhysicalPhase::Ragdoll) return;
    if (const auto* Health = ULyraHealthComponent::FindHealthComponent(Character))
        if (Health->IsDeadOrDying()) return;
    FBaselinePhysicalState Next;
    Next.Phase = EBaselinePhysicalPhase::Ragdoll;
    Next.StartTransform = Character->GetActorTransform();
    Next.Velocity = Velocity.GetClampedToMaxSize(2500.f);
    CommitState(Next);
}

void UBaselinePhysicalInteractionComponent::StartDeathRagdoll(FVector Velocity)
{
    if (!Character || !Character->HasAuthority() || !bControlsCreated) return;
    if (State.Phase == EBaselinePhysicalPhase::Interaction)
    {
        ACharacter* Partner = State.Role == TEXT("Attacker") ? State.Victim.Get() : State.Attacker.Get();
        if (Partner)
            if (auto* Other = Partner->FindComponentByClass<UBaselinePhysicalInteractionComponent>();
                Other && Other->State.Phase == EBaselinePhysicalPhase::Interaction)
            {
                Partner->GetMesh()->GetAnimInstance()->Montage_Stop(.15f);
                Other->FinishAction();
            }
    }
    FBaselinePhysicalState Next;
    Next.Phase = EBaselinePhysicalPhase::Dead;
    Next.Velocity = Velocity.GetClampedToMaxSize(2500.f);
    CommitState(Next);
}

void UBaselinePhysicalInteractionComponent::ServerInteract_Implementation(EBaselineInteraction Type)
{
    if (!CanInteract() || ServerNow() - LastRequestTime < .3f) return;
    LastRequestTime = ServerNow();
    ACharacter* Target = FindInteractionTarget();
    if (!Target) { LastResult = TEXT("Move closer and face a ready training partner"); return; }
    auto* Other = Target->FindComponentByClass<UBaselinePhysicalInteractionComponent>();
    TArray<UPoseSearchDatabase*> Databases;
    if (Type == EBaselineInteraction::Shove) Databases.Add(ShoveDatabase);
    else if (Type == EBaselineInteraction::Tackle) Databases.Add(TackleDatabase);
    else if (Type == EBaselineInteraction::Takedown)
    {
        // The sample supplies separate standing, walking and running coverage.
        const float Speed = Character->GetVelocity().Size2D();
        const int32 Index = Speed < 100.f ? 0 : Speed < 400.f ? 1 : 2;
        if (TakedownDatabases.IsValidIndex(Index)) Databases.Add(TakedownDatabases[Index]);
    }
    TArray<FPoseSearchMotionMatchMultiQuery> Queries;
    for (auto* Database : Databases)
    {
        if (!Database) continue;
        auto& Query = Queries.AddDefaulted_GetRef();
        Query.Database = Database;
        auto& A = Query.AnimContextsRoles.AddDefaulted_GetRef();
        A.AnimContext = Character->GetMesh()->GetAnimInstance(); A.Roles.Add(TEXT("Attacker"));
        auto& B = Query.AnimContextsRoles.AddDefaulted_GetRef();
        B.AnimContext = Target->GetMesh()->GetAnimInstance(); B.Roles.Add(TEXT("Victim"));
    }
    TArray<FPoseSearchBlueprintResult> Results;
    UPoseSearchInteractionLibrary::MotionMatchMulti(Queries, TEXT("PoseHistory"), {}, Results);
    if (Results.Num() != 2) { LastResult = TEXT("No matching paired animation"); return; }
    FBaselinePhysicalState Next[2];
    for (auto& Result : Results)
    {
        const int32 Index = UPoseSearchLibrary::GetActor(Result) == Character ? 0 : 1;
        auto& S = Next[Index];
        S.Phase = EBaselinePhysicalPhase::Interaction;
        S.Montage = Cast<UAnimMontage>(Result.GetAnimationAssetForRole());
        S.Interaction = Cast<UPoseSearchInteractionAsset>(Result.SelectedAnim);
        S.Database = const_cast<UPoseSearchDatabase*>(Result.SelectedDatabase.Get());
        if (!S.Montage || !S.Interaction || Result.bIsMirrored) { LastResult = TEXT("Unsupported interaction result"); return; }
        S.Attacker = Character; S.Victim = Target;
        S.Role = Result.Role; S.RoleIndex = Result.RoleIndex;
        S.Roots = Result.ActorRootTransforms; S.RootBones = Result.ActorRootBoneTransforms;
        S.StartTime = Result.SelectedTime;
        S.StartTransform = (Index == 0 ? Character.Get() : Target)->GetActorTransform();
        // Preserve the sample's authored contact/release timing without requiring its Mover-only notify.
        for (const auto& Notify : S.Montage->Notifies)
            if (Notify.Notify && Notify.Notify->GetClass()->GetName().Contains(TEXT("TriggerRagdoll")))
                S.RagdollAt = Notify.GetTriggerTime();
        if (S.RagdollAt < 0.f && (Index == 1 || Type == EBaselineInteraction::Tackle))
            S.RagdollAt = S.Montage->GetPlayLength() - .15f;
        LastSearchCost = Other->LastSearchCost = Result.SearchCost;
    }
    if (!Next[0].Montage || !Next[1].Montage) return;
    // Both decisions are validated before either participant is reserved.
    CommitState(Next[0]); Other->CommitState(Next[1]);
    LastResult = TEXT("Paired motion match started");
}

FPoseSearchBlueprintResult UBaselinePhysicalInteractionComponent::GetInteractionResult() const
{
    FPoseSearchBlueprintResult Result;
    if (!State.Interaction) return Result;
    Result.SelectedAnim = State.Interaction; Result.SelectedTime = State.StartTime;
    Result.SelectedDatabase = State.Database;
    Result.Role = State.Role; Result.RoleIndex = State.RoleIndex; Result.bIsInteraction = true;
    Result.ActorRootTransforms = State.Roots; Result.ActorRootBoneTransforms = State.RootBones;
    Result.AnimContexts.SetNum(2);
    // The schema order is Attacker, Victim; transient instances are resolved locally.
    if (State.Attacker) Result.AnimContexts[0] = State.Attacker->GetMesh()->GetAnimInstance();
    if (State.Victim) Result.AnimContexts[1] = State.Victim->GetMesh()->GetAnimInstance();
    return Result;
}

void UBaselinePhysicalInteractionComponent::ServerRecover_Implementation()
{
    if (!Character || State.Phase != EBaselinePhysicalPhase::Ragdoll || PhaseAge < .65f || !GetUpDatabase) return;
    if (const auto* Health = ULyraHealthComponent::FindHealthComponent(Character))
        if (Health->IsDeadOrDying()) return;
    auto* Mesh = Character->GetMesh();
    if (Mesh->GetPhysicsLinearVelocity(TEXT("pelvis")).Size() > 350.f) return;
    const FVector Pelvis = Mesh->GetSocketLocation(TEXT("pelvis"));
    FCollisionQueryParams Params(SCENE_QUERY_STAT(BaselineGetUp), false, Character);
    FHitResult Ground;
    if (!GetWorld()->LineTraceSingleByChannel(Ground, Pelvis + FVector(0,0,40), Pelvis - FVector(0,0,160), ECC_Visibility, Params)
        || Ground.ImpactNormal.Z < .65f) return;
    const float HalfHeight = Character->GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight();
    const float Radius = Character->GetCapsuleComponent()->GetUnscaledCapsuleRadius();
    FVector Position = Ground.ImpactPoint + FVector(0,0,HalfHeight + 3.f);
    auto* Anim = Mesh->GetAnimInstance();
    UPoseSearchLibrary::OverridePoseHistoryFromOwningMesh(Anim, TEXT("PoseHistory"));
    FPoseSearchBlueprintResult Match;
    UPoseSearchLibrary::MotionMatch(Anim, {GetUpDatabase}, TEXT("PoseHistory"), {}, {}, Match);
    auto* Montage = Cast<UAnimMontage>(Match.SelectedAnim);
    if (!Montage || Match.bIsMirrored) { LastResult = TEXT("No matching get-up pose"); return; }
    FBaselinePhysicalState Next;
    Next.Phase = EBaselinePhysicalPhase::Recovery;
    Next.Montage = Montage; Next.StartTime = Match.SelectedTime;
    // Align the selected get-up to the physical pelvis. A bone's Y axis is
    // not character facing once the body lies on its front, back or side.
    FTransform AnimatedPelvis;
    if (!SampleGetUpPelvis(Montage, Next.StartTime, AnimatedPelvis)) return;
    const FQuat LocalRotation = MeshRelative.GetRotation() * AnimatedPelvis.GetRotation();
    const FQuat PhysicalRotation = Mesh->GetSocketQuaternion(TEXT("pelvis"));
    float SinYaw = 0.f, CosYaw = 0.f;
    for (const FVector Axis : {FVector::ForwardVector, FVector::RightVector, FVector::UpVector})
    {
        const FVector From = LocalRotation.RotateVector(Axis);
        const FVector To = PhysicalRotation.RotateVector(Axis);
        SinYaw += From.X * To.Y - From.Y * To.X;
        CosYaw += From.X * To.X + From.Y * To.Y;
    }
    const float Yaw = FMath::RadiansToDegrees(FMath::Atan2(SinYaw, CosYaw));
    const FRotator Facing(0, Yaw, 0);
    const FVector PelvisOffset = Facing.RotateVector(MeshRelative.TransformPosition(AnimatedPelvis.GetLocation()));
    Position.X = Pelvis.X - PelvisOffset.X;
    Position.Y = Pelvis.Y - PelvisOffset.Y;
    if (GetWorld()->OverlapBlockingTestByChannel(Position, FQuat::Identity, ECC_Pawn,
        FCollisionShape::MakeCapsule(Radius, HalfHeight), Params)) { LastResult = TEXT("Not enough room to stand"); return; }
    Next.StartTransform = FTransform(Facing, Position);
    LastGetUp = Montage;
    LastSearchCost = Match.SearchCost;
    CommitState(Next);
}

void UBaselinePhysicalInteractionComponent::RestoreMesh()
{
    auto* Mesh = Character->GetMesh();
    if (Controls) Controls->InvokeControlProfile(TEXT("Kinematic"));
    Mesh->SetAllBodiesSimulatePhysics(false);
    Mesh->SetSimulatePhysics(false);
    for (int32 Index = 0; Index < Mesh->Bodies.Num(); ++Index)
        if (FBodyInstance* Body = Mesh->Bodies[Index]; Body && SavedAngularDamping.IsValidIndex(Index))
        {
            Body->AngularDamping = SavedAngularDamping[Index];
            Body->UpdateDampingProperties();
        }
    SavedAngularDamping.Reset();
    Mesh->SetConstraintProfileForAll(NAME_None, true);
    Mesh->AttachToComponent(Character->GetCapsuleComponent(), FAttachmentTransformRules::KeepWorldTransform);
    Mesh->SetRelativeTransform(MeshRelative);
    Mesh->SetCollisionProfileName(MeshCollisionProfile);
    Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    Mesh->SetCollisionResponseToAllChannels(ECR_Ignore);
    Mesh->SetCollisionResponseToChannel(Lyra_TraceChannel_Weapon, ECR_Block);
    // A body reattached after simulation can update its parent's collision
    // responses. Restore the entire capsule contract after changing mesh bodies.
    Character->GetCapsuleComponent()->SetCollisionProfileName(CapsuleCollisionProfile);
    Character->GetCapsuleComponent()->SetCollisionResponseToChannels(CapsuleResponses);
    Character->GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
}

void UBaselinePhysicalInteractionComponent::OnRep_State() { ApplyState(); }

void UBaselinePhysicalInteractionComponent::ApplyState()
{
    if (!Character || !bControlsCreated) return;
    auto* Mesh = Character->GetMesh();
    auto* Anim = Mesh->GetAnimInstance();
    auto* Move = Character->GetCharacterMovement();
    const bool bWasPhysical = AppliedPhase == EBaselinePhysicalPhase::Ragdoll || AppliedPhase == EBaselinePhysicalPhase::Dead;
    const bool bPhysical = State.Phase == EBaselinePhysicalPhase::Ragdoll || State.Phase == EBaselinePhysicalPhase::Dead;
    const bool bLeavingRagdoll = bWasPhysical && !bPhysical;
    if (auto* Equipment = Character->FindComponentByClass<UBaselineEquipmentComponent>())
        if (auto* Presentation = Equipment->GetPresentationMesh(); Presentation && Presentation != Mesh)
            Presentation->AddTickPrerequisiteComponent(this);
    PhaseAge = FMath::Max(0.f, ServerNow() - State.ServerTime);
    RestReference.Reset();
    RestAge = 0.f;
    if (IgnoredPartner.IsValid()) Character->GetCapsuleComponent()->IgnoreActorWhenMoving(IgnoredPartner.Get(), false);
    IgnoredPartner.Reset();
    if (bLeavingRagdoll)
    {
        const FTransform PhysicalMeshWorld = Mesh->GetComponentTransform();
        FPoseSnapshot Snapshot;
        Anim->SnapshotPose(Snapshot);
        Snapshot.SnapshotName = TEXT("BaselineRagdoll");
        RestoreMesh();
        if (State.Phase == EBaselinePhysicalPhase::Recovery)
        {
            // Snapshot bones are local to the detached, rotated physics mesh.
            // Rebase its root into the upright recovery mesh so every bone
            // starts at the same world position after capsule reattachment.
            Character->SetActorTransform(State.StartTransform, false, nullptr, ETeleportType::TeleportPhysics);
            if (Snapshot.bIsValid && !Snapshot.LocalTransforms.IsEmpty())
            {
                const FTransform RebasedRoot = (Snapshot.LocalTransforms[0] * PhysicalMeshWorld).GetRelativeTransform(Mesh->GetComponentTransform());
                const auto& Skeleton = Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
                const FTransform NeutralRoot = Skeleton.GetRefBonePose()[0];
                // Keep the recovery root upright and carry the physical pose
                // in its children. Blending a rolled root AND pelvis otherwise
                // makes the hips/head arc through the floor between poses.
                for (int32 Index = 1; Index < Snapshot.LocalTransforms.Num(); ++Index)
                {
                    const int32 Bone = Skeleton.FindBoneIndex(Snapshot.BoneNames[Index]);
                    if (Bone != INDEX_NONE && Skeleton.GetParentIndex(Bone) == 0)
                        Snapshot.LocalTransforms[Index] = (Snapshot.LocalTransforms[Index] * RebasedRoot).GetRelativeTransform(NeutralRoot);
                }
                Snapshot.LocalTransforms[0] = NeutralRoot;
            }
        }
        Anim->AddPoseSnapshot(TEXT("BaselineRagdoll")) = MoveTemp(Snapshot);
        if (auto* Source = Cast<UBaselineSourceAnimInstance>(Anim)) Source->StartRecoveryBlend();
    }
    if (auto* Source = Cast<UBaselineSourceAnimInstance>(Anim))
        Source->RecoveryAnimationWeight = State.Phase == EBaselinePhysicalPhase::Recovery ? 1.f : 0.f;
    if (auto* BaselineMove = Cast<UBaselineCharacterMovement>(Move)) BaselineMove->SetSlideRequested(false);
    Move->StopMovementImmediately();
    if (bPhysical)
    {
        if (!bWasPhysical)
        {
            Anim->Montage_Stop(.15f);
            Move->DisableMovement();
            Character->GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
            Mesh->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform);
            Mesh->SetCollisionProfileName(TEXT("Ragdoll"));
            Mesh->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
            Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
            Mesh->SetAllBodiesSimulatePhysics(true);
            // The physics asset also has its own angular motors, independent of
            // Physics Control. Leave both sets passive instead of pulling limbs
            // toward the asset's reference pose while they contact the floor.
            Mesh->SetAllMotorsAngularPositionDrive(false, false);
            Mesh->SetAllMotorsAngularVelocityDrive(false, false);
            // Give every passive limb rotational drag. The sample's zero damping
            // lets repeated floor contacts keep small limbs oscillating at rest.
            SavedAngularDamping.Reset(Mesh->Bodies.Num());
            for (FBodyInstance* Body : Mesh->Bodies)
            {
                SavedAngularDamping.Add(Body ? Body->AngularDamping : 0.f);
                if (Body)
                {
                    Body->AngularDamping = FMath::Max(Body->AngularDamping, 2.f);
                    Body->UpdateDampingProperties();
                }
            }
            Controls->UpdateTargetCaches(GetWorld()->GetDeltaSeconds());
            Controls->InvokeControlProfile(TEXT("Ragdoll"));
            // The sample's ragdoll profile powers the joints toward the animation.
            // Leave this fall passive: gravity, contacts and the physics asset's
            // joint limits should settle the body, with no pose motors fighting it.
            Controls->SetControlsInSetEnabled(TEXT("All"), false);
            FPhysicsControlModifierData RagdollBodies;
            RagdollBodies.bEnableCCD = true;
            Controls->SetBodyModifierDatasInSet(TEXT("All"), RagdollBodies);
            Mesh->SetAllPhysicsLinearVelocity(State.Velocity);
            Mesh->WakeAllRigidBodies();
        }
    }
    else if (State.Phase == EBaselinePhysicalPhase::Locomotion)
    {
        Character->GetCapsuleComponent()->SetCollisionProfileName(CapsuleCollisionProfile);
        Character->GetCapsuleComponent()->SetCollisionResponseToChannels(CapsuleResponses);
        Character->GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        Move->bForceNextFloorCheck = true;
        Move->bOrientRotationToMovement = bSavedOrientToMovement;
        Move->SetMovementMode(MOVE_Walking);
    }
    else
    {
        if (State.Phase == EBaselinePhysicalPhase::Recovery)
        {
            Character->SetActorTransform(State.StartTransform, false, nullptr, ETeleportType::TeleportPhysics);
            LastGetUp = State.Montage;
        }
        else
        {
            IgnoredPartner = State.Role == TEXT("Attacker") ? State.Victim.Get() : State.Attacker.Get();
            if (IgnoredPartner.IsValid()) Character->GetCapsuleComponent()->IgnoreActorWhenMoving(IgnoredPartner.Get(), true);
        }
        Move->bOrientRotationToMovement = false;
        Move->SetMovementMode(MOVE_Flying);
        if (State.Montage)
        {
            const float Position = FMath::Min(State.StartTime + PhaseAge, State.Montage->GetPlayLength() - .01f);
            if (State.Phase == EBaselinePhysicalPhase::Recovery)
                // The physical snapshot supplies the blend-in. Blending the
                // montage from locomotion as well pulls the body upright first.
                Anim->Montage_PlayWithBlendIn(State.Montage, FAlphaBlendArgs(0.f), 1.f, EMontagePlayReturnType::MontageLength, Position);
            else Anim->Montage_Play(State.Montage, 1.f, EMontagePlayReturnType::MontageLength, Position);
        }
    }
    AppliedPhase = State.Phase;
    Controls->SetComponentTickEnabled(bPhysical);
    if (bLeavingRagdoll && State.Phase == EBaselinePhysicalPhase::Recovery)
    {
        // Automatic recovery starts after physics, after the normal animation
        // tick. Publish the rebased snapshot now rather than rendering one
        // frame of old bone transforms under the newly upright component.
        Mesh->TickAnimation(0.f, false);
        Mesh->RefreshBoneTransforms();
    }
}

void UBaselinePhysicalInteractionComponent::FinishAction()
{
    FBaselinePhysicalState Next;
    CommitState(Next);
}

void UBaselinePhysicalInteractionComponent::OnRep_Pelvis()
{
    if (!Character || (State.Phase != EBaselinePhysicalPhase::Ragdoll && State.Phase != EBaselinePhysicalPhase::Dead)) return;
    auto* Mesh = Character->GetMesh();
    const FVector Error = FVector(ReplicatedPelvis) - Mesh->GetSocketLocation(TEXT("pelvis"));
    if (Error.SizeSquared() > FMath::Square(30.f))
        if (const FBodyInstance* RootBody = Mesh->GetBodyInstance())
            Mesh->SetAllPhysicsPosition(RootBody->GetUnrealWorldTransform().GetLocation() + Error);
}

void UBaselinePhysicalInteractionComponent::UpdatePassiveRest(float DeltaTime)
{
    auto* Mesh = Character->GetMesh();
    // Let the modifier apply once, then leave passive bodies to Chaos. Reapplying
    // simulated movement settings every frame can interfere with island sleep.
    if (PhaseAge > .2f) Controls->SetComponentTickEnabled(false);
    if (PhaseAge < 1.f) return;

    const FVector Pelvis = Mesh->GetSocketLocation(TEXT("pelvis"));
    FHitResult Ground;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(RagdollRest), false, Character);
    const bool bGrounded = GetWorld()->LineTraceSingleByChannel(Ground, Pelvis,
        Pelvis - FVector(0, 0, 55.f), ECC_WorldStatic, Params) && Ground.Normal.Z > .5f;
    bool bQuiet = bGrounded && RestReference.Num() == Mesh->Bodies.Num();
    for (int32 Index = 0; bQuiet && Index < Mesh->Bodies.Num(); ++Index)
        if (const FBodyInstance* Body = Mesh->Bodies[Index])
        {
            const FTransform Pose = Body->GetUnrealWorldTransform();
            bQuiet = Body->GetUnrealWorldVelocity().SizeSquared() < FMath::Square(25.f)
                && FVector::DistSquared(Pose.GetLocation(), RestReference[Index].GetLocation()) < FMath::Square(2.f)
                && Pose.GetRotation().AngularDistance(RestReference[Index].GetRotation()) < FMath::DegreesToRadians(7.f);
        }
    if (!bQuiet)
    {
        RestAge = 0.f;
        RestReference.Reset(Mesh->Bodies.Num());
        for (const FBodyInstance* Body : Mesh->Bodies)
            RestReference.Add(Body ? Body->GetUnrealWorldTransform() : FTransform::Identity);
        return;
    }
    RestAge += DeltaTime;
    if (RestAge >= .65f)
    {
        // Sleep the complete jointed island after a quiet grounded interval.
        // Simulation remains enabled: impacts/impulses wake it normally.
        Mesh->PutAllRigidBodiesToSleep();
        RestAge = 0.f;
        RestReference.Reset();
    }
}

void UBaselinePhysicalInteractionComponent::TickComponent(float Dt, ELevelTick TickType, FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(Dt, TickType, TickFunction);
    if (!Character || !bControlsCreated) return;
    PhaseAge += Dt;
    // Lyra death owns disabling collision and movement. A pending interaction
    // must never restore those or stand up a character that died mid-action.
    if (const auto* Health = ULyraHealthComponent::FindHealthComponent(Character))
        if (Health->IsDeadOrDying() && State.Phase != EBaselinePhysicalPhase::Dead) return;
    auto* Mesh = Character->GetMesh();
    auto* Move = Character->GetCharacterMovement();
    if (State.Phase == EBaselinePhysicalPhase::Ragdoll || State.Phase == EBaselinePhysicalPhase::Dead)
    {
        UpdatePassiveRest(Dt);
        const FVector Pelvis = Mesh->GetSocketLocation(TEXT("pelvis"));
        // Follow the body with the camera/capsule without dragging the simulation.
        Character->SetActorLocation(Pelvis + FVector(0,0,35.f), false, nullptr, ETeleportType::None);
        if (Character->HasAuthority())
        {
            NetAccumulator += Dt;
            if (NetAccumulator > .066f) { ReplicatedPelvis = Pelvis; NetAccumulator = 0.f; Character->ForceNetUpdate(); }
            if (State.Phase == EBaselinePhysicalPhase::Ragdoll && bAutoRecover && PhaseAge > AutoRecoveryDelay) ServerRecover();
        }
    }
    if (!Character->HasAuthority()) return;
    if (State.Phase == EBaselinePhysicalPhase::Interaction || State.Phase == EBaselinePhysicalPhase::Recovery)
    {
        const float Position = State.StartTime + PhaseAge;
        const bool bMontageStopped = PhaseAge > .2f && !Mesh->GetAnimInstance()->Montage_IsPlaying(State.Montage);
        if (State.RagdollAt >= 0.f && (Position >= State.RagdollAt || bMontageStopped))
            StartRagdoll(Move->Velocity + Character->GetActorForwardVector() * 80.f);
        else if (!State.Montage || Position >= State.Montage->GetPlayLength() - .05f
            || bMontageStopped) FinishAction();
    }
    else if (!IsBusy() && Move->IsFalling() && Move->Velocity.Z < -FallRagdollSpeed)
        StartRagdoll(Move->Velocity);
}

void UBaselineSourceAnimInstance::NativeUpdateAnimation(float DeltaSeconds)
{
    Super::NativeUpdateAnimation(DeltaSeconds);
    const APawn* Pawn = TryGetPawnOwner();
    const auto* Roll = Pawn ? Pawn->FindComponentByClass<UCRRollComponent>() : nullptr;
    const auto* Movement = Pawn ? Pawn->FindComponentByClass<UBaselineCharacterMovement>() : nullptr;
    const auto* Equipment = Pawn ? Pawn->FindComponentByClass<UBaselineEquipmentComponent>() : nullptr;
    const float ThrowWeight = GetSlotMontageLocalWeight(TEXT("ThrowUpperBody"));
    ThrowRootRotation = FRotator::ZeroRotator;
    if (Movement && Movement->IsSliding() && Equipment && ThrowWeight > 0.f)
        ThrowRootRotation.Yaw = FMath::Clamp(FRotator::NormalizeAxis(Equipment->GetWeaponAimRotation().Yaw-Pawn->GetActorRotation().Yaw),-85.f,85.f)*ThrowWeight;
    LocomotionCorrectionBypassWeight = FMath::Max(RecoveryAnimationWeight,
        Roll && Roll->IsRolling() ? 1.f : 0.f);
    if (RecoveryPoseWeight > 0.f && GetWorld())
    {
        // Network root-motion updates/replays can tick animation repeatedly in
        // one world frame. They must not consume the physical-pose blend early.
        const float Age = float(GetWorld()->GetTimeSeconds() - RecoveryBlendStartTime);
        const float Alpha = FMath::Clamp(Age / .45f, 0.f, 1.f);
        RecoveryPoseWeight = 1.f - Alpha * Alpha * (3.f - 2.f * Alpha);
    }
}

void UBaselineSourceAnimInstance::StartRecoveryBlend()
{
    RecoveryBlendStartTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
    RecoveryPoseWeight = 1.f;
}
