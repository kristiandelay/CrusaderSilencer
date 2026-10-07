#pragma once

#include "Components/ActorComponent.h"
#include "Engine/DataAsset.h"
#include "GameplayTagContainer.h"
#include "CRFootsteps.generated.h"

class USoundBase;
class USoundAttenuation;
class USoundConcurrency;

UENUM(BlueprintType)
enum class ECRFootstepGait : uint8 { Sneak, Walk, Run, Sprint, Jump, Land };

USTRUCT(BlueprintType)
struct FCRFootstepSurface
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TEnumAsByte<EPhysicalSurface> Surface = SurfaceType_Default;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TObjectPtr<USoundBase>> Sneak;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TObjectPtr<USoundBase>> Walk;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TObjectPtr<USoundBase>> Run;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TObjectPtr<USoundBase>> Sprint;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TObjectPtr<USoundBase>> Jump;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TObjectPtr<USoundBase>> Land;
    const TArray<TObjectPtr<USoundBase>>& GetSounds(ECRFootstepGait Gait) const;
};

UCLASS(BlueprintType)
class LYRAGAME_API UCRFootstepProfile : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<FCRFootstepSurface> Surfaces;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<USoundAttenuation> Attenuation;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<USoundConcurrency> Concurrency;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) float RunSpeed = 300.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) float SprintSpeed = 650.f;
    const FCRFootstepSurface* FindSurface(EPhysicalSurface Surface) const;
};

/** Consumes GASP foot-contact notifies on each rendered pawn, including proxies.
 * No timer footsteps or multicast: each animation produces one local contact. */
UCLASS(meta=(BlueprintSpawnableComponent))
class LYRAGAME_API UCRFootstepComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UCRFootstepComponent();
    void GroundContact();
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Crusader|Audio") TObjectPtr<UCRFootstepProfile> Profile;
    UFUNCTION(BlueprintCallable, Category="Crusader|Audio")
    static bool HandleFoleyEvent(UActorComponent* Source, FGameplayTag Event, uint8 Side, float Volume = 1.f, float Pitch = 1.f);
    UPROPERTY(BlueprintReadOnly, Transient) int32 SoundsPlayed = 0;
    UPROPERTY(BlueprintReadOnly, Transient) int32 StepsPlayed = 0;
    UPROPERTY(BlueprintReadOnly, Transient) int32 JumpsPlayed = 0;
    UPROPERTY(BlueprintReadOnly, Transient) int32 LandingsPlayed = 0;
    UPROPERTY(BlueprintReadOnly, Transient) uint8 LastSurface = 0;
    UPROPERTY(BlueprintReadOnly, Transient) ECRFootstepGait LastGait = ECRFootstepGait::Walk;
    UPROPERTY(BlueprintReadOnly, Transient) FName LastFoot;
    UPROPERTY(BlueprintReadOnly, Transient) FVector LastPosition;
    UPROPERTY(BlueprintReadOnly, Transient) TObjectPtr<USoundBase> LastSound;
private:
    void PlayContact(FName Event, uint8 Side, float Volume, float Pitch);
    double LastContactTimes[3] = {-100., -100., -100.};
    double LastJumpTime = -100.;
    double LastLandTime = -100.;
    TMap<int32, int32> LastVariants;
};
