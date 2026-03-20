import pygame

# Dimensions and UI constants
BOARD_SIZE = 512
SIDEBAR_WIDTH = 260
BAR_H = 48
EVAL_BAR_W = 16
EVAL_GAP = 6
BOARD_X = EVAL_BAR_W + EVAL_GAP  # offset board to leave room for left eval bar
WIDTH = BOARD_X + BOARD_SIZE + SIDEBAR_WIDTH
HEIGHT = BOARD_SIZE + 2*BAR_H
DIM = 8
SQ = BOARD_SIZE // DIM

UI_PAD = 12
ROW_H = 22
BTN_H = 31
BTN_GAP = 8
BG_COLOR = pygame.Color("#302E2B")

# globals for rendering
screen = None
IMAGES = {}
FLIPPED = False


def font(size, bold=False):
    return pygame.font.SysFont(["Inter", "Arial", "Helvetica", "sans-serif"], size, bold=bold)


def init_display():
    global screen
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Chess")
    return screen


def clear():
    """Fill the whole screen with the base background color."""
    screen.fill(BG_COLOR)


def load_images():
    pieces = ["wp","wR","wN","wB","wQ","wK","bp","bR","bN","bB","bQ","bK"]
    for p in pieces:
        IMAGES[p] = pygame.transform.scale(
            pygame.image.load(f"images/{p}.png"),
            (SQ, SQ)
        )


# ================= UI helpers =================
def to_screen(r, c, flipped=False):
    sr = 7 - r if flipped else r
    sc = 7 - c if flipped else c
    return BOARD_X + sc * SQ, BAR_H + sr * SQ


def from_screen(x, y, flipped=False):
    if x < BOARD_X or x >= BOARD_X + BOARD_SIZE or y < BAR_H or y >= BAR_H + BOARD_SIZE:
        return None
    c = (x - BOARD_X) // SQ
    r = (y - BAR_H) // SQ
    if flipped:
        c = 7 - c
        r = 7 - r
    return r, c


def draw_board(flipped=False):
    colors = [pygame.Color("#EBECD0"), pygame.Color("#739552")]
    for r in range(8):
        for c in range(8):
            x, y = to_screen(r, c, flipped)
            pygame.draw.rect(screen, colors[(r+c)%2], (x, y, SQ, SQ))


def draw_eval_bar(cp=None, mate=None, flipped=False, ratio_override=None):
    """Vertical eval bar hugging the left edge of the board (chess.com style)."""
    x = 4
    y = BAR_H
    h = BOARD_SIZE
    w = EVAL_BAR_W

    # background rail
    rail = pygame.Rect(x - 2, y, w + 4, h)
    pygame.draw.rect(screen, BG_COLOR, rail, border_radius=6)

    def score_to_ratio(cp_val, mate_val):
        if mate_val is not None:
            return 1.0 if mate_val > 0 else 0.0
        if cp_val is None:
            return 0.5
        cap = 900  # clamp at ~9 pawns
        cp_clamped = max(-cap, min(cap, cp_val))
        return 0.5 + cp_clamped / (2 * cap)

    ratio = ratio_override if ratio_override is not None else score_to_ratio(cp, mate)
    ratio = max(0.0, min(1.0, ratio))

    white_top = flipped
    white_color = pygame.Color(235, 235, 235)
    black_color = pygame.Color(18, 18, 18)

    white_h = int(h * ratio)
    black_h = h - white_h

    if white_top:
        white_rect = pygame.Rect(x, y, w, white_h)
        black_rect = pygame.Rect(x, y + white_h, w, black_h)
    else:
        black_rect = pygame.Rect(x, y, w, black_h)
        white_rect = pygame.Rect(x, y + black_h, w, white_h)

    pygame.draw.rect(screen, white_color, white_rect, border_radius=4)
    pygame.draw.rect(screen, black_color, black_rect, border_radius=4)


def highlight(moves, board, flipped=False):
    for r, c in moves:
        x, y = to_screen(r, c, flipped)
        surf = pygame.Surface((SQ, SQ), pygame.SRCALPHA)
        center = (SQ//2, SQ//2)
        is_dark = (r + c) % 2 == 1
        ring_col = pygame.Color("#638046" if is_dark else "#CACBB2")
        ring_col.a = 255
        dot_col = pygame.Color("#638046" if is_dark else "#CACBB2")
        dot_col.a = 235

        if board[r][c] != "--":
            radius = SQ // 2 - 1  # outer stays the same
            base_width = max(8, SQ // 6)
            width = max(4, int(base_width * 0.6))  # inner pulled 40% closer for thinner ring
            pygame.draw.circle(surf, ring_col, center, radius, width=width)
        else:
            pygame.draw.circle(surf, dot_col, center, max(2, int((SQ // 4) / 1.5)))  # 1.5x smaller dot
        screen.blit(surf, (x, y))


def draw_pieces(board, flipped=False):
    for r in range(8):
        for c in range(8):
            if board[r][c] != "--":
                x, y = to_screen(r, c, flipped)
                screen.blit(IMAGES[board[r][c]], (x, y))


def highlight_last_move(last_move, flipped=False):
    ((sr, sc), (er, ec)) = last_move
    for r, c in [(sr, sc), (er, ec)]:
        is_dark = (r + c) % 2 == 1
        color = pygame.Color("#BACA49") if is_dark else pygame.Color("#F5F68C")
        surf = pygame.Surface((SQ, SQ))
        surf.fill(color)
        surf.set_alpha(120)
        x, y = to_screen(r, c, flipped)
        screen.blit(surf, (x, y))


def highlight_check(gs, flipped=False):
    king = "wK" if gs.white_turn else "bK"
    for r in range(8):
        for c in range(8):
            if gs.board[r][c] == king:
                surf = pygame.Surface((SQ, SQ))
                surf.set_alpha(120)
                surf.fill(pygame.Color(200, 60, 60))
                x, y = to_screen(r, c, flipped)
                screen.blit(surf, (x, y))
                return


def draw_player_bars(white_name, black_name, white_ms, black_ms, material_diff=0, captured_top=None, captured_bot=None, flipped=False):
    font_name = font(20, bold=True)
    font_clock = font(22, bold=True)
    bar_color = BG_COLOR
    clock_color = pygame.Color("#2B2926")
    font_material = font(16, bold=True)
    font_cap = font(14)
    icon_size = 18
    icon_gap = 4

    def draw_captured_list(pieces, x, y):
        if not pieces:
            return x
        # group identical pieces and overlap them horizontally (domino stack look)
        from collections import Counter
        counts = Counter(pieces)
        pos_x = x
        stack_step = max(6, icon_size - 10)  # how much of the next icon peeks out
        order = ["bQ", "bR", "bB", "bN", "bp", "wQ", "wR", "wB", "wN", "wp"]
        for p in order:
            cnt = counts[p]
            if cnt == 0:
                continue
            img = IMAGES.get(p)
            if not img:
                continue
            icon = pygame.transform.smoothscale(img, (icon_size, icon_size))
            icon.fill((180,180,180,200), special_flags=pygame.BLEND_RGBA_MULT)
            for i in range(cnt):
                screen.blit(icon, (pos_x + i * stack_step, y))
            # advance past the stacked cluster
            pos_x += (icon_size if cnt == 1 else (icon_size + (cnt - 1) * stack_step)) + icon_gap
        return pos_x

    def fmt(ms):
        m = ms // 60000
        s = (ms // 1000) % 60
        return f"{m}:{s:02d}"

    top_is_white = flipped
    top_name = white_name if top_is_white else black_name
    bot_name = black_name if top_is_white else white_name
    top_ms = white_ms if top_is_white else black_ms
    bot_ms = black_ms if top_is_white else white_ms

    # top bar
    top_rect = pygame.Rect(BOARD_X, 0, BOARD_SIZE, BAR_H)
    pygame.draw.rect(screen, bar_color, top_rect)
    name_surf = font_name.render(top_name, True, pygame.Color("#F7F7F7"))
    screen.blit(name_surf, (12, (BAR_H - name_surf.get_height())//2))
    cap_x_start = 12 + name_surf.get_width() + 10
    end_x_top = draw_captured_list(captured_top or [], cap_x_start, (BAR_H - icon_size)//2)
    top_mat = material_diff if top_is_white else -material_diff
    mat_text = f"{top_mat:+d}" if top_mat != 0 else ""
    if mat_text:
        mat_surf = font_material.render(mat_text, True, pygame.Color("#82807F"))
        screen.blit(mat_surf, (end_x_top + (icon_gap if end_x_top > cap_x_start else 0), (BAR_H - mat_surf.get_height())//2))
    clock_rect = pygame.Rect(BOARD_X + BOARD_SIZE - 100, 6, 100, BAR_H-12)
    pygame.draw.rect(screen, clock_color, clock_rect, border_radius=6)
    clock_surf = font_clock.render(fmt(top_ms), True, pygame.Color("lightgray"))
    screen.blit(clock_surf, clock_surf.get_rect(center=clock_rect.center))

    # bottom bar
    bot_rect = pygame.Rect(BOARD_X, BAR_H + BOARD_SIZE, BOARD_SIZE, BAR_H)
    pygame.draw.rect(screen, bar_color, bot_rect)
    name_surf2 = font_name.render(bot_name, True, pygame.Color("#F7F7F7"))
    screen.blit(name_surf2, (12, bot_rect.y + (BAR_H - name_surf2.get_height())//2))
    cap_x_start2 = 12 + name_surf2.get_width() + 10
    end_x_bot = draw_captured_list(captured_bot or [], cap_x_start2, bot_rect.y + (BAR_H - icon_size)//2)
    bot_mat = -material_diff if top_is_white else material_diff
    mat_text2 = f"{bot_mat:+d}" if bot_mat != 0 else ""
    if mat_text2:
        mat_surf2 = font_material.render(mat_text2, True, pygame.Color("#82807F"))
        screen.blit(mat_surf2, (end_x_bot + (icon_gap if end_x_bot > cap_x_start2 else 0), bot_rect.y + (BAR_H - mat_surf2.get_height())//2))
    clock_rect2 = pygame.Rect(BOARD_X + BOARD_SIZE - 100, bot_rect.y + 6, 100, BAR_H-12)
    pygame.draw.rect(screen, clock_color, clock_rect2, border_radius=6)
    clock_surf2 = font_clock.render(fmt(bot_ms), True, pygame.Color("lightgray"))
    screen.blit(clock_surf2, clock_surf2.get_rect(center=clock_rect2.center))

    # captured rows drawn inline above; nothing more to do here


def move_list_bounds(move_history):
    list_top = BAR_H + UI_PAD + 52
    # leave extra space at bottom so move log doesn't overlap action/nav buttons
    list_height = HEIGHT - list_top - (UI_PAD + BTN_H + UI_PAD + 50)
    rows_visible = max(1, list_height // ROW_H)
    total_rows = (len(move_history) + 1) // 2
    max_start = max(0, total_rows - rows_visible)
    return list_top, list_height, rows_visible, total_rows, max_start


def nav_buttons():
    labels = [("<<", "first"), ("<", "prev"), (">", "next"), (">>", "last")]
    pad = UI_PAD
    btn_h = BTN_H
    gap = BTN_GAP
    btn_w = (SIDEBAR_WIDTH - pad*2 - gap*3) // 4
    y = HEIGHT - pad - btn_h
    sidebar_x = BOARD_X + BOARD_SIZE
    buttons = []
    for i, (label, action) in enumerate(labels):
        x = sidebar_x + pad + i*(btn_w + gap)
        buttons.append({"rect": pygame.Rect(x, y, btn_w, btn_h), "label": label, "action": action})
    return buttons


def draw_sidebar(move_history, view_index, total_states, buttons, status_text, scroll_row, scrollbar_alpha=0, timers=None, flipped=False, draw_buttons=None, eval_text=None):
    sidebar_x = BOARD_X + BOARD_SIZE
    sidebar_rect = pygame.Rect(sidebar_x, 0, SIDEBAR_WIDTH, HEIGHT)
    pygame.draw.rect(screen, BG_COLOR, sidebar_rect)

    pad = UI_PAD
    header_y = pad
    font_title = font(22)
    font_small = font(14)

    title = font_title.render("Moves", True, pygame.Color("white"))
    screen.blit(title, (sidebar_x + pad, header_y))

    live = (view_index == total_states - 1)
    status = "Live" if live else f"Reviewing move {view_index}/{total_states-1}"
    status_label = font_small.render(status, True, pygame.Color(120,220,120) if live else pygame.Color("orange"))
    screen.blit(status_label, (sidebar_x + pad, header_y + 26))
    if status_text:
        st = font_small.render(status_text, True, pygame.Color("yellow"))
        screen.blit(st, (sidebar_x + pad, header_y + 44))
    if eval_text:
        ev = font_small.render(f"Eval: {eval_text}", True, pygame.Color("white"))
        screen.blit(ev, (sidebar_x + pad, header_y + 62))

    if timers:
        turn_text = timers  # repurpose to show turn indicator text
        turn_label = font_small.render(turn_text, True, pygame.Color("white"))
        screen.blit(turn_label, (sidebar_x + SIDEBAR_WIDTH - pad - turn_label.get_width(), header_y))

    list_top, list_height, rows_visible, total_rows, max_start = move_list_bounds(move_history)
    start_row = max(0, min(scroll_row, max_start))

    row_h = ROW_H

    # Draw move table background
    table_rect = pygame.Rect(sidebar_x + pad, list_top, SIDEBAR_WIDTH - 2*pad, rows_visible*row_h)
    pygame.draw.rect(screen, pygame.Color(28,28,28), table_rect)

    col_split = table_rect.x + table_rect.w // 2
    ply_highlight = max(0, view_index - 1)  # ply corresponds to board after move

    zebra_colors = [pygame.Color("#262522"), pygame.Color("#2A2926")]
    for idx in range(rows_visible):
        row_num = start_row + idx
        if row_num >= total_rows:
            break
        row_y = list_top + idx * row_h
        move_no = row_num + 1
        ply_white = row_num*2
        ply_black = row_num*2 + 1

        # zebra row background
        zebra = zebra_colors[(row_num) % 2]
        row_rect = pygame.Rect(table_rect.x, row_y, table_rect.w, row_h)
        pygame.draw.rect(screen, zebra, row_rect)

        label = font_small.render(f"{move_no}.", True, pygame.Color(160,160,160))
        screen.blit(label, (table_rect.x + 4, row_y + 5))

        # white cell
        white_rect = pygame.Rect(table_rect.x + 36, row_y, table_rect.w//2 - 36, row_h)
        if ply_white < len(move_history):
            if ply_highlight == ply_white:
                pygame.draw.rect(screen, pygame.Color(70,70,90), white_rect)
            w_text = font_small.render(move_history[ply_white], True, pygame.Color("white"))
            screen.blit(w_text, (white_rect.x + 4, row_y + 5))

        # black cell
        black_rect = pygame.Rect(col_split, row_y, table_rect.w//2, row_h)
        if ply_black < len(move_history):
            if ply_highlight == ply_black:
                pygame.draw.rect(screen, pygame.Color(70,70,90), black_rect)
            b_text = font_small.render(move_history[ply_black], True, pygame.Color("white"))
            screen.blit(b_text, (black_rect.x + 4, row_y + 5))

    # Scrollbar (only if content exceeds view)
    if total_rows > rows_visible and scrollbar_alpha > 0:
        track_w = 8
        track_x = table_rect.right - track_w - 4
        track_h = rows_visible * row_h
        track_rect = pygame.Rect(track_x, list_top, track_w, track_h)
        pygame.draw.rect(screen, pygame.Color(55,55,55, scrollbar_alpha), track_rect, border_radius=4)

        thumb_min = 16
        thumb_h = max(thumb_min, int(track_h * rows_visible / total_rows))
        max_start_px = track_h - thumb_h
        thumb_y = track_rect.y
        if max_start > 0:
            thumb_y += int((start_row / max_start) * max_start_px)
        thumb_rect = pygame.Rect(track_x, thumb_y, track_w, thumb_h)
        pygame.draw.rect(screen, pygame.Color(120,120,120, scrollbar_alpha), thumb_rect, border_radius=4)

    # Buttons
    for b in buttons:
        rect = b["rect"]
        enabled = True
        if b["action"] == "first" and view_index == 0:
            enabled = False
        if b["action"] == "prev" and view_index == 0:
            enabled = False
        if b["action"] == "next" and view_index >= total_states - 1:
            enabled = False
        if b["action"] == "last" and view_index >= total_states - 1:
            enabled = False

        bg = pygame.Color("#3D3C39") if enabled else pygame.Color("#2B2926")
        pygame.draw.rect(screen, bg, rect, border_radius=6)
        pygame.draw.rect(screen, pygame.Color(90,90,90), rect, 2, border_radius=6)
        label = font_title.render(b["label"], True, pygame.Color("white") if enabled else pygame.Color(120,120,120))
        screen.blit(label, label.get_rect(center=rect.center))

    if draw_buttons:
        font_btn = font(16)
        for b in draw_buttons:
            rect = b["rect"]
            bg = pygame.Color("#3D3C39") if b.get("enabled", True) else pygame.Color("#2B2926")
            pygame.draw.rect(screen, bg, rect, border_radius=6)
            pygame.draw.rect(screen, pygame.Color(90,90,90), rect, 2, border_radius=6)
            label = font_btn.render(b["label"], True, pygame.Color("white") if b.get("enabled", True) else pygame.Color(130,130,130))
            screen.blit(label, label.get_rect(center=rect.center))

    # return geometry info for clicks/scroll clamping
    return {
        "list_top": list_top,
        "list_height": list_height,
        "row_h": row_h,
        "rows_visible": rows_visible,
        "total_rows": total_rows,
        "max_start": max_start,
        "start_row": start_row,
    }


def choose_promotion(color, origin, flipped=False):
    """
    Show a vertical picker near the promotion square.
    Returns one of "Q", "R", "B", "N" or None if the window closes.
    """
    options = ["Q", "R", "B", "N"]
    tile = SQ  # same footprint as a board square
    pad = 0    # no gaps between buttons
    width = tile
    height = tile * (len(options) + 1)  # +1 for close button

    # anchor near the promotion square; clamp to board
    r, c = origin
    screen_x, screen_y = to_screen(r, c, flipped)
    x0 = max(0, min(BOARD_SIZE - width, screen_x - width//2 + SQ//2))
    y0 = max(0, min(HEIGHT - height, screen_y - height//2 + SQ//2))

    font_pick = font(max(tile//2 - 3, 10))
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 0))  # fully transparent; no board dimming

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return None
            if e.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                # close box
                close_rect = pygame.Rect(x0, y0, tile, tile)
                if close_rect.collidepoint(mx, my):
                    return None
                # piece buttons
                for i, opt in enumerate(options):
                    rect = pygame.Rect(x0, y0 + tile*(i+1), tile, tile)
                    if rect.collidepoint(mx, my):
                        return opt

        screen.blit(overlay, (0, 0))

        # close button
        close_rect = pygame.Rect(x0, y0, tile, tile)
        pygame.draw.rect(screen, pygame.Color("lightgray"), close_rect, border_radius=6)
        pygame.draw.rect(screen, pygame.Color("dimgray"), close_rect, 2, border_radius=6)
        text = font_pick.render("X", True, pygame.Color("black"))
        screen.blit(text, text.get_rect(center=close_rect.center))

        # piece buttons
        for i, opt in enumerate(options):
            rect = pygame.Rect(x0, y0 + tile*(i+1), tile, tile)
            pygame.draw.rect(screen, pygame.Color("white"), rect, border_radius=6)
            pygame.draw.rect(screen, pygame.Color("dimgray"), rect, 2, border_radius=6)

            # scale image to fill most of the tile
            img = pygame.transform.smoothscale(IMAGES[color + opt], (tile - 8, tile - 8))
            screen.blit(img, img.get_rect(center=rect.center))

        pygame.display.flip()


def show_game_over(message):
    """Show game-over overlay; return True to start a new game, False to quit."""
    font_big = font(36)
    font_small = font(18)
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((245, 245, 245, 235))
    clock = pygame.time.Clock()

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_q, pygame.K_ESCAPE):
                    return False
                if e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                    return True
            if e.type == pygame.MOUSEBUTTONDOWN:
                return True

        screen.blit(overlay, (0, 0))
        title = font_big.render(message, True, pygame.Color("black"))
        prompt = font_small.render("Click or press Enter/Space/R to play again, Q to quit.", True, pygame.Color("dimgray"))
        screen.blit(title, title.get_rect(center=(WIDTH//2, HEIGHT//2 - 20)))
        screen.blit(prompt, prompt.get_rect(center=(WIDTH//2, HEIGHT//2 + 20)))
        pygame.display.flip()
        clock.tick(30)


def choose_time_control():
    """
    Blocking menu to pick a time control. Returns (base_ms, inc_ms) or None if quit.
    Layout mimics chess.com style categories: Bullet, Blitz, Rapid.
    """
    categories = [
        ("Bullet", [("1 min", 60_000, 0), ("1 | 1", 60_000, 1_000), ("2 | 1", 120_000, 1_000)]),
        ("Blitz",  [("3 min", 180_000, 0), ("3 | 2", 180_000, 2_000), ("5 min", 300_000, 0)]),
        ("Rapid",  [("10 min", 600_000, 0), ("15 | 10", 900_000, 10_000), ("30 min", 1_800_000, 0)]),
    ]
    selected = ("10 min", 600_000, 0)  # default

    font_title = font(27)
    font_cat = font(23, bold=True)
    font_btn = font(22, bold=True)
    font_start = font(29, bold=True)

    btn_w, btn_h = 150, 54
    gap_x = 14
    gap_y = 12
    pad_top = 40
    row_gap = 46

    start_rect = pygame.Rect((WIDTH-320)//2, HEIGHT-90, 320, 60)

    clock = pygame.time.Clock()
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return None
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    return None
                if e.key == pygame.K_RETURN and selected:
                    return selected[1], selected[2]
            if e.type == pygame.MOUSEBUTTONDOWN and getattr(e, "button", 0) == 1:
                mx, my = pygame.mouse.get_pos()
                if start_rect.collidepoint(mx, my) and selected:
                    return selected[1], selected[2]
                y_cursor = pad_top
                for cat, opts in categories:
                    y_cursor += row_gap  # heading height
                    for idx, opt in enumerate(opts):
                        x = (WIDTH - (3*btn_w + 2*gap_x))//2 + idx*(btn_w + gap_x)
                        rect = pygame.Rect(x, y_cursor, btn_w, btn_h)
                        if rect.collidepoint(mx, my):
                            selected = opt
                        # no break; continue to allow further detection
                    y_cursor += btn_h + gap_y

        screen.fill((22,22,22))
        title = font_title.render("Choose Time Control", True, pygame.Color("white"))
        screen.blit(title, title.get_rect(center=(WIDTH//2, 24)))

        y_cursor = pad_top
        for cat, opts in categories:
            cat_label = font_cat.render(cat, True, pygame.Color("white"))
            screen.blit(cat_label, ( (WIDTH - (3*btn_w + 2*gap_x))//2, y_cursor))
            y_cursor += row_gap
            for idx, opt in enumerate(opts):
                x = (WIDTH - (3*btn_w + 2*gap_x))//2 + idx*(btn_w + gap_x)
                rect = pygame.Rect(x, y_cursor, btn_w, btn_h)
                is_sel = (opt == selected)
                bg = pygame.Color(70,120,60) if is_sel else pygame.Color(60,60,60)
                border = pygame.Color(140,220,120) if is_sel else pygame.Color(30,30,30)
                pygame.draw.rect(screen, bg, rect, border_radius=8)
                pygame.draw.rect(screen, border, rect, 3 if is_sel else 1, border_radius=8)
                label = font_btn.render(opt[0], True, pygame.Color("white"))
                screen.blit(label, label.get_rect(center=rect.center))
            y_cursor += btn_h + gap_y

        # Start button
        pygame.draw.rect(screen, pygame.Color(80,170,70), start_rect, border_radius=10)
        pygame.draw.rect(screen, pygame.Color(40,110,40), start_rect, 3, border_radius=10)
        start_text = font_start.render("Start Game", True, pygame.Color("white"))
        screen.blit(start_text, start_text.get_rect(center=start_rect.center))

        pygame.display.flip()
        clock.tick(30)
