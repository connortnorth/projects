import sys
import random
import math
import pygame
from perlin_noise import PerlinNoise

# --- CONFIGURATION ---
# Size of each tile in pixels
TILE_SIZE = 32
# Number of tiles per chunk (for procedural generation)
CHUNK_SIZE = 16
# Display dimensions
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
# Game frame rate
FPS = 60

# Tile & Item Types
AIR = 0
GRASS = 1
DIRT = 2
STONE = 3
COAL_ORE = 4
IRON_ORE = 5
FURNACE = 6
COAL = 7
IRON_INGOT = 8
WOOD = 9
LEAVES = 10
PLANKS = 11
WORKBENCH = 12
# Natural variants have no collision (can walk through)
NATURAL_WOOD = 13
NATURAL_LEAVES = 14

# Colors
COLOR_SKY = (135, 206, 235)
COLOR_GRASS = (34, 139, 34)
COLOR_DIRT = (139, 69, 19)
COLOR_STONE = (128, 128, 128)
COLOR_COAL = (40, 40, 40)
COLOR_IRON_ORE = (184, 115, 51)
COLOR_FURNACE = (80, 80, 80)
COLOR_IRON_INGOT = (210, 210, 210)
COLOR_WOOD = (101, 67, 33)
COLOR_LEAVES = (46, 139, 87)
COLOR_PLANKS = (190, 140, 90)
COLOR_WORKBENCH = (150, 100, 50)
COLOR_PLAYER = (220, 20, 60)

COLOR_UI_BG = (40, 40, 40, 240)
COLOR_SLOT_BG = (20, 20, 20)
COLOR_UI_BORDER = (180, 180, 180)
COLOR_HOTBAR_SELECT = (255, 215, 0)

TILE_COLORS = {
    GRASS: COLOR_GRASS, DIRT: COLOR_DIRT, STONE: COLOR_STONE,
    COAL_ORE: COLOR_COAL, IRON_ORE: COLOR_IRON_ORE, FURNACE: COLOR_FURNACE,
    COAL: COLOR_COAL, IRON_INGOT: COLOR_IRON_INGOT, WOOD: COLOR_WOOD,
    LEAVES: COLOR_LEAVES, NATURAL_WOOD: COLOR_WOOD, NATURAL_LEAVES: COLOR_LEAVES,
    PLANKS: COLOR_PLANKS, WORKBENCH: COLOR_WORKBENCH
}

BLOCK_HARDNESS = {
    GRASS: 3, DIRT: 3, WOOD: 4, LEAVES: 2, STONE: 8,
    COAL_ORE: 10, IRON_ORE: 12, FURNACE: 6, PLANKS: 4, WORKBENCH: 5,
    NATURAL_WOOD: 4, NATURAL_LEAVES: 2
}


# --- WORLD MANAGEMENT ---
class World:
    """Manages procedural world generation using Perlin noise and chunk-based storage."""

    def __init__(self):
        self.chunks = {}  # Stores generated chunks keyed by (chunk_x, chunk_y)
        self.seed = random.randint(0, 100000)
        # Different noise generators for terrain features
        self.hill_noise = PerlinNoise(octaves=3, seed=self.seed)  # Surface terrain
        self.cave_noise = PerlinNoise(octaves=6, seed=self.seed + 1)  # Cave systems
        self.ore_noise = PerlinNoise(octaves=8, seed=self.seed + 2)  # Ore distribution
        self.base_surface = 10  # Base y-level for terrain surface
        self.amplitude = 12  # How much the terrain varies
        self.furnaces = {}  # Stores furnace state at positions
        self.mining_progress = {}  # Tracks mining progress for each tile

    def get_tile(self, tile_x, tile_y):
        """Get the tile type at world coordinates (tile_x, tile_y)."""
        chunk_x = tile_x // CHUNK_SIZE
        chunk_y = tile_y // CHUNK_SIZE
        local_x = tile_x % CHUNK_SIZE
        local_y = tile_y % CHUNK_SIZE

        chunk = self.get_chunk(chunk_x, chunk_y)
        return chunk[local_y][local_x]

    def set_tile(self, tile_x, tile_y, tile_type):
        """Set the tile type at world coordinates. Clears mining progress if present."""
        chunk_x = tile_x // CHUNK_SIZE
        chunk_y = tile_y // CHUNK_SIZE
        local_x = tile_x % CHUNK_SIZE
        local_y = tile_y % CHUNK_SIZE

        chunk = self.get_chunk(chunk_x, chunk_y)
        chunk[local_y][local_x] = tile_type
        # Reset mining progress when tile changes
        if (tile_x, tile_y) in self.mining_progress:
            del self.mining_progress[(tile_x, tile_y)]

    def get_chunk(self, chunk_x, chunk_y):
        """Get or generate a chunk at the given chunk coordinates."""
        key = (chunk_x, chunk_y)
        if key not in self.chunks:
            self.chunks[key] = self.generate_chunk(chunk_x, chunk_y)
        return self.chunks[key]

    def generate_chunk(self, chunk_x, chunk_y):
        """Procedurally generate a chunk using Perlin noise for terrain, caves, and ores."""
        chunk = [[AIR for _ in range(CHUNK_SIZE)] for _ in range(CHUNK_SIZE)]

        # Generate terrain layers
        for lx in range(CHUNK_SIZE):
            world_x = chunk_x * CHUNK_SIZE + lx
            noise_val = self.hill_noise([world_x / 100.0])
            surface_y = int(self.base_surface + noise_val * self.amplitude)

            for ly in range(CHUNK_SIZE):
                world_y = chunk_y * CHUNK_SIZE + ly

                # Air above surface
                if world_y < surface_y:
                    chunk[ly][lx] = AIR
                else:
                    # Cave generation using 2D noise
                    cave_val = self.cave_noise([world_x / 30.0, world_y / 30.0])
                    if cave_val > 0.15 and world_y > surface_y + 2:
                        chunk[ly][lx] = AIR
                    else:
                        # Layer generation: grass -> dirt -> stone with ores
                        if world_y == surface_y:
                            chunk[ly][lx] = GRASS
                        elif world_y < surface_y + 5:
                            chunk[ly][lx] = DIRT
                        else:
                            # Ore distribution using noise
                            ore_val = self.ore_noise([world_x / 15.0, world_y / 15.0])
                            if ore_val > 0.3:
                                chunk[ly][lx] = IRON_ORE
                            elif ore_val < -0.3:
                                chunk[ly][lx] = COAL_ORE
                            else:
                                chunk[ly][lx] = STONE

        # Tree Spawning (Uses NATURAL_WOOD and NATURAL_LEAVES with no collision)
        for lx in range(2, CHUNK_SIZE - 2):
            world_x = chunk_x * CHUNK_SIZE + lx
            noise_val = self.hill_noise([world_x / 100.0])
            surface_y = int(self.base_surface + noise_val * self.amplitude)

            # Deterministic random for consistent tree placement
            random.seed(self.seed + world_x)
            if random.random() < 0.2:  # 20% chance of tree
                tree_height = random.randint(4, 6)
                # Generate trunk
                for h in range(1, tree_height + 1):
                    ty = surface_y - h
                    if chunk_y * CHUNK_SIZE <= ty < (chunk_y + 1) * CHUNK_SIZE:
                        chunk[ty % CHUNK_SIZE][lx] = NATURAL_WOOD

                # Generate leaves (5x3 canopy at top)
                top_y = surface_y - tree_height
                for cx in range(-2, 3):
                    for cy in range(-2, 1):
                        lx_leaf = lx + cx
                        ty_leaf = top_y + cy
                        if 0 <= lx_leaf < CHUNK_SIZE and chunk_y * CHUNK_SIZE <= ty_leaf < (chunk_y + 1) * CHUNK_SIZE:
                            if chunk[ty_leaf % CHUNK_SIZE][lx_leaf] == AIR:
                                chunk[ty_leaf % CHUNK_SIZE][lx_leaf] = NATURAL_LEAVES

        random.seed()  # Reset to non-deterministic
        return chunk

    def hit_tile(self, tile_x, tile_y, item_drops):
        """Process a mining hit on a tile. Returns True if tile is broken."""
        tile = self.get_tile(tile_x, tile_y)
        if tile == AIR:
            return False

        max_hp = BLOCK_HARDNESS.get(tile, 3)
        current_hits = self.mining_progress.get((tile_x, tile_y), 0) + 1
        self.mining_progress[(tile_x, tile_y)] = current_hits

        # Tile broken when hits reach hardness
        if current_hits >= max_hp:
            self.set_tile(tile_x, tile_y, AIR)

            # Map natural variants back to normal placed item drops
            drop_type = tile
            if tile == COAL_ORE:
                drop_type = COAL
            elif tile == NATURAL_WOOD:
                drop_type = WOOD
            elif tile == NATURAL_LEAVES:
                drop_type = LEAVES

            drop_x = tile_x * TILE_SIZE + TILE_SIZE // 4
            drop_y = tile_y * TILE_SIZE + TILE_SIZE // 4
            item_drops.append(ItemDrop(drop_x, drop_y, drop_type))
            # Remove furnace if tile was a furnace
            if (tile_x, tile_y) in self.furnaces:
                del self.furnaces[(tile_x, tile_y)]
            return True
        return False

    def update_furnaces(self):
        """Update all furnaces: smelt iron ore when fuel is available (3 seconds at 60 FPS)."""
        for (fx, fy), data in list(self.furnaces.items()):
            if data["iron_ore"] > 0 and data["coal"] > 0:
                data["timer"] += 1.0
                if data["timer"] >= 180:  # 180 frames = 3 seconds
                    data["timer"] = 0
                    data["iron_ore"] -= 1
                    data["coal"] -= 1
                    data["output"] += 1
            else:
                data["timer"] = 0  # Reset timer if missing resources

    def get_surface_height(self, world_x):
        """Calculate the terrain surface y-level at a given world x-coordinate."""
        noise_val = self.hill_noise([world_x / 100.0])
        return int(self.base_surface + noise_val * self.amplitude)


# --- CAMERA ---
class Camera:
    """Follows the player and offsets rendering to create a scrolling viewport."""

    def __init__(self):
        self.x = 0  # Camera x offset in world coordinates
        self.y = 0  # Camera y offset in world coordinates

    def update(self, target):
        """Center camera on the target (usually the player)."""
        self.x = target.rect.centerx - SCREEN_WIDTH // 2
        self.y = target.rect.centery - SCREEN_HEIGHT // 2

    def apply(self, rect):
        """Convert world coordinates to screen coordinates."""
        return rect.move(-self.x, -self.y)


# --- ITEM DROP ---
class ItemDrop:
    """Dropped items that can be picked up by the player with physics."""

    def __init__(self, x, y, item_type):
        self.x = float(x)
        self.y = float(y)
        self.item_type = item_type
        self.size = 12
        self.rect = pygame.Rect(x, y, self.size, self.size)
        self.vy = -3.0  # Initial upward velocity (pop effect)
        self.vx = random.uniform(-1.5, 1.5)  # Random horizontal spread
        self.gravity = 0.3
        self.pickup_radius = 80  # Distance at which magnet effect activates
        self.magnet_speed = 6.0

    def update(self, player, world):
        """Update item physics: magnet effect when near player, gravity otherwise."""
        dx = player.rect.centerx - self.rect.centerx
        dy = player.rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)

        # Magnet effect: fly toward player when close
        if dist < self.pickup_radius and dist > 0:
            self.x += (dx / dist) * self.magnet_speed
            self.y += (dy / dist) * self.magnet_speed
        else:
            # Normal physics: gravity and collision
            self.vy += self.gravity
            self.x += self.vx
            self.y += self.vy

            # Ground collision
            gx = math.floor(self.x / TILE_SIZE)
            gy = math.floor((self.y + self.size) / TILE_SIZE)
            if world.get_tile(gx, gy) not in (AIR, NATURAL_WOOD, NATURAL_LEAVES):
                self.y = gy * TILE_SIZE - self.size
                self.vy = 0
                self.vx *= 0.8  # Friction

        self.rect.x = int(self.x)
        self.rect.y = int(self.y)

    def draw(self, surface, camera):
        """Render the item drop as a colored square with outline."""
        screen_pos = camera.apply(self.rect)
        pygame.draw.rect(surface, TILE_COLORS.get(self.item_type, (255, 255, 255)), screen_pos)
        pygame.draw.rect(surface, (0, 0, 0), screen_pos, 1)


# --- PLAYER CLASS & INVENTORY ---
class Player:
    """Player entity with movement, collision, inventory, and crafting systems."""

    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, TILE_SIZE * 0.8, TILE_SIZE * 1.8)
        self.vx = 0
        self.vy = 0
        self.speed = 5
        self.jump_power = -11
        self.gravity = 0.5
        self.on_ground = False

        # Inventory Storage: 27 slots (9 hotbar + 18 main)
        self.inventory = [AIR] * 27
        self.counts = [0] * 27
        self.selected_slot = 0

        # 2x2 Crafting Grid & Output
        self.craft_grid = [AIR] * 4
        self.craft_counts = [0] * 4
        self.craft_out_type = AIR
        self.craft_out_count = 0

        # Cursor Held Item (for inventory management)
        self.held_type = AIR
        self.held_count = 0

    def handle_input(self):
        """Process keyboard input for movement (WASD/Arrows + Space to jump)."""
        keys = pygame.key.get_pressed()
        self.vx = 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.vx = -self.speed
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.vx = self.speed
        if (keys[pygame.K_w] or keys[pygame.K_SPACE]) and self.on_ground:
            self.vy = self.jump_power
            self.on_ground = False

    def check_2x2_recipes(self):
        """Check crafting grid for valid recipes and update output."""
        # 1 Wood -> 4 Planks
        total_wood = sum(1 for i in range(4) if self.craft_grid[i] == WOOD)
        if total_wood == 1 and sum(1 for i in range(4) if self.craft_grid[i] != AIR) == 1:
            self.craft_out_type = PLANKS
            self.craft_out_count = 4
            return

        # 4 Wood -> 1 Workbench
        if self.craft_grid == [WOOD, WOOD, WOOD, WOOD]:
            self.craft_out_type = WORKBENCH
            self.craft_out_count = 1
            return

        # No valid recipe
        self.craft_out_type = AIR
        self.craft_out_count = 0

    def add_item(self, item_type, amount=1):
        for _ in range(amount):
            added = False
            for i in range(27):
                if self.inventory[i] == item_type:
                    self.counts[i] += 1
                    added = True
                    break
            if not added:
                for i in range(27):
                    if self.inventory[i] == AIR or self.counts[i] == 0:
                        self.inventory[i] = item_type
                        self.counts[i] = 1
                        added = True
                        break
            if not added:
                return False
        return True

    def update(self, world):
        self.rect.x += self.vx
        self.collide(self.vx, 0, world)

        self.vy += self.gravity
        self.rect.y += self.vy
        self.on_ground = False
        self.collide(0, self.vy, world)

    def collide(self, vx, vy, world):
        start_x = math.floor(self.rect.left / TILE_SIZE) - 1
        end_x = math.floor(self.rect.right / TILE_SIZE) + 2
        start_y = math.floor(self.rect.top / TILE_SIZE) - 1
        end_y = math.floor(self.rect.bottom / TILE_SIZE) + 2

        # Tiles with disabled collision
        passable_tiles = (AIR, NATURAL_WOOD, NATURAL_LEAVES)

        for y in range(start_y, end_y):
            for x in range(start_x, end_x):
                tile = world.get_tile(x, y)
                if tile not in passable_tiles:
                    tile_rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                    if self.rect.colliderect(tile_rect):
                        if vx > 0:
                            self.rect.right = tile_rect.left
                        if vx < 0:
                            self.rect.left = tile_rect.right
                        if vy > 0:
                            self.rect.bottom = tile_rect.top
                            self.vy = 0
                            self.on_ground = True
                        if vy < 0:
                            self.rect.top = tile_rect.bottom
                            self.vy = 0

    def draw(self, surface, camera):
        pygame.draw.rect(surface, COLOR_PLAYER, camera.apply(self.rect))


# --- MINECRAFT-STYLE INVENTORY UI ---
def draw_slot(surface, rect, item_type, count, font, is_selected=False):
    border_color = COLOR_HOTBAR_SELECT if is_selected else COLOR_UI_BORDER
    pygame.draw.rect(surface, COLOR_SLOT_BG, rect)
    pygame.draw.rect(surface, border_color, rect, 2 if is_selected else 1)

    if item_type != AIR and count > 0:
        pygame.draw.rect(surface, TILE_COLORS[item_type], (rect.x + 6, rect.y + 6, rect.w - 12, rect.h - 12))
        text = font.render(str(count), True, (255, 255, 255))
        surface.blit(text, (rect.right - text.get_width() - 3, rect.bottom - text.get_height() - 2))


def draw_minecraft_inventory(surface, player, font, mouse_pos):
    panel = pygame.Rect(SCREEN_WIDTH // 2 - 210, SCREEN_HEIGHT // 2 - 170, 420, 340)
    pygame.draw.rect(surface, COLOR_UI_BG, panel)
    pygame.draw.rect(surface, COLOR_UI_BORDER, panel, 2)

    title = font.render("INVENTORY & CRAFTING (E to Close)", True, (255, 255, 255))
    surface.blit(title, (panel.x + 15, panel.y + 12))

    slot_rects = {}

    start_x = panel.x + 20
    start_y = panel.y + 130
    for row in range(2):
        for col in range(9):
            idx = 9 + row * 9 + col
            r = pygame.Rect(start_x + col * 42, start_y + row * 42, 38, 38)
            draw_slot(surface, r, player.inventory[idx], player.counts[idx], font)
            slot_rects[("inv", idx)] = r

    hotbar_y = panel.y + 275
    for col in range(9):
        r = pygame.Rect(start_x + col * 42, hotbar_y, 38, 38)
        draw_slot(surface, r, player.inventory[col], player.counts[col], font, col == player.selected_slot)
        slot_rects[("inv", col)] = r

    craft_x = panel.x + 100
    craft_y = panel.y + 40
    for row in range(2):
        for col in range(2):
            idx = row * 2 + col
            r = pygame.Rect(craft_x + col * 44, craft_y + row * 44, 40, 40)
            draw_slot(surface, r, player.craft_grid[idx], player.craft_counts[idx], font)
            slot_rects[("craft", idx)] = r

    arrow = font.render("==>", True, (255, 255, 255))
    surface.blit(arrow, (craft_x + 98, craft_y + 30))

    out_r = pygame.Rect(craft_x + 140, craft_y + 22, 44, 44)
    draw_slot(surface, out_r, player.craft_out_type, player.craft_out_count, font)
    slot_rects[("out", 0)] = out_r

    if player.held_type != AIR and player.held_count > 0:
        mx, my = mouse_pos
        pygame.draw.rect(surface, TILE_COLORS[player.held_type], (mx - 15, my - 15, 30, 30))
        txt = font.render(str(player.held_count), True, (255, 255, 255))
        surface.blit(txt, (mx + 8, my + 8))

    return slot_rects


def draw_hotbar(surface, player, font):
    slot_size = 40
    slot_margin = 6
    num_slots = 9
    total_width = num_slots * (slot_size + slot_margin) + slot_margin
    start_x = (SCREEN_WIDTH - total_width) // 2
    start_y = SCREEN_HEIGHT - slot_size - 16

    bg_surface = pygame.Surface((total_width, slot_size + slot_margin * 2), pygame.SRCALPHA)
    bg_surface.fill(COLOR_UI_BG)
    surface.blit(bg_surface, (start_x, start_y - slot_margin))

    for i in range(num_slots):
        x = start_x + slot_margin + i * (slot_size + slot_margin)
        y = start_y
        rect = pygame.Rect(x, y, slot_size, slot_size)

        border_color = COLOR_HOTBAR_SELECT if i == player.selected_slot else COLOR_UI_BORDER
        border_width = 3 if i == player.selected_slot else 1

        pygame.draw.rect(surface, (20, 20, 20), rect)
        pygame.draw.rect(surface, border_color, rect, border_width)

        item = player.inventory[i]
        count = player.counts[i]
        if item != AIR and count > 0:
            icon_rect = pygame.Rect(x + 8, y + 8, slot_size - 16, slot_size - 16)
            pygame.draw.rect(surface, TILE_COLORS[item], icon_rect)

            text_surf = font.render(str(count), True, (255, 255, 255))
            surface.blit(text_surf,
                         (x + slot_size - text_surf.get_width() - 3, y + slot_size - text_surf.get_height() - 2))

        num_surf = font.render(str(i + 1), True, (180, 180, 180))
        surface.blit(num_surf, (x + 3, y + 2))


# --- MAIN LOOP ---
def main():
    pygame.init()
    font = pygame.font.SysFont(None, 20)
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Terraria Pygame - Passable Trees & Empty Start")
    clock = pygame.time.Clock()

    world = World()
    start_surface = world.get_surface_height(0)
    player = Player(0, (start_surface - 3) * TILE_SIZE)

    camera = Camera()
    item_drops = []
    show_inventory = False

    running = True
    while running:
        clock.tick(FPS)
        mouse_pos = pygame.mouse.get_pos()

        # Event Handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_e:
                    show_inventory = not show_inventory
                if pygame.K_1 <= event.key <= pygame.K_9:
                    player.selected_slot = event.key - pygame.K_1

            if event.type == pygame.MOUSEWHEEL:
                player.selected_slot = (player.selected_slot - event.y) % 9

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if show_inventory:
                    slot_rects = draw_minecraft_inventory(screen, player, font, mouse_pos)
                    for key, rect in slot_rects.items():
                        if rect.collidepoint(mouse_pos):
                            stype, idx = key

                            if stype == "inv":
                                player.inventory[idx], player.held_type = player.held_type, player.inventory[idx]
                                player.counts[idx], player.held_count = player.held_count, player.counts[idx]

                            elif stype == "craft":
                                player.craft_grid[idx], player.held_type = player.held_type, player.craft_grid[idx]
                                player.craft_counts[idx], player.held_count = player.held_count, player.craft_counts[
                                    idx]
                                player.check_2x2_recipes()

                            elif stype == "out" and player.craft_out_type != AIR:
                                if player.held_type == AIR or player.held_type == player.craft_out_type:
                                    player.held_type = player.craft_out_type
                                    player.held_count += player.craft_out_count

                                    for c_i in range(4):
                                        if player.craft_grid[c_i] != AIR:
                                            player.craft_counts[c_i] -= 1
                                            if player.craft_counts[c_i] <= 0:
                                                player.craft_grid[c_i] = AIR
                                    player.check_2x2_recipes()

                else:
                    world_x = mouse_pos[0] + camera.x
                    world_y = mouse_pos[1] + camera.y
                    grid_x = math.floor(world_x / TILE_SIZE)
                    grid_y = math.floor(world_y / TILE_SIZE)
                    world.hit_tile(grid_x, grid_y, item_drops)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and not show_inventory:
                world_x = mouse_pos[0] + camera.x
                world_y = mouse_pos[1] + camera.y
                grid_x = math.floor(world_x / TILE_SIZE)
                grid_y = math.floor(world_y / TILE_SIZE)

                selected_item = player.inventory[player.selected_slot]
                selected_count = player.counts[player.selected_slot]

                if selected_item != AIR and selected_count > 0:
                    target_rect = pygame.Rect(grid_x * TILE_SIZE, grid_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                    if not player.rect.colliderect(target_rect) and world.get_tile(grid_x, grid_y) == AIR:
                        # Placing Wood or Leaves sets them to solid variants
                        world.set_tile(grid_x, grid_y, selected_item)
                        player.counts[player.selected_slot] -= 1
                        if player.counts[player.selected_slot] == 0:
                            player.inventory[player.selected_slot] = AIR

        # State Updates
        player.handle_input()
        player.update(world)
        camera.update(player)
        world.update_furnaces()

        for drop in item_drops[:]:
            drop.update(player, world)
            if player.rect.colliderect(drop.rect):
                if player.add_item(drop.item_type):
                    item_drops.remove(drop)

        # Rendering
        screen.fill(COLOR_SKY)

        min_tile_x = math.floor(camera.x / TILE_SIZE) - 1
        max_tile_x = math.floor((camera.x + SCREEN_WIDTH) / TILE_SIZE) + 2
        min_tile_y = math.floor(camera.y / TILE_SIZE) - 1
        max_tile_y = math.floor((camera.y + SCREEN_HEIGHT) / TILE_SIZE) + 2

        for tile_y in range(min_tile_y, max_tile_y):
            for tile_x in range(min_tile_x, max_tile_x):
                tile = world.get_tile(tile_x, tile_y)
                if tile != AIR:
                    tile_rect = pygame.Rect(tile_x * TILE_SIZE, tile_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                    pygame.draw.rect(screen, TILE_COLORS[tile], camera.apply(tile_rect))

        for drop in item_drops:
            drop.draw(screen, camera)

        player.draw(screen, camera)
        draw_hotbar(screen, player, font)

        if show_inventory:
            draw_minecraft_inventory(screen, player, font, mouse_pos)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()