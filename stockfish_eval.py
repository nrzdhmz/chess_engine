import atexit
import shutil
from pathlib import Path

import engine


class StockfishAnalyzer:
    def __init__(self, path=None, think_time=0.25, depth=None):
        self.requested_path = path
        self.think_time = think_time
        self.depth = depth
        self.engine_path = None
        self.engine = None
        self.available = False
        self.status = ""
        self._chess = None
        self._chess_engine = None
        self._init_engine()

    def _init_engine(self):
        try:
            import chess
            import chess.engine
        except Exception:
            self.status = "Install python-chess to enable eval"
            return

        self._chess = chess
        self._chess_engine = chess.engine

        self.engine_path = self._find_engine(self.requested_path)
        if not self.engine_path:
            self.status = "Stockfish binary not found"
            return

        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            self.available = True
            self.status = f"Using Stockfish at {self.engine_path}"
            atexit.register(self.close)
        except Exception:
            self.engine = None
            self.available = False
            self.status = "Failed to start Stockfish"

    def _find_engine(self, path_hint):
        candidates = []
        if path_hint:
            candidates.append(path_hint)
        candidates.extend([
            "./stockfish",
            "./bin/stockfish",
            "stockfish",
        ])
        for cand in candidates:
            if cand:
                p = Path(cand).expanduser()
                if p.is_file() and p.exists():
                    return str(p)
                resolved = shutil.which(cand)
                if resolved:
                    return resolved
        return None

    def evaluate_state(self, gs):
        if not self.available or not self.engine:
            return None

        fen = engine.to_fen(gs)
        board = self._chess.Board(fen)
        limit = self._chess_engine.Limit(depth=self.depth) if self.depth else self._chess_engine.Limit(time=self.think_time)

        try:
            info = self.engine.analyse(board, limit)
        except Exception:
            self.status = "Stockfish analyse failed"
            return None

        score = info.get("score")
        if score is None:
            return None

        pov = score.white()
        mate = pov.mate()
        cp = None if mate is not None else pov.score(mate_score=32000)
        text = self._format(cp, mate)
        return {"cp": cp, "mate": mate, "text": text}

    def best_move(self, gs):
        """Return the best move for the side to move as dict with keys: from, to, promo."""
        if not self.available or not self.engine:
            return None
        fen = engine.to_fen(gs)
        board = self._chess.Board(fen)
        limit = self._chess_engine.Limit(depth=self.depth) if self.depth else self._chess_engine.Limit(time=self.think_time)
        try:
            result = self.engine.play(board, limit)
        except Exception:
            self.status = "Stockfish play failed"
            return None
        move = result.move
        if move is None:
            return None

        def square_to_rc(sq):
            rank = sq // 8  # 0 = rank1 (white home)
            file = sq % 8
            return 7 - rank, file  # our board row 0 is rank 8

        sr, sc = square_to_rc(move.from_square)
        er, ec = square_to_rc(move.to_square)
        promo = None
        if move.promotion:
            promo_map = {
                self._chess.QUEEN: "Q",
                self._chess.ROOK: "R",
                self._chess.BISHOP: "B",
                self._chess.KNIGHT: "N",
            }
            promo = promo_map.get(move.promotion)
        return {"from": (sr, sc), "to": (er, ec), "promo": promo}

    def _format(self, cp, mate):
        if mate is not None:
            return f"Mate in {abs(mate)}" if mate > 0 else f"-Mate in {abs(mate)}"
        if cp is None:
            return "--"
        return f"{cp/100:+.2f}"

    def close(self):
        try:
            if self.engine:
                self.engine.quit()
        finally:
            self.engine = None
