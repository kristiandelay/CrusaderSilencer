#include "CRDestructibleActor.h"
#include "GeometryCollection/GeometryCollectionComponent.h"
#include "Field/FieldSystemObjects.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Net/UnrealNetwork.h"
#include "UObject/StructOnScope.h"
#include "UObject/UnrealType.h"
#include "AI/Navigation/NavigationRelevantData.h"
#include "NavAreas/NavArea_Null.h"

UCRDestructibleNavigation::UCRDestructibleNavigation(const FObjectInitializer& Initializer)
    : Super(Initializer)
{
    bAttachToOwnersRoot = false;
    SetCanEverAffectNavigation(false);
}

void UCRDestructibleNavigation::CalcAndCacheBounds() const
{
    Bounds = FBox(ForceInit);
    if (const auto* Owner = Cast<ACRDestructibleActor>(GetOwner()))
        if (const auto* Geometry = Owner->GetDestructibleGeometry())
            Bounds = Geometry->CalcBounds(Geometry->GetComponentTransform()).GetBox();
    bBoundsInitialized = true;
}

void UCRDestructibleNavigation::GetNavigationData(FNavigationRelevantData& Data) const
{
    if (!CanEverAffectNavigation() || !Bounds.IsValid) return;
    FAreaNavModifier Modifier(Bounds, FTransform::Identity, UNavArea_Null::StaticClass());
    Modifier.SetIncludeAgentHeight(true);
    Data.Modifiers.Add(Modifier);
}

ACRDestructibleActor::ACRDestructibleActor()
{
    bReplicates = true;
    SetNetUpdateFrequency(20.f);
    PrimaryActorTick.bCanEverTick = false;
    IntactNavigation = CreateDefaultSubobject<UCRDestructibleNavigation>(TEXT("IntactFootprint"));
}

UGeometryCollectionComponent* ACRDestructibleActor::GetDestructibleGeometry() const
{
    return FindComponentByClass<UGeometryCollectionComponent>();
}

void ACRDestructibleActor::ConfigureGeometry()
{
    // Recover serialized instances authored before the dedicated footprint
    // component replaced the generic navigation modifier.
    if (!IntactNavigation) IntactNavigation = FindComponentByClass<UCRDestructibleNavigation>();
    if (auto* Geometry = GetDestructibleGeometry())
    {
        Geometry->SetIsReplicated(true);
        Geometry->SetCanEverAffectNavigation(false);
        Geometry->SetEnableReplication(true);
        Geometry->SetReplicationAbandonAfterLevel(100);
        Geometry->SetCollisionProfileName(TEXT("CRDestructible"));
        Geometry->SetNotifyBreaks(true);
        Geometry->SetNotifyGlobalBreaks(true);
        Geometry->SetNotifyGlobalCollision(true);
        Geometry->SetNotifyGlobalTrailings(true);
        // Small fragments should not throw characters around or pull the camera in.
        Geometry->SetAbandonedParticleCollisionProfileName(TEXT("IgnoreCharChaos"));
    }
    if (IntactNavigation)
    {
        IntactNavigation->CalcAndCacheBounds();
        IntactNavigation->SetCanEverAffectNavigation(bBlockNavigationUntilBroken && BreakEffects.Revision == 0);
        IntactNavigation->SetNavigationRelevancy(bBlockNavigationUntilBroken && BreakEffects.Revision == 0);
        IntactNavigation->RefreshNavigationModifiers();
    }
}

void ACRDestructibleActor::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    ConfigureGeometry();
}

void ACRDestructibleActor::BeginPlay()
{
    Super::BeginPlay();
    ConfigureGeometry();
    if (auto* Geometry = GetDestructibleGeometry())
        Geometry->OnChaosBreakEvent.AddDynamic(this, &ThisClass::OnGeometryBroken);
}

void ACRDestructibleActor::OnGeometryBroken(const FChaosBreakEvent& Event)
{
    if (bRelayingBreakEffects) return;
    ++LocalBreakEvents;
    if (HasAuthority() && IntactNavigation && BreakEffects.Revision == 0)
    {
        // Remove the octree entry as well as its relevancy flag. Keeping the
        // registered modifier can leave its cached NavArea_Null footprint.
        IntactNavigation->SetNavigationRelevancy(false);
        IntactNavigation->DestroyComponent();
        IntactNavigation = nullptr;
    }
    // Chaos replicates particle state without replaying the server's break
    // delegate on clients. Send a bounded cosmetic sample, retaining the first
    // broken-material transition for actors that become relevant later.
    if (HasAuthority() && GetWorld()->GetTimeSeconds() >= NextBreakEffectsTime)
    {
        BreakEffects.Location = Event.Location;
        BreakEffects.Velocity = Event.Velocity;
        BreakEffects.PieceIndex = Event.Index;
        ++BreakEffects.Revision;
        NextBreakEffectsTime = GetWorld()->GetTimeSeconds() + .15;
        ForceNetUpdate();
    }
}

void ACRDestructibleActor::OnRep_BreakEffects()
{
    auto* Geometry = GetDestructibleGeometry();
    if (!Geometry || BreakEffects.Revision == 0) return;
    if (IntactNavigation)
    {
        IntactNavigation->SetNavigationRelevancy(false);
        IntactNavigation->DestroyComponent();
        IntactNavigation = nullptr;
    }
    FChaosBreakEvent Event;
    Event.Component = Geometry;
    Event.Location = BreakEffects.Location;
    Event.Velocity = BreakEffects.Velocity;
    Event.Index = BreakEffects.PieceIndex;
    Event.Mass = 1.f;
    ++ReceivedBreakEffects;
    TGuardValue<bool> RelayGuard(bRelayingBreakEffects, true);
    // Reuse the toolkit's glass material switch, sound throttling and Niagara
    // effects. This does not apply strain or fracture the client a second time.
    Geometry->OnChaosBreakEvent.Broadcast(Event);
}

bool ACRDestructibleActor::ApplyWeaponHit(const FHitResult& Hit)
{
    auto* Target = Cast<ACRDestructibleActor>(Hit.GetActor());
    if (!Target || !Target->HasAuthority() || !Hit.bBlockingHit
        || Hit.GetComponent() != Target->GetDestructibleGeometry()) return false;

    // The toolkit's Blueprint interface owns material-specific radius, torque,
    // strain and directional impulse. Marshal its reflected signature rather
    // than duplicating that logic or assuming a Blueprint parameter layout.
    UFunction* Impact = Target->FindFunction(TEXT("BulletImpact"));
    FStructProperty* HitParameter = Impact ? FindFProperty<FStructProperty>(Impact, TEXT("HitInfo")) : nullptr;
    if (!HitParameter || HitParameter->Struct != FHitResult::StaticStruct()) return false;
    FStructOnScope Parameters(Impact);
    *HitParameter->ContainerPtrToValuePtr<FHitResult>(Parameters.GetStructMemory()) = Hit;
    Target->ProcessEvent(Impact, Parameters.GetStructMemory());
    if (Target->WeaponContactStrain > 0.f && Hit.Item != INDEX_NONE)
    {
        // Table tops and edges can lie outside the kit's small radial field.
        // Address the contacted cluster itself; this cannot damage a neighbor.
        Target->GetDestructibleGeometry()->ApplyExternalStrain(Hit.Item, Hit.ImpactPoint,
            0.f, 2, 1.f, Target->WeaponContactStrain);
    }
    ++Target->WeaponHits;
    Target->ForceNetUpdate();
    return true;
}

void ACRDestructibleActor::ApplyExplosion(UWorld* World, const FVector& Origin, float Radius, AActor* Causer)
{
    if (!World || World->GetNetMode() == NM_Client || Radius <= 0.f) return;
    for (TActorIterator<ACRDestructibleActor> It(World); It; ++It)
    {
        auto* Geometry = It->GetDestructibleGeometry();
        if (!Geometry) continue;
        const FBox Bounds = Geometry->Bounds.GetBox();
        const FVector Nearest = Bounds.GetClosestPointTo(Origin);
        if (FVector::DistSquared(Nearest, Origin) > FMath::Square(Radius)) continue;

        // Cover blocks blast damage. Ignore the recipient so the near face of
        // a thick wall does not shield itself from a nearby explosion.
        FCollisionQueryParams Query(SCENE_QUERY_STAT(DestructionBlastCover), false, Causer);
        Query.AddIgnoredActor(*It);
        FHitResult Cover;
        if (World->LineTraceSingleByChannel(Cover, Origin, Nearest, ECC_Visibility, Query)) continue;

        auto* Strain = NewObject<URadialFalloff>(Geometry);
        Strain->SetRadialFalloff(2000000.f, 1.f, 1.f, 0.f, Radius, Origin, EFieldFalloffType::Field_FallOff_None);
        Geometry->ApplyPhysicsField(true, EGeometryCollectionPhysicsTypeEnum::Chaos_ExternalClusterStrain, nullptr, Strain);
        auto* Velocity = NewObject<URadialVector>(Geometry);
        Velocity->SetRadialVector(800.f, Origin);
        // Scope the field to this collection, preserving nearby character,
        // ragdoll and projectile movement.
        Geometry->ApplyPhysicsField(true, EGeometryCollectionPhysicsTypeEnum::Chaos_LinearVelocity, nullptr, Velocity);
        ++It->ExplosionHits;
        It->ForceNetUpdate();
    }
}

void ACRDestructibleActor::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ThisClass, WeaponHits);
    DOREPLIFETIME(ThisClass, ExplosionHits);
    DOREPLIFETIME(ThisClass, BreakEffects);
}
