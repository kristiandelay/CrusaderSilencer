#pragma once

#include "Components/ActorComponent.h"
#include "GameFramework/Actor.h"
#include "CRThrowable.generated.h"

class ACRTraversalCharacter;
class USphereComponent;
class UStaticMeshComponent;
class UInstancedStaticMeshComponent;
class UDecalComponent;
class UProjectileMovementComponent;
class UAnimSequence;
class UAnimMontage;
class UStaticMesh;
class UParticleSystem;
class UParticleSystemComponent;
class UMaterialInterface;
class USoundBase;
class UGameplayEffect;

UENUM(BlueprintType)
enum class ECRThrowableType : uint8 { Grenade, Smoke };
UENUM(BlueprintType)
enum class ECRThrowPhase : uint8 { Idle, Aiming, Throwing };

/** Server projectile with identical gravity/radius to the owner's trajectory preview. */
UCLASS(Blueprintable)
class LYRAGAME_API ACRThrownObject : public AActor
{
    GENERATED_BODY()
public:
    ACRThrownObject();
    virtual void BeginPlay() override;
    virtual void Tick(float Delta) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly) TObjectPtr<USphereComponent> Collision;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly) TObjectPtr<UStaticMeshComponent> Mesh;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly) TObjectPtr<UProjectileMovementComponent> Movement;
    UPROPERTY(EditDefaultsOnly,Category="Throw") TObjectPtr<UStaticMesh> GrenadeMesh;
    UPROPERTY(EditDefaultsOnly,Category="Throw") TObjectPtr<UStaticMesh> SmokeMesh;
    UPROPERTY(EditDefaultsOnly,Category="Throw") TObjectPtr<UParticleSystem> ExplosionEffect;
    UPROPERTY(EditDefaultsOnly,Category="Throw") TObjectPtr<UParticleSystem> SmokeEffect;
    UPROPERTY(EditDefaultsOnly,Category="Throw") TObjectPtr<USoundBase> ExplosionSound;
    UPROPERTY(EditDefaultsOnly,Category="Throw") TObjectPtr<USoundBase> BounceSound;
    UPROPERTY(EditDefaultsOnly,Category="Throw") TSubclassOf<UGameplayEffect> DamageEffect;
    UPROPERTY(EditDefaultsOnly,Category="Throw") float GrenadeFuse=3.f;
    UPROPERTY(EditDefaultsOnly,Category="Throw") float SmokeFuse=1.3f;
    UPROPERTY(EditDefaultsOnly,Category="Throw") float BlastRadius=550.f;
    UPROPERTY(EditDefaultsOnly,Category="Throw") float MaximumDamage=110.f;
    UPROPERTY(EditDefaultsOnly,Category="Throw") float SmokeRadius=450.f;
    UPROPERTY(EditDefaultsOnly,Category="Throw") float SmokeDuration=12.f;
    UPROPERTY(BlueprintReadOnly,ReplicatedUsing=OnRep_Type) ECRThrowableType Type=ECRThrowableType::Grenade;
    UPROPERTY(BlueprintReadOnly,ReplicatedUsing=OnRep_Detonated) bool bDetonated=false;
    UPROPERTY(BlueprintReadOnly,Replicated) FVector_NetQuantize DetonationLocation;
    UPROPERTY(BlueprintReadOnly,Replicated) float DetonationTime=0.f;
    UPROPERTY(BlueprintReadOnly,Replicated) int32 BounceCount=0;
    UPROPERTY(BlueprintReadOnly,Replicated) FVector_NetQuantize FirstImpact;
    void Launch(const FVector& Velocity);
    UFUNCTION(BlueprintPure,Category="Throw",meta=(WorldContext="WorldContext"))
    static bool IsSightObscured(const UObject* WorldContext,FVector Start,FVector End);
private:
    UFUNCTION() void OnRep_Type();
    UFUNCTION() void OnRep_Detonated();
    UFUNCTION() void OnBounce(const FHitResult& Hit,const FVector& Velocity);
    UFUNCTION(NetMulticast,Unreliable) void PlayBounce(FVector_NetQuantize Location);
    void Detonate();
    void ApplyBlastDamage();
    float ServerTime() const;
    double FuseAt=0.;
    double NextBounceSound=0.;
    UPROPERTY(Transient) TObjectPtr<UParticleSystemComponent> Smoke;
};

/** Hold to preview, release to throw. Inventory, release and interruption are server checked. */
UCLASS(meta=(BlueprintSpawnableComponent))
class LYRAGAME_API UCRThrowableComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UCRThrowableComponent();
    virtual void BeginPlay() override;
    virtual void TickComponent(float Delta,ELevelTick Type,FActorComponentTickFunction* Function) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
    UFUNCTION(BlueprintCallable,Category="Throw") void BeginAim();
    UFUNCTION(BlueprintCallable,Category="Throw") void ReleaseThrow();
    UFUNCTION(BlueprintCallable,Category="Throw") void CancelThrow();
    UFUNCTION(BlueprintCallable,Category="Throw") void CycleType();
    UFUNCTION(BlueprintPure,Category="Throw") bool IsBusy() const { return Phase!=ECRThrowPhase::Idle; }
    UFUNCTION(BlueprintPure,Category="Throw") bool CanBeginAim() const;
    UFUNCTION(BlueprintPure,Category="Throw") bool CanSwapShoulder() const;
    UFUNCTION(BlueprintPure,Category="Throw") bool IsLeftThrowHand() const;
    void ShoulderChanged();
    UFUNCTION(BlueprintPure,Category="Throw") int32 GetRemaining() const { return SelectedType==ECRThrowableType::Grenade ? Grenades : SmokeGrenades; }
    UFUNCTION(BlueprintPure,Category="Throw") bool CalculateLaunch(FRotator Aim,FVector& Start,FVector& Velocity) const;
    UPROPERTY(EditDefaultsOnly,Category="Throw") TSubclassOf<ACRThrownObject> ProjectileClass;
    UPROPERTY(EditDefaultsOnly,Category="Throw") TObjectPtr<UAnimSequence> AimAnimation;
    UPROPERTY(EditDefaultsOnly,Category="Throw") TObjectPtr<UAnimMontage> ThrowMontage;
    UPROPERTY(EditDefaultsOnly,Category="Throw") TObjectPtr<UAnimSequence> LeftAimAnimation;
    UPROPERTY(EditDefaultsOnly,Category="Throw") TObjectPtr<UAnimMontage> LeftThrowMontage;
    UPROPERTY(EditDefaultsOnly,Category="Throw") FTransform LeftHandGrip;
    UPROPERTY(EditDefaultsOnly,Category="Throw") TObjectPtr<UMaterialInterface> TrajectoryMaterial;
    UPROPERTY(EditDefaultsOnly,Category="Throw") TObjectPtr<UMaterialInterface> LandingMaterial;
    UPROPERTY(EditDefaultsOnly,Category="Throw") TObjectPtr<UStaticMesh> TrajectoryMesh;
    UPROPERTY(EditDefaultsOnly,Category="Throw") float ThrowSpeed=1450.f;
    UPROPERTY(EditDefaultsOnly,Category="Throw") float UpwardBoost=300.f;
    // Matches the pack's release notify in AM_Throw.
    UPROPERTY(EditDefaultsOnly,Category="Throw") float ReleaseDelay=.168179f;
    UPROPERTY(BlueprintReadOnly,ReplicatedUsing=OnRep_Phase) ECRThrowPhase Phase=ECRThrowPhase::Idle;
    UPROPERTY(BlueprintReadOnly,ReplicatedUsing=OnRep_Phase) ECRThrowableType SelectedType=ECRThrowableType::Grenade;
    UPROPERTY(BlueprintReadOnly,ReplicatedUsing=OnRep_Phase) bool bReleaseLeftHand=false;
    UPROPERTY(EditDefaultsOnly,BlueprintReadOnly,Replicated,Category="Throw") int32 Grenades=6;
    UPROPERTY(EditDefaultsOnly,BlueprintReadOnly,Replicated,Category="Throw") int32 SmokeGrenades=6;
    UPROPERTY(BlueprintReadOnly,Replicated) int32 ThrowsReleased=0;
    UPROPERTY(BlueprintReadOnly) FVector PredictedImpact;
    UPROPERTY(BlueprintReadOnly) bool bPreviewVisible=false;
    UPROPERTY(BlueprintReadOnly) bool bPreviewHit=false;
    UPROPERTY(BlueprintReadOnly) bool bLaunchBlocked=false;
    UPROPERTY(BlueprintReadOnly) TArray<FVector> PreviewPoints;
private:
    ACRTraversalCharacter* Character() const;
    bool CanContinue() const;
    void SetPhase(ECRThrowPhase NewPhase);
    void UpdatePresentation();
    void UpdatePreview();
    void HidePreview();
    UFUNCTION() void OnRep_Phase();
    UFUNCTION(Server,Reliable) void ServerBeginAim(ECRThrowableType Kind);
    UFUNCTION(Server,Reliable) void ServerRelease(FRotator Aim);
    UFUNCTION(Server,Reliable) void ServerCancel();
    UFUNCTION(Server,Reliable) void ServerSelect(ECRThrowableType Kind);
    UFUNCTION(Client,Reliable) void ClientRejected();
    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> HeldObject;
    UPROPERTY(Transient) TObjectPtr<UInstancedStaticMeshComponent> Arc;
    UPROPERTY(Transient) TObjectPtr<UDecalComponent> Landing;
    UPROPERTY(Transient) TObjectPtr<UAnimMontage> AimMontage;
    ECRThrowPhase PresentedPhase=ECRThrowPhase::Idle;
    bool bPresentedLeftHand=false;
    bool bReleased=false;
    double ReleaseAt=0.;
    double FinishAt=0.;
    double NextThrowAt=0.;
    double LocalThrowStarted=0.;
    FVector ReleaseOrigin;
    FVector ReleaseVelocity;
    FRotator ReleaseAim;
};
