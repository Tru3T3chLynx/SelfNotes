from dataclasses import dataclass
from typing import Optional, Dict, List
from .items import ItemDef, Items

@dataclass
class ItemStack:
    item_id : str
    qty : int
    iid : Optional[str] = None

class Inventory:
    def __init__(self, capacity : int, items : Items) -> None:
        self.capacity = capacity
        self.slots : List[Optional[ItemStack]] = [None] * capacity
        self.items = items
        self.item_defs = items.defs

    def add(self, item_id : str, qty : int) -> int:
        """
        Try to add qty of an item.
        Returns how many were successfully added.
        """
        if item_id not in self.item_defs:
            print(f"Unkown item: {item_id}")
            return 0
        
        max_stack = self.item_defs[item_id].stack_size
        to_add = qty

        # Fill existing stacks first
        if max_stack > 1:
            for slot in self.slots:
                if slot and self._canStack(slot, ItemStack(item_id, 1, None)):
                    space = max_stack - slot.qty
                    take = min(space, to_add)
                    slot.qty += take
                    to_add -= take
                    if to_add == 0:
                        return qty
                
        # Put leftover items in empty slots
        for i in range(self.capacity):
            if self.slots[i] is None:
                if max_stack > 1:
                    place = min(max_stack, to_add)
                    iid = None
                else:
                    place = 1
                    iid = self.items.newInstance(item_id)
                self.slots[i] = ItemStack(item_id, place, iid)
                to_add -= place
                if to_add == 0:
                    return qty
                
        return qty - to_add
    
    def remove(self, item_id : str, qty : int) -> int:
        """
        Try to remove up to 'qty' of 'item_id'.
        Returns how many were actually removed.
        """
        if qty <= 0:
            return 0
        
        to_remove = qty

        # Remove from stacks right to left
        for i in range(self.capacity - 1, -1, -1):
                s = self.slots[i]
                if s and s.item_id == item_id:
                    take = min(s.qty, to_remove)
                    s.qty -= take
                    to_remove -= take

                    # Clear empty stacks
                    if s.qty == 0:
                        self.items.destroyInstance(s.iid)
                        self.slots[i] = None

                    if to_remove == 0:
                        break

        return qty - to_remove
    
    def move(self, src : int, dst : int) -> bool:
        """
        Move/merge between slots.
        - If dst empty: move src -> dst.
        - If same item and dst has space: merge into dst.
        - Else: swap.
        Returns True if any change happened.
        """
        if not (0 <= src < self.capacity and 0 <= dst < self.capacity):
            return False
        if src == dst:
            return False
        
        source = self.slots[src]
        destination = self.slots[dst]

        # nothing to move
        if source is None and destination is None:
            return False
        
        # move into empty
        if source is not None and destination is None:
            self.slots[dst], self.slots[src] = source, None
            return True

        # empty src but dst has item, make it intuitive: swap so item ends up at src
        if source is None and destination is not None:
            self.slots[src], self.slots[dst] = destination, None
            return True
        
        # both occupied
        assert source is not None and destination is not None
        if self._canStack(source, destination):
            max_stack = self._maxStack(source.item_id)
            space = max_stack - destination.qty
            if space > 0:
                moved = min(space, source.qty)
                destination.qty += moved
                source.qty -= moved
                if source.qty == 0:
                    self.items.destroyInstance(source.iid)
                    self.slots[src] = None
                return moved > 0
            # no space: swap them
            self.slots[src], self.slots[dst] = destination, source
            return True
        
        # different items: swap stacks
        self.slots[src], self.slots[dst] = destination, source
        return True
        
    def split(self, src : int, dst : int, amount : int) -> bool:
        """
        Move 'amount' items from src to dst, but ONLY if dst is empty.
        Caps the moved amount to the item's max stack size.
        """
        if amount <= 0:
            return False
        if not (0 <= src < self.capacity and 0 <= dst < self.capacity):
            return False
        if src == dst:
            return False
        
        source = self.slots[src]
        if source is None or source.qty < amount:
            return False
        
        max_stack = self._maxStack(source.item_id)

        # ensure no more than allowed or available is moved
        move_qty = min(amount, source.qty, max_stack)
        if move_qty <= 0:
            return False
        
        # destination must be empty
        if self.slots[dst] is not None:
            return False
        
        # create new stack in destination
        self.slots[dst] = ItemStack(source.item_id, move_qty, source.iid)
        source.qty -= move_qty
        if source.qty == 0:
            self.items.destroyInstance(s.iid)
            self.slots[src] = None

        return True
    
    def splitHalf(self, src : int, dst : int) -> bool:
        """Split half of src stack (round down) into dst."""
        if not (0 <= src < self.capacity and 0 <= dst < self.capacity):
            return False
        if src == dst:
            return False
        source = self.slots[src]
        if source is None or source.qty < 2:
            return False
        amount = source.qty // 2
        return self.split(src, dst, amount)
    
    def sort(self) -> None:
        """
        1) Merge like items respecting max stack and per-instance state (e.g., durability).
        2) Compact: pack items from the left (no gaps).
        3) Sort last: by item name, then item_id; within same item,
           full stacks come before the final partial stack.
        """
        from typing import Dict, List

        # Helper: is this stack allowed to merge?
        def isStackableInstance(s) -> bool:
            if s is None:
                return False
            max_stack = self._maxStack(s.item_id)
            # do not merge if max_stack <= 1 or if it has per-instance state like durability
            if max_stack <= 1:
                return False
            if s.iid is not None:
                return False
            return True
        
        # ------------- 1) MERGE -------------
        counts : Dict[str, int] = {}
        singles : List[ItemStack] = [] # non-mergeables

        for s in self.slots:
            if s is None:
                continue
            if isStackableInstance(s):
                counts[s.item_id] = counts.get(s.item_id, 0) + s.qty
            else:
                # copy so we do not mutate original while rebuilding
                singles.append(ItemStack(s.item_id, s.qty, s.iid))

        merged : List[ItemStack] = []
        for item_id, total in counts.items():
            max_stack = self._maxStack(item_id)
            full, rem = divmod(total, max_stack)
            # full stacks first
            for _ in range(full):
                merged.append(ItemStack(item_id, max_stack))
            # then one remainder (if any)
            if rem > 0:
                merged.append(ItemStack(item_id, rem))

        # ------------- 2) SORT -------------
        def nameOf(item_id : str) -> str:
            n = self.item_defs.get(item_id)
            return n.name if n else item_id
        
        def isFull(stack : ItemStack) -> bool:
            return stack.qty >= self._maxStack(stack.item_id)
        
        all_stacks : List[ItemStack] = singles + merged

        # Sort by: name, then "fullness", then item_id, then qty desc as a tiebreaker
        all_stacks.sort(
            key=lambda stack: (
                nameOf(stack.item_id).lower(),
                0 if isFull(stack) else 1,
                stack.item_id,
                -stack.qty
            )
        )

        # Write back packed from the left; leave empties after last item
        i = 0
        for stack in all_stacks:
            if i >= self.capacity:
                break
            self.slots[i] = stack
            i += 1
        while i < self.capacity:
            self.slots[i] = None
            i += 1

    def _maxStack(self, item_id : str) -> int:
        return self.item_defs[item_id].stack_size if item_id in self.item_defs else 1
    
    def _canStack(self, a : ItemStack, b : ItemStack) -> bool:
        if a.item_id != b.item_id:
            return False
        
        # Per-instance (has iid) -> never merge
        if a.iid is not None or b.iid is not None:
            return False
        
        return self._maxStack(a.item_id) > 1
    
    def __str__(self) -> str:
        """Print the inventory slots."""
        parts = []
        for i, slot in enumerate(self.slots):
            if slot is None:
                parts.append(f"{i:02d}: empty")
            else:
                parts.append(f"{i:02d}: {slot.item_id} x{slot.qty}")
        
        return " | ".join(parts)
    
    def count(self, item_id : str) -> int:
        """Return the total quantity of an item across all slots"""
        total = 0
        for s in self.slots:
            if s and s.item_id == item_id:
                total += s.qty
        
        return total
    
    def setSlot(self, index : int, item_id : str, qty : int, *, current_durability : Optional[float] = None):
        """Directly place an item in a slot (ignores stacking rules)."""
        if not (0 <= index < self.capacity):
            raise IndexError("Invalid slot index")
        iid = None
        if self._maxStack(item_id) <= 1 and (self.items.isWeapon(item_id) or self.items.isArmor(item_id)):
            if qty != 1:
                raise ValueError("Non-stacable items should have qty=1 per slot")
            iid = self.items.newInstance(item_id, current=current_durability)
        self.slots[index] = ItemStack(item_id, qty, iid)

    def describeSlot(self, index : int) -> str:
        s = self.slots[index]
        if not s:
            return f"{index:02d} : empty"
        
        d = self.item_defs.get(s.item_id)
        name = d.name if d else s.item_id
        stack_size = d.stack_size if d else 1
        weight = d.weight if d else 0.0
        tags = list(d.tags) if d else []

        # recognize types from tags
        is_weapon = ("weapon" in tags)
        is_armor = ("armor" in tags)

        # core attrs
        attrs = [
            f"{index:02d} : {name} (id={s.item_id})",
            f"qty = {s.qty}/{stack_size}",
            f"weight = {weight:.2f}",
            f"tags = [{', '.join(tags)}]" if tags else "tags = []",
        ]

        # type specific attrs from ItemDef
        if d and d.base_damage is not None:
            attrs.append(f"damage = {d.base_damage}")
        if d and hasattr(d, "base_protection") and d.base_protection is not None:
            attrs.append(f"protection = {d.base_protection}")
        if d and hasattr(d, "status_effects") and d.status_effects:
            attrs.append(f"effects = [{', '.join(d.status_effects)}]")

        # durability 
        cur = self.items.getDurability(s.iid)
        max_dur = d.max_durability if d else None
        ratio = self.items.durabilityRatio(s.iid)

        # only show durability if relevant (weapon/armor or any durability present)
        cur_txt = f"{cur:.2f}" if cur is not None else "n/a"
        max_txt = f"{max_dur:.2f}" if isinstance(max_dur, (int, float)) and max_dur is not None else "n/a"
        ratio_txt = f"{ratio:.1%}" if ratio is not None else "n/a"
        attrs.append(f"dur = {cur_txt}/{max_txt} ({ratio_txt})")

        return " | ".join(attrs)