"""Dark colour scheme and a few sizing constants shared by every screen."""

from kivy.metrics import dp, sp


def _rgba(hex_str, alpha=1.0):
    hex_str = hex_str.lstrip("#")
    r, g, b = (int(hex_str[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return (r, g, b, alpha)


# --- palette -------------------------------------------------------------
BG = _rgba("#101014")           # window background
SURFACE = _rgba("#17171C")      # bars, sheets
SURFACE_HI = _rgba("#1F1F26")   # cards, tiles, inputs
SURFACE_PRESS = _rgba("#2A2A33")
OUTLINE = _rgba("#2E2E38")

TEXT = _rgba("#ECECF1")
TEXT_DIM = _rgba("#9A9AA8")
TEXT_FAINT = _rgba("#63636F")

ACCENT = _rgba("#4F9CF9")
ACCENT_DIM = _rgba("#4F9CF9", 0.18)
DANGER = _rgba("#F2555A")
SCRIM = _rgba("#000000", 0.55)

# --- metrics -------------------------------------------------------------
GRID_COLUMNS = 3                # photo mode is a fixed 3-per-row grid
GUTTER = dp(8)
PAGE_PAD = dp(10)
TILE_RADIUS = dp(16)
PHOTO_RADIUS = dp(10)
BAR_HEIGHT = dp(56)
ROW_HEIGHT = dp(64)
FONT_XS = sp(11)
FONT_SM = sp(12)
FONT_MD = sp(14)
FONT_LG = sp(17)
FONT_XL = sp(22)
