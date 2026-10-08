#pragma once

#include "Components/ActorComponent.h"
#include "Player/LyraPlayerController.h"
#include "UI/LyraHUD.h"
#include "Weapons/LyraRangedWeaponInstance.h"
#include "Animation/AnimInstance.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "BaselineEquipment.generated.h"

class UBoxComponent;
class USkeletalMeshComponent;
class ULyraInventoryManagerComponent;
class ULyraInventoryItemDefinition;
class ULyraInventoryItemInstance;
class ULyraQuickBarComponent;
class ULyraEquipmentManagerComponent;
class ULyraWeaponStateComponent;
class UAnimSequence;
class UAnimMontage;
class UBlendSpace;
class UCRWeaponEffectsProfile;

UCLASS()
class UBaselineAnimationLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintPure, Category="Baseline|Animation")
    static AActor* GetGameplayOwner(UActorComponent* Component);
};

USTRUCT(BlueprintType)
struct FBaselineItemStat
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FGameplayTag Tag;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) int32 Count = 0;
};

/** A recoverable world item. All pickup transactions are checked on the server. */
UCLASS(Blueprintable)
class ABaselineWeaponPickup : public AActor
{
    GENERATED_BODY()
public:
    ABaselineWeaponPickup();
    UPROPERTY(EditAnywhere, BlueprintReadOnly, ReplicatedUsing=OnRep_Definition, Category="Baseline|Item")
    TSubclassOf<ULyraInventoryItemDefinition> ItemDefinition;
    UPROPERTY(BlueprintReadOnly, Replicated, Category="Baseline|Item")
    TArray<FBaselineItemStat> SavedStats;
    UPROPERTY(BlueprintReadOnly, Replicated, Category="Baseline|Item")
    bool bHasSavedStats = false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<UBoxComponent> Collision;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<USkeletalMeshComponent> DisplayMesh;
    UFUNCTION(BlueprintPure) FText GetItemName() const;
    void CaptureItem(const ULyraInventoryItemInstance* Item);
    void RestoreItem(ULyraInventoryItemInstance* Item) const;
    void LaunchDrop(const FVector& Velocity);
    bool bClaimed = false;
    virtual void OnConstruction(const FTransform& Transform) override;
    virtual void BeginPlay() override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
private:
    UFUNCTION() void OnRep_Definition();
};

UCLASS()
class ABaselinePlayerController : public ALyraPlayerController
{
    GENERATED_BODY()
public:
    ABaselinePlayerController(const FObjectInitializer& ObjectInitializer = FObjectInitializer::Get());
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<ULyraInventoryManagerComponent> Inventory;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<ULyraQuickBarComponent> QuickBar;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<ULyraWeaponStateComponent> WeaponState;
};

/** Lyra equipment, inventory and ability sets; only world transfer/presentation is added. */
UCLASS(BlueprintType, meta=(BlueprintSpawnableComponent))
class UBaselineEquipmentComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UBaselineEquipmentComponent();
    UFUNCTION(BlueprintCallable) void Interact();
    UFUNCTION(Server, Reliable, BlueprintCallable) void ServerPickup(ABaselineWeaponPickup* Pickup);
    UFUNCTION(Server, Reliable, BlueprintCallable) void DropActiveWeapon();
    UFUNCTION(BlueprintCallable) void CycleWeapon();
    UFUNCTION(BlueprintPure) ABaselineWeaponPickup* FindPickup() const;
    UFUNCTION(BlueprintPure) ULyraInventoryItemInstance* GetActiveItem() const;
    UFUNCTION(BlueprintPure) USkeletalMeshComponent* GetPresentationMesh() const;
    UFUNCTION(BlueprintPure) USkeletalMeshComponent* GetWeaponAnimationMesh() const;
    UPROPERTY(EditDefaultsOnly, Category="Baseline|Animation") TSubclassOf<UAnimInstance> VisualRetargetAnimation;
    UFUNCTION(BlueprintPure) bool AreHandsBusy() const;
    UFUNCTION(BlueprintPure) bool ShouldHideWeapon() const;
    UFUNCTION(BlueprintPure) FRotator GetWeaponAimRotation() const;
    UFUNCTION(BlueprintPure) bool IsWeaponReady() const { return bWeaponReady; }
    bool IsFireRequested() const { return bFireRequested; }
    void BeginAim();
    void EndAim();
    void BeginFire();
    void EndFire();
    UFUNCTION(BlueprintCallable) void ToggleShoulder();
    bool CanChangeShoulder() const;
    UFUNCTION(BlueprintPure) bool IsLeftShoulder() const { return bLeftShoulder; }
    UFUNCTION(BlueprintPure) bool IsChangingShoulder() const { return ShoulderAge < .35f; }
    void HandleDeath();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Baseline|Interaction") float PickupDistance = 220.f;
    UPROPERTY(BlueprintReadOnly, Category="Baseline|Interaction") FString LastInteractionResult;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
private:
    void RefreshVisualOverride();
    TWeakObjectPtr<USkeletalMeshComponent> PreparedVisual;
    TWeakObjectPtr<USkeletalMeshComponent> PreparedAnimationMesh;
    bool CanReachPickup(const ABaselineWeaponPickup* Pickup) const;
    ULyraQuickBarComponent* GetQuickBar() const;
    ULyraInventoryManagerComponent* GetInventory() const;
    bool bWasHandsBusy = false;
    bool bWasWeaponHidden = false;
    bool bAimRequested = false;
    bool bFireRequested = false;
    double FireReadyUntil = 0.0;
    UFUNCTION(Server, Reliable) void ServerSetWeaponInput(bool bAim, bool bFire);
    void SetWeaponInput(bool bAim, bool bFire);
    UPROPERTY(Replicated) bool bWeaponReady = false;
    UPROPERTY(Replicated) FRotator ReplicatedAimRotation = FRotator::ZeroRotator;
    UFUNCTION(Server, Reliable) void ServerSetShoulder(bool bLeft);
    UFUNCTION(Client, Reliable) void ClientConfirmShoulder(bool bLeft);
    UFUNCTION() void OnRep_Shoulder();
    void SetShoulder(bool bLeft);
    UPROPERTY(ReplicatedUsing=OnRep_Shoulder) bool bLeftShoulder = false;
    float ShoulderAge = 1.f;
    TWeakObjectPtr<AActor> TransferringWeapon;
    FTransform HandTransferOffset;
    float HandTransferAge = 1.f;
};

/** Reuses Lyra's ranged tuning with presentation on the visible retargeted mesh. */
UCLASS(Blueprintable)
class UBaselineWeaponInstance : public ULyraRangedWeaponInstance
{
    GENERATED_BODY()
public:
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Crusader|Effects") TObjectPtr<UCRWeaponEffectsProfile> EffectsProfile;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Baseline|Animation") TObjectPtr<UAnimSequence> HoldAnimation;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Baseline|Animation") TObjectPtr<UAnimSequence> CarryAnimation;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Baseline|Animation") TObjectPtr<UBlendSpace> AimOffset;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Baseline|Animation") TObjectPtr<UAnimMontage> WeaponEquipMontage;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Baseline|Animation") TObjectPtr<UAnimMontage> WeaponUnequipMontage;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Baseline|Animation") TObjectPtr<UAnimMontage> MeleeAttackMontage;
    virtual void OnEquipped() override;
};

UCLASS(Transient, Blueprintable)
class UBaselineAnimInstance : public UAnimInstance
{
    GENERATED_BODY()
public:
    UPROPERTY(BlueprintReadOnly, Transient) TObjectPtr<UAnimSequence> WeaponPose;
    UPROPERTY(BlueprintReadOnly, Transient) TObjectPtr<UAnimSequence> WeaponCarryPose;
    UPROPERTY(BlueprintReadOnly, Transient) TObjectPtr<UBlendSpace> WeaponAimOffset;
    UPROPERTY(BlueprintReadOnly, Transient) float AimYaw = 0.f;
    UPROPERTY(BlueprintReadOnly, Transient) float AimPitch = 0.f;
    UPROPERTY(BlueprintReadOnly, Transient) float WeaponReadyWeight = 0.f;
    UPROPERTY(BlueprintReadOnly, Transient) FRotator WeaponRootRotation = FRotator::ZeroRotator;
    UPROPERTY(BlueprintReadOnly, Transient) float WeaponPoseWeight = 0.f;
    UPROPERTY(BlueprintReadOnly, Transient) float WeaponUpperBodyWeight = 0.f;
    UPROPERTY(BlueprintReadOnly, Transient) bool bWeaponLeftHand = false;
    virtual void NativeUpdateAnimation(float DeltaSeconds) override;
};

UCLASS()
class ABaselineHUD : public ALyraHUD
{
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
};
