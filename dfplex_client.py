#!/usr/bin/env python3
"""
dfplex-term: A terminal client for DFPlex multiplayer Dwarf Fortress.
"""

import sys
import os
import subprocess
import platform

# ---------------------------------------------------------------------------
# Font setup — install a CP437-compatible font if needed
# ---------------------------------------------------------------------------

FONT_NAME = "Terminus"
FONT_URL_LINUX = "https://files.ax86.net/terminus-ttf/files/latest/terminus-ttf.zip"
FONT_URL_MAC   = "https://files.ax86.net/terminus-ttf/files/latest/terminus-ttf.zip"

def _run(cmd, **kwargs):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kwargs)

def check_font_installed():
    """Check if a CP437-capable font is available."""
    system = platform.system()
    if system == "Linux":
        result = _run("fc-list | grep -i terminus")
        return result.returncode == 0 and result.stdout.strip()
    elif system == "Darwin":
        result = _run("fc-list | grep -i terminus")
        return result.returncode == 0 and result.stdout.strip()
    return True  # unknown system, assume ok

def install_font():
    """Try to install Terminus font automatically."""
    system = platform.system()
    installed = False

    if system == "Linux":
        # Try package manager first
        for cmd in [
            "apt-get install -y fonts-terminus 2>/dev/null",
            "pacman -S --noconfirm terminus-font 2>/dev/null",
            "dnf install -y terminus-fonts 2>/dev/null",
        ]:
            if _run(f"sudo {cmd}").returncode == 0:
                installed = True
                break

        if not installed:
            # Manual install to ~/.local/share/fonts
            font_dir = os.path.expanduser("~/.local/share/fonts")
            os.makedirs(font_dir, exist_ok=True)
            tmp = "/tmp/terminus-ttf.zip"
            if _run(f"wget -q '{FONT_URL_LINUX}' -O {tmp}").returncode == 0:
                if _run(f"unzip -o {tmp} '*.ttf' -d {font_dir}").returncode == 0:
                    _run("fc-cache -f")
                    installed = True

    elif system == "Darwin":
        # Try homebrew
        if _run("brew install --cask font-terminus 2>/dev/null").returncode == 0:
            installed = True
        if not installed:
            font_dir = os.path.expanduser("~/Library/Fonts")
            os.makedirs(font_dir, exist_ok=True)
            tmp = "/tmp/terminus-ttf.zip"
            if _run(f"curl -sL '{FONT_URL_MAC}' -o {tmp}").returncode == 0:
                if _run(f"unzip -o {tmp} '*.ttf' -d {font_dir}").returncode == 0:
                    installed = True

    return installed

def setup_font():
    """Check for CP437 font, offer to install if missing."""
    # Skip if user set env var to disable
    if os.environ.get("DFPLEX_NO_FONT_CHECK"):
        return

    # Skip if already marked as done
    marker = os.path.expanduser("~/.dfplex_font_ok")
    if os.path.exists(marker):
        return

    if check_font_installed():
        open(marker, 'w').close()
        return

    print("╔══════════════════════════════════════════════════════╗")
    print("║  dfplex-term: CP437 font not detected                ║")
    print("║                                                      ║")
    print("║  Dwarf Fortress uses special box-drawing characters  ║")
    print("║  that require a compatible font (e.g. Terminus).     ║")
    print("║                                                      ║")
    print("║  Install Terminus font automatically? [Y/n]          ║")
    print("╚══════════════════════════════════════════════════════╝")

    try:
        answer = input("  → ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"

    if answer in ("", "y", "yes"):
        print("Installing Terminus font...")
        if install_font():
            print("✓ Font installed!")
            print("  Please set your terminal font to 'Terminus' or 'xos4 Terminus'")
            print("  at size 16 for best results.")
            open(marker, 'w').close()
        else:
            print("✗ Auto-install failed.")
            print("  Install manually:")
            print("    Linux:  sudo apt-get install fonts-terminus")
            print("    Mac:    brew install --cask font-terminus")
            print("    Or download from: https://files.ax86.net/terminus-ttf/")
    else:
        print("Skipping. Set DFPLEX_NO_FONT_CHECK=1 to suppress this message.")
        open(marker, 'w').close()

    print()

setup_font()

"""
dfplex-term: A terminal client for DFPlex multiplayer Dwarf Fortress.

Connects to DFPlex's WebSocket (port 1234 by default), renders the
curses screen buffer as ANSI colour in your terminal, and sends
keystrokes back.  Each SSH user gets their own independent view and
cursor – exactly as DFPlex intended.

Usage:
    python3 dfplex_client.py [host] [port] [nick]
    python3 dfplex_client.py 192.168.1.10 1234 Urist
"""

import sys
import os
import struct
import threading
import time
import signal
import argparse
import urllib.parse
import curses

try:
    import websocket  # websocket-client library
except ImportError:
    print("Missing dependency: pip install websocket-client")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Protocol constants (from dfplex server.cpp / dfplex.js)
# ---------------------------------------------------------------------------
CMD_UPDATE       = 110   # client → server: request frame; server → client: frame data
CMD_SENDKEY      = 111   # client → server: keypress  [111, jsKeyCode, charCode, mod]
CMD_CONNECT      = 115   # client → server: init (triggers full screen reset on server)
CMD_REQUEST_TURN = 116   # client → server: request active turn
CMD_RESIZE       = 117   # client → server: tell server our terminal dimensions

# Modifier bits (same as JS: shift|ctrl<<1|alt<<2)
MOD_SHIFT = 1
MOD_CTRL  = 2
MOD_ALT   = 4

# ---------------------------------------------------------------------------
# JS keyCode → DFPlex wire byte  (mirrors input.cpp + keycode.js)
# For terminal keys we send keyCode=0, charCode=ascii, mod=0 (unicode path)
# For special keys we send keyCode=<js code>, charCode=0, mod=<mods>
# ---------------------------------------------------------------------------
# Map: curses key constant → (jsKeyCode, mod)
CURSES_SPECIAL = {
    curses.KEY_UP:       (38, 0),
    curses.KEY_DOWN:     (40, 0),
    curses.KEY_LEFT:     (37, 0),
    curses.KEY_RIGHT:    (39, 0),
    curses.KEY_PPAGE:    (33, 0),   # page up
    curses.KEY_NPAGE:    (34, 0),   # page down
    curses.KEY_HOME:     (36, 0),
    curses.KEY_END:      (35, 0),
    curses.KEY_DC:       (46, 0),   # delete
    curses.KEY_BACKSPACE:(8,  0),
    curses.KEY_ENTER:    (13, 0),
    curses.KEY_F1:       (112, 0),
    curses.KEY_F2:       (113, 0),
    curses.KEY_F3:       (114, 0),
    curses.KEY_F4:       (115, 0),
    curses.KEY_F5:       (116, 0),
    curses.KEY_F6:       (117, 0),
    curses.KEY_F7:       (118, 0),
    curses.KEY_F8:       (119, 0),
    curses.KEY_F9:       (120, 0),
    curses.KEY_F10:      (121, 0),
    curses.KEY_F11:      (122, 0),
    curses.KEY_F12:      (123, 0),
    # numpad (curses sends these as KEY_B2 etc – map best effort)
    curses.KEY_B2:       (101, 0),  # KP5
}

# ---------------------------------------------------------------------------
# DFPlex 16-colour palette (from dfplex.js `colors` array)
# Each entry is (R, G, B) for colours 0..15
# ---------------------------------------------------------------------------
DF_PALETTE_RGB = [
    ( 32,  39,  49),   # 0  black
    (  0, 106, 255),   # 1  blue
    ( 68, 184,  57),   # 2  green
    (114, 156, 251),   # 3  cyan
    (212,  54,  85),   # 4  red
    (176,  50, 255),   # 5  magenta
    (217, 118,  65),   # 6  brown/dark-yellow
    (170, 196, 178),   # 7  light-grey
    (128, 151, 156),   # 8  dark-grey
    ( 48, 165, 255),   # 9  bright-blue
    (144, 255,  79),   # 10 bright-green
    (168, 212, 255),   # 11 bright-cyan
    (255,  82,  82),   # 12 bright-red
    (255, 107, 255),   # 13 bright-magenta
    (255, 232, 102),   # 14 yellow
    (255, 250, 232),   # 15 white
]

# Map DF colour index → closest curses colour pair index.
# We initialise up to 16×16 = 256 colour pairs in setup_colors().
# pair index = fg*16 + bg  (1-based because pair 0 is reserved)
def pair_index(fg, bg):
    """Return the curses colour pair number for (fg, bg) in DF palette."""
    return fg * 16 + bg + 1   # +1: pair 0 reserved


def setup_colors(stdscr):
    """
    Initialise all 256 DF colour combinations as curses colour pairs.
    Returns True if 256-colour / true-colour terminal available,
    False if we fall back to the basic 8 ANSI colours.
    """
    curses.start_color()
    curses.use_default_colors()

    has_256 = curses.COLORS >= 256

    if has_256 and curses.can_change_color():
        # Program the first 16 colour slots with DF's exact palette.
        for i, (r, g, b) in enumerate(DF_PALETTE_RGB):
            # curses uses 0-1000 scale
            curses.init_color(i, r * 1000 // 255, g * 1000 // 255, b * 1000 // 255)

    # Initialise all fg×bg pairs
    for fg in range(16):
        for bg in range(16):
            cf = fg if has_256 else _approx_ansi(fg)
            cb = bg if has_256 else _approx_ansi(bg)
            curses.init_pair(pair_index(fg, bg), cf, cb)

    return has_256


# Closest ANSI-8 fallback mapping for DF colour index
_ANSI_MAP = [0, 4, 2, 6, 1, 5, 3, 7, 8, 12, 10, 14, 9, 13, 11, 15]
def _approx_ansi(df_idx):
    return _ANSI_MAP[df_idx % 16] % 8  # clamp to 8


# ---------------------------------------------------------------------------
# Tile / screen state
# ---------------------------------------------------------------------------
class Tile:
    __slots__ = ('ch', 'fg', 'bg')
    def __init__(self):
        self.ch = ord(' ')
        self.fg = 7
        self.bg = 0


class ScreenState:
    def __init__(self, w=80, h=25):
        self.w = w
        self.h = h
        self.tiles = [[Tile() for _ in range(h)] for _ in range(w)]
        self.lock  = threading.Lock()
        self.dirty = True
        self.status = "Connecting…"
        self.player_count = 0

    def resize(self, w, h):
        if w == self.w and h == self.h:
            return
        self.w = w
        self.h = h
        self.tiles = [[Tile() for _ in range(h)] for _ in range(w)]
        self.dirty = True

    def apply_delta(self, data, offset):
        """Apply the 5-bytes-per-changed-tile delta from a frame packet."""
        i = offset
        while i + 4 < len(data):
            x   = data[i]
            y   = data[i+1]
            ch  = data[i+2]
            raw_bg = data[i+3]
            raw_fg = data[i+4]
            i  += 5

            bg = raw_bg & 0x0f
            # bit 6 = is_text, bit 7 = is_overworld — we ignore tile-set
            # differences and treat both as plain text for terminal.
            fg = raw_fg & 0x0f

            if 0 <= x < self.w and 0 <= y < self.h:
                t = self.tiles[x][y]
                t.ch = ch
                t.fg = fg
                t.bg = bg
        self.dirty = True


# ---------------------------------------------------------------------------
# Parse a server frame
# ---------------------------------------------------------------------------
def parse_frame(data, screen):
    """
    Parse a CMD_UPDATE (110) binary frame from the server.
    Returns the status dict.
    """
    # [0]    msgtype (110)
    # [1]    player_count (lower 7 bits)
    # [2]    is_active flag
    # [3-6]  load (int32, ignored)
    # [7]    grid width
    # [8]    grid height
    # [9]    info_message length
    # [10..M] info_message bytes
    # [M]    debug_info_len_lo
    # [M+1]  debug_info_len_hi
    # [M+2..N] debug_info bytes
    # [N..]  tile deltas (5 bytes each)

    if len(data) < 9:
        return

    player_count = data[1] & 0x7f
    gw = data[7]
    gh = data[8]

    with screen.lock:
        screen.resize(gw, gh)

    offset = 9
    info_len = data[offset]
    offset += 1
    info_msg = ""
    if info_len > 0 and offset + info_len <= len(data):
        raw = data[offset:offset + info_len]
        info_msg = raw.rstrip(b'\x00').decode('utf-8', errors='replace')
    offset += info_len

    # debug info (2-byte length)
    if offset + 2 <= len(data):
        debug_len = data[offset] | (data[offset+1] << 8)
        offset += 2
        offset += debug_len

    with screen.lock:
        screen.player_count = player_count
        screen.status = info_msg or f"{player_count} player(s) connected"
        screen.apply_delta(data, offset)


# ---------------------------------------------------------------------------
# WebSocket connection
# ---------------------------------------------------------------------------
class DFPlexConnection:
    def __init__(self, host, port, nick, screen):
        self.uri    = f"ws://{host}:{port}/{urllib.parse.quote(nick)}/secret"
        self.screen = screen
        self.ws     = None
        self.connected = False
        self._pending_frame = threading.Event()

    def connect(self):
        # Send the subprotocol header so the server accepts us,
        # but skip client-side subprotocol validation since ixwebsocket
        # doesn't echo it back in the response header.
        self.ws = websocket.WebSocketApp(
            self.uri,
            on_open      = self._on_open,
            on_message   = self._on_message,
            on_error     = self._on_error,
            on_close     = self._on_close,
            header       = ["Sec-WebSocket-Protocol: DFPlex-v0.2"],
        )
        t = threading.Thread(target=self.ws.run_forever, daemon=True)
        t.start()

    def _on_open(self, ws):
        self.connected = True
        # Send CMD_CONNECT to reset screen on server side
        ws.send(bytes([CMD_CONNECT]), opcode=websocket.ABNF.OPCODE_BINARY)
        # Request first frame
        ws.send(bytes([CMD_UPDATE]), opcode=websocket.ABNF.OPCODE_BINARY)

    def _on_message(self, ws, raw):
        if isinstance(raw, str):
            raw = raw.encode('latin-1')
        data = bytes(raw) if not isinstance(raw, (bytes, bytearray)) else raw
        if len(data) > 0 and data[0] == CMD_UPDATE:
            parse_frame(data, self.screen)
            self._pending_frame.set()

    def _on_error(self, ws, err):
        with self.screen.lock:
            self.screen.status = f"Connection error: {err}"
            self.screen.dirty  = True

    def _on_close(self, ws, code, reason):
        self.connected = False
        with self.screen.lock:
            self.screen.status = f"Disconnected (code={code} reason={reason})"
            self.screen.dirty  = True

    def request_frame(self):
        if self.ws and self.connected:
            try:
                self.ws.send(bytes([CMD_UPDATE]),
                             opcode=websocket.ABNF.OPCODE_BINARY)
            except Exception:
                pass

    def send_resize(self, w, h):
        if self.ws and self.connected:
            try:
                self.ws.send(bytes([CMD_RESIZE, min(w, 255), min(h, 255)]),
                             opcode=websocket.ABNF.OPCODE_BINARY)
            except Exception:
                pass

    def send_key(self, js_keycode, char_code, mod):
        if self.ws and self.connected:
            try:
                self.ws.send(bytes([CMD_SENDKEY, js_keycode & 0xff,
                                    char_code & 0xff, mod & 0xff]),
                             opcode=websocket.ABNF.OPCODE_BINARY)
            except Exception:
                pass

    def request_turn(self):
        if self.ws and self.connected:
            try:
                self.ws.send(bytes([CMD_REQUEST_TURN]),
                             opcode=websocket.ABNF.OPCODE_BINARY)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Terminal rendering
# ---------------------------------------------------------------------------
CP437_TO_UNICODE = {
    # Control-range glyphs that DF uses as box-drawing / special chars
    0x01: '☺', 0x02: '☻', 0x03: '♥', 0x04: '♦', 0x05: '♣', 0x06: '♠',
    0x07: '•', 0x08: '◘', 0x09: '○', 0x0A: '◙', 0x0B: '♂', 0x0C: '♀',
    0x0D: '♪', 0x0E: '♫', 0x0F: '☼', 0x10: '►', 0x11: '◄', 0x12: '↕',
    0x13: '‼', 0x14: '¶', 0x15: '§', 0x16: '▬', 0x17: '↨', 0x18: '↑',
    0x19: '↓', 0x1A: '→', 0x1B: '←', 0x1C: '∟', 0x1D: '↔', 0x1E: '▲',
    0x1F: '▼',
    0x7F: '⌂',
    # Box drawing / block elements in high range
    0x80: 'Ç', 0x81: 'ü', 0x82: 'é', 0x83: 'â', 0x84: 'ä', 0x85: 'à',
    0x86: 'å', 0x87: 'ç', 0x88: 'ê', 0x89: 'ë', 0x8A: 'è', 0x8B: 'ï',
    0x8C: 'î', 0x8D: 'ì', 0x8E: 'Ä', 0x8F: 'Å', 0x90: 'É', 0x91: 'æ',
    0x92: 'Æ', 0x93: 'ô', 0x94: 'ö', 0x95: 'ò', 0x96: 'û', 0x97: 'ù',
    0x98: 'ÿ', 0x99: 'Ö', 0x9A: 'Ü', 0x9B: '¢', 0x9C: '£', 0x9D: '¥',
    0x9E: '₧', 0x9F: 'ƒ', 0xA0: 'á', 0xA1: 'í', 0xA2: 'ó', 0xA3: 'ú',
    0xA4: 'ñ', 0xA5: 'Ñ', 0xA6: 'ª', 0xA7: 'º', 0xA8: '¿', 0xA9: '⌐',
    0xAA: '¬', 0xAB: '½', 0xAC: '¼', 0xAD: '¡', 0xAE: '«', 0xAF: '»',
    0xB0: '░', 0xB1: '▒', 0xB2: '▓', 0xB3: '│', 0xB4: '┤', 0xB5: '╡',
    0xB6: '╢', 0xB7: '╖', 0xB8: '╕', 0xB9: '╣', 0xBA: '║', 0xBB: '╗',
    0xBC: '╝', 0xBD: '╜', 0xBE: '╛', 0xBF: '┐', 0xC0: '└', 0xC1: '┴',
    0xC2: '┬', 0xC3: '├', 0xC4: '─', 0xC5: '┼', 0xC6: '╞', 0xC7: '╟',
    0xC8: '╚', 0xC9: '╔', 0xCA: '╩', 0xCB: '╦', 0xCC: '╠', 0xCD: '═',
    0xCE: '╬', 0xCF: '╧', 0xD0: '╨', 0xD1: '╤', 0xD2: '╥', 0xD3: '╙',
    0xD4: '╘', 0xD5: '╒', 0xD6: '╓', 0xD7: '╫', 0xD8: '╪', 0xD9: '┘',
    0xDA: '┌', 0xDB: '█', 0xDC: '▄', 0xDD: '▌', 0xDE: '▐', 0xDF: '▀',
    0xE0: 'α', 0xE1: 'ß', 0xE2: 'Γ', 0xE3: 'π', 0xE4: 'Σ', 0xE5: 'σ',
    0xE6: 'µ', 0xE7: 'τ', 0xE8: 'Φ', 0xE9: 'Θ', 0xEA: 'Ω', 0xEB: 'δ',
    0xEC: '∞', 0xED: 'φ', 0xEE: 'ε', 0xEF: '∩', 0xF0: '≡', 0xF1: '±',
    0xF2: '≥', 0xF3: '≤', 0xF4: '⌠', 0xF5: '⌡', 0xF6: '÷', 0xF7: '≈',
    0xF8: '°', 0xF9: '∙', 0xFA: '·', 0xFB: '√', 0xFC: 'ⁿ', 0xFD: '²',
    0xFE: '■', 0xFF: '\xa0',
}

def cp437_char(code):
    """Convert CP437 byte to a unicode character for terminal display."""
    if code == 0 or code == 32:
        return ' '
    if 0x20 <= code <= 0x7E:
        return chr(code)
    return CP437_TO_UNICODE.get(code, '?')


def render(stdscr, screen, has_256):
    """Paint the entire screen buffer to the curses window."""
    max_y, max_x = stdscr.getmaxyx()

    with screen.lock:
        if not screen.dirty:
            return
        screen.dirty = False
        w = screen.w
        h = screen.h
        tiles = screen.tiles
        status = screen.status
        pcount = screen.player_count

    # Use curses' internal double-buffering: addstr without erase first,
    # then noutrefresh + doupdate to avoid flicker.
    for x in range(min(w, max_x)):
        for y in range(min(h, max_y - 1)):   # leave bottom row for status
            t = tiles[x][y]
            ch = cp437_char(t.ch)
            attr = curses.color_pair(pair_index(t.fg, t.bg))
            try:
                stdscr.addstr(y, x, ch, attr)
            except curses.error:
                pass  # bottom-right corner write is harmless error

    # Status bar at bottom
    status_line = f" [{pcount} player(s)]  {status}  "
    status_line = status_line[:max_x - 1].ljust(max_x - 1)
    try:
        stdscr.addstr(max_y - 1, 0, status_line,
                      curses.color_pair(pair_index(0, 7)) | curses.A_BOLD)
    except curses.error:
        pass

    stdscr.noutrefresh()
    curses.doupdate()


# ---------------------------------------------------------------------------
# Key input → DFPlex wire bytes
# ---------------------------------------------------------------------------
def handle_key(key, conn):
    """
    Translate a curses key event into a DFPlex sendKey message and send it.
    Returns True if handled, False if it's the quit key (Ctrl-Q).
    """
    # Ctrl-Q → quit
    if key == 17:  # ord('\x11')
        return False

    # Ctrl-T → request turn
    if key == 20:  # ord('\x14')
        conn.request_turn()
        return True

    # Special curses keys (arrows, F-keys, etc.)
    if key in CURSES_SPECIAL:
        js_code, mod = CURSES_SPECIAL[key]
        conn.send_key(js_code, 0, mod)
        return True

    # ESC
    if key == 27:
        conn.send_key(27, 0, 0)
        return True

    # Enter / Return
    if key in (10, 13, curses.KEY_ENTER):
        conn.send_key(13, 0, 0)
        return True

    # Backspace
    if key in (127, 8, curses.KEY_BACKSPACE):
        conn.send_key(8, 0, 0)
        return True

    # Tab
    if key == 9:
        conn.send_key(9, 0, 0)
        return True

    # Printable ASCII / unicode
    if 32 <= key <= 126:
        if key == 32:
            # Space: send via both paths so it works in menus AND text input
            conn.send_key(32, 32, 0)
        else:
            conn.send_key(0, key, 0)
        return True

    # Ctrl-letter (curses gives 1-26 for ctrl-a through ctrl-z)
    if 1 <= key <= 26:
        # Send as keyCode = uppercase letter, mod = CTRL
        js_code = key + 64  # ctrl-a=1 → keyCode 65 ('A')
        conn.send_key(js_code, 0, MOD_CTRL)
        return True

    return True  # ignore unknowns but don't quit


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main(stdscr, args):
    # Terminal setup
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)
    has_256 = setup_colors(stdscr)

    screen = ScreenState()
    conn   = DFPlexConnection(args.host, args.port, args.nick, screen)

    # Send resize several times after connect — DF needs a moment to apply it
    def on_connected():
        for delay in [0.5, 1.0, 2.0, 4.0]:
            time.sleep(delay)
            if conn.connected:
                h, w = stdscr.getmaxyx()
                conn.send_resize(w, h - 1)
                with screen.lock:
                    screen.dirty = True

    with screen.lock:
        screen.status = f"Connecting to {args.host}:{args.port} as '{args.nick}'…"

    conn.connect()
    threading.Thread(target=on_connected, daemon=True).start()

    last_resize_check = time.time()
    last_size = stdscr.getmaxyx()

    FPS = 10
    frame_interval = 1.0 / FPS

    # Frame request loop: poll server at ~20 fps
    def frame_pump():
        while True:
            time.sleep(frame_interval)
            conn.request_frame()

    threading.Thread(target=frame_pump, daemon=True).start()

    # Main event loop
    while True:
        # --- Render ---
        render(stdscr, screen, has_256)

        # --- Resize check ---
        now = time.time()
        if now - last_resize_check > 0.5:
            new_size = stdscr.getmaxyx()
            if new_size != last_size:
                last_size = new_size
                h, w = new_size
                conn.send_resize(w, h - 1)
                curses.resizeterm(h, w)
                stdscr.clear()
            last_resize_check = now

        # --- Input ---
        try:
            key = stdscr.getch()
        except curses.error:
            key = -1

        if key != -1:
            if not handle_key(key, conn):
                break  # quit

        time.sleep(0.01)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="dfplex-term: terminal client for DFPlex multiplayer DF")
    parser.add_argument("host", nargs="?", default="localhost",
                        help="DFPlex server host (default: localhost)")
    parser.add_argument("port", nargs="?", type=int, default=1234,
                        help="DFPlex WebSocket port (default: 1234)")
    parser.add_argument("nick", nargs="?", default="Urist",
                        help="Your player nickname (default: Urist)")
    args = parser.parse_args()

    print(f"dfplex-term connecting to ws://{args.host}:{args.port} as '{args.nick}'")
    print("Controls:  Ctrl-Q = quit   Ctrl-T = request turn")
    print("Starting in 1 second…")
    time.sleep(1)

    try:
        curses.wrapper(main, args)
    except KeyboardInterrupt:
        pass
    print("Disconnected. May your fortress stand eternal.")
