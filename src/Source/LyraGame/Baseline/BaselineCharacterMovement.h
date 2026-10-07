#pragma once

#include "Character/LyraCharacterMovementComponent.h"
#include "BaselineCharacterMovement.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FBaselineSlideChanged, bool, bSliding);

/** Momentum slide integrated with CMC floor sweeps, crouch clearance and prediction. */
UCLASS(BlueprintType, Blueprintable)
class UBaselineCharacterMovement : public ULyraCharacterMovementComponent
{
    GENERATED_BODY()
public:
    UBaselineCharacterMovement(const FObjectInitializer& ObjectInitializer = FObjectInitializer::Get());
    UFUNCTION(BlueprintCallable, Category="Baseline|Movement")
    void SetSlideRequested(bool bRequested) { bWantsToSlide = bRequested; }
    UFUNCTION(BlueprintPure, Category="Baseline|Movement")
    bool IsSliding() const { return bSliding; }
    UFUNCTION(BlueprintPure, Category="Baseline|Movement")
    bool CanStartSlide() const;
    UFUNCTION(BlueprintPure, Category="Baseline|Movement")
    bool CanCancelSlide() const { return bSliding && SlideMinimumTimeRemaining <= 0.f; }
    UFUNCTION(BlueprintPure, Category="Baseline|Movement")
    float GetSlideRecoveryRemaining() const { return SlideRecoveryRemaining; }

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Baseline|Slide", meta=(ClampMin="0", Units="s"))
    float SlideMinimumDuration = .35f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Baseline|Slide", meta=(ClampMin="0", Units="s"))
    float SlideRecoveryDuration = .65f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Baseline|Slide", meta=(ClampMin="0"))
    float SlideMinimumStartSpeed = 550.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Baseline|Slide", meta=(ClampMin="0"))
    float SlideExitSpeed = 180.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Baseline|Slide", meta=(ClampMin="0"))
    float SlideEntryBoost = 100.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Baseline|Slide", meta=(ClampMin="0"))
    float SlideMaximumSpeed = 1400.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Baseline|Slide", meta=(ClampMin="0"))
    float SlideDrag = 0.15f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Baseline|Slide", meta=(ClampMin="0"))
    float SlideBraking = 180.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Baseline|Slide", meta=(ClampMin="0"))
    float SlideGravityScale = 1.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Baseline|Slide", meta=(ClampMin="0"))
    float SlideSteeringDegreesPerSecond = 40.f;
    UPROPERTY(BlueprintAssignable, Category="Baseline|Slide")
    FBaselineSlideChanged OnSlideChanged;

    virtual void CalcVelocity(float DeltaTime, float Friction, bool bFluid, float BrakingDeceleration) override;
    virtual float GetMaxSpeed() const override;
    virtual float GetMaxAcceleration() const override;
    virtual void PhysicsRotation(float DeltaTime) override;
    virtual void UpdateCharacterStateBeforeMovement(float DeltaSeconds) override;
    virtual void UpdateCharacterStateAfterMovement(float DeltaSeconds) override;
    virtual FNetworkPredictionData_Client* GetPredictionData_Client() const override;
    virtual void UpdateFromCompressedFlags(uint8 Flags) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

    bool bWantsToSlide = false;
    // Movement-time clocks must rewind with saved moves, rather than using world
    // timers which would run ahead when the client replays a correction.
    float GetSlideMinimumTimeRemaining() const { return SlideMinimumTimeRemaining; }
    void RestorePredictedSlide(bool bSavedSliding, float MinimumTime, float RecoveryTime)
    {
        bSliding = bSavedSliding;
        SlideMinimumTimeRemaining = MinimumTime;
        SlideRecoveryRemaining = RecoveryTime;
    }
private:
    void SetSliding(bool bNewSliding);
    UFUNCTION() void OnRep_Sliding();
    UPROPERTY(ReplicatedUsing=OnRep_Sliding)
    bool bSliding = false;
    float SlideMinimumTimeRemaining = 0.f;
    float SlideRecoveryRemaining = 0.f;
};
