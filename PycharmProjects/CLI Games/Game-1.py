import curses
import time

def main(stdscr):
    # Setup curses
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.clear()

    # Enable mouse movement tracking
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    # Send xterm escape sequence to continuously report mouse movement without clicking
    print("\033[?1003h", end="", flush=True)

    height, width = stdscr.getmaxyx()

    # Game state
    paddle_len = 5
    ai_y = height // 2 - paddle_len // 2
    player_y = height // 2 - paddle_len // 2

    ball_x = float(width // 2)
    ball_y = float(height // 2)

    # Ball velocities
    ball_vx = 35.0
    ball_vy = 18.0

    ai_score = 0
    player_score = 0

    # Cache previous frame's visual positions
    prev_ball_x = int(ball_x)
    prev_ball_y = int(ball_y)
    prev_ai_y = ai_y
    prev_player_y = player_y

    # Initial frame draw setup
    stdscr.box()
    last_time = time.perf_counter()

    try:
        while True:
            current_time = time.perf_counter()
            dt = current_time - last_time
            last_time = current_time

            # Handle terminal resize
            new_h, new_w = stdscr.getmaxyx()
            if new_h != height or new_w != width:
                height, width = new_h, new_w
                stdscr.clear()
                stdscr.box()

            # Process input & Mouse Y tracking
            key = stdscr.getch()
            if key == ord('q'):
                break
            elif key == curses.KEY_MOUSE:
                try:
                    _, _, mouse_y, _, _ = curses.getmouse()
                    # Center the paddle around the mouse cursor
                    player_y = max(1, min(height - paddle_len - 1, mouse_y - paddle_len // 2))
                except curses.error:
                    pass

            # AI Movement
            if ball_vx < 0:
                if ai_y + paddle_len / 2 < ball_y and ai_y < height - paddle_len - 1:
                    ai_y += 1
                elif ai_y + paddle_len / 2 > ball_y and ai_y > 1:
                    ai_y -= 1

            # Physics calculations
            ball_x += ball_vx * dt
            ball_y += ball_vy * dt

            # Wall bounce
            if ball_y <= 1:
                ball_y = 1
                ball_vy *= -1
            elif ball_y >= height - 2:
                ball_y = height - 2
                ball_vy *= -1

            curr_bx, curr_by = int(ball_x), int(ball_y)

            # Paddle collisions
            if curr_bx <= 2 and ai_y <= curr_by < ai_y + paddle_len:
                ball_x = 3
                ball_vx *= -1
            elif curr_bx >= width - 3 and player_y <= curr_by < player_y + paddle_len:
                ball_x = width - 4
                ball_vx *= -1

            # Scoring
            if curr_bx <= 0:
                player_score += 1
                ball_x, ball_y = width // 2, height // 2
                ball_vx = abs(ball_vx)
            elif curr_bx >= width - 1:
                ai_score += 1
                ball_x, ball_y = width // 2, height // 2
                ball_vx = -abs(ball_vx)

            # --- SINGLE-FRAME BATCH RENDERING ---

            # 1. Clear old positions in memory
            if (prev_ball_x, prev_ball_y) != (curr_bx, curr_by):
                if 0 < prev_ball_y < height - 1 and 0 < prev_ball_x < width - 1:
                    stdscr.addch(prev_ball_y, prev_ball_x, ' ')
                prev_ball_x, prev_ball_y = curr_bx, curr_by

            if prev_ai_y != ai_y:
                for i in range(paddle_len):
                    if 0 < prev_ai_y + i < height - 1:
                        stdscr.addch(prev_ai_y + i, 1, ' ')
                prev_ai_y = ai_y

            if prev_player_y != player_y:
                for i in range(paddle_len):
                    if 0 < prev_player_y + i < height - 1:
                        stdscr.addch(prev_player_y + i, width - 2, ' ')
                prev_player_y = player_y

            # 2. Write new positions into the back-buffer
            score_str = f" AI: {ai_score}  |  Player: {player_score} "
            stdscr.addstr(0, max(0, (width - len(score_str)) // 2), score_str)

            for i in range(paddle_len):
                if 0 < ai_y + i < height - 1:
                    stdscr.addch(ai_y + i, 1, '|')

            for i in range(paddle_len):
                if 0 < player_y + i < height - 1:
                    stdscr.addch(player_y + i, width - 2, '|')

            if 0 < curr_by < height - 1 and 0 < curr_bx < width - 1:
                stdscr.addch(curr_by, curr_bx, 'O')

            # 3. Queue changes to double buffer and sync terminal in ONE atomic update
            stdscr.noutrefresh()
            curses.doupdate()

            time.sleep(1 / 60)

    finally:
        # Turn off mouse tracking mode on exit
        print("\033[?1003l", end="", flush=True)

if __name__ == "__main__":
    curses.wrapper(main)