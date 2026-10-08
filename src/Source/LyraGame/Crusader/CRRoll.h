#pragma once

#include "Components/ActorComponent.h"
#include "AbilitySystem/Abilities/LyraGameplayAbility.h"
#include "Abilities/GameplayAbilityTargetTypes.h"
#include "GameplayEffect.h"
#include "CRRoll.generated.h"

class ACRTraversalCharacter;
class UAnimMontage;

USTRUCT()
struct FCRRollTargetData : public FGameplayAbilityTargetData
{
    GENERATED_BODY()
    UPROPERTY() uint8 Direction=0;
    virtual UScriptStruct* GetScriptStruct() const override { return StaticStruct(); }
    bool NetSerialize(FArchive& Ar,UPackageMap* Map,bool& bSuccess)
    {
        Ar.SerializeBits(&Direction,3);bSuccess=true;return true;
    }
};
template<> struct TStructOpsTypeTraits<FCRRollTargetData> : TStructOpsTypeTraitsBase2<FCRRollTargetData>
{
    enum { WithNetSerializer=true,WithCopy=true };
};

USTRUCT()
struct FCRRollState
{
    GENERATED_BODY()
    UPROPERTY() bool bActive=false;
    UPROPERTY() uint8 Direction=0;
    UPROPERTY() uint16 Serial=0;
    UPROPERTY() float ServerStartTime=0.f;
};

DECLARE_MULTICAST_DELEGATE_OneParam(FCRRollFinished,bool);

/** Source-mesh montage presentation. CMC owns all swept root-motion movement. */
UCLASS(meta=(BlueprintSpawnableComponent))
class LYRAGAME_API UCRRollComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UCRRollComponent();
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
    virtual void TickComponent(float Delta,ELevelTick Type,FActorComponentTickFunction* Function) override;
    UFUNCTION(BlueprintPure,Category="Crusader|Roll") bool CanStartRoll() const;
    UFUNCTION(BlueprintPure,Category="Crusader|Roll") bool IsRolling() const { return bRolling; }
    UFUNCTION(BlueprintCallable,Category="Crusader|Roll") bool RequestRoll(FVector WorldDirection);
    /** Clockwise from forward: F, FR, R, BR, B, BL, L, FL. */
    UPROPERTY(EditDefaultsOnly,Category="Crusader|Roll") TArray<TObjectPtr<UAnimMontage>> Montages;
    UPROPERTY(EditDefaultsOnly,Category="Crusader|Roll",meta=(ClampMin="0.5",ClampMax="2.0")) float PlayRate=1.15f;
    UPROPERTY(EditDefaultsOnly,Category="Crusader|Roll",meta=(ClampMin="0.1",Units="s")) float RecoveryTime=.55f;
    UPROPERTY(BlueprintReadOnly,Category="Crusader|Roll") int32 RollsStarted=0;
    UPROPERTY(BlueprintReadOnly,Category="Crusader|Roll") int32 ActiveDirection=0;
    int32 SelectDirection() const;
    float GetCooldownDuration(int32 Direction) const;
    bool StartRoll(int32 Direction);
    void StopRoll(bool bInterrupted);
    FCRRollFinished OnRollFinished;
private:
    UFUNCTION() void OnRep_State();
    void PlayRoll(int32 Direction,float Position=0.f);
    void MontageEnded(UAnimMontage* Montage,bool bInterrupted);
    ACRTraversalCharacter* Character() const;
    UPROPERTY(ReplicatedUsing=OnRep_State) FCRRollState State;
    UPROPERTY(Transient) TObjectPtr<UAnimMontage> ActiveMontage;
    bool bRolling=false;
    bool bWasCrouched=false;
    bool bPredictionPending=false;
    TOptional<FVector> RequestedDirection;
};

UCLASS()
class LYRAGAME_API UCRRollCooldown : public UGameplayEffect
{
    GENERATED_BODY()
public:
    UCRRollCooldown();
};

/** Predicted GAS entry, validated direction and cooldown; no damage immunity. */
UCLASS()
class LYRAGAME_API UCRRollAbility : public ULyraGameplayAbility
{
    GENERATED_BODY()
public:
    UCRRollAbility(const FObjectInitializer& Initializer=FObjectInitializer::Get());
    virtual bool CanActivateAbility(const FGameplayAbilitySpecHandle Handle,const FGameplayAbilityActorInfo* Info,
        const FGameplayTagContainer* SourceTags=nullptr,const FGameplayTagContainer* TargetTags=nullptr,FGameplayTagContainer* RelevantTags=nullptr) const override;
    virtual void ActivateAbility(const FGameplayAbilitySpecHandle Handle,const FGameplayAbilityActorInfo* Info,
        const FGameplayAbilityActivationInfo ActivationInfo,const FGameplayEventData* Event) override;
    virtual void ApplyCooldown(const FGameplayAbilitySpecHandle Handle,const FGameplayAbilityActorInfo* Info,const FGameplayAbilityActivationInfo ActivationInfo) const override;
    virtual void EndAbility(const FGameplayAbilitySpecHandle Handle,const FGameplayAbilityActorInfo* Info,
        const FGameplayAbilityActivationInfo ActivationInfo,bool bReplicate,bool bCancelled) override;
private:
    void DirectionReceived(const FGameplayAbilityTargetDataHandle& Data,FGameplayTag Tag);
    void RollFinished(bool bInterrupted);
    void DirectionTimedOut();
    TWeakObjectPtr<UCRRollComponent> Roll;
    FDelegateHandle DirectionDelegate;
    FDelegateHandle FinishDelegate;
    FTimerHandle DirectionTimer;
    int32 SelectedDirection=0;
    bool bDirectionReceived=false;
};
