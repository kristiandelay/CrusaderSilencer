#pragma once

#include "AbilitySystem/Abilities/LyraGameplayAbility_Death.h"
#include "BaselineDeathAbility.generated.h"

/** Use Lyra's death cancellation/tags, then complete a short physical death. */
UCLASS()
class UBaselineDeathAbility : public ULyraGameplayAbility_Death
{
    GENERATED_BODY()
protected:
    virtual void ActivateAbility(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo,
        const FGameplayAbilityActivationInfo ActivationInfo, const FGameplayEventData* TriggerEventData) override;
    virtual void EndAbility(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo,
        const FGameplayAbilityActivationInfo ActivationInfo, bool bReplicateEndAbility, bool bWasCancelled) override;
    void CompleteDeath();
    FTimerHandle DeathTimer;
};
