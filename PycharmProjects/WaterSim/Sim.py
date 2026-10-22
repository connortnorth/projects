import pygame
import sys

pygame.init()

# Display & Grid Settings
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
TILE_SIZE = 20
GRID_COLS = SCREEN_WIDTH // TILE_SIZE
GRID_ROWS = SCREEN_HEIGHT // TILE_SIZE
FPS = 60

# Tile ID Constants
AIR = 0
DIRT = 1
GRASS = 2
STONE = 3
WATER = 4

MAX_WATER_LEVEL = 7

# Base Colors
COLORS = {
    AIR: (135, 206, 235),
    DIRT: (134, 96, 67),
    GRASS: (86, 125, 70),
    STONE: (112, 128, 144),
}

# Distinct blue shades for liquids
SOURCE_WATER_COLOR = (15, 60, 180)  # Darker blue for source blocks

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Minecraft-Style Leveled Water Simulation")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 24)


class Cell:
    """Represents a single tile in the grid with water level metadata."""

    def __init__(self, tile_type=AIR, level=0, is_source=False):
        self.type = tile_type
        self.level = level  # 1 to 7 for water depth/strength
        self.is_source = is_source  # True if manually placed by player


def generate_world():
    grid = [[Cell(AIR) for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
    grass_y = 15
    dirt_depth = 5

    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            if r == grass_y:
                grid[r][c] = Cell(GRASS)
            elif grass_y < r <= grass_y + dirt_depth:
                grid[r][c] = Cell(DIRT)
            elif r > grass_y + dirt_depth:
                grid[r][c] = Cell(STONE)
    return grid


def update_minecraft_water(grid):
    """
    Minecraft-style fluid logic:
    1. Carry forward active source blocks.
    2. Calculate downward flow and horizontal flow (both source and non-source blocks).
    3. Iterate horizontal spreading until equilibrium is reached.
    """
    new_levels = [[0 for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]
    new_sources = [[False for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]

    # 1. Retain existing active source blocks
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            if grid[r][c].type == WATER and grid[r][c].is_source:
                new_levels[r][c] = MAX_WATER_LEVEL
                new_sources[r][c] = True

    # 2. Propagate downward streams first
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            current_lvl = new_levels[r][c]
            if current_lvl <= 0:
                continue

            # Check if there is space directly below
            can_fall_down = (r + 1 < GRID_ROWS) and (grid[r + 1][c].type in (AIR, WATER))

            # Downward Flow: Full strength transfers directly down
            if can_fall_down:
                new_levels[r + 1][c] = MAX_WATER_LEVEL

    # 3. Horizontal Spreading with iterative cascade
    changed = True
    while changed:
        changed = False
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                current_lvl = new_levels[r][c]
                if current_lvl <= 0:
                    continue

                # Check if there is space directly below
                can_fall_down = (r + 1 < GRID_ROWS) and (grid[r + 1][c].type in (AIR, WATER))

                # Horizontal Spreading: Occurs when supported by ground/blocks underneath
                if not can_fall_down:
                    spread_lvl = current_lvl - 1
                    if spread_lvl > 0:
                        for dc in (-1, 1):
                            nc = c + dc
                            if 0 <= nc < GRID_COLS and grid[r][nc].type in (AIR, WATER):
                                if spread_lvl > new_levels[r][nc]:
                                    new_levels[r][nc] = spread_lvl
                                    changed = True

    # 4. Apply calculated states back to grid
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            if grid[r][c].type in (AIR, WATER):
                lvl = new_levels[r][c]
                if lvl > 0:
                    grid[r][c].type = WATER
                    grid[r][c].level = lvl
                    grid[r][c].is_source = new_sources[r][c]
                else:
                    grid[r][c].type = AIR
                    grid[r][c].level = 0
                    grid[r][c].is_source = False


def draw_grid(surface, grid):
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            cell = grid[r][c]

            if cell.type == WATER:
                # Calculate dynamic water height based on level (1-7 scale)
                water_height = int(TILE_SIZE * (cell.level / MAX_WATER_LEVEL))
                y_offset = TILE_SIZE - water_height

                rect = pygame.Rect(
                    c * TILE_SIZE,
                    r * TILE_SIZE + y_offset,
                    TILE_SIZE,
                    water_height
                )

                # Darker blue for source blocks; dynamic lighter blue for flowing water
                if cell.is_source:
                    water_color = SOURCE_WATER_COLOR
                else:
                    blue_shade = max(140, 255 - (MAX_WATER_LEVEL - cell.level) * 18)
                    water_color = (60, 140, blue_shade)

                pygame.draw.rect(surface, water_color, rect)

            elif cell.type != AIR:
                rect = pygame.Rect(c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                pygame.draw.rect(surface, COLORS[cell.type], rect)
                pygame.draw.rect(surface, (0, 0, 0), rect, 1)


def main():
    world_grid = generate_world()
    selected_block = DIRT
    block_names = {DIRT: "Dirt", STONE: "Stone", WATER: "Water Source"}

    # Physics frame update timer increased to 250ms for slower, clearer water updates
    WATER_UPDATE_EVENT = pygame.USEREVENT + 1
    pygame.time.set_timer(WATER_UPDATE_EVENT, 250)

    running = True
    while running:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == WATER_UPDATE_EVENT:
                update_minecraft_water(world_grid)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    selected_block = DIRT
                elif event.key == pygame.K_2:
                    selected_block = STONE
                elif event.key == pygame.K_3:
                    selected_block = WATER

        mouse_buttons = pygame.mouse.get_pressed()
        mx, my = pygame.mouse.get_pos()
        col, row = mx // TILE_SIZE, my // TILE_SIZE

        if 0 <= col < GRID_COLS and 0 <= row < GRID_ROWS:
            if mouse_buttons[0]:  # Mine block / Remove Source
                world_grid[row][col] = Cell(AIR)
            elif mouse_buttons[2]:  # Place block
                if world_grid[row][col].type in (AIR, WATER):
                    if selected_block == WATER:
                        world_grid[row][col] = Cell(WATER, level=MAX_WATER_LEVEL, is_source=True)
                    else:
                        world_grid[row][col] = Cell(selected_block)

        screen.fill(COLORS[AIR])
        draw_grid(screen, world_grid)

        # UI Overlay
        ui_text = f"Selected [1-3]: {block_names[selected_block]} | Left-Click: Mine | Right-Click: Place"
        txt = font.render(ui_text, True, (255, 255, 255))
        pygame.draw.rect(screen, (0, 0, 0), (8, 8, txt.get_width() + 8, txt.get_height() + 4))
        screen.blit(txt, (12, 10))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()