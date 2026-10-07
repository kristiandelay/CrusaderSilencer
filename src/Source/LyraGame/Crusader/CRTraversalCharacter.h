#pragma once

#include "Character/LyraCharacter.h"
#include "Character/LyraHeroComponent.h"
#include "Camera/LyraCameraMode_ThirdPerson.h"
#include "GameModes/LyraGameMode.h"
#include "PoseSearch/PoseSearchResult.h"
#include "CRTraversalCharacter.generated.h"

class UBaselineEquipmentComponent;
class ULyraEquipmentManagerComponent;
class UAnimSequence;
class UAnimMontage;
class UPhysicsControlComponent;
class UBaselinePhysicalInteractionComponent;
class UChildActorComponent;
class UCRWeaponEffectsComponent;
class UCRFootstepComponent;
class UCRCrowdAgentComponent;

/** Lyra lifecycle and ability ownership for the GASP CMC animation/traversal graph. */
UCLASS()
class LYRAGAME_API ACRTraversalCharacter : public ALyraCharacter
{
    GENERATED_BODY()
public:
    ACRTraversalCharacter(const FObjectInitializer& ObjectInitializer = FObjectInitializer::Get());
    UFUNCTION(BlueprintCallable, Category="Baseline|Movement") void ToggleSlideCrouch();
    UFUNCTION(BlueprintImplementableEvent, Category="Baseline|Animation") void SetWeaponReadyForAnimation(bool bReady);
    UFUNCTION(BlueprintPure, Category="Baseline|Physical") FPoseSearchBlueprintResult GetPhysicalInteractionResult() const;
    UFUNCTION(BlueprintPure, Category="Baseline|Physical") bool CanUseMovementActions() const;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Baseline") TObjectPtr<UPhysicsControlComponent> PhysicsControl;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Baseline") TObjectPtr<UBaselinePhysicalInteractionComponent> PhysicalInteraction;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Baseline") TObjectPtr<UChildActorComponent> SelectedVisualOverride;
    bool IsSlideMontage(const UAnimMontage* Montage) const { return Montage && Montage == SlideMontage; }
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Baseline") TObjectPtr<UBaselineEquipmentComponent> BaselineEquipment;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Crusader") TObjectPtr<UCRWeaponEffectsComponent> WeaponEffects;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Crusader") TObjectPtr<UCRFootstepComponent> Footsteps;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Crusader") TObjectPtr<UCRCrowdAgentComponent> CrowdAgent;
    UFUNCTION(BlueprintCallable, Category="Crusader|Movement") bool RequestAITraversal();
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Baseline") TObjectPtr<ULyraEquipmentManagerComponent> EquipmentManager;
    UPROPERTY(EditDefaultsOnly, Category="Baseline|Slide") TObjectPtr<UAnimSequence> SlideAnimation;
protected:
    virtual void BeginPlay() override;
    virtual void OnMovementModeChanged(EMovementMode PreviousMovementMode, uint8 PreviousCustomMode = 0) override;
    virtual void OnAbilitySystemInitialized() override;
    virtual void OnDeathStarted(AActor* OwningActor) override;
    virtual void OnDeathFinished(AActor* OwningActor) override;
    void FinishCombatDeath();
    FTransform InitialSpawnTransform;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Crusader")
    TObjectPtr<ULyraHeroComponent> HeroComponent;
    UFUNCTION() void OnSlideChanged(bool bSliding);
    UPROPERTY(Transient) TObjectPtr<UAnimMontage> SlideMontage;
};

/** GASP actions are bound once by the character graph; Lyra owns initialization. */
UCLASS()
class UCRTraversalHeroComponent : public ULyraHeroComponent
{
    GENERATED_BODY()
public:
    UCRTraversalHeroComponent(const FObjectInitializer& ObjectInitializer = FObjectInitializer::Get());
protected:
    virtual void InitializePlayerInput(UInputComponent* PlayerInputComponent) override;
};

UCLASS()
class UCRTraversalCameraMode : public ULyraCameraMode_ThirdPerson
{
    GENERATED_BODY()
public:
    UCRTraversalCameraMode();
protected:
    virtual void UpdateView(float DeltaTime) override;
    float ShoulderOffset = 50.f;
};

UCLASS()
class ACRTraversalGameMode : public ALyraGameMode
{
    GENERATED_BODY()
public:
    ACRTraversalGameMode(const FObjectInitializer& ObjectInitializer = FObjectInitializer::Get());
    virtual void InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage) override;
};
