import sys
import math
import random
import urllib.request
import threading
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
import pygame
from collections import defaultdict

# --- CONFIGURATION & CONSTANTS ---
# (Pygame init and display setup are inside __main__ to keep worker processes headless)

# Colors
COLOR_BG = (18, 18, 19)
COLOR_TEXT = (255, 255, 255)
COLOR_TEXT_DIM = (160, 160, 160)
COLOR_CORRECT = (83, 141, 78)  # Green
COLOR_PRESENT = (181, 159, 59)  # Yellow
COLOR_ABSENT = (58, 58, 60)  # Dark Gray
COLOR_BORDER_EMPTY = (58, 58, 60)
COLOR_BORDER_FILLED = (86, 87, 88)
COLOR_HIGHLIGHT = (100, 200, 255)

COLOR_BUTTON_BG = (40, 40, 45)
COLOR_BUTTON_HOVER = (60, 60, 70)
COLOR_OVERLAY_BG = (28, 28, 30)

WIDTH, HEIGHT = 1000, 850

# Grid Layout
ROWS = 6
COLS = 5
BOX_SIZE = 48
GAP = 6

GRID_WIDTH = COLS * BOX_SIZE + (COLS - 1) * GAP  # 264px per grid
BOARD_GAP = 80  # Space between grids

TOTAL_BOARDS_WIDTH = (2 * GRID_WIDTH) + BOARD_GAP
HUMAN_START_X = (WIDTH - TOTAL_BOARDS_WIDTH) // 2  # 196px
AI_START_X = HUMAN_START_X + GRID_WIDTH + BOARD_GAP  # 540px
START_Y = 190

# Global Config Defaults
CUSTOM_FIRST_WORD = "ADIEU"
CUSTOM_SIM_COUNT = 1000


# --- WORD LIST LOADING ---
def load_full_word_list():
    """Downloads the official Wordle valid word dictionary."""
    url = "https://raw.githubusercontent.com/tabatkins/wordle-list/main/words"
    try:
        print("Fetching official Wordle dictionary...")
        with urllib.request.urlopen(url, timeout=5) as response:
            words = response.read().decode('utf-8').splitlines()
            return set(word.upper() for word in words if len(word) == 5)
    except Exception as e:
        print(f"Network error loading dictionary ({e}). Falling back to built-in list.")
        fallback = [
            "ADIEU", "CRANE", "SLATE", "AUDIO", "RAISE", "ROAST", "PLANT", "SNAKE",
            "DRIVE", "PIXEL", "LOGIC", "CLONE", "TRAIN", "STORM", "FLAME", "SHARK"
        ]
        return set(fallback)


VALID_WORDS = load_full_word_list()
WORD_LIST = list(VALID_WORDS)


# --- HEADLESS WORKER & AI MATH FUNCTIONS ---

def calculate_feedback(guess, hidden_target):
    """Calculates standard Wordle feedback (0=Gray, 1=Yellow, 2=Green)."""
    res = [0] * COLS
    target_chars = list(hidden_target)

    # Pass 1: Green
    for i in range(COLS):
        if guess[i] == hidden_target[i]:
            res[i] = 2
            target_chars[i] = None

    # Pass 2: Yellow
    for i in range(COLS):
        if res[i] == 0 and guess[i] in target_chars:
            res[i] = 1
            target_chars[target_chars.index(guess[i])] = None

    return tuple(res)


def get_possible_candidates(dictionary, history):
    """Filters candidate target words using past feedback."""
    candidates = list(dictionary)
    for past_guess, actual_pattern in history:
        candidates = [
            word for word in candidates
            if calculate_feedback(past_guess, word) == actual_pattern
        ]
    return candidates


def calculate_entropy(guess, candidate_pool):
    """Calculates Expected Information Gain (Entropy) in bits."""
    if len(candidate_pool) <= 1:
        return 0.0

    pattern_counts = defaultdict(int)
    total_candidates = len(candidate_pool)

    for candidate in candidate_pool:
        pattern = calculate_feedback(guess, candidate)
        pattern_counts[pattern] += 1

    entropy = 0.0
    for count in pattern_counts.values():
        p = count / total_candidates
        entropy -= p * math.log2(p)

    return entropy


def compute_top_recommendations(dictionary, history, top_n=5, first_word="ADIEU"):
    """Computes top recommended guesses for a given player's feedback history."""
    if not history:
        turn_1_recs = [
            (first_word, 5.82),
            ("RAISE", 5.88),
            ("SLATE", 5.87),
            ("CRANE", 5.74),
            ("AUDIO", 5.65)
        ]
        unique_recs = []
        seen = set()
        for w, s in turn_1_recs:
            if w not in seen:
                unique_recs.append((w, s))
                seen.add(w)
        return unique_recs[:top_n], list(dictionary)

    possible = get_possible_candidates(dictionary, history)

    if not possible:
        return [], possible

    if len(possible) <= 2:
        return [(w, 0.0) for w in possible[:top_n]], possible

    sample_pool = possible if len(possible) <= 250 else random.sample(possible, 250)

    scored_words = []
    for word in sample_pool:
        info_gain = calculate_entropy(word, possible)
        scored_words.append((word, info_gain))

    scored_words.sort(key=lambda x: x[1], reverse=True)
    return scored_words[:top_n], possible


def get_ai_best_guess(dictionary, history, first_word="ADIEU"):
    """Gets the single best guess for the AI opponent."""
    if not history:
        return first_word

    top_recs, _ = compute_top_recommendations(dictionary, history, top_n=1, first_word=first_word)
    if top_recs:
        return top_recs[0][0]
    return random.choice(dictionary)


def simulate_single_target(target, word_list, first_word):
    """Pure headless worker task that runs independently on a single core."""
    sim_history = []
    for turn in range(1, 7):
        guess = get_ai_best_guess(word_list, sim_history, first_word=first_word)
        feedback = calculate_feedback(guess, target)
        sim_history.append((guess, feedback))

        if guess == target:
            return turn
    return "Fail"


# --- MULTI-CORE SIMULATION THREAD ---

def parallel_brute_force_simulation(sample_size=1000, first_word="ADIEU"):
    """Distributes target simulations across ALL CPU cores using ProcessPoolExecutor."""
    global sim_progress, ai_sim_stats, is_simulating, show_stats_overlay, message

    targets = random.sample(WORD_LIST, min(sample_size, len(WORD_LIST)))
    total_count = len(targets)
    distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, "Fail": 0}
    total_turns = 0
    wins = 0

    cpu_cores = os.cpu_count() or 4
    completed_count = 0

    with ProcessPoolExecutor(max_workers=cpu_cores) as executor:
        futures = [executor.submit(simulate_single_target, target, WORD_LIST, first_word) for target in targets]

        for future in as_completed(futures):
            result_turn = future.result()
            distribution[result_turn] += 1

            if result_turn != "Fail":
                total_turns += result_turn
                wins += 1

            completed_count += 1
            sim_progress = completed_count / total_count

    avg_guesses = (total_turns / wins) if wins > 0 else 0.0
    win_rate = (wins / total_count) * 100

    ai_sim_stats = {
        "total_simulated": total_count,
        "wins": wins,
        "win_rate": win_rate,
        "avg_guesses": avg_guesses,
        "distribution": distribution,
        "cores_used": cpu_cores,
        "first_word": first_word
    }

    is_simulating = False
    show_stats_overlay = True
    message = f"Simulation complete ({total_count} words) using {cpu_cores} CPU cores!"


# --- DRAWING FUNCTIONS ---

def draw_top_panels(screen, fonts):
    """Renders Recommendations and Target Word Header."""
    FONT_LETTER, FONT_MSG, FONT_INFO, FONT_STATS_TITLE = fonts

    left_x = 25
    user_rec_title = FONT_INFO.render("YOUR TOP 5 GUESSES:", True, COLOR_HIGHLIGHT)
    screen.blit(user_rec_title, (left_x, 15))

    if human_top_recs:
        for idx, (word, bits) in enumerate(human_top_recs):
            is_possible = word in remaining_human_pool
            color = COLOR_CORRECT if is_possible else COLOR_TEXT_DIM
            text = f"{idx + 1}. {word} ({bits:.2f} bits)"
            surf = FONT_INFO.render(text, True, color)
            screen.blit(surf, (left_x, 35 + idx * 18))
    else:
        surf = FONT_INFO.render("No recommendations", True, COLOR_TEXT_DIM)
        screen.blit(surf, (left_x, 35))

    title_surface = FONT_LETTER.render("WORDLE AI", True, COLOR_TEXT)
    title_rect = title_surface.get_rect(center=(WIDTH // 2, 35))
    screen.blit(title_surface, title_rect)

    target_label = FONT_INFO.render("GOAL WORD (DEBUG):", True, COLOR_HIGHLIGHT)
    target_val = FONT_LETTER.render(TARGET_WORD, True, COLOR_CORRECT)
    lbl_rect = target_label.get_rect(center=(WIDTH // 2, 70))
    val_rect = target_val.get_rect(center=(WIDTH // 2, 95))
    screen.blit(target_label, lbl_rect)
    screen.blit(target_val, val_rect)

    right_x = WIDTH - 200
    ai_rec_title = FONT_INFO.render("AI TOP 5 GUESSES:", True, COLOR_HIGHLIGHT)
    screen.blit(ai_rec_title, (right_x, 15))

    if ai_top_recs:
        for idx, (word, bits) in enumerate(ai_top_recs):
            is_possible = word in remaining_ai_pool
            color = COLOR_CORRECT if is_possible else COLOR_TEXT_DIM
            text = f"{idx + 1}. {word} ({bits:.2f} bits)"
            surf = FONT_INFO.render(text, True, color)
            screen.blit(surf, (right_x, 35 + idx * 18))
    else:
        surf = FONT_INFO.render("No recommendations", True, COLOR_TEXT_DIM)
        screen.blit(surf, (right_x, 35))

    h_title = FONT_INFO.render("YOUR BOARD", True, COLOR_HIGHLIGHT)
    h_rect = h_title.get_rect(center=(HUMAN_START_X + GRID_WIDTH // 2, 165))
    screen.blit(h_title, h_rect)

    a_title = FONT_INFO.render("AI OPPONENT BOARD", True, COLOR_HIGHLIGHT)
    a_rect = a_title.get_rect(center=(AI_START_X + GRID_WIDTH // 2, 165))
    screen.blit(a_title, a_rect)


def draw_grid(screen, fonts, start_x, grid_data):
    """Renders a 6x5 Wordle board."""
    FONT_LETTER = fonts[0]
    for r in range(ROWS):
        for c in range(COLS):
            x = start_x + c * (BOX_SIZE + GAP)
            y = START_Y + r * (BOX_SIZE + GAP)
            letter, status = grid_data[r][c]

            rect = pygame.Rect(x, y, BOX_SIZE, BOX_SIZE)

            if status == 'correct':
                bg_color, border_color = COLOR_CORRECT, COLOR_CORRECT
            elif status == 'present':
                bg_color, border_color = COLOR_PRESENT, COLOR_PRESENT
            elif status == 'absent':
                bg_color, border_color = COLOR_ABSENT, COLOR_ABSENT
            else:
                bg_color = COLOR_BG
                border_color = COLOR_BORDER_FILLED if letter else COLOR_BORDER_EMPTY

            pygame.draw.rect(screen, bg_color, rect, border_radius=4)
            if status in ('empty', 'filled'):
                pygame.draw.rect(screen, border_color, rect, width=2, border_radius=4)

            if letter:
                text_surface = FONT_LETTER.render(letter, True, COLOR_TEXT)
                text_rect = text_surface.get_rect(center=rect.center)
                screen.blit(text_surface, text_rect)


def draw_footer(screen, fonts, mouse_pos, sim_btn_rect, word_btn_rect, count_btn_rect):
    """Renders status message, action buttons, and progress bar."""
    FONT_MSG, FONT_INFO = fonts[1], fonts[2]

    msg_surface = FONT_MSG.render(message, True, COLOR_TEXT)
    msg_rect = msg_surface.get_rect(center=(WIDTH // 2, HEIGHT - 115))
    screen.blit(msg_surface, msg_rect)

    if is_simulating:
        bar_track = pygame.Rect(WIDTH // 2 - 175, HEIGHT - 75, 350, 26)
        pygame.draw.rect(screen, COLOR_BUTTON_BG, bar_track, border_radius=6)
        pygame.draw.rect(screen, COLOR_BORDER_FILLED, bar_track, width=1, border_radius=6)

        fill_width = int(350 * sim_progress)
        if fill_width > 0:
            bar_fill = pygame.Rect(WIDTH // 2 - 175, HEIGHT - 75, fill_width, 26)
            pygame.draw.rect(screen, COLOR_CORRECT, bar_fill, border_radius=6)

        cores_count = os.cpu_count() or 4
        pct_text = FONT_INFO.render(
            f"Simulating ({CUSTOM_SIM_COUNT} words on {cores_count} cores)... {int(sim_progress * 100)}%", True,
            COLOR_TEXT)
        pct_rect = pct_text.get_rect(center=bar_track.center)
        screen.blit(pct_text, pct_rect)
    else:
        # Run Simulation Button
        btn1_color = COLOR_BUTTON_HOVER if sim_btn_rect.collidepoint(mouse_pos) else COLOR_BUTTON_BG
        pygame.draw.rect(screen, btn1_color, sim_btn_rect, border_radius=6)
        pygame.draw.rect(screen, COLOR_HIGHLIGHT, sim_btn_rect, width=2, border_radius=6)

        btn1_text = FONT_INFO.render("RUN AI SIMULATION", True, COLOR_TEXT)
        btn1_rect = btn1_text.get_rect(center=sim_btn_rect.center)
        screen.blit(btn1_text, btn1_rect)

        # Change First Word Button
        btn2_color = COLOR_BUTTON_HOVER if word_btn_rect.collidepoint(mouse_pos) else COLOR_BUTTON_BG
        pygame.draw.rect(screen, btn2_color, word_btn_rect, border_radius=6)
        pygame.draw.rect(screen, COLOR_HIGHLIGHT, word_btn_rect, width=2, border_radius=6)

        btn2_text = FONT_INFO.render(f"FIRST WORD: {CUSTOM_FIRST_WORD}", True, COLOR_TEXT)
        btn2_rect = btn2_text.get_rect(center=word_btn_rect.center)
        screen.blit(btn2_text, btn2_rect)

        # Change Word Count Button
        btn3_color = COLOR_BUTTON_HOVER if count_btn_rect.collidepoint(mouse_pos) else COLOR_BUTTON_BG
        pygame.draw.rect(screen, btn3_color, count_btn_rect, border_radius=6)
        pygame.draw.rect(screen, COLOR_HIGHLIGHT, count_btn_rect, width=2, border_radius=6)

        btn3_text = FONT_INFO.render(f"SIM WORDS: {CUSTOM_SIM_COUNT}", True, COLOR_TEXT)
        btn3_rect = btn3_text.get_rect(center=count_btn_rect.center)
        screen.blit(btn3_text, btn3_rect)


def draw_first_word_modal(screen, fonts, mouse_pos, current_input, close_rect, confirm_rect):
    """Renders modal to change AI starting word."""
    FONT_LETTER, FONT_INFO, FONT_STATS_TITLE = fonts[0], fonts[2], fonts[3]

    overlay = pygame.Surface((WIDTH, HEIGHT))
    overlay.set_alpha(200)
    overlay.fill((0, 0, 0))
    screen.blit(overlay, (0, 0))

    dialog_rect = pygame.Rect(WIDTH // 2 - 200, HEIGHT // 2 - 120, 400, 240)
    pygame.draw.rect(screen, COLOR_OVERLAY_BG, dialog_rect, border_radius=12)
    pygame.draw.rect(screen, COLOR_HIGHLIGHT, dialog_rect, width=2, border_radius=12)

    t_surf = FONT_STATS_TITLE.render("SET AI FIRST WORD", True, COLOR_TEXT)
    t_rect = t_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 80))
    screen.blit(t_surf, t_rect)

    input_box = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 - 30, 200, 40)
    pygame.draw.rect(screen, COLOR_BG, input_box, border_radius=6)
    pygame.draw.rect(screen, COLOR_BORDER_FILLED, input_box, width=2, border_radius=6)

    in_surf = FONT_LETTER.render(current_input, True, COLOR_TEXT)
    in_rect = in_surf.get_rect(center=input_box.center)
    screen.blit(in_surf, in_rect)

    c_btn_color = COLOR_BUTTON_HOVER if confirm_rect.collidepoint(mouse_pos) else COLOR_BUTTON_BG
    pygame.draw.rect(screen, c_btn_color, confirm_rect, border_radius=6)
    pygame.draw.rect(screen, COLOR_CORRECT, confirm_rect, width=1, border_radius=6)
    conf_text = FONT_INFO.render("SET WORD", True, COLOR_TEXT)
    conf_rect = conf_text.get_rect(center=confirm_rect.center)
    screen.blit(conf_text, conf_rect)

    can_btn_color = COLOR_BUTTON_HOVER if close_rect.collidepoint(mouse_pos) else COLOR_BUTTON_BG
    pygame.draw.rect(screen, can_btn_color, close_rect, border_radius=6)
    pygame.draw.rect(screen, COLOR_HIGHLIGHT, close_rect, width=1, border_radius=6)
    can_text = FONT_INFO.render("CANCEL", True, COLOR_TEXT)
    can_rect = can_text.get_rect(center=close_rect.center)
    screen.blit(can_text, can_rect)


def draw_count_modal(screen, fonts, mouse_pos, current_input, close_rect, confirm_rect):
    """Renders modal to change simulation word count."""
    FONT_LETTER, FONT_INFO, FONT_STATS_TITLE = fonts[0], fonts[2], fonts[3]

    overlay = pygame.Surface((WIDTH, HEIGHT))
    overlay.set_alpha(200)
    overlay.fill((0, 0, 0))
    screen.blit(overlay, (0, 0))

    dialog_rect = pygame.Rect(WIDTH // 2 - 200, HEIGHT // 2 - 120, 400, 240)
    pygame.draw.rect(screen, COLOR_OVERLAY_BG, dialog_rect, border_radius=12)
    pygame.draw.rect(screen, COLOR_HIGHLIGHT, dialog_rect, width=2, border_radius=12)

    t_surf = FONT_STATS_TITLE.render("SET SIMULATION COUNT", True, COLOR_TEXT)
    t_rect = t_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 80))
    screen.blit(t_surf, t_rect)

    input_box = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 - 30, 200, 40)
    pygame.draw.rect(screen, COLOR_BG, input_box, border_radius=6)
    pygame.draw.rect(screen, COLOR_BORDER_FILLED, input_box, width=2, border_radius=6)

    in_surf = FONT_LETTER.render(current_input, True, COLOR_TEXT)
    in_rect = in_surf.get_rect(center=input_box.center)
    screen.blit(in_surf, in_rect)

    c_btn_color = COLOR_BUTTON_HOVER if confirm_rect.collidepoint(mouse_pos) else COLOR_BUTTON_BG
    pygame.draw.rect(screen, c_btn_color, confirm_rect, border_radius=6)
    pygame.draw.rect(screen, COLOR_CORRECT, confirm_rect, width=1, border_radius=6)
    conf_text = FONT_INFO.render("SET COUNT", True, COLOR_TEXT)
    conf_rect = conf_text.get_rect(center=confirm_rect.center)
    screen.blit(conf_text, conf_rect)

    can_btn_color = COLOR_BUTTON_HOVER if close_rect.collidepoint(mouse_pos) else COLOR_BUTTON_BG
    pygame.draw.rect(screen, can_btn_color, close_rect, border_radius=6)
    pygame.draw.rect(screen, COLOR_HIGHLIGHT, close_rect, width=1, border_radius=6)
    can_text = FONT_INFO.render("CANCEL", True, COLOR_TEXT)
    can_rect = can_text.get_rect(center=close_rect.center)
    screen.blit(can_text, can_rect)


def draw_stats_modal(screen, fonts, mouse_pos, close_rect):
    """Renders statistical dialog window."""
    FONT_INFO, FONT_STATS_TITLE = fonts[2], fonts[3]

    overlay = pygame.Surface((WIDTH, HEIGHT))
    overlay.set_alpha(200)
    overlay.fill((0, 0, 0))
    screen.blit(overlay, (0, 0))

    dialog_rect = pygame.Rect(WIDTH // 2 - 260, HEIGHT // 2 - 230, 520, 460)
    pygame.draw.rect(screen, COLOR_OVERLAY_BG, dialog_rect, border_radius=12)
    pygame.draw.rect(screen, COLOR_HIGHLIGHT, dialog_rect, width=2, border_radius=12)

    t_surf = FONT_STATS_TITLE.render("AI SOLVER STATISTICS", True, COLOR_TEXT)
    t_rect = t_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 190))
    screen.blit(t_surf, t_rect)

    if ai_sim_stats:
        summary_txt = f"First Word: {ai_sim_stats['first_word']} | Words: {ai_sim_stats['total_simulated']}"
        s_surf = FONT_INFO.render(summary_txt, True, COLOR_HIGHLIGHT)
        s_rect = s_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 155))
        screen.blit(s_surf, s_rect)

        sub_txt = f"Win Rate: {ai_sim_stats['win_rate']:.1f}%  |  Avg Guesses: {ai_sim_stats['avg_guesses']:.2f}"
        sub_surf = FONT_INFO.render(sub_txt, True, COLOR_TEXT)
        sub_rect = sub_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 132))
        screen.blit(sub_surf, sub_rect)

        dist = ai_sim_stats["distribution"]
        max_val = max(max(dist.values()), 1)
        start_y = HEIGHT // 2 - 95

        for idx, key in enumerate([1, 2, 3, 4, 5, 6, "Fail"]):
            count = dist[key]
            bar_pct = count / max_val
            bar_width = int(bar_pct * 300)

            lbl_txt = f"{key}:" if key != "Fail" else "X:"
            l_surf = FONT_INFO.render(lbl_txt, True, COLOR_TEXT)
            screen.blit(l_surf, (WIDTH // 2 - 180, start_y + idx * 34))

            bar_rect = pygame.Rect(WIDTH // 2 - 150, start_y + idx * 34, max(bar_width, 20), 22)
            bar_color = COLOR_ABSENT if key == "Fail" else COLOR_CORRECT
            pygame.draw.rect(screen, bar_color, bar_rect, border_radius=4)

            v_surf = FONT_INFO.render(str(count), True, COLOR_TEXT)
            screen.blit(v_surf, (WIDTH // 2 - 140 + max(bar_width, 20), start_y + idx * 34 + 2))

    c_btn_color = COLOR_BUTTON_HOVER if close_rect.collidepoint(mouse_pos) else COLOR_BUTTON_BG
    pygame.draw.rect(screen, c_btn_color, close_rect, border_radius=6)
    pygame.draw.rect(screen, COLOR_HIGHLIGHT, close_rect, width=1, border_radius=6)

    c_text = FONT_INFO.render("CLOSE", True, COLOR_TEXT)
    c_rect = c_text.get_rect(center=close_rect.center)
    screen.blit(c_text, c_rect)


# --- MAIN ENTRY POINT ---

if __name__ == "__main__":
    pygame.init()
    SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Wordle: Human vs. AI (Multi-Core Headless Simulator)")

    FONT_LETTER = pygame.font.SysFont("Helvetica", 28, bold=True)
    FONT_MSG = pygame.font.SysFont("Helvetica", 18, bold=True)
    FONT_INFO = pygame.font.SysFont("Helvetica", 13, bold=True)
    FONT_STATS_TITLE = pygame.font.SysFont("Helvetica", 24, bold=True)
    FONTS = (FONT_LETTER, FONT_MSG, FONT_INFO, FONT_STATS_TITLE)

    TARGET_WORD = random.choice(WORD_LIST)

    human_grid = [[["", 'empty'] for _ in range(COLS)] for _ in range(ROWS)]
    ai_grid = [[["", 'empty'] for _ in range(COLS)] for _ in range(ROWS)]

    current_row = 0
    current_col = 0

    human_won = False
    ai_won = False
    game_over = False
    message = f"Dictionary loaded ({len(VALID_WORDS):,} words)! Enter your guess."

    human_history = []
    ai_history = []

    is_simulating = False
    sim_progress = 0.0
    show_stats_overlay = False
    show_word_modal = False
    show_count_modal = False
    custom_word_input = ""
    custom_count_input = ""
    ai_sim_stats = None

    # Bottom Buttons Layout
    SIMULATE_BTN_RECT = pygame.Rect(WIDTH // 2 - 275, HEIGHT - 75, 170, 36)
    CHANGE_WORD_BTN_RECT = pygame.Rect(WIDTH // 2 - 90, HEIGHT - 75, 180, 36)
    CHANGE_COUNT_BTN_RECT = pygame.Rect(WIDTH // 2 + 105, HEIGHT - 75, 170, 36)

    CLOSE_STATS_BTN_RECT = pygame.Rect(WIDTH // 2 - 60, HEIGHT // 2 + 180, 120, 36)
    CONFIRM_MODAL_BTN_RECT = pygame.Rect(WIDTH // 2 + 10, HEIGHT // 2 + 40, 100, 32)
    CANCEL_MODAL_BTN_RECT = pygame.Rect(WIDTH // 2 - 110, HEIGHT // 2 + 40, 100, 32)

    human_top_recs, remaining_human_pool = compute_top_recommendations(WORD_LIST, human_history,
                                                                       first_word=CUSTOM_FIRST_WORD)
    ai_top_recs, remaining_ai_pool = compute_top_recommendations(WORD_LIST, ai_history, first_word=CUSTOM_FIRST_WORD)

    clock = pygame.time.Clock()

    while True:
        mouse_pos = pygame.mouse.get_pos()
        SCREEN.fill(COLOR_BG)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if show_stats_overlay:
                    if CLOSE_STATS_BTN_RECT.collidepoint(mouse_pos):
                        show_stats_overlay = False
                elif show_word_modal:
                    if CANCEL_MODAL_BTN_RECT.collidepoint(mouse_pos):
                        show_word_modal = False
                        custom_word_input = ""
                    elif CONFIRM_MODAL_BTN_RECT.collidepoint(mouse_pos):
                        if len(custom_word_input) == 5 and custom_word_input in VALID_WORDS:
                            CUSTOM_FIRST_WORD = custom_word_input
                            show_word_modal = False
                            custom_word_input = ""
                            message = f"AI first word updated to '{CUSTOM_FIRST_WORD}'!"
                            human_top_recs, remaining_human_pool = compute_top_recommendations(WORD_LIST, human_history,
                                                                                               first_word=CUSTOM_FIRST_WORD)
                            ai_top_recs, remaining_ai_pool = compute_top_recommendations(WORD_LIST, ai_history,
                                                                                         first_word=CUSTOM_FIRST_WORD)
                        else:
                            message = "Invalid 5-letter word!"
                elif show_count_modal:
                    if CANCEL_MODAL_BTN_RECT.collidepoint(mouse_pos):
                        show_count_modal = False
                        custom_count_input = ""
                    elif CONFIRM_MODAL_BTN_RECT.collidepoint(mouse_pos):
                        if custom_count_input.isdigit() and int(custom_count_input) > 0:
                            CUSTOM_SIM_COUNT = min(int(custom_count_input), len(VALID_WORDS))
                            show_count_modal = False
                            custom_count_input = ""
                            message = f"Simulation word count set to {CUSTOM_SIM_COUNT}!"
                        else:
                            message = "Enter a valid positive number!"
                elif not is_simulating:
                    if SIMULATE_BTN_RECT.collidepoint(mouse_pos):
                        is_simulating = True
                        sim_progress = 0.0
                        message = f"Running simulation on {CUSTOM_SIM_COUNT} words..."

                        sim_thread = threading.Thread(
                            target=parallel_brute_force_simulation,
                            args=(CUSTOM_SIM_COUNT, CUSTOM_FIRST_WORD),
                            daemon=True
                        )
                        sim_thread.start()
                    elif CHANGE_WORD_BTN_RECT.collidepoint(mouse_pos):
                        show_word_modal = True
                        custom_word_input = CUSTOM_FIRST_WORD
                    elif CHANGE_COUNT_BTN_RECT.collidepoint(mouse_pos):
                        show_count_modal = True
                        custom_count_input = str(CUSTOM_SIM_COUNT)

            elif event.type == pygame.KEYDOWN:
                if show_word_modal:
                    if event.unicode.isalpha() and len(custom_word_input) < 5:
                        custom_word_input += event.unicode.upper()
                    elif event.key == pygame.K_BACKSPACE and len(custom_word_input) > 0:
                        custom_word_input = custom_word_input[:-1]
                    elif event.key == pygame.K_RETURN:
                        if len(custom_word_input) == 5 and custom_word_input in VALID_WORDS:
                            CUSTOM_FIRST_WORD = custom_word_input
                            show_word_modal = False
                            custom_word_input = ""
                            message = f"AI first word updated to '{CUSTOM_FIRST_WORD}'!"
                            human_top_recs, remaining_human_pool = compute_top_recommendations(WORD_LIST, human_history,
                                                                                               first_word=CUSTOM_FIRST_WORD)
                            ai_top_recs, remaining_ai_pool = compute_top_recommendations(WORD_LIST, ai_history,
                                                                                         first_word=CUSTOM_FIRST_WORD)
                        else:
                            message = "Invalid 5-letter word!"

                elif show_count_modal:
                    if event.unicode.isdigit() and len(custom_count_input) < 5:
                        custom_count_input += event.unicode
                    elif event.key == pygame.K_BACKSPACE and len(custom_count_input) > 0:
                        custom_count_input = custom_count_input[:-1]
                    elif event.key == pygame.K_RETURN:
                        if custom_count_input.isdigit() and int(custom_count_input) > 0:
                            CUSTOM_SIM_COUNT = min(int(custom_count_input), len(VALID_WORDS))
                            show_count_modal = False
                            custom_count_input = ""
                            message = f"Simulation word count set to {CUSTOM_SIM_COUNT}!"
                        else:
                            message = "Enter a valid positive number!"

                elif not game_over and not show_stats_overlay and not is_simulating:
                    if event.unicode.isalpha() and len(event.unicode) == 1:
                        if current_col < COLS:
                            letter = event.unicode.upper()
                            human_grid[current_row][current_col] = [letter, 'filled']
                            current_col += 1

                    elif event.key == pygame.K_BACKSPACE:
                        if current_col > 0:
                            current_col -= 1
                            human_grid[current_row][current_col] = ["", 'empty']

                    elif event.key == pygame.K_RETURN:
                        if current_col == COLS:
                            human_guess = "".join(human_grid[current_row][c][0] for c in range(COLS))

                            if human_guess not in VALID_WORDS:
                                message = f"'{human_guess}' is not a valid word!"
                                continue

                            # 1. Human Turn
                            human_feedback = calculate_feedback(human_guess, TARGET_WORD)
                            human_history.append((human_guess, human_feedback))

                            status_map = {0: 'absent', 1: 'present', 2: 'correct'}
                            for c in range(COLS):
                                human_grid[current_row][c][1] = status_map[human_feedback[c]]

                            if human_guess == TARGET_WORD:
                                human_won = True

                            # 2. AI Turn
                            ai_guess = get_ai_best_guess(WORD_LIST, ai_history, first_word=CUSTOM_FIRST_WORD)
                            ai_feedback = calculate_feedback(ai_guess, TARGET_WORD)
                            ai_history.append((ai_guess, ai_feedback))

                            for c in range(COLS):
                                ai_grid[current_row][c][0] = ai_guess[c]
                                ai_grid[current_row][c][1] = status_map[ai_feedback[c]]

                            if ai_guess == TARGET_WORD:
                                ai_won = True

                            # 3. Compute Next Turn Recommendations
                            human_top_recs, remaining_human_pool = compute_top_recommendations(WORD_LIST, human_history,
                                                                                               first_word=CUSTOM_FIRST_WORD)
                            ai_top_recs, remaining_ai_pool = compute_top_recommendations(WORD_LIST, ai_history,
                                                                                         first_word=CUSTOM_FIRST_WORD)

                            # 4. Evaluate Game End
                            if human_won and ai_won:
                                message = "It's a Tie! Both solved it on the same turn!"
                                game_over = True
                            elif human_won:
                                message = f"You Won! You beat the AI in {current_row + 1} turns!"
                                game_over = True
                            elif ai_won:
                                message = f"AI Won! The AI solved it in {current_row + 1} turns!"
                                game_over = True
                            elif current_row == ROWS - 1:
                                message = f"Game Over! Goal was: {TARGET_WORD}"
                                game_over = True
                            else:
                                current_row += 1
                                current_col = 0
                                message = f"Turn {current_row + 1} of {ROWS}. Enter your next guess!"

        # Render Main Elements
        draw_top_panels(SCREEN, FONTS)
        draw_grid(SCREEN, FONTS, HUMAN_START_X, human_grid)
        draw_grid(SCREEN, FONTS, AI_START_X, ai_grid)
        draw_footer(SCREEN, FONTS, mouse_pos, SIMULATE_BTN_RECT, CHANGE_WORD_BTN_RECT, CHANGE_COUNT_BTN_RECT)

        if show_word_modal:
            draw_first_word_modal(SCREEN, FONTS, mouse_pos, custom_word_input, CANCEL_MODAL_BTN_RECT,
                                  CONFIRM_MODAL_BTN_RECT)
        elif show_count_modal:
            draw_count_modal(SCREEN, FONTS, mouse_pos, custom_count_input, CANCEL_MODAL_BTN_RECT,
                             CONFIRM_MODAL_BTN_RECT)
        elif show_stats_overlay:
            draw_stats_modal(SCREEN, FONTS, mouse_pos, CLOSE_STATS_BTN_RECT)

        pygame.display.flip()
        clock.tick(30)