import copy


class GameState:
  def __init__(self):
    self.board = [
      ["bR","bN","bB","bQ","bK","bB","bN","bR"],
      ["bp","bp","bp","bp","bp","bp","bp","bp"],
      ["--","--","--","--","--","--","--","--"],
      ["--","--","--","--","--","--","--","--"],
      ["--","--","--","--","--","--","--","--"],
      ["--","--","--","--","--","--","--","--"],
      ["wp","wp","wp","wp","wp","wp","wp","wp"],
      ["wR","wN","wB","wQ","wK","wB","wN","wR"]
    ]

    self.white_turn = True
    self.en_passant = None
    self.castling = {"wK": True, "wQ": True, "bK": True, "bQ": True}
    self.halfmove_clock = 0
    self.fullmove_number = 1

  def move(self, sr, sc, er, ec):
    piece = self.board[sr][sc]
    target_piece = self.board[er][ec]
    promotion = None

    if piece[1] == "p" and (er, ec) == self.en_passant:
      self.board[sr][ec] = "--"
      target_piece = "bp" if piece[0] == "w" else "wp"

    self.board[er][ec] = piece
    self.board[sr][sc] = "--"

    if piece == "wp" and er == 0:
      self.board[er][ec] = "wQ"
      promotion = (er, ec, "w")
    if piece == "bp" and er == 7:
      self.board[er][ec] = "bQ"
      promotion = (er, ec, "b")

    if piece[1] == "p" and abs(er - sr) == 2:
      self.en_passant = ((sr + er)//2, ec)
    else:
      self.en_passant = None

    if piece[1] == "K":
      if ec - sc == 2:
        self.board[er][5] = self.board[er][7]
        self.board[er][7] = "--"
      elif ec - sc == -2:
        self.board[er][3] = self.board[er][0]
        self.board[er][0] = "--"

    if piece == "wK":
      self.castling["wK"] = self.castling["wQ"] = False
    if piece == "bK":
      self.castling["bK"] = self.castling["bQ"] = False
    if piece == "wR":
      if sr == 7 and sc == 0:
        self.castling["wQ"] = False
      if sr == 7 and sc == 7:
        self.castling["wK"] = False
    if piece == "bR":
      if sr == 0 and sc == 0:
        self.castling["bQ"] = False
      if sr == 0 and sc == 7:
        self.castling["bK"] = False

    if target_piece == "wR":
      if er == 7 and ec == 0:
        self.castling["wQ"] = False
      if er == 7 and ec == 7:
        self.castling["wK"] = False
    if target_piece == "bR":
      if er == 0 and ec == 0:
        self.castling["bQ"] = False
      if er == 0 and ec == 7:
        self.castling["bK"] = False

    self.white_turn = not self.white_turn
    if not self.white_turn:
      self.fullmove_number += 1

    if piece[1] == "p" or target_piece != "--":
      self.halfmove_clock = 0
    else:
      self.halfmove_clock += 1
    return promotion

  def get_valid_moves(self, r, c):
    moves = self.get_all_moves(r, c)
    valid = []
    for m in moves:
      temp = copy.deepcopy(self)
      temp.move(r, c, m[0], m[1])
      temp.white_turn = self.white_turn
      if not temp.in_check():
        valid.append(m)
    return valid

  def in_check(self):
    king = "wK" if self.white_turn else "bK"
    for r in range(8):
      for c in range(8):
        if self.board[r][c] == king:
          return self.square_under_attack(r, c)
    return False

  def square_under_attack(self, r, c):
    self.white_turn = not self.white_turn
    for i in range(8):
      for j in range(8):
        if self.board[i][j] != "--":
          for m in self.get_all_moves(i, j, allow_castling=False):
            if m == (r, c):
              self.white_turn = not self.white_turn
              return True
    self.white_turn = not self.white_turn
    return False

  def get_all_moves(self, r, c, allow_castling=True):
    piece = self.board[r][c]
    if piece == "--":
      return []
    color = piece[0]
    if (color == "w") != self.white_turn:
      return []
    if piece[1] == "p":
      return self.pawn_moves(r, c, color)
    if piece[1] == "R":
      return self.rook_moves(r, c, color)
    if piece[1] == "N":
      return self.knight_moves(r, c, color)
    if piece[1] == "B":
      return self.bishop_moves(r, c, color)
    if piece[1] == "Q":
      return self.queen_moves(r, c, color)
    if piece[1] == "K":
      return self.king_moves(r, c, color, allow_castling)

  def pawn_moves(self, r, c, color):
    moves = []
    d = -1 if color == "w" else 1
    start = 6 if color == "w" else 1
    if 0 <= r+d < 8 and self.board[r+d][c] == "--":
      moves.append((r+d, c))
      if r == start and self.board[r+2*d][c] == "--":
        moves.append((r+2*d, c))
    for dc in [-1, 1]:
      nr, nc = r+d, c+dc
      if 0 <= nr < 8 and 0 <= nc < 8:
        if self.board[nr][nc] != "--" and self.board[nr][nc][0] != color:
          moves.append((nr, nc))
        if (nr, nc) == self.en_passant:
          moves.append((nr, nc))
    return moves

  def rook_moves(self, r, c, color):
    moves = []
    for dr, dc in [(1,0),(-1,0),(0,1),(0,-1)]:
      for i in range(1,8):
        nr, nc = r+dr*i, c+dc*i
        if 0 <= nr < 8 and 0 <= nc < 8:
          if self.board[nr][nc] == "--":
            moves.append((nr,nc))
          elif self.board[nr][nc][0] != color:
            moves.append((nr,nc))
            break
          else:
            break
    return moves

  def bishop_moves(self, r, c, color):
    moves = []
    for dr, dc in [(1,1),(1,-1),(-1,1),(-1,-1)]:
      for i in range(1,8):
        nr, nc = r+dr*i, c+dc*i
        if 0 <= nr < 8 and 0 <= nc < 8:
          if self.board[nr][nc] == "--":
            moves.append((nr,nc))
          elif self.board[nr][nc][0] != color:
            moves.append((nr,nc))
            break
          else:
            break
    return moves

  def queen_moves(self, r, c, color):
    return self.rook_moves(r,c,color) + self.bishop_moves(r,c,color)

  def knight_moves(self, r, c, color):
    moves = []
    for dr, dc in [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]:
      nr, nc = r+dr, c+dc
      if 0 <= nr < 8 and 0 <= nc < 8:
        if self.board[nr][nc] == "--" or self.board[nr][nc][0] != color:
          moves.append((nr,nc))
    return moves

  def king_moves(self, r, c, color, allow_castling=True):
    moves = []
    for dr, dc in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
      nr, nc = r+dr, c+dc
      if 0 <= nr < 8 and 0 <= nc < 8:
        if self.board[nr][nc] == "--" or self.board[nr][nc][0] != color:
          moves.append((nr,nc))
    if allow_castling:
      if color == "w" and r == 7 and c == 4:
        if self.castling["wK"] and self.board[7][5] == "--" and self.board[7][6] == "--":
          if not self.square_under_attack(7,4) and not self.square_under_attack(7,5) and not self.square_under_attack(7,6):
            moves.append((7,6))
        if self.castling["wQ"] and self.board[7][1] == "--" and self.board[7][2] == "--" and self.board[7][3] == "--":
          if not self.square_under_attack(7,4) and not self.square_under_attack(7,3) and not self.square_under_attack(7,2):
            moves.append((7,2))
      if color == "b" and r == 0 and c == 4:
        if self.castling["bK"] and self.board[0][5] == "--" and self.board[0][6] == "--":
          if not self.square_under_attack(0,4) and not self.square_under_attack(0,5) and not self.square_under_attack(0,6):
            moves.append((0,6))
        if self.castling["bQ"] and self.board[0][1] == "--" and self.board[0][2] == "--" and self.board[0][3] == "--":
          if not self.square_under_attack(0,4) and not self.square_under_attack(0,3) and not self.square_under_attack(0,2):
            moves.append((0,2))
    return moves


def square_name(r, c):
  file = chr(ord("a") + c)
  rank = str(8 - r)
  return f"{file}{rank}"


def has_moves(gs):
  for r in range(8):
    for c in range(8):
      if gs.get_valid_moves(r,c):
        return True
  return False


def insufficient_material(board):
  pieces = []
  bishops_white = []
  bishops_black = []
  for r in range(8):
    for c in range(8):
      p = board[r][c]
      if p == "--":
        continue
      if p[1] == "K":
        continue
      pieces.append(p)
      if p[1] == "B":
        color_square = (r + c) % 2
        if p[0] == "w":
          bishops_white.append(color_square)
        else:
          bishops_black.append(color_square)
  if not pieces:
    return True
  if len(pieces) == 1 and pieces[0][1] in ("B","N"):
    return True
  if all(p[1] == "B" for p in pieces):
    all_colors = bishops_white + bishops_black
    return len(all_colors) > 0 and (len(set(all_colors)) == 1 or True)
  if all(p[1] == "N" for p in pieces):
    return True
  return False


def position_key(gs):
  board_tuple = tuple(tuple(row) for row in gs.board)
  castle = (gs.castling["wK"], gs.castling["wQ"], gs.castling["bK"], gs.castling["bQ"])
  ep = gs.en_passant if gs.en_passant is None else tuple(gs.en_passant)
  return (board_tuple, gs.white_turn, castle, ep)


def move_san(gs_before, sr, sc, er, ec, captured_piece, promotion_choice, was_en_passant):
  piece = gs_before.board[sr][sc]
  color = piece[0]
  p = piece[1]
  if p == "K" and abs(ec - sc) == 2:
    san = "O-O" if ec > sc else "O-O-O"
  else:
    target = square_name(er, ec)
    capture = captured_piece != "--" or was_en_passant
    if p == "p":
      prefix = chr(ord("a") + sc) if capture else ""
      capture_mark = "x" if capture else ""
      promo = f"={promotion_choice.upper()}" if promotion_choice else ""
      ep = " e.p." if was_en_passant else ""
      san = f"{prefix}{capture_mark}{target}{promo}{ep}"
    else:
      disamb = ""
      others = []
      for r in range(8):
        for c in range(8):
          if (r, c) == (sr, sc):
            continue
          if gs_before.board[r][c] == piece:
            if (er, ec) in gs_before.get_valid_moves(r, c):
              others.append((r, c))
      if others:
        same_file = any(c == sc for _, c in others)
        same_rank = any(r == sr for r, _ in others)
        if not same_file:
          disamb = chr(ord("a") + sc)
        elif not same_rank:
          disamb = str(8 - sr)
        else:
          disamb = square_name(sr, sc)
      capture_mark = "x" if capture else ""
      piece_letter = {"K":"K","Q":"Q","R":"R","B":"B","N":"N"}[p]
      san = f"{piece_letter}{disamb}{capture_mark}{target}"

  gs_after = copy.deepcopy(gs_before)
  promotion_info = gs_after.move(sr, sc, er, ec)
  if promotion_info and promotion_choice:
    pr, pc, _ = promotion_info
    gs_after.board[pr][pc] = color + promotion_choice
  check = gs_after.in_check()
  mate = check and not has_moves(gs_after)
  if mate:
    san += "#"
  elif check:
    san += "+"
  return san


def to_fen(gs: GameState):
  """Serialize the current GameState into a FEN string for engine use."""
  piece_map = {"p": "p", "R": "r", "N": "n", "B": "b", "Q": "q", "K": "k"}

  rows = []
  for row in gs.board:
    empty = 0
    parts = []
    for cell in row:
      if cell == "--":
        empty += 1
      else:
        if empty:
          parts.append(str(empty))
          empty = 0
        color = cell[0]
        piece = piece_map[cell[1]]
        parts.append(piece.upper() if color == "w" else piece)
    if empty:
      parts.append(str(empty))
    rows.append("".join(parts))

  board_fen = "/".join(rows)
  active = "w" if gs.white_turn else "b"

  castle = ""
  if gs.castling.get("wK"):
    castle += "K"
  if gs.castling.get("wQ"):
    castle += "Q"
  if gs.castling.get("bK"):
    castle += "k"
  if gs.castling.get("bQ"):
    castle += "q"
  castle = castle or "-"

  ep = square_name(*gs.en_passant) if gs.en_passant else "-"

  return f"{board_fen} {active} {castle} {ep} {gs.halfmove_clock} {gs.fullmove_number}"


def material_diff(board):
  """Return material balance: positive = White ahead, negative = Black ahead."""
  values = {"p": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 0}
  score = 0
  for row in board:
    for cell in row:
      if cell == "--":
        continue
      color, piece = cell[0], cell[1]
      val = values.get(piece, 0)
      score += val if color == "w" else -val
  return score


def captured_pieces(board):
  """
  Return (captured_by_white, captured_by_black) as lists of piece codes like 'bp','wQ'.
  These are pieces missing from the opposing side compared to the starting position.
  """
  start_counts = {"p": 8, "N": 2, "B": 2, "R": 2, "Q": 1, "K": 1}
  counts = {
    "w": {"p": 0, "N": 0, "B": 0, "R": 0, "Q": 0, "K": 0},
    "b": {"p": 0, "N": 0, "B": 0, "R": 0, "Q": 0, "K": 0},
  }
  for row in board:
    for cell in row:
      if cell == "--":
        continue
      color, piece = cell[0], cell[1]
      counts[color][piece] += 1

  def missing(color):
    """Pieces of 'color' that have been captured by the opponent."""
    out = []
    for p in ["Q", "R", "B", "N", "p"]:  # descending importance for display
      missing_count = start_counts[p] - counts[color][p]
      if missing_count > 0:
        out.extend([color + p] * missing_count)
    return out

  captured_by_white = missing("b")  # White captured Black's missing pieces
  captured_by_black = missing("w")  # Black captured White's missing pieces
  return captured_by_white, captured_by_black
