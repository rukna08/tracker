import tkinter as tk
from tkinter import ttk
import json, os, time, ctypes, ctypes.wintypes
from collections import defaultdict
from datetime import datetime, timedelta

DATA_FILE     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "projects.json")
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

ONE_WEEK  = 7  * 24 * 3600
TWO_WEEKS = 14 * 24 * 3600

# ── Windows DWM blur (Vista/7/10/11 Aero Glass) ───────────────────────────────

def _dwm_blur(hwnd, enable: bool, blur_region=None):
    """Enable DWM blur-behind on a window using the real Aero Glass API."""
    try:
        dwmapi = ctypes.windll.dwmapi

        class MARGINS(ctypes.Structure):
            _fields_ = [("left","i"),("right","i"),("top","i"),("bottom","i")]

        class DWM_BLURBEHIND(ctypes.Structure):
            _fields_ = [
                ("dwFlags",       ctypes.wintypes.DWORD),
                ("fEnable",       ctypes.wintypes.BOOL),
                ("hRgnBlur",      ctypes.wintypes.HANDLE),
                ("fTransitionOnMaximized", ctypes.wintypes.BOOL),
            ]

        bb = DWM_BLURBEHIND()
        bb.dwFlags  = 0x01 | 0x02   # DWM_BB_ENABLE | DWM_BB_BLURREGION
        bb.fEnable  = int(enable)
        bb.hRgnBlur = 0

        # Extend frame into entire client area (makes background transparent)
        if enable:
            m = MARGINS(-1, -1, -1, -1)
            dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(m))

        dwmapi.DwmEnableBlurBehindWindow(hwnd, ctypes.byref(bb))
        return True
    except Exception:
        return False


def _set_window_alpha_color(hwnd, color_key):
    """Set layered window with a transparent colour key so blur shows through."""
    try:
        GWL_EXSTYLE     = -20
        WS_EX_LAYERED   = 0x00080000
        LWA_COLORKEY    = 0x00000001

        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                             style | WS_EX_LAYERED)
        # colour key in COLORREF (BGR)
        r = int(color_key[1:3], 16)
        g = int(color_key[3:5], 16)
        b = int(color_key[5:7], 16)
        colorref = r | (g << 8) | (b << 16)
        ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, colorref, 0,
                                                         LWA_COLORKEY)
        return True
    except Exception:
        return False


def _acrylic_blur(hwnd, enable: bool, tint_color: int = 0x80000000):
    """
    Windows 10/11 Acrylic blur via undocumented SetWindowCompositionAttribute.
    tint_color is ABGR (alpha, blue, green, red).
    Higher alpha = more opaque tint over the blur.
    """
    try:
        ACCENT_DISABLED                = 0
        ACCENT_ENABLE_ACRYLICBLURBEHIND = 4

        class ACCENT_POLICY(ctypes.Structure):
            _fields_ = [
                ("AccentState",   ctypes.c_int),
                ("AccentFlags",   ctypes.c_int),
                ("GradientColor", ctypes.c_int),
                ("AnimationId",   ctypes.c_int),
            ]

        class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
            _fields_ = [
                ("Attribute",  ctypes.c_int),
                ("pData",      ctypes.c_void_p),
                ("cbData",     ctypes.c_size_t),
            ]

        SetWCA = ctypes.windll.user32.SetWindowCompositionAttribute

        accent = ACCENT_POLICY()
        accent.AccentState   = ACCENT_ENABLE_ACRYLICBLURBEHIND if enable else ACCENT_DISABLED
        accent.AccentFlags   = 0x20 | 0x40 | 0x80 | 0x100
        accent.GradientColor = tint_color
        accent.AnimationId   = 0

        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = 19   # WCA_ACCENT_POLICY
        data.pData     = ctypes.cast(ctypes.byref(accent), ctypes.c_void_p)
        data.cbData    = ctypes.sizeof(accent)

        SetWCA(hwnd, ctypes.byref(data))
        return True
    except Exception:
        return False


def apply_blur(hwnd, level: int, theme_key: str):
    """
    level 0  = no blur (solid)
    level 1  = subtle (low opacity tint + acrylic)
    level 2  = medium
    level 3  = strong (most transparent)
    """
    if theme_key != "y2k":
        # Disable any blur for default theme
        _acrylic_blur(hwnd, False)
        return

    if level == 0:
        _acrylic_blur(hwnd, False)
        return

    # Map level → alpha tint (lower alpha = more see-through blur)
    alphas = {1: 0xD0, 2: 0x90, 3: 0x40}
    alpha  = alphas.get(level, 0x90)

    # Base tint: deep blue #0d1f4a in BGR = 0x4a1f0d, combined with alpha
    tint = (alpha << 24) | 0x301808   # ABGR: alpha + dark blue tint
    _acrylic_blur(hwnd, True, tint_color=tint)


# ── Themes ─────────────────────────────────────────────────────────────────────

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
        "FN":  ("Segoe UI", 10, "bold"),
        "FS":  ("Segoe UI", 9),
        "FT":  ("Segoe UI", 8),
        "FB":  ("Segoe UI", 9, "bold"),
        "FC":  ("Segoe UI", 8),
    },
    "y2k": {
        "name":        "2007 Aesthetic",
        "C_ROOT":      "#00000000",   # will be overridden with transparency
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
        "FN":  ("Tahoma", 10, "bold"),
        "FS":  ("Tahoma", 9),
        "FT":  ("Tahoma", 8),
        "FB":  ("Tahoma", 9, "bold"),
        "FC":  ("Tahoma", 8),
    },
}

T = dict(THEMES["default"])

CW     = [160, 120, 200, 120, 110]
CHEADS = ["Project", "Status", "Session / Last worked", "This week", "Last week"]


# ── Settings ──────────────────────────────────────────────────────────────────

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f: return json.load(f)
        except Exception: pass
    return {"theme": "default", "blur_level": 2}

def save_settings(s):
    with open(SETTINGS_FILE, "w") as f: json.dump(s, f, indent=2)


# ── Project data ──────────────────────────────────────────────────────────────

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f: return json.load(f)
    return []

def save_data(p):
    with open(DATA_FILE, "w") as f: json.dump(p, f, indent=2)

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
    h, sec = divmod(sec, 3600); m, s = divmod(sec, 60)
    if h: return f"{h}h {m:02d}m {s:02d}s"
    if m: return f"{m}m {s:02d}s"
    return f"{s}s"

def week_sec(proj):
    now=time.time(); cut=now-ONE_WEEK
    tot=sum(min(s["end"],now)-max(s["start"],cut)
            for s in proj.get("sessions",[]) if s["end"]>cut)
    ss=proj.get("session_start")
    if ss: tot+=now-max(ss,cut)
    return max(0,tot)

def lweek_sec(proj):
    now=time.time(); w0=now-ONE_WEEK; w1=now-TWO_WEEKS
    return max(0,sum(min(s["end"],w0)-max(s["start"],w1)
                     for s in proj.get("sessions",[])
                     if s["start"]<w0 and s["end"]>w1))

def ago(proj):
    ss=proj.get("session_start")
    if ss: return f"working now  {fmt_hms(time.time()-ss)}"
    lw=proj.get("last_worked")
    if lw is None: return "never"
    el=int(time.time()-lw)
    if el<60:    return "just now"
    if el<3600:  return f"{el//60}m ago"
    if el<86400: return f"{el//3600}h ago"
    return f"{el//86400}d ago"

def daily(proj):
    sessions=list(proj.get("sessions",[]))
    ss=proj.get("session_start"); now=time.time()
    if ss: sessions=sessions+[{"start":ss,"end":now}]
    if not sessions: return []
    dt=defaultdict(float)
    for s in sessions:
        cur,end=s["start"],s["end"]
        while cur<end:
            d=datetime.fromtimestamp(cur).date()
            nxt=datetime.combine(d+timedelta(1),datetime.min.time()).timestamp()
            dt[d]+=min(end,nxt)-cur; cur=nxt
    if not dt: return []
    first=min(dt.keys()); today=datetime.fromtimestamp(now).date()
    out,d=[],today
    while d>=first: out.append((d,dt.get(d,0))); d-=timedelta(1)
    return out


# ── Widgets ───────────────────────────────────────────────────────────────────

def make_led(parent, color, size=10, bg="#232323"):
    c = tk.Canvas(parent, width=size, height=size, bg=bg, highlightthickness=0)
    c.create_oval(1, 1, size-1, size-1, fill=color, outline="")
    return c


class Btn(tk.Frame):
    def __init__(self, parent, text, cmd, w=50, h=22,
                 bg=None, bgh=None, bgp=None, fg=None, font=None, fbg=None):
        bg=bg or T["C_BTN"]; bgh=bgh or T["C_BTN_H"]; bgp=bgp or T["C_BTN_P"]
        fg=fg or T["C_TEXT"]; font=font or T["FB"]; fbg=fbg or T["C_BG"]
        super().__init__(parent, bg=fbg, width=w, height=h)
        self.pack_propagate(False)
        self._bg=bg; self._bgh=bgh; self._bgp=bgp; self._cmd=cmd
        self._b=tk.Frame(self,bg=bg,cursor="hand2",
                         highlightthickness=1,highlightbackground=T["C_BORDER"])
        self._b.place(x=0,y=0,relwidth=1,relheight=1)
        self._l=tk.Label(self._b,text=text,fg=fg,bg=bg,font=font,cursor="hand2")
        self._l.place(relx=.5,rely=.5,anchor="center")
        for w_ in (self._b,self._l):
            w_.bind("<Enter>",           lambda e: self._c(self._bgh))
            w_.bind("<Leave>",           lambda e: self._c(self._bg))
            w_.bind("<ButtonPress-1>",   lambda e: self._c(self._bgp))
            w_.bind("<ButtonRelease-1>", lambda e: self._fire())

    def _c(self,c):
        hb=T["C_BORDER_LT"] if c==self._bgh else T["C_BORDER"]
        self._b.configure(bg=c,highlightbackground=hb)
        self._l.configure(bg=c)

    def _fire(self):
        self._c(self._bgh)
        if self._cmd: self._cmd()


# ── Dialogs ───────────────────────────────────────────────────────────────────

class AskDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.result=None; self.title("Add project")
        self.configure(bg=T["C_BG"]); self.resizable(False,False)
        self.grab_set(); self.transient(parent)
        tk.Frame(self,bg=T["C_ACCENT"],height=2).pack(fill="x")
        f=tk.Frame(self,bg=T["C_BG"],padx=16,pady=14); f.pack()
        tk.Label(f,text="Project name",fg=T["C_TEXT_HEAD"],bg=T["C_BG"],font=T["FN"]).pack(anchor="w",pady=(0,8))
        self._e=tk.Entry(f,bg=T["C_HEADER"],fg=T["C_TEXT"],insertbackground=T["C_ACCENT"],
                         relief="flat",font=T["FS"],bd=0,highlightthickness=1,
                         highlightcolor=T["C_ACCENT"],highlightbackground=T["C_BORDER"])
        self._e.pack(fill="x",ipady=5); self._e.focus_set()
        bf=tk.Frame(f,bg=T["C_BG"],pady=10); bf.pack(fill="x")
        Btn(bf,"Cancel",self.destroy,w=72,h=26,fbg=T["C_BG"]).pack(side="right",padx=(4,0))
        Btn(bf,"Add",self._ok,w=72,h=26,bg=T["C_ACCENT"],bgh=T["C_ACCENT_LT"],
            bgp=T["C_ACCENT_DK"],fg=T["C_ADD_FG"],fbg=T["C_BG"]).pack(side="right")
        self.bind("<Return>",lambda e:self._ok()); self.bind("<Escape>",lambda e:self.destroy())
        self._ctr(parent); parent.wait_window(self)

    def _ok(self): self.result=self._e.get(); self.destroy()
    def _ctr(self,p):
        self.update_idletasks()
        self.geometry(f"+{p.winfo_x()+p.winfo_width()//2-self.winfo_width()//2}"
                      f"+{p.winfo_y()+p.winfo_height()//2-self.winfo_height()//2}")


class ConfirmDialog(tk.Toplevel):
    def __init__(self, parent, msg):
        super().__init__(parent)
        self.result=False; self.title("Confirm")
        self.configure(bg=T["C_BG"]); self.resizable(False,False)
        self.grab_set(); self.transient(parent)
        tk.Frame(self,bg=T["C_RED"],height=2).pack(fill="x")
        f=tk.Frame(self,bg=T["C_BG"],padx=16,pady=14); f.pack()
        tk.Label(f,text=msg,fg=T["C_TEXT"],bg=T["C_BG"],font=T["FS"],wraplength=280).pack(pady=(0,12))
        bf=tk.Frame(f,bg=T["C_BG"]); bf.pack(fill="x")
        Btn(bf,"Cancel",self.destroy,w=72,h=26,fbg=T["C_BG"]).pack(side="right",padx=(4,0))
        Btn(bf,"Delete",self._yes,w=72,h=26,bg=T["C_RED"],bgh=T["C_RED_H"],
            bgp=T["C_RED_P"],fg=T["C_TEXT"],fbg=T["C_BG"]).pack(side="right")
        self.bind("<Escape>",lambda e:self.destroy())
        self._ctr(parent); parent.wait_window(self)

    def _yes(self): self.result=True; self.destroy()
    def _ctr(self,p):
        self.update_idletasks()
        self.geometry(f"+{p.winfo_x()+p.winfo_width()//2-self.winfo_width()//2}"
                      f"+{p.winfo_y()+p.winfo_height()//2-self.winfo_height()//2}")


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, settings, on_apply):
        super().__init__(parent)
        self.title("Settings")
        self.configure(bg=T["C_BG"])
        self.resizable(False, False)
        self.grab_set(); self.transient(parent)
        self._on_apply = on_apply
        self._settings = settings

        tk.Frame(self, bg=T["C_ACCENT"], height=2).pack(fill="x")
        f = tk.Frame(self, bg=T["C_BG"], padx=20, pady=16)
        f.pack(fill="both")

        # ── Theme section ──────────────────────────────────────────────────
        tk.Label(f, text="Theme", fg=T["C_TEXT_DIM"], bg=T["C_BG"],
                 font=T["FT"]).pack(anchor="w")
        tk.Frame(f, bg=T["C_BORDER"], height=1).pack(fill="x", pady=(4,8))

        self._theme_var = tk.StringVar(value=settings.get("theme","default"))
        for key, theme in THEMES.items():
            row = tk.Frame(f, bg=T["C_BG"])
            row.pack(fill="x", pady=2)
            tk.Radiobutton(row, variable=self._theme_var, value=key,
                           bg=T["C_BG"], activebackground=T["C_BG"],
                           selectcolor=T["C_HEADER"], fg=T["C_ACCENT"],
                           cursor="hand2",
                           command=self._on_theme_change).pack(side="left")
            tk.Label(row, text=theme["name"], fg=T["C_TEXT"], bg=T["C_BG"],
                     font=T["FS"]).pack(side="left", padx=(4,0))

        # ── Blur section (only shown for y2k theme) ────────────────────────
        self._blur_frame = tk.Frame(f, bg=T["C_BG"])
        self._blur_frame.pack(fill="x", pady=(12,0))
        self._build_blur_section()

        # ── Close ──────────────────────────────────────────────────────────
        tk.Frame(f, bg=T["C_BORDER"], height=1).pack(fill="x", pady=(14,0))
        Btn(f, "Close", self.destroy, w=80, h=26,
            fbg=T["C_BG"]).pack(anchor="e", pady=(10,0))

        self.bind("<Escape>", lambda e: self.destroy())
        # Position near top-right of parent
        self.update_idletasks()
        x = parent.winfo_x() + parent.winfo_width() - self.winfo_width() - 10
        y = parent.winfo_y() + 48
        self.geometry(f"+{x}+{y}")

    def _build_blur_section(self):
        for w in self._blur_frame.winfo_children():
            w.destroy()

        is_y2k = self._theme_var.get() == "y2k"
        if not is_y2k:
            return

        tk.Label(self._blur_frame, text="Background Blur", fg=T["C_TEXT_DIM"],
                 bg=T["C_BG"], font=T["FT"]).pack(anchor="w")
        tk.Frame(self._blur_frame, bg=T["C_BORDER"], height=1).pack(fill="x", pady=(4,10))

        blur_labels = {0: "Off", 1: "Subtle", 2: "Medium", 3: "Strong"}
        current = self._settings.get("blur_level", 2)

        # Slider row
        slider_row = tk.Frame(self._blur_frame, bg=T["C_BG"])
        slider_row.pack(fill="x")

        self._blur_val_lbl = tk.Label(slider_row,
                                      text=blur_labels[current],
                                      fg=T["C_ACCENT"], bg=T["C_BG"],
                                      font=(T["FN"][0], 9, "bold"), width=8)
        self._blur_val_lbl.pack(side="right")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Blur.Horizontal.TScale",
                         background=T["C_BG"],
                         troughcolor=T["C_BORDER"],
                         sliderthickness=16,
                         sliderrelief="flat")

        self._blur_var = tk.IntVar(value=current)
        slider = ttk.Scale(slider_row, from_=0, to=3,
                           variable=self._blur_var,
                           orient="horizontal", length=180,
                           style="Blur.Horizontal.TScale",
                           command=lambda v: self._on_blur_change(int(float(v))))
        slider.pack(side="left", fill="x", expand=True, padx=(0,8))

        # Level labels underneath
        lbl_row = tk.Frame(self._blur_frame, bg=T["C_BG"])
        lbl_row.pack(fill="x", padx=2)
        for i, lbl in blur_labels.items():
            tk.Label(lbl_row, text=lbl, fg=T["C_TEXT_DIM"], bg=T["C_BG"],
                     font=T["FT"]).pack(side="left", expand=True)

    def _on_theme_change(self):
        key = self._theme_var.get()
        self._settings["theme"] = key
        self._on_apply(self._settings)
        self._build_blur_section()
        # Resize to fit
        self.update_idletasks()

    def _on_blur_change(self, level):
        self._blur_var.set(level)
        labels = {0: "Off", 1: "Subtle", 2: "Medium", 3: "Strong"}
        self._blur_val_lbl.configure(text=labels[level])
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
        self._hwnd     = None   # set after window is shown

        self.projects = load_data()
        now = time.time()
        for p in self.projects:
            ss = p.get("session_start")
            if ss:
                p.setdefault("sessions",[]).append({"start":ss,"end":now})
                p["last_worked"]=now; p["session_start"]=None
        save_data(self.projects)

        self._expanded = set()
        self._refs     = {}

        self._apply_theme_colors(self._settings.get("theme","default"))
        self._build_ui()
        self._render()

        # Apply blur after the window is visible
        self.after(100, self._init_blur)
        self._tick()

    def _init_blur(self):
        self._hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
        if not self._hwnd:
            self._hwnd = self.winfo_id()
        self._refresh_blur()

    def _apply_theme_colors(self, key):
        global T
        T = dict(THEMES.get(key, THEMES["default"]))

    def _refresh_blur(self):
        if not self._hwnd: return
        theme  = self._settings.get("theme", "default")
        level  = self._settings.get("blur_level", 2)
        apply_blur(self._hwnd, level, theme)

    def _apply_settings(self, settings):
        """Called by settings dialog on any change."""
        self._settings = settings
        save_settings(settings)
        theme = settings.get("theme", "default")
        self._apply_theme_colors(theme)

        # Set window background opacity for y2k theme
        if T.get("transparent"):
            self.configure(bg="#010203")   # near-black magic key
        else:
            self.configure(bg=T["C_ROOT"])

        self._refresh_blur()
        self._full_rebuild()

    def _full_rebuild(self):
        for w in self.winfo_children():
            w.destroy()
        self._refs = {}
        self._build_ui()
        self._render()

    # ── Skeleton ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root_bg = "#010203" if T.get("transparent") else T["C_ROOT"]
        self.configure(bg=root_bg)

        top = tk.Frame(self, bg=T["C_HEADER"], height=38)
        top.pack(fill="x"); top.pack_propagate(False)
        tk.Frame(top, bg=T["C_BORDER"], height=1).pack(side="bottom", fill="x")

        Btn(top, "⚙", self._open_settings, w=28, h=26,
            bg=T["C_BTN"], bgh=T["C_BTN_H"], bgp=T["C_BTN_P"],
            fg=T["C_TEXT_DIM"], font=(T["FN"][0], 13),
            fbg=T["C_HEADER"]).pack(side="right", padx=(4,8), pady=6)

        Btn(top, "+", self._add, w=28, h=26,
            bg=T["C_ADD_BTN"], bgh=T["C_BTN_H"], bgp=T["C_BTN_P"],
            fg=T["C_ADD_FG"], font=(T["FN"][0], 14, "bold"),
            fbg=T["C_HEADER"]).pack(side="right", padx=(0,2), pady=6)

        ch = tk.Frame(self, bg=T["C_HEADER"])
        ch.pack(fill="x")
        tk.Frame(ch, bg=T["C_BORDER"], height=1).pack(side="bottom", fill="x")
        tk.Frame(ch, bg=T["C_HEADER"], width=4, height=28).pack(side="left")
        for label, w in zip(CHEADS, CW):
            cell = tk.Frame(ch, bg=T["C_HEADER"], width=w, height=28)
            cell.pack(side="left"); cell.pack_propagate(False)
            tk.Label(cell, text=label, fg=T["C_TEXT_DIM"], bg=T["C_HEADER"],
                     font=T["FC"], anchor="w", padx=8).pack(fill="both", expand=True)

        wrap = tk.Frame(self, bg=root_bg)
        wrap.pack(fill="both", expand=True)

        self._cv = tk.Canvas(wrap, bg=T["C_BG"], highlightthickness=0)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self._cv.yview,
                          bg=T["C_SCR_BG"], troughcolor=T["C_SCR_BG"],
                          activebackground=T["C_SCR_TH"], width=7,
                          relief="flat", elementborderwidth=0, borderwidth=0)
        self._cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._cv.pack(side="left", fill="both", expand=True)

        self._lf = tk.Frame(self._cv, bg=T["C_BG"])
        self._cw_id = self._cv.create_window((0,0), window=self._lf, anchor="nw")
        self._lf.bind("<Configure>", lambda e: self._cv.configure(
            scrollregion=self._cv.bbox("all")))
        self._cv.bind("<Configure>", lambda e: self._cv.itemconfig(
            self._cw_id, width=e.width))
        self._cv.bind_all("<MouseWheel>",
            lambda e: self._cv.yview_scroll(-1*(e.delta//120),"units"))

        tk.Frame(self, bg=T["C_BORDER"], height=1).pack(fill="x")
        self._sv = tk.StringVar()
        tk.Label(self, textvariable=self._sv, fg=T["C_TEXT_DIM"],
                 bg=T["C_HEADER"], font=T["FT"],
                 anchor="w", padx=10, pady=3).pack(fill="x")

    # ── Render ────────────────────────────────────────────────────────────────

    def _render(self):
        self._refs.clear()
        for w in self._lf.winfo_children(): w.destroy()

        if not self.projects:
            tk.Label(self._lf, text="No projects. Click + to add one.",
                     fg=T["C_TEXT_DIM"], bg=T["C_BG"], font=T["FS"], pady=40).pack()
        else:
            for i,p in enumerate(self.projects):
                self._row(i, p, i%2==0)

        n    = len(self.projects)
        g    = sum(1 for p in self.projects if get_status(p)=="green")
        y    = sum(1 for p in self.projects if get_status(p)=="yellow")
        r    = sum(1 for p in self.projects if get_status(p)=="red")
        live = sum(1 for p in self.projects if p.get("session_start"))
        pts  = [f"{n} project{'s' if n!=1 else ''}",
                f"active {g}",f"idle {y}",f"stalled {r}"]
        if live: pts.append(f"in session {live}")
        self._sv.set("   ·   ".join(pts))

    def _row(self, idx, proj, alt):
        active = proj.get("session_start") is not None
        status = get_status(proj)
        sc     = (T["C_GREEN"] if status=="green"
                  else T["C_YELLOW"] if status=="yellow"
                  else T["C_RED_LED"])
        sl     = ("working" if active
                  else "active" if status=="green"
                  else "idle" if status=="yellow"
                  else "stalled")
        exp    = idx in self._expanded
        bbg    = T["C_ROW_ACT"] if active else (T["C_ROW_ALT"] if alt else T["C_BG"])
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
        row.bind("<Button-1>", lambda e,i=idx: self._toggle(i))

        # Accent strip
        tk.Frame(row, bg=T["C_ACCENT"] if active else sc, width=4).pack(side="left",fill="y")

        # Name
        c0=tk.Frame(row,bg=bbg,width=CW[0],height=34); c0.pack(side="left"); c0.pack_propagate(False)
        nl=tk.Label(c0,text=proj["name"],fg=T["C_TEXT_HEAD"] if active else T["C_TEXT"],
                    bg=bbg,font=T["FN"],anchor="w",padx=10,cursor="hand2")
        nl.pack(fill="both",expand=True)
        nl.bind("<Button-1>",lambda e,i=idx:self._toggle(i))
        nl.bind("<Enter>",enter); nl.bind("<Leave>",leave)
        hw+=[c0,nl]

        # Status
        c1=tk.Frame(row,bg=bbg,width=CW[1],height=34); c1.pack(side="left"); c1.pack_propagate(False)
        si=tk.Frame(c1,bg=bbg); si.pack(side="left",padx=10,fill="y")
        sc_f=tk.Frame(si,bg=bbg); sc_f.pack(expand=True,fill="both")
        make_led(sc_f,sc,size=10,bg=bbg).pack(side="left",pady=12)
        tk.Label(sc_f,text=sl,fg=sc,bg=bbg,font=T["FS"],padx=4).pack(side="left")
        hw+=[c1,si,sc_f]

        # Session
        c2=tk.Frame(row,bg=bbg,width=CW[2],height=34); c2.pack(side="left"); c2.pack_propagate(False)
        tv=tk.StringVar(value=ago(proj))
        tl=tk.Label(c2,textvariable=tv,fg=T["C_GREEN"] if active else T["C_TEXT_DIM"],
                    bg=bbg,font=T["FS"],anchor="w",padx=10)
        tl.pack(fill="both",expand=True)
        hw+=[c2,tl]

        # This week
        c3=tk.Frame(row,bg=bbg,width=CW[3],height=34); c3.pack(side="left"); c3.pack_propagate(False)
        ws=week_sec(proj); wv=tk.StringVar(value=fmt_hms(ws) if ws>0 else "—")
        wl=tk.Label(c3,textvariable=wv,fg=T["C_TEXT_DIM"],bg=bbg,font=T["FS"],anchor="w",padx=10)
        wl.pack(fill="both",expand=True)
        hw+=[c3,wl]

        # Last week
        c4=tk.Frame(row,bg=bbg,width=CW[4],height=34); c4.pack(side="left"); c4.pack_propagate(False)
        lws=lweek_sec(proj)
        ll=tk.Label(c4,text=fmt_hms(lws) if lws>0 else "—",
                    fg=T["C_TEXT_DIM"],bg=bbg,font=T["FS"],anchor="w",padx=10)
        ll.pack(fill="both",expand=True)
        hw+=[c4,ll]

        # Chevron
        chev=tk.Label(row,text="▲" if exp else "▼",fg=T["C_TEXT_DIM"],bg=bbg,
                      font=T["FT"],cursor="hand2",padx=8)
        chev.pack(side="left")
        chev.bind("<Button-1>",lambda e,i=idx:self._toggle(i))
        chev.bind("<Enter>",enter); chev.bind("<Leave>",leave)
        hw.append(chev)

        # Buttons
        bf=tk.Frame(row,bg=bbg,padx=6); bf.pack(side="right"); hw.append(bf)
        bf2=tk.Frame(bf,bg=bbg); bf2.pack(pady=6); hw.append(bf2)
        if active:
            Btn(bf2,"End",lambda i=idx:self._end(i),w=42,h=22,
                bg=T["C_RED"],bgh=T["C_RED_H"],bgp=T["C_RED_P"],
                fg=T["C_TEXT"],font=T["FT"],fbg=bbg).pack(side="left",padx=(0,4))
        else:
            Btn(bf2,"Start",lambda i=idx:self._start(i),w=42,h=22,
                fbg=bbg,font=T["FT"]).pack(side="left",padx=(0,4))
        Btn(bf2,"×",lambda i=idx:self._delete(i),w=22,h=22,
            bg=T["C_BTN"],bgh=T["C_RED_H"],bgp=T["C_RED_P"],
            fg=T["C_TEXT_DIM"],font=(T["FN"][0],11,"bold"),fbg=bbg).pack(side="left")

        self._refs[idx]={"tv":tv,"wv":wv,"active":active}

        if exp: self._detail(idx,proj)

    def _detail(self, idx, proj):
        panel=tk.Frame(self._lf,bg=T["C_EXP_BG"]); panel.pack(fill="x")
        tk.Frame(self._lf,bg=T["C_BORDER"],height=1).pack(fill="x")
        breakdown=daily(proj)
        if not breakdown:
            tk.Label(panel,text="No sessions yet.",fg=T["C_TEXT_DIM"],
                     bg=T["C_EXP_BG"],font=T["FS"],pady=8,padx=20).pack(anchor="w")
            return
        hf=tk.Frame(panel,bg=T["C_EXP_BG"],padx=20,pady=6); hf.pack(fill="x")
        tk.Label(hf,text="",bg=T["C_EXP_BG"],width=2).pack(side="left")
        tk.Label(hf,text="Date",fg=T["C_TEXT_DIM"],bg=T["C_EXP_BG"],
                 font=T["FT"],width=22,anchor="w").pack(side="left")
        tk.Label(hf,text="Time worked",fg=T["C_TEXT_DIM"],bg=T["C_EXP_BG"],
                 font=T["FT"],anchor="w").pack(side="left",padx=(30,0))
        tk.Frame(panel,bg=T["C_BORDER"],height=1).pack(fill="x",padx=20)
        today=breakdown[0][0] if breakdown else None
        for day_dt,secs in breakdown:
            is_today=day_dt==today; worked=secs>0
            dot_col=T["C_GREEN"] if worked else T["C_RED_LED"]
            date_str=day_dt.strftime("%Y-%m-%d")+(" (today)" if is_today else "")
            time_str=fmt_hms(secs) if worked else "—"
            date_fg=T["C_TEXT"] if is_today else T["C_TEXT_DIM"]
            time_fg=T["C_ACCENT"] if worked else T["C_TEXT_DIM"]
            rfont=(T["FS"][0],9,"bold") if is_today else T["FT"]
            r=tk.Frame(panel,bg=T["C_EXP_BG"],padx=20,pady=2); r.pack(fill="x")
            make_led(r,dot_col,size=9,bg=T["C_EXP_BG"]).pack(side="left",padx=(0,10),pady=3)
            tk.Label(r,text=date_str,fg=date_fg,bg=T["C_EXP_BG"],
                     font=rfont,width=22,anchor="w").pack(side="left")
            tk.Label(r,text=time_str,fg=time_fg,bg=T["C_EXP_BG"],
                     font=rfont,anchor="w").pack(side="left",padx=(30,0))
        tk.Frame(panel,bg=T["C_EXP_BG"],height=6).pack()

    # ── Tick ─────────────────────────────────────────────────────────────────

    def _tick(self):
        for idx,refs in self._refs.items():
            if idx>=len(self.projects): continue
            proj=self.projects[idx]
            if refs["active"]:
                refs["tv"].set(ago(proj))
                ws=week_sec(proj); refs["wv"].set(fmt_hms(ws) if ws>0 else "—")
        self.after(1000,self._tick)

    # ── Actions ──────────────────────────────────────────────────────────────

    def _open_settings(self):
        SettingsDialog(self, dict(self._settings), self._apply_settings)

    def _toggle(self,i):
        if i in self._expanded: self._expanded.discard(i)
        else: self._expanded.add(i)
        self._render()

    def _start(self,i):
        self.projects[i]["session_start"]=time.time()
        save_data(self.projects); self._render()

    def _end(self,i):
        proj=self.projects[i]; ss=proj.get("session_start")
        if ss is None: return
        now=time.time()
        proj.setdefault("sessions",[]).append({"start":ss,"end":now})
        proj["last_worked"]=now; proj["session_start"]=None
        save_data(self.projects); self._render()

    def _add(self):
        dlg=AskDialog(self)
        if dlg.result and dlg.result.strip():
            self.projects.append({"name":dlg.result.strip(),
                                  "last_worked":None,"session_start":None,"sessions":[]})
            save_data(self.projects); self._render()

    def _delete(self,i):
        if self.projects[i].get("session_start"): self._end(i)
        dlg=ConfirmDialog(self,f"Delete \"{self.projects[i]['name']}\"?")
        if dlg.result:
            self._expanded.discard(i)
            self._expanded={x-1 if x>i else x for x in self._expanded}
            self.projects.pop(i)
            save_data(self.projects); self._render()


if __name__ == "__main__":
    app = Tracker()
    app.mainloop()
