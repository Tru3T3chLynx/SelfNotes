from dataclasses import dataclass
from typing import Optional, Dict, Tuple, List, Literal
from inventory.items import Items
from inventory.inventory import Inventory
from .recipes import CookingRecipe

State = Literal["idle", "cooking", "ready", "burned"]
    
@dataclass
class Slot:
    item_id : Optional[str] = None
    qty : int = 0

class CookingStation:
    def __init__(self, items : Items, recipes : Dict[str, CookingRecipe],
               *, num_inputs : int = 5, num_outputs : int = 1, burn_enabled : bool = True) -> None:
        self.items = items
        self.recipes = recipes
        self.inputs : List[Slot] = [Slot() for _ in range(num_inputs)]
        self.cooked_out : List[Slot] = [Slot() for _ in range(num_outputs)]
        self.burned_out : List[Slot] = [Slot() for _ in range(num_outputs)]
        self.active_recipe : Optional[str] = None
        self.job_elapsed : float = -1.0
        self.burn_elapsed : float = 0.0
        self.burn_enabled : bool = burn_enabled

    def setRecipe(self, recipe_key : str) -> bool:
        if recipe_key not in self.recipes: 
            return False
        if self.isCooking(): 
            return False
        self.active_recipe = recipe_key

        return True
    
    def isCooking(self) -> bool:
        return self.active_recipe is not None and self.job_elapsed >= 0.0
    
    def setBurningEnabled(self, enabled : bool) -> None:
        self.burn_enabled = enabled
        self.burn_elapsed = 0.0

    def _maxStack(self, item_id : str) -> int:
        d = self.items.defs.get(item_id)
        return d.stack_size if d else 99
    
    def addIngredient(self, idx : int, item_id : str, qty : int) -> int:
        if not (0 <= idx < len(self.inputs)) or qty <= 0:
            return 0
        s = self.inputs[idx]
        if s.item_id is None:
            take = min(qty, self._maxStack(item_id))
            s.item_id, s.qty = item_id, take
            return take
        if s.item_id != item_id:
            return 0
        space = self._maxStack(item_id) - s.qty
        take = min(space, qty)
        s.qty += take
        return take
    
    def _countInputs(self, item_id : str) -> int:
        return sum(s.qty for s in self.inputs if s.item_id == item_id)
    
    def _consumeInputs(self, item_id : str, qty : int) -> int:
        left = qty
        for s in self.inputs:
            if s.item_id != item_id:
                continue
            take = min(s.qty, left)
            s.qty -= take
            left -= take
            if s.qty == 0:
                s.item_id = None
            if left == 0:
                break
        return qty - left
    
    def _haveForOne(self, rec : CookingRecipe) -> bool:
        for iid, need in rec.inputs:
            if self._countInputs(iid) < need:
                return False
            
        return True
    
    def _roomInCooked(self, cooked_id : str, cooked_qty : int) -> bool:
        for s in self.cooked_out:
            if s.item_id is None:
                return cooked_qty <= self._maxStack(cooked_id)
            if s.item_id == cooked_id and s.qty + cooked_qty <= self._maxStack(cooked_id):
                return True
            
        return False
    
    def _depositCooked(self, cooked_id : str, cooked_qty : int) -> bool:
        # matching stack first
        for s in self.cooked_out:
            if s.item_id == cooked_id:
                maxs = self._maxStack(cooked_id)
                space = maxs - s.qty
                if cooked_qty <= space:
                    s.qty += cooked_qty
                    return True
                
        # empty slot
        for s in self.cooked_out:
            if s.item_id is None:
                s.item_id, s.qty = cooked_id, cooked_qty
                return True
        
        return False
    
    def _roomInBurned(self, burned_id : str, burned_qty : int) -> bool:
        for s in self.burned_out:
            if s.item_id == burned_id and s.qty + burned_qty <= self._maxStack(burned_id):
                return True
        for s in self.burned_out:
            if s.item_id is None:
                return burned_qty <= self._maxStack(burned_id)
            
        return False
    
    def _depositBurned(self, burned_id : str, burned_qty : int) -> bool:
        for s in self.burned_out:
            if s.item_id == burned_id:
                maxs = self._maxStack(burned_id)
                space = maxs - s.qty
                if burned_qty <= space:
                    s.qty += burned_qty
                    return True
        for s in self.burned_out:
            if s.item_id is None:
                s.item_id, s.qty = burned_id, burned_qty
                return True
        
        return False
    
    def _startOne(self) -> bool:
        if self.active_recipe is None:
            return False
        rec = self.recipes[self.active_recipe]
        cooked_id, cooked_qty = rec.cooked_output
        if not self._roomInCooked(cooked_id, cooked_qty):
            return False
        if not self._haveForOne(rec):
            return False
        # consume inputs
        for iid, need in rec.inputs:
            got = self._consumeInputs(iid, need)
            assert got == need
        self.job_elapsed = 0.0

        return True
    
    def advance(self, dt : float) -> None:
        if dt <= 0:
            return
        
        # try to start a job BEFORE tiking time (so this dt applies to it)
        if self.active_recipe and self.job_elapsed < 0.0:
            started_now = self._startOne()
            if started_now:
                self.burn_elapsed = 0.0

        rec = self.recipes.get(self.active_recipe) if self.active_recipe else None
        did_cook = False

        # progress cooking
        if rec and self.job_elapsed >= 0.0:
            self.job_elapsed += dt
            if self.job_elapsed >= rec.cook_time:
                cooked_id, cooked_qty = rec.cooked_output
                if self._depositCooked(cooked_id, cooked_qty):
                    self.job_elapsed = -1.0
                    self.burn_elapsed = 0.0
                    did_cook = True
                else:
                    self.job_elapsed = -1.0

        # try to start more cooking if idle
        started = False
        if self.active_recipe and self.job_elapsed < 0.0:
            started = self._startOne()
            if started:
                self.burn_elapsed = 0.0

        if not started and self.job_elapsed < 0.0 and self.burn_enabled and not did_cook:
            cooked_idx = next((i for i, s in enumerate(self.cooked_out) if s.item_id and s.qty > 0), None)
            if cooked_idx is not None and self.active_recipe:
                cooked_id = self.cooked_out[cooked_idx].item_id
                r = self.recipes.get(cooked_id)
                if r:
                    self.burn_elapsed += dt
                    if self.burn_elapsed >= r.burn_time:
                        self._burnOne(cooked_idx, r)
                        self.burn_elapsed = 0.0

        # hide burned slots that became empty
        for s in self.burned_out:
            if s.item_id is not None and s.qty == 0:
                s.item_id = None

    def _burnOne(self, cooked_idx : int, r : CookingRecipe) -> bool:
        s = self.cooked_out[cooked_idx]
        if not s.item_id or s.qty <= 0:
            return False
        burned_id, burned_qty = r.burned_output
        if not self._roomInBurned(burned_id, burned_qty):
            return False
        # convert one cooked -> burned
        s.qty -= 1
        if s.qty == 0:
            s.item_id = None
        
        return self._depositBurned(burned_id, burned_qty)
    
    def collectCooked(self, inv : Inventory, slot_idx : int = 0, qty : Optional[int] = None) -> int:
        if not (0 <= slot_idx < len(self.cooked_out)):
            return 0
        s = self.cooked_out[slot_idx]
        if not s.item_id or s.qty <= 0:
            return 0
        take = s.qty if qty is None else min(qty, s.qty)
        added = inv.add(s.item_id, take)
        if added > 0:
            s.qty -= added
            if s.qty == 0:
                s.item_id = None
        
        return added
    
    def collectBurned(self, inv : Inventory, slot_idx : int = 0, qty : Optional[int] = None) -> int:
        if not (0 <= slot_idx < len(self.burned_out)):
            return 0
        s = self.burned_out[slot_idx]
        if not s.item_id or s.qty <= 0:
            return 0
        take = s.qty if qty is None else min(qty, s.qty)
        added = inv.add(s.item_id, take)
        if added > 0:
            s.qty -= added
            if s.qty == 0:
                s.item_id = None
        
        return added
    
    def _inputCounts(self) -> Dict[str, int]:
        counts : Dict[str, int] = {}
        for s in self.inputs:
            if s.item_id:
                counts[s.item_id] = counts.get(s.item_id, 0) + s.qty
        
        return counts
    
    def _canMakeWithCounts(self, rec : CookingRecipe, counts : Dict[str, int]) -> bool:
        for iid, need in rec.inputs:
            if counts.get(iid, 0) < need:
                return False
        return True
    
    def _maxFromIngredients(self, rec : CookingRecipe, counts : Dict[str, int]) -> int:
        return min(counts.get(iid, 0) // need for iid, need in rec.inputs)
    
    def _outputCapacityUnits(self, cooked_id : str, unit_qty : int) -> int:
        cap = 0
        maxs = self._maxStack(cooked_id)
        for s in self.cooked_out:
            if s.item_id is None:
                cap += maxs // unit_qty
            elif s.item_id == cooked_id:
                free = maxs - s.qty
                if free > 0:
                    cap += free // unit_qty

        return cap
    
    def recipeOptions(self) -> List[Dict[str, object]]:
        if not self.recipes:
            return []
        counts = self._inputCounts()
        opts : List[Dict[str, object]] = []
        for key, r in self.recipes.items():
            if not self._canMakeWithCounts(r, counts):
                continue
            out_id, out_qty = r.cooked_output
            max_by_mats = self._maxFromIngredients(r, counts)
            max_by_capacity = self._outputCapacityUnits(out_id, out_qty)
            name = self.items.defs.get(out_id).name if self.items.defs.get(out_id) else out_id
            opts.append({
                "key" : key,
                "name" : name,
                "cook_time" : r.cook_time,
                "burn_time" : r.burn_time,
                "max_by_mats" : max_by_mats,
                "max_by_capacity" : max_by_capacity,
                "max_now" : min(max_by_mats, max_by_capacity),
                "specificity_score" : (sum(q for _, q in r.inputs), len(r.inputs), key)
            })
        opts.sort(key = lambda o : o["specificity_score"], reverse = True)
        return opts
    
    def printRecipeOptions(self) -> None:
        opts = self.recipeOptions()
        if not opts:
            print("No craftable recipes from current inputs.")
            return
        for i, o in enumerate(opts):
            print(f"[{i}] {o['name']} (key = {o['key']}): cook = {o['cook_time']}s, burn = {o['burn_time']}s,"
                  f" can make now = {o['max_now']} (by mats {o['max_by_mats']}, by cap {o['max_by_capacity']})")
            
    def selectRecipeByKey(self, key : str) -> Tuple[bool, str]:
        if self.isCooking():
            return False, "Busy: wait until current item finishes."
        if key not in self.recipes:
            return False, f"Unkown recipe key '{key}'."
        counts = self._inputCounts()
        rec = self.recipes[key]
        if not self._canMakeWithCounts(rec, counts):
            return False, "Insufficient ingredients for that recipe."
        self.active_recipe = key
        self.job_elapsed = -1.0
        self.burn_elapsed = 0.0
        out_id, out_qty = rec.cooked_output
        if self._outputCapacityUnits(out_id, out_qty) <= 0:
            return True, "Selected; note: cooked output has no room right now."
        
        return True, "Selected."
    
    def selectRecipeByIndex(self, index : int) -> Tuple[bool, str]:
        opts = self.recipeOptions()
        if not (0 <= index < len(opts)):
            return False, "Invalid option index."
        return self.selectRecipeByKey(opts[index]["key"])
    
    def previewRecipeKey(self) -> Optional[str]:
        if not self.recipes:
            return None
        counts = self._inputCounts()

        if self.active_recipe:
            r = self.recipes.get(self.active_recipe)
            if r and self._canMakeWithCounts(r, counts):
                return self.active_recipe
            
        matches : List[str] = []
        for key, r in self.recipes.items():
            if self._canMakeWithCounts(r, counts):
                matches.append(key)
        if not matches:
            return None
        
        def score(key : str) -> tuple[int, int, str]:
            r = self.recipes[key]
            total = sum(q for _, q in r.inputs)
            distinct = len(r.inputs)
            return (total, distinct, key)
        
        matches.sort(key = score, reverse = True)
        return matches[0]
    
    def previewCookedName(self) -> Optional[str]:
        key = self.previewRecipeKey()
        if not key:
            return None
        out_id, _ = self.recipes[key].cooked_output
        d = self.items.defs.get(out_id)
        
        return d.name if d else out_id
    
    def statusText(self) -> str:
        def fmt_slots(label : str, arr: List[Slot]) -> str:
            vis = [f"{s.item_id} x{s.qty}" for s in arr if s.item_id]
            return f"{label}[{'; '.join(vis) if vis else '-'}]"
        cook_state = "COOKING" if self.isCooking() else "IDLE"
        parts = [
            f"{cook_state}({self.active_recipe or 'none'})",
            fmt_slots("Cooked", self.cooked_out),
            fmt_slots("Burned", self.burned_out)
        ]
        preview = self.previewCookedName()
        if preview:
            parts.append(f"Preview: {preview}")
        return " | ".join(parts)


