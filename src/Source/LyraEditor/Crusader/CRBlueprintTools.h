#pragma once
#include "Kismet/BlueprintFunctionLibrary.h"
#include "CRBlueprintTools.generated.h"

UCLASS()
class UCRBlueprintTools : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="Crusader|Editor")
    static bool ConfigureCrowdVisualGate(UBlueprint* Manager);
    UFUNCTION(BlueprintCallable, Category="Crusader|Editor")
    static bool ConfigureFootstepEvents(UBlueprint* FoleyComponent);
    UFUNCTION(BlueprintCallable, Category="Crusader|Editor")
    static bool ConfigureWeaponEffectsGate(UBlueprint* Weapon);
    UFUNCTION(BlueprintCallable, Category="Baseline|Editor")
    static bool ConfigureVisualOverrideFallback(UBlueprint* Manager, UClass* Catalog);
    UFUNCTION(BlueprintCallable, Category="Baseline|Editor")
    static bool ConfigureWeaponMirrorTable(class UMirrorDataTable* Table, class USkeleton* Skeleton);
    UFUNCTION(BlueprintCallable, Category="Baseline|Editor")
    static bool ConfigurePhysicalAnimation(UBlueprint* Character, class UAnimBlueprint* Animation);
    UFUNCTION(BlueprintCallable, Category="Crusader|Editor")
    static FString DescribeObject(UObject* Object);
    UFUNCTION(BlueprintCallable, Category="Crusader|Editor")
    static FString DescribeBlueprint(UBlueprint* Blueprint);
    UFUNCTION(BlueprintCallable, Category="Crusader|Editor")
    static int32 RemapGaspTraceChannels(UBlueprint* Blueprint);
    UFUNCTION(BlueprintCallable, Category="Crusader|Editor")
    static bool DisconnectFunctionEntry(UBlueprint* Blueprint, FName GraphName);
    UFUNCTION(BlueprintCallable, Category="Crusader|Editor")
    static int32 RemoveSampleCameraComponents(UBlueprint* Blueprint);
    UFUNCTION(BlueprintCallable, Category="Baseline|Editor")
    static int32 RemoveInputActionBinding(UBlueprint* Blueprint, UObject* Action);
    UFUNCTION(BlueprintCallable, Category="Baseline|Editor")
    static bool BuildWeaponOverlay(class UAnimBlueprint* Blueprint, class UAnimSequence* FallbackPose, class UBlendSpace* FallbackAimOffset);
    UFUNCTION(BlueprintCallable, Category="Baseline|Editor")
    static bool ConfigureWeaponStance(UBlueprint* Character, UClass* NativeCharacterClass, UObject* AimAction, class UAnimBlueprint* SourceAnimation);
    UFUNCTION(BlueprintPure, Category="Baseline|Editor")
    static bool HasBlueprintErrors(UBlueprint* Blueprint);
    UFUNCTION(BlueprintCallable, Category="Baseline|Editor")
    static bool SetPropertyText(UObject* Object, FName PropertyName, const FString& Value);
    UFUNCTION(BlueprintCallable, Category="Baseline|Editor")
    static FString DescribePawnInput(class APawn* Pawn);
    UFUNCTION(BlueprintCallable, Category="Baseline|Editor")
    static int32 RouteNotifyGameplayOwner(UBlueprint* Blueprint, UClass* LibraryClass);
    UFUNCTION(BlueprintCallable, Category="Baseline|Editor")
    static AActor* SpawnPIETestActor(UObject* WorldContext, TSubclassOf<AActor> ActorClass, const FTransform& Transform);
};
