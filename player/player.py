from typing import Optional
from inventory.items import Items
from inventory.inventory import Inventory

class Player:
    def __init__(self, name : str, items : Items, inv_capacity : int = 30) -> None:
        self.name = name
        self.inv = Inventory(capacity = inv_capacity, items = items)

    # <<----------- Inventory pass-through functions ----------->>
    def addInv(self, item_id : str, qty : int) -> int:
        return self.inv.add(item_id, qty)
    
    def removeInv(self, item_id : str, qty : int) -> int:
        return self.inv.remove(item_id, qty)
    
    def moveInv(self, src : int, dst : int) -> bool:
        return self.inv.move(src, dst)
    
    def splitInv(self, src : int, dst : int, amount : int) -> bool:
        return self.inv.split(src, dst, amount)
    
    def splitHalfInv(self, src : int, dst : int) -> bool:
        return self.inv.splitHalf(src, dst)
    
    def sortInv(self) -> None:
        self.inv.sort()
    
    def count(self, item_id : str) -> int:
        return self.inv.count(item_id)
    
    # additional inventory functions
    def showInventory(self, *, detailed : bool = False) -> None:
        """
        Print Inventory in a quick or detailed form.
        Detailed uses Inventory.describeSlot if you add it.
        """
        print(f"== {self.name}'s Inventory ==")
        if detailed and hasattr(self.inv, "describeSlot"):
            for i in range(self.inv.capacity):
                print(getattr(self.inv, "describeSlot")(i))
        else:
            print(self.inv)
    
    def setSlot(self, index : int, item_id : str, qty : int, *,
                current_durability : Optional[float] = None) -> None:
        """
        Directly seed a slot.
        """
        if "current_durability" in self.inv.setSlot.__code__.co_varnames:
            self.inv.setSlot(index, item_id, qty, current_durability = current_durability)
        else:
            self.inv.setSlot(index, item_id, qty)