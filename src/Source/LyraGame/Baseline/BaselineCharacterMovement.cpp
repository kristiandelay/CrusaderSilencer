#include "BaselineCharacterMovement.h"
#include "BaselinePhysicalInteraction.h"
#include "Crusader/CRCrowdAI.h"
#include "GameFramework/Character.h"
#include "Net/UnrealNetwork.h"

namespace
{
class FBaselineSavedMove final : public FSavedMove_Character
{
public:
    using Super = FSavedMove_Character;
    bool bSavedWantsSlide = false;
    bool bSavedSliding = false;
    virtual void Clear() override
    {
        Super::Clear();
        bSavedWantsSlide = bSavedSliding = false;
    }
    virtual uint8 GetCompressedFlags() const override
    {
        return Super::GetCompressedFlags() | (bSavedWantsSlide ? FLAG_Custom_0 : 0);
    }
    virtual bool CanCombineWith(const FSavedMovePtr& NewMove, ACharacter* Character, float MaxDelta) const override
    {
        const auto* Other = static_cast<const FBaselineSavedMove*>(NewMove.Get());
        return bSavedWantsSlide == Other->bSavedWantsSlide && bSavedSliding == Other->bSavedSliding
            && Super::CanCombineWith(NewMove, Character, MaxDelta);
    }
    virtual void SetMoveFor(ACharacter* Character, float InDeltaTime, FVector const& NewAccel,
        FNetworkPredictionData_Client_Character& ClientData) override
    {
        Super::SetMoveFor(Character, InDeltaTime, NewAccel, ClientData);
        const auto* Movement = CastChecked<UBaselineCharacterMovement>(Character->GetCharacterMovement());
        bSavedWantsSlide = Movement->bWantsToSlide;
        bSavedSliding = Movement->IsSliding();
    }
    virtual void PrepMoveFor(ACharacter* Character) override
    {
        Super::PrepMoveFor(Character);
        auto* Movement = CastChecked<UBaselineCharacterMovement>(Character->GetCharacterMovement());
        Movement->bWantsToSlide = bSavedWantsSlide;
        Movement->RestorePredictedSlide(bSavedSliding);
    }
};

class FBaselinePredictionData final : public FNetworkPredictionData_Client_Character
{
public:
    explicit FBaselinePredictionData(const UCharacterMovementComponent& Movement)
        : FNetworkPredictionData_Client_Character(Movement) {}
    virtual FSavedMovePtr AllocateNewMove() override { return FSavedMovePtr(new FBaselineSavedMove()); }
};
}

UBaselineCharacterMovement::UBaselineCharacterMovement(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    SetIsReplicatedByDefault(true);
}

void UBaselineCharacterMovement::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME_CONDITION(UBaselineCharacterMovement, bSliding, COND_SimulatedOnly);
}

bool UBaselineCharacterMovement::CanStartSlide() const
{
    return IsMovingOnGround() && CurrentFloor.IsWalkableFloor() && !HasAnimRootMotion()
        && Velocity.SizeSquared2D() >= FMath::Square(SlideMinimumStartSpeed)
        && Super::GetMaxSpeed() > 0.f;
}

void UBaselineCharacterMovement::SetSliding(bool bNewSliding)
{
    if (bSliding != bNewSliding)
    {
        bSliding = bNewSliding;
        OnSlideChanged.Broadcast(bSliding);
    }
}

void UBaselineCharacterMovement::OnRep_Sliding()
{
    OnSlideChanged.Broadcast(bSliding);
}

void UBaselineCharacterMovement::UpdateCharacterStateBeforeMovement(float DeltaSeconds)
{
    if (bWantsToSlide && !bSliding)
    {
        if (CanStartSlide())
        {
            bWantsToCrouch = true;
            Velocity += Velocity.GetSafeNormal2D() * SlideEntryBoost;
            SetSliding(true);
        }
        else bWantsToSlide = false;
    }
    if (bSliding && (!bWantsToSlide || !IsMovingOnGround() || Velocity.Size2D() < SlideExitSpeed))
    {
        bWantsToSlide = false;
        SetSliding(false);
    }
    Super::UpdateCharacterStateBeforeMovement(DeltaSeconds);
}

void UBaselineCharacterMovement::UpdateCharacterStateAfterMovement(float DeltaSeconds)
{
    Super::UpdateCharacterStateAfterMovement(DeltaSeconds);
    if (bSliding && (!IsMovingOnGround() || !IsCrouching() || Velocity.Size2D() < SlideExitSpeed))
    {
        bWantsToSlide = false;
        SetSliding(false);
    }
}

float UBaselineCharacterMovement::GetMaxSpeed() const
{
    if (CharacterOwner)
        if (auto* Physical = CharacterOwner->FindComponentByClass<UBaselinePhysicalInteractionComponent>())
            if (Physical->IsBusy()) return 0.f;
    float NormalSpeed = Super::GetMaxSpeed();
    if (NormalSpeed>0.f && CharacterOwner)
        if (const auto* Agent=CharacterOwner->FindComponentByClass<UCRCrowdAgentComponent>();Agent && Agent->bEnabled)
            NormalSpeed=IsCrouching() ? FMath::Min(Agent->DesiredSpeed,MaxWalkSpeedCrouched) : Agent->DesiredSpeed;
    return bSliding && NormalSpeed > 0.f ? SlideMaximumSpeed : NormalSpeed;
}

float UBaselineCharacterMovement::GetMaxAcceleration() const
{
    if (CharacterOwner)
        if (auto* Physical = CharacterOwner->FindComponentByClass<UBaselinePhysicalInteractionComponent>())
            if (Physical->IsBusy()) return 0.f;
    return Super::GetMaxAcceleration();
}

void UBaselineCharacterMovement::CalcVelocity(float DeltaTime, float Friction, bool bFluid, float BrakingDeceleration)
{
    if (!bSliding || !IsMovingOnGround() || HasAnimRootMotion())
    {
        Super::CalcVelocity(DeltaTime, Friction, bFluid, BrakingDeceleration);
        return;
    }
    // CMC still performs the floor following, sweeps, step handling and collision response.
    // Only its velocity integration changes: gravity along the slope, drag, limited steering.
    FVector Planar = FVector(Velocity.X, Velocity.Y, 0.f);
    const float Speed = Planar.Size();
    const float ReducedSpeed = FMath::Max(0.f, Speed - (SlideBraking + Speed * SlideDrag) * DeltaTime);
    FVector Direction = Planar.GetSafeNormal();
    if (!Acceleration.IsNearlyZero() && Speed > UE_SMALL_NUMBER)
    {
        const FRotator Current = Direction.Rotation();
        const FRotator Desired = Acceleration.GetSafeNormal2D().Rotation();
        Direction = FMath::RInterpConstantTo(Current, Desired, DeltaTime, SlideSteeringDegreesPerSecond).Vector();
    }
    const FVector SlopeGravity = FVector::VectorPlaneProject(
        FVector(0.f, 0.f, GetGravityZ() * SlideGravityScale), CurrentFloor.HitResult.ImpactNormal);
    Planar = Direction * ReducedSpeed + FVector(SlopeGravity.X, SlopeGravity.Y, 0.f) * DeltaTime;
    Velocity = Planar.GetClampedToMaxSize(SlideMaximumSpeed);
}

void UBaselineCharacterMovement::PhysicsRotation(float DeltaTime)
{
    if (CharacterOwner)
        if (auto* Physical = CharacterOwner->FindComponentByClass<UBaselinePhysicalInteractionComponent>())
            if (Physical->IsBusy()) return;
    if (bSliding && UpdatedComponent && !Velocity.IsNearlyZero())
    {
        const FRotator Facing = FMath::RInterpTo(UpdatedComponent->GetComponentRotation(),
            Velocity.GetSafeNormal2D().Rotation(), DeltaTime, 12.f);
        MoveUpdatedComponent(FVector::ZeroVector, Facing, false);
    }
    else Super::PhysicsRotation(DeltaTime);
}

FNetworkPredictionData_Client* UBaselineCharacterMovement::GetPredictionData_Client() const
{
    if (!ClientPredictionData)
        const_cast<UBaselineCharacterMovement*>(this)->ClientPredictionData = new FBaselinePredictionData(*this);
    return ClientPredictionData;
}

void UBaselineCharacterMovement::UpdateFromCompressedFlags(uint8 Flags)
{
    Super::UpdateFromCompressedFlags(Flags);
    bWantsToSlide = (Flags & FSavedMove_Character::FLAG_Custom_0) != 0;
}
