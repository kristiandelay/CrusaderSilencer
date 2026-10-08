#include "CRThrowable.h"
#include "CRDestructibleActor.h"
#include "CRTraversalCharacter.h"
#include "CRRobotCharacter.h"
#include "CRRoll.h"
#include "Baseline/BaselineEquipment.h"
#include "Baseline/BaselinePhysicalInteraction.h"
#include "Baseline/BaselineCharacterMovement.h"
#include "AbilitySystemGlobals.h"
#include "AbilitySystemComponent.h"
#include "Character/LyraHealthComponent.h"
#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/DecalComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/ProjectileMovementComponent.h"
#include "GameFramework/GameStateBase.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSequence.h"
#include "Particles/ParticleSystemComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Perception/AISense_Hearing.h"
#include "EngineUtils.h"
#include "Net/UnrealNetwork.h"

namespace
{
constexpr float ObjectRadius=7.f;
void IgnoreCharacter(FCollisionQueryParams& Query,const AActor* Character)
{
    Query.AddIgnoredActor(Character);
    TArray<AActor*> Attached;Character->GetAttachedActors(Attached,true,true);Query.AddIgnoredActors(Attached);
}
}

ACRThrownObject::ACRThrownObject()
{
    bReplicates=true;SetReplicateMovement(true);SetNetUpdateFrequency(40.f);
    PrimaryActorTick.bCanEverTick=true;
    Collision=CreateDefaultSubobject<USphereComponent>(TEXT("Collision"));SetRootComponent(Collision);
    Collision->InitSphereRadius(ObjectRadius);Collision->SetCollisionProfileName(TEXT("BlockAllDynamic"));
    Collision->SetCollisionResponseToChannel(ECC_Camera,ECR_Ignore);Collision->SetCanEverAffectNavigation(false);
    Mesh=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));Mesh->SetupAttachment(Collision);
    Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);Mesh->SetCanEverAffectNavigation(false);Mesh->SetRelativeScale3D(FVector(.65f));
    Movement=CreateDefaultSubobject<UProjectileMovementComponent>(TEXT("Movement"));
    Movement->UpdatedComponent=Collision;Movement->bAutoActivate=false;Movement->ProjectileGravityScale=1.f;
    Movement->bShouldBounce=true;Movement->Bounciness=.35f;Movement->Friction=.4f;
    Movement->BounceVelocityStopSimulatingThreshold=55.f;Movement->bForceSubStepping=true;
    Movement->MaxSimulationTimeStep=1.f/60.f;Movement->MaxSimulationIterations=8;
    Movement->bRotationFollowsVelocity=false;
}

void ACRThrownObject::BeginPlay()
{
    Super::BeginPlay();OnRep_Type();
    if (GetInstigator())
    {
        Collision->IgnoreActorWhenMoving(GetInstigator(),true);
        TArray<AActor*> Attached;GetInstigator()->GetAttachedActors(Attached,true,true);
        for (auto* Actor:Attached) Collision->IgnoreActorWhenMoving(Actor,true);
    }
    Movement->OnProjectileBounce.AddDynamic(this,&ThisClass::OnBounce);
    if (!HasAuthority()) { Movement->Deactivate();Collision->SetCollisionEnabled(ECollisionEnabled::NoCollision); }
}
void ACRThrownObject::Launch(const FVector& Velocity)
{
    if (!HasAuthority()) return;
    Movement->Velocity=Velocity;Movement->Activate();
    FuseAt=GetWorld()->GetTimeSeconds()+(Type==ECRThrowableType::Grenade ? GrenadeFuse : SmokeFuse);
}
float ACRThrownObject::ServerTime() const
{
    return GetWorld()->GetGameState() ? GetWorld()->GetGameState()->GetServerWorldTimeSeconds() : GetWorld()->GetTimeSeconds();
}
void ACRThrownObject::Tick(float Delta)
{
    Super::Tick(Delta);
    if (HasAuthority() && !bDetonated && FuseAt>0. && GetWorld()->GetTimeSeconds()>=FuseAt) Detonate();
    if (bDetonated && Smoke)
    {
        const float Age=FMath::Max(0.f,ServerTime()-DetonationTime);
        const float Envelope=FMath::Min(FMath::Clamp(Age/.7f,0.f,1.f),FMath::Clamp((SmokeDuration-Age)/1.5f,0.f,1.f));
        Smoke->SetWorldScale3D(FVector(FMath::Max(.01f,Envelope)*4.f));
    }
}
void ACRThrownObject::OnRep_Type() { Mesh->SetStaticMesh(Type==ECRThrowableType::Grenade ? GrenadeMesh : SmokeMesh); }
void ACRThrownObject::OnBounce(const FHitResult& Hit,const FVector& Velocity)
{
    if (!HasAuthority()) return;
    if (BounceCount++==0) FirstImpact=Hit.ImpactPoint;
    if (Velocity.Size()>100.f && GetWorld()->GetTimeSeconds()>NextBounceSound && BounceSound)
    {
        PlayBounce(Hit.ImpactPoint);
        NextBounceSound=GetWorld()->GetTimeSeconds()+.12;
    }
}
void ACRThrownObject::PlayBounce_Implementation(FVector_NetQuantize Location)
{
    if (GetNetMode()!=NM_DedicatedServer && BounceSound) UGameplayStatics::PlaySoundAtLocation(this,BounceSound,Location,.3f);
}
void ACRThrownObject::EndPlay(const EEndPlayReason::Type Reason)
{
    if (Smoke) Smoke->DestroyComponent();
    Super::EndPlay(Reason);
}
void ACRThrownObject::Detonate()
{
    if (!HasAuthority() || bDetonated) return;
    Movement->StopMovementImmediately();Movement->Deactivate();
    Collision->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    DetonationLocation=GetActorLocation();DetonationTime=ServerTime();bDetonated=true;
    if (Type==ECRThrowableType::Grenade)
    {
        ApplyBlastDamage();
        ACRDestructibleActor::ApplyExplosion(GetWorld(),DetonationLocation,BlastRadius,this);
        UAISense_Hearing::ReportNoiseEvent(this,DetonationLocation,1.f,GetInstigator(),5000.f,TEXT("Gunfire"));
    }
    OnRep_Detonated();ForceNetUpdate();SetLifeSpan(Type==ECRThrowableType::Smoke ? SmokeDuration : 2.5f);
}
void ACRThrownObject::ApplyBlastDamage()
{
    if (!DamageEffect) return;
    auto* SourceASC=UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(GetInstigator());
    if (!SourceASC) return;
    for (TActorIterator<APawn> It(GetWorld());It;++It)
    {
        APawn* Target=*It;auto* TargetASC=UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(Target);
        const auto* Health=ULyraHealthComponent::FindHealthComponent(Target);
        const float Distance=FVector::Distance(Target->GetActorLocation(),DetonationLocation);
        if (!TargetASC || !Health || Health->IsDeadOrDying() || Distance>BlastRadius) continue;
        FCollisionQueryParams Query(SCENE_QUERY_STAT(GrenadeCover),true,this);IgnoreCharacter(Query,Target);
        if (GetInstigator() && Target!=GetInstigator()) IgnoreCharacter(Query,GetInstigator());
        FHitResult Hit;
        if (GetWorld()->LineTraceSingleByChannel(Hit,DetonationLocation,Target->GetActorLocation(),ECC_Visibility,Query)) continue;
        auto Context=SourceASC->MakeEffectContext();Context.AddInstigator(GetInstigator(),GetInstigator());Context.AddOrigin(DetonationLocation);
        auto Spec=SourceASC->MakeOutgoingSpec(DamageEffect,1.f,Context);
        if (Spec.IsValid())
        {
            const float Damage=MaximumDamage*FMath::Clamp(1.f-(Distance-100.f)/(BlastRadius-100.f),.15f,1.f);
            Spec.Data->SetSetByCallerMagnitude(FGameplayTag::RequestGameplayTag(TEXT("SetByCaller.Damage")),Damage);
            SourceASC->ApplyGameplayEffectSpecToTarget(*Spec.Data.Get(),TargetASC);
        }
    }
}
void ACRThrownObject::OnRep_Detonated()
{
    if (!bDetonated) return;
    Mesh->SetVisibility(Type==ECRThrowableType::Smoke);Movement->Deactivate();
    Collision->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    if (GetNetMode()==NM_DedicatedServer) return;
    if (Type==ECRThrowableType::Grenade)
    {
        if (ExplosionEffect) UGameplayStatics::SpawnEmitterAtLocation(GetWorld(),ExplosionEffect,DetonationLocation,FRotator::ZeroRotator,FVector(2.f));
        if (ExplosionSound) UGameplayStatics::PlaySoundAtLocation(this,ExplosionSound,DetonationLocation);
    }
    else if (SmokeEffect && !Smoke)
        Smoke=UGameplayStatics::SpawnEmitterAtLocation(GetWorld(),SmokeEffect,DetonationLocation,FRotator::ZeroRotator,FVector(.01f),false);
}
bool ACRThrownObject::IsSightObscured(const UObject* WorldContext,FVector Start,FVector End)
{
    const auto* World=WorldContext ? WorldContext->GetWorld() : nullptr;
    if (!World) return false;
    for (TActorIterator<ACRThrownObject> It(World);It;++It)
    {
        if (!It->bDetonated || It->Type!=ECRThrowableType::Smoke) continue;
        const float Age=It->ServerTime()-It->DetonationTime;
        const float Radius=It->SmokeRadius*FMath::Min(FMath::Clamp(Age/.7f,0.f,1.f),FMath::Clamp((It->SmokeDuration-Age)/1.5f,0.f,1.f));
        const FVector Center=FVector(It->DetonationLocation)+FVector(0,0,100);
        if (Radius>40.f && FVector::DistSquared(FMath::ClosestPointOnSegment(Center,Start,End),Center)<FMath::Square(Radius)) return true;
    }
    return false;
}
void ACRThrownObject::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ThisClass,Type);DOREPLIFETIME(ThisClass,bDetonated);DOREPLIFETIME(ThisClass,DetonationLocation);
    DOREPLIFETIME(ThisClass,DetonationTime);DOREPLIFETIME(ThisClass,BounceCount);DOREPLIFETIME(ThisClass,FirstImpact);
}

UCRThrowableComponent::UCRThrowableComponent()
{
    SetIsReplicatedByDefault(true);PrimaryComponentTick.bCanEverTick=true;
}
void UCRThrowableComponent::BeginPlay()
{
    Super::BeginPlay();
    // Preview and release use this frame's location, after movement prediction.
    if (auto* C=Character()) AddTickPrerequisiteComponent(C->GetCharacterMovement());
}
ACRTraversalCharacter* UCRThrowableComponent::Character() const { return Cast<ACRTraversalCharacter>(GetOwner()); }
bool UCRThrowableComponent::CanContinue() const
{
    const auto* C=Character();const auto* Health=C ? ULyraHealthComponent::FindHealthComponent(C) : nullptr;
    const auto* Move=C ? Cast<UBaselineCharacterMovement>(C->GetCharacterMovement()) : nullptr;
    return C && !C->IsA<ACRRobotCharacter>() && ProjectileClass && AimAnimation && ThrowMontage && LeftAimAnimation && LeftThrowMontage && Move && Move->IsMovingOnGround()
        && !C->Roll->IsRolling() && !C->PhysicalInteraction->IsBusy() && (!Health || !Health->IsDeadOrDying());
}
bool UCRThrowableComponent::CanBeginAim() const
{
    return !IsBusy() && CanContinue() && GetRemaining()>0 && GetWorld()->GetTimeSeconds()>=NextThrowAt
        && !Character()->BaselineEquipment->AreHandsBusy() && !Character()->BaselineEquipment->IsChangingShoulder();
}
bool UCRThrowableComponent::CanSwapShoulder() const
{
    return Phase==ECRThrowPhase::Aiming && CanContinue();
}
bool UCRThrowableComponent::IsLeftThrowHand() const
{
    return Phase==ECRThrowPhase::Throwing ? bReleaseLeftHand
        : Character() && Character()->BaselineEquipment->IsLeftShoulder();
}
void UCRThrowableComponent::ShoulderChanged()
{
    if (Phase==ECRThrowPhase::Aiming) { UpdatePresentation();UpdatePreview(); }
}
void UCRThrowableComponent::SetPhase(ECRThrowPhase NewPhase)
{
    Phase=NewPhase;UpdatePresentation();GetOwner()->ForceNetUpdate();
    if (auto* ASC=UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(GetOwner()))
    {
        ASC->SetLooseGameplayTagCount(FGameplayTag::RequestGameplayTag(TEXT("Baseline.State.HandsBusy")),IsBusy()?1:0);
        if (IsBusy())
        {
            FGameplayTagContainer Tags;Tags.AddTag(FGameplayTag::RequestGameplayTag(TEXT("Ability.Type.Action.WeaponFire")));
            Tags.AddTag(FGameplayTag::RequestGameplayTag(TEXT("Ability.Type.Action.Reload")));ASC->CancelAbilities(&Tags);
        }
    }
}
void UCRThrowableComponent::BeginAim()
{
    if (!CanBeginAim()) return;
    if (!GetOwner()->HasAuthority()) SetPhase(ECRThrowPhase::Aiming);
    ServerBeginAim(SelectedType);
}
void UCRThrowableComponent::ServerBeginAim_Implementation(ECRThrowableType Kind)
{
    if (Kind!=ECRThrowableType::Grenade && Kind!=ECRThrowableType::Smoke) { ClientRejected();return; }
    if (IsBusy()) { ClientRejected();return; }
    SelectedType=Kind;
    if (!CanBeginAim()) { ClientRejected();return; }
    SetPhase(ECRThrowPhase::Aiming);
}
void UCRThrowableComponent::ReleaseThrow()
{
    if (Phase!=ECRThrowPhase::Aiming) return;
    FVector Start,Velocity;const auto Aim=Character()->GetBaseAimRotation();
    if (!CanContinue() || !CalculateLaunch(Aim,Start,Velocity)) { CancelThrow();return; }
    bReleaseLeftHand=Character()->BaselineEquipment->IsLeftShoulder();
    if (!GetOwner()->HasAuthority()) SetPhase(ECRThrowPhase::Throwing);
    ServerRelease(Aim);
}
void UCRThrowableComponent::ServerRelease_Implementation(FRotator Aim)
{
    if (Phase!=ECRThrowPhase::Aiming || !CanContinue() || GetRemaining()<=0 || Aim.ContainsNaN()
        || !CalculateLaunch(Aim,ReleaseOrigin,ReleaseVelocity)) { SetPhase(ECRThrowPhase::Idle);ClientRejected();return; }
    bReleaseLeftHand=Character()->BaselineEquipment->IsLeftShoulder();
    ReleaseAim=Aim;
    const double Now=GetWorld()->GetTimeSeconds();ReleaseAt=Now+ReleaseDelay;
    FinishAt=Now+(bReleaseLeftHand ? LeftThrowMontage : ThrowMontage)->GetPlayLength();
    bReleased=false;SetPhase(ECRThrowPhase::Throwing);
}
void UCRThrowableComponent::CancelThrow()
{
    if (Phase!=ECRThrowPhase::Aiming) return;
    if (!GetOwner()->HasAuthority()) SetPhase(ECRThrowPhase::Idle);
    ServerCancel();
}
void UCRThrowableComponent::ServerCancel_Implementation()
{
    if (Phase==ECRThrowPhase::Aiming) SetPhase(ECRThrowPhase::Idle);
}
void UCRThrowableComponent::ClientRejected_Implementation() { SetPhase(ECRThrowPhase::Idle); }
void UCRThrowableComponent::CycleType()
{
    if (IsBusy()) return;
    SelectedType=SelectedType==ECRThrowableType::Grenade ? ECRThrowableType::Smoke : ECRThrowableType::Grenade;
    ServerSelect(SelectedType);
}
void UCRThrowableComponent::ServerSelect_Implementation(ECRThrowableType Kind)
{
    if (!IsBusy() && (Kind==ECRThrowableType::Grenade || Kind==ECRThrowableType::Smoke)) SelectedType=Kind;
}
bool UCRThrowableComponent::CalculateLaunch(FRotator Aim,FVector& Start,FVector& Velocity) const
{
    const auto* C=Character();if (!C || Aim.ContainsNaN()) return false;
    Aim.Pitch=FMath::Clamp(FRotator::NormalizeAxis(Aim.Pitch),-60.f,70.f);Aim.Roll=0;
    const FRotator Yaw(0,Aim.Yaw,0);
    const FVector Chest=C->GetActorLocation()+FVector(0,0,48);
    Start=Chest+Yaw.Vector()*38.f+FRotationMatrix(Yaw).GetUnitAxis(EAxis::Y)*(IsLeftThrowHand() ? -24.f : 24.f);
    Velocity=Aim.Vector()*ThrowSpeed+FVector(0,0,UpwardBoost);
    FCollisionQueryParams Query(SCENE_QUERY_STAT(ThrowOrigin),false,C);IgnoreCharacter(Query,C);
    FHitResult Hit;
    return !GetWorld()->SweepSingleByChannel(Hit,Chest,Start,FQuat::Identity,ECC_WorldDynamic,FCollisionShape::MakeSphere(ObjectRadius),Query);
}
void UCRThrowableComponent::OnRep_Phase() { UpdatePresentation(); }
void UCRThrowableComponent::UpdatePresentation()
{
    auto* C=Character();if (!C || !C->GetMesh()->GetAnimInstance()) return;
    auto* Anim=C->GetMesh()->GetAnimInstance();
    const bool bLeft=IsLeftThrowHand();
    if (Phase!=PresentedPhase || (Phase==ECRThrowPhase::Aiming && bLeft!=bPresentedLeftHand))
    {
        if (Phase==ECRThrowPhase::Aiming)
        {
            C->BaselineEquipment->EndFire();
            Anim->Montage_StopGroupByName(.12f,TEXT("ThrowGroup"));
            AimMontage=UAnimMontage::CreateSlotAnimationAsDynamicMontage(bLeft ? LeftAimAnimation : AimAnimation,TEXT("ThrowUpperBody"),.12f,.15f,1.f,99999);
            Anim->Montage_Play(AimMontage,1.f,EMontagePlayReturnType::MontageLength,0.f,false);
        }
        else if (Phase==ECRThrowPhase::Throwing)
        {
            Anim->Montage_StopGroupByName(.1f,TEXT("ThrowGroup"));
            LocalThrowStarted=GetWorld()->GetTimeSeconds();
            Anim->Montage_Play(bLeft ? LeftThrowMontage : ThrowMontage,1.f,EMontagePlayReturnType::MontageLength,0.f,false);
        }
        else
        {
            if (AimMontage) Anim->Montage_Stop(.15f,AimMontage);
            if (ThrowMontage) Anim->Montage_Stop(.15f,ThrowMontage);
            if (LeftThrowMontage) Anim->Montage_Stop(.15f,LeftThrowMontage);
        }
        PresentedPhase=Phase;
        bPresentedLeftHand=bLeft;
    }
    if (!HeldObject && IsBusy() && GetNetMode()!=NM_DedicatedServer)
    {
        HeldObject=NewObject<UStaticMeshComponent>(C);HeldObject->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        HeldObject->SetCanEverAffectNavigation(false);HeldObject->RegisterComponent();
    }
    if (HeldObject)
    {
        const auto* Defaults=ProjectileClass ? ProjectileClass->GetDefaultObject<ACRThrownObject>() : nullptr;
        auto* Visible=C->BaselineEquipment->GetPresentationMesh();
        if (Defaults && Visible)
        {
            const FName Hand=bLeft ? TEXT("hand_l") : TEXT("hand_r");
            HeldObject->AttachToComponent(Visible,FAttachmentTransformRules::KeepWorldTransform,Hand);
            // Use source grip axes on custom visual overrides, too. Mirroring
            // the grip along with the arm preserves the canister's orientation.
            const FTransform SourceHand=C->GetMesh()->GetSocketTransform(Hand);
            const FTransform TargetHand=Visible->GetSocketTransform(Hand);
            FTransform WorldGrip=(bLeft ? LeftHandGrip : FTransform(FVector(4,0,0)))*SourceHand;
            WorldGrip.AddToTranslation(TargetHand.GetLocation()-SourceHand.GetLocation());
            FTransform Grip=WorldGrip.GetRelativeTransform(TargetHand);Grip.SetScale3D(FVector(.65f));
            HeldObject->SetRelativeTransform(Grip);
            HeldObject->SetStaticMesh(SelectedType==ECRThrowableType::Grenade ? Defaults->GrenadeMesh : Defaults->SmokeMesh);
        }
        HeldObject->SetVisibility(Phase==ECRThrowPhase::Aiming || (Phase==ECRThrowPhase::Throwing && GetWorld()->GetTimeSeconds()-LocalThrowStarted<ReleaseDelay));
    }
    if (Phase!=ECRThrowPhase::Aiming) HidePreview();
}
void UCRThrowableComponent::HidePreview()
{
    bPreviewVisible=false;PreviewPoints.Reset();
    if (Arc) Arc->SetVisibility(false);if (Landing) Landing->SetVisibility(false);
}
void UCRThrowableComponent::UpdatePreview()
{
    auto* C=Character();if (!C || !C->IsLocallyControlled() || GetNetMode()==NM_DedicatedServer) return;
    FVector Start,Velocity;bLaunchBlocked=!CalculateLaunch(C->GetBaseAimRotation(),Start,Velocity);
    if (bLaunchBlocked) { HidePreview();return; }
    FPredictProjectilePathParams Params(ObjectRadius,Start,Velocity,3.f,ECC_WorldDynamic,C);
    TArray<AActor*> Attached;C->GetAttachedActors(Attached,true,true);Params.ActorsToIgnore.Append(Attached);
    Params.SimFrequency=25.f;Params.bTraceComplex=false;
    FPredictProjectilePathResult Result;bPreviewHit=UGameplayStatics::PredictProjectilePath(this,Params,Result);
    PreviewPoints.Reset();for (const auto& Point:Result.PathData) PreviewPoints.Add(Point.Location);
    PredictedImpact=bPreviewHit ? Result.HitResult.ImpactPoint : Result.LastTraceDestination.Location;
    if (!Arc)
    {
        Arc=NewObject<UInstancedStaticMeshComponent>(C);Arc->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Arc->SetCanEverAffectNavigation(false);Arc->SetCastShadow(false);Arc->SetStaticMesh(TrajectoryMesh);
        Arc->SetMaterial(0,TrajectoryMaterial);Arc->RegisterComponent();
        Landing=NewObject<UDecalComponent>(C);Landing->SetDecalMaterial(LandingMaterial);Landing->DecalSize=FVector(16,32,32);Landing->RegisterComponent();
    }
    Arc->ClearInstances();Arc->SetVisibility(true);
    // Cylinder uses Z as its length; render actual predicted segments, not debug lines.
    for (int32 Index=1;Index<PreviewPoints.Num();++Index)
    {
        const FVector Delta=PreviewPoints[Index]-PreviewPoints[Index-1];
        Arc->AddInstance(FTransform(FRotationMatrix::MakeFromZ(Delta).ToQuat(),(PreviewPoints[Index]+PreviewPoints[Index-1])*.5,FVector(.018,.018,Delta.Length()/100.)),true);
    }
    Landing->SetWorldLocation(PredictedImpact+Result.HitResult.ImpactNormal*2.f);
    Landing->SetWorldRotation((-Result.HitResult.ImpactNormal).Rotation());Landing->SetVisibility(bPreviewHit);
    bPreviewVisible=true;
}
void UCRThrowableComponent::TickComponent(float Delta,ELevelTick Type,FActorComponentTickFunction* Function)
{
    Super::TickComponent(Delta,Type,Function);auto* C=Character();if (!C || !IsBusy()) return;
    if ((C->HasAuthority() || C->IsLocallyControlled()) && !CanContinue()) { SetPhase(ECRThrowPhase::Idle);return; }
    const auto* Move=CastChecked<UBaselineCharacterMovement>(C->GetCharacterMovement());
    // Sliding keeps the legs aligned with momentum; the torso aims independently.
    if (!Move->IsSliding() && (C->HasAuthority() || C->IsLocallyControlled()))
        C->SetActorRotation(FRotator(0,C->GetBaseAimRotation().Yaw,0));
    UpdatePresentation();
    if (Phase==ECRThrowPhase::Aiming) UpdatePreview();
    if (GetOwner()->HasAuthority() && Phase==ECRThrowPhase::Throwing)
    {
        const double Now=GetWorld()->GetTimeSeconds();
        if (!bReleased && Now>=ReleaseAt)
        {
            // Walking continues during release. Launch from the current hand side,
            // keeping the committed aim direction and checking cover again here.
            if (CalculateLaunch(ReleaseAim,ReleaseOrigin,ReleaseVelocity))
            {
                FTransform Transform(ReleaseVelocity.Rotation(),ReleaseOrigin);
                auto* Object=GetWorld()->SpawnActorDeferred<ACRThrownObject>(ProjectileClass,Transform,C,C,ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
                if (Object)
                {
                    Object->Type=SelectedType;Object->FinishSpawning(Transform);Object->Launch(ReleaseVelocity);
                    if (SelectedType==ECRThrowableType::Grenade) --Grenades;else --SmokeGrenades;
                    ++ThrowsReleased;
                }
            }
            bReleased=true;
        }
        if (Now>=FinishAt) { NextThrowAt=Now+.35;SetPhase(ECRThrowPhase::Idle); }
    }
}
void UCRThrowableComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    for (UActorComponent* Component:{static_cast<UActorComponent*>(HeldObject),static_cast<UActorComponent*>(Arc),static_cast<UActorComponent*>(Landing)})
        if (Component) Component->DestroyComponent();
    Super::EndPlay(Reason);
}
void UCRThrowableComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);DOREPLIFETIME(ThisClass,Phase);DOREPLIFETIME(ThisClass,SelectedType);
    DOREPLIFETIME(ThisClass,Grenades);DOREPLIFETIME(ThisClass,SmokeGrenades);DOREPLIFETIME(ThisClass,ThrowsReleased);
    DOREPLIFETIME(ThisClass,bReleaseLeftHand);
}
