import copy
import pygame
import io

import engine
from engine import GameState, move_san, has_moves
import ui
import stockfish_eval


def main():
    ui.init_display()
    ui.load_images()

    analyzer = stockfish_eval.StockfishAnalyzer()

    def build_pgn(move_history, result_code):
        import datetime
        tags = {
            "Event": "Casual Game",
            "Site": "Local",
            "Date": datetime.date.today().isoformat(),
            "Round": "1",
            "White": "White",
            "Black": "Black",
            "Result": result_code,
        }
        lines = [f'[{k} "{v}"]' for k, v in tags.items()]
        moves_out = []
        for i in range(0, len(move_history), 2):
            num = i // 2 + 1
            w = move_history[i]
            b = move_history[i + 1] if i + 1 < len(move_history) else ""
            moves_out.append(f"{num}. {w} {b}".strip())
        lines.append(" ".join(moves_out) + " " + result_code)
        return "\n".join(lines)

    def copy_to_clipboard(text):
        try:
            import tkinter
            r = tkinter.Tk()
            r.withdraw()
            r.clipboard_clear()
            r.clipboard_append(text)
            r.update()
            r.destroy()
            return True
        except Exception:
            return False

    tc = ui.choose_time_control()
    if tc is None:
        return
    base_time_ms, increment_ms = tc

    keep_playing = True
    while keep_playing:
        gs = GameState()
        selected = None
        moves = []
        result = None

        state_history = [copy.deepcopy(gs)]
        move_history = []
        view_index = 0  # index into history
        buttons = ui.nav_buttons()
        action_buttons = [
            {"label": "Flip", "action": "flip"},
            {"label": "Undo", "action": "undo"},
            {"label": "Restart", "action": "restart"},
            {"label": "Bot: Off", "action": "bot"},
            {"label": "Home", "action": "home"},
            {"label": "Export", "action": "export"},
        ]
        scroll_row = 0
        scroll_alpha = 0
        last_scroll_ms = 0
        position_counts = {engine.position_key(gs): 1}
        flipped = False
        claimable = None
        result_code = "*"
        white_time = base_time_ms
        black_time = base_time_ms
        last_tick = pygame.time.get_ticks()
        clock_started = False
        dragging = None  # {"from":(r,c), "pos":(x,y), "moves":[(r,c)]}
        last_move = None  # ((sr,sc),(er,ec))
        animation = None  # active move animation
        eval_cache = {}
        last_eval_key = None
        last_eval_tick = 0
        eval_cp = None
        eval_mate = None
        eval_text = "--"
        eval_ratio = 0.5
        engine_on = False
        engine_is_white = False  # engine plays Black by default
        engine_thinking = False
        game_over = False
        pgn_printed = False
        captured_white = []
        captured_black = []
        premove = None
        premove_selection = None
        premove_moves = []
        processing_premove = False
        export_msg = None
        export_msg_time = 0
        home_requested = False

        def score_to_ratio(cp_val, mate_val):
            if mate_val is not None:
                return 1.0 if mate_val > 0 else 0.0
            if cp_val is None:
                return 0.5
            cap = 900
            cp_clamped = max(-cap, min(cap, cp_val))
            return 0.5 + cp_clamped / (2 * cap)

        def apply_move(sr, sc, r, c, promo_choice=None):
            nonlocal gs, state_history, move_history, view_index, last_move, clock_started, last_tick, animation
            nonlocal white_time, black_time, scroll_row, scroll_alpha, last_scroll_ms
            nonlocal position_counts, claimable, result, result_code, run

            prev_state = copy.deepcopy(gs)
            board_before = copy.deepcopy(gs.board)
            piece = gs.board[sr][sc]
            target_piece = gs.board[r][c]
            was_en_passant = piece[1] == "p" and (r, c) == gs.en_passant and target_piece == "--"

            mover_is_white = gs.white_turn
            promotion = gs.move(sr, sc, r, c)

            if promotion:
                pr, pc, color = promotion
                if promo_choice:
                    choice = promo_choice.upper()
                else:
                    choice = ui.choose_promotion(color, (pr, pc), flipped=flipped)
                    if choice is None:  # canceled via X
                        gs = prev_state  # undo move, keep playing
                        return False
                gs.board[pr][pc] = color + choice
            else:
                choice = None

            # notation and history update (SAN with disambiguation/check/mate)
            san = move_san(prev_state, sr, sc, r, c, target_piece, choice, was_en_passant)

            # truncate future if we ever implement branching
            state_history = state_history[:view_index+1]
            move_history = move_history[:view_index]

            state_history.append(copy.deepcopy(gs))
            move_history.append(san)
            view_index = len(state_history) - 1
            last_move = ((sr, sc), (r, c))
            animation = {
                "from": board_before,
                "to": copy.deepcopy(gs.board),
                "move": (sr, sc, r, c),
                "start": pygame.time.get_ticks(),
                "duration": 180,
            }

            # start clock after first move
            if not clock_started:
                clock_started = True
                last_tick = pygame.time.get_ticks()

            # increment for mover
            if increment_ms > 0:
                if mover_is_white:
                    white_time += increment_ms
                else:
                    black_time += increment_ms

            # auto-scroll to newest row
            _, _, _, total_rows, max_start = ui.move_list_bounds(move_history)
            scroll_row = max_start
            scroll_alpha = 255
            last_scroll_ms = pygame.time.get_ticks()

            # repetition count
            key = engine.position_key(gs)
            position_counts[key] = position_counts.get(key, 0) + 1

            # end/claim conditions
            claimable = None
            if not has_moves(gs):
                if gs.in_check():
                    result = "CHECKMATE"
                    winner = "Black" if gs.white_turn else "White"
                    result_code = "0-1" if winner == "Black" else "1-0"
                else:
                    result = "STALEMATE"
                    result_code = "1/2-1/2"
                game_over = True
                clock_started = False
            elif gs.halfmove_clock >= 150:  # 75-move auto draw
                result = "DRAW (75-move rule)"
                result_code = "1/2-1/2"
                game_over = True
                clock_started = False
            elif position_counts[key] >= 5:
                result = "DRAW (fivefold repetition)"
                result_code = "1/2-1/2"
                game_over = True
                clock_started = False
            elif gs.halfmove_clock >= 100:
                claimable = "50-move rule"
            elif position_counts[key] >= 3:
                claimable = "threefold repetition"
            elif engine.insufficient_material(gs.board):
                result = "DRAW (insufficient material)"
                result_code = "1/2-1/2"
                game_over = True
                clock_started = False

            return True

        run = True
        while run:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    keep_playing = False
                    run = False
                    break

                elif e.type == pygame.MOUSEWHEEL:
                    _, _, _, _, max_start = ui.move_list_bounds(move_history)
                    scroll_row = max(0, min(scroll_row - e.y, max_start))
                    scroll_alpha = 255
                    last_scroll_ms = pygame.time.get_ticks()

                elif e.type == pygame.MOUSEBUTTONDOWN:
                    if getattr(e, "button", 0) != 1:  # only left click
                        continue

                    x, y = pygame.mouse.get_pos()

                    # Sidebar interactions
                    sidebar_x = ui.BOARD_X + ui.BOARD_SIZE
                    if x >= sidebar_x:
                        handled = False
                        for b in buttons:
                            if b["rect"].collidepoint(x, y):
                                if b["action"] == "first":
                                    view_index = 0
                                elif b["action"] == "prev":
                                    view_index = max(0, view_index - 1)
                                elif b["action"] == "next":
                                    view_index = min(len(state_history) - 1, view_index + 1)
                                elif b["action"] == "last":
                                    view_index = len(state_history) - 1
                                handled = True
                                break
                        if handled:
                            selected = None
                            moves = []
                            continue

                        # action buttons (flip/undo/bot/restart/home/export)
                        for b in action_buttons:
                            if b.get("rect") and b["rect"].collidepoint(x, y) and b.get("enabled", True):
                                if b["action"] == "flip":
                                    flipped = not flipped
                                    dragging = None
                                    selected = None
                                    moves = []
                                elif b["action"] == "undo":
                                    if len(state_history) > 1:
                                        state_history.pop()
                                        move_history.pop()
                                        gs = copy.deepcopy(state_history[-1])
                                        view_index = len(state_history) - 1
                                        animation = None
                                        position_counts = {}
                                        for st in state_history:
                                            key = engine.position_key(st)
                                            position_counts[key] = position_counts.get(key, 0) + 1
                                        last_move = None
                                        selected = None
                                        moves = []
                                        dragging = None
                                        # clocks not rolled back; simple undo only
                                elif b["action"] == "bot":
                                    engine_on = not engine_on
                                    engine_thinking = False
                                    b["label"] = "Bot: On" if engine_on else "Bot: Off"
                                elif b["action"] == "restart":
                                    run = False
                                    handled = True
                                    break
                                elif b["action"] == "home":
                                    home_requested = True
                                    run = False
                                    handled = True
                                    break
                                elif b["action"] == "export":
                                    fen = engine.to_fen(state_history[view_index])
                                    pgn = build_pgn(move_history, result_code)
                                    print("\nFEN:\n" + fen + "\n")
                                    print("PGN:\n" + pgn + "\n")
                                    combined = f"FEN: {fen}\n\n{pgn}"
                                    copied = copy_to_clipboard(combined)
                                    export_msg = "Copied FEN+PGN to clipboard" if copied else "Exported FEN/PGN to console"
                                    export_msg_time = pygame.time.get_ticks()
                                handled = True
                                break
                        if handled:
                            selected = None
                            moves = []
                            continue

                        # move list click
                        list_top, list_height, rows_visible, total_rows, max_start = ui.move_list_bounds(move_history)
                        start_row = max(0, min(scroll_row, max_start))
                        rel_y = y - list_top
                        if 0 <= rel_y < list_height:
                            row = rel_y // ui.ROW_H
                            actual_row = start_row + row
                            col_split = sidebar_x + ui.UI_PAD + (ui.SIDEBAR_WIDTH - 2*ui.UI_PAD)//2
                            col = 0 if x < col_split else 1
                            ply = actual_row*2 + col
                            if actual_row < total_rows and ply < len(move_history):
                                view_index = ply + 1  # board after that move
                                gs = copy.deepcopy(state_history[view_index])
                                selected = None
                                moves = []
                        continue

                    # Ignore board clicks when reviewing history or after game over
                    if game_over:
                        selected = None
                        moves = []
                        continue

                    # Ignore board clicks when reviewing history
                    if view_index != len(state_history) - 1:
                        selected = None
                        moves = []
                        continue

                    rc = ui.from_screen(x, y, flipped)
                    if rc is None:
                        continue
                    r, c = rc

                    if gs.board[r][c] != "--" and ((gs.board[r][c][0] == "w") == gs.white_turn):
                        # select and immediately start drag
                        selected = (r, c)
                        moves = gs.get_valid_moves(r, c)
                        dragging = {"from": (r, c), "pos": (x, y), "moves": moves}

                elif e.type == pygame.MOUSEMOTION:
                    if dragging:
                        dragging["pos"] = pygame.mouse.get_pos()

                elif e.type == pygame.MOUSEBUTTONUP:
                    if getattr(e, "button", 0) != 1:
                        continue
                    x, y = pygame.mouse.get_pos()
                    if dragging:
                        rc = ui.from_screen(x, y, flipped)
                        if rc and rc in dragging["moves"]:
                            sr, sc = dragging["from"]
                            r, c = rc
                            apply_move(sr, sc, r, c)
                            selected = None
                            moves = []
                        else:
                            # illegal drop: snap back, keep selection and show moves
                            selected = dragging["from"]
                            moves = dragging["moves"]
                        dragging = None
                    else:
                        rc = ui.from_screen(x, y, flipped)
                        if rc and selected and rc in moves:
                            sr, sc = selected
                            r, c = rc
                            apply_move(sr, sc, r, c)
                            selected = None
                            moves = []
                        elif rc and rc == selected:
                            selected = None
                            moves = []
                        elif rc and gs.board[rc[0]][rc[1]] != "--" and ((gs.board[rc[0]][rc[1]][0] == "w") == gs.white_turn):
                            selected = rc
                            moves = gs.get_valid_moves(rc[0], rc[1])
                        else:
                            # click empty or opponent square: keep or clear selection
                            selected = None
                            moves = []

            # clocks update
            now_tick = pygame.time.get_ticks()
            if clock_started and view_index == len(state_history) - 1 and run and not game_over:
                delta = now_tick - last_tick
                if gs.white_turn:
                    white_time = max(0, white_time - delta)
                else:
                    black_time = max(0, black_time - delta)
                if white_time == 0 or black_time == 0:
                    winner = "Black" if white_time == 0 else "White"
                    result = f"{winner} wins on time"
                    result_code = "0-1" if winner == "Black" else "1-0"
                    game_over = True
                    clock_started = False
                last_tick = now_tick
            else:
                last_tick = now_tick

            # layout for sidebar/buttons (used in both normal and animation render)
            pad = ui.UI_PAD
            # action buttons: 3 on upper row, 3 on lower row
            row1 = 3
            row2 = 3
            cols = max(row1, row2)
            btn_w = int((ui.SIDEBAR_WIDTH - pad*2 - ui.BTN_GAP*(cols-1)) / cols)
            btn_h = 24  # slimmer action buttons
            nav_y = ui.HEIGHT - pad - ui.BTN_H
            gap_between_rows = 10  # vertical gap between rows of buttons
            y_row2 = nav_y - gap_between_rows - btn_h
            y_row1 = y_row2 - gap_between_rows - btn_h
            sidebar_x = ui.BOARD_X + ui.BOARD_SIZE

            positions = []
            for i in range(row1):
                x = sidebar_x + pad + i*(btn_w + ui.BTN_GAP)
                positions.append((x, y_row1))
            for i in range(row2):
                x = sidebar_x + pad + i*(btn_w + ui.BTN_GAP)
                positions.append((x, y_row2))

            for (pos, b) in zip(positions, action_buttons):
                b["rect"] = pygame.Rect(pos[0], pos[1], btn_w, btn_h)
                b["enabled"] = True

            # update scrollbar alpha fade (show for 1s, then fade 0.3s)
            now = pygame.time.get_ticks()
            elapsed = now - last_scroll_ms
            if elapsed <= 1000:
                display_alpha = scroll_alpha
            elif elapsed <= 1300:
                display_alpha = int(scroll_alpha * max(0, 1 - (elapsed - 1000)/300))
            else:
                display_alpha = 0

            # Stockfish eval update when position/view changes
            skip_eval = False
            if animation and view_index == len(state_history) - 1:
                anim_progress = (now - animation["start"]) / animation["duration"]
                if anim_progress < 1:
                    skip_eval = True
            current_key = engine.position_key(state_history[view_index])
            now_tick_ms = now
            if not skip_eval:
                if current_key in eval_cache:
                    eval_cp, eval_mate, eval_text = eval_cache[current_key]
                    last_eval_key = current_key
                else:
                    if now_tick_ms - last_eval_tick >= 1000 or current_key != last_eval_key:
                        last_eval_tick = now_tick_ms
                        last_eval_key = current_key
                        res = analyzer.evaluate_state(state_history[view_index])
                        if res:
                            eval_cp = res.get("cp")
                            eval_mate = res.get("mate")
                            eval_text = res.get("text", "--")
                        else:
                            eval_cp = None
                            eval_mate = None
                            eval_text = analyzer.status or "--"
                        eval_cache[current_key] = (eval_cp, eval_mate, eval_text)

            # smooth the visible eval ratio toward target
            target_ratio = score_to_ratio(eval_cp, eval_mate)
            lerp = 0.12  # smoothing factor per frame
            eval_ratio += (target_ratio - eval_ratio) * lerp

            material = engine.material_diff(state_history[view_index].board)
            captured_white, captured_black = engine.captured_pieces(state_history[view_index].board)

            if game_over and not pgn_printed:
                pgn = build_pgn(move_history, result_code)
                print("\nPGN:\n" + pgn + "\n")
                try:
                    import chess.pgn
                    chess.pgn.read_game(io.StringIO(pgn))
                    print("PGN validated by python-chess.")
                except Exception:
                    pass
                pgn_printed = True
                engine_on = False
                for b in action_buttons:
                    if b["action"] == "engine":
                        b["label"] = "Engine: Off"
                        break

            # engine auto-move (plays Black by default)
            engine_to_move = engine_on and run and not game_over and view_index == len(state_history) - 1 and not animation and dragging is None and result is None and claimable is None and ((gs.white_turn and engine_is_white) or (not gs.white_turn and not engine_is_white))
            if engine_to_move and not engine_thinking and analyzer.available:
                engine_thinking = True
                move_res = analyzer.best_move(gs)
                engine_thinking = False
                if move_res:
                    sr, sc = move_res["from"]
                    er, ec = move_res["to"]
                    promo = move_res.get("promo")
                    apply_move(sr, sc, er, ec, promo_choice=promo)
                else:
                    engine_on = False
                    for b in action_buttons:
                        if b["action"] == "engine":
                            b["label"] = "Engine: Off"
                            break
            timers = "White to move" if gs.white_turn else "Black to move"
            msg = export_msg if export_msg and now - export_msg_time < 2000 else ""
            status_text = result or claimable or msg or ("Engine thinking..." if engine_thinking else "")

            # Rendering (with optional move animation)
            ui.clear()
            anim_active = animation and view_index == len(state_history) - 1
            if anim_active:
                anim = animation
                progress = (now - anim["start"]) / anim["duration"]
                if progress >= 1:
                    animation = None
                    anim_active = False

            if anim_active:
                sr, sc, er, ec = animation["move"]
                ui.draw_board(flipped)
                if last_move:
                    ui.highlight_last_move(last_move, flipped)
                if gs.in_check():
                    ui.highlight_check(gs, flipped)

                temp_board = copy.deepcopy(animation["to"])
                temp_board[er][ec] = "--"
                ui.draw_pieces(temp_board, flipped)

                start_x, start_y = ui.to_screen(sr, sc, flipped)
                end_x, end_y = ui.to_screen(er, ec, flipped)
                cx = int(start_x + (end_x - start_x) * progress)
                cy = int(start_y + (end_y - start_y) * progress)
                piece = animation["from"][sr][sc]
                img = ui.IMAGES.get(piece)
                if img:
                    ui.screen.blit(img, img.get_rect(topleft=(cx, cy)))

                ui.draw_eval_bar(eval_cp, eval_mate, flipped, ratio_override=eval_ratio)
                top_caps = captured_white if flipped else captured_black
                bot_caps = captured_black if flipped else captured_white
                ui.draw_player_bars("Player", "Computer", white_time, black_time, material_diff=material, captured_top=top_caps, captured_bot=bot_caps, flipped=flipped)
            else:
                ui.draw_board(flipped)

                # overlays first so pieces stay clean
                if last_move:
                    ui.highlight_last_move(last_move, flipped)
                if view_index == len(state_history) - 1 and gs.in_check():
                    ui.highlight_check(gs, flipped)
                # show legal targets under the pieces so they don't tint pieces
                if selected and view_index == len(state_history) - 1:
                    ui.highlight(moves, gs.board, flipped)
                # draw board state
                board_to_draw = state_history[view_index].board
                temp_board = board_to_draw
                if dragging and view_index == len(state_history) - 1:
                    temp_board = copy.deepcopy(board_to_draw)
                    sr, sc = dragging["from"]
                    temp_board[sr][sc] = "--"
                ui.draw_pieces(temp_board, flipped)

                # draw dragging piece on top
                if dragging:
                    sr, sc = dragging["from"]
                    px, py = dragging["pos"]
                    piece = gs.board[sr][sc]
                    img = ui.IMAGES.get(piece)
                    if img:
                        img_rect = img.get_rect(center=(px, py))
                        ui.screen.blit(img, img_rect)

                # player bars
                ui.draw_eval_bar(eval_cp, eval_mate, flipped, ratio_override=eval_ratio)
                top_caps = captured_white if flipped else captured_black
                bot_caps = captured_black if flipped else captured_white
                ui.draw_player_bars("Player", "Computer", white_time, black_time, material_diff=material, captured_top=top_caps, captured_bot=bot_caps, flipped=flipped)

            ui.draw_sidebar(move_history, view_index, len(state_history), buttons, status_text, scroll_row, display_alpha, timers=timers, flipped=flipped, draw_buttons=action_buttons, eval_text=eval_text)
            pygame.display.flip()

        if home_requested:
            tc = ui.choose_time_control()
            if tc is None:
                keep_playing = False
                break
            base_time_ms, increment_ms = tc
            home_requested = False
            continue

        if not keep_playing:
            break

    pygame.quit()


if __name__ == "__main__":
    main()
