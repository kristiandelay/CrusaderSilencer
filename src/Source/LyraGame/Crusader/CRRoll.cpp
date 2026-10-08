#include "CRRoll.h"
#include "CRTraversalCharacter.h"
#include "CRRobotCharacter.h"
#include "AbilitySystem/LyraAbilitySystemComponent.h"
#include "Baseline/BaselineCharacterMovement.h"
#include "Baseline/BaselineEquipment.h"
#include "Baseline/BaselinePhysicalInteraction.h"
#include "Character/LyraHealthComponent.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/GameStateBase.h"
#include "GameplayEffectComponents/TargetTagsGameplayEffectComponent.h"
#include "NativeGameplayTags.h"
#include "Net/UnrealNetwork.h"
#include "TimerManager.h"

UE_DEFINE_GAMEPLAY_TAG_STATIC(TAG_CRRolledInput,"InputTag.Movement.Roll");
UE_DEFINE_GAMEPLAY_TAG_STATIC(TAG_CRRollAbility,"Ability.Type.Action.Roll");
UE_DEFINE_GAMEPLAY_TAG_STATIC(TAG_CRRolling,"Crusader.State.Rolling");
UE_DEFINE_GAMEPLAY_TAG_STATIC(TAG_CRRollCooldown,"Crusader.Cooldown.Roll");

UCRRollComponent::UCRRollComponent()
{
    SetIsReplicatedByDefault(true);
    PrimaryComponentTick.bCanEverTick=true;
}

ACRTraversalCharacter* UCRRollComponent::Character() const { return Cast<ACRTraversalCharacter>(GetOwner()); }

void UCRRollComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(UCRRollComponent,State);
}

bool UCRRollComponent::CanStartRoll() const
{
    const auto* C=Character();
    if (!C || C->IsA<ACRRobotCharacter>() || bRolling || Montages.Num()!=8 || C->PhysicalInteraction->IsBusy()) return false;
    const auto* Health=ULyraHealthComponent::FindHealthComponent(C);
    const auto* Move=Cast<UBaselineCharacterMovement>(C->GetCharacterMovement());
    return (!Health || !Health->IsDeadOrDying()) && Move && Move->IsMovingOnGround()
        && !Move->IsSliding() && !Move->bWantsToSlide && Move->GetSlideRecoveryRemaining()<=0.f
        && !C->BaselineEquipment->AreHandsBusy() && !C->BaselineEquipment->IsChangingShoulder()
        && C->GetMesh()->GetAnimInstance();
}

int32 UCRRollComponent::SelectDirection() const
{
    const auto* C=Character();
    if (!C) return 0;
    // Input is queued before CMC consumes it. Prefer this frame so pressing a
    // direction and Roll together does not select last frame's direction.
    FVector Direction=RequestedDirection.Get(C->GetPendingMovementInputVector());
    if (Direction.IsNearlyZero()) Direction=C->GetLastMovementInputVector();
    if (Direction.IsNearlyZero()) Direction=C->GetCharacterMovement()->GetCurrentAcceleration();
    if (Direction.IsNearlyZero()) Direction=C->GetVelocity();
    // Normalized diagonal inputs can be just below 1 due to float rounding.
    // Only discard a zero direction; partial analog input is valid as well.
    if (Direction.SizeSquared2D()<=UE_SMALL_NUMBER) return 0;
    const FVector Local=C->GetActorTransform().InverseTransformVectorNoScale(Direction.GetSafeNormal2D());
    return (FMath::RoundToInt(FMath::RadiansToDegrees(FMath::Atan2(Local.Y,Local.X))/45.f)+8)%8;
}

bool UCRRollComponent::RequestRoll(FVector WorldDirection)
{
    auto* C=Character();
    if (!C || !C->HasAuthority() || !CanStartRoll()) return false;
    auto* ASC=C->GetLyraAbilitySystemComponent();
    if (!ASC) return false;
    RequestedDirection=WorldDirection;
    const bool bStarted=ASC->TryActivateAbilityByClass(UCRRollAbility::StaticClass());
    RequestedDirection.Reset();
    return bStarted;
}

float UCRRollComponent::GetCooldownDuration(int32 Direction) const
{
    return (Montages.IsValidIndex(Direction) && Montages[Direction] ? Montages[Direction]->GetPlayLength()/PlayRate : 1.f)+RecoveryTime;
}

bool UCRRollComponent::StartRoll(int32 Direction)
{
    if (!CanStartRoll() || !Montages.IsValidIndex(Direction) || !Montages[Direction]) return false;
    auto* C=Character();
    bWasCrouched=C->bIsCrouched;
    if (C->HasAuthority())
    {
        State.bActive=true;State.Direction=Direction;++State.Serial;
        State.ServerStartTime=GetWorld()->GetGameState() ? GetWorld()->GetGameState()->GetServerWorldTimeSeconds() : GetWorld()->GetTimeSeconds();
        C->ForceNetUpdate();
    }
    else bPredictionPending=true;
    C->Crouch();
    C->BaselineEquipment->EndFire();
    PlayRoll(Direction);
    return bRolling;
}

void UCRRollComponent::PlayRoll(int32 Direction,float Position)
{
    auto* C=Character();auto* Anim=C ? C->GetMesh()->GetAnimInstance() : nullptr;
    if (!Anim || !Montages.IsValidIndex(Direction) || !Montages[Direction]) return;
    ActiveMontage=Montages[Direction];ActiveDirection=Direction;
    bRolling=Anim->Montage_Play(ActiveMontage,PlayRate,EMontagePlayReturnType::MontageLength,Position)>0.f;
    if (bRolling)
    {
        ++RollsStarted;
        FOnMontageEnded Delegate;Delegate.BindUObject(this,&ThisClass::MontageEnded);
        Anim->Montage_SetEndDelegate(Delegate,ActiveMontage);
    }
}

void UCRRollComponent::MontageEnded(UAnimMontage* Montage,bool bInterrupted)
{
    if (Montage==ActiveMontage && bRolling) StopRoll(bInterrupted);
}

void UCRRollComponent::StopRoll(bool bInterrupted)
{
    const bool bWasRolling=bRolling;bRolling=false;
    auto* C=Character();
    if (!C) return;
    if (C->HasAuthority()) { State.bActive=false;C->ForceNetUpdate(); }
    if (bInterrupted) bPredictionPending=false;
    if (!bWasRolling) return;
    if (auto* Anim=C->GetMesh()->GetAnimInstance();Anim && bInterrupted && ActiveMontage)
        Anim->Montage_Stop(.12f,ActiveMontage);
    if ((C->HasAuthority() || C->IsLocallyControlled()) && !bWasCrouched) C->UnCrouch();
    OnRollFinished.Broadcast(bInterrupted);
}

void UCRRollComponent::OnRep_State()
{
    auto* C=Character();if (!C) return;
    if (!State.bActive) { bPredictionPending=false;StopRoll(true);return; }
    // Acknowledging the predicted roll must never restart its montage.
    if (C->IsLocallyControlled() && bPredictionPending && ActiveDirection==State.Direction)
    {
        bPredictionPending=false;return;
    }
    if (bRolling && ActiveDirection==State.Direction) return;
    const float Now=GetWorld()->GetGameState() ? GetWorld()->GetGameState()->GetServerWorldTimeSeconds() : State.ServerStartTime;
    const float Position=FMath::Max(0.f,Now-State.ServerStartTime)*PlayRate;
    if (Montages.IsValidIndex(State.Direction) && Montages[State.Direction] && Position<Montages[State.Direction]->GetPlayLength())
        PlayRoll(State.Direction,Position);
}

void UCRRollComponent::TickComponent(float Delta,ELevelTick Type,FActorComponentTickFunction* Function)
{
    Super::TickComponent(Delta,Type,Function);
    if (!bRolling) return;
    auto* C=Character();
    const auto* Health=C ? ULyraHealthComponent::FindHealthComponent(C) : nullptr;
    if (!C || C->PhysicalInteraction->IsBusy() || (Health && Health->IsDeadOrDying()) || C->GetCharacterMovement()->IsFalling())
        StopRoll(true);
}

UCRRollCooldown::UCRRollCooldown()
{
    DurationPolicy=EGameplayEffectDurationType::HasDuration;
    DurationMagnitude=FScalableFloat(1.42f);
    FInheritedTagContainer Tags;Tags.AddTag(TAG_CRRollCooldown);
    auto* GrantedTags=CreateDefaultSubobject<UTargetTagsGameplayEffectComponent>(TEXT("RollCooldownTags"));
    GEComponents.Add(GrantedTags);
    GrantedTags->SetAndApplyTargetTagChanges(Tags);
}

UCRRollAbility::UCRRollAbility(const FObjectInitializer& Initializer):Super(Initializer)
{
    InstancingPolicy=EGameplayAbilityInstancingPolicy::InstancedPerActor;
    NetExecutionPolicy=EGameplayAbilityNetExecutionPolicy::LocalPredicted;
    ActivationPolicy=ELyraAbilityActivationPolicy::OnInputTriggered;
    SetAssetTags(FGameplayTagContainer(TAG_CRRollAbility));
    ActivationOwnedTags.AddTag(TAG_CRRolling);
    ActivationBlockedTags.AddTag(FGameplayTag::RequestGameplayTag(TEXT("Status.Death")));
    ActivationBlockedTags.AddTag(FGameplayTag::RequestGameplayTag(TEXT("Baseline.State.HandsBusy")));
    BlockAbilitiesWithTag.AddTag(FGameplayTag::RequestGameplayTag(TEXT("Ability.Type.Action.WeaponFire")));
    BlockAbilitiesWithTag.AddTag(FGameplayTag::RequestGameplayTag(TEXT("Ability.Type.Action.Reload")));
    CancelAbilitiesWithTag=BlockAbilitiesWithTag;
    CooldownGameplayEffectClass=UCRRollCooldown::StaticClass();
}

bool UCRRollAbility::CanActivateAbility(const FGameplayAbilitySpecHandle Handle,const FGameplayAbilityActorInfo* Info,
    const FGameplayTagContainer* SourceTags,const FGameplayTagContainer* TargetTags,FGameplayTagContainer* RelevantTags) const
{
    const auto* C=Info ? Cast<ACRTraversalCharacter>(Info->AvatarActor.Get()) : nullptr;
    return C && C->Roll && C->Roll->CanStartRoll() && Super::CanActivateAbility(Handle,Info,SourceTags,TargetTags,RelevantTags);
}

void UCRRollAbility::ActivateAbility(const FGameplayAbilitySpecHandle Handle,const FGameplayAbilityActorInfo* Info,
    const FGameplayAbilityActivationInfo ActivationInfo,const FGameplayEventData* Event)
{
    Super::ActivateAbility(Handle,Info,ActivationInfo,Event);
    auto* C=Cast<ACRTraversalCharacter>(Info->AvatarActor.Get());
    if (!C || !C->Roll) { EndAbility(Handle,Info,ActivationInfo,true,true);return; }
    Roll=C->Roll;bDirectionReceived=false;
    auto* ASC=Info->AbilitySystemComponent.Get();
    DirectionDelegate=ASC->AbilityTargetDataSetDelegate(Handle,ActivationInfo.GetActivationPredictionKey()).AddUObject(this,&ThisClass::DirectionReceived);
    if (Info->IsLocallyControlled() || (Info->IsNetAuthority() && !C->IsPlayerControlled()))
    {
        FGameplayAbilityTargetDataHandle Data;
        auto* Selection=new FCRRollTargetData();
        Selection->Direction=Roll->SelectDirection();Data.Add(Selection);
        DirectionReceived(Data,FGameplayTag());
    }
    else
    {
        GetWorld()->GetTimerManager().SetTimer(DirectionTimer,this,&ThisClass::DirectionTimedOut,2.f,false);
        ASC->CallReplicatedTargetDataDelegatesIfSet(Handle,ActivationInfo.GetActivationPredictionKey());
    }
}

void UCRRollAbility::DirectionReceived(const FGameplayAbilityTargetDataHandle& Data,FGameplayTag Tag)
{
    if (!IsActive() || bDirectionReceived) return;
    auto* ASC=CurrentActorInfo->AbilitySystemComponent.Get();
    FScopedPredictionWindow Prediction(ASC);
    if (CurrentActorInfo->IsLocallyControlled() && !CurrentActorInfo->IsNetAuthority())
        ASC->CallServerSetReplicatedTargetData(CurrentSpecHandle,CurrentActivationInfo.GetActivationPredictionKey(),Data,Tag,ASC->ScopedPredictionKey);
    const bool bValid=Data.Num()==1 && Data.Get(0) && Data.Get(0)->GetScriptStruct()==FCRRollTargetData::StaticStruct();
    SelectedDirection=bValid ? static_cast<const FCRRollTargetData*>(Data.Get(0))->Direction : -1;
    ASC->ConsumeClientReplicatedTargetData(CurrentSpecHandle,CurrentActivationInfo.GetActivationPredictionKey());
    GetWorld()->GetTimerManager().ClearTimer(DirectionTimer);
    if (!bValid || SelectedDirection<0 || SelectedDirection>=8 || !Roll.IsValid() || !Roll->CanStartRoll())
    {
        EndAbility(CurrentSpecHandle,CurrentActorInfo,CurrentActivationInfo,true,true);return;
    }
    bDirectionReceived=true;
    if (!CommitAbility(CurrentSpecHandle,CurrentActorInfo,CurrentActivationInfo))
    {
        EndAbility(CurrentSpecHandle,CurrentActorInfo,CurrentActivationInfo,true,true);return;
    }
    FinishDelegate=Roll->OnRollFinished.AddUObject(this,&ThisClass::RollFinished);
    if (!Roll->StartRoll(SelectedDirection)) EndAbility(CurrentSpecHandle,CurrentActorInfo,CurrentActivationInfo,true,true);
}

void UCRRollAbility::ApplyCooldown(const FGameplayAbilitySpecHandle Handle,const FGameplayAbilityActorInfo* Info,const FGameplayAbilityActivationInfo ActivationInfo) const
{
    auto Spec=MakeOutgoingGameplayEffectSpec(CooldownGameplayEffectClass,GetAbilityLevel(Handle,Info));
    if (Spec.IsValid() && Roll.IsValid())
    {
        Spec.Data->SetDuration(Roll->GetCooldownDuration(SelectedDirection),true);
        ApplyGameplayEffectSpecToOwner(Handle,Info,ActivationInfo,Spec);
    }
}

void UCRRollAbility::RollFinished(bool bInterrupted)
{
    if (IsActive()) EndAbility(CurrentSpecHandle,CurrentActorInfo,CurrentActivationInfo,true,bInterrupted);
}

void UCRRollAbility::DirectionTimedOut()
{
    if (IsActive()) EndAbility(CurrentSpecHandle,CurrentActorInfo,CurrentActivationInfo,true,true);
}

void UCRRollAbility::EndAbility(const FGameplayAbilitySpecHandle Handle,const FGameplayAbilityActorInfo* Info,
    const FGameplayAbilityActivationInfo ActivationInfo,bool bReplicate,bool bCancelled)
{
    if (!IsEndAbilityValid(Handle,Info)) return;
    GetWorld()->GetTimerManager().ClearTimer(DirectionTimer);
    if (Roll.IsValid())
    {
        Roll->OnRollFinished.Remove(FinishDelegate);
        Roll->StopRoll(bCancelled);
    }
    if (auto* ASC=Info->AbilitySystemComponent.Get())
    {
        ASC->AbilityTargetDataSetDelegate(Handle,ActivationInfo.GetActivationPredictionKey()).Remove(DirectionDelegate);
        ASC->ConsumeClientReplicatedTargetData(Handle,ActivationInfo.GetActivationPredictionKey());
    }
    Super::EndAbility(Handle,Info,ActivationInfo,bReplicate,bCancelled);
}
