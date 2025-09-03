from dataclasses import dataclass
from typing import Dict, Optional
from pathlib import Path
from uuid import uuid4
import json

@dataclass(frozen=True)
class ItemDef:
    id : str
    name : str
    stack_size : int = 1
    weight : float = 0.0
    tags : tuple[str, ...] = ()
    base_damage : Optional[int] = None
    max_durability : Optional[float] = None
    base_protection : Optional[float] = None
    status_effects : tuple[str, ...] = ()

def loadItemDefs(path: Path) -> Dict[str, ItemDef]:
    data = json.loads(path.read_text(encoding="utf-8"))
    defs : Dict[str, ItemDef] = {}
    for row in data:
        defs[row["id"]] = ItemDef(
            id = row["id"],
            name = row["name"],
            stack_size = int(row.get("stack_size", 1)),
            weight = float(row.get("weight", 0.0)),
            tags = tuple(row.get("tags", [])),
            base_damage = (int(row["base_damage"]) if "base_damage" in row else None),
            max_durability = (int(row["max_durability"]) if "max_durability" in row else None),
            base_protection = (float(row["base_protection"]) if "base_protection" in row else None),
            status_effects = tuple(row.get("staus_effects", [])),
        )
    return defs

class Items:
    def __init__(self, defs : Dict[str, ItemDef]) -> None:
        self.defs = defs
        self._instances: Dict[str, tuple[str, float]] = {}
        
    @classmethod
    def load(cls, path : Path) -> "Items":
        return cls(loadItemDefs(path))

    def isWeapon(self, item_id : str) -> bool:
        """
        True if the item has the 'weapon' tag.
        """
        w = self.defs.get(item_id)
        return bool(w and "weapon" in w.tags)
    
    def isArmor(self, item_id : str) -> bool:
        a = self.defs.get(item_id)
        return bool(a and ("armor" in a.tags))
    
    def protection(self, item_id : str) -> float:
        p = self.defs.get(item_id)
        return float(p.base_protection) if p and p.base_protection is not None else 0.0
    
    def effects(self, item_id : str) -> tuple[str, ...]:
        s = self.defs.get(item_id)
        return s.status_effects if s else ()

    def initialDurability(self, item_id : str) -> Optional[float]:
        """
        For weapons, return their starting durability.
        Uses max_durability if present; defaults to 100 if missing.
        Returns None for non-weapons.
        """
        d = self.defs.get(item_id)
        if not d or (("weapon" not in d.tags) and ("armor" not in d.tags)):
            return None
        return float(d.max_durability) if d.max_durability is not None else 100.0
    
    def newInstance(self, item_id : str, *, current : Optional[float] = None) -> Optional[str]:
        """
        Create and register a per-instance durability record.
        Returns an iid or None for stackable/non-weapon items.
        """
        d = self.defs.get(item_id)
        if not d:
            return None
        if d.stack_size <= 1 and (("weapon" in d.tags) or ("armor" in d.tags)):
            cur = float(current) if current is not None else float(self.initialDurability(item_id) or 0.0)
            iid = str(uuid4())
            self._instances[iid] = (item_id, cur)
            return iid
        
        return None
    
    def destroyInstance(self, iid : Optional[str]) -> None:
        if iid is not None:
            self._instances.pop(iid, None)
    
    def getDurability(self, iid: Optional[str]) -> Optional[float]:
        if iid is None:
            return None
        rec = self._instances.get(iid)

        return None if rec is None else rec[1]

    def durabilityRatio(self, iid : Optional[str]) -> Optional[float]:
        if iid is None:
            return None
        rec = self._instances.get(iid)
        if rec is None:
            return None
        item_id, cur = rec
        d = self.defs.get(item_id)
        if not d or d.max_durability is None or d.max_durability <= 0:
            return None
        
        return cur / float(d.max_durability)
    
    def loseDurability(self, iid: Optional[str], rate: float) -> Optional[int]:
        """
        Reduce durability for instance 'iid' by a fraction of its max durability.
        - 'rate' is a fraction
        - If 'rate' > 0, at least 1 point is lost.
        - Clamps at 0; Does NOT delete the instance.
        Returns the new durability, or None if iid not found
        """
        if iid is None:
            return None
        rec = self._instances.get(iid)
        if rec is None:
            return None
        
        item_id, cur = rec
        dec = max(0.0, float(rate))
        new_val = max(0.0, float(cur) - dec)
        self._instances[iid] = (item_id, new_val)

        return new_val
    
    def setDurability(self, iid : Optional[str], value : float) -> None:
        if iid is None:
            return None
        rec = self._instances.get(iid)
        if rec is None:
            return None
        item_id, _ = rec
        new_val = max(0.0, float(value))
        self._instances[iid] = (item_id, new_val)
        
        return new_val