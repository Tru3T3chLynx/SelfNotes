from pathlib import Path
from inventory.items import Items
from inventory.inventory import Inventory
from player.player import Player
from storage.storage import Storage

# Dictionary of sections
MODES = {
    "inventory" : 0
}
# Choose what section to run
state = MODES["inventory"]

def runInventory():
    root = Path(__file__).parent
    items_path = root / "inventory" / "items.json"
    items = Items.load(items_path)
    inv = Inventory(capacity=8, items=items)

    player = Player(name = "Player", items = items, inv_capacity = 8)
    chest = Storage(items = items, capacity = 8, name = "Chest")

    test = 5
    match test:
        case 0:
            print("\n=== Seed exact test state with setSlot ===")
            inv.setSlot(0, "wood", 95)      # nearly full wood
            inv.setSlot(1, "wood", 20)      # partial wood
            inv.setSlot(2, "apple", 5)      # small apple stack
            inv.setSlot(4, "iron_sword", 1) # non-stackable weapon
            print(inv)

            # ---- MOVE: merge same item into dst up to max stack ----
            print("\n=== move(1 -> 0): merge wood into slot 0 up to 99 ===")
            inv.move(1, 0)     # expect slot 0: 99, slot 1: 16
            print(inv)

            # ---- SPLIT: empty only split ----
            print("\n=== split(1 -> 3, amount=8): split wood into empty slot 3 ===")
            t = inv.split(1, 3, 8) # expect slot 1: 8, slot 3: 8
            print("split success?", t)
            print(inv)

            print("\n=== split(2 -> 0, amount=2) should FAIL (dst not empty) ===")
            t = inv.split(2, 0, 2) # expect False; inventory unchanged
            print("split success?", t)
            print(inv)

            # ---- SPLIT HALF: empty only ----
            print("\n=== splitHalf(0 -> 6): take half of slot 0 into empty slot 6 ===")
            t = inv.splitHalf(0, 6) # with 99 in slot 0, moves 49 to slot 6
            print("splitHalf success?", t)
            print(inv)

            # ---- MOVE: swap different items ----
            print("\n=== move(4 -> 0): swap sword with (likely) wood (since slot 0 is full) ===")
            t = inv.move(4, 0)
            print("swap success?", t)
            print(inv)

            # ---- COUNT + REMOVE (right -> left) ----
            print("\n=== count('wood') then remove 10 (consume rightmost wood first) ===")
            before = inv.count("wood")
            removed = inv.remove("wood", 10)
            after = inv.count("wood")
            print(f"wood before = {before}, removed = {removed}, after = {after}")
            print(inv)

            # ---- ADD: stacking across existing stacks and empties ----
            print("\n=== add('wood', 25): top up existing stacks, then use empty slots if needed ===")
            added = inv.add("wood", 25)
            print("added: ", added)
            print(inv)

            # ---- SORT: merge and sort inventory
            inv.sort()
            print("\n", inv, "\n")

            # quick non fatal checks
            def expect(name, cond):
                print(f"[{'PASS' if cond else 'FAIL'}] {name}")

            expect("splitHalf placed something at slot 6",
                inv.slots[6] is None or inv.slots[6].item_id in ("wood", "apple"))
            expect("remove decreased wood count by 10", before - after == 10)
        case 1:
            # one sword and some wood
            inv.setSlot(0, "iron_sword", 1)
            inv.setSlot(1, "wood", 50)
            inv.add("wood", 60)
            print(inv)

            # show sword durability
            iid = inv.slots[0].iid
            print("start:", items.getDurability(iid))
            items.loseDurability(iid, 0.05)
            print("after:", items.getDurability(iid))
            print("ratio:", f"{items.durabilityRatio(iid):.2%}")
            items.setDurability(iid, 250.0)
            print("set 250:", items.getDurability(iid))
            items.setDurability(iid, -10.0)
            print("set -10:", items.getDurability(iid))
        case 2:
            # figure out the items max durability
            max_dur = items.defs["iron_sword"].max_durability or 100.0
            d95 = max_dur * 0.95
            d50 = max_dur * 0.50

            # slot 1 sword @95%, slot 2 sword @50%
            inv.setSlot(0, "iron_sword", 1, current_durability=d95)
            inv.setSlot(1, "iron_sword", 1, current_durability=d50)

            print("BEFORE SWAP:", inv)
            iid1_before = inv.slots[0].iid
            iid2_before = inv.slots[1].iid
            dur1_before = items.getDurability(iid1_before)
            dur2_before = items.getDurability(iid2_before)
            print(f" slot1 iid={iid1_before}, dur={dur1_before}")
            print(f" slot2 iid={iid2_before}, dur={dur2_before}")

            # perform swap
            t = inv.move(0, 1)
            print("swap ok?", t)
            print("AFTER SWAP:", inv)

            # durability should have moved with the stacks
            iid1_after = inv.slots[0].iid
            iid2_after = inv.slots[1].iid
            dur1_after = items.getDurability(iid1_after)
            dur2_after = items.getDurability(iid2_after)
            print(f" slot1 iid={iid1_after}, dur={dur1_after}")
            print(f" slot2 iid={iid2_after}, dur={dur2_after}")
        case 3:
            # place Cloth Armor with default durability
            inv.setSlot(0, "cloth_armor", 1)
            # place another Cloth Armor at 50% durability
            max_dur = items.defs["cloth_armor"].max_durability or 60.0
            inv.setSlot(1, "cloth_armor", 1, current_durability=max_dur * 0.50)

            print(inv)
            print(inv.describeSlot(0))
            print(inv.describeSlot(1))
            # wear down slot 0 a bit
            items.loseDurability(inv.slots[0].iid, 0.5)
            print("after small wear:")
            print(inv.describeSlot(0))
        case 4:
            # basic pickup
            player.addInv("wood", 50)
            player.addInv("apple", 3)
            player.showInventory()

            # add weapon
            player.addInv("iron_sword", 1)
            player.showInventory(detailed = True)

            # rearrange a bit
            player.moveInv(0, 3)
            player.showInventory(detailed = True)
            player.splitInv(1, 5, 2)
            player.showInventory(detailed = True)
            player.sortInv()
            player.showInventory(detailed = True)
            player.splitHalfInv(2, 7)
            player.showInventory(detailed = True)
        case 5:
            # check different inventory types
            player.addInv("wood", 50)
            player.addInv("apple", 3)
            player.showInventory()

            sword_max = items.defs["iron_sword"].max_durability or 100.0
            d80 = sword_max * 0.80
            d45 = sword_max * 0.45

            chest.setSlot(1, "iron_sword", 1, current_durability = d80)
            chest.setSlot(2, "iron_sword", 1, current_durability = d45)

            chest.addInv("wood", 150)
            chest.addInv("apple", 10)
            chest.showInventory()

            # armor one fully durable, one 50%
            armor_max = items.defs["cloth_armor"].max_durability or 60.0
            chest.setSlot(5, "cloth_armor", 1)
            chest.setSlot(6, "cloth_armor", 1, current_durability = armor_max * 0.50)

            print("\n=== Before ===")
            chest.showInventory(detailed = True)

            # verify sword durabilities before swap
            iid1_before = chest.inv.slots[1].iid
            iid2_before = chest.inv.slots[2].iid
            dur1_before = items.getDurability(iid1_before)
            dur2_before = items.getDurability(iid2_before)
            print(f"\nslot1 sword dur(before): {dur1_before}")
            print(f"\nslot2 sword dur(before): {dur2_before}")

            # swap
            t = chest.moveInv(1, 2)
            print("\nswap swords ok?", t)

            iid1_after = chest.inv.slots[1].iid
            iid2_after = chest.inv.slots[2].iid
            dur1_after = items.getDurability(iid1_after)
            dur2_after = items.getDurability(iid2_after)
            print(f"slot1 sword dur(after): {dur1_after}")
            print(f"slot2 sword dur(after): {dur2_after}")

            # wear down armor in slot 5 by a small amount
            items.loseDurability(chest.inv.slots[5].iid, 0.5)
            print("\nafter slight armor wear on slot 5:")
            if hasattr(chest.inv, "describeSlot"):
                print(chest.inv.describeSlot(5))
            else:
                print("slot5 armor dur:", items.getDurability(chest.inv.slots[5].iid))

            # --- remove some wood, then sort ---
            print(f"wood: {chest.count("wood")}")
            removed = chest.removeInv("wood", 60)
            print(f"\nremoved wood: {removed}")
            print(f"wood: {chest.count("wood")}")
            chest.sortInv()

            print("\n=== AFTER SORT ===")
            chest.showInventory(detailed = True)

if __name__ == "__main__":
    if state == MODES["inventory"]:
        runInventory()