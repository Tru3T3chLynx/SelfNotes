from typing import Dict
from crafting.crafting import Recipe 

recipes : Dict[str, Recipe] = {
    "wooden_pickaxe" : Recipe(
        output_id = "wooden_pickaxe",
        output_qty = 1,
        inputs = [("wood", 3)]
    ),
    "iron_pickaxe" : Recipe(
        output_id = "iron_pickaxe",
        output_qty = 1,
        inputs = [("iron_ingot", 2), ("wood", 1)]
    )
}

def getRecipes() -> Dict[str, Recipe]:
    return dict(recipes)