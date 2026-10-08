#pragma once

#include "GameFramework/Actor.h"
#include "Engine/NetSerialization.h"
#include "NavRelevantComponent.h"
#include "CRDestructibleActor.generated.h"

class UGeometryCollectionComponent;
struct FChaosBreakEvent;

/** A collection has no ordinary static-mesh body setup for UNavModifierComponent.
 * Export its intact world bounds explicitly, without exporting fracture triangles. */
UCLASS()
class LYRAGAME_API UCRDestructibleNavigation : public UNavRelevantComponent
{
    GENERATED_BODY()
public:
    UCRDestructibleNavigation(const FObjectInitializer& Initializer);
    virtual void CalcAndCacheBounds() const override;
    virtual void GetNavigationData(FNavigationRelevantData& Data) const override;
};

USTRUCT()
struct FCRDestructionBreakEffects
{
    GENERATED_BODY()
    UPROPERTY() FVector_NetQuantize Location = FVector::ZeroVector;
    UPROPERTY() FVector_NetQuantize10 Velocity = FVector::ZeroVector;
    UPROPERTY() int32 PieceIndex = INDEX_NONE;
    UPROPERTY() int32 Revision = 0;
};

/** Game integration for the Next Gen Destruction Toolkit's breakable Blueprint. */
UCLASS(Blueprintable)
class LYRAGAME_API ACRDestructibleActor : public AActor
{
    GENERATED_BODY()
public:
    ACRDestructibleActor();
    virtual void OnConstruction(const FTransform& Transform) override;
    virtual void BeginPlay() override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

    /** Called only for committed weapon hits on the authority, including robot weapons. */
    static bool ApplyWeaponHit(const FHitResult& Hit);
    static void ApplyExplosion(UWorld* World, const FVector& Origin, float Radius, AActor* Causer);

    UFUNCTION(BlueprintPure, Category="Destruction")
    UGeometryCollectionComponent* GetDestructibleGeometry() const;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Replicated, Category="Destruction")
    int32 WeaponHits = 0;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Replicated, Category="Destruction")
    int32 ExplosionHits = 0;
    /** Local Chaos events, useful for verifying that the simulation actually fractures. */
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Destruction")
    int32 LocalBreakEvents = 0;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Destruction")
    int32 ReceivedBreakEffects = 0;
    /** Cheap intact footprint for furniture inside the crowd patrol buildings. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Destruction")
    bool bBlockNavigationUntilBroken = false;
    /** Optional direct strain on the hit cluster, for furniture with distant centers of mass. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Destruction", meta=(ClampMin="0"))
    float WeaponContactStrain = 0.f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Destruction")
    TObjectPtr<UCRDestructibleNavigation> IntactNavigation;

private:
    void ConfigureGeometry();
    UFUNCTION()
    void OnGeometryBroken(const FChaosBreakEvent& Event);
    UFUNCTION()
    void OnRep_BreakEffects();
    UPROPERTY(ReplicatedUsing=OnRep_BreakEffects)
    FCRDestructionBreakEffects BreakEffects;
    double NextBreakEffectsTime = 0.;
    bool bRelayingBreakEffects = false;
};
