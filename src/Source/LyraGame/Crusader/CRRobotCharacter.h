#pragma once

#include "CRTraversalCharacter.h"
#include "Animation/AnimInstance.h"
#include "CRRobotCharacter.generated.h"

class UCRWeaponEffectsProfile;
class UGameplayEffect;
class USkeletalMesh;
class USkeletalMeshComponent;

/** Mechanical pawn using the same Lyra health lifecycle and crowd controller. */
UCLASS()
class LYRAGAME_API ACRRobotCharacter : public ACRTraversalCharacter
{
    GENERATED_BODY()
public:
    ACRRobotCharacter(const FObjectInitializer& Initializer=FObjectInitializer::Get());
    virtual void Tick(float DeltaSeconds) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Robot") float ArmorHealth=240.f;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Robot") float LaserDamage=9.f;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Robot") float WeaponRange=2800.f;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Robot") TObjectPtr<UCRWeaponEffectsProfile> LaserEffects;
    UPROPERTY(EditDefaultsOnly, Category="Robot") TSubclassOf<UGameplayEffect> DamageEffect;
    /** Model-space barrel tips, in centimetres, relative to the imported mesh. */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Robot") TArray<FVector> MuzzlePositions;
    UPROPERTY(BlueprintReadOnly, Replicated, Category="Robot") int32 MountedShots=0;
    UPROPERTY(BlueprintReadOnly, Replicated, Category="Robot") bool bShutdown=false;
    UPROPERTY(BlueprintReadOnly, Replicated, Category="Robot") FVector LastMuzzlePosition;
    UFUNCTION(BlueprintPure, Category="Robot") FVector GetMountedMuzzle() const;
    bool StartMountedBurst(AActor* Target);
    void StopMountedBurst();
protected:
    virtual void BeginPlay() override;
    virtual void OnAbilitySystemInitialized() override;
    virtual void OnDeathStarted(AActor* OwningActor) override;
    virtual void OnDeathFinished(AActor* OwningActor) override;
private:
    bool HasFiringLane(AActor* Target, FVector& Origin, FVector& Aim) const;
    void FireMountedShot();
    void RespawnRobot();
    TWeakObjectPtr<AActor> BurstTarget;
    int32 BurstRemaining=0;
    double NextMountedShot=0.;
    FTimerHandle ShutdownTimer;
};

/** Game-thread foot placement and rigid hinge solving; evaluation reads a copy. */
UCLASS(Transient)
class LYRAGAME_API UCRRobotAnimInstance : public UAnimInstance
{
    GENERATED_BODY()
public:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) override;
    void UpdateRobotPose(float DeltaSeconds);
    UPROPERTY(BlueprintReadOnly, Transient, Category="Robot") float GroundSpeed=0.f;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Robot") float GaitPhase=0.f;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Robot") int32 FootPlants=0;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Robot") float MaximumFootError=0.f;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Robot") float ShutdownBlend=0.f;
    const TArray<FTransform>& GetMechanicalPose() const { return LocalPose; }
private:
    struct FLeg
    {
        int32 Bones[4]={INDEX_NONE,INDEX_NONE,INDEX_NONE,INDEX_NONE};
        float Angles[3]={0,0,0};
        FVector Planted=FVector::ZeroVector;
        FVector SwingStart=FVector::ZeroVector;
        FVector SwingEnd=FVector::ZeroVector;
        bool bSwinging=false;
    };
    bool CacheRig(USkeletalMeshComponent* Mesh);
    void BuildComponentPose();
    FVector GroundTarget(ACRRobotCharacter* Robot,const FVector& Nominal,float AnkleHeight) const;
    void SolveLeg(FLeg& Leg,const FVector& ComponentTarget);
    TArray<FTransform> ReferenceLocal,ReferenceComponent,LocalPose,ComponentPose;
    TArray<int32> Parents;
    FLeg Legs[2];
    int32 Chassis=INDEX_NONE;
    int32 Pistons[2][2]={{INDEX_NONE,INDEX_NONE},{INDEX_NONE,INDEX_NONE}};
    TWeakObjectPtr<USkeletalMesh> CachedMesh;
    FVector PreviousLocation=FVector::ZeroVector;
    float PreviousYaw=0.f;
    bool bFeetInitialized=false;
    bool bWasGrounded=false;
    float Recoil=0.f;
    float ChassisPitch=0.f;
    int32 PreviousShots=0;
};
