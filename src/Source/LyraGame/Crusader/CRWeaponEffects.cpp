#include "CRWeaponEffects.h"
#include "CRCrowdAI.h"
#include "Baseline/BaselineEquipment.h"
#include "Equipment/LyraEquipmentManagerComponent.h"
#include "Abilities/GameplayAbilityTargetTypes.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/DecalComponent.h"
#include "Components/PrimitiveComponent.h"
#include "GameFramework/Pawn.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraComponent.h"
#include "Kismet/GameplayStatics.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "Sound/SoundAttenuation.h"
#include "TimerManager.h"

const FCRSurfaceImpact* UCRWeaponEffectsProfile::FindSurface(EPhysicalSurface Surface) const
{
    const auto* Match = Surfaces.FindByPredicate([Surface](const auto& Entry){ return Entry.Surface == Surface; });
    return Match ? Match : Surfaces.FindByPredicate([](const auto& Entry){ return Entry.Surface == SurfaceType_Default; });
}

UCRWeaponEffectsComponent::UCRWeaponEffectsComponent()
{
    SetIsReplicatedByDefault(true);
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.bStartWithTickEnabled = false;
    PrimaryComponentTick.TickGroup = TG_PrePhysics;
}

void UCRWeaponEffectsComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
    for (int32 Index = MovingTrails.Num() - 1; Index >= 0; --Index)
    {
        auto& Flight = MovingTrails[Index];
        auto* Trail = Flight.Component.Get();
        if (!Trail) { MovingTrails.RemoveAtSwap(Index); continue; }
        if (!Flight.bArrived)
        {
            Flight.Elapsed += DeltaTime;
            const float Alpha = FMath::Clamp(Flight.Elapsed / Flight.Duration, 0.f, 1.f);
            Trail->SetWorldLocation(FMath::Lerp(Flight.Start, Flight.End, Alpha));
            Flight.bArrived = Alpha >= 1.f;
        }
        else
        {
            // Niagara ticks after this component. Give it the arrival frame to
            // finish the ribbon at the wall before stopping particle emission.
            if (!Flight.bDeactivated) { Trail->Deactivate(); Flight.bDeactivated = true; }
            Flight.FadeRemaining -= DeltaTime;
            if (Flight.FadeRemaining <= 0.f)
            {
                Trail->DestroyComponent();
                MovingTrails.RemoveAtSwap(Index);
            }
        }
    }
    if (MovingTrails.IsEmpty()) SetComponentTickEnabled(false);
}

void UCRWeaponEffectsComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    for (const auto& Flight : MovingTrails) if (Flight.Component.IsValid()) Flight.Component->DestroyComponent();
    MovingTrails.Empty();
    Super::EndPlay(EndPlayReason);
}

int32 UCRWeaponEffectsComponent::GetActiveTrailCount() const
{
    int32 Count = 0;
    for (const auto& Flight : MovingTrails) if (Flight.Component.IsValid()) ++Count;
    return Count;
}

int32 UCRWeaponEffectsComponent::GetActiveBulletHoleCount() const
{
    int32 Count = 0;
    for (const auto& Decal : Decals) if (Decal.IsValid()) ++Count;
    return Count;
}

bool UCRWeaponEffectsComponent::UsesCustomWeaponEffects(AActor* WeaponActor)
{
    AActor* Pawn = WeaponActor ? WeaponActor->GetOwner() : nullptr;
    auto* Manager = Pawn ? Pawn->FindComponentByClass<ULyraEquipmentManagerComponent>() : nullptr;
    auto* Weapon = Manager ? Manager->GetFirstInstanceOfType<UBaselineWeaponInstance>() : nullptr;
    return Weapon && Weapon->EffectsProfile && Pawn->FindComponentByClass<UCRWeaponEffectsComponent>();
}

void UCRWeaponEffectsComponent::SubmitShot(UBaselineWeaponInstance* Weapon, const FGameplayAbilityTargetDataHandle& Data)
{
    if (!Weapon || !Weapon->EffectsProfile) return;
    USkeletalMeshComponent* Mesh = nullptr;
    for (AActor* Actor : Weapon->GetSpawnedActors())
        if (Actor) if (auto* Candidate = Actor->FindComponentByClass<USkeletalMeshComponent>()) { Mesh = Candidate; break; }
    if (!Mesh) return;
    const FTransform Muzzle = Mesh->GetSocketTransform(TEXT("Muzzle"));
    const FTransform Ejection = Mesh->GetSocketTransform(TEXT("ShellEject"));
    TArray<FCRShotImpact> Hits;
    for (int32 Index = 0; Index < FMath::Min(Data.Num(), 32); ++Index)
    {
        const auto* Target = Data.Get(Index);
        const FHitResult* Hit = Target ? Target->GetHitResult() : nullptr;
        if (!Hit) continue;
        FCRShotImpact& Impact = Hits.AddDefaulted_GetRef();
        Impact.bBlockingHit = Hit->bBlockingHit;
        Impact.Position = Hit->bBlockingHit ? Hit->ImpactPoint : Hit->TraceEnd;
        Impact.Normal = Hit->ImpactNormal.GetSafeNormal();
        Impact.Surface = UPhysicalMaterial::DetermineSurfaceType(Hit->PhysMaterial.Get());
    }
    if (GetOwner()->HasAuthority())
    {
        UCRCrowdAgentComponent::ReportGunshot(Cast<APawn>(GetOwner()), Muzzle.GetLocation(), Hits);
        MulticastShot(Weapon->EffectsProfile, Muzzle, Ejection, Hits);
    }
    else PlayShot(Weapon->EffectsProfile, Muzzle, Ejection, Hits);
}

void UCRWeaponEffectsComponent::MulticastShot_Implementation(UCRWeaponEffectsProfile* Profile, const FTransform& Muzzle, const FTransform& Ejection, const TArray<FCRShotImpact>& Hits)
{
    const APawn* Pawn = Cast<APawn>(GetOwner());
    if (GetNetMode() == NM_DedicatedServer || (GetNetMode() == NM_Client && Pawn && Pawn->IsLocallyControlled())) return;
    PlayShot(Profile, Muzzle, Ejection, Hits);
}

void UCRWeaponEffectsComponent::PlayShot(UCRWeaponEffectsProfile* Profile, const FTransform& Muzzle, const FTransform& Ejection, const TArray<FCRShotImpact>& Hits)
{
    if (!Profile || GetNetMode() == NM_DedicatedServer) return;
    ++ShotsPlayed; LastImpacts = Hits; LastProfile = Profile;
    auto Spawn = [this](UNiagaraSystem* System, const FVector& Location, const FRotator& Rotation, float Scale)
    {
        return System ? UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, System, Location, Rotation, FVector(Scale), true, true, ENCPoolMethod::AutoRelease) : nullptr;
    };
    Spawn(Profile->MuzzleFlash, Muzzle.GetLocation(), Muzzle.Rotator(), Profile->MuzzleScale);
    Spawn(Profile->ShellEjection, Ejection.GetLocation(), Ejection.Rotator(), 1.f);
    TArray<FVector> SoundPositions;
    for (const FCRShotImpact& Hit : Hits)
    {
        const FVector Travel = FVector(Hit.Position) - Muzzle.GetLocation();
        const float Distance = Travel.Size();
        // Both trail styles stop at the accepted trace endpoint. They are only
        // presentation; hit authority, damage and pellet spread remain in Lyra.
        if (Profile->BulletTrail && Distance > 30.f)
        {
            const float Speed = FMath::Max(Profile->TrailSpeed, 100.f);
            if (auto* Trail = UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, Profile->BulletTrail, Muzzle.GetLocation(), Travel.Rotation(), FVector::OneVector, false, false))
            {
                if (Profile->bMovementDrivenTrail)
                {
                    // Laser Trace 5 from Bullet Tracers & Trails uses Spawn Per
                    // Unit. Moving its source is essential; X_Velocity does not
                    // drive this emitter. Solo ticking honors our prerequisite.
                    Trail->SetForceSolo(true);
                    Trail->AddTickPrerequisiteComponent(this);
                    const float Lifetime = FMath::Clamp(Profile->TrailParticleLifetime, .01f, .25f);
                    Trail->SetVariableFloat(TEXT("User.Lifetime"), Lifetime);
                    Trail->SetVariableFloat(TEXT("User.Max Movement Threshold"), 250000.f);
                    Trail->Activate(true);
                    // Prime the source position before its first movement, so
                    // even short shots can draw a muzzle-to-endpoint ribbon.
                    Trail->AdvanceSimulation(1, .001f);
                    FMovingTrail& Flight = MovingTrails.AddDefaulted_GetRef();
                    Flight.Component = Trail;
                    Flight.Start = Muzzle.GetLocation();
                    Flight.End = Hit.Position;
                    Flight.Duration = FMath::Clamp(Distance / Speed, .001f, 2.f);
                    Flight.FadeRemaining = Lifetime + .05f;
                    SetComponentTickEnabled(true);
                }
                else
                {
                    Trail->SetVariableFloat(TEXT("User.X_Velocity"), Speed);
                    Trail->SetVariableFloat(TEXT("User.BulletSmoke_Wdith"), 1.2f);
                    Trail->SetVariableFloat(TEXT("User.BulletSmoke_Opacity"), .12f);
                    Trail->SetVariableVec2(TEXT("User.BulletScaleFactor"), FVector2D(.35f, .35f));
                    Trail->Activate(true);
                    FTimerHandle Timer;
                    TWeakObjectPtr<UNiagaraComponent> WeakTrail(Trail);
                    GetWorld()->GetTimerManager().SetTimer(Timer, [WeakTrail] { if (WeakTrail.IsValid()) WeakTrail->DestroyComponent(); }, FMath::Clamp(Distance / Speed, .001f, 2.f), false);
                }
                ++TrailsPlayed;
            }
        }
        if (!Hit.bBlockingHit || Hit.Normal.IsNearlyZero()) continue;
        const auto* Surface = Profile->FindSurface(static_cast<EPhysicalSurface>(Hit.Surface));
        if (!Surface) continue;
        ++ImpactsPlayed;
        const FVector Position = FVector(Hit.Position) + FVector(Hit.Normal) * .5f;
        // Impact emitters use +Z as their outward surface normal.
        Spawn(Surface->Effect, Position, FRotationMatrix::MakeFromZ(Hit.Normal).Rotator(), Surface->Scale);
        // A shotgun cluster needs one audible hit at a spot, not ten stacked cues.
        if (Surface->Sound && !SoundPositions.ContainsByPredicate([&](const FVector& Point){return FVector::DistSquared(Point, Position) < FMath::Square(60.f);}))
        {
            UGameplayStatics::PlaySoundAtLocation(this, Surface->Sound, Position, FRotator::ZeroRotator, .75f, FMath::FRandRange(.94f, 1.06f), 0.f, Profile->ImpactAttenuation, nullptr, GetOwner());
            SoundPositions.Add(Position);
        }
        UMaterialInterface* DecalMaterial = Surface->Decal;
        if (!Surface->DecalVariants.IsEmpty()) DecalMaterial = Surface->DecalVariants[FMath::RandRange(0, Surface->DecalVariants.Num()-1)];
        if (DecalMaterial)
        {
            // Resolve the receiving component in this world: a replicated shot
            // cannot safely serialize arbitrary, non-replicated prop components.
            // Attaching locally lets holes move with doors and physics props.
            FHitResult Receiver;
            FCollisionQueryParams Query(SCENE_QUERY_STAT(CrusaderBulletHole), true, GetOwner());
            if (!GetWorld()->LineTraceSingleByChannel(Receiver, FVector(Hit.Position)+FVector(Hit.Normal)*8.f,
                FVector(Hit.Position)-FVector(Hit.Normal)*8.f, ECC_Visibility, Query)
                || !Receiver.GetComponent() || !Receiver.GetComponent()->bReceivesDecals
                || Receiver.GetComponent()->IsA<USkeletalMeshComponent>()) continue;
            FRotator Rotation = (-FVector(Hit.Normal)).Rotation();
            Rotation.Roll = FMath::FRandRange(-180.f,180.f);
            const float Lifetime = FMath::Max(Profile->DecalLifetime, 1.f);
            const float Size = Profile->DecalSize*FMath::FRandRange(.85f,1.15f);
            if (auto* Decal = UGameplayStatics::SpawnDecalAttached(DecalMaterial, FVector(1.5f, Size, Size),
                Receiver.GetComponent(), NAME_None, Receiver.ImpactPoint+FVector(Hit.Normal)*.15f, Rotation,
                EAttachLocation::KeepWorldPosition, Lifetime))
            {
                const float FadeDuration = FMath::Min(20.f, Lifetime*.25f);
                Decal->SetFadeOut(Lifetime-FadeDuration, FadeDuration, false);
                Decal->SetFadeScreenSize(.0005f);
                Decals.RemoveAll([](const auto& Item){return !Item.IsValid();});
                while (Decals.Num() >= FMath::Max(Profile->MaxBulletHoles, 1)) { if (Decals[0].IsValid()) Decals[0]->DestroyComponent(); Decals.RemoveAt(0); }
                Decals.Add(Decal);
                LastDecal = Decal; ++DecalsSpawned;
            }
        }
    }
}
