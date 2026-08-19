import os
import random
import streamlit as st
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

# Robust pypdf import handling
try:
    from pypdf import PdfReader, PdfWriter, PageObject, Transformation
except ImportError:
    try:
        from pypdf import PdfReader, PdfWriter, PageObject
        from pypdf.transformation import Transformation
    except ImportError:
        from PyPDF2 import PdfReader, PdfWriter, PageObject
        from PyPDF2.transformation import Transformation

# Page Dimensions (Field Notes: 3.5 x 5.5 inches)
PAGE_WIDTH, PAGE_HEIGHT = 3.5 * inch, 5.5 * inch

# =============================================================================
# 1. SUDOKU GENERATION ENGINE (Backtracking + Clue Stripping)
# =============================================================================
def is_valid(board, row, col, num):
    for i in range(9):
        if board[row][i] == num or board[i][col] == num:
            return False
    start_r, start_c = 3 * (row // 3), 3 * (col // 3)
    for i in range(3):
        for j in range(3):
            if board[start_r + i][start_c + j] == num:
                return False
    return True

def solve_sudoku(board):
    for r in range(9):
        for c in range(9):
            if board[r][c] == 0:
                nums = list(range(1, 10))
                random.shuffle(nums)
                for num in nums:
                    if is_valid(board, r, c, num):
                        board[r][c] = num
                        if solve_sudoku(board):
                            return True
                        board[r][c] = 0
                return False
    return True

def generate_solved_board():
    board = [[0]*9 for _ in range(9)]
    solve_sudoku(board)
    return board

def count_solutions(board):
    """Checks for solution uniqueness."""
    count = 0
    def solve(b):
        nonlocal count
        for r in range(9):
            for c in range(9):
                if b[r][c] == 0:
                    for num in range(1, 10):
                        if is_valid(b, r, c, num):
                            b[r][c] = num
                            solve(b)
                            b[r][c] = 0
                            if count >= 2:
                                return
                    return
        count += 1

    solve([row[:] for row in board])
    return count

def generate_puzzle(difficulty="Medium"):
    solution = generate_solved_board()
    puzzle = [row[:] for row in solution]
    
    # Target clues based on difficulty
    target_clues = {"Easy": 40, "Medium": 32, "Hard": 26}.get(difficulty, 32)
    
    cells = [(r, c) for r in range(9) for c in range(9)]
    random.shuffle(cells)
    
    removed = 0
    max_to_remove = 81 - target_clues
    
    for r, c in cells:
        if removed >= max_to_remove:
            break
        temp = puzzle[r][c]
        puzzle[r][c] = 0
        
        # Verify unique solution
        if count_solutions(puzzle) != 1:
            puzzle[r][c] = temp
        else:
            removed += 1
            
    return puzzle, solution

# Page Dimensions: 3.0 in x 4.25 in
PAGE_WIDTH, PAGE_HEIGHT = 3.0 * inch, 4.25 * inch

# =============================================================================
# 2. PDF RENDERING & EXACT 3" MARGIN IMPOSITION ENGINE
# =============================================================================
def draw_sudoku_grid(c, x_offset, y_offset, size, board, is_mini=False):
    cell_size = size / 9.0
    c.setLineWidth(1.0 if is_mini else 1.5)
    c.rect(x_offset, y_offset, size, size)
    
    # Grid Lines
    for i in range(1, 9):
        c.setLineWidth((0.8 if is_mini else 1.5) if i % 3 == 0 else (0.25 if is_mini else 0.5))
        c.line(x_offset + i * cell_size, y_offset, x_offset + i * cell_size, y_offset + size)
        c.line(x_offset, y_offset + i * cell_size, x_offset + size, y_offset + i * cell_size)
        
    # Numbers
    c.setFont("Helvetica", 4.5 if is_mini else 11)
    x_off = 1.8 if is_mini else 3.5
    y_off = 1.5 if is_mini else 3.8

    for r in range(9):
        for col in range(9):
            val = board[r][col]
            if val != 0:
                x = x_offset + col * cell_size + (cell_size / 2.0) - x_off
                y = y_offset + (8 - r) * cell_size + (cell_size / 2.0) - y_off
                c.drawString(x, y, str(val))

def draw_single_page_content(c, x_origin, y_origin, page_num, total_puzzles, puzzles, solutions, difficulty_label):
    """Draws content of a 3.0" x 4.25" page anchored at x_origin."""
    
    # 1. Cover Page
    if page_num == 1:
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(x_origin + PAGE_WIDTH / 2, y_origin + 2.5 * inch, "MINI SUDOKU")
        c.setFont("Helvetica", 8)
        c.drawCentredString(x_origin + PAGE_WIDTH / 2, y_origin + 2.1 * inch, f"Edition: {difficulty_label}")
        return

    # 2. Main Puzzles (2.5" Grid centered with 0.25" side margins)
    puzzle_idx = page_num - 1
    if puzzle_idx <= total_puzzles:
        board = puzzles[puzzle_idx - 1]
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x_origin + 0.25 * inch, y_origin + 3.65 * inch, f"PUZZLE #{puzzle_idx}  [{difficulty_label.upper()}]")
        
        grid_size = 2.5 * inch
        grid_x = x_origin + 0.25 * inch  # Exactly 0.25" from left cut/fold
        grid_y = y_origin + 0.85 * inch  # Vertically centered
        draw_sudoku_grid(c, grid_x, grid_y, grid_size, board)
        return

    # 3. Mini Solutions Pages
    sol_page_idx = page_num - 1 - total_puzzles
    start_num = (sol_page_idx - 1) * 4 + 1
    end_num = min(start_num + 3, total_puzzles)
    
    if start_num <= total_puzzles:
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x_origin + 0.25 * inch, y_origin + 3.65 * inch, f"SOLUTIONS (#{start_num}–#{end_num})")
        c.setLineWidth(0.5)
        c.line(x_origin + 0.25 * inch, y_origin + 3.55 * inch, x_origin + 2.75 * inch, y_origin + 3.55 * inch)
        
        mini_size = 1.0 * inch
        positions = [
            (x_origin + 0.35 * inch, y_origin + 2.10 * inch),
            (x_origin + 1.65 * inch, y_origin + 2.10 * inch),
            (x_origin + 0.35 * inch, y_origin + 0.75 * inch),
            (x_origin + 1.65 * inch, y_origin + 0.75 * inch)
        ]
        
        for idx in range(end_num - start_num + 1):
            p_num = start_num + idx
            gx, gy = positions[idx]
            sol_board = solutions[p_num - 1]
            c.setFont("Helvetica-Bold", 6)
            c.drawString(gx, gy + mini_size + 0.04 * inch, f"#{p_num}")
            draw_sudoku_grid(c, gx, gy, mini_size, sol_board, is_mini=True)

def generate_booklet_pdf(output_pdf, puzzles, solutions, difficulty_label):
    sheet_w, sheet_h = 11 * inch, 8.5 * inch  # Landscape Letter
    c = canvas.Canvas(output_pdf, pagesize=(sheet_w, sheet_h))
    
    total_puzzles = len(puzzles)
    solution_pages = (total_puzzles + 3) // 4
    total_booklet_pages = 1 + total_puzzles + solution_pages
    
    padded_pages = ((total_booklet_pages + 7) // 8) * 8
    
    # Page Boundaries on 11.0" Sheet
    left_x = 2.5 * inch   # Left Page: 2.5" to 5.5" (3.0" Wide)
    right_x = 5.5 * inch  # Right Page: 5.5" to 8.5" (3.0" Wide)
    
    top_y = 4.25 * inch   # Top Strip Y Position
    bot_y = 0.0 * inch    # Bottom Strip Y Position
    
    total_sheets = padded_pages // 4
    
    for s in range(total_sheets):
        top_left_p = padded_pages - (2 * s)
        top_right_p = (2 * s) + 1
        
        bot_left_p = padded_pages - (2 * s) - 1
        bot_right_p = (2 * s) + 2
        
        # Reverse sides for back of duplex sheet
        if s % 2 != 0:
            top_left_p, top_right_p = top_right_p, top_left_p
            bot_left_p, bot_right_p = bot_right_p, bot_left_p

        # --- DRAW PAGES ---
        if top_left_p <= total_booklet_pages:
            draw_single_page_content(c, left_x, top_y, top_left_p, total_puzzles, puzzles, solutions, difficulty_label)
        if top_right_p <= total_booklet_pages:
            draw_single_page_content(c, right_x, top_y, top_right_p, total_puzzles, puzzles, solutions, difficulty_label)
            
        if bot_left_p <= total_booklet_pages:
            draw_single_page_content(c, left_x, bot_y, bot_left_p, total_puzzles, puzzles, solutions, difficulty_label)
        if bot_right_p <= total_booklet_pages:
            draw_single_page_content(c, right_x, bot_y, bot_right_p, total_puzzles, puzzles, solutions, difficulty_label)

        # --- DRAW CUT & FOLD GUIDES ---
        c.setLineWidth(0.4)
        c.setDash(3, 3)
        
        # 1. Horizontal Middle Cut Line (y = 4.25")
        c.line(0.25 * inch, 4.25 * inch, 10.75 * inch, 4.25 * inch)
        
        # 2. Vertical Outer Edge Cut Lines (x = 2.5" and x = 8.5")
        c.line(2.5 * inch, 0.25 * inch, 2.5 * inch, 8.25 * inch)
        c.line(8.5 * inch, 0.25 * inch, 8.5 * inch, 8.25 * inch)
        
        # 3. Center Spine Fold Lines (x = 5.5")
        c.line(5.5 * inch, 0.25 * inch, 5.5 * inch, 4.0 * inch)
        c.line(5.5 * inch, 4.5 * inch, 5.5 * inch, 8.25 * inch)
        
        c.setDash()  # Reset line style
        c.showPage()
        
    c.save()

# =============================================================================
# 3. STREAMLIT APP USER INTERFACE
# =============================================================================
st.set_page_config(page_title="Sudoku Booklet Builder", page_icon="📖", layout="centered")

st.title("📖 Pocket Sudoku Booklet Generator")
st.write("Generate custom 3.5\" x 5.5\" Field Notes style printable Sudoku books.")

difficulty = st.selectbox("Select Difficulty", ["Easy", "Medium", "Hard"], index=1)
num_puzzles = st.slider("Number of Puzzles", min_value=4, max_value=32, value=16, step=4)

if st.button("🚀 Generate Booklet PDF", type="primary"):
    puzzles = []
    solutions = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i in range(num_puzzles):
        status_text.text(f"Generating puzzle {i+1} of {num_puzzles} ({difficulty})...")
        p, s = generate_puzzle(difficulty)
        puzzles.append(p)
        solutions.append(s)
        progress_bar.progress((i + 1) / num_puzzles)
        
    status_text.text("Rendering print-ready booklet...")
    output_pdf = "field_sudoku_booklet.pdf"
    
    generate_booklet_pdf(output_pdf, puzzles, solutions, difficulty)
    
    status_text.text("Done!")
    st.success("Booklet generated successfully!")
    
    with open(output_pdf, "rb") as f:
        st.download_button(
            label="⬇️ Download Print-Ready PDF",
            data=f,
            file_name=f"Sudoku_Booklet_{difficulty}_{num_puzzles}Puzzles.pdf",
            mime="application/pdf"
        )