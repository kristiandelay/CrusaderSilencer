#include "CRRobotCharacter.h"
#include "CRThrowable.h"
#include "CRCrowdAI.h"
#include "CRFootsteps.h"
#include "CRWeaponEffects.h"
#include "Baseline/BaselineEquipment.h"
#include "Baseline/BaselinePhysicalInteraction.h"
#include "AbilitySystem/LyraAbilitySystemComponent.h"
#include "AbilitySystem/Attributes/LyraHealthSet.h"
#include "Character/LyraHealthComponent.h"
#include "Teams/LyraTeamSubsystem.h"
#include "Physics/LyraCollisionChannels.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimTypes.h"
#include "Engine/SkeletalMesh.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "AbilitySystemGlobals.h"
#include "GameplayEffect.h"
#include "Net/UnrealNetwork.h"
#include "TimerManager.h"

ACRRobotCharacter::ACRRobotCharacter(const FObjectInitializer& Initializer) : Super(Initializer)
{
    AIControllerClass=ACRCrowdController::StaticClass();
    AutoPossessAI=EAutoPossessAI::PlacedInWorldOrSpawned;
    CrowdAgent->bEnabled=true;CrowdAgent->bGuard=true;CrowdAgent->bReturnFireOnly=true;
    CrowdAgent->PatrolSpeed=155.f;CrowdAgent->RunSpeed=320.f;CrowdAgent->CombatRange=1450.f;
    CrowdAgent->DesiredSpeed=CrowdAgent->PatrolSpeed;
    GetCapsuleComponent()->InitCapsuleSize(56.f,90.f);
    GetCapsuleComponent()->SetCollisionResponseToChannel(Lyra_TraceChannel_Weapon,ECR_Block);
    GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);
    GetMesh()->SetRelativeLocation(FVector(0,0,-90));
    GetMesh()->SetRelativeRotation(FRotator(0,-90,0));
    GetMesh()->SetAnimInstanceClass(UCRRobotAnimInstance::StaticClass());
    GetMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    GetMesh()->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    GetMesh()->bEnableUpdateRateOptimizations=false;
    auto* Movement=GetCharacterMovement();
    Movement->bOrientRotationToMovement=true;Movement->bUseControllerDesiredRotation=false;
    Movement->RotationRate=FRotator(0,220,0);Movement->MaxAcceleration=800.f;
    Movement->BrakingDecelerationWalking=900.f;Movement->MaxStepHeight=40.f;
    BaseEyeHeight=48.f;
    PhysicalInteraction->bAutoRecover=true;
    PhysicalInteraction->PrimaryComponentTick.bStartWithTickEnabled=false;
    BaselineEquipment->PrimaryComponentTick.bStartWithTickEnabled=false;
}

void ACRRobotCharacter::BeginPlay()
{
    Super::BeginPlay();
    PhysicalInteraction->SetComponentTickEnabled(false);
    BaselineEquipment->SetComponentTickEnabled(false);
    GetCapsuleComponent()->SetCollisionResponseToChannel(Lyra_TraceChannel_Weapon,ECR_Block);
    GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);
}

void ACRRobotCharacter::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ThisClass,MountedShots);DOREPLIFETIME(ThisClass,bShutdown);DOREPLIFETIME(ThisClass,LastMuzzlePosition);
}

void ACRRobotCharacter::OnAbilitySystemInitialized()
{
    Super::OnAbilitySystemInitialized();
    if (HasAuthority())
    {
        auto* ASC=GetLyraAbilitySystemComponent();
        ASC->SetNumericAttributeBase(ULyraHealthSet::GetMaxHealthAttribute(),ArmorHealth);
        ASC->SetNumericAttributeBase(ULyraHealthSet::GetHealthAttribute(),ArmorHealth);
    }
}

void ACRRobotCharacter::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!HasAuthority() || bShutdown) return;
    // The legs walk in their mechanical hinge plane. Face travel while moving;
    // once stopped, turn the whole chassis to bring the mounted guns to bear.
    if (CrowdAgent->bProvoked && IsValid(CrowdAgent->Threat) && GetVelocity().Size2D()<30.f)
    {
        FRotator Facing=(CrowdAgent->Threat->GetActorLocation()-GetActorLocation()).Rotation();
        Facing.Pitch=Facing.Roll=0.f;
        SetActorRotation(FMath::RInterpConstantTo(GetActorRotation(),Facing,DeltaSeconds,160.f));
    }
    if (BurstRemaining>0 && GetWorld()->GetTimeSeconds()>=NextMountedShot) FireMountedShot();
}

FVector ACRRobotCharacter::GetMountedMuzzle() const
{
    const FVector Point=MuzzlePositions.IsEmpty() ? FVector(0,48,135) : MuzzlePositions[MountedShots%MuzzlePositions.Num()];
    // Follow chassis recoil/shutdown motion while preserving the authored tip.
    const int32 Bone=GetMesh()->GetBoneIndex(TEXT("chassis"));
    if (Bone!=INDEX_NONE && GetMesh()->GetSkeletalMeshAsset())
    {
        const auto& Ref=GetMesh()->GetSkeletalMeshAsset()->GetRefSkeleton();
        FTransform Bind=Ref.GetRefBonePose()[Bone];
        for (int32 Parent=Ref.GetParentIndex(Bone);Parent!=INDEX_NONE;Parent=Ref.GetParentIndex(Parent)) Bind*=Ref.GetRefBonePose()[Parent];
        return GetMesh()->GetSocketTransform(TEXT("chassis")).TransformPosition(Bind.InverseTransformPosition(Point));
    }
    return GetMesh()->GetComponentTransform().TransformPosition(Point);
}

bool ACRRobotCharacter::HasFiringLane(AActor* Target,FVector& Origin,FVector& Aim) const
{
    if (bShutdown || !CrowdAgent->bProvoked || Target!=CrowdAgent->Threat || !IsValid(Target)) return false;
    if (const auto* Health=ULyraHealthComponent::FindHealthComponent(Target);Health && Health->IsDeadOrDying()) return false;
    const FVector TargetPoint=Target->GetActorLocation()+FVector(0,0,15);
    const FVector Delta=TargetPoint-GetActorLocation();
    if (Delta.SizeSquared()>FMath::Square(WeaponRange) || FVector::DotProduct(GetActorForwardVector(),Delta.GetSafeNormal2D())<.92f) return false;
    Origin=GetMountedMuzzle();Aim=(TargetPoint-Origin).GetSafeNormal();
    if (ACRThrownObject::IsSightObscured(this,Origin,TargetPoint)) return false;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(RobotFiringLane),true,this);
    FHitResult Hit;
    // Two channels: world visibility and the actual weapon hit channel. A clear
    // eye line alone must not permit a barrel to fire through cover or a pawn.
    for (const ECollisionChannel Channel : {ECC_Visibility,Lyra_TraceChannel_Weapon})
        if (GetWorld()->LineTraceSingleByChannel(Hit,Origin,TargetPoint,Channel,Query)
            && Hit.GetActor()!=Target && (!Hit.GetActor() || Hit.GetActor()->GetAttachParentActor()!=Target)) return false;
    // Human hit meshes can leave gaps between limbs, and their capsules ignore
    // visibility/weapon traces. Test occupied pawn space before firing past one.
    FCollisionObjectQueryParams Pawns;Pawns.AddObjectTypesToQuery(ECC_Pawn);
    if (GetWorld()->SweepSingleByObjectType(Hit,Origin,TargetPoint,FQuat::Identity,Pawns,FCollisionShape::MakeSphere(12.f),Query)
        && Hit.GetActor()!=Target && (!Hit.GetActor() || Hit.GetActor()->GetAttachParentActor()!=Target)) return false;
    // Catch a barrel poking through a thin wall even when its tip is beyond it.
    const FVector Body=GetActorLocation()+FVector(0,0,35);
    if (GetWorld()->LineTraceSingleByChannel(Hit,Body,Origin,ECC_Visibility,Query) && Hit.GetActor()!=Target) return false;
    return true;
}

bool ACRRobotCharacter::StartMountedBurst(AActor* Target)
{
    FVector Origin,Aim;
    if (!HasAuthority() || BurstRemaining>0 || !LaserEffects || !DamageEffect || !HasFiringLane(Target,Origin,Aim)) return false;
    BurstTarget=Target;BurstRemaining=3;NextMountedShot=GetWorld()->GetTimeSeconds();
    return true;
}

void ACRRobotCharacter::StopMountedBurst() { BurstRemaining=0;BurstTarget.Reset(); }

void ACRRobotCharacter::FireMountedShot()
{
    FVector Origin,Aim;
    if (!HasFiringLane(BurstTarget.Get(),Origin,Aim)) { StopMountedBurst();return; }
    auto* ASC=GetLyraAbilitySystemComponent();
    if (!ASC) { StopMountedBurst();return; }
    // Visible laser travel follows this accepted authoritative trace, matching
    // the player's weapon effects. Small spread avoids perfect AI accuracy.
    const FVector Direction=FMath::VRandCone(Aim,FMath::DegreesToRadians(1.2f));
    FCollisionQueryParams Query(SCENE_QUERY_STAT(RobotLaser),true,this);Query.bReturnPhysicalMaterial=true;
    FHitResult Hit;const FVector End=Origin+Direction*WeaponRange;
    GetWorld()->LineTraceSingleByChannel(Hit,Origin,End,Lyra_TraceChannel_Weapon,Query);
    Hit.TraceStart=Origin;Hit.TraceEnd=End;
    // A civilian/ally crossing into the actual spread ray cancels the shot.
    if (auto* Pawn=Cast<APawn>(Hit.GetActor());Pawn && Pawn!=BurstTarget.Get()) { StopMountedBurst();return; }
    if (auto* TargetASC=UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(Hit.GetActor()))
    {
        auto* Teams=GetWorld()->GetSubsystem<ULyraTeamSubsystem>();
        if (Teams && Teams->CanCauseDamage(this,Hit.GetActor()))
        {
            auto Context=ASC->MakeEffectContext();Context.AddInstigator(this,this);Context.AddHitResult(Hit);Context.AddOrigin(Origin);
            auto Spec=ASC->MakeOutgoingSpec(DamageEffect,1.f,Context);
            if (Spec.IsValid())
            {
                Spec.Data->SetSetByCallerMagnitude(FGameplayTag::RequestGameplayTag(TEXT("SetByCaller.Damage")),LaserDamage);
                ASC->ApplyGameplayEffectSpecToTarget(*Spec.Data.Get(),TargetASC);
            }
        }
    }
    LastMuzzlePosition=Origin;++MountedShots;--BurstRemaining;NextMountedShot=GetWorld()->GetTimeSeconds()+.18;
    WeaponEffects->SubmitMountedShot(LaserEffects,FTransform(Direction.Rotation(),Origin),Hit);
    ForceNetUpdate();
}

void ACRRobotCharacter::OnDeathStarted(AActor* OwningActor)
{
    ALyraCharacter::OnDeathStarted(OwningActor);
    StopMountedBurst();bShutdown=true;CrowdAgent->bProvoked=false;CrowdAgent->State=ECRCrowdState::Dead;
    if (auto* ASC=GetLyraAbilitySystemComponent()) ASC->ClearAbilityInput();
    ForceNetUpdate();
}

void ACRRobotCharacter::OnDeathFinished(AActor*)
{
    if (HasAuthority()) GetWorld()->GetTimerManager().SetTimer(ShutdownTimer,this,&ThisClass::RespawnRobot,5.f,false);
}

void ACRRobotCharacter::RespawnRobot()
{
    auto* ShutdownController=GetController();auto* Home=CrowdAgent->HomeArea.Get();
    FActorSpawnParameters Params;Params.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;
    if (auto* Replacement=GetWorld()->SpawnActor<ACRRobotCharacter>(GetClass(),InitialSpawnTransform,Params)) Replacement->CrowdAgent->HomeArea=Home;
    DestroyDueToDeath();
    if (ShutdownController) ShutdownController->Destroy();
}

// No UObject access from the animation worker thread. Every evaluated transform
// has unit scale and each imported rigid module retains its one bone binding.
struct FCRRobotAnimProxy : FAnimInstanceProxy
{
    explicit FCRRobotAnimProxy(UAnimInstance* Instance) : FAnimInstanceProxy(Instance) {}
    TArray<FTransform> Pose;
    virtual void PreUpdate(UAnimInstance* Instance,float DeltaSeconds) override
    {
        FAnimInstanceProxy::PreUpdate(Instance,DeltaSeconds);
        auto* Anim=CastChecked<UCRRobotAnimInstance>(Instance);
        Anim->UpdateRobotPose(DeltaSeconds);Pose=Anim->GetMechanicalPose();
    }
    virtual bool Evaluate(FPoseContext& Output) override
    {
        Output.ResetToRefPose();
        const auto& Container=Output.Pose.GetBoneContainer();
        for (const FCompactPoseBoneIndex Index : Output.Pose.ForEachBoneIndex())
        {
            const int32 MeshIndex=Container.MakeMeshPoseIndex(Index).GetInt();
            if (Pose.IsValidIndex(MeshIndex)) Output.Pose[Index]=Pose[MeshIndex];
        }
        return true;
    }
};

FAnimInstanceProxy* UCRRobotAnimInstance::CreateAnimInstanceProxy() { return new FCRRobotAnimProxy(this); }
void UCRRobotAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) { delete Proxy; }

bool UCRRobotAnimInstance::CacheRig(USkeletalMeshComponent* Mesh)
{
    if (!Mesh || !Mesh->GetSkeletalMeshAsset()) return false;
    if (CachedMesh==Mesh->GetSkeletalMeshAsset()) return Chassis!=INDEX_NONE;
    CachedMesh=Mesh->GetSkeletalMeshAsset();const auto& Ref=CachedMesh->GetRefSkeleton();
    ReferenceLocal=Ref.GetRefBonePose();Parents.Reset();
    for (int32 Index=0;Index<Ref.GetNum();++Index) Parents.Add(Ref.GetParentIndex(Index));
    LocalPose=ReferenceLocal;BuildComponentPose();ReferenceComponent=ComponentPose;
    Chassis=Ref.FindBoneIndex(TEXT("chassis"));
    for (int32 Side=0;Side<2;++Side)
    {
        const FString Suffix=Side==0 ? TEXT("_l") : TEXT("_r");Legs[Side]=FLeg();
        const TCHAR* Names[]={TEXT("upper_leg"),TEXT("middle_leg"),TEXT("lower_leg"),TEXT("foot")};
        for (int32 Joint=0;Joint<4;++Joint)
        {
            Legs[Side].Bones[Joint]=Ref.FindBoneIndex(FName(FString(Names[Joint])+Suffix));
            if (Legs[Side].Bones[Joint]==INDEX_NONE) { Chassis=INDEX_NONE;return false; }
        }
        Pistons[Side][0]=Ref.FindBoneIndex(FName(TEXT("piston_housing")+Suffix));
        Pistons[Side][1]=Ref.FindBoneIndex(FName(TEXT("piston_rod")+Suffix));
    }
    bFeetInitialized=false;return Chassis!=INDEX_NONE;
}

void UCRRobotAnimInstance::BuildComponentPose()
{
    ComponentPose.SetNum(LocalPose.Num());
    for (int32 Index=0;Index<LocalPose.Num();++Index)
        ComponentPose[Index]=Parents[Index]==INDEX_NONE ? LocalPose[Index] : LocalPose[Index]*ComponentPose[Parents[Index]];
}

FVector UCRRobotAnimInstance::GroundTarget(ACRRobotCharacter* Robot,const FVector& Nominal,float AnkleHeight) const
{
    FCollisionQueryParams Query(SCENE_QUERY_STAT(RobotFootPlacement),false,Robot);
    FCollisionObjectQueryParams Objects;Objects.AddObjectTypesToQuery(ECC_WorldStatic);
    FHitResult Hit;
    if (Robot->GetWorld()->LineTraceSingleByObjectType(Hit,Nominal+FVector(0,0,65),Nominal-FVector(0,0,125),Objects,Query) && Hit.ImpactNormal.Z>.55f)
        return FVector(Nominal.X,Nominal.Y,Hit.ImpactPoint.Z+AnkleHeight);
    return Nominal;
}

void UCRRobotAnimInstance::SolveLeg(FLeg& Leg,const FVector& Target)
{
    const float Limits[3]={30.f,35.f,35.f};
    auto Apply=[&](int32 Joint)
    {
        const int32 Bone=Leg.Bones[Joint];
        LocalPose[Bone].SetRotation((ReferenceLocal[Bone].GetRotation()*FQuat(FVector::ForwardVector,Leg.Angles[Joint])).GetNormalized());
    };
    for (int32 Joint=0;Joint<3;++Joint) Apply(Joint);
    BuildComponentPose();
    for (int32 Iteration=0;Iteration<14;++Iteration)
    {
        if (FVector::DistSquared(ComponentPose[Leg.Bones[3]].GetLocation(),Target)<.0025f) break;
        for (int32 Joint=2;Joint>=0;--Joint)
        {
            const FVector Origin=ComponentPose[Leg.Bones[Joint]].GetLocation();
            FVector A=ComponentPose[Leg.Bones[3]].GetLocation()-Origin;FVector B=Target-Origin;
            A.X=B.X=0;A.Normalize();B.Normalize();
            const float Delta=FMath::Atan2(FVector::CrossProduct(A,B).X,FVector::DotProduct(A,B));
            Leg.Angles[Joint]=FMath::Clamp(Leg.Angles[Joint]+Delta,-FMath::DegreesToRadians(Limits[Joint]),FMath::DegreesToRadians(Limits[Joint]));
            Apply(Joint);BuildComponentPose();
        }
    }
    const int32 Foot=Leg.Bones[3];
    LocalPose[Foot].SetRotation((ComponentPose[Parents[Foot]].GetRotation().Inverse()*ReferenceComponent[Foot].GetRotation()).GetNormalized());
    BuildComponentPose();
    MaximumFootError=FMath::Max(MaximumFootError,float(FVector::Dist(ComponentPose[Foot].GetLocation(),Target)));
}

void UCRRobotAnimInstance::UpdateRobotPose(float DeltaSeconds)
{
    auto* Robot=Cast<ACRRobotCharacter>(TryGetPawnOwner());auto* Mesh=GetSkelMeshComponent();
    if (!Robot || !CacheRig(Mesh)) return;
    const float Dt=FMath::Clamp(DeltaSeconds,0.f,.06f);
    GroundSpeed=Robot->GetVelocity().Size2D();MaximumFootError=0.f;
    const float TurnDistance=bFeetInitialized ? FMath::Abs(FMath::FindDeltaAngleDegrees(PreviousYaw,Robot->GetActorRotation().Yaw))*.55f : 0.f;
    const float TurnSpeed=TurnDistance/FMath::Max(DeltaSeconds,.001f);
    const float TravelDistance=bFeetInitialized ? FVector::Dist2D(PreviousLocation,Mesh->GetComponentLocation()) : 0.f;
    PreviousYaw=Robot->GetActorRotation().Yaw;
    const float PoseSpeed=FMath::Max(GroundSpeed,FMath::Min(TurnSpeed,180.f));
    const bool bGrounded=Robot->GetCharacterMovement()->IsMovingOnGround() || Robot->bShutdown;
    const bool bMoving=PoseSpeed>5.f && !Robot->bShutdown && bGrounded;
    // Short-legged chassis need shorter, quicker steps. A shared stride length
    // otherwise asks their rigid links to reach past their mechanical limits.
    float LegLength=0.f;
    for (int32 Joint=1;Joint<4;++Joint) LegLength+=ReferenceLocal[Legs[0].Bones[Joint]].GetTranslation().Size();
    const float Stride=FMath::Lerp(48.f,68.f,FMath::Clamp(PoseSpeed/320.f,0.f,1.f))*FMath::Clamp(LegLength/144.f,.6f,1.1f);
    // Drive steps by actual travel, including network smoothing. Clamping the
    // animation delta while movement advances through a slow frame leaves a
    // planted foot metres behind. Recover contacts after large discontinuities.
    if (bMoving) GaitPhase=FMath::Fmod(GaitPhase+FMath::Min(FMath::Max(TravelDistance,TurnDistance)/(Stride*2.f),.49f),1.f);
    ShutdownBlend=FMath::FInterpConstantTo(ShutdownBlend,Robot->bShutdown ? 1.f : 0.f,Dt,.65f);
    if (Robot->MountedShots!=PreviousShots) { PreviousShots=Robot->MountedShots;Recoil=1.f; }
    Recoil=FMath::FInterpTo(Recoil,0.f,Dt,13.f);
    LocalPose=ReferenceLocal;
    // Small load transfer, with a rigid crouched shutdown instead of human flailing.
    FVector ChassisOffset=ReferenceLocal[Chassis].GetTranslation();
    const FVector ComponentOffset(0,-Recoil*1.5f,-ShutdownBlend*27.f-(bMoving ? 1.2f*(1.f-FMath::Cos(GaitPhase*4.f*PI)) : 0.f));
    ChassisOffset+=ReferenceComponent[Parents[Chassis]].InverseTransformVectorNoScale(ComponentOffset);
    LocalPose[Chassis].SetTranslation(ChassisOffset);
    float DesiredPitch=Robot->bShutdown ? -.20f : 0.f;
    if (!Robot->bShutdown && Robot->CrowdAgent->bProvoked && IsValid(Robot->CrowdAgent->Threat))
    {
        const FVector Aim=Robot->CrowdAgent->Threat->GetActorLocation()+FVector(0,0,15)-Robot->GetMountedMuzzle();
        DesiredPitch=FMath::Clamp(float(FMath::Atan2(Aim.Z,Aim.Size2D())),-.26f,.35f);
    }
    ChassisPitch=FMath::FInterpTo(ChassisPitch,DesiredPitch,Dt,5.f);
    LocalPose[Chassis].SetRotation((ReferenceComponent[Parents[Chassis]].GetRotation().Inverse()
        *FQuat(FVector::ForwardVector,ChassisPitch)*ReferenceComponent[Chassis].GetRotation()).GetNormalized());
    BuildComponentPose();
    const FTransform World=Mesh->GetComponentTransform();
    const bool bReset=!bFeetInitialized || (bGrounded && !bWasGrounded) || TravelDistance>Stride*.7f;
    PreviousLocation=Mesh->GetComponentLocation();bWasGrounded=bGrounded;
    for (int32 Side=0;Side<2;++Side)
    {
        FLeg& Leg=Legs[Side];const int32 Foot=Leg.Bones[3];
        const FVector Rest=ReferenceComponent[Foot].GetLocation();
        const FVector Nominal=World.TransformPosition(Rest);
        const FVector Ground=GroundTarget(Robot,Nominal,Rest.Z);
        if (bReset) { Leg.Planted=Ground;Leg.bSwinging=false; }
        const float Phase=FMath::Fmod(GaitPhase+Side*.5f,1.f);
        FVector Goal=Leg.Planted;
        if (!bGrounded)
        {
            Goal=Nominal+FVector(0,0,12);Leg.Planted=Ground;Leg.bSwinging=false;
        }
        else if (!bMoving)
        {
            Leg.Planted=FMath::VInterpTo(Leg.Planted,Ground,Dt,9.f);Goal=Leg.Planted;Leg.bSwinging=false;
        }
        else if (Phase>=.60f)
        {
            if (!Leg.bSwinging)
            {
                Leg.SwingStart=Leg.Planted;
                // Account for the body's travel during swing, then land ahead
                // by half the stance distance. This keeps planted feet in reach.
                Leg.SwingEnd=GroundTarget(Robot,Nominal+Robot->GetVelocity().GetSafeNormal2D()*Stride*1.4f,Rest.Z);
                Leg.bSwinging=true;
            }
            const float Alpha=(Phase-.60f)/.40f;
            // Navigation can turn during a step. Revise the landing point for
            // remaining travel instead of leaving a foot beyond the old corner.
            const FVector Landing=GroundTarget(Robot,Nominal+Robot->GetVelocity().GetSafeNormal2D()*Stride*(1.4f-.8f*Alpha),Rest.Z);
            Leg.SwingEnd=FMath::VInterpTo(Leg.SwingEnd,Landing,Dt,12.f);
            Goal=FMath::Lerp(Leg.SwingStart,Leg.SwingEnd,Alpha*Alpha*(3.f-2.f*Alpha))+FVector(0,0,FMath::Sin(Alpha*PI)*12.f);
        }
        else if (Leg.bSwinging)
        {
            Leg.Planted=Leg.SwingEnd;Goal=Leg.Planted;Leg.bSwinging=false;++FootPlants;
            UCRFootstepComponent::HandleFoleyEvent(Robot->Footsteps,FGameplayTag::RequestGameplayTag(TEXT("Foley.Event.Walk")),Side+1,1.f,.8f);
        }
        FVector Target=World.InverseTransformPosition(Goal);
        // Keep the articulated metal hinges planar; turn the pawn to change gait
        // direction instead of adding lateral skin deformation at the hip.
        Target.X=Rest.X;
        SolveLeg(Leg,Target);
    }
    bFeetInitialized=true;
    for (int32 Side=0;Side<2;++Side)
    {
        const int32 Housing=Pistons[Side][0],Rod=Pistons[Side][1];
        if (Housing==INDEX_NONE || Rod==INDEX_NONE) continue;
        const FVector Direction=(ComponentPose[Rod].GetLocation()-ComponentPose[Housing].GetLocation()).GetSafeNormal();
        const FVector RestDirection=(ReferenceComponent[Rod].GetLocation()-ReferenceComponent[Housing].GetLocation()).GetSafeNormal();
        const FQuat Aim=FQuat::FindBetweenNormals(RestDirection,Direction);
        for (const int32 Bone : {Housing,Rod})
        {
            const FQuat Rotation=Aim*ReferenceComponent[Bone].GetRotation();
            LocalPose[Bone].SetRotation((ComponentPose[Parents[Bone]].GetRotation().Inverse()*Rotation).GetNormalized());
        }
    }
    for (FTransform& Pose : LocalPose) Pose.SetScale3D(FVector::OneVector);
}
