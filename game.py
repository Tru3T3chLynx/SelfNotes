# import modules
import sys
from pathlib import Path
import pygame

# my modules
from player.player import Player
from storage.storage import Storage
from inventory.items import Items
from inventory.inventory import Inventory
from crafting.crafting import Crafting
from crafting.recipes import getRecipes as getCraftingRecipes
from cooking.cooking import CookingStation
from cooking.recipes import getRecipes as getCookingRecipes

# variables
WIDTH, HEIGHT = 1024, 640

BG = (24, 26, 32)
PANEL = (34, 38, 46)
GRID_BG = (44, 48, 56)
SLOT = (64, 68, 78)
SLOT_HOVER = (90, 98, 112)
TEXT = (230, 232, 235)
TEXT_DIM = (170, 175, 185)
ACCENT = (80, 200, 120)
ALERT = (230, 95, 95)
YELLOW = (240, 210, 120)

FONT_SIZE = 16
TITLE_SIZE = 22

SLOT_SIZE = 64
SLOT_PAD = 8
GRID_COLS = 4
GRID_ROWS = 4

LEFT_GRID_X = 24
LEFT_GRID_Y = 96

RIGHT_GRID_X = 560
RIGHT_GRID_Y = 96

MENU_Y = 16
BTN_W, BTN_H = 160, 32
BTN_PAD = 12

# Cooking station specifics
COOK_INPUT_ROWS = 1
COOK_INPUT_COLS = 5
COOK_INPUT_X = RIGHT_GRID_X
COOK_INPUT_Y = RIGHT_GRID_Y

COOK_BAR_W = SLOT_SIZE * 5 + SLOT_PAD * 4
COOK_BAR_H = 10
COOK_BAR_X = RIGHT_GRID_X
COOK_BAR_Y = RIGHT_GRID_Y + SLOT_SIZE + 16

COOK_OUT_X = RIGHT_GRID_X
COOK_OUT_Y = COOK_BAR_Y + 32

LIST_X = RIGHT_GRID_X
LIST_Y = RIGHT_GRID_Y
LIST_W = WIDTH - RIGHT_GRID_X - 24
ROW_H = 28

# Functions
def makeInv(items, capacity=16):
    return Inventory(capacity=capacity, items=items)

def nameOf(items : Items, item_id : str) -> str:
    d = items.defs.get(item_id)
    return d.name if d else item_id

def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

def moveBetweenInventories(items : Items, src_inv : Inventory, src_idx : int,
                           dst_inv : Inventory, dst_idx : int) -> bool:
    if not (0 <= src_idx < src_inv.capacity and 0 <= dst_idx < dst_inv.capacity):
        return False
    
    src = src_inv.slots[src_idx]
    dst = dst_inv.slots[dst_idx]

    # Nothing to move
    if src is None:
        return False
    
    def maxStack(inv, iid):
        return inv._maxStack(iid)
    
    # if dest empty -> move stack
    if dst is None:
        dst_inv.slots[dst_idx] = src
        src_inv.slots[src_idx] = None
        return True
    
    # same item -> merge if stackable and no per instance iid
    if src.item_id == dst.item_id:
        m = maxStack(dst_inv, dst.item_id)
        if getattr(src, "iid", None) is None and getattr(dst, "iid", None) is None:
            space = m - dst.qty
            if space <= 0:
                # no space
                src_inv[src_idx], dst_inv.slots[dst_idx] = dst, src
                return True
            moved = min(space, src.qty)
            dst.qty += moved
            src.qty -= moved
            if src.qty == 0:
                src_inv.slots[src_idx] = None
            return moved > 0
        else:
            src_inv.slots[src_idx], dst_inv.slots[dst_idx] = dst, src
            return True
        
    # Different items -> swap stacks
    src_inv.slots[src_idx], dst_inv.slots[dst_idx] = dst, src
    return True

class Button:
    def __init__(self, rect, label):
        self.rect = pygame.Rect(rect)
        self.label = label

    def draw(self, surf, font, mouse):
        hovered = self.rect.collidepoint(mouse)
        pygame.draw.rect(surf, SLOT_HOVER if hovered else SLOT, self.rect, border_radius=6)
        text = font.render(self.label, True, TEXT)
        surf.blit(text, text.get_rect(center=self.rect.center))

    def hit(self, pos):
        return self.rect.collidepoint(pos)
    
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("freesansbold.ttf", FONT_SIZE)
        self.title_font = pygame.font.SysFont("freesansbold.ttf", TITLE_SIZE, bold=True)

        # Data
        root = Path(__file__).parent
        self.items = Items.load(root / "inventory" / "items.json")
        # Inventories
        self.player = Player("Player", self.items, capacity=16)
        self.storage = Storage(self.items, capacity=16, name="Storage")

        # Seed some stuff
        self.player.addInv("apple", 3)
        self.player.addInv("dough", 2)
        self.player.addInv("wood", 25)
        self.player.addInv("iron_ingot", 4)
        self.player.addInv("iron_sword", 1)

        # Crafting
        self.crafting = Crafting(self.items, recipes=getCraftingRecipes())

        # Cooking station
        self.cookingStation = CookingStation(self.items, recipes=getCookingRecipes(),
                                             num_inputs=5, num_outputs=1, burn_enabled=False)
        
        # UI state
        self.mode = "menu"
        self.msg = ""

        # Menu buttons
        self.btn_storage = Button((24, MENU_Y, BTN_W, BTN_H), "Go to Storage")
        self.btn_crafting = Button((24 + BTN_W + BTN_PAD, MENU_Y, BTN_W, BTN_H), "Go to Crafting")
        self.btn_cooking = Button((24 + 2*(BTN_W + BTN_PAD), MENU_Y, BTN_W, BTN_H), "Go to Cooking")

        # Drag state
        self.dragging = False
        self.drag_from = None
        self.drag_item = None
        self.drag_offset = (0, 0)

        # crafting list scroll/selection
        self.craft_scroll = 0

        # cooking: show recipe options list for selection
        self.show_cook_options = True

    def gridRect(self, x, y, cols, rows):
        w = cols * SLOT_SIZE + (cols - 1) * SLOT_PAD
        h = rows * SLOT_SIZE + (rows - 1) * SLOT_PAD
        
        return pygame.Rect(x, y, w, h)
    
    def slotRect(self, gx, gy, col, row):
        x = gx + col * (SLOT_SIZE + SLOT_PAD)
        y = gy + row * (SLOT_SIZE + SLOT_PAD)

        return pygame.Rect(x, y, SLOT_SIZE, SLOT_SIZE)
    
    def hitInvSlot(self, pos, origin_x, origin_y, inv):
        cols = GRID_COLS
        rows = (inv.capacity + cols - 1) // cols
        grid = self.gridRect(origin_x, origin_y, cols, rows)
        if not grid.collidepoint(pos):
            return None
        # Which slot
        relx, rely = pos[0] - origin_x, pos[1] - origin_y
        col = relx // (SLOT_SIZE + SLOT_PAD)
        row = rely // (SLOT_SIZE + SLOT_PAD)
        if col >= cols or row >= rows:
            return None
        idx = int(row * cols + col)
        if idx >= inv.capacity:
            return None
        
        return idx
    
    def hitCookInputSlot(self, pos):
        # 5 input slots laid out in a row at COOK_INPUT_X/Y
        for i in range(5):
            r = self.slotRect(COOK_INPUT_X, COOK_INPUT_Y, i, 0)
            if r.collidepoint(pos):
                return i
            
        return None
        
    def hitCookOutputSlot(self, pos):
        cooked_r = self.slotRect(COOK_OUT_X, COOK_OUT_Y, 0, 0)
        burned_r = self.slotRect(COOK_OUT_X + SLOT_SIZE + SLOT_PAD, COOK_OUT_Y, 0, 0)
        if cooked_r.collidepoint(pos):
            return ("cooked", 0)
        if burned_r.collidepoint(pos):
            return ("burned", 0)
        
        return None
    
    


