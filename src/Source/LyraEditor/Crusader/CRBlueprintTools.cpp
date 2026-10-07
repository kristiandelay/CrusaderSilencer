#include "CRBlueprintTools.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "UObject/UnrealType.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/SCS_Node.h"
#include "Animation/AnimBlueprint.h"
#include "Animation/AnimSequence.h"
#include "AnimGraphNode_Root.h"
#include "AnimGraphNode_SequencePlayer.h"
#include "AnimGraphNode_Slot.h"
#include "AnimGraphNode_LayeredBoneBlend.h"
#include "AnimGraphNode_RotationOffsetBlendSpace.h"
#include "AnimGraphNode_ModifyBone.h"
#include "AnimGraphNode_LocalToComponentSpace.h"
#include "AnimGraphNode_ComponentToLocalSpace.h"
#include "Animation/BlendSpace.h"
#include "K2Node_VariableGet.h"
#include "EnhancedInputComponent.h"
#include "GameFramework/Pawn.h"
#include "AbilitySystemGlobals.h"
#include "AbilitySystemComponent.h"
#include "Abilities/GameplayAbility.h"
#include "InputAction.h"
#include "K2Node_CallFunction.h"
#include "K2Node_Event.h"
#include "Engine/World.h"
#include "Crusader/CRTraversalCharacter.h"
#include "AnimGraphNode_PoseSnapshot.h"
#include "AnimGraphNode_TwoWayBlend.h"
#include "AnimGraphNode_SaveCachedPose.h"
#include "AnimGraphNode_UseCachedPose.h"
#include "K2Node_IfThenElse.h"
#include "AnimGraphNode_Mirror.h"
#include "Animation/MirrorDataTable.h"
#include "Animation/Skeleton.h"
#include "K2Node_GetClassDefaults.h"
#include "K2Node_DynamicCast.h"
#include "K2Node_VariableSet.h"
#include "K2Node_CustomEvent.h"
#include "K2Node_Self.h"
#include "Crusader/CRWeaponEffects.h"

bool UCRBlueprintTools::ConfigureWeaponEffectsGate(UBlueprint* Weapon)
{
    if (!Weapon) return false;
    for (UEdGraph* Graph : Weapon->UbergraphPages)
    {
        UK2Node_CustomEvent* Fire = nullptr;
        for (UEdGraphNode* Node : Graph->Nodes)
        {
            if (Node->NodeComment == TEXT("Crusader uses committed shot effects")) return true;
            if (auto* Event = Cast<UK2Node_CustomEvent>(Node))
                if (Event->CustomFunctionName == TEXT("Fire")) Fire = Event;
        }
        if (!Fire || Fire->FindPinChecked(TEXT("then"))->LinkedTo.IsEmpty()) continue;
        Weapon->Modify();
        UEdGraphPin* Continue = Fire->FindPinChecked(TEXT("then"))->LinkedTo[0];
        auto* Check = NewObject<UK2Node_CallFunction>(Graph);
        Check->SetFromFunction(UCRWeaponEffectsComponent::StaticClass()->FindFunctionByName(TEXT("UsesCustomWeaponEffects")));
        Graph->AddNode(Check, false, false); Check->CreateNewGuid(); Check->AllocateDefaultPins();
        auto* Self = NewObject<UK2Node_Self>(Graph);
        Graph->AddNode(Self, false, false); Self->CreateNewGuid(); Self->AllocateDefaultPins();
        auto* Gate = NewObject<UK2Node_IfThenElse>(Graph);
        Graph->AddNode(Gate, false, false); Gate->CreateNewGuid(); Gate->AllocateDefaultPins();
        Gate->NodeComment = TEXT("Crusader uses committed shot effects");
        Gate->NodePosX = Fire->NodePosX + 250; Gate->NodePosY = Fire->NodePosY;
        Check->NodePosX = Fire->NodePosX; Check->NodePosY = Fire->NodePosY + 250;
        const auto* Schema = Graph->GetSchema();
        Fire->FindPinChecked(TEXT("then"))->BreakAllPinLinks();
        const bool bOK = Schema->TryCreateConnection(Fire->FindPinChecked(TEXT("then")), Gate->FindPinChecked(TEXT("execute")))
            && Schema->TryCreateConnection(Gate->FindPinChecked(TEXT("else")), Continue)
            && Schema->TryCreateConnection(Check->FindPinChecked(TEXT("ReturnValue")), Gate->FindPinChecked(TEXT("Condition")))
            && Schema->TryCreateConnection(Self->FindPinChecked(TEXT("self")), Check->FindPinChecked(TEXT("WeaponActor")));
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Weapon);
        return bOK;
    }
    return false;
}

bool UCRBlueprintTools::ConfigureVisualOverrideFallback(UBlueprint* Manager, UClass* Catalog)
{
    if (!Manager || !Catalog) return false;
    for (UEdGraph* Graph : Manager->FunctionGraphs)
    {
        if (Graph->GetFName() != TEXT("FindAndApplyVisualOverride")) continue;
        UEdGraphNode* Entry = nullptr;
        bool bHasAuthorityGate = false;
        for (UEdGraphNode* Node : Graph->Nodes)
        {
            if (Node->GetClass()->GetName() == TEXT("K2Node_FunctionEntry")) Entry = Node;
            bHasAuthorityGate |= Node->NodeComment == TEXT("Server selects visual overrides");
        }
        if (!bHasAuthorityGate && Entry && !Entry->FindPinChecked(TEXT("then"))->LinkedTo.IsEmpty())
        {
            auto* Continue = Entry->FindPinChecked(TEXT("then"))->LinkedTo[0];
            auto* Owner = NewObject<UK2Node_CallFunction>(Graph);
            Owner->SetFromFunction(UActorComponent::StaticClass()->FindFunctionByName(TEXT("GetOwner")));
            Graph->AddNode(Owner, false, false);
            Owner->CreateNewGuid(); Owner->AllocateDefaultPins();
            auto* Authority = NewObject<UK2Node_CallFunction>(Graph);
            Authority->SetFromFunction(AActor::StaticClass()->FindFunctionByName(TEXT("HasAuthority")));
            Graph->AddNode(Authority, false, false);
            Authority->CreateNewGuid(); Authority->AllocateDefaultPins();
            auto* Gate = NewObject<UK2Node_IfThenElse>(Graph);
            Graph->AddNode(Gate, false, false);
            Gate->CreateNewGuid(); Gate->AllocateDefaultPins();
            Gate->NodeComment = TEXT("Server selects visual overrides");
            Gate->NodePosX = Entry->NodePosX + 200;
            Gate->NodePosY = Entry->NodePosY;
            const auto* Schema = Graph->GetSchema();
            Entry->FindPinChecked(TEXT("then"))->BreakAllPinLinks();
            if (!Schema->TryCreateConnection(Entry->FindPinChecked(TEXT("then")), Gate->FindPinChecked(TEXT("execute")))
                || !Schema->TryCreateConnection(Gate->FindPinChecked(TEXT("then")), Continue)
                || !Schema->TryCreateConnection(Owner->FindPinChecked(TEXT("ReturnValue")), Authority->FindPinChecked(TEXT("self")))
                || !Schema->TryCreateConnection(Authority->FindPinChecked(TEXT("ReturnValue")), Gate->FindPinChecked(TEXT("Condition")))) return false;
            FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Manager);
        }
        UK2Node_DynamicCast* CastMode = nullptr;
        UK2Node_VariableSet* SetList = nullptr;
        for (UEdGraphNode* Node : Graph->Nodes)
        {
            if (Node->NodeComment == TEXT("Baseline visual catalog fallback")) return true;
            if (auto* Candidate = Cast<UK2Node_DynamicCast>(Node)) CastMode = Candidate;
            if (auto* Set = Cast<UK2Node_VariableSet>(Node))
                if (Set->VariableReference.GetMemberName() == TEXT("VisualOverridesList")) SetList = Set;
        }
        if (!CastMode || !SetList || SetList->FindPinChecked(TEXT("then"))->LinkedTo.IsEmpty()) return false;
        auto* Defaults = NewObject<UK2Node_GetClassDefaults>(Graph);
        Graph->AddNode(Defaults, false, false);
        Defaults->CreateNewGuid();
        Defaults->AllocateDefaultPins();
        Defaults->FindClassPin()->DefaultObject = Catalog;
        Defaults->PinDefaultValueChanged(Defaults->FindClassPin());
        Defaults->NodePosX = CastMode->NodePosX;
        Defaults->NodePosY = CastMode->NodePosY + 300;
        Defaults->NodeComment = TEXT("Baseline visual catalog fallback");
        auto* Fallback = NewObject<UK2Node_VariableSet>(Graph);
        Graph->AddNode(Fallback, false, false);
        Fallback->CreateNewGuid();
        Fallback->VariableReference = SetList->VariableReference;
        Fallback->AllocateDefaultPins();
        Fallback->NodePosX = SetList->NodePosX;
        Fallback->NodePosY = Defaults->NodePosY;
        const auto* Schema = Graph->GetSchema();
        const bool bLinked = Schema->TryCreateConnection(CastMode->FindPinChecked(TEXT("CastFailed")), Fallback->FindPinChecked(TEXT("execute")))
            && Schema->TryCreateConnection(Defaults->FindPinChecked(TEXT("VisualOverrides_Soft")), Fallback->FindPinChecked(TEXT("VisualOverridesList")))
            && Schema->TryCreateConnection(Fallback->FindPinChecked(TEXT("then")), SetList->FindPinChecked(TEXT("then"))->LinkedTo[0]);
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Manager);
        return bLinked;
    }
    return false;
}

bool UCRBlueprintTools::ConfigureWeaponMirrorTable(UMirrorDataTable* Table, USkeleton* Skeleton)
{
    if (!Table || !Skeleton) return false;
    Table->Modify();
    Table->Skeleton = Skeleton;
    Table->MirrorAxis = EAxis::X;
    Table->bMirrorRootMotion = false;
    Table->EmptyTable();
    Table->UpdateFromFindReplaceExpressions(UMirrorDataTable::FFindReplaceOptions::Sync());
    // Weapon animations also use curve names from Lyra's compatible skeleton.
    // Pair named sides and explicitly preserve central curves such as recoil.
    if (auto* WeaponSkeleton = LoadObject<USkeleton>(nullptr, TEXT("/Game/Characters/Heroes/Mannequin/Meshes/SK_Mannequin.SK_Mannequin")))
    {
        TArray<FName> Curves;
        WeaponSkeleton->GetCurveMetaDataNames(Curves);
        for (FName Curve : Curves)
        {
            const FName Candidate = Table->FindReplace(Curve);
            const FName Other = !Candidate.IsNone() && Curves.Contains(Candidate) ? Candidate : Curve;
            Table->AddRow(FName(*(TEXT("WeaponCurve_") + Curve.ToString())), FMirrorTableRow(Curve, Other, EMirrorRowType::Curve, true));
        }
    }
    Table->MarkPackageDirty();
    return !Table->GetRowMap().IsEmpty();
}

AActor* UCRBlueprintTools::SpawnPIETestActor(UObject* WorldContext, TSubclassOf<AActor> ActorClass, const FTransform& Transform)
{
    UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
    if (!World || World->WorldType != EWorldType::PIE || !ActorClass) return nullptr;
    FActorSpawnParameters Parameters;
    Parameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    return World->SpawnActor<AActor>(ActorClass, Transform, Parameters);
}

FString UCRBlueprintTools::DescribeObject(UObject* Object)
{
    FString Result;
    if (!Object) return TEXT("null");
    for (TFieldIterator<FProperty> It(Object->GetClass()); It; ++It)
    {
        FString Value;
        It->ExportText_InContainer(0, Value, Object, Object, Object, PPF_None);
        Result += It->GetName() + TEXT(" = ") + Value + TEXT("\n");
    }
    return Result;
}

int32 UCRBlueprintTools::RouteNotifyGameplayOwner(UBlueprint* Blueprint, UClass* LibraryClass)
{
    UFunction* Function = LibraryClass ? LibraryClass->FindFunctionByName(TEXT("GetGameplayOwner")) : nullptr;
    if (!Blueprint || !Function) return 0;
    int32 Count = 0;
    TArray<UEdGraph*> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    for (UEdGraph* Graph : Graphs)
        for (UEdGraphNode* Node : Graph->Nodes)
            if (auto* Call = Cast<UK2Node_CallFunction>(Node))
                if (Call->FunctionReference.GetMemberName() == TEXT("GetOwner"))
                {
                    UEdGraphPin* OldInput = Call->FindPin(TEXT("self"));
                    UEdGraphPin* OldOutput = Call->FindPin(TEXT("ReturnValue"));
                    if (!OldInput || !OldOutput) continue;
                    const auto InputLinks = OldInput->LinkedTo;
                    const auto OutputLinks = OldOutput->LinkedTo;
                    Call->BreakAllNodeLinks();
                    Call->SetFromFunction(Function);
                    Call->ReconstructNode();
                    for (UEdGraphPin* Pin : InputLinks) Call->FindPinChecked(TEXT("Component"))->MakeLinkTo(Pin);
                    for (UEdGraphPin* Pin : OutputLinks) Call->FindPinChecked(TEXT("ReturnValue"))->MakeLinkTo(Pin);
                    ++Count;
                }
    if (Count) FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
    return Count;
}

FString UCRBlueprintTools::DescribePawnInput(APawn* Pawn)
{
    if (!Pawn) return TEXT("No pawn");
    FString Result;
    if (auto* Input = Pawn->FindComponentByClass<UEnhancedInputComponent>())
        for (const auto& Binding : Input->GetActionEventBindings())
            Result += FString::Printf(TEXT("Binding %s event %d owner %s\n"), *GetPathNameSafe(Binding->GetAction()), int32(Binding->GetTriggerEvent()), *GetPathNameSafe(Binding->GetUObject()));
    if (auto* ASC = UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(Pawn))
        for (const auto& Spec : ASC->GetActivatableAbilities())
            Result += FString::Printf(TEXT("Ability %s input tags %s pressed %d active %d\n"), *GetPathNameSafe(Spec.Ability),
                *Spec.GetDynamicSpecSourceTags().ToStringSimple(), Spec.InputPressed, Spec.IsActive());
    return Result;
}

bool UCRBlueprintTools::SetPropertyText(UObject* Object, FName PropertyName, const FString& Value)
{
    if (!Object) return false;
    FProperty* Property = Object->GetClass()->FindPropertyByName(PropertyName);
    return Property && Property->ImportText_Direct(*Value, Property->ContainerPtrToValuePtr<void>(Object), Object, PPF_None);
}

bool UCRBlueprintTools::HasBlueprintErrors(UBlueprint* Blueprint)
{
    return !Blueprint || Blueprint->Status == BS_Error;
}

int32 UCRBlueprintTools::RemapGaspTraceChannels(UBlueprint* Blueprint)
{
    int32 Count = 0;
    TArray<UEdGraph*> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    for (UEdGraph* Graph : Graphs)
        for (UEdGraphNode* Node : Graph->Nodes)
            for (UEdGraphPin* Pin : Node->Pins)
                if (Pin->Direction == EGPD_Input && Pin->LinkedTo.IsEmpty() &&
                    Pin->PinType.PinSubCategoryObject.IsValid() &&
                    Pin->PinType.PinSubCategoryObject->GetName() == TEXT("ETraceTypeQuery"))
                {
                    if (Pin->DefaultValue == TEXT("TraceTypeQuery3")) { Pin->DefaultValue = TEXT("TraceTypeQuery8"); ++Count; }
                    else if (Pin->DefaultValue == TEXT("TraceTypeQuery4")) { Pin->DefaultValue = TEXT("TraceTypeQuery9"); ++Count; }
                }
    if (Count) FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
    return Count;
}

bool UCRBlueprintTools::DisconnectFunctionEntry(UBlueprint* Blueprint, FName GraphName)
{
    for (UEdGraph* Graph : Blueprint->FunctionGraphs)
        if (Graph->GetFName() == GraphName)
            for (UEdGraphNode* Node : Graph->Nodes)
                if (Node->GetClass()->GetName() == TEXT("K2Node_FunctionEntry"))
                {
                    Node->BreakAllNodeLinks();
                    // These source setup functions have no outputs. Keep callable empty
                    // stubs while removing references to the superseded sample cameras.
                    const TArray<TObjectPtr<UEdGraphNode>> OldNodes = Graph->Nodes;
                    for (UEdGraphNode* Other : OldNodes)
                        if (Other != Node) FBlueprintEditorUtils::RemoveNode(Blueprint, Other, true);
                    FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
                    return true;
                }
    return false;
}

int32 UCRBlueprintTools::RemoveSampleCameraComponents(UBlueprint* Blueprint)
{
    int32 Count = 0;
    USimpleConstructionScript* SCS = Blueprint ? Blueprint->SimpleConstructionScript : nullptr;
    if (!SCS) return Count;
    for (const FString& Prefix : {FString(TEXT("GameplayCamera")), FString(TEXT("Camera(NotUsedByDefault)")), FString(TEXT("SpringArm"))})
    {
        const TArray<USCS_Node*> Nodes = SCS->GetAllNodes();
        for (USCS_Node* Node : Nodes)
            if (Node->ComponentTemplate && Node->ComponentTemplate->GetName().StartsWith(Prefix))
            {
                // Remove leaves directly. Editor 'promote children' expects a Blueprint
                // parent node, but these source nodes can attach to the native capsule.
                check(Node->GetChildNodes().IsEmpty());
                SCS->RemoveNode(Node);
                ++Count;
            }
    }
    if (Count) FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
    return Count;
}

FString UCRBlueprintTools::DescribeBlueprint(UBlueprint* Blueprint)
{
    FString Result;
    if (!Blueprint) return Result;
    TArray<UEdGraph*> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    for (UEdGraph* Graph : Graphs)
    {
        Result += TEXT("\nGRAPH ") + Graph->GetName() + TEXT("\n");
        for (UEdGraphNode* Node : Graph->Nodes)
        {
            Result += Node->GetName() + TEXT(" | ") + Node->GetNodeTitle(ENodeTitleType::FullTitle).ToString() + TEXT("\n");
            for (UEdGraphPin* Pin : Node->Pins)
            {
                Result += FString::Printf(TEXT("  %s %s = %s %s -> "), Pin->Direction == EGPD_Input ? TEXT("IN") : TEXT("OUT"), *Pin->PinName.ToString(), *Pin->DefaultValue, *GetPathNameSafe(Pin->DefaultObject));
                for (UEdGraphPin* Link : Pin->LinkedTo)
                    Result += Link->GetOwningNode()->GetName() + TEXT(".") + Link->PinName.ToString() + TEXT(" ");
                Result += TEXT("\n");
            }
        }
    }
    return Result;
}

int32 UCRBlueprintTools::RemoveInputActionBinding(UBlueprint* Blueprint, UObject* Action)
{
    int32 Count = 0;
    TArray<UEdGraph*> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    for (UEdGraph* Graph : Graphs)
    {
        const TArray<TObjectPtr<UEdGraphNode>> Nodes = Graph->Nodes;
        for (UEdGraphNode* Node : Nodes)
            if (Node->GetClass()->GetName() == TEXT("K2Node_EnhancedInputAction"))
                if (const UEdGraphPin* Pin = Node->FindPin(TEXT("InputAction")))
                    if (Pin->DefaultObject == Action)
                    {
                        FBlueprintEditorUtils::RemoveNode(Blueprint, Node, true);
                        ++Count;
                    }
    }
    if (Count) FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
    return Count;
}

namespace
{
template <class T> T* AddBaselineAnimNode(UEdGraph* Graph, int32 X, int32 Y)
{
    T* Node = NewObject<T>(Graph);
    Graph->AddNode(Node, false, false);
    Node->CreateNewGuid();
    Node->PostPlacedNewNode();
    Node->AllocateDefaultPins();
    Node->NodePosX = X;
    Node->NodePosY = Y;
    return Node;
}

bool ConfigureRecoveryPosePath(UEdGraph* Graph, UEdGraphNode* SnapshotBlend)
{
    UAnimGraphNode_Slot* Slot = nullptr;
    for (UEdGraphNode* Node : Graph->Nodes)
    {
        if (Node->NodeComment == TEXT("Baseline recovery without locomotion IK")) return true;
        if (auto* Candidate = Cast<UAnimGraphNode_Slot>(Node))
            if (Candidate->Node.SlotName == TEXT("DefaultSlot")) Slot = Candidate;
    }
    if (!Slot || SnapshotBlend->FindPinChecked(TEXT("A"))->LinkedTo.IsEmpty()) return false;
    const auto* Schema = Graph->GetSchema();
    // Share the full-body montage before locomotion root offsets and foot
    // planting. Those standing-foot corrections distort a prone get-up.
    auto* Cache = AddBaselineAnimNode<UAnimGraphNode_SaveCachedPose>(Graph, Slot->NodePosX+200, Slot->NodePosY);
    Cache->CacheName = TEXT("BaselineFullBodySlot");
    auto* Normal = AddBaselineAnimNode<UAnimGraphNode_UseCachedPose>(Graph, Slot->NodePosX+400, Slot->NodePosY);
    auto* Recovery = AddBaselineAnimNode<UAnimGraphNode_UseCachedPose>(Graph, SnapshotBlend->NodePosX-500, SnapshotBlend->NodePosY-300);
    Normal->SaveCachedPoseNode = Cache;
    Recovery->SaveCachedPoseNode = Cache;
    auto* SlotOutput = Slot->FindPinChecked(TEXT("Pose"));
    const auto Consumers = SlotOutput->LinkedTo;
    SlotOutput->BreakAllPinLinks();
    if (!Schema->TryCreateConnection(SlotOutput, Cache->FindPinChecked(TEXT("Pose")))) return false;
    for (auto* Consumer : Consumers)
        if (!Schema->TryCreateConnection(Normal->FindPinChecked(TEXT("Pose")), Consumer)) return false;
    auto* Select = AddBaselineAnimNode<UAnimGraphNode_TwoWayBlend>(Graph, SnapshotBlend->NodePosX-200, SnapshotBlend->NodePosY-150);
    Select->NodeComment = TEXT("Baseline recovery without locomotion IK");
    // Keep the normal graph current so returning to locomotion cannot restore
    // stale root offsets or planted feet from before the fall.
    auto* AlwaysUpdate = FindFProperty<FBoolProperty>(FAnimNode_TwoWayBlend::StaticStruct(), TEXT("bAlwaysUpdateChildren"));
    check(AlwaysUpdate);
    AlwaysUpdate->SetPropertyValue_InContainer(&Select->BlendNode, true);
    auto* Weight = AddBaselineAnimNode<UK2Node_VariableGet>(Graph, Select->NodePosX-300, Select->NodePosY+200);
    Weight->VariableReference.SetSelfMember(TEXT("RecoveryAnimationWeight"));
    Weight->ReconstructNode();
    auto* NormalOutput = SnapshotBlend->FindPinChecked(TEXT("A"))->LinkedTo[0];
    SnapshotBlend->FindPinChecked(TEXT("A"))->BreakAllPinLinks();
    return Schema->TryCreateConnection(NormalOutput, Select->FindPinChecked(TEXT("A")))
        && Schema->TryCreateConnection(Recovery->FindPinChecked(TEXT("Pose")), Select->FindPinChecked(TEXT("B")))
        && Schema->TryCreateConnection(Weight->GetValuePin(), Select->FindPinChecked(TEXT("Alpha")))
        && Schema->TryCreateConnection(Select->FindPinChecked(TEXT("Pose")), SnapshotBlend->FindPinChecked(TEXT("A")));
}
}


bool UCRBlueprintTools::ConfigurePhysicalAnimation(UBlueprint* Character, UAnimBlueprint* Animation)
{
    if (!Character || !Animation) return false;
    TArray<UEdGraph*> Graphs;
    Character->GetAllGraphs(Graphs);
    for (UEdGraph* Graph : Graphs)
    {
        const auto* Schema = Graph->GetSchema();
        if (Graph->GetFName() == TEXT("Get_MMIResult"))
        {
            UEdGraphNode* Return = nullptr;
            for (UEdGraphNode* Node : Graph->Nodes) if (Node->GetClass()->GetName() == TEXT("K2Node_FunctionResult")) Return = Node;
            if (!Return) return false;
            if (Return->FindPinChecked(TEXT("Result"))->LinkedTo.IsEmpty())
            {
                auto* Call = AddBaselineAnimNode<UK2Node_CallFunction>(Graph, 0, 100);
                Call->SetFromFunction(ACRTraversalCharacter::StaticClass()->FindFunctionByName(TEXT("GetPhysicalInteractionResult")));
                Call->ReconstructNode();
                if (!Schema->TryCreateConnection(Call->GetReturnValuePin(), Return->FindPinChecked(TEXT("Result")))) return false;
            }
        }
        const auto Nodes = Graph->Nodes;
        for (UEdGraphNode* Node : Nodes)
        {
            if (Node->GetClass()->GetName() != TEXT("K2Node_EnhancedInputAction")) continue;
            auto* Action = Node->FindPin(TEXT("InputAction"));
            if (!Action || !Action->DefaultObject || Action->DefaultObject->GetName() != TEXT("IA_Jump")) continue;
            for (const FName PinName : {FName(TEXT("Started")), FName(TEXT("Triggered"))})
            {
                auto* Pin = Node->FindPin(PinName);
                if (!Pin || Pin->LinkedTo.IsEmpty() || Pin->LinkedTo[0]->GetOwningNode()->NodeComment == TEXT("Physical action gate")) continue;
                const auto Links = Pin->LinkedTo;
                Pin->BreakAllPinLinks();
                auto* Gate = AddBaselineAnimNode<UK2Node_IfThenElse>(Graph, Node->NodePosX+200, Node->NodePosY);
                Gate->NodeComment = TEXT("Physical action gate");
                auto* Call = AddBaselineAnimNode<UK2Node_CallFunction>(Graph, Node->NodePosX, Node->NodePosY-150);
                Call->SetFromFunction(ACRTraversalCharacter::StaticClass()->FindFunctionByName(TEXT("CanUseMovementActions")));
                Call->ReconstructNode();
                Schema->TryCreateConnection(Call->GetReturnValuePin(), Gate->GetConditionPin());
                Schema->TryCreateConnection(Pin, Gate->GetExecPin());
                for (auto* Link : Links) Schema->TryCreateConnection(Gate->GetThenPin(), Link);
            }
        }
    }
    Graphs.Reset(); Animation->GetAllGraphs(Graphs);
    for (UEdGraph* Graph : Graphs)
    {
        if (Graph->GetFName() != TEXT("AnimGraph")) continue;
        UEdGraphNode* History = nullptr;
        for (UEdGraphNode* Node : Graph->Nodes)
        {
            if (Node->NodeComment == TEXT("Baseline recovery blend"))
            {
                const bool bConfigured = ConfigureRecoveryPosePath(Graph, Node);
                if (bConfigured)
                {
                    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Character);
                    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Animation);
                }
                return bConfigured;
            }
            if (Node->GetClass()->GetName() == TEXT("AnimGraphNode_PoseSearchHistoryCollector")) History = Node;
        }
        if (!History || History->FindPinChecked(TEXT("Source"))->LinkedTo.IsEmpty()) return false;
        auto* Source = History->FindPinChecked(TEXT("Source"))->LinkedTo[0];
        History->FindPinChecked(TEXT("Source"))->BreakAllPinLinks();
        auto* Snapshot = AddBaselineAnimNode<UAnimGraphNode_PoseSnapshot>(Graph, History->NodePosX-500, History->NodePosY+250);
        Snapshot->Node.Mode = ESnapshotSourceMode::NamedSnapshot;
        Snapshot->Node.SnapshotName = TEXT("BaselineRagdoll");
        Snapshot->FindPinChecked(TEXT("SnapshotName"))->DefaultValue = TEXT("BaselineRagdoll");
        auto* Blend = AddBaselineAnimNode<UAnimGraphNode_TwoWayBlend>(Graph, History->NodePosX-200, History->NodePosY);
        Blend->NodeComment = TEXT("Baseline recovery blend");
        auto* Weight = AddBaselineAnimNode<UK2Node_VariableGet>(Graph, History->NodePosX-500, History->NodePosY+400);
        Weight->VariableReference.SetSelfMember(TEXT("RecoveryPoseWeight")); Weight->ReconstructNode();
        const auto* Schema = Graph->GetSchema();
        if (!Schema->TryCreateConnection(Source, Blend->FindPinChecked(TEXT("A")))
            || !Schema->TryCreateConnection(Snapshot->FindPinChecked(TEXT("Pose")), Blend->FindPinChecked(TEXT("B")))
            || !Schema->TryCreateConnection(Weight->GetValuePin(), Blend->FindPinChecked(TEXT("Alpha")))
            || !Schema->TryCreateConnection(Blend->FindPinChecked(TEXT("Pose")), History->FindPinChecked(TEXT("Source")))) return false;
        if (!ConfigureRecoveryPosePath(Graph, Blend)) return false;
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Character);
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Animation);
    return true;
}

bool UCRBlueprintTools::BuildWeaponOverlay(UAnimBlueprint* Blueprint, UAnimSequence* FallbackPose, UBlendSpace* FallbackAimOffset)
{
    if (!Blueprint || !FallbackPose || !FallbackAimOffset) return false;
    TArray<UEdGraph*> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    for (UEdGraph* Graph : Graphs)
    {
        if (Graph->GetFName() != TEXT("AnimGraph")) continue;
        UAnimGraphNode_Root* Root = nullptr;
        UEdGraphNode* Retarget = nullptr;
        const TArray<TObjectPtr<UEdGraphNode>> OldNodes = Graph->Nodes;
        for (UEdGraphNode* Node : OldNodes)
        {
            if (auto* Candidate = Cast<UAnimGraphNode_Root>(Node)) Root = Candidate;
            else if (Node->GetClass()->GetName() == TEXT("AnimGraphNode_RetargetPoseFromMesh")) Retarget = Node;
            else FBlueprintEditorUtils::RemoveNode(Blueprint, Node, true);
        }
        if (!Root || !Retarget) return false;
        Root->BreakAllNodeLinks();
        Retarget->FindPinChecked(TEXT("Pose"))->BreakAllPinLinks();
        Retarget->NodePosX = -700;
        Retarget->NodePosY = -200;
        auto* Player = AddBaselineAnimNode<UAnimGraphNode_SequencePlayer>(Graph, -900, 100);
        Player->Node.SetSequence(FallbackPose);
        Player->Node.SetLoopAnimation(true);
        for (FOptionalPinFromProperty& Pin : Player->ShowPinForProperties)
            if (Pin.PropertyName == TEXT("Sequence")) Pin.bShowPin = true;
        Player->ReconstructNode();
        auto* PoseVar = AddBaselineAnimNode<UK2Node_VariableGet>(Graph, -1200, 150);
        PoseVar->VariableReference.SetSelfMember(TEXT("WeaponPose"));
        PoseVar->ReconstructNode();
        auto* WeightVar = AddBaselineAnimNode<UK2Node_VariableGet>(Graph, -250, 350);
        WeightVar->VariableReference.SetSelfMember(TEXT("WeaponPoseWeight"));
        WeightVar->ReconstructNode();
        auto* UpperWeight = AddBaselineAnimNode<UK2Node_VariableGet>(Graph, 400, 450);
        UpperWeight->VariableReference.SetSelfMember(TEXT("WeaponUpperBodyWeight"));
        UpperWeight->ReconstructNode();
        auto* CarryPlayer = AddBaselineAnimNode<UAnimGraphNode_SequencePlayer>(Graph, -650, -500);
        CarryPlayer->Node.SetSequence(FallbackPose);
        CarryPlayer->Node.SetLoopAnimation(true);
        for (FOptionalPinFromProperty& Pin : CarryPlayer->ShowPinForProperties)
            if (Pin.PropertyName == TEXT("Sequence")) Pin.bShowPin = true;
        CarryPlayer->ReconstructNode();
        auto* CarryPose = AddBaselineAnimNode<UK2Node_VariableGet>(Graph, -950, -500);
        CarryPose->VariableReference.SetSelfMember(TEXT("WeaponCarryPose"));
        CarryPose->ReconstructNode();
        auto* CarryBlend = AddBaselineAnimNode<UAnimGraphNode_LayeredBoneBlend>(Graph, -300, -300);
        CarryBlend->Node.BlendPoses.SetNum(1);
        CarryBlend->Node.BlendWeights = {1.f};
        CarryBlend->Node.LayerSetup.SetNum(1);
        for (const FName Bone : {FName(TEXT("clavicle_l")), FName(TEXT("clavicle_r"))})
        {
            FBranchFilter Arm;
            Arm.BoneName = Bone;
            Arm.BlendDepth = 1;
            CarryBlend->Node.LayerSetup[0].BranchFilters.Add(Arm);
        }
        // Local-space arms inherit the source chest's breathing, sway and turns.
        // The relaxed overlay never replaces the head, neck, spine or pelvis.
        CarryBlend->Node.bMeshSpaceRotationBlend = false;
        CarryBlend->ReconstructNode();
        auto* FireSlot = AddBaselineAnimNode<UAnimGraphNode_Slot>(Graph, -650, 100);
        FireSlot->Node.SlotName = TEXT("FullBodyAdditivePreAim");
        auto* UpperSlot = AddBaselineAnimNode<UAnimGraphNode_Slot>(Graph, -400, 100);
        UpperSlot->Node.SlotName = TEXT("UpperBody");
        UAnimGraphNode_Mirror* UpperMirror = nullptr;
        UAnimGraphNode_Mirror* CarryMirror = nullptr;
        if (auto* Table = LoadObject<UMirrorDataTable>(nullptr, TEXT("/Game/Baseline/Animations/MDT_WeaponHands.MDT_WeaponHands")))
        {
            // Mirror only weapon animation branches. GASP locomotion, physical
            // recovery and root-facing correction retain their original pose.
            auto* Hand = AddBaselineAnimNode<UK2Node_VariableGet>(Graph, -850, -700);
            Hand->VariableReference.SetSelfMember(TEXT("bWeaponLeftHand"));
            Hand->ReconstructNode();
            UpperMirror = AddBaselineAnimNode<UAnimGraphNode_Mirror>(Graph, -180, 180);
            CarryMirror = AddBaselineAnimNode<UAnimGraphNode_Mirror>(Graph, -430, -500);
            for (auto* Mirror : {UpperMirror, CarryMirror})
            {
                Mirror->Node.SetMirrorDataTable(Table);
                Mirror->Node.SetMirror(false);
                Mirror->Node.SetBlendTimeOnMirrorStateChange(.35f);
                auto* BlendType = FindFProperty<FEnumProperty>(FAnimNode_Mirror::StaticStruct(), TEXT("BlendType"));
                check(BlendType);
                BlendType->GetUnderlyingProperty()->SetIntPropertyValue(BlendType->ContainerPtrToValuePtr<void>(&Mirror->Node),
                    static_cast<int64>(EMirrorBlendType::StandardBlend));
                Mirror->ReconstructNode();
                if (!Graph->GetSchema()->TryCreateConnection(Hand->GetValuePin(), Mirror->FindPinChecked(TEXT("bMirror")))) return false;
            }
        }
        auto* Aim = AddBaselineAnimNode<UAnimGraphNode_RotationOffsetBlendSpace>(Graph, -400, 450);
        Aim->Node.SetBlendSpace(FallbackAimOffset);
        for (FOptionalPinFromProperty& Pin : Aim->ShowPinForProperties)
            if (Pin.PropertyName == TEXT("BlendSpace")) Pin.bShowPin = true;
        Aim->ReconstructNode();
        auto* AimAsset = AddBaselineAnimNode<UK2Node_VariableGet>(Graph, -700, 600);
        AimAsset->VariableReference.SetSelfMember(TEXT("WeaponAimOffset"));
        AimAsset->ReconstructNode();
        auto* AimYaw = AddBaselineAnimNode<UK2Node_VariableGet>(Graph, -700, 700);
        AimYaw->VariableReference.SetSelfMember(TEXT("AimYaw"));
        AimYaw->ReconstructNode();
        auto* AimPitch = AddBaselineAnimNode<UK2Node_VariableGet>(Graph, -700, 800);
        AimPitch->VariableReference.SetSelfMember(TEXT("AimPitch"));
        AimPitch->ReconstructNode();
        auto* Blend = AddBaselineAnimNode<UAnimGraphNode_LayeredBoneBlend>(Graph, 0, 0);
        auto* ToComponent = AddBaselineAnimNode<UAnimGraphNode_LocalToComponentSpace>(Graph, -100, 100);
        auto* RootRotation = AddBaselineAnimNode<UAnimGraphNode_ModifyBone>(Graph, 100, 150);
        RootRotation->Node.BoneToModify.BoneName = TEXT("root");
        RootRotation->Node.RotationMode = BMM_Additive;
        RootRotation->Node.RotationSpace = BCS_ComponentSpace;
        auto* ToLocal = AddBaselineAnimNode<UAnimGraphNode_ComponentToLocalSpace>(Graph, 350, 150);
        auto* RootRotationVar = AddBaselineAnimNode<UK2Node_VariableGet>(Graph, -100, 500);
        RootRotationVar->VariableReference.SetSelfMember(TEXT("WeaponRootRotation"));
        RootRotationVar->ReconstructNode();
        Blend->Node.BlendPoses.SetNum(1);
        Blend->Node.BlendWeights.SetNum(1);
        Blend->Node.BlendWeights[0] = 1.f;
        Blend->Node.LayerSetup.SetNum(1);
        FBranchFilter Filter;
        Filter.BoneName = TEXT("spine_01");
        Filter.BlendDepth = 3;
        Blend->Node.LayerSetup[0].BranchFilters = {Filter};
        Blend->Node.bMeshSpaceRotationBlend = true;
        Blend->ReconstructNode();
        const UEdGraphSchema* Schema = Graph->GetSchema();
        auto Link = [Schema](UEdGraphNode* A, const TCHAR* APin, UEdGraphNode* B, const TCHAR* BPin)
        {
            UEdGraphPin* Out = A->FindPin(APin);
            UEdGraphPin* In = B->FindPin(BPin);
            return Out && In && Schema->TryCreateConnection(Out, In);
        };
        const bool bLinked = Link(PoseVar, TEXT("WeaponPose"), Player, TEXT("Sequence"))
            && Link(Player, TEXT("Pose"), FireSlot, TEXT("Source"))
            && Link(FireSlot, TEXT("Pose"), Aim, TEXT("BasePose"))
            && Link(AimAsset, TEXT("WeaponAimOffset"), Aim, TEXT("BlendSpace"))
            && Link(AimYaw, TEXT("AimYaw"), Aim, TEXT("X"))
            && Link(AimPitch, TEXT("AimPitch"), Aim, TEXT("Y"))
            && Link(Aim, TEXT("Pose"), UpperSlot, TEXT("Source"))
            && (UpperMirror
                ? Link(UpperSlot, TEXT("Pose"), UpperMirror, TEXT("Source")) && Link(UpperMirror, TEXT("Pose"), ToComponent, TEXT("LocalPose"))
                : Link(UpperSlot, TEXT("Pose"), ToComponent, TEXT("LocalPose")))
            && Link(ToComponent, TEXT("ComponentPose"), RootRotation, TEXT("ComponentPose"))
            && Link(RootRotationVar, TEXT("WeaponRootRotation"), RootRotation, TEXT("Rotation"))
            && Link(RootRotation, TEXT("Pose"), ToLocal, TEXT("ComponentPose"))
            && Link(ToLocal, TEXT("Pose"), Blend, TEXT("BlendPoses_0"))
            && Link(UpperWeight, TEXT("WeaponUpperBodyWeight"), Blend, TEXT("BlendWeights_0"))
            && Link(CarryPose, TEXT("WeaponCarryPose"), CarryPlayer, TEXT("Sequence"))
            && (CarryMirror
                ? Link(CarryPlayer, TEXT("Pose"), CarryMirror, TEXT("Source")) && Link(CarryMirror, TEXT("Pose"), CarryBlend, TEXT("BlendPoses_0"))
                : Link(CarryPlayer, TEXT("Pose"), CarryBlend, TEXT("BlendPoses_0")))
            && Link(WeightVar, TEXT("WeaponPoseWeight"), CarryBlend, TEXT("BlendWeights_0"))
            && Link(Retarget, TEXT("Pose"), CarryBlend, TEXT("BasePose"))
            && Link(CarryBlend, TEXT("Pose"), Blend, TEXT("BasePose"))
            && Link(Blend, TEXT("Pose"), Root, TEXT("Result"));
        Blend->NodePosX = 650;
        Root->NodePosX = 950;
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
        return bLinked;
    }
    return false;
}

bool UCRBlueprintTools::ConfigureWeaponStance(UBlueprint* Character, UClass* NativeCharacterClass, UObject* AimAction, UAnimBlueprint* SourceAnimation)
{
    if (!Character || !NativeCharacterClass || !AimAction || !SourceAnimation) return false;
    const FName EventName(TEXT("SetWeaponReadyForAnimation"));
    auto KeepLocalStanceUpdate = [](UK2Node_Event* Event)
    {
        // The native equipment component already replicates readiness. The old
        // input handler forwarded its struct to a server RPC; calling that from
        // animation updates would resend every frame, including on observers.
        for (UEdGraphPin* SetterInput : Event->FindPinChecked(TEXT("then"))->LinkedTo)
            if (auto* Then = SetterInput->GetOwningNode()->FindPin(TEXT("then")))
                Then->BreakAllPinLinks();
    };
    bool bHasEvent = false;
    TArray<UEdGraph*> Graphs;
    Character->GetAllGraphs(Graphs);
    for (UEdGraph* Graph : Graphs)
    {
        const auto OldNodes = Graph->Nodes;
        for (UEdGraphNode* Node : OldNodes)
        {
            if (auto* Event = Cast<UK2Node_Event>(Node))
                if (Event->EventReference.GetMemberName() == EventName)
                {
                    KeepLocalStanceUpdate(Event);
                    bHasEvent = true;
                }
            if (Node->GetClass()->GetName() != TEXT("K2Node_EnhancedInputAction")) continue;
            auto* ActionPin = Node->FindPin(TEXT("InputAction"));
            if (!ActionPin || ActionPin->DefaultObject != AimAction) continue;
            const auto ExecLinks = Node->FindPinChecked(TEXT("Triggered"))->LinkedTo;
            const auto ValueLinks = Node->FindPinChecked(TEXT("ActionValue"))->LinkedTo;
            auto* Event = NewObject<UK2Node_Event>(Graph);
            Event->EventReference.SetExternalMember(EventName, NativeCharacterClass);
            Event->bOverrideFunction = true;
            Graph->AddNode(Event, false, false);
            Event->CreateNewGuid();
            Event->AllocateDefaultPins();
            Event->NodePosX = Node->NodePosX;
            Event->NodePosY = Node->NodePosY;
            FBlueprintEditorUtils::RemoveNode(Character, Node, true);
            for (UEdGraphPin* Pin : ExecLinks) Event->FindPinChecked(TEXT("then"))->MakeLinkTo(Pin);
            for (UEdGraphPin* Pin : ValueLinks) Event->FindPinChecked(TEXT("bReady"))->MakeLinkTo(Pin);
            KeepLocalStanceUpdate(Event);
            bHasEvent = true;
        }
    }
    if (!bHasEvent) return false;
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Character);
    Graphs.Reset();
    SourceAnimation->GetAllGraphs(Graphs);
    bool bThresholdSet = false;
    for (UEdGraph* Graph : Graphs)
        if (Graph->GetFName() == TEXT("ShouldTurnInPlace"))
            for (UEdGraphNode* Node : Graph->Nodes)
                if (Node->GetNodeTitle(ENodeTitleType::FullTitle).ToString() == TEXT("float >= float"))
                    if (auto* Threshold = Node->FindPin(TEXT("B")))
                    {
                        Threshold->DefaultValue = TEXT("35.000000");
                        bThresholdSet = true;
                    }
    FBlueprintEditorUtils::MarkBlueprintAsModified(SourceAnimation);
    return bThresholdSet;
}
