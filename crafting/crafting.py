from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from inventory.items import Items
from inventory.inventory import Inventory

@dataclass(frozen=True)
class Recipe:
    output_id : str
    output_qty : int
    inputs : List[Tuple[str, int]]

class Crafting:
    def __init__(self, items : Items, recipes : Optional[Dict[str, Recipe]] = None) -> None:
        self.items = items
        self.recipes : Dict[str, Recipe] = dict(recipes) if recipes else {}

    def addRecipe(self, recipe : Recipe) -> None:
        self.recipes[recipe.output_id] = recipe

    def canCraft(self, inv : Inventory, output_id : str, times : int = 1) -> Tuple[bool, str]:
        rec = self.recipes.get(output_id)
        if not rec:
            return False, f"No recipe for '{output_id}'."
        
        # check inputs
        needed : Dict[str, int] = {}
        for iid, q in rec.inputs:
            needed[iid] = needed.get(iid, 0) + q * times

        # collect ALL shortages
        shortages : list[str] = []
        for iid, req in needed.items():
            have = inv.count(iid)
            if have < req:
                shortages.append(f"{iid}: need {req}, have {have} (short {req - have})")

        if shortages:
            try:
                max_craftable = min(inv.count(iid) // q for iid, q in rec.inputs)
            except ZeroDivisionError:
                max_craftable = 0
            hint = f" You can craft at most {max_craftable} right now." if max_craftable > 0 else ""
            return False, "Missing materials: " + "; ".join(shortages) + "." + hint
            
        # check capacity for outputs
        total_out = rec.output_qty * times
        if not self._canAdd(inv, rec.output_id, total_out):
            return False, "Not enough space to place crafted items."
        
        c = self.items.defs.get(rec.output_id)
        if not c or "craftable" not in c.tags:
            return True, "Item not tagged craftable, but recipe exists."
        
        return True, "Yes"
    
    def craft(self, inv : Inventory, output_id : str, times : int = 1) -> bool:
        """
        If counts/space insufficient, do nothing.
        If removing inputs partially succeeds, roll back.
        """
        ok, _ = self.canCraft(inv, output_id, times)
        if not ok:
            return False
        
        rec = self.recipes[output_id]
        needed : Dict[str, int] = {}
        for iid, q in rec.inputs:
            needed[iid] = needed.get(iid, 0) + q * times

        # remove inputs, tracking what we actually removed to allow rollback
        removed : Dict[str, int] = {}
        for iid, req in needed.items():
            got = inv.remove(iid, req)
            removed[iid] = got
            if got < req:
                # rollback previously removed
                for rid, qty in removed.items:
                    if qty > 0:
                        inv.add(rid, qty)
                return False
            
        # add outputs
        out_total = rec.output_qty * times
        added = inv.add(rec.output_id, out_total)
        if added < out_total:
            # rollback: remove what we add and give back inputs
            if added > 0:
                inv.remove(rec.output_id, added)
            for rid, qty in removed.items():
                if qty > 0:
                    inv.add(rid, qty)
            return False
        
        return True
    
    def _canAdd(self, inv : Inventory, item_id : str, qty : int) -> bool:
        """
        Estimate if we can fit 'qty' of item_id into the inventory based on:
        - free space in existing stacks of that item (only for stackables)
        - number of empty slots * max_stack
        """
        max_stack = inv._maxStack(item_id)
        # space in existing stacks (only vaid for stackables)
        space = 0
        if max_stack > 1:
            for s in inv.slots:
                if s and s.item_id == item_id:
                    space += (max_stack - s.qty)
        # empty slots capacity
        empties = sum(1 for s in inv.slots if s is None)
        capacity = space + empties * max_stack
        return capacity >= qty