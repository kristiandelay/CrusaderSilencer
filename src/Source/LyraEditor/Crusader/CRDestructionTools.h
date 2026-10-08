#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "CRDestructionTools.generated.h"

UCLASS()
class UCRDestructionTools : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Fracture the original meshes/materials in the first actor's local space. */
    UFUNCTION(BlueprintCallable, Category="Crusader|Editor")
    static int32 BuildFurnitureCollection(class UGeometryCollection* Target,
        const TArray<class AStaticMeshActor*>& Sources, class UMaterialInterface* Interior,
        int32 Cells = 24, int32 Seed = 723, float Mass = 50.f);
    UFUNCTION(BlueprintPure, Category="Crusader|Editor")
    static int32 GetRigidPieceCount(class UGeometryCollection* Collection);
    /** Build collision hulls and simulation data after authoring fracture geometry. */
    UFUNCTION(BlueprintCallable, Category="Crusader|Editor")
    static int32 RebuildFurniturePhysics(class UGeometryCollection* Collection);
    /** Bake uniform placement scale into both geometry and physics. */
    UFUNCTION(BlueprintCallable, Category="Crusader|Editor")
    static int32 BakeFurnitureScale(class UGeometryCollection* Collection, float Factor);
};
