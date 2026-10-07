#pragma once

#include "Components/ActorComponent.h"
#include "Engine/DataAsset.h"
#include "Engine/NetSerialization.h"
#include "CRWeaponEffects.generated.h"

class UNiagaraSystem;
class USoundBase;
class USoundAttenuation;
class UMaterialInterface;
class UBaselineWeaponInstance;
class UDecalComponent;
struct FGameplayAbilityTargetDataHandle;

USTRUCT(BlueprintType)
struct FCRSurfaceImpact
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TEnumAsByte<EPhysicalSurface> Surface = SurfaceType_Default;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<UNiagaraSystem> Effect;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<USoundBase> Sound;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<UMaterialInterface> Decal;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) float Scale = 1.f;
};

/** Surface IDs are shared with PhysicsSettings and the traversal firing range. */
UCLASS(BlueprintType)
class LYRAGAME_API UCRWeaponEffectsProfile : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<UNiagaraSystem> MuzzleFlash;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<UNiagaraSystem> ShellEjection;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<UNiagaraSystem> BulletTrail;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<USoundAttenuation> ImpactAttenuation;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<FCRSurfaceImpact> Surfaces;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) float MuzzleScale = .6f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) float TrailSpeed = 18000.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) float DecalSize = 3.f;
    const FCRSurfaceImpact* FindSurface(EPhysicalSurface Surface) const;
};

USTRUCT(BlueprintType)
struct FCRShotImpact
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) FVector_NetQuantize Position;
    UPROPERTY(BlueprintReadOnly) FVector_NetQuantizeNormal Normal;
    UPROPERTY(BlueprintReadOnly) uint8 Surface = 0;
    UPROPERTY(BlueprintReadOnly) bool bBlockingHit = false;
};

/** Cosmetic replication follows accepted Lyra target data, including every pellet.
 * The owning client predicts once; server multicast only plays on other clients. */
UCLASS(meta=(BlueprintSpawnableComponent))
class LYRAGAME_API UCRWeaponEffectsComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UCRWeaponEffectsComponent();
    void SubmitShot(UBaselineWeaponInstance* Weapon, const FGameplayAbilityTargetDataHandle& Data);
    UFUNCTION(BlueprintPure, Category="Crusader|Weapons")
    static bool UsesCustomWeaponEffects(AActor* WeaponActor);
    UPROPERTY(BlueprintReadOnly, Transient) int32 ShotsPlayed = 0;
    UPROPERTY(BlueprintReadOnly, Transient) int32 ImpactsPlayed = 0;
    UPROPERTY(BlueprintReadOnly, Transient) int32 TrailsPlayed = 0;
    UPROPERTY(BlueprintReadOnly, Transient) TArray<FCRShotImpact> LastImpacts;
    UPROPERTY(BlueprintReadOnly, Transient) TObjectPtr<UCRWeaponEffectsProfile> LastProfile;
private:
    UFUNCTION(NetMulticast, Unreliable)
    void MulticastShot(UCRWeaponEffectsProfile* Profile, const FTransform& Muzzle, const FTransform& Ejection, const TArray<FCRShotImpact>& Hits);
    void PlayShot(UCRWeaponEffectsProfile* Profile, const FTransform& Muzzle, const FTransform& Ejection, const TArray<FCRShotImpact>& Hits);
    TArray<TWeakObjectPtr<UDecalComponent>> Decals;
};
