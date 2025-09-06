from dataclasses import dataclass
from typing import Dict, List, Tuple

@dataclass(frozen=True)
class CookingRecipe:
    key : str
    inputs : List[Tuple[str, int]]
    cooked_output : Tuple[str, int]
    burned_output : Tuple[str, int]
    cook_time : float
    burn_time : float

recipes : Dict[str, CookingRecipe] = {
    "cooked_apple" : CookingRecipe(
        key = "cooked_apple",
        inputs = [("apple", 1)],
        cooked_output = ("cooked_apple", 1),
        burned_output = ("burned_apple", 1),
        cook_time = 5.0,
        burn_time = 5.0
    ),
    "apple_pie" : CookingRecipe(
        key = "apple_pie",
        inputs = [("apple", 1), ("bread", 1)],
        cooked_output = ("apple_pie", 1),
        burned_output = ("burned_apple_pie", 1),
        cook_time = 10.0,
        burn_time = 10.0
    )
}

def getRecipes() -> Dict[str, CookingRecipe]:
    return dict(recipes)