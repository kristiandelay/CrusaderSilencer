#pragma once

#include "Components/ActorComponent.h"
#include "Animation/AnimInstance.h"
#include "PoseSearch/PoseSearchResult.h"
#include "BaselinePhysicalInteraction.generated.h"

class ACharacter;
class UPhysicsControlComponent;
class UPhysicsControlAsset;
class UPoseSearchDatabase;
class UPoseSearchInteractionAsset;

UENUM(BlueprintType)
enum class EBaselinePhysicalPhase : uint8 { Locomotion, Interaction, Ragdoll, Recovery, Dead };
UENUM(BlueprintType)
enum class EBaselineInteraction : uint8 { Shove, Tackle, Takedown };

/** Replicate the selection, participants and alignment, never transient AnimInstances. */
USTRUCT()
struct FBaselinePhysicalState
{
    GENERATED_BODY()
    UPROPERTY() EBaselinePhysicalPhase Phase = EBaselinePhysicalPhase::Locomotion;
    UPROPERTY() int32 Revision = 0;
    UPROPERTY() TObjectPtr<UAnimMontage> Montage;
    UPROPERTY() TObjectPtr<UPoseSearchInteractionAsset> Interaction;
    UPROPERTY() TObjectPtr<UPoseSearchDatabase> Database;
    UPROPERTY() TObjectPtr<ACharacter> Attacker;
    UPROPERTY() TObjectPtr<ACharacter> Victim;
    UPROPERTY() FName Role;
    UPROPERTY() int32 RoleIndex = 0;
    UPROPERTY() TArray<FTransform> Roots;
    UPROPERTY() TArray<FTransform> RootBones;
    UPROPERTY() float StartTime = 0.f;
    UPROPERTY() float ServerTime = 0.f;
    UPROPERTY() FTransform StartTransform;
    UPROPERTY() FVector Velocity = FVector::ZeroVector;
    UPROPERTY() float RagdollAt = -1.f;
};

/** Physics Control and server-selected paired motion matching on the existing CMC pawn. */
UCLASS(BlueprintType, ClassGroup=Baseline, meta=(BlueprintSpawnableComponent))
class UBaselinePhysicalInteractionComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UBaselinePhysicalInteractionComponent();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;

    UFUNCTION(BlueprintCallable) void ToggleRagdoll();
    UFUNCTION(BlueprintCallable) void RequestRecovery();
    UFUNCTION(BlueprintCallable) void Shove();
    UFUNCTION(BlueprintCallable) void Tackle();
    UFUNCTION(BlueprintCallable) void Takedown();
    UFUNCTION(BlueprintPure) bool IsBusy() const { return State.Phase != EBaselinePhysicalPhase::Locomotion; }
    UFUNCTION(BlueprintPure) EBaselinePhysicalPhase GetPhase() const { return State.Phase; }
    UFUNCTION(BlueprintPure) FPoseSearchBlueprintResult GetInteractionResult() const;
    UFUNCTION(BlueprintPure) ACharacter* FindInteractionTarget() const;
    UFUNCTION(BlueprintCallable) void StartRagdoll(FVector Velocity);
    void StartDeathRagdoll(FVector Velocity);
    UPROPERTY(EditDefaultsOnly, Category="Physical Animation") TObjectPtr<UPhysicsControlAsset> ControlProfile;
    UPROPERTY(EditDefaultsOnly, Category="Physical Animation") TObjectPtr<UPoseSearchDatabase> GetUpDatabase;
    UPROPERTY(EditDefaultsOnly, Category="Interactions") TObjectPtr<UPoseSearchDatabase> ShoveDatabase;
    UPROPERTY(EditDefaultsOnly, Category="Interactions") TObjectPtr<UPoseSearchDatabase> TackleDatabase;
    UPROPERTY(EditDefaultsOnly, Category="Interactions") TArray<TObjectPtr<UPoseSearchDatabase>> TakedownDatabases;
    UPROPERTY(EditAnywhere, Category="Interactions") float InteractionDistance = 220.f;
    UPROPERTY(EditAnywhere, Category="Physical Animation") bool bAutoRecover = false;
    UPROPERTY(EditAnywhere, Category="Physical Animation") float AutoRecoveryDelay = 3.f;
    UPROPERTY(EditAnywhere, Category="Physical Animation") float FallRagdollSpeed = 1100.f;
    UPROPERTY(BlueprintReadOnly, Category="Physical Animation") bool bControlsCreated = false;
    UPROPERTY(BlueprintReadOnly, Category="Interactions") FString LastResult;
    UPROPERTY(BlueprintReadOnly, Category="Interactions") float LastSearchCost = 0.f;
    UPROPERTY(BlueprintReadOnly, Category="Physical Animation") TObjectPtr<UAnimMontage> LastGetUp;
private:
    UFUNCTION(Server, Reliable) void ServerToggleRagdoll();
    UFUNCTION(Server, Reliable) void ServerRecover();
    UFUNCTION(Server, Reliable) void ServerInteract(EBaselineInteraction Type);
    UFUNCTION() void OnRep_State();
    UFUNCTION() void OnRep_Pelvis();
    void ApplyState();
    void CommitState(FBaselinePhysicalState NewState);
    void FinishAction();
    bool CanInteract() const;
    bool CanReach(const ACharacter* Other) const;
    float ServerNow() const;
    void RestoreMesh();
    void UpdatePassiveRest(float DeltaTime);
    UPROPERTY(ReplicatedUsing=OnRep_State) FBaselinePhysicalState State;
    UPROPERTY(ReplicatedUsing=OnRep_Pelvis) FVector_NetQuantize ReplicatedPelvis;
    UPROPERTY(Transient) TObjectPtr<ACharacter> Character;
    UPROPERTY(Transient) TObjectPtr<UPhysicsControlComponent> Controls;
    TWeakObjectPtr<ACharacter> IgnoredPartner;
    FTransform MeshRelative;
    FName MeshCollisionProfile;
    FName CapsuleCollisionProfile;
    FCollisionResponseContainer CapsuleResponses;
    TArray<float> SavedAngularDamping;
    TArray<FTransform> RestReference;
    float RestAge = 0.f;
    EBaselinePhysicalPhase AppliedPhase = EBaselinePhysicalPhase::Locomotion;
    float PhaseAge = 0.f;
    float NetAccumulator = 0.f;
    float LastRequestTime = -10.f;
    bool bSavedOrientToMovement = false;
};

/** Keeps the final physical pose while the matched get-up blends in. */
UCLASS(Transient, Blueprintable)
class UBaselineSourceAnimInstance : public UAnimInstance
{
    GENERATED_BODY()
public:
    virtual void NativeUpdateAnimation(float DeltaSeconds) override;
    void StartRecoveryBlend();
    UPROPERTY(BlueprintReadOnly, Transient) float RecoveryPoseWeight = 0.f;
    UPROPERTY(BlueprintReadOnly, Transient) float RecoveryAnimationWeight = 0.f;
    /** Full-body rolls/get-ups keep their authored pose instead of standing foot IK. */
    UPROPERTY(BlueprintReadOnly, Transient) float LocomotionCorrectionBypassWeight = 0.f;
    /** Independent upper-body aim while the sliding legs follow momentum. */
    UPROPERTY(BlueprintReadOnly, Transient) FRotator ThrowRootRotation = FRotator::ZeroRotator;
private:
    double RecoveryBlendStartTime = 0.0;
};
