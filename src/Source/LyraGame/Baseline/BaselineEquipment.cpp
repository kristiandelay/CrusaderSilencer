#include "BaselineEquipment.h"
#include "BaselinePhysicalInteraction.h"
#include "BaselineCharacterMovement.h"
#include "Crusader/CRTraversalCharacter.h"
#include "AbilitySystem/LyraAbilitySystemComponent.h"
#include "AbilitySystemGlobals.h"
#include "Components/BoxComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/ChildActorComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/Canvas.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Equipment/LyraEquipmentManagerComponent.h"
#include "Equipment/LyraQuickBarComponent.h"
#include "Inventory/LyraInventoryManagerComponent.h"
#include "Inventory/LyraInventoryItemDefinition.h"
#include "Inventory/LyraInventoryItemInstance.h"
#include "Inventory/InventoryFragment_PickupIcon.h"
#include "Inventory/InventoryFragment_EquippableItem.h"
#include "GameFramework/Character.h"
#include "Net/UnrealNetwork.h"
#include "NativeGameplayTags.h"
#include "Weapons/LyraWeaponStateComponent.h"
#include "Character/LyraHealthComponent.h"

UE_DEFINE_GAMEPLAY_TAG_STATIC(TAG_Baseline_HandsBusy, "Baseline.State.HandsBusy");
UE_DEFINE_GAMEPLAY_TAG_STATIC(TAG_Baseline_ChangingShoulder, "Baseline.State.ChangingShoulder");

namespace
{
FGameplayTag MagazineTag() { return FGameplayTag::RequestGameplayTag(TEXT("Lyra.ShooterGame.Weapon.MagazineAmmo")); }
FGameplayTag SpareTag() { return FGameplayTag::RequestGameplayTag(TEXT("Lyra.ShooterGame.Weapon.SpareAmmo")); }
}

AActor* UBaselineAnimationLibrary::GetGameplayOwner(UActorComponent* Component)
{
    AActor* Actor = Component ? Component->GetOwner() : nullptr;
    // A retarget presentation mesh can belong to a ChildActor rather than the pawn.
    // Keep weapon notifies and GAS reload events on the actor that owns equipment.
    for (int32 Depth = 0; Actor && Depth < 8; ++Depth)
    {
        if (Actor->FindComponentByClass<ULyraEquipmentManagerComponent>()) return Actor;
        AActor* Parent = Actor->GetParentActor();
        if (!Parent) Parent = Actor->GetOwner();
        if (!Parent || Parent == Actor) break;
        Actor = Parent;
    }
    return Actor;
}

ABaselineWeaponPickup::ABaselineWeaponPickup()
{
    bReplicates = true;
    SetReplicateMovement(true);
    Collision = CreateDefaultSubobject<UBoxComponent>(TEXT("Collision"));
    SetRootComponent(Collision);
    Collision->InitBoxExtent(FVector(40.f, 12.f, 9.f));
    Collision->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    Collision->SetCollisionObjectType(ECC_WorldDynamic);
    Collision->SetCollisionResponseToAllChannels(ECR_Ignore);
    Collision->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
    Collision->SetCollisionResponseToChannel(ECC_WorldDynamic, ECR_Block);
    DisplayMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("WeaponMesh"));
    DisplayMesh->SetupAttachment(Collision);
    DisplayMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    DisplayMesh->SetRelativeRotation(FRotator(0.f, -90.f, 0.f));
}

void ABaselineWeaponPickup::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ThisClass, ItemDefinition);
    DOREPLIFETIME(ThisClass, SavedStats);
    DOREPLIFETIME(ThisClass, bHasSavedStats);
}

void ABaselineWeaponPickup::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    OnRep_Definition();
}

void ABaselineWeaponPickup::BeginPlay()
{
    Super::BeginPlay();
    OnRep_Definition();
}

void ABaselineWeaponPickup::OnRep_Definition()
{
    if (ItemDefinition)
        if (const auto* Icon = Cast<UInventoryFragment_PickupIcon>(GetDefault<ULyraInventoryItemDefinition>(ItemDefinition)->FindFragmentByClass(UInventoryFragment_PickupIcon::StaticClass())))
            DisplayMesh->SetSkeletalMesh(Icon->SkeletalMesh);
}

FText ABaselineWeaponPickup::GetItemName() const
{
    return ItemDefinition ? GetDefault<ULyraInventoryItemDefinition>(ItemDefinition)->DisplayName : FText::GetEmpty();
}

void ABaselineWeaponPickup::CaptureItem(const ULyraInventoryItemInstance* Item)
{
    check(HasAuthority() && Item);
    ItemDefinition = Item->GetItemDef();
    bHasSavedStats = true;
    SavedStats.Reset();
    for (const auto& Pair : Item->GetStatTagStacks())
    {
        FBaselineItemStat& Stat = SavedStats.AddDefaulted_GetRef();
        Stat.Tag = Pair.Key;
        Stat.Count = Pair.Value;
    }
    OnRep_Definition();
}

void ABaselineWeaponPickup::RestoreItem(ULyraInventoryItemInstance* Item) const
{
    if (!bHasSavedStats || !Item || !HasAuthority()) return;
    // Clear definition defaults first, including ammo which reached zero before dropping.
    const TMap<FGameplayTag, int32> Initial = Item->GetStatTagStacks();
    for (const auto& Pair : Initial) Item->RemoveStatTagStack(Pair.Key, Pair.Value);
    for (const FBaselineItemStat& Stat : SavedStats) Item->AddStatTagStack(Stat.Tag, Stat.Count);
}

void ABaselineWeaponPickup::LaunchDrop(const FVector& Velocity)
{
    if (!HasAuthority()) return;
    Collision->SetSimulatePhysics(true);
    Collision->SetPhysicsLinearVelocity(Velocity);
    Collision->SetLinearDamping(0.6f);
    Collision->SetAngularDamping(1.5f);
    ForceNetUpdate();
}

ABaselinePlayerController::ABaselinePlayerController(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    Inventory = CreateDefaultSubobject<ULyraInventoryManagerComponent>(TEXT("Inventory"));
    QuickBar = CreateDefaultSubobject<ULyraQuickBarComponent>(TEXT("QuickBar"));
    WeaponState = CreateDefaultSubobject<ULyraWeaponStateComponent>(TEXT("WeaponState"));
}

UBaselineEquipmentComponent::UBaselineEquipmentComponent()
{
    SetIsReplicatedByDefault(true);
    PrimaryComponentTick.bCanEverTick = true;
}

void UBaselineEquipmentComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME_CONDITION(ThisClass, ReplicatedAimRotation, COND_SkipOwner);
    DOREPLIFETIME_CONDITION(ThisClass, bWeaponReady, COND_SkipOwner);
    DOREPLIFETIME(ThisClass, bLeftShoulder);
}

void UBaselineEquipmentComponent::ToggleShoulder()
{
    if (AreHandsBusy() || IsChangingShoulder()) return;
    const bool bLeft = !bLeftShoulder;
    SetShoulder(bLeft);
    if (!GetOwner()->HasAuthority()) ServerSetShoulder(bLeft);
}

void UBaselineEquipmentComponent::SetShoulder(bool bLeft)
{
    if (bLeftShoulder == bLeft) return;
    bLeftShoulder = bLeft;
    OnRep_Shoulder();
    GetOwner()->ForceNetUpdate();
}

void UBaselineEquipmentComponent::OnRep_Shoulder()
{
    ShoulderAge = 0.f;
    if (auto* ASC = UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(GetOwner()))
    {
        ASC->SetLooseGameplayTagCount(TAG_Baseline_ChangingShoulder, 1);
        FGameplayTagContainer FireTags(FGameplayTag::RequestGameplayTag(TEXT("Ability.Type.Action.WeaponFire")));
        ASC->CancelAbilities(&FireTags);
    }
}

void UBaselineEquipmentComponent::ServerSetShoulder_Implementation(bool bLeft)
{
    if (!AreHandsBusy() && !IsChangingShoulder()) SetShoulder(bLeft);
    ClientConfirmShoulder(bLeftShoulder);
}

void UBaselineEquipmentComponent::ClientConfirmShoulder_Implementation(bool bLeft) { SetShoulder(bLeft); }

void UBaselineEquipmentComponent::HandleDeath()
{
    bAimRequested = bFireRequested = bWeaponReady = false;
    FireReadyUntil = 0.0;
    if (!GetOwner()->HasAuthority()) return;
    auto* QuickBar = GetQuickBar();
    auto* Inventory = GetInventory();
    if (!QuickBar || !Inventory) return;
    const auto Slots = QuickBar->GetSlots();
    for (int32 Index = 0; Index < Slots.Num(); ++Index)
    {
        auto* Item = Slots[Index];
        if (!Item) continue;
        const FTransform Transform(GetOwner()->GetActorRotation(), GetOwner()->GetActorLocation() + FVector(0,0,25));
        auto* Pickup = GetWorld()->SpawnActorDeferred<ABaselineWeaponPickup>(ABaselineWeaponPickup::StaticClass(),
            Transform, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn);
        if (Pickup)
        {
            Pickup->CaptureItem(Item);
            Pickup->FinishSpawning(Transform);
            const FVector Direction = FRotator(0, GetOwner()->GetActorRotation().Yaw + Index * 100.f, 0).Vector();
            Pickup->LaunchDrop(Direction * 100.f + FVector(0,0,80));
        }
        QuickBar->RemoveItemFromSlot(Index);
        Inventory->RemoveItemInstance(Item);
    }
}

void UBaselineEquipmentComponent::BeginAim() { SetWeaponInput(true, bFireRequested); }
void UBaselineEquipmentComponent::EndAim() { SetWeaponInput(false, bFireRequested); }
void UBaselineEquipmentComponent::BeginFire() { SetWeaponInput(bAimRequested, true); }
void UBaselineEquipmentComponent::EndFire() { SetWeaponInput(bAimRequested, false); }

void UBaselineEquipmentComponent::SetWeaponInput(bool bAim, bool bFire)
{
    if (const auto* Health = ULyraHealthComponent::FindHealthComponent(GetOwner()))
        if (Health->IsDeadOrDying()) bAim = bFire = false;
    if (bFireRequested && !bFire) FireReadyUntil = GetWorld()->GetTimeSeconds() + .65;
    bAimRequested = bAim;
    bFireRequested = bFire;
    if (!GetOwner()->HasAuthority()) ServerSetWeaponInput(bAim, bFire);
}

void UBaselineEquipmentComponent::ServerSetWeaponInput_Implementation(bool bAim, bool bFire)
{
    SetWeaponInput(bAim, bFire);
}

FRotator UBaselineEquipmentComponent::GetWeaponAimRotation() const
{
    const APawn* Pawn = Cast<APawn>(GetOwner());
    // Pawn's standard remote view only carries pitch. Slides can aim sideways
    // while the capsule keeps facing its velocity, so observers also need yaw.
    return Pawn && (Pawn->IsLocallyControlled() || Pawn->HasAuthority())
        ? Pawn->GetBaseAimRotation() : ReplicatedAimRotation;
}

ULyraQuickBarComponent* UBaselineEquipmentComponent::GetQuickBar() const
{
    const auto* Pawn=Cast<APawn>(GetOwner());
    const auto* Controller=Pawn ? Pawn->GetController() : nullptr;
    return Controller ? Controller->FindComponentByClass<ULyraQuickBarComponent>() : nullptr;
}

ULyraInventoryManagerComponent* UBaselineEquipmentComponent::GetInventory() const
{
    const auto* Pawn=Cast<APawn>(GetOwner());
    const auto* Controller=Pawn ? Pawn->GetController() : nullptr;
    return Controller ? Controller->FindComponentByClass<ULyraInventoryManagerComponent>() : nullptr;
}

USkeletalMeshComponent* UBaselineEquipmentComponent::GetPresentationMesh() const
{
    if (const auto* Character = Cast<ACRTraversalCharacter>(GetOwner()))
        if (AActor* Visual = Character->SelectedVisualOverride->GetChildActor())
        {
            TInlineComponentArray<USkeletalMeshComponent*> Meshes(Visual);
            for (USkeletalMeshComponent* Mesh : Meshes)
                // Modular characters also have face, hair and clothing meshes.
                // Select their animated full body, never the first component.
                if (Mesh->GetAnimClass() && Mesh->GetBoneIndex(TEXT("hand_r")) != INDEX_NONE
                    && Mesh->GetBoneIndex(TEXT("foot_l")) != INDEX_NONE) return Mesh;
        }
    return GetWeaponAnimationMesh();
}

USkeletalMeshComponent* UBaselineEquipmentComponent::GetWeaponAnimationMesh() const
{
    TInlineComponentArray<UChildActorComponent*> Children(GetOwner());
    for (UChildActorComponent* Child : Children)
        if (Child->ComponentHasTag(TEXT("BaselineAnimationSource")) && Child->GetChildActor())
            if (auto* Mesh = Child->GetChildActor()->FindComponentByClass<USkeletalMeshComponent>()) return Mesh;
    const ACharacter* Character = Cast<ACharacter>(GetOwner());
    return Character ? Character->GetMesh() : nullptr;
}

void UBaselineEquipmentComponent::RefreshVisualOverride()
{
    auto* Character = Cast<ACRTraversalCharacter>(GetOwner());
    auto* Driver = GetWeaponAnimationMesh();
    if (!Character || !Driver || Driver == Character->GetMesh()) return;
    if (PreparedAnimationMesh != Driver)
    {
        if (auto* Previous = PreparedAnimationMesh.Get()) RemoveTickPrerequisiteComponent(Previous);
        Driver->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
        Driver->AddTickPrerequisiteComponent(Character->PhysicalInteraction);
        AddTickPrerequisiteComponent(Driver);
        Character->SelectedVisualOverride->AttachToComponent(Driver, FAttachmentTransformRules::SnapToTargetNotIncludingScale);
        PreparedAnimationMesh = Driver;
    }
    auto* Visual = GetPresentationMesh();
    Character->GetMesh()->SetVisibility(false, false);
    Driver->SetVisibility(Visual == Driver, false);
    if (PreparedVisual != Visual)
    {
        if (auto* Previous = PreparedVisual.Get()) RemoveTickPrerequisiteComponent(Previous);
        if (Visual != Driver)
        {
            Visual->AddTickPrerequisiteComponent(Driver);
            Visual->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
            if (Visual->GetSkeletalMeshAsset()->GetSkeleton() == Driver->GetSkeletalMeshAsset()->GetSkeleton())
                Visual->SetLeaderPoseComponent(Driver);
            else if (VisualRetargetAnimation) Visual->SetAnimInstanceClass(VisualRetargetAnimation);
        }
        // Grip conversion reads both poses. They must be from the same frame,
        // especially on clients with independent retargeted hand orientations.
        AddTickPrerequisiteComponent(Driver);
        AddTickPrerequisiteComponent(Visual);
        PreparedVisual = Visual;
    }
}

bool UBaselineEquipmentComponent::CanReachPickup(const ABaselineWeaponPickup* Pickup) const
{
    const APawn* Pawn = Cast<APawn>(GetOwner());
    if (!IsValid(Pickup) || Pickup->bClaimed || !Pawn || !Pickup->ItemDefinition
        || FVector::DistSquared(Pawn->GetActorLocation(), Pickup->GetActorLocation()) > FMath::Square(PickupDistance)) return false;
    const FVector Start = Pawn->GetPawnViewLocation();
    FCollisionQueryParams Params(SCENE_QUERY_STAT(BaselinePickup), false, Pawn);
    Params.AddIgnoredActor(Pickup);
    FHitResult Hit;
    return !GetWorld()->LineTraceSingleByChannel(Hit, Start, Pickup->GetActorLocation(), ECC_Visibility, Params);
}

ABaselineWeaponPickup* UBaselineEquipmentComponent::FindPickup() const
{
    const APawn* Pawn = Cast<APawn>(GetOwner());
    if (!Pawn || AreHandsBusy()) return nullptr;
    const FVector Forward = Pawn->GetControlRotation().Vector().GetSafeNormal2D();
    ABaselineWeaponPickup* Best = nullptr;
    float BestScore = UE_BIG_NUMBER;
    for (TActorIterator<ABaselineWeaponPickup> It(GetWorld()); It; ++It)
    {
        if (!CanReachPickup(*It)) continue;
        const FVector Delta = It->GetActorLocation() - Pawn->GetActorLocation();
        const float Dot = FVector::DotProduct(Forward, Delta.GetSafeNormal2D());
        if (Dot < 0.1f) continue;
        const float Score = Delta.Size() + (1.f - Dot) * 150.f;
        if (Score < BestScore) { Best = *It; BestScore = Score; }
    }
    return Best;
}

void UBaselineEquipmentComponent::Interact()
{
    if (ABaselineWeaponPickup* Pickup = FindPickup()) ServerPickup(Pickup);
}

void UBaselineEquipmentComponent::ServerPickup_Implementation(ABaselineWeaponPickup* Pickup)
{
    auto* QuickBar = GetQuickBar();
    auto* Inventory = GetInventory();
    if (!QuickBar || !Inventory || !CanReachPickup(Pickup) || AreHandsBusy()) return;
    const int32 Slot = QuickBar->GetNextFreeItemSlot();
    if (Slot == INDEX_NONE) { LastInteractionResult = TEXT("Inventory full - drop a weapon first"); return; }
    auto* ASC = Cast<ULyraAbilitySystemComponent>(UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(GetOwner()));
    if (!ASC || !ASC->GetAvatarActor()) return;
    const auto* Definition = GetDefault<ULyraInventoryItemDefinition>(Pickup->ItemDefinition);
    if (!Definition->FindFragmentByClass(UInventoryFragment_EquippableItem::StaticClass())) return;
    Pickup->bClaimed = true;
    ULyraInventoryItemInstance* Item = Inventory->AddItemDefinition(Pickup->ItemDefinition, 1);
    if (!Item) { Pickup->bClaimed = false; return; }
    Pickup->RestoreItem(Item);
    QuickBar->AddItemToSlot(Slot, Item);
    QuickBar->SetActiveSlotIndex(Slot);
    LastInteractionResult = TEXT("Picked up ") + Pickup->GetItemName().ToString();
    Pickup->Destroy();
}

ULyraInventoryItemInstance* UBaselineEquipmentComponent::GetActiveItem() const
{
    const auto* QuickBar = GetQuickBar();
    return QuickBar ? QuickBar->GetActiveSlotItem() : nullptr;
}

void UBaselineEquipmentComponent::DropActiveWeapon_Implementation()
{
    auto* QuickBar = GetQuickBar();
    auto* Inventory = GetInventory();
    auto* Pawn = Cast<APawn>(GetOwner());
    ULyraInventoryItemInstance* Item = GetActiveItem();
    if (!QuickBar || !Inventory || !Pawn || !Item || AreHandsBusy()) return;
    const FVector Forward = Pawn->GetBaseAimRotation().Vector().GetSafeNormal2D();
    const FVector Start = GetOwner()->GetActorLocation() + FVector(0, 0, 25);
    FVector Location = Start + Forward * 105.f;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(BaselineDrop), false, GetOwner());
    FHitResult Hit;
    if (GetWorld()->SweepSingleByChannel(Hit, Start, Location, FQuat::Identity, ECC_WorldStatic,
        FCollisionShape::MakeSphere(45.f), Params)) Location = Hit.Location;
    FTransform Transform(Forward.Rotation(), Location);
    auto* Pickup = GetWorld()->SpawnActorDeferred<ABaselineWeaponPickup>(ABaselineWeaponPickup::StaticClass(),
        Transform, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButDontSpawnIfColliding);
    if (!Pickup) { LastInteractionResult = TEXT("No room to drop weapon"); return; }
    Pickup->CaptureItem(Item);
    Pickup->FinishSpawning(Transform);
    if (Pickup->IsActorBeingDestroyed()) return;
    const FString ItemName = Pickup->GetItemName().ToString();
    QuickBar->RemoveItemFromSlot(QuickBar->GetActiveSlotIndex());
    Inventory->RemoveItemInstance(Item);
    QuickBar->CycleActiveSlotForward();
    Pickup->LaunchDrop(GetOwner()->GetVelocity() + Forward * 120.f + FVector(0, 0, 80.f));
    LastInteractionResult = TEXT("Dropped ") + ItemName;
}

void UBaselineEquipmentComponent::CycleWeapon()
{
    if (auto* QuickBar = GetQuickBar())
        if (!AreHandsBusy()) QuickBar->CycleActiveSlotForward();
}

bool UBaselineEquipmentComponent::AreHandsBusy() const
{
    const ACharacter* Character = Cast<ACharacter>(GetOwner());
    if (!Character) return false;
    if (const auto* Health = ULyraHealthComponent::FindHealthComponent(Character))
        if (Health->IsDeadOrDying()) return true;
    if (const auto* Physical = Character->FindComponentByClass<UBaselinePhysicalInteractionComponent>())
        if (Physical->IsBusy()) return true;
    const auto* SourceAnim = Character->GetMesh()->GetAnimInstance();
    const UAnimMontage* Montage = SourceAnim ? SourceAnim->GetCurrentActiveMontage() : nullptr;
    const auto* TraversalCharacter = Cast<ACRTraversalCharacter>(Character);
    // Sliding keeps both hands available for the weapon. Other source montages
    // (vaults, mantles, climbs and smart-object actions) put it away completely.
    return Montage && (!TraversalCharacter || !TraversalCharacter->IsSlideMontage(Montage));
}

void UBaselineEquipmentComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
    ShoulderAge += DeltaTime;
    HandTransferAge += DeltaTime;
    RefreshVisualOverride();
    auto* Character = Cast<ACharacter>(GetOwner());
    auto* Manager = GetOwner()->FindComponentByClass<ULyraEquipmentManagerComponent>();
    USkeletalMeshComponent* Mesh = GetPresentationMesh();
    USkeletalMeshComponent* AnimationMesh = GetWeaponAnimationMesh();
    if (!Character || !Manager || !Mesh || !AnimationMesh) return;
    if (Character->HasAuthority()) ReplicatedAimRotation = Character->GetBaseAimRotation();
    const bool bBusy = AreHandsBusy();
    if (Character->HasAuthority() || Character->IsLocallyControlled())
        bWeaponReady = !bBusy && Manager->GetFirstInstanceOfType<UBaselineWeaponInstance>()
            && (bAimRequested || bFireRequested || GetWorld()->GetTimeSeconds() < FireReadyUntil);
    // Feed the same stance to GASP on owners and simulated proxies. Its existing
    // motion-matched turn-in-place poses then move the feet during aim or fire.
    if (auto* TraversalCharacter = Cast<ACRTraversalCharacter>(Character))
        TraversalCharacter->SetWeaponReadyForAnimation(bWeaponReady);
    if (auto* ASC = Cast<ULyraAbilitySystemComponent>(UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(GetOwner())))
        {
            // Weapon GAS montages belong on Manny. GASP traversal montages still run
            // directly on its source mesh and are copied through the retarget graph.
            if (ASC->AbilityActorInfo.IsValid()) ASC->AbilityActorInfo->SkeletalMeshComponent = AnimationMesh;
            ASC->SetLooseGameplayTagCount(TAG_Baseline_ChangingShoulder, IsChangingShoulder() ? 1 : 0);
            // The PlayerState ASC survives death. Publish the new pawn's state
            // even when it starts idle, clearing the dead avatar's loose tag.
            ASC->SetLooseGameplayTagCount(TAG_Baseline_HandsBusy, bBusy ? 1 : 0);
            if (bBusy != bWasHandsBusy)
            {
                if (bBusy)
                {
                    FGameplayTagContainer Tags;
                    Tags.AddTag(FGameplayTag::RequestGameplayTag(TEXT("Ability.Type.Action.WeaponFire")));
                    Tags.AddTag(FGameplayTag::RequestGameplayTag(TEXT("Ability.Type.Action.Reload"), false));
                    ASC->CancelAbilities(&Tags);
                }
            }
        }
    if (auto* Weapon = Manager->GetFirstInstanceOfType<UBaselineWeaponInstance>())
    {
        Weapon->Tick(DeltaTime);
        if (bWasHandsBusy && !bBusy && Weapon->WeaponEquipMontage)
            if (UAnimInstance* Anim = AnimationMesh->GetAnimInstance()) Anim->Montage_Play(Weapon->WeaponEquipMontage);
        for (AActor* Actor : Weapon->GetSpawnedActors())
        {
            if (!Actor) continue;
            Actor->SetActorHiddenInGame(bBusy);
            FName Socket(bLeftShoulder ? TEXT("weapon_l") : TEXT("weapon_r"));
            FTransform Grip(FRotator(0, bLeftShoulder ? 90.f : -90.f, 0));
            // Mirrored wrist axes reverse both forward and up. Yaw fixes the
            // barrel direction; rotate around the weapon's local +Y barrel too
            // so the sights stay above the grip in the left hand.
            if (bLeftShoulder)
                Grip.SetRotation(Grip.GetRotation() * FQuat(FVector::YAxisVector, PI));
            if (Mesh->GetSkeletalMeshAsset()->GetSkeleton() != AnimationMesh->GetSkeletalMeshAsset()->GetSkeleton())
            {
                // Retargeted rigs have different wrist/socket axes. Keep the
                // authored gun orientation and grip offset at the visible hand.
                const FName Hand(bLeftShoulder ? TEXT("hand_l") : TEXT("hand_r"));
                const FTransform SourceHand = AnimationMesh->GetSocketTransform(Hand);
                const FTransform TargetHand = Mesh->GetSocketTransform(Hand);
                FTransform WorldGrip = Grip * AnimationMesh->GetSocketTransform(Socket);
                WorldGrip.AddToTranslation(TargetHand.GetLocation() - SourceHand.GetLocation());
                Grip = WorldGrip.GetRelativeTransform(TargetHand);
                Socket = Hand;
            }
            else if (!Mesh->DoesSocketExist(Socket))
            {
                const FName Hand(bLeftShoulder ? TEXT("hand_l") : TEXT("hand_r"));
                Grip *= AnimationMesh->GetSocketTransform(Socket).GetRelativeTransform(AnimationMesh->GetSocketTransform(Hand));
                Socket = Hand;
            }
            if (Actor->GetRootComponent()->GetAttachParent() != Mesh || Actor->GetRootComponent()->GetAttachSocketName() != Socket)
            {
                const bool bTransfer = Actor->GetRootComponent()->GetAttachParent() == Mesh;
                Actor->AttachToComponent(Mesh, FAttachmentTransformRules::KeepWorldTransform, Socket);
                HandTransferOffset = Actor->GetRootComponent()->GetRelativeTransform();
                TransferringWeapon = Actor;
                HandTransferAge = bTransfer ? 0.f : .35f;
            }
            if (TransferringWeapon == Actor && HandTransferAge < .35f)
            {
                FTransform Transfer;
                Transfer.Blend(HandTransferOffset, Grip, FMath::Clamp(HandTransferAge / .35f, 0.f, 1.f));
                Actor->SetActorRelativeTransform(Transfer);
            }
            else Actor->SetActorRelativeTransform(Grip);
        }
    }
    bWasHandsBusy = bBusy;
}

void UBaselineEquipmentComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    if (auto* ASC = UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(GetOwner()))
    {
        ASC->SetLooseGameplayTagCount(TAG_Baseline_HandsBusy, 0);
        ASC->SetLooseGameplayTagCount(TAG_Baseline_ChangingShoulder, 0);
    }
    Super::EndPlay(Reason);
}

void UBaselineWeaponInstance::OnEquipped()
{
    Super::OnEquipped();
    if (APawn* Pawn = GetPawn())
        if (auto* Equipment = Pawn->FindComponentByClass<UBaselineEquipmentComponent>())
            if (USkeletalMeshComponent* Mesh = Equipment->GetWeaponAnimationMesh())
                if (auto* Anim = Mesh->GetAnimInstance())
                    if (WeaponEquipMontage) Anim->Montage_Play(WeaponEquipMontage);
}

void UBaselineAnimInstance::NativeUpdateAnimation(float DeltaSeconds)
{
    Super::NativeUpdateAnimation(DeltaSeconds);
    AActor* Actor = GetOwningActor();
    APawn* Pawn = Cast<APawn>(Actor);
    if (!Pawn && Actor) Pawn = Cast<APawn>(Actor->GetParentActor());
    if (!Pawn) return;
    auto* Equipment = Pawn->FindComponentByClass<UBaselineEquipmentComponent>();
    auto* Manager = Pawn->FindComponentByClass<ULyraEquipmentManagerComponent>();
    auto* Weapon = Manager ? Manager->GetFirstInstanceOfType<UBaselineWeaponInstance>() : nullptr;
    if (Weapon && Weapon->HoldAnimation) WeaponPose = Weapon->HoldAnimation;
    if (Weapon && Weapon->CarryAnimation) WeaponCarryPose = Weapon->CarryAnimation;
    if (Weapon && Weapon->AimOffset) WeaponAimOffset = Weapon->AimOffset;
    // GASP's animated root can face away from the capsule while its feet turn.
    // Align the overlay with that root and apply only a bounded torso offset.
    const auto* Character = Cast<ACharacter>(Pawn);
    const float RootYaw = Character ? Character->GetMesh()->GetSocketTransform(TEXT("root"), RTS_Component).Rotator().Yaw : 0.f;
    WeaponRootRotation = FRotator(0.f, RootYaw, 0.f);
    const FRotator Aim = ((Equipment ? Equipment->GetWeaponAimRotation() : Pawn->GetBaseAimRotation())
        - FRotator(0.f, Pawn->GetActorRotation().Yaw + RootYaw, 0.f)).GetNormalized();
    const bool bReady = Weapon && Equipment && Equipment->IsWeaponReady();
    bWeaponLeftHand = Equipment && Equipment->IsLeftShoulder();
    // Aim transitions blend into the full weapon pose. Fire raises promptly;
    // relaxed carry uses its own arm animation and leaves the head/spine to GASP.
    WeaponReadyWeight = bReady && Equipment->IsFireRequested() ? 1.f
        : FMath::FInterpTo(WeaponReadyWeight, bReady ? 1.f : 0.f, DeltaSeconds, bReady ? 18.f : 10.f);
    const auto* Movement = Pawn->FindComponentByClass<UBaselineCharacterMovement>();
    const float MaxYaw = Movement && Movement->IsSliding() ? 85.f : 65.f;
    AimYaw = FMath::Clamp(Aim.Yaw, -MaxYaw, MaxYaw) * WeaponReadyWeight * (bWeaponLeftHand ? -1.f : 1.f);
    AimPitch = FMath::Clamp(Aim.Pitch, -90.f, 90.f) * WeaponReadyWeight;
    const bool bHandsBusy = Equipment && Equipment->AreHandsBusy();
    WeaponPoseWeight = bHandsBusy ? 0.f : FMath::FInterpTo(WeaponPoseWeight,
        Weapon && Equipment ? 1.f : 0.f, DeltaSeconds, 12.f);
    // Equip and reload still use the full upper body even when aim is released.
    const float MontageWeight = FMath::Max(GetSlotMontageLocalWeight(TEXT("UpperBody")),
        GetSlotMontageLocalWeight(TEXT("FullBodyAdditivePreAim")));
    WeaponUpperBodyWeight = WeaponPoseWeight * FMath::Max(WeaponReadyWeight, MontageWeight);
}

void ABaselineHUD::DrawHUD()
{
    Super::DrawHUD();
    if (!Canvas || !PlayerOwner || !PlayerOwner->GetPawn()) return;
    const auto* Equipment = PlayerOwner->GetPawn()->FindComponentByClass<UBaselineEquipmentComponent>();
    if (!Equipment) return;
    const float W = Canvas->SizeX, H = Canvas->SizeY;
    if (const auto* Health = ULyraHealthComponent::FindHealthComponent(PlayerOwner->GetPawn()))
    {
        DrawText(FString::Printf(TEXT("Health %d / %d"), FMath::CeilToInt(Health->GetHealth()), FMath::CeilToInt(Health->GetMaxHealth())),
            FLinearColor::White, 24, 78);
        if (Health->IsDeadOrDying())
        {
            DrawText(TEXT("YOU DIED - Respawning..."), FLinearColor(1.f,.3f,.25f), W*.5f-150, H*.5f, nullptr, 1.6f);
            return;
        }
    }
    DrawText(TEXT("MOVEMENT + EQUIPMENT BASELINE"), FLinearColor(0.5f, 0.8f, 1.f), 24, 24);
    DrawText(TEXT("WASD Move   Shift Sprint   C Crouch / Slide   Space Jump / Traverse"), FLinearColor::White, 24, H - 76);
    DrawText(TEXT("E Pick up   G Drop   Tab Switch   Q Shoulder / Hand   LMB Fire   RMB Aim   R Reload"), FLinearColor::White, 24, H - 54);
    DrawText(TEXT("F Shove   V Tackle   B Takedown   T Ragdoll / Get up"), FLinearColor::White, 24, H - 32);
    if (const auto* Physical = PlayerOwner->GetPawn()->FindComponentByClass<UBaselinePhysicalInteractionComponent>())
    {
        if (Physical->GetPhase() == EBaselinePhysicalPhase::Ragdoll)
            DrawText(TEXT("[T / Space] Get up when settled"), FLinearColor(0.3f, 1.f, .65f), W*.5f-105, H*.67f);
        else if (Physical->FindInteractionTarget())
            DrawText(TEXT("[F] Shove   [V] Tackle   [B] Takedown"), FLinearColor(0.3f, 1.f, .65f), W*.5f-125, H*.73f);
    }
    if (ABaselineWeaponPickup* Pickup = Equipment->FindPickup())
        DrawText(TEXT("[E] Pick up ") + Pickup->GetItemName().ToString(), FLinearColor(0.3f, 1.f, 0.65f), W * .5f - 80, H * .67f, nullptr, 1.3f);
    if (ULyraInventoryItemInstance* Item = Equipment->GetActiveItem())
    {
        const FString Name = GetDefault<ULyraInventoryItemDefinition>(Item->GetItemDef())->DisplayName.ToString();
        DrawText(FString::Printf(TEXT("%s   %d / %d"), *Name, Item->GetStatTagStackCount(MagazineTag()), Item->GetStatTagStackCount(SpareTag())),
            FLinearColor::White, 24, H - 110, nullptr, 1.3f);
        if (!Equipment->AreHandsBusy())
        {
            DrawLine(W*.5f - 9, H*.5f, W*.5f - 3, H*.5f, FLinearColor::White);
            DrawLine(W*.5f + 3, H*.5f, W*.5f + 9, H*.5f, FLinearColor::White);
            DrawLine(W*.5f, H*.5f - 9, W*.5f, H*.5f - 3, FLinearColor::White);
            DrawLine(W*.5f, H*.5f + 3, W*.5f, H*.5f + 9, FLinearColor::White);
        }
    }
    if (const auto* Movement = PlayerOwner->GetPawn()->FindComponentByClass<UBaselineCharacterMovement>())
        if (Movement->IsSliding()) DrawText(TEXT("SLIDING"), FLinearColor(0.3f, 1.f, 0.65f), 24, 50);
}
