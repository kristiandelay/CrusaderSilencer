#include "CRFootsteps.h"
#include "CRTraversalCharacter.h"
#include "Baseline/BaselineCharacterMovement.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Kismet/GameplayStatics.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "Sound/SoundBase.h"
#include "Perception/AISense_Hearing.h"

const TArray<TObjectPtr<USoundBase>>& FCRFootstepSurface::GetSounds(ECRFootstepGait Gait) const
{
    switch (Gait)
    {
    case ECRFootstepGait::Sneak: return Sneak;
    case ECRFootstepGait::Run: return Run;
    case ECRFootstepGait::Sprint: return Sprint;
    case ECRFootstepGait::Jump: return Jump;
    case ECRFootstepGait::Land: return Land;
    default: return Walk;
    }
}

const FCRFootstepSurface* UCRFootstepProfile::FindSurface(EPhysicalSurface Surface) const
{
    const auto* Match = Surfaces.FindByPredicate([Surface](const auto& Row){return Row.Surface == Surface;});
    return Match ? Match : Surfaces.FindByPredicate([](const auto& Row){return Row.Surface == SurfaceType_Default;});
}

UCRFootstepComponent::UCRFootstepComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
}

void UCRFootstepComponent::GroundContact()
{
    // Motion matching can choose a landing without a Foley notify. The movement
    // transition is available on authority and simulated proxies; debounce with
    // animation contacts so each rendered pawn still plays exactly one landing.
    if (Profile) PlayContact(TEXT("Foley.Event.Land"), 0, 1.f, 1.f);
}

bool UCRFootstepComponent::HandleFoleyEvent(UActorComponent* Source, FGameplayTag Event, uint8 Side, float Volume, float Pitch)
{
    auto* Component = Source && Source->GetOwner() ? Source->GetOwner()->FindComponentByClass<UCRFootstepComponent>() : nullptr;
    if (!Component || !Component->Profile) return false;
    const FName Name = Event.GetTagName();
    if (Name != TEXT("Foley.Event.Walk") && Name != TEXT("Foley.Event.Run") && Name != TEXT("Foley.Event.Jump")
        && Name != TEXT("Foley.Event.Land") && Name != TEXT("Foley.Event.Tumble") && Name != TEXT("Foley.Event.Scuff")) return false;
    // Scuffs retain their timing but must not add a second heel strike.
    if (Name != TEXT("Foley.Event.Scuff")) Component->PlayContact(Name, Side, Volume, Pitch);
    return true;
}

void UCRFootstepComponent::PlayContact(FName Event, uint8 Side, float Volume, float Pitch)
{
    auto* Character = Cast<ACRTraversalCharacter>(GetOwner());
    if (!Character || !GetWorld() || !Character->CanUseMovementActions()) return;
    auto* Movement = Cast<UBaselineCharacterMovement>(Character->GetCharacterMovement());
    if (!Movement || Movement->IsSliding()) return;
    const bool bJump = Event == TEXT("Foley.Event.Jump");
    const bool bLand = Event == TEXT("Foley.Event.Land") || Event == TEXT("Foley.Event.Tumble");
    if (!bJump && !Movement->IsMovingOnGround()) return;
    const double Now = GetWorld()->GetTimeSeconds();
    // The supplied E_FoleyEventSide has None=0, Left=1, Right=2.
    const uint8 FootIndex = FMath::Min<uint8>(Side, 2);
    if ((bJump && Now-LastJumpTime < .25) || (bLand && Now-LastLandTime < .25)
        || (!bJump && !bLand && (Now-LastContactTimes[FootIndex] < .14 || Now-LastLandTime < .14))) return;
    const FName Foot = FootIndex == 1 ? FName(TEXT("foot_l")) : FootIndex == 2 ? FName(TEXT("foot_r")) : FName(NAME_None);
    FVector Position = Character->GetActorLocation() - FVector(0,0,Character->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
    if (!Foot.IsNone() && Character->GetMesh()->DoesSocketExist(Foot)) Position = Character->GetMesh()->GetSocketLocation(Foot);
    FCollisionQueryParams Query(SCENE_QUERY_STAT(CrusaderFootstep), false, Character);
    Query.bReturnPhysicalMaterial = true;
    TArray<AActor*> Attached;
    Character->GetAttachedActors(Attached, true, true);
    Query.AddIgnoredActors(Attached);
    FHitResult Hit;
    if (!GetWorld()->LineTraceSingleByChannel(Hit, Position+FVector(0,0,30), Position-FVector(0,0,bJump ? 100 : 65), ECC_Visibility, Query)) return;
    if (Hit.ImpactNormal.Z < .4f) return;
    const auto Surface = UPhysicalMaterial::DetermineSurfaceType(Hit.PhysMaterial.Get());
    const auto* Row = Profile->FindSurface(Surface);
    if (!Row) return;
    const float Speed = Character->GetVelocity().Size2D();
    ECRFootstepGait Gait = bJump ? ECRFootstepGait::Jump : bLand ? ECRFootstepGait::Land
        : Character->bIsCrouched ? ECRFootstepGait::Sneak : Speed >= Profile->SprintSpeed ? ECRFootstepGait::Sprint
        : Speed >= Profile->RunSpeed ? ECRFootstepGait::Run : ECRFootstepGait::Walk;
    const auto& Sounds = Row->GetSounds(Gait).IsEmpty() ? Row->Walk : Row->GetSounds(Gait);
    if (Sounds.IsEmpty()) return;
    const int32 Key = int32(Surface)*8+int32(Gait);
    int32 Index = FMath::RandRange(0, Sounds.Num()-1);
    if (const int32* Previous = LastVariants.Find(Key); Previous && Index == *Previous && Sounds.Num()>1)
        Index = (Index+FMath::RandRange(1,Sounds.Num()-1))%Sounds.Num();
    USoundBase* Sound = Sounds[Index];
    if (!Sound) return;
    LastVariants.Add(Key, Index);
    const float Gain = FMath::Clamp(Volume, .15f, 1.5f)*(Gait == ECRFootstepGait::Sneak ? .55f : .85f);
    if (Character->HasAuthority())
        UAISense_Hearing::ReportNoiseEvent(Character,Hit.ImpactPoint,Gain,Character,
            Gait == ECRFootstepGait::Sneak ? 250.f : Gait == ECRFootstepGait::Sprint ? 1500.f : 850.f,TEXT("Footstep"));
    if (GetNetMode() != NM_DedicatedServer)
        UGameplayStatics::PlaySoundAtLocation(this, Sound, Hit.ImpactPoint, FRotator::ZeroRotator, Gain,
            FMath::Clamp(Pitch, .75f, 1.25f)*FMath::FRandRange(.96f,1.04f), 0.f, Profile->Attenuation, Profile->Concurrency, Character);
    ++SoundsPlayed;
    if (bJump) { ++JumpsPlayed; LastJumpTime=Now; }
    else if (bLand) { ++LandingsPlayed; LastLandTime=Now; }
    else { ++StepsPlayed; LastContactTimes[FootIndex]=Now; }
    LastSurface=Surface; LastGait=Gait; LastFoot=Foot; LastPosition=Hit.ImpactPoint; LastSound=Sound;
}
