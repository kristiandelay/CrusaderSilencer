#pragma once

#include "Player/LyraPlayerBotController.h"
#include "Components/ActorComponent.h"
#include "GameFramework/Actor.h"
#include "Perception/AIPerceptionTypes.h"
#include "Navigation/NavLinkProxy.h"
#include "Navigation/CrowdAgentInterface.h"
#include "CRCrowdAI.generated.h"

class USphereComponent;
class ULyraInventoryManagerComponent;
class ULyraQuickBarComponent;
class ULyraWeaponStateComponent;
class ULyraInventoryItemDefinition;
class ULyraHealthComponent;
class UAIPerceptionComponent;
class ACRTraversalCharacter;
struct FCRShotImpact;

UENUM(BlueprintType)
enum class ECRCrowdState : uint8 { Idle, Patrol, Investigate, Pursue, Reposition, Attack, Flee, Recover, Dead };

/** A reusable navigation tether. Links opt into occasional visits to other areas. */
UCLASS(Blueprintable)
class LYRAGAME_API ACRCrowdArea : public AActor
{
    GENERATED_BODY()
public:
    ACRCrowdArea();
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<USphereComponent> Bounds;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Crowd") float Radius = 1000.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Crowd") float WanderChance = .18f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Crowd") bool bAllowGuards = true;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Crowd") bool bAllowCivilians = true;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Crowd") TArray<TObjectPtr<ACRCrowdArea>> Neighbours;
    virtual void OnConstruction(const FTransform& Transform) override;
    bool SampleLocation(const APawn* Pawn, FVector& Out) const;
};

/** Shared pawn subobject: player movement/physics/equipment remain authoritative. */
UCLASS(meta=(BlueprintSpawnableComponent))
class LYRAGAME_API UCRCrowdAgentComponent : public UActorComponent, public ICrowdAgentInterface
{
    GENERATED_BODY()
public:
    UCRCrowdAgentComponent();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual FVector GetCrowdAgentLocation() const override;
    virtual FVector GetCrowdAgentVelocity() const override;
    virtual void GetCrowdAgentCollisions(float& Radius, float& HalfHeight) const override;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Crowd") bool bEnabled = false;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Crowd") bool bGuard = false;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Crowd") TObjectPtr<ACRCrowdArea> HomeArea;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Crowd") TArray<TSubclassOf<AActor>> Visuals;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Crowd") TArray<TSubclassOf<ULyraInventoryItemDefinition>> Weapons;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Crowd") float PatrolSpeed = 190.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Crowd") float RunSpeed = 650.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Crowd") float CombatRange = 1350.f;
    UPROPERTY(BlueprintReadOnly, Replicated) ECRCrowdState State = ECRCrowdState::Idle;
    UPROPERTY(BlueprintReadOnly, Replicated) TObjectPtr<ACRCrowdArea> CurrentArea;
    UPROPERTY(BlueprintReadOnly, Replicated) TObjectPtr<AActor> Threat;
    UPROPERTY(BlueprintReadOnly, Replicated) FVector LastKnownThreatLocation;
    UPROPERTY(BlueprintReadOnly, Replicated) FVector Destination;
    UPROPERTY(BlueprintReadOnly, Replicated) int32 AreaVisits = 0;
    UPROPERTY(BlueprintReadOnly, Replicated) int32 TacticalMoves = 0;
    UPROPERTY(BlueprintReadOnly, Replicated) int32 TraversalsStarted = 0;
    UPROPERTY(BlueprintReadOnly, Replicated) int32 ShotsRequested = 0;
    UPROPERTY(BlueprintReadOnly, Replicated) int32 SightDetections = 0;
    UPROPERTY(BlueprintReadOnly, Replicated) int32 HearingDetections = 0;
    UPROPERTY(BlueprintReadOnly, Replicated) int32 DamageReactions = 0;
    UPROPERTY(BlueprintReadOnly, Replicated) bool bInitialized = false;
    UPROPERTY(BlueprintReadOnly, Replicated) float DesiredSpeed = 190.f;
    UPROPERTY(BlueprintReadOnly, ReplicatedUsing=OnRep_Visual) TSubclassOf<AActor> SelectedVisual;
    void SetVisual(TSubclassOf<AActor> Visual);
    void UpdateLocomotionIntent();
    UFUNCTION() void OnRep_Visual();
    UFUNCTION(BlueprintPure, Category="Crowd") static bool OwnsVisualOverride(UActorComponent* Source);
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
    static void ReportGunshot(APawn* Shooter, const FVector& Origin, const TArray<FCRShotImpact>& Hits);
};

UCLASS()
class LYRAGAME_API ACRCrowdController : public ALyraPlayerBotController
{
    GENERATED_BODY()
public:
    ACRCrowdController(const FObjectInitializer& Initializer = FObjectInitializer::Get());
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<ULyraInventoryManagerComponent> Inventory;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<ULyraQuickBarComponent> QuickBar;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<ULyraWeaponStateComponent> WeaponState;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<UAIPerceptionComponent> Senses;
    virtual void Tick(float DeltaSeconds) override;
    virtual void OnPossess(APawn* Pawn) override;
    virtual void OnUnPossess() override;
    virtual void UpdateControlRotation(float DeltaTime, bool bUpdatePawn = true) override;
    void ReactToThreat(AActor* Actor, const FVector& Location, bool bAggression);
    UFUNCTION(BlueprintCallable, Category="Crowd") bool RequestMovementAction(FName Action, FVector Goal);
    bool bUsingTraversalLink = false;
private:
    UFUNCTION() void PerceptionUpdated(AActor* Actor, FAIStimulus Stimulus);
    UFUNCTION() void HealthChanged(ULyraHealthComponent* Health, float OldValue, float NewValue, AActor* DamageInstigator);
    void InitializeAgent();
    void Think();
    void StopFiring();
    void MoveTowards(const FVector& Goal, ECRCrowdState NewState, float Speed);
    void Patrol();
    void Combat();
    void Flee();
    bool CanSee(const AActor* Actor) const;
    bool SelectTacticalPosition(FVector& Out) const;
    bool ClearShot(const AActor* Actor) const;
    void FireBurst();
    ACRTraversalCharacter* Character() const;
    UCRCrowdAgentComponent* Agent() const;
    double NextThink = 0.;
    double NextPatrol = 0.;
    double NextTactic = 0.;
    double NextShot = 0.;
    double StopFireAt = 0.;
    double LastThreatTime = -100.;
    double LastSeenTime = -100.;
    double NextTraversal = 0.;
    double ActionUntil = 0.;
    double NextAreaChange = 0.;
    double YieldUntil = 0.;
    FVector YieldReturnGoal;
    bool bTriggerHeld = false;
    bool bAggressive = false;
    bool bHeardGunfire = false;
    FVector ActionGoal;
    FName ActiveAction;
    FVector LastProgressPosition;
    double LastProgressTime = 0.;
    float LastCrowdMaxSpeed = -1.f;
};

/** Authored route links invoke the same movement action on either NPC role. */
UCLASS()
class LYRAGAME_API ACRCrowdTraversalLink : public ANavLinkProxy
{
    GENERATED_BODY()
public:
    ACRCrowdTraversalLink();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Traversal") FName Action = TEXT("Vault");
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Traversal") bool bBidirectional = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Traversal", meta=(MakeEditWidget)) FVector Start = FVector(-120,0,0);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Traversal", meta=(MakeEditWidget)) FVector End = FVector(120,0,0);
    virtual void OnConstruction(const FTransform& Transform) override;
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
private:
    UFUNCTION() void LinkReached(AActor* MovingActor, const FVector& DestinationPoint);
    struct FPendingTraversal
    {
        double Time = 0.;
        FVector Approach;
        FVector Destination;
        bool bStarted = false;
    };
    TMap<TWeakObjectPtr<AActor>,FPendingTraversal> PendingAgents;
};
