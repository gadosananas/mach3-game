import random
import tkinter as tk
from tkinter import messagebox, simpledialog
from functools import partial
import threading
try:
    import winsound
    SOUND_AVAILABLE = True
except ImportError:
    SOUND_AVAILABLE = False

# Constants
grid_size = 8
tile_types = ['A', 'B', 'C', 'D', 'E']
tile_colors = {
    'A': 'red',
    'B': 'blue',
    'C': 'green',
    'D': 'yellow',
    'E': 'purple',
}
HIGHLIGHT_COLOR = 'white'
SCORE_POP_COLOR = 'orange'
SCORE_NORMAL_COLOR = 'black'

LEVEL_BASE_TARGET = 30
LEVEL_TARGET_INCREMENT = 20

# Special tile types
STRIPED_H = 'SH'  # Horizontal striped
STRIPED_V = 'SV'  # Vertical striped
COLOR_BOMB = 'CB'

SPECIAL_TILE_BG = {
    STRIPED_H: 'lightblue',
    STRIPED_V: 'lightgreen',
    COLOR_BOMB: 'black',
}

SPECIAL_TILE_TEXT = {
    STRIPED_H: '-',
    STRIPED_V: '|',
    COLOR_BOMB: '*',
}

TILE_SIZE = 48
TILE_PAD = 4
ANIMATION_SPEED = 8  # pixels per frame

# Game modes
game_modes = ["Objective Mode", "Endless Mode"]

def create_board():
    return [[random.choice(tile_types) for _ in range(grid_size)] for _ in range(grid_size)]

def is_special(tile):
    return isinstance(tile, tuple)

def get_tile_type(tile):
    if is_special(tile):
        return tile[0]
    return tile

def get_special_kind(tile):
    if is_special(tile):
        return tile[1]
    return None

def find_matches_with_lengths(board):
    matched = dict()
    # Horizontal matches
    for y in range(grid_size):
        count = 1
        for x in range(1, grid_size):
            if get_tile_type(board[y][x]) == get_tile_type(board[y][x-1]) and get_tile_type(board[y][x]) not in [COLOR_BOMB]:
                count += 1
            else:
                if count >= 3:
                    for k in range(count):
                        matched[(x-1-k, y)] = count
                count = 1
        if count >= 3:
            for k in range(count):
                matched[(grid_size-1-k, y)] = count
    # Vertical matches
    for x in range(grid_size):
        count = 1
        for y in range(1, grid_size):
            if get_tile_type(board[y][x]) == get_tile_type(board[y-1][x]) and get_tile_type(board[y][x]) not in [COLOR_BOMB]:
                count += 1
            else:
                if count >= 3:
                    for k in range(count):
                        pos = (x, y-1-k)
                        matched[pos] = max(matched.get(pos, 0), count)
                count = 1
        if count >= 3:
            for k in range(count):
                pos = (x, grid_size-1-k)
                matched[pos] = max(matched.get(pos, 0), count)
    return matched

def clear_matches(board, matches):
    for (x, y) in matches:
        board[y][x] = None

def drop_tiles(board):
    for x in range(grid_size):
        col = [board[y][x] for y in range(grid_size)]
        col = [tile for tile in col if tile is not None]
        missing = grid_size - len(col)
        new_col = [None]*missing + col
        for y in range(grid_size):
            board[y][x] = new_col[y]

def refill_board(board):
    for y in range(grid_size):
        for x in range(grid_size):
            if board[y][x] is None:
                board[y][x] = random.choice(tile_types)

def is_adjacent(x1, y1, x2, y2):
    return (abs(x1 - x2) == 1 and y1 == y2) or (abs(y1 - y2) == 1 and x1 == x2)

def has_possible_moves(board):
    for y in range(grid_size):
        for x in range(grid_size):
            for dx, dy in [(1,0),(0,1)]:
                nx, ny = x+dx, y+dy
                if nx < grid_size and ny < grid_size:
                    t1, t2 = board[y][x], board[ny][nx]
                    board[y][x], board[ny][nx] = t2, t1
                    if find_matches_with_lengths(board):
                        board[y][x], board[ny][nx] = t1, t2
                        return True
                    board[y][x], board[ny][nx] = t1, t2
    return False

def simulate_move_and_score(board, x1, y1, x2, y2):
    temp_board = [row[:] for row in board]
    temp_board[y1][x1], temp_board[y2][x2] = temp_board[y2][x2], temp_board[y1][x1]
    total_score = 0
    matches = find_matches_with_lengths(temp_board)
    while matches:
        for pos, length in matches.items():
            if length >= 5:
                total_score += 3
            elif length == 4:
                total_score += 2
            else:
                total_score += 1
        clear_matches(temp_board, matches)
        drop_tiles(temp_board)
        refill_board(temp_board)
        matches = find_matches_with_lengths(temp_board)
    return total_score

class Match3Game:
    def __init__(self, root):
        self.root = root
        self.mode = self.ask_mode()
        self.board = create_board()
        while find_matches_with_lengths(self.board):
            self.board = create_board()
        self.score = 0
        self.level = 1
        self.high_score = 0
        self.target_score = LEVEL_BASE_TARGET
        self.selected = None  # (x, y) or None
        self.bot_running = False
        self.bot_should_stop = False
        self.objective_color = None
        self.objective_target = None
        self.objective_progress = 0
        self.objective_label = None
        if self.mode == "Objective Mode":
            self.set_new_objective()
        # Top info frame for labels
        self.info_frame = tk.Frame(root)
        self.info_frame.grid(row=0, column=0, columnspan=grid_size, sticky='ew')
        self.info_frame.grid_columnconfigure(0, weight=1)
        self.info_frame.grid_columnconfigure(1, weight=1)
        self.info_frame.grid_columnconfigure(2, weight=1)
        self.score_label = tk.Label(self.info_frame, text=f"Score: {self.score}", font=("Arial", 16), fg=SCORE_NORMAL_COLOR, anchor='w', justify='left')
        self.score_label.grid(row=0, column=0, sticky='w')
        self.level_label = tk.Label(self.info_frame, text=f"Level: {self.level}", font=("Arial", 16))
        self.level_label.grid(row=0, column=1)
        self.target_label = tk.Label(self.info_frame, text=f"Target: {self.target_score}", font=("Arial", 16))
        self.target_label.grid(row=0, column=2, sticky='e')
        if self.mode == "Objective Mode":
            self.objective_label = tk.Label(root, text=self.get_objective_text(), font=("Arial", 15, "bold"), fg=self.get_objective_color())
            self.objective_label.grid(row=1, column=0, columnspan=grid_size, sticky='ew')
        self.high_score_label = tk.Label(root, text=f"High Score: {self.high_score}", font=("Arial", 12), anchor='e', justify='right')
        self.high_score_label.grid(row=grid_size+2, column=0, columnspan=grid_size, sticky='e')
        # Canvas for board
        self.canvas = tk.Canvas(root, width=grid_size*TILE_SIZE, height=grid_size*TILE_SIZE, bg='white', highlightthickness=0)
        self.canvas.grid(row=2, column=0, columnspan=grid_size)
        self.canvas.bind('<Button-1>', self.on_canvas_click)
        self.tile_items = [[None for _ in range(grid_size)] for _ in range(grid_size)]
        self.animating = False
        # Bot controls
        self.bot_button = tk.Button(root, text="Bot Move", font=("Arial", 12), command=self.bot_move)
        self.bot_button.grid(row=grid_size+3, column=0, columnspan=grid_size//3, sticky="we")
        self.start_bot_button = tk.Button(root, text="Start Bot", font=("Arial", 12), command=self.start_bot)
        self.start_bot_button.grid(row=grid_size+3, column=grid_size//3, columnspan=grid_size//3, sticky="we")
        self.stop_bot_button = tk.Button(root, text="Stop Bot", font=("Arial", 12), command=self.stop_bot)
        self.stop_bot_button.grid(row=grid_size+3, column=2*grid_size//3, columnspan=grid_size-2*grid_size//3, sticky="we")
        self.update_board()

    def ask_mode(self):
        # Use a dialog with two buttons instead of text input
        mode_choice = {'mode': None}
        dialog = tk.Toplevel(self.root)
        dialog.title("Choose Game Mode")
        dialog.geometry("300x120")
        dialog.grab_set()
        label = tk.Label(dialog, text="Choose Game Mode:", font=("Arial", 14))
        label.pack(pady=10)
        def choose_objective():
            mode_choice['mode'] = "Objective Mode"
            dialog.destroy()
        def choose_endless():
            mode_choice['mode'] = "Endless Mode"
            dialog.destroy()
        btn_obj = tk.Button(dialog, text="Objective Mode", font=("Arial", 12), width=15, command=choose_objective)
        btn_obj.pack(pady=2)
        btn_end = tk.Button(dialog, text="Endless Mode", font=("Arial", 12), width=15, command=choose_endless)
        btn_end.pack(pady=2)
        self.root.wait_window(dialog)
        return mode_choice['mode'] or "Objective Mode"

    def set_new_objective(self):
        self.objective_color = random.choice(tile_types)
        self.objective_target = random.randint(12, 20) + self.level * 2
        self.objective_progress = 0

    def get_objective_text(self):
        return f"Objective: Clear {self.objective_target} {self.objective_color} tiles ({self.objective_progress}/{self.objective_target})"

    def get_objective_color(self):
        return tile_colors.get(self.objective_color, 'black')

    def canvas_coords(self, x, y):
        return x*TILE_SIZE+TILE_PAD, y*TILE_SIZE+TILE_PAD

    def draw_tile(self, x, y, tile, highlight=False):
        color = tile_colors.get(get_tile_type(tile), 'gray')
        if is_special(tile):
            kind = get_special_kind(tile)
            base = get_tile_type(tile)
            if kind == STRIPED_H:
                color = SPECIAL_TILE_BG[STRIPED_H]
            elif kind == STRIPED_V:
                color = SPECIAL_TILE_BG[STRIPED_V]
            elif kind == COLOR_BOMB:
                color = SPECIAL_TILE_BG[COLOR_BOMB]
        if highlight:
            color = HIGHLIGHT_COLOR
        x0, y0 = self.canvas_coords(x, y)
        rect = self.canvas.create_rectangle(x0, y0, x0+TILE_SIZE-2*TILE_PAD, y0+TILE_SIZE-2*TILE_PAD, fill=color, outline='black', width=2)
        text = get_tile_type(tile)
        if is_special(tile):
            kind = get_special_kind(tile)
            if kind == STRIPED_H:
                text += SPECIAL_TILE_TEXT[STRIPED_H]
            elif kind == STRIPED_V:
                text += SPECIAL_TILE_TEXT[STRIPED_V]
            elif kind == COLOR_BOMB:
                text = SPECIAL_TILE_TEXT[COLOR_BOMB]
        txt = self.canvas.create_text(x0+TILE_SIZE//2-TILE_PAD, y0+TILE_SIZE//2-TILE_PAD, text=text, font=("Arial", 18, "bold"), fill='white' if is_special(tile) and get_special_kind(tile)==COLOR_BOMB else 'black')
        return rect, txt

    def update_board(self, highlight_matches=None):
        self.canvas.delete('all')
        for y in range(grid_size):
            for x in range(grid_size):
                highlight = highlight_matches and (x, y) in highlight_matches
                self.draw_tile(x, y, self.board[y][x], highlight=highlight)
        self.score_label.config(text=f"Score: {self.score}", fg=SCORE_NORMAL_COLOR)
        self.level_label.config(text=f"Level: {self.level}")
        self.target_label.config(text=f"Target: {self.target_score}")
        self.high_score_label.config(text=f"High Score: {self.high_score}")
        if self.mode == "Objective Mode" and self.objective_label:
            self.objective_label.config(text=self.get_objective_text(), fg=self.get_objective_color())
        # Visually disable bot controls if animating
        state = tk.DISABLED if self.bot_running or self.animating else tk.NORMAL
        self.bot_button.config(state=state)
        self.start_bot_button.config(state=state if not self.bot_running and not self.animating else tk.DISABLED)
        self.stop_bot_button.config(state=tk.NORMAL if self.bot_running else tk.DISABLED)

    def on_canvas_click(self, event):
        if self.bot_running or self.animating:
            return
        x = event.x // TILE_SIZE
        y = event.y // TILE_SIZE
        if not (0 <= x < grid_size and 0 <= y < grid_size):
            return
        if self.selected is None:
            self.selected = (x, y)
            self.update_board()
            self.highlight_selected()
        else:
            x1, y1 = self.selected
            if (x, y) == (x1, y1):
                self.selected = None
                self.update_board()
                return
            t1 = self.board[y1][x1]
            t2 = self.board[y][x]
            if is_special(t1) and get_special_kind(t1) == COLOR_BOMB:
                self.activate_color_bomb(x1, y1, get_tile_type(t2))
                self.selected = None
                self.update_board()
                return
            if is_special(t2) and get_special_kind(t2) == COLOR_BOMB:
                self.activate_color_bomb(x, y, get_tile_type(t1))
                self.selected = None
                self.update_board()
                return
            if is_adjacent(x, y, x1, y1):
                self.animate_swap(x1, y1, x, y)
                self.selected = None
            else:
                self.selected = (x, y)
                self.update_board()
                self.highlight_selected()

    def highlight_selected(self):
        if self.selected:
            x, y = self.selected
            x0, y0 = self.canvas_coords(x, y)
            self.canvas.create_rectangle(x0, y0, x0+TILE_SIZE-2*TILE_PAD, y0+TILE_SIZE-2*TILE_PAD, outline='orange', width=4)

    def animate_swap(self, x1, y1, x2, y2):
        self.animating = True
        dx = (x2 - x1) * ANIMATION_SPEED
        dy = (y2 - y1) * ANIMATION_SPEED
        steps = TILE_SIZE // ANIMATION_SPEED
        tile1 = self.board[y1][x1]
        tile2 = self.board[y2][x2]
        # Draw initial positions
        self.update_board()
        rect1, txt1 = self.draw_tile(x1, y1, tile1)
        rect2, txt2 = self.draw_tile(x2, y2, tile2)
        def move_step(step):
            if step > steps:
                self.canvas.delete(rect1)
                self.canvas.delete(txt1)
                self.canvas.delete(rect2)
                self.canvas.delete(txt2)
                self.board[y1][x1], self.board[y2][x2] = self.board[y2][x2], self.board[y1][x1]
                matches = find_matches_with_lengths(self.board)
                if not matches:
                    self.board[y1][x1], self.board[y2][x2] = self.board[y2][x2], self.board[y1][x1]
                    self.animating = False
                    self.update_board()
                    return
                self.process_matches(matches)
                self.animating = False
                return
            self.canvas.move(rect1, dx, dy)
            self.canvas.move(txt1, dx, dy)
            self.canvas.move(rect2, -dx, -dy)
            self.canvas.move(txt2, -dx, -dy)
            self.root.after(10, lambda: move_step(step+1))
        move_step(1)

    def highlight_matches(self, matches, callback):
        # Highlight matched tiles and show sparkles
        self.update_board(highlight_matches=matches)
        for (x, y) in matches:
            self.show_sparkle(x, y)
        self.root.after(250, callback)

    def show_sparkle(self, x, y):
        # Simple sparkle effect: draw a few white circles
        x0, y0 = self.canvas_coords(x, y)
        for i in range(6):
            r = 4 + i*2
            oval = self.canvas.create_oval(x0+TILE_SIZE//2-r, y0+TILE_SIZE//2-r, x0+TILE_SIZE//2+r, y0+TILE_SIZE//2+r, outline='white', width=2)
            self.root.after(40*i, lambda o=oval: self.canvas.delete(o))

    def play_match_sound(self):
        if SOUND_AVAILABLE:
            threading.Thread(target=lambda: winsound.Beep(800, 120)).start()

    def pop_score(self):
        self.score_label.config(fg=SCORE_POP_COLOR, font=("Arial", 18, "bold"))
        self.root.after(200, lambda: self.score_label.config(fg=SCORE_NORMAL_COLOR, font=("Arial", 16)))

    def process_matches(self, matches):
        # Visual highlight
        self.highlight_matches(matches, lambda: self._after_highlight(matches))
        self.play_match_sound()
        self.pop_score()

    def _after_highlight(self, matches):
        # Special tile creation and effect
        specials_to_create = []
        color_counts = {c: 0 for c in tile_types}
        for pos, length in matches.items():
            x, y = pos
            base = get_tile_type(self.board[y][x])
            if base in color_counts:
                color_counts[base] += 1
            if length == 4:
                # Striped tile: randomly horizontal or vertical
                kind = random.choice([STRIPED_H, STRIPED_V])
                specials_to_create.append((x, y, (base, kind)))
            elif length >= 5:
                # Color bomb
                specials_to_create.append((x, y, (base, COLOR_BOMB)))
        # Objective mode: update progress
        if self.mode == "Objective Mode" and self.objective_color:
            self.objective_progress += color_counts.get(self.objective_color, 0)
        # Scoring: 3 in a row = 1pt/tile, 4 in a row = 2pt/tile, 5+ in a row = 3pt/tile
        for pos, length in matches.items():
            if length >= 5:
                self.score += 3
            elif length == 4:
                self.score += 2
            else:
                self.score += 1
        # Place special tiles after clearing
        clear_matches(self.board, matches)
        for x, y, special in specials_to_create:
            self.board[y][x] = special
        # Activate special effects if matched
        for pos in matches:
            x, y = pos
            tile = self.board[y][x]
            if is_special(tile):
                kind = get_special_kind(tile)
                if kind == STRIPED_H:
                    for xx in range(grid_size):
                        self.board[y][xx] = None
                elif kind == STRIPED_V:
                    for yy in range(grid_size):
                        self.board[yy][x] = None
        drop_tiles(self.board)
        refill_board(self.board)
        self.update_board()
        # Progression: check for level up or objective
        if self.mode == "Objective Mode" and self.objective_progress >= self.objective_target:
            self.level_up_objective()
            return
        if self.score >= self.target_score:
            self.level_up()
            return
        next_matches = find_matches_with_lengths(self.board)
        if next_matches:
            self.process_matches(next_matches)
        else:
            if not has_possible_moves(self.board):
                self.end_game()

    def level_up_objective(self):
        self.level += 1
        self.target_score += LEVEL_TARGET_INCREMENT
        self.set_new_objective()
        self.score_label.config(fg='green')
        self.update_board()
        # Refill board for new level
        self.board = create_board()
        while find_matches_with_lengths(self.board):
            self.board = create_board()
        self.update_board()

    def activate_color_bomb(self, x, y, color):
        # Remove all tiles of the given color
        for yy in range(grid_size):
            for xx in range(grid_size):
                if get_tile_type(self.board[yy][xx]) == color:
                    self.board[yy][xx] = None
        self.board[y][x] = None
        drop_tiles(self.board)
        refill_board(self.board)
        self.update_board()
        next_matches = find_matches_with_lengths(self.board)
        if next_matches:
            self.process_matches(next_matches)
        else:
            if not has_possible_moves(self.board):
                self.end_game()

    def level_up(self):
        self.level += 1
        self.target_score += LEVEL_TARGET_INCREMENT
        self.score_label.config(fg='green')
        self.update_board()
        # Refill board for new level
        self.board = create_board()
        while find_matches_with_lengths(self.board):
            self.board = create_board()
        self.update_board()

    def end_game(self):
        if self.score > self.high_score:
            self.high_score = self.score
            self.update_board()
            messagebox.showinfo("Game Over", f"New High Score! {self.score}")
        else:
            messagebox.showinfo("Game Over", f"No more possible moves! Final Score: {self.score}")
        self.root.destroy()

    def bot_move(self):
        best_score = -1
        best_move = None
        for y in range(grid_size):
            for x in range(grid_size):
                for dx, dy in [(1,0),(0,1)]:
                    nx, ny = x+dx, y+dy
                    if nx < grid_size and ny < grid_size:
                        score = simulate_move_and_score(self.board, x, y, nx, ny)
                        if score > best_score:
                            best_score = score
                            best_move = (x, y, nx, ny)
        if best_move:
            self.animate_swap(*best_move)
            self.update_board()
            # In both modes, bot should keep playing as normal
        else:
            messagebox.showinfo("Bot", "No possible moves for the bot!")

    def start_bot(self):
        self.bot_running = True
        self.bot_should_stop = False
        self.update_board()
        self.root.after(200, self.bot_auto_play)

    def stop_bot(self):
        self.bot_should_stop = True
        # The bot will stop after the current move

    def bot_auto_play(self):
        if self.bot_should_stop:
            self.bot_running = False
            self.update_board()
            return
        if not has_possible_moves(self.board):
            self.bot_running = False
            self.update_board()
            return
        best_score = -1
        best_move = None
        for y in range(grid_size):
            for x in range(grid_size):
                for dx, dy in [(1,0),(0,1)]:
                    nx, ny = x+dx, y+dy
                    if nx < grid_size and ny < grid_size:
                        score = simulate_move_and_score(self.board, x, y, nx, ny)
                        if score > best_score:
                            best_score = score
                            best_move = (x, y, nx, ny)
        if best_move:
            self.animate_swap(*best_move)
            self.update_board()
            self.root.after(200, self.bot_auto_play)
        else:
            self.bot_running = False
            self.update_board()
            messagebox.showinfo("Bot", "No possible moves for the bot!")

def main():
    root = tk.Tk()
    root.title("Match 3 Game - Modes & Challenges!")
    game = Match3Game(root)
    root.mainloop()

if __name__ == "__main__":
    main() 