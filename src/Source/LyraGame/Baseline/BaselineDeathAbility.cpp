#include "BaselineDeathAbility.h"
#include "TimerManager.h"
#include "Engine/World.h"

void UBaselineDeathAbility::ActivateAbility(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo,
    const FGameplayAbilityActivationInfo ActivationInfo, const FGameplayEventData* TriggerEventData)
{
    Super::ActivateAbility(Handle, ActorInfo, ActivationInfo, TriggerEventData);
    if (ActorInfo->IsNetAuthority())
        GetWorld()->GetTimerManager().SetTimer(DeathTimer, this, &ThisClass::CompleteDeath, 3.f, false);
}

void UBaselineDeathAbility::CompleteDeath()
{
    EndAbility(CurrentSpecHandle, CurrentActorInfo, CurrentActivationInfo, true, false);
}

void UBaselineDeathAbility::EndAbility(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo,
    const FGameplayAbilityActivationInfo ActivationInfo, bool bReplicateEndAbility, bool bWasCancelled)
{
    GetWorld()->GetTimerManager().ClearTimer(DeathTimer);
    Super::EndAbility(Handle, ActorInfo, ActivationInfo, bReplicateEndAbility, bWasCancelled);
}
