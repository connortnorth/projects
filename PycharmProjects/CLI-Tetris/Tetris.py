import os
import random
import time

# Platform-specific non-blocking key reader without using sys
try:
    import msvcrt


    def get_key():
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            if ch in (b'\x00', b'\xe0'):
                ch = msvcrt.getch()
                return {b'K': 'LEFT', b'M': 'RIGHT', b'H': 'UP', b'P': 'DOWN'}.get(ch)
            return ch.decode('utf-8', errors='ignore').lower()
        return None
except ImportError:
    import select
    import termios
    import tty


    def get_key():
        fd = 0
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            rlist, _, _ = select.select([fd], [], [], 0)
            if rlist:
                ch = os.read(fd, 3)
                if ch == b'\x1b[D': return 'LEFT'
                if ch == b'\x1b[C': return 'RIGHT'
                if ch == b'\x1b[A': return 'UP'
                if ch == b'\x1b[B': return 'DOWN'
                return ch.decode('utf-8', errors='ignore').lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return None

BOARD_WIDTH = 10
BOARD_HEIGHT = 20

SHAPES = [
    [[[1, 1, 1, 1]], [[1], [1], [1], [1]]],
    [[[1, 1], [1, 1]]],
    [[[0, 1, 0], [1, 1, 1]], [[1, 0], [1, 1], [1, 0]], [[1, 1, 1], [0, 1, 0]], [[0, 1], [1, 1], [0, 1]]],
    [[[0, 1, 1], [1, 1, 0]], [[1, 0], [1, 1], [0, 1]]],
    [[[1, 1, 0], [0, 1, 1]], [[0, 1], [1, 1], [1, 0]]],
    [[[1, 0, 0], [1, 1, 1]], [[1, 1], [1, 0], [1, 0]], [[1, 1, 1], [0, 0, 1]], [[0, 1], [0, 1], [1, 1]]],
    [[[0, 0, 1], [1, 1, 1]], [[1, 0], [1, 0], [1, 1]], [[1, 1, 1], [1, 0, 0]], [[1, 1], [0, 1], [0, 1]]]
]


def create_piece():
    shape = random.choice(SHAPES)
    return {'shape': shape, 'rotation': 0, 'x': BOARD_WIDTH // 2 - len(shape[0][0]) // 2, 'y': 0}


def get_matrix(piece):
    return piece['shape'][piece['rotation'] % len(piece['shape'])]


def check_collision(board, piece, offset_x=0, offset_y=0, rotation_offset=0):
    matrix = piece['shape'][(piece['rotation'] + rotation_offset) % len(piece['shape'])]
    for r, row in enumerate(matrix):
        for c, val in enumerate(row):
            if val:
                nx = piece['x'] + c + offset_x
                ny = piece['y'] + r + offset_y
                if nx < 0 or nx >= BOARD_WIDTH or ny >= BOARD_HEIGHT: return True
                if ny >= 0 and board[ny][nx]: return True
    return False


def merge_piece(board, piece):
    matrix = get_matrix(piece)
    for r, row in enumerate(matrix):
        for c, val in enumerate(row):
            if val: board[piece['y'] + r][piece['x'] + c] = 1


def animate_clear_lines(board, full_rows, score):
    """Animates full rows clearing from middle outwards before collapsing upper rows."""
    mid = BOARD_WIDTH // 2

    # 5 steps from center (4,5) expanding out to (0,9)
    for step in range(mid):
        left_col = mid - 1 - step
        right_col = mid + step

        # Clear middle cells step-by-step
        for row_idx in full_rows:
            board[row_idx][left_col] = 0
            board[row_idx][right_col] = 0

        render(board, None, score)
        time.sleep(0.06)


def clear_lines(board, score):
    full_rows = [i for i, row in enumerate(board) if all(v == 1 for v in row)]
    cleared = len(full_rows)

    if cleared > 0:
        animate_clear_lines(board, full_rows, score)

        # Move upper rows down
        new_board = [row for i, row in enumerate(board) if i not in full_rows]
        for _ in range(cleared):
            new_board.insert(0, [0] * BOARD_WIDTH)
        return new_board, cleared

    return board, 0


def render(board, piece, score):
    output = ["\033[2J\033[H"]
    output.append(f"Score: {score} | Controls: Arrows = Move/Rotate, Q = Quit\n")
    output.append("+" + "-" * (BOARD_WIDTH * 2) + "+\n")

    display_grid = [row[:] for row in board]
    if piece:
        matrix = get_matrix(piece)
        for r, row in enumerate(matrix):
            for c, val in enumerate(row):
                if val:
                    py, px = piece['y'] + r, piece['x'] + c
                    if 0 <= py < BOARD_HEIGHT and 0 <= px < BOARD_WIDTH:
                        display_grid[py][px] = 1

    for row in display_grid:
        output.append("|" + "".join("[]" if cell else "  " for cell in row) + "|\n")
    output.append("+" + "-" * (BOARD_WIDTH * 2) + "+\n")
    print("".join(output), end="", flush=True)


def main():
    board = [[0] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]
    piece = create_piece()
    score = 0
    drop_timer = time.time()

    while True:
        render(board, piece, score)

        key = get_key()
        if key == 'q':
            break
        elif key == 'LEFT' and not check_collision(board, piece, offset_x=-1):
            piece['x'] -= 1
        elif key == 'RIGHT' and not check_collision(board, piece, offset_x=1):
            piece['x'] += 1
        elif key == 'UP' and not check_collision(board, piece, rotation_offset=1):
            piece['rotation'] += 1
        elif key == 'DOWN' and not check_collision(board, piece, offset_y=1):
            piece['y'] += 1

        if time.time() - drop_timer > 0.4:
            if not check_collision(board, piece, offset_y=1):
                piece['y'] += 1
            else:
                merge_piece(board, piece)
                board, cleared = clear_lines(board, score)
                score += cleared * 100
                piece = create_piece()
                if check_collision(board, piece):
                    render(board, piece, score)
                    print("\nGAME OVER!")
                    break
            drop_timer = time.time()

        time.sleep(0.05)


if __name__ == "__main__":
    main()