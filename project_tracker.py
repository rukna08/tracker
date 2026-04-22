import tkinter as tk
import json, os, time, math, subprocess, webbrowser
from collections import defaultdict
from datetime import datetime, timedelta

# ── Safe Windows API imports ──────────────────────────────────────────────────
try:
    import ctypes, ctypes.wintypes
    _WIN = True
except Exception:
    _WIN = False

DATA_FILE     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "projects.json")
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

ONE_WEEK  = 7  * 24 * 3600
TWO_WEEKS = 14 * 24 * 3600


# ── DWM (all calls wrapped in try/except, never crash) ───────────────────────

def _get_hwnd(widget):
    if not _WIN: return None
    try:
        hwnd = ctypes.windll.user32.GetParent(widget.winfo_id())
        return hwnd if hwnd else widget.winfo_id()
    except Exception:
        return None

def _dwm_set(hwnd, attr, value):
    if not _WIN or not hwnd: return
    try:
        v = ctypes.c_int(value)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))
    except Exception:
        pass

def style_titlebar(hwnd, theme_key):
    if not hwnd: return
    _dwm_set(hwnd, 20, 1)  # dark mode
    _dwm_set(hwnd, 19, 1)  # older Win10
    if theme_key == "y2k":
        _dwm_set(hwnd, 35, 0x28160a)   # caption colour deep blue (COLORREF BGR)
        _dwm_set(hwnd, 36, 0xffcce8)   # text colour
    else:
        _dwm_set(hwnd, 35, 0x1a1a1a)
        _dwm_set(hwnd, 36, 0xe0e0e0)

def apply_blur(hwnd, level, theme_key):
    if not _WIN or not hwnd: return
    try:
        class _AP(ctypes.Structure):
            _fields_ = [("AccentState",ctypes.c_int),("AccentFlags",ctypes.c_int),
                        ("GradientColor",ctypes.c_int),("AnimationId",ctypes.c_int)]
        class _WD(ctypes.Structure):
            _fields_ = [("Attribute",ctypes.c_int),("pData",ctypes.c_void_p),
                        ("cbData",ctypes.c_size_t)]
        a = _AP()
        if theme_key != "y2k" or level == 0:
            a.AccentState = 0
        else:
            alpha = {1: 0xCC, 2: 0x88, 3: 0x33}.get(level, 0x88)
            a.AccentState   = 4
            a.AccentFlags   = 0x20 | 0x40 | 0x80 | 0x100
            a.GradientColor = (alpha << 24) | (0x3a << 16) | (0x1a << 8) | 0x0d
        d = _WD()
        d.Attribute = 19
        d.pData     = ctypes.cast(ctypes.byref(a), ctypes.c_void_p)
        d.cbData    = ctypes.sizeof(a)
        ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(d))
    except Exception:
        pass


# ── Themes ────────────────────────────────────────────────────────────────────

THEMES = {
    "default": {
        "name":        "Default",
        "C_ROOT":      "#1a1a1a",
        "C_BG":        "#232323",
        "C_ROW_ALT":   "#272727",
        "C_ROW_HOVER": "#2e2e2e",
        "C_ROW_ACT":   "#1a2a1a",
        "C_ROW_ACT_H": "#1f301f",
        "C_EXP_BG":    "#1c1c1c",
        "C_HEADER":    "#2d2d2d",
        "C_BORDER":    "#3a3a3a",
        "C_BORDER_LT": "#555555",
        "C_ACCENT":    "#e8a000",
        "C_ACCENT_DK": "#b07800",
        "C_ACCENT_LT": "#ffb830",
        "C_BTN":       "#383838",
        "C_BTN_H":     "#484848",
        "C_BTN_P":     "#2a2a2a",
        "C_RED":       "#c03020",
        "C_RED_H":     "#e04030",
        "C_RED_P":     "#902010",
        "C_GREEN":     "#4caf50",
        "C_YELLOW":    "#c8a000",
        "C_RED_LED":   "#c03020",
        "C_TEXT":      "#d0d0d0",
        "C_TEXT_DIM":  "#686868",
        "C_TEXT_HEAD": "#e8e8e8",
        "C_SCR_BG":    "#2a2a2a",
        "C_SCR_TH":    "#484848",
        "C_ADD_BTN":   "#383838",
        "C_ADD_FG":    "#d0d0d0",
        "transparent": False,
        "FN": ("Segoe UI", 10, "bold"),
        "FS": ("Segoe UI", 9),
        "FT": ("Segoe UI", 8),
        "FB": ("Segoe UI", 9, "bold"),
        "FC": ("Segoe UI", 8),
    },
    "y2k": {
        "name":        "2007 Aesthetic",
        "C_ROOT":      "#0d1a3a",
        "C_BG":        "#0d1a3a",
        "C_ROW_ALT":   "#0a1630",
        "C_ROW_HOVER": "#1a3060",
        "C_ROW_ACT":   "#082810",
        "C_ROW_ACT_H": "#0a3214",
        "C_EXP_BG":    "#08122a",
        "C_HEADER":    "#060e20",
        "C_BORDER":    "#1a3870",
        "C_BORDER_LT": "#3060b0",
        "C_ACCENT":    "#00c8ff",
        "C_ACCENT_DK": "#0090cc",
        "C_ACCENT_LT": "#60dfff",
        "C_BTN":       "#0e2860",
        "C_BTN_H":     "#1a3e8a",
        "C_BTN_P":     "#061440",
        "C_RED":       "#cc2010",
        "C_RED_H":     "#ee3828",
        "C_RED_P":     "#881008",
        "C_GREEN":     "#00e676",
        "C_YELLOW":    "#ffd700",
        "C_RED_LED":   "#ff3820",
        "C_TEXT":      "#cce8ff",
        "C_TEXT_DIM":  "#5580b0",
        "C_TEXT_HEAD": "#ffffff",
        "C_SCR_BG":    "#060e20",
        "C_SCR_TH":    "#1a3870",
        "C_ADD_BTN":   "#00c8ff",
        "C_ADD_FG":    "#001020",
        "transparent": True,
        "FN": ("Tahoma", 10, "bold"),
        "FS": ("Tahoma", 9),
        "FT": ("Tahoma", 8),
        "FB": ("Tahoma", 9, "bold"),
        "FC": ("Tahoma", 8),
    },
}

T  = dict(THEMES["default"])
CW = [160, 120, 200, 120, 110]
CHEADS = ["Project", "Status", "Session / Last worked", "This week", "Last week"]


# ── Settings ──────────────────────────────────────────────────────────────────

def load_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {"theme": "default", "blur_level": 2}

def save_settings(s):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(s, f, indent=2)
    except Exception:
        pass


# ── Data ──────────────────────────────────────────────────────────────────────

def load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return []

def save_data(p):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(p, f, indent=2)
    except Exception:
        pass

def get_status(proj):
    if proj.get("session_start") is not None: return "green"
    lw = proj.get("last_worked")
    if lw is None: return "red"
    el = time.time() - lw
    if el <= ONE_WEEK:  return "green"
    if el <= TWO_WEEKS: return "yellow"
    return "red"

def fmt_hms(sec):
    sec = int(max(0, sec))
    h, sec = divmod(sec, 3600)
    m, s   = divmod(sec, 60)
    if h: return f"{h}h {m:02d}m {s:02d}s"
    if m: return f"{m}m {s:02d}s"
    return f"{s}s"

def week_sec(proj):
    now = time.time(); cut = now - ONE_WEEK
    tot = sum(min(s["end"], now) - max(s["start"], cut)
              for s in proj.get("sessions", []) if s["end"] > cut)
    ss = proj.get("session_start")
    if ss: tot += now - max(ss, cut)
    return max(0, tot)

def lweek_sec(proj):
    now = time.time(); w0 = now - ONE_WEEK; w1 = now - TWO_WEEKS
    return max(0, sum(min(s["end"], w0) - max(s["start"], w1)
                      for s in proj.get("sessions", [])
                      if s["start"] < w0 and s["end"] > w1))

def ago(proj):
    ss = proj.get("session_start")
    if ss: return f"working now  {fmt_hms(time.time() - ss)}"
    lw = proj.get("last_worked")
    if lw is None: return "never"
    el = int(time.time() - lw)
    if el < 60:    return "just now"
    if el < 3600:  return f"{el // 60}m ago"
    if el < 86400: return f"{el // 3600}h ago"
    return f"{el // 86400}d ago"

def daily(proj):
    sessions = list(proj.get("sessions", []))
    ss = proj.get("session_start")
    now = time.time()
    if ss: sessions = sessions + [{"start": ss, "end": now}]
    if not sessions: return []
    dt = defaultdict(float)
    for s in sessions:
        cur, end = s["start"], s["end"]
        while cur < end:
            d   = datetime.fromtimestamp(cur).date()
            nxt = datetime.combine(d + timedelta(1), datetime.min.time()).timestamp()
            dt[d] += min(end, nxt) - cur
            cur = nxt
    if not dt: return []
    first = min(dt.keys())
    today = datetime.fromtimestamp(now).date()
    out, d = [], today
    while d >= first:
        out.append((d, dt.get(d, 0)))
        d -= timedelta(1)
    return out


# ── Color helpers ─────────────────────────────────────────────────────────────

def _h2rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def _rgb2h(r, g, b):
    return f"#{max(0,min(255,r)):02x}{max(0,min(255,g)):02x}{max(0,min(255,b)):02x}"

def blend(c1, c2, t):
    r1,g1,b1 = _h2rgb(c1)
    r2,g2,b2 = _h2rgb(c2)
    return _rgb2h(int(r1+(r2-r1)*t), int(g1+(g2-g1)*t), int(b1+(b2-b1)*t))


# ── 3D LED canvas ─────────────────────────────────────────────────────────────

def make_led(parent, color, size=14, bg="#232323"):
    c = tk.Canvas(parent, width=size, height=size, bg=bg, highlightthickness=0)
    cx = cy = size // 2
    r  = size // 2 - 1
    if r < 2:
        c.create_oval(1, 1, size-1, size-1, fill=color, outline="")
        return c
    dark  = blend(color, "#000000", 0.5)
    mid   = blend(color, "#000000", 0.15)
    hi    = blend(color, "#ffffff", 0.6)
    # Shadow
    c.create_oval(cx-r+1, cy-r+1, cx+r+1, cy+r+1, fill="#111111", outline="")
    # Gradient body (4 steps)
    for i in range(4, 0, -1):
        t  = i / 4
        rc = max(1, int(r * t))
        col = blend(dark, mid, 1 - t)
        c.create_oval(cx-rc, cy-rc, cx+rc, cy+rc, fill=col, outline="")
    # Top gloss
    gr = max(1, int(r * 0.5))
    c.create_oval(cx-gr, cy-r+1, cx+gr, cy-r+1+int(r*0.6), fill=hi, outline="")
    # Specular
    sr = max(1, int(r * 0.2))
    c.create_oval(cx-sr, cy-int(r*0.5), cx+sr, cy-int(r*0.15),
                  fill="#ffffff", outline="")
    return c


# ── 3D Gear icon ──────────────────────────────────────────────────────────────

def draw_gear(canvas, cx, cy, r, color):
    if r < 4: return
    teeth   = 8
    tooth_h = max(2, int(r * 0.35))
    tooth_r = r + tooth_h
    inner_r = max(2, int(r * 0.38))
    tw      = 0.30   # tooth angular width fraction

    shadow  = blend(color, "#000000", 0.5)
    light   = blend(color, "#ffffff", 0.45)
    mid     = blend(color, "#000000", 0.2)

    # Build gear outline polygon
    def gear_pts(ox=0, oy=0):
        pts = []
        for i in range(teeth):
            base = i * 360 / teeth
            for frac, radius in [
                (-tw*0.5,  r),
                ( 0,       tooth_r),
                ( tw*0.5,  tooth_r),
                ( 0.5-tw*0.5, r),
            ]:
                a = math.radians(base + frac * 360 / teeth)
                pts += [ox + radius * math.cos(a), oy + radius * math.sin(a)]
        return pts

    # Drop shadow
    sp = gear_pts(cx+1, cy+1)
    canvas.create_polygon(sp, fill="#111111", outline="", smooth=False)

    # Gear body
    gp = gear_pts(cx, cy)
    canvas.create_polygon(gp, fill=shadow, outline="", smooth=False)

    # Gradient circles over body
    for step in range(6, 0, -1):
        t  = step / 6
        rc = max(1, int(r * t))
        col = blend(shadow, mid, 1 - t * 0.6)
        canvas.create_oval(cx-rc, cy-rc, cx+rc, cy+rc, fill=col, outline="")

    # Top-left shine arc
    canvas.create_arc(cx-r+2, cy-r+2, cx+r-2, cy+r-2,
                      start=100, extent=75, style="arc",
                      outline=light, width=2)

    # Inner hole
    canvas.create_oval(cx-inner_r, cy-inner_r, cx+inner_r, cy+inner_r,
                       fill=blend(color, "#000000", 0.7), outline=shadow, width=1)


class GearBtn(tk.Canvas):
    def __init__(self, parent, cmd, size=24, bg=None):
        bg = bg or T["C_HEADER"]
        super().__init__(parent, width=size, height=size,
                         bg=bg, highlightthickness=0, cursor="hand2")
        self._cmd  = cmd
        self._size = size
        self._bg   = bg
        self._redraw(hover=False)
        self.bind("<Enter>",    lambda e: self._redraw(True))
        self.bind("<Leave>",    lambda e: self._redraw(False))
        self.bind("<Button-1>", lambda e: self._click())

    def _redraw(self, hover):
        self.delete("all")
        s  = self._size
        color = T["C_ACCENT"] if hover else T["C_TEXT_DIM"]
        draw_gear(self, s // 2, s // 2, s // 2 - 4, color)

    def _click(self):
        self._redraw(False)
        if self._cmd: self._cmd()


# ── Launch arrow button ───────────────────────────────────────────────────────

def draw_launch_arrow(canvas, cx, cy, r, color):
    """Draw a diagonal arrow-up-right icon like the provided image."""
    # Arrow shaft + head pointing top-right
    # We draw a thick arrow as a polygon
    s = r  # scale
    # Arrow points: diagonal arrow NE direction
    pts = [
        # tail-left
        cx - int(s*0.55), cy + int(s*0.20),
        cx - int(s*0.55), cy + int(s*0.55),
        cx - int(s*0.20), cy + int(s*0.55),
        # bottom-right notch
        cx + int(s*0.15), cy + int(s*0.10),
        # arrowhead right
        cx + int(s*0.55), cy - int(s*0.55),
        # arrowhead top
        cx - int(s*0.10), cy - int(s*0.15),
    ]
    canvas.create_polygon(pts, fill=color, outline="", smooth=False)


class LaunchBtn(tk.Canvas):
    """Small diagonal-arrow launch button."""
    def __init__(self, parent, cmd, size=20, bg=None):
        bg = bg or T["C_BTN"]
        super().__init__(parent, width=size, height=size,
                         bg=bg, highlightthickness=0, cursor="hand2")
        self._cmd   = cmd
        self._size  = size
        self._bg    = bg
        self._draw(False)
        self.bind("<Enter>",    lambda e: self._draw(True))
        self.bind("<Leave>",    lambda e: self._draw(False))
        self.bind("<Button-1>", lambda e: self._click())

    def _draw(self, hover):
        self.delete("all")
        s  = self._size
        bg = T["C_BTN_H"] if hover else self._bg
        self.configure(bg=bg)
        color = T["C_ACCENT"] if hover else T["C_TEXT_DIM"]
        draw_launch_arrow(self, s // 2, s // 2, s // 2 - 2, color)

    def _click(self):
        self._draw(False)
        if self._cmd: self._cmd()


# ── Resources dialog ──────────────────────────────────────────────────────────

class ResourcesDialog(tk.Toplevel):
    """Manage URLs and EXE paths for a project."""
    def __init__(self, parent, proj):
        super().__init__(parent)
        self.title(f"Resources — {proj['name']}")
        self.configure(bg=T["C_BG"])
        self.resizable(False, False)
        self.grab_set(); self.transient(parent)

        self._proj     = proj
        self._entries  = []   # list of (type_var, path_var, row_frame)

        tk.Frame(self, bg=T["C_ACCENT"], height=2).pack(fill="x")

        # Header
        hdr = tk.Frame(self, bg=T["C_HEADER"], padx=14, pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Launch Resources", fg=T["C_TEXT_HEAD"],
                 bg=T["C_HEADER"], font=T["FN"]).pack(side="left")
        tk.Label(hdr, text="Opened automatically when you Start this project",
                 fg=T["C_TEXT_DIM"], bg=T["C_HEADER"], font=T["FT"]).pack(side="left", padx=(10,0))
        tk.Frame(self, bg=T["C_BORDER"], height=1).pack(fill="x")

        # Column headers
        ch = tk.Frame(self, bg=T["C_BG"], padx=14, pady=4)
        ch.pack(fill="x")
        tk.Label(ch, text="Type",  fg=T["C_TEXT_DIM"], bg=T["C_BG"],
                 font=T["FT"], width=6,  anchor="w").pack(side="left")
        tk.Label(ch, text="URL or file path", fg=T["C_TEXT_DIM"], bg=T["C_BG"],
                 font=T["FT"], anchor="w").pack(side="left", padx=(8,0))
        tk.Frame(self, bg=T["C_BORDER"], height=1).pack(fill="x")

        # Scrollable list of resources
        self._list_frame = tk.Frame(self, bg=T["C_BG"])
        self._list_frame.pack(fill="both", expand=True, padx=14, pady=6)

        # Load existing
        for res in proj.get("resources", []):
            self._add_row(res.get("type", "url"), res.get("path", ""))

        # Bottom bar
        tk.Frame(self, bg=T["C_BORDER"], height=1).pack(fill="x")
        bot = tk.Frame(self, bg=T["C_BG"], padx=14, pady=8)
        bot.pack(fill="x")
        Btn(bot, "+ Add URL",  lambda: self._add_row("url",  ""), w=90,  h=26,
            fbg=T["C_BG"]).pack(side="left", padx=(0,6))
        Btn(bot, "+ Add EXE",  lambda: self._add_row("exe",  ""), w=90,  h=26,
            fbg=T["C_BG"]).pack(side="left")
        Btn(bot, "Save",       self._save,                         w=80,  h=26,
            bg=T["C_ACCENT"], bgh=T["C_ACCENT_LT"], bgp=T["C_ACCENT_DK"],
            fg=T["C_ADD_FG"], fbg=T["C_BG"]).pack(side="right")
        Btn(bot, "Cancel",     self.destroy,                       w=80,  h=26,
            fbg=T["C_BG"]).pack(side="right", padx=(0,6))

        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        x = parent.winfo_x() + parent.winfo_width()  // 2 - self.winfo_width()  // 2
        y = parent.winfo_y() + parent.winfo_height() // 2 - self.winfo_height() // 2
        self.geometry(f"+{x}+{y}")
        parent.wait_window(self)

    def _add_row(self, rtype="url", path=""):
        row = tk.Frame(self._list_frame, bg=T["C_BG"])
        row.pack(fill="x", pady=2)

        # Type badge
        type_var = tk.StringVar(value=rtype)
        type_lbl = tk.Label(row, textvariable=type_var,
                            fg=T["C_ACCENT"] if rtype=="url" else T["C_YELLOW"],
                            bg=T["C_HEADER"], font=T["FT"],
                            width=5, anchor="center", padx=4, pady=2)
        type_lbl.pack(side="left", padx=(0,6))

        # Toggle URL/EXE
        def toggle(tv=type_var, lbl=type_lbl):
            v = "exe" if tv.get() == "url" else "url"
            tv.set(v)
            lbl.configure(fg=T["C_ACCENT"] if v=="url" else T["C_YELLOW"])
        type_lbl.configure(cursor="hand2")
        type_lbl.bind("<Button-1>", lambda e: toggle())

        # Path entry
        path_var = tk.StringVar(value=path)
        entry = tk.Entry(row, textvariable=path_var,
                         bg=T["C_HEADER"], fg=T["C_TEXT"],
                         insertbackground=T["C_ACCENT"],
                         relief="flat", font=T["FS"],
                         bd=0, highlightthickness=1,
                         highlightcolor=T["C_ACCENT"],
                         highlightbackground=T["C_BORDER"],
                         width=42)
        entry.pack(side="left", ipady=4, padx=(0,6))

        # Browse button (for EXE)
        def browse(pv=path_var, tv=type_var):
            from tkinter import filedialog
            if tv.get() == "exe":
                f = filedialog.askopenfilename(
                    title="Select executable",
                    filetypes=[("Executables","*.exe *.bat *.cmd *.lnk"),("All files","*.*")])
            else:
                f = ""
            if f: pv.set(f)
        Btn(row, "…", lambda: browse(), w=24, h=26,
            fbg=T["C_BG"], font=T["FT"]).pack(side="left", padx=(0,4))

        # Remove
        def remove(r=row, entry_tuple=None):
            r.destroy()
            self._entries = [(tv, pv, rf) for tv, pv, rf in self._entries
                             if rf.winfo_exists()]
        rm_btn = Btn(row, "×", None, w=22, h=26,
                     bg=T["C_BTN"], bgh=T["C_RED_H"], bgp=T["C_RED_P"],
                     fg=T["C_TEXT_DIM"], font=(T["FN"][0],11,"bold"), fbg=T["C_BG"])
        rm_btn.pack(side="left")
        rm_btn._cmd = lambda r=row: remove(r)
        rm_btn._l.configure(cursor="hand2")

        self._entries.append((type_var, path_var, row))
        self.update_idletasks()

    def _save(self):
        resources = []
        for tv, pv, row in self._entries:
            if row.winfo_exists():
                path = pv.get().strip()
                if path:
                    resources.append({"type": tv.get(), "path": path})
        self._proj["resources"] = resources
        save_data_ref()   # save via global reference
        self.destroy()


def save_data_ref():
    """Called from dialog — uses the global app instance."""
    pass   # overridden at app init


# ── Smooth scrolling canvas ───────────────────────────────────────────────────

class SmoothCanvas(tk.Canvas):
    DECEL = 0.85
    FPS   = 16
    MIN_V = 0.5

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._vy       = 0.0
        self._anim     = False

    def add_velocity(self, dy):
        self._vy += dy
        if not self._anim:
            self._anim = True
            self._step()

    def _step(self):
        if abs(self._vy) < self.MIN_V:
            self._vy = 0.0; self._anim = False; return
        bbox = self.bbox("all")
        if not bbox:
            self._anim = False; return
        content_h = bbox[3] - bbox[1]
        canvas_h  = self.winfo_height()
        if content_h <= canvas_h:
            self._anim = False; return
        frac = self._vy / content_h
        cur  = self.yview()[0]
        self.yview_moveto(max(0.0, min(1.0, cur + frac)))
        self._vy *= self.DECEL
        self.after(self.FPS, self._step)


# ── Flat button ───────────────────────────────────────────────────────────────

class Btn(tk.Frame):
    def __init__(self, parent, text, cmd, w=50, h=22,
                 bg=None, bgh=None, bgp=None, fg=None, font=None, fbg=None):
        bg  = bg  or T["C_BTN"]
        bgh = bgh or T["C_BTN_H"]
        bgp = bgp or T["C_BTN_P"]
        fg  = fg  or T["C_TEXT"]
        font = font or T["FB"]
        fbg = fbg or T["C_BG"]
        super().__init__(parent, bg=fbg, width=w, height=h)
        self.pack_propagate(False)
        self._bg=bg; self._bgh=bgh; self._bgp=bgp; self._cmd=cmd
        self._b = tk.Frame(self, bg=bg, cursor="hand2",
                           highlightthickness=1,
                           highlightbackground=T["C_BORDER"])
        self._b.place(x=0, y=0, relwidth=1, relheight=1)
        self._l = tk.Label(self._b, text=text, fg=fg, bg=bg,
                           font=font, cursor="hand2")
        self._l.place(relx=.5, rely=.5, anchor="center")
        for w_ in (self._b, self._l):
            w_.bind("<Enter>",           lambda e: self._c(self._bgh))
            w_.bind("<Leave>",           lambda e: self._c(self._bg))
            w_.bind("<ButtonPress-1>",   lambda e: self._c(self._bgp))
            w_.bind("<ButtonRelease-1>", lambda e: self._fire())

    def _c(self, c):
        hb = T["C_BORDER_LT"] if c == self._bgh else T["C_BORDER"]
        self._b.configure(bg=c, highlightbackground=hb)
        self._l.configure(bg=c)

    def _fire(self):
        self._c(self._bgh)
        if self._cmd: self._cmd()


# ── Draggable blur slider ─────────────────────────────────────────────────────

class BlurSlider(tk.Frame):
    LABELS = {0: "Off", 1: "Subtle", 2: "Medium", 3: "Strong"}

    def __init__(self, parent, value=2, on_change=None, bg=None):
        bg = bg or T["C_BG"]
        super().__init__(parent, bg=bg)
        self._cb    = on_change
        self._value = value
        self._drag  = False
        W = 240; H = 28; TP = 16
        self._W = W; self._TP = TP; self._TW = W - TP * 2; self._TR = 8

        top = tk.Frame(self, bg=bg); top.pack(fill="x")
        tk.Label(top, text="Blur level", fg=T["C_TEXT_DIM"],
                 bg=bg, font=T["FT"]).pack(side="left")
        self._vl = tk.Label(top, text=self.LABELS[value],
                            fg=T["C_ACCENT"], bg=bg,
                            font=(T["FN"][0], 9, "bold"))
        self._vl.pack(side="right")

        self._cv = tk.Canvas(self, width=W, height=H, bg=bg,
                             highlightthickness=0, cursor="hand2")
        self._cv.pack(pady=(3, 0))
        self._draw()

        bot = tk.Frame(self, bg=bg); bot.pack(fill="x", padx=TP - 2)
        for lbl in self.LABELS.values():
            tk.Label(bot, text=lbl, fg=T["C_TEXT_DIM"],
                     bg=bg, font=T["FT"]).pack(side="left", expand=True)

        self._cv.bind("<ButtonPress-1>",   self._press)
        self._cv.bind("<B1-Motion>",       self._motion)
        self._cv.bind("<ButtonRelease-1>", self._release)

    def _xv(self, x):
        return max(0, min(3, round((x - self._TP) / self._TW * 3)))

    def _vx(self, v):
        return self._TP + int(v / 3 * self._TW)

    def _draw(self):
        self._cv.delete("all")
        W = self._W; H = 28; cy = H // 2; TP = self._TP

        # Track bg
        self._cv.create_rectangle(TP, cy-2, W-TP, cy+2,
                                  fill=T["C_BORDER"], outline="")
        # Filled
        self._cv.create_rectangle(TP, cy-2, self._vx(self._value), cy+2,
                                  fill=T["C_ACCENT"], outline="")
        # Tick marks
        for i in range(4):
            x = self._vx(i)
            self._cv.create_line(x, cy-5, x, cy+5,
                                 fill=T["C_BORDER_LT"], width=1)

        # Thumb as 3D LED
        tx = self._vx(self._value)
        r  = self._TR
        dark  = blend(T["C_ACCENT"], "#000000", 0.4)
        light = blend(T["C_ACCENT"], "#ffffff", 0.55)
        self._cv.create_oval(tx-r+1, cy-r+1, tx+r+1, cy+r+1,
                             fill="#111111", outline="")
        for step in range(4, 0, -1):
            t  = step / 4
            rc = max(1, int(r * t))
            col = blend(dark, T["C_ACCENT"], 1 - t * 0.5)
            self._cv.create_oval(tx-rc, cy-rc, tx+rc, cy+rc,
                                 fill=col, outline="")
        gr = max(1, int(r * 0.5))
        self._cv.create_oval(tx-gr, cy-r+1, tx+gr, cy-r+1+int(r*0.6),
                             fill=light, outline="")

    def _press(self, e):
        self._drag = True
        v = self._xv(e.x)
        if v != self._value:
            self._value = v
            self._vl.configure(text=self.LABELS[v])
            self._draw()
            if self._cb: self._cb(v)

    def _motion(self, e):
        if not self._drag: return
        v = self._xv(e.x)
        if v != self._value:
            self._value = v
            self._vl.configure(text=self.LABELS[v])
            self._draw()
            if self._cb: self._cb(v)

    def _release(self, e):
        self._drag = False
        v = self._xv(e.x)
        if v != self._value:
            self._value = v
            self._vl.configure(text=self.LABELS[v])
            self._draw()
        if self._cb: self._cb(self._value)


# ── Dialogs ───────────────────────────────────────────────────────────────────

class AskDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.result = None
        self.title("Add project")
        self.configure(bg=T["C_BG"])
        self.resizable(False, False)
        self.grab_set(); self.transient(parent)

        tk.Frame(self, bg=T["C_ACCENT"], height=2).pack(fill="x")
        f = tk.Frame(self, bg=T["C_BG"], padx=16, pady=14); f.pack()
        tk.Label(f, text="Project name", fg=T["C_TEXT_HEAD"],
                 bg=T["C_BG"], font=T["FN"]).pack(anchor="w", pady=(0,8))
        self._e = tk.Entry(f, bg=T["C_HEADER"], fg=T["C_TEXT"],
                           insertbackground=T["C_ACCENT"], relief="flat",
                           font=T["FS"], bd=0, highlightthickness=1,
                           highlightcolor=T["C_ACCENT"],
                           highlightbackground=T["C_BORDER"])
        self._e.pack(fill="x", ipady=5)
        self._e.focus_set()

        bf = tk.Frame(f, bg=T["C_BG"], pady=10); bf.pack(fill="x")
        Btn(bf, "Cancel", self.destroy, w=72, h=26,
            fbg=T["C_BG"]).pack(side="right", padx=(4,0))
        Btn(bf, "Add", self._ok, w=72, h=26,
            bg=T["C_ACCENT"], bgh=T["C_ACCENT_LT"], bgp=T["C_ACCENT_DK"],
            fg=T["C_ADD_FG"], fbg=T["C_BG"]).pack(side="right")

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self._ctr(parent); parent.wait_window(self)

    def _ok(self):
        self.result = self._e.get(); self.destroy()

    def _ctr(self, p):
        self.update_idletasks()
        x = p.winfo_x() + p.winfo_width()  // 2 - self.winfo_width()  // 2
        y = p.winfo_y() + p.winfo_height() // 2 - self.winfo_height() // 2
        self.geometry(f"+{x}+{y}")


class ConfirmDialog(tk.Toplevel):
    def __init__(self, parent, msg):
        super().__init__(parent)
        self.result = False
        self.title("Confirm")
        self.configure(bg=T["C_BG"])
        self.resizable(False, False)
        self.grab_set(); self.transient(parent)

        tk.Frame(self, bg=T["C_RED"], height=2).pack(fill="x")
        f = tk.Frame(self, bg=T["C_BG"], padx=16, pady=14); f.pack()
        tk.Label(f, text=msg, fg=T["C_TEXT"], bg=T["C_BG"],
                 font=T["FS"], wraplength=280).pack(pady=(0,12))
        bf = tk.Frame(f, bg=T["C_BG"]); bf.pack(fill="x")
        Btn(bf, "Cancel", self.destroy, w=72, h=26,
            fbg=T["C_BG"]).pack(side="right", padx=(4,0))
        Btn(bf, "Delete", self._yes, w=72, h=26,
            bg=T["C_RED"], bgh=T["C_RED_H"], bgp=T["C_RED_P"],
            fg=T["C_TEXT"], fbg=T["C_BG"]).pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        self._ctr(parent); parent.wait_window(self)

    def _yes(self): self.result = True; self.destroy()

    def _ctr(self, p):
        self.update_idletasks()
        x = p.winfo_x() + p.winfo_width()  // 2 - self.winfo_width()  // 2
        y = p.winfo_y() + p.winfo_height() // 2 - self.winfo_height() // 2
        self.geometry(f"+{x}+{y}")


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, settings, on_apply):
        super().__init__(parent)
        self.title("Settings")
        self.configure(bg=T["C_BG"])
        self.resizable(False, False)
        self.grab_set(); self.transient(parent)
        self._on_apply = on_apply
        self._settings = dict(settings)

        tk.Frame(self, bg=T["C_ACCENT"], height=2).pack(fill="x")
        self._f = tk.Frame(self, bg=T["C_BG"], padx=20, pady=16)
        self._f.pack(fill="both")
        self._build()
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        x = parent.winfo_x() + parent.winfo_width() - self.winfo_width() - 10
        y = parent.winfo_y() + 48
        self.geometry(f"+{x}+{y}")

    def _build(self):
        for w in self._f.winfo_children(): w.destroy()
        f = self._f

        tk.Label(f, text="Theme", fg=T["C_TEXT_DIM"],
                 bg=T["C_BG"], font=T["FT"]).pack(anchor="w")
        tk.Frame(f, bg=T["C_BORDER"], height=1).pack(fill="x", pady=(4,8))

        self._tv = tk.StringVar(value=self._settings.get("theme","default"))
        for key, theme in THEMES.items():
            row = tk.Frame(f, bg=T["C_BG"]); row.pack(fill="x", pady=2)
            tk.Radiobutton(row, variable=self._tv, value=key,
                           bg=T["C_BG"], activebackground=T["C_BG"],
                           selectcolor=T["C_HEADER"], fg=T["C_ACCENT"],
                           cursor="hand2",
                           command=lambda k=key: self._pick(k)).pack(side="left")
            tk.Label(row, text=theme["name"], fg=T["C_TEXT"],
                     bg=T["C_BG"], font=T["FS"]).pack(side="left", padx=(4,0))

        self._bw = tk.Frame(f, bg=T["C_BG"])
        self._bw.pack(fill="x", pady=(14,0))
        self._build_blur()

        tk.Frame(f, bg=T["C_BORDER"], height=1).pack(fill="x", pady=(14,0))
        Btn(f, "Close", self.destroy, w=80, h=26,
            fbg=T["C_BG"]).pack(anchor="e", pady=(10,0))

    def _build_blur(self):
        for w in self._bw.winfo_children(): w.destroy()
        if self._settings.get("theme","default") != "y2k": return
        BlurSlider(self._bw,
                   value=self._settings.get("blur_level", 2),
                   on_change=self._on_blur,
                   bg=T["C_BG"]).pack(fill="x")

    def _pick(self, key):
        self._settings["theme"] = key
        self._on_apply(self._settings)
        self._build_blur()

    def _on_blur(self, level):
        self._settings["blur_level"] = level
        self._on_apply(self._settings)


# ── Main App ──────────────────────────────────────────────────────────────────

class Tracker(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tracker")
        self.geometry("820x460")
        self.minsize(640, 300)
        self.resizable(True, True)

        try:
            icon = tk.PhotoImage(width=1, height=1)
            self.iconphoto(True, icon)
        except Exception: pass

        self._settings = load_settings()
        self._hwnd     = None
        self._anim     = False

        # Recover crashed sessions
        self.projects = load_data()
        now = time.time()
        for p in self.projects:
            ss = p.get("session_start")
            if ss:
                p.setdefault("sessions", []).append({"start": ss, "end": now})
                p["last_worked"] = now
                p["session_start"] = None
        save_data(self.projects)

        self._expanded = set()
        self._refs     = {}

        global T, save_data_ref
        T = dict(THEMES.get(self._settings.get("theme","default"), THEMES["default"]))
        save_data_ref = lambda: save_data(self.projects)

        self._build_ui()
        self._render()
        self.after(200, self._init_dwm)
        self._tick()

    def _init_dwm(self):
        self._hwnd = _get_hwnd(self)
        if self._hwnd:
            style_titlebar(self._hwnd, self._settings.get("theme","default"))
            apply_blur(self._hwnd,
                       self._settings.get("blur_level", 2),
                       self._settings.get("theme","default"))

    def _apply_settings(self, settings):
        self._settings = settings
        save_settings(settings)
        global T
        T = dict(THEMES.get(settings.get("theme","default"), THEMES["default"]))
        self.configure(bg=T["C_ROOT"])
        if self._hwnd:
            style_titlebar(self._hwnd, settings.get("theme","default"))
            apply_blur(self._hwnd,
                       settings.get("blur_level", 2),
                       settings.get("theme","default"))
        self._full_rebuild()

    def _full_rebuild(self):
        for w in self.winfo_children(): w.destroy()
        self._refs = {}
        self._build_ui()
        self._render()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.configure(bg=T["C_ROOT"])

        # Header
        top = tk.Frame(self, bg=T["C_HEADER"], height=38)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Frame(top, bg=T["C_BORDER"], height=1).pack(side="bottom", fill="x")

        GearBtn(top, self._open_settings, size=24,
                bg=T["C_HEADER"]).pack(side="right", padx=8, pady=7)
        Btn(top, "+", self._add, w=28, h=26,
            bg=T["C_ADD_BTN"], bgh=T["C_BTN_H"], bgp=T["C_BTN_P"],
            fg=T["C_ADD_FG"], font=(T["FN"][0], 14, "bold"),
            fbg=T["C_HEADER"]).pack(side="right", padx=(0,4), pady=6)

        # Column headers
        ch = tk.Frame(self, bg=T["C_HEADER"])
        ch.pack(fill="x")
        tk.Frame(ch, bg=T["C_BORDER"], height=1).pack(side="bottom", fill="x")
        tk.Frame(ch, bg=T["C_HEADER"], width=4, height=28).pack(side="left")
        for label, w in zip(CHEADS, CW):
            cell = tk.Frame(ch, bg=T["C_HEADER"], width=w, height=28)
            cell.pack(side="left")
            cell.pack_propagate(False)
            tk.Label(cell, text=label, fg=T["C_TEXT_DIM"], bg=T["C_HEADER"],
                     font=T["FC"], anchor="w", padx=8).pack(fill="both", expand=True)

        # Scroll area
        wrap = tk.Frame(self, bg=T["C_ROOT"])
        wrap.pack(fill="both", expand=True)

        self._cv = SmoothCanvas(wrap, bg=T["C_BG"], highlightthickness=0)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self._cv.yview,
                          bg=T["C_SCR_BG"], troughcolor=T["C_SCR_BG"],
                          activebackground=T["C_SCR_TH"], width=7,
                          relief="flat", elementborderwidth=0, borderwidth=0)
        self._cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._cv.pack(side="left", fill="both", expand=True)

        self._lf = tk.Frame(self._cv, bg=T["C_BG"])
        self._cid = self._cv.create_window((0,0), window=self._lf, anchor="nw")

        self._lf.bind("<Configure>", lambda e: self._cv.configure(
            scrollregion=self._cv.bbox("all")))
        self._cv.bind("<Configure>", lambda e: self._cv.itemconfig(
            self._cid, width=e.width))

        # Bind mouse wheel globally — route to smooth canvas
        self.bind_all("<MouseWheel>", self._wheel)

        # Status bar
        tk.Frame(self, bg=T["C_BORDER"], height=1).pack(fill="x")
        self._sv = tk.StringVar()
        tk.Label(self, textvariable=self._sv, fg=T["C_TEXT_DIM"],
                 bg=T["C_HEADER"], font=T["FT"],
                 anchor="w", padx=10, pady=3).pack(fill="x")

    def _wheel(self, e):
        # Positive delta = scroll up, negative = scroll down
        self._cv.add_velocity(-e.delta / 120 * 40)

    # ── Render ────────────────────────────────────────────────────────────────

    def _render(self):
        self._refs.clear()
        for w in self._lf.winfo_children(): w.destroy()

        if not self.projects:
            tk.Label(self._lf, text="No projects. Click + to add one.",
                     fg=T["C_TEXT_DIM"], bg=T["C_BG"],
                     font=T["FS"], pady=40).pack()
        else:
            for i, p in enumerate(self.projects):
                self._row(i, p, i % 2 == 0)

        n    = len(self.projects)
        g    = sum(1 for p in self.projects if get_status(p) == "green")
        y    = sum(1 for p in self.projects if get_status(p) == "yellow")
        r    = sum(1 for p in self.projects if get_status(p) == "red")
        live = sum(1 for p in self.projects if p.get("session_start"))
        pts  = [f"{n} project{'s' if n!=1 else ''}",
                f"active {g}", f"idle {y}", f"stalled {r}"]
        if live: pts.append(f"in session {live}")
        self._sv.set("   ·   ".join(pts))

    def _row(self, idx, proj, alt):
        active = proj.get("session_start") is not None
        status = get_status(proj)
        sc     = (T["C_GREEN"] if status == "green"
                  else T["C_YELLOW"] if status == "yellow"
                  else T["C_RED_LED"])
        sl     = ("working" if active
                  else "active" if status == "green"
                  else "idle" if status == "yellow"
                  else "stalled")
        exp    = idx in self._expanded
        bbg    = (T["C_ROW_ACT"] if active
                  else T["C_ROW_ALT"] if alt
                  else T["C_BG"])
        hbg    = T["C_ROW_ACT_H"] if active else T["C_ROW_HOVER"]

        row = tk.Frame(self._lf, bg=bbg)
        row.pack(fill="x")
        tk.Frame(self._lf, bg=T["C_BORDER"], height=1).pack(fill="x")

        hw = []
        def enter(e, r=row, h=hbg, ww=hw):
            r.configure(bg=h)
            for w in ww:
                try: w.configure(bg=h)
                except Exception: pass
        def leave(e, r=row, b=bbg, ww=hw):
            r.configure(bg=b)
            for w in ww:
                try: w.configure(bg=b)
                except Exception: pass

        row.bind("<Enter>",    enter)
        row.bind("<Leave>",    leave)
        row.bind("<Button-1>", lambda e, i=idx: self._toggle(i))

        # Left accent strip
        tk.Frame(row, bg=T["C_ACCENT"] if active else sc,
                 width=4).pack(side="left", fill="y")

        # Name
        c0 = tk.Frame(row, bg=bbg, width=CW[0], height=34)
        c0.pack(side="left"); c0.pack_propagate(False)
        nl = tk.Label(c0, text=proj["name"],
                      fg=T["C_TEXT_HEAD"] if active else T["C_TEXT"],
                      bg=bbg, font=T["FN"], anchor="w", padx=10, cursor="hand2")
        nl.pack(fill="both", expand=True)
        nl.bind("<Button-1>", lambda e, i=idx: self._toggle(i))
        nl.bind("<Enter>", enter); nl.bind("<Leave>", leave)
        hw += [c0, nl]

        # Status — 3D LED
        c1 = tk.Frame(row, bg=bbg, width=CW[1], height=34)
        c1.pack(side="left"); c1.pack_propagate(False)
        sf = tk.Frame(c1, bg=bbg); sf.pack(side="left", padx=10, fill="y")
        si = tk.Frame(sf, bg=bbg); si.pack(expand=True, fill="both")
        make_led(si, sc, size=14, bg=bbg).pack(side="left", pady=10)
        tk.Label(si, text=sl, fg=sc, bg=bbg,
                 font=T["FS"], padx=5).pack(side="left")
        hw += [c1, sf, si]

        # Session / last worked
        c2 = tk.Frame(row, bg=bbg, width=CW[2], height=34)
        c2.pack(side="left"); c2.pack_propagate(False)
        tv = tk.StringVar(value=ago(proj))
        tl = tk.Label(c2, textvariable=tv,
                      fg=T["C_GREEN"] if active else T["C_TEXT_DIM"],
                      bg=bbg, font=T["FS"], anchor="w", padx=10)
        tl.pack(fill="both", expand=True)
        hw += [c2, tl]

        # This week
        c3 = tk.Frame(row, bg=bbg, width=CW[3], height=34)
        c3.pack(side="left"); c3.pack_propagate(False)
        ws = week_sec(proj)
        wv = tk.StringVar(value=fmt_hms(ws) if ws > 0 else "—")
        wl = tk.Label(c3, textvariable=wv, fg=T["C_TEXT_DIM"],
                      bg=bbg, font=T["FS"], anchor="w", padx=10)
        wl.pack(fill="both", expand=True)
        hw += [c3, wl]

        # Last week
        c4 = tk.Frame(row, bg=bbg, width=CW[4], height=34)
        c4.pack(side="left"); c4.pack_propagate(False)
        lws = lweek_sec(proj)
        ll = tk.Label(c4, text=fmt_hms(lws) if lws > 0 else "—",
                      fg=T["C_TEXT_DIM"], bg=bbg, font=T["FS"],
                      anchor="w", padx=10)
        ll.pack(fill="both", expand=True)
        hw += [c4, ll]

        # Chevron
        chev = tk.Label(row, text="▲" if exp else "▼",
                        fg=T["C_TEXT_DIM"], bg=bbg, font=T["FT"],
                        cursor="hand2", padx=8)
        chev.pack(side="left")
        chev.bind("<Button-1>", lambda e, i=idx: self._toggle(i))
        chev.bind("<Enter>", enter); chev.bind("<Leave>", leave)
        hw.append(chev)

        # Buttons
        bf = tk.Frame(row, bg=bbg, padx=6); bf.pack(side="right")
        bf2 = tk.Frame(bf, bg=bbg); bf2.pack(pady=6)
        hw += [bf, bf2]

        # Launch resources button (arrow icon)
        LaunchBtn(bf2, lambda i=idx: self._open_resources(i),
                  size=22, bg=bbg).pack(side="left", padx=(0,6))

        if active:
            Btn(bf2, "End", lambda i=idx: self._end(i), w=42, h=22,
                bg=T["C_RED"], bgh=T["C_RED_H"], bgp=T["C_RED_P"],
                fg=T["C_TEXT"], font=T["FT"], fbg=bbg).pack(side="left", padx=(0,4))
        else:
            Btn(bf2, "Start", lambda i=idx: self._start(i), w=42, h=22,
                fbg=bbg, font=T["FT"]).pack(side="left", padx=(0,4))

        Btn(bf2, "×", lambda i=idx: self._delete(i), w=22, h=22,
            bg=T["C_BTN"], bgh=T["C_RED_H"], bgp=T["C_RED_P"],
            fg=T["C_TEXT_DIM"], font=(T["FN"][0], 11, "bold"),
            fbg=bbg).pack(side="left")

        self._refs[idx] = {"tv": tv, "wv": wv, "active": active}

        if exp: self._detail(idx, proj)

    def _detail(self, idx, proj):
        panel = tk.Frame(self._lf, bg=T["C_EXP_BG"])
        panel.pack(fill="x")
        tk.Frame(self._lf, bg=T["C_BORDER"], height=1).pack(fill="x")

        bd = daily(proj)
        if not bd:
            tk.Label(panel, text="No sessions yet.", fg=T["C_TEXT_DIM"],
                     bg=T["C_EXP_BG"], font=T["FS"],
                     pady=8, padx=20).pack(anchor="w")
            return

        hf = tk.Frame(panel, bg=T["C_EXP_BG"], padx=20, pady=6)
        hf.pack(fill="x")
        tk.Label(hf, text="", bg=T["C_EXP_BG"], width=2).pack(side="left")
        tk.Label(hf, text="Date", fg=T["C_TEXT_DIM"], bg=T["C_EXP_BG"],
                 font=T["FT"], width=22, anchor="w").pack(side="left")
        tk.Label(hf, text="Time worked", fg=T["C_TEXT_DIM"], bg=T["C_EXP_BG"],
                 font=T["FT"], anchor="w").pack(side="left", padx=(30,0))
        tk.Frame(panel, bg=T["C_BORDER"], height=1).pack(fill="x", padx=20)

        today = bd[0][0] if bd else None
        for day_dt, secs in bd:
            is_today = (day_dt == today)
            worked   = secs > 0
            r = tk.Frame(panel, bg=T["C_EXP_BG"], padx=20, pady=3)
            r.pack(fill="x")
            make_led(r, T["C_GREEN"] if worked else T["C_RED_LED"],
                     size=12, bg=T["C_EXP_BG"]).pack(side="left", padx=(0,10), pady=2)
            rfont = (T["FS"][0], 9, "bold") if is_today else T["FT"]
            ds    = day_dt.strftime("%Y-%m-%d") + (" (today)" if is_today else "")
            tk.Label(r, text=ds,
                     fg=T["C_TEXT"] if is_today else T["C_TEXT_DIM"],
                     bg=T["C_EXP_BG"], font=rfont,
                     width=22, anchor="w").pack(side="left")
            tk.Label(r, text=fmt_hms(secs) if worked else "—",
                     fg=T["C_ACCENT"] if worked else T["C_TEXT_DIM"],
                     bg=T["C_EXP_BG"], font=rfont,
                     anchor="w").pack(side="left", padx=(30,0))

        tk.Frame(panel, bg=T["C_EXP_BG"], height=6).pack()

    # ── Tick ─────────────────────────────────────────────────────────────────

    def _tick(self):
        for idx, refs in self._refs.items():
            if idx >= len(self.projects): continue
            proj = self.projects[idx]
            if refs["active"]:
                refs["tv"].set(ago(proj))
                ws = week_sec(proj)
                refs["wv"].set(fmt_hms(ws) if ws > 0 else "—")
        self.after(1000, self._tick)

    # ── Actions ──────────────────────────────────────────────────────────────

    def _open_settings(self):
        SettingsDialog(self, dict(self._settings), self._apply_settings)

    def _toggle(self, i):
        if i in self._expanded: self._expanded.discard(i)
        else: self._expanded.add(i)
        self._render()

    def _start(self, i):
        self.projects[i]["session_start"] = time.time()
        save_data(self.projects)
        self._launch_resources(i)
        self._render()

    def _launch_resources(self, i):
        """Open all URLs in Chrome and start all EXEs for project i."""
        proj = self.projects[i]
        for res in proj.get("resources", []):
            path = res.get("path", "").strip()
            if not path: continue
            try:
                if res.get("type") == "url":
                    # Try Chrome first, fall back to default browser
                    chrome_paths = [
                        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
                    ]
                    opened = False
                    for cp in chrome_paths:
                        if os.path.exists(cp):
                            subprocess.Popen([cp, path])
                            opened = True
                            break
                    if not opened:
                        webbrowser.open(path)
                else:
                    # EXE / bat / lnk
                    subprocess.Popen([path], shell=True)
            except Exception:
                pass

    def _open_resources(self, i):
        ResourcesDialog(self, self.projects[i])

    def _end(self, i):
        proj = self.projects[i]
        ss   = proj.get("session_start")
        if ss is None: return
        now = time.time()
        proj.setdefault("sessions", []).append({"start": ss, "end": now})
        proj["last_worked"]   = now
        proj["session_start"] = None
        save_data(self.projects); self._render()

    def _add(self):
        dlg = AskDialog(self)
        if dlg.result and dlg.result.strip():
            self.projects.append({
                "name": dlg.result.strip(),
                "last_worked": None, "session_start": None, "sessions": []
            })
            save_data(self.projects); self._render()

    def _delete(self, i):
        if self.projects[i].get("session_start"): self._end(i)
        dlg = ConfirmDialog(self, f"Delete \"{self.projects[i]['name']}\"?")
        if dlg.result:
            self._expanded.discard(i)
            self._expanded = {x-1 if x > i else x for x in self._expanded}
            self.projects.pop(i)
            save_data(self.projects); self._render()


if __name__ == "__main__":
    app = Tracker()
    app.mainloop()
