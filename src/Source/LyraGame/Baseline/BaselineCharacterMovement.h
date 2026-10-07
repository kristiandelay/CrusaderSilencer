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
    // Saved moves restore this alongside CMC's crouch and velocity state.
    void RestorePredictedSlide(bool bSavedSliding) { bSliding = bSavedSliding; }
private:
    void SetSliding(bool bNewSliding);
    UFUNCTION() void OnRep_Sliding();
    UPROPERTY(ReplicatedUsing=OnRep_Sliding)
    bool bSliding = false;
};
