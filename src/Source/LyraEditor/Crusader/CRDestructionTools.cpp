#include "CRDestructionTools.h"
#include "Engine/StaticMeshActor.h"
#include "Components/StaticMeshComponent.h"
#include "GeometryCollection/GeometryCollection.h"
#include "GeometryCollection/GeometryCollectionObject.h"
#include "GeometryCollection/GeometryCollectionEngineConversion.h"
#include "GeometryCollection/GeometryCollectionClusteringUtility.h"
#include "GeometryCollection/GeometryCollectionConvexUtility.h"
#include "GeometryCollection/GeometryCollectionComponent.h"
#include "ComponentReregisterContext.h"
#include "UObject/UObjectIterator.h"
#include "FractureEngineFracturing.h"

int32 UCRDestructionTools::GetRigidPieceCount(UGeometryCollection* Collection)
{
    if (!Collection || !Collection->GetGeometryCollection()) return 0;
    int32 Count = 0;
    for (int32 Type : Collection->GetGeometryCollection()->SimulationType)
        if (Type == FGeometryCollection::ESimulationTypes::FST_Rigid) ++Count;
    return Count;
}

int32 UCRDestructionTools::RebuildFurniturePhysics(UGeometryCollection* Target)
{
    if (!Target || !Target->GetGeometryCollection()) return 0;
    TArray<UActorComponent*> Users;
    for (TObjectIterator<UGeometryCollectionComponent> It; It; ++It)
        if (It->IsRegistered() && It->GetRestCollection() == Target) Users.Add(*It);
    FMultiComponentReregisterContext Reregister(Users);
    Target->Modify();
    // FractureEngine cuts visual geometry. Convexes/proximity/volume are a
    // separate authoring step; simulation data alone does not generate them.
    Target->UpdateGeometryDependentProperties();
    auto Hulls = FGeometryCollectionConvexUtility::GetValidConvexHullData(Target->GetGeometryCollection().Get());
    const int32 Count = Hulls.ConvexHull.Num();
    Target->InvalidateCollection();
    Target->CreateSimulationData();
    Target->PostEditChange();
    Target->MarkPackageDirty();
    return Count;
}

int32 UCRDestructionTools::BakeFurnitureScale(UGeometryCollection* Target, float Factor)
{
    if (!Target || !Target->GetGeometryCollection() || Factor <= 0.f) return 0;
    TArray<UActorComponent*> Users;
    for (TObjectIterator<UGeometryCollectionComponent> It; It; ++It)
        if (It->IsRegistered() && It->GetRestCollection() == Target) Users.Add(*It);
    FMultiComponentReregisterContext Reregister(Users);
    Target->Modify();
    auto Collection = Target->GetGeometryCollection();
    for (auto& Vertex : Collection->Vertex) Vertex *= Factor;
    for (auto& Transform : Collection->Transform)
        Transform.SetTranslation(Transform.GetTranslation() * Factor);
    for (auto& Box : Collection->BoundingBox)
    {
        Box.Min *= Factor;
        Box.Max *= Factor;
    }
    TArray<int32> AllBones;
    for (int32 Index = 0; Index < Collection->Transform.Num(); ++Index) AllBones.Add(Index);
    FGeometryCollectionConvexUtility::RemoveConvexHulls(Collection.Get(), AllBones);
    return RebuildFurniturePhysics(Target);
}

int32 UCRDestructionTools::BuildFurnitureCollection(UGeometryCollection* Target,
    const TArray<AStaticMeshActor*>& Sources, UMaterialInterface* Interior, int32 Cells, int32 Seed, float Mass)
{
    if (!Target || Sources.IsEmpty() || !Sources[0] || !Interior) return 0;
    // Refracturing changes the number of transforms. Detach existing render and
    // physics proxies until the new collection is complete so they cannot read
    // the new transform array with an old geometry-index map.
    TArray<UActorComponent*> Users;
    for (TObjectIterator<UGeometryCollectionComponent> It; It; ++It)
        if (It->IsRegistered() && It->GetRestCollection() == Target) Users.Add(*It);
    FMultiComponentReregisterContext Reregister(Users);
    Target->Modify();
    Target->SetGeometryCollection(MakeShared<FGeometryCollection, ESPMode::ThreadSafe>());
    Target->Materials.Reset();
    Target->GeometrySource.Reset();
    const FTransform Frame = Sources[0]->GetActorTransform();
    for (const AStaticMeshActor* Source : Sources)
    {
        if (!Source) return 0;
        const UStaticMeshComponent* Mesh = Source->GetStaticMeshComponent();
        if (!Mesh || !Mesh->GetStaticMesh()) return 0;
        const FTransform Local = Mesh->GetComponentTransform().GetRelativeTransform(Frame);
        const TArray<UMaterialInterface*> Materials = Mesh->GetMaterials();
        if (!FGeometryCollectionEngineConversion::AppendStaticMesh(Mesh->GetStaticMesh(), Materials,
            Local, Target, true, false, false)) return 0;
    }

    auto Collection = Target->GetGeometryCollection();
    FDataflowTransformSelection Selection;
    Selection.Initialize(Collection->Transform.Num(), true);
    FUniformFractureSettings Settings{};
    Settings.Transform = FTransform::Identity;
    Settings.MinVoronoiSites = Settings.MaxVoronoiSites = FMath::Clamp(Cells, 8, 64);
    Settings.InternalMaterialID = Target->Materials.Add(Interior);
    Settings.RandomSeed = Seed;
    Settings.ChanceToFracture = 1.f;
    Settings.GroupFracture = true;
    // Keep each cell as a rigid part; Meshy surface islands should not become
    // hundreds of tiny independently simulated triangles.
    Settings.SplitIslands = false;
    Settings.Grout = 0.f;
    Settings.NoiseSettings.Amplitude = 0.f;
    Settings.AddSamplesForCollision = false;
    Settings.CollisionSampleSpacing = 10.f;
    FFractureEngineFracturing::UniformFracture(*Collection, Selection, Settings);
    FGeometryCollectionClusteringUtility::ClusterAllBonesUnderNewRoot(Collection.Get(), TEXT("Furniture"));
    Collection->ReindexMaterials();
    Target->InitializeMaterials();
    Target->DamageThreshold = {500000.f, 100000.f, 50000.f};
    Target->bMassAsDensity = false;
    Target->Mass = FMath::Max(5.f, Mass);
    Target->MinimumMassClamp = .2f;
    auto& Size = Target->GetDefaultSizeSpecificData();
    for (auto& Shape : Size.CollisionShapes)
    {
        Shape.CollisionType = ECollisionTypeEnum::Chaos_Volumetric;
        Shape.ImplicitType = EImplicitTypeEnum::Chaos_Implicit_Convex;
        Shape.CollisionMarginFraction = .01f;
    }
    RebuildFurniturePhysics(Target);
    return GetRigidPieceCount(Target);
}
