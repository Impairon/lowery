"""
╔─────────────────────────────────╗
│ L O W E R YOUR G A Z E YADD 🫵  │
╚─────────────────────────────────╝

Run:
    python lower_gaze.py

Requires (install once):
    pip install pystray pillow

Panel:
  ×   quit everything
  ◑   toggle all screens on / off
  +   spawn a black screen (always visible)
  −   remove the last screen

Each black screen:
  drag body          → move
  drag any edge/corner → resize  (window stays still)
  hover              → × button appears (clear red)
  click ×            → close that screen

Tray icon (Windows taskbar):
  left-click         → show / hide panel
  right-click        → Show/Hide | Quit

  # Heavily Vibe Coded
  
"""

import tkinter as tk
import threading
import sys

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFilter
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False
    print("[LowerGaze] pip install pystray pillow  →  enables tray icon")


# ══════════════════════════════════════════════════════════════════
#  CUSTOMISE HERE — all sizes, colours, fonts in one place
# ══════════════════════════════════════════════════════════════════

# ── Panel colours ─────────────────────────────────────────────────
PANEL_BG       = "#1A1A1A"
PANEL_BORDER   = "#2F2F2F"
PANEL_HANDLE   = "#2C2C2C"
BTN_IDLE       = "#1A1A1A"
BTN_HOVER      = "#2C2C2C"
BTN_PRESS      = "#0E0E0E"

C_QUIT         = "#E84545"
C_TOGGLE       = "#4ECDC4"
C_ADD          = "#FF8C42"
C_REMOVE       = "#666666"

# ── Panel size & behaviour ────────────────────────────────────────
PANEL_W        = 44
PANEL_H        = 192
PANEL_RADIUS   = 18
PANEL_PADDING  = 8
PANEL_ALPHA    = 0.96
SNAP_PX        = 44
HANDLE_H       = 8

# ── Panel font ────────────────────────────────────────────────────
BTN_FONT       = ("Segoe UI Symbol", 14, "bold")

# ── Overlay (black screen) ────────────────────────────────────────
OV_COLOR       = "#333333"
OV_ALPHA       = 1.0
OV_DEFAULT_W   = 320
OV_DEFAULT_H   = 200
OV_MIN_W       = 60
OV_MIN_H       = 40
OV_CORNER_RADIUS = 15
OV_RESIZE_BORDER = 10

# ── Overlay × button ─────────────────────────────────────────────
OV_CLOSE_BG    = "#E84545"
OV_CLOSE_FG    = "#FFFFFF"
OV_CLOSE_SIZE  = 22
OV_CLOSE_FONT  = ("Segoe UI", 14, "bold")

# ── Tray icon (haram blur style) ──────────────────────────────────
TRAY_BG        = "#1A1A1A"
TRAY_BORDER    = "#4ECDC4"
TRAY_DOT       = "#E84545"

# ══════════════════════════════════════════════════════════════════
#  END CUSTOMISE BLOCK
# ══════════════════════════════════════════════════════════════════

overlays: list       = []
overlays_visible     = True


def screen_wh(root):
    return root.winfo_screenwidth(), root.winfo_screenheight()


class Overlay:
    def __init__(self, root):
        self.root = root
        win = tk.Toplevel(root)
        self.win = win

        win.geometry(f"{OV_DEFAULT_W}x{OV_DEFAULT_H}+260+260")
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", OV_ALPHA)

        TRANSPARENT_COLOR = "magenta"
        win.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        win.configure(bg=TRANSPARENT_COLOR)

        canvas = tk.Canvas(win, bg=TRANSPARENT_COLOR,
                           highlightthickness=0, borderwidth=0)
        canvas.pack(fill="both", expand=True)
        self.canvas = canvas

        self._bg_items = []
        self._current_cursor = None
        self._gesture = None
        self._edges = set()

        self._anc_x = self._anc_y = 0
        self._anc_w = self._anc_h = 0
        self._anc_mx = self._anc_my = 0

        self._draw_rounded_bg()

        # create close button (hidden) – top‑left corner
        r = OV_CLOSE_SIZE // 2
        cx, cy = OV_CORNER_RADIUS + r, OV_CORNER_RADIUS + r
        self._create_close_button(cx, cy, r)

        # Canvas bindings for interaction
        canvas.bind("<ButtonPress-1>",   self._on_press)
        canvas.bind("<B1-Motion>",       self._on_move)
        canvas.bind("<ButtonRelease-1>", self._on_release)

        # Motion tracking for cursor feedback only
        canvas.bind("<Motion>",          self._on_motion_track)

        # Redraw rounded shape on resize
        canvas.bind("<Configure>",       self._on_configure)

        # 🔁 Reliable hover detection via polling (fixes transparent‑color issue)
        self._hover_after_id = None
        self._start_hover_poll()

    def _start_hover_poll(self):
        self._poll_hover()
        self._hover_after_id = self.win.after(100, self._start_hover_poll)

    def _poll_hover(self):
        """Show/hide the close button based on cursor position."""
        try:
            wx, wy = self.win.winfo_rootx(), self.win.winfo_rooty()
            ww, wh = self.win.winfo_width(), self.win.winfo_height()
            mx, my = self.win.winfo_pointerx(), self.win.winfo_pointery()
            inside = wx <= mx <= wx+ww and wy <= my <= wy+wh
        except Exception:
            inside = False

        if hasattr(self, '_circle') and hasattr(self, '_cross'):
            state = "normal" if inside else "hidden"
            self.canvas.itemconfigure(self._circle, state=state)
            self.canvas.itemconfigure(self._cross, state=state)

    def _draw_rounded_bg(self, event=None):
        canvas = self.canvas
        for item in self._bg_items:
            canvas.delete(item)
        self._bg_items.clear()

        w = canvas.winfo_width()
        h = canvas.winfo_height()
        r = OV_CORNER_RADIUS
        c = OV_COLOR

        if w <= 2 * r or h <= 2 * r:
            rect = canvas.create_rectangle(0, 0, w, h, fill=c, outline="")
            self._bg_items.append(rect)
            return

        arc_tl = canvas.create_arc(0, 0, 2*r, 2*r, start=90, extent=90,
                                   style="pieslice", outline="", fill=c)
        arc_tr = canvas.create_arc(w-2*r, 0, w, 2*r, start=0, extent=90,
                                   style="pieslice", outline="", fill=c)
        arc_br = canvas.create_arc(w-2*r, h-2*r, w, h, start=270, extent=90,
                                   style="pieslice", outline="", fill=c)
        arc_bl = canvas.create_arc(0, h-2*r, 2*r, h, start=180, extent=90,
                                   style="pieslice", outline="", fill=c)
        rtop = canvas.create_rectangle(r, 0, w-r, r, fill=c, outline="")
        rbot = canvas.create_rectangle(r, h-r, w-r, h, fill=c, outline="")
        rlef = canvas.create_rectangle(0, r, r, h-r, fill=c, outline="")
        rrig = canvas.create_rectangle(w-r, r, w, h-r, fill=c, outline="")
        rmid = canvas.create_rectangle(r, r, w-r, h-r, fill=c, outline="")

        self._bg_items.extend([arc_tl, arc_tr, arc_br, arc_bl,
                               rtop, rbot, rlef, rrig, rmid])

    def _create_close_button(self, cx, cy, r):
        canvas = self.canvas
        self._circle = canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                          fill=OV_CLOSE_BG, outline="",
                                          state="hidden")
        self._cross = canvas.create_text(cx, cy, text="×",
                                         fill=OV_CLOSE_FG, font=OV_CLOSE_FONT,
                                         state="hidden")
        canvas.tag_bind(self._circle, "<Button-1>", lambda e: self.destroy())
        canvas.tag_bind(self._cross, "<Button-1>", lambda e: self.destroy())

    def _on_motion_track(self, e):
        # Cursor feedback only (resize arrows)
        if self._gesture is None:
            self._on_motion_passive(e)

    def _on_motion_passive(self, e):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        b = OV_RESIZE_BORDER
        x, y = e.x, e.y

        edges = set()
        if x <= b: edges.add("w")
        if x >= w - b: edges.add("e")
        if y <= b: edges.add("n")
        if y >= h - b: edges.add("s")
        if "w" in edges and "e" in edges:
            edges.discard("w")
            edges.discard("e")
        if "n" in edges and "s" in edges:
            edges.discard("n")
            edges.discard("s")

        cur = ""
        if edges == {"w"}:
            cur = "sb_h_double_arrow"
        elif edges == {"e"}:
            cur = "sb_h_double_arrow"
        elif edges == {"n"}:
            cur = "sb_v_double_arrow"
        elif edges == {"s"}:
            cur = "sb_v_double_arrow"
        elif edges == {"n", "w"}:
            cur = "size_nw_se"
        elif edges == {"n", "e"}:
            cur = "size_ne_sw"
        elif edges == {"s", "w"}:
            cur = "size_ne_sw"
        elif edges == {"s", "e"}:
            cur = "size_nw_se"
        else:
            cur = "arrow"

        if self._current_cursor != cur:
            self.canvas.config(cursor=cur)
            self._current_cursor = cur

    def _on_press(self, e):
        # avoid triggering on the close button area
        r = OV_CLOSE_SIZE // 2
        if e.x < OV_CORNER_RADIUS + 2*r and e.y < OV_CORNER_RADIUS + 2*r:
            return

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        b = OV_RESIZE_BORDER

        edges = set()
        if e.x <= b: edges.add("w")
        if e.x >= w - b: edges.add("e")
        if e.y <= b: edges.add("n")
        if e.y >= h - b: edges.add("s")
        if "w" in edges and "e" in edges:
            edges.discard("w")
            edges.discard("e")
        if "n" in edges and "s" in edges:
            edges.discard("n")
            edges.discard("s")

        if edges:
            self._gesture = "resize"
            self._edges = edges
            self._anc_x = self.win.winfo_x()
            self._anc_y = self.win.winfo_y()
            self._anc_w = self.win.winfo_width()
            self._anc_h = self.win.winfo_height()
            self._anc_mx = e.x_root
            self._anc_my = e.y_root
        else:
            self._gesture = "move"
            self._ox = e.x_root - self.win.winfo_x()
            self._oy = e.y_root - self.win.winfo_y()

    def _on_move(self, e):
        if self._gesture == "move":
            self.win.geometry(f"+{e.x_root - self._ox}+{e.y_root - self._oy}")
        elif self._gesture == "resize":
            delta_x = e.x_root - self._anc_mx
            delta_y = e.y_root - self._anc_my
            new_x, new_y = self._anc_x, self._anc_y
            new_w, new_h = self._anc_w, self._anc_h

            if "w" in self._edges:
                new_x = self._anc_x + delta_x
                new_w = self._anc_w - delta_x
                if new_w < OV_MIN_W:
                    new_w = OV_MIN_W
                    new_x = self._anc_x + self._anc_w - OV_MIN_W
            if "e" in self._edges:
                new_w = self._anc_w + delta_x
                if new_w < OV_MIN_W:
                    new_w = OV_MIN_W
            if "n" in self._edges:
                new_y = self._anc_y + delta_y
                new_h = self._anc_h - delta_y
                if new_h < OV_MIN_H:
                    new_h = OV_MIN_H
                    new_y = self._anc_y + self._anc_h - OV_MIN_H
            if "s" in self._edges:
                new_h = self._anc_h + delta_y
                if new_h < OV_MIN_H:
                    new_h = OV_MIN_H

            self.win.geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")

    def _on_release(self, e):
        self._gesture = None
        self._edges.clear()
        self._on_motion_passive(e)

    def _on_configure(self, event):
        self._draw_rounded_bg()

    def show(self):
        self.win.deiconify()
    def hide(self):
        self.win.withdraw()
    def destroy(self):
        if self in overlays: overlays.remove(self)
        if self._hover_after_id:
            self.win.after_cancel(self._hover_after_id)
        self.win.destroy()


class ControlPanel:
    _VERT  = "v"
    _HORIZ = "h"

    def __init__(self):
        self.root = tk.Tk()
        r = self.root
        r.title("Lower Gaze")

        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.attributes("-alpha", PANEL_ALPHA)
        r.resizable(False, False)

        self._TRANSPARENT = "magenta"
        r.wm_attributes("-transparentcolor", self._TRANSPARENT)
        r.configure(bg=self._TRANSPARENT)

        self._canvas = tk.Canvas(r, bg=self._TRANSPARENT,
                                 highlightthickness=0, borderwidth=0)
        self._canvas.pack(fill="both", expand=True)

        self._orient = self._VERT
        self._dragging = False
        self._btn_items = []
        self._handle_id = None

        sw, _ = screen_wh(r)
        pw, ph = self._total_dims()
        r.geometry(f"{pw}x{ph}+{sw - pw}+180")

        self._build_ui(self._VERT)

        r.protocol("WM_DELETE_WINDOW", self.quit)
        if HAS_TRAY:
            self._start_tray()
        r.mainloop()

    def _total_dims(self):
        if self._orient == self._VERT:
            return PANEL_W + 2 * PANEL_PADDING, PANEL_H + 2 * PANEL_PADDING + HANDLE_H
        else:
            return PANEL_H + 2 * PANEL_PADDING, PANEL_W + 2 * PANEL_PADDING + HANDLE_H

    def _snap(self):
        r = self.root
        sw, sh = screen_wh(r)
        x, y = r.winfo_x(), r.winfo_y()
        pw, ph = r.winfo_width(), r.winfo_height()

        if x <= SNAP_PX:
            self._apply("left",   0,            y)
        elif x + pw >= sw - SNAP_PX:
            self._apply("right",  sw - pw,      y)
        elif y <= SNAP_PX:
            self._apply("top",    x,            0)
        elif y + ph >= sh - SNAP_PX:
            self._apply("bottom", x,            sh - ph)
        else:
            self._apply("free",   x,            y)

    def _apply(self, edge, x, y):
        if edge in ("top", "bottom"):
            new_orient = self._HORIZ
        else:
            new_orient = self._VERT
        if new_orient != self._orient:
            self._build_ui(new_orient)
        pw, ph = self._total_dims()
        self.root.geometry(f"{pw}x{ph}+{x}+{y}")

    def _draw_pill_background(self, canvas, x1, y1, x2, y2, r):
        c = canvas
        for item in getattr(self, '_pill_items', []):
            c.delete(item)
        items = []

        w, h = x2 - x1, y2 - y1
        if w <= 2*r or h <= 2*r:
            rect = c.create_rectangle(x1, y1, x2, y2, fill=PANEL_BG, outline=PANEL_BORDER, width=1)
            items.append(rect)
        else:
            arc_tl = c.create_arc(x1, y1, x1+2*r, y1+2*r, start=90, extent=90,
                                  style="pieslice", fill=PANEL_BG, outline="")
            arc_tr = c.create_arc(x2-2*r, y1, x2, y1+2*r, start=0, extent=90,
                                  style="pieslice", fill=PANEL_BG, outline="")
            arc_br = c.create_arc(x2-2*r, y2-2*r, x2, y2, start=270, extent=90,
                                  style="pieslice", fill=PANEL_BG, outline="")
            arc_bl = c.create_arc(x1, y2-2*r, x1+2*r, y2, start=180, extent=90,
                                  style="pieslice", fill=PANEL_BG, outline="")
            r_top = c.create_rectangle(x1+r, y1, x2-r, y1+r, fill=PANEL_BG, outline="")
            r_bot = c.create_rectangle(x1+r, y2-r, x2-r, y2, fill=PANEL_BG, outline="")
            r_lef = c.create_rectangle(x1, y1+r, x1+r, y2-r, fill=PANEL_BG, outline="")
            r_rig = c.create_rectangle(x2-r, y1+r, x2, y2-r, fill=PANEL_BG, outline="")
            r_mid = c.create_rectangle(x1+r, y1+r, x2-r, y2-r, fill=PANEL_BG, outline="")
            items.extend([arc_tl, arc_tr, arc_br, arc_bl, r_top, r_bot, r_lef, r_rig, r_mid])
            border = c.create_rectangle(x1, y1, x2, y2, outline=PANEL_BORDER, width=1)
            items.append(border)

        self._pill_items = items

    def _build_ui(self, orient):
        self._orient = orient
        c = self._canvas
        c.delete("all")
        self._btn_items.clear()

        w, h = self._total_dims()
        pad = PANEL_PADDING

        self._draw_pill_background(c, pad, pad, w-pad, h-pad, PANEL_RADIUS)

        # drag handle
        handle_y1 = pad
        handle_y2 = pad + HANDLE_H
        handle_rect = c.create_rectangle(pad, handle_y1, w-pad, handle_y2,
                                        fill=PANEL_HANDLE, outline="")
        self._handle_id = handle_rect
        c.tag_bind(handle_rect, "<ButtonPress-1>",   self._drag_start)
        c.tag_bind(handle_rect, "<B1-Motion>",       self._drag_move)
        c.tag_bind(handle_rect, "<ButtonRelease-1>",  self._drag_end)

        interior_top = pad + HANDLE_H
        if orient == self._VERT:
            btn_w = PANEL_W
            btn_h = (PANEL_H - 3 * 2) // 4
            spacing = 2
            x_center = w // 2
            for i, (text, fg, cmd) in enumerate([
                ("×", C_QUIT, self.quit),
                ("◑", C_TOGGLE, self._toggle_overlays),
                ("+", C_ADD, self._add_overlay),
                ("−", C_REMOVE, self._remove_last),
            ]):
                y_center = interior_top + i * (btn_h + spacing) + btn_h // 2
                self._place_button(x_center, y_center, btn_w, btn_h, text, fg, cmd)
        else:
            btn_h = PANEL_W
            btn_w = (PANEL_H - 3 * 2) // 4
            spacing = 2
            y_center = (h - interior_top) // 2 + interior_top
            for i, (text, fg, cmd) in enumerate([
                ("×", C_QUIT, self.quit),
                ("◑", C_TOGGLE, self._toggle_overlays),
                ("+", C_ADD, self._add_overlay),
                ("−", C_REMOVE, self._remove_last),
            ]):
                x_center = pad + i * (btn_w + spacing) + btn_w // 2
                self._place_button(x_center, y_center, btn_w, btn_h, text, fg, cmd)

        self._toggle_label = None
        self._toggle_var = tk.StringVar(value="◑")

    def _place_button(self, cx, cy, w, h, text, fg, cmd):
        c = self._canvas
        btn_frame = tk.Frame(c, bg=PANEL_BG, width=w, height=h)
        btn_frame.pack_propagate(False)
        lbl = tk.Label(btn_frame, text=text, bg=BTN_IDLE, fg=fg,
                       font=BTN_FONT, cursor="hand2")
        lbl.pack(fill="both", expand=True)

        wid = c.create_window(cx, cy, window=btn_frame, width=w, height=h)
        self._btn_items.append(wid)

        def on_press(e):
            lbl.configure(bg=BTN_PRESS)
            return "break"

        def on_release(e):
            lbl.configure(bg=BTN_HOVER)
            cmd()
            return "break"

        lbl.bind("<ButtonPress-1>", on_press)
        lbl.bind("<ButtonRelease-1>", on_release)
        lbl.bind("<Enter>", lambda e: lbl.configure(bg=BTN_HOVER))
        lbl.bind("<Leave>", lambda e: lbl.configure(bg=BTN_IDLE))

        if text == "◑":
            self._toggle_label = lbl
            self._toggle_var = tk.StringVar(value="◑")
            lbl.configure(textvariable=self._toggle_var)
            def toggle_callback():
                self._toggle_overlays()
                self._toggle_var.set("◑" if overlays_visible else "○")
            lbl.unbind("<ButtonRelease-1>")
            lbl.bind("<ButtonRelease-1>", lambda e: (lbl.configure(bg=BTN_HOVER), toggle_callback(), "break"))

    def _drag_start(self, e):
        self._ox = e.x_root - self.root.winfo_x()
        self._oy = e.y_root - self.root.winfo_y()
        self._dragging = False

    def _drag_move(self, e):
        self._dragging = True
        self.root.geometry(f"+{e.x_root - self._ox}+{e.y_root - self._oy}")

    def _drag_end(self, e):
        if self._dragging:
            self._snap()
        self._dragging = False

    def _add_overlay(self):
        ov = Overlay(self.root)
        overlays.append(ov)
        # New overlays always visible – toggle only affects existing ones

    def _remove_last(self):
        if overlays:
            overlays[-1].destroy()

    def _toggle_overlays(self):
        global overlays_visible
        overlays_visible = not overlays_visible
        for ov in overlays:
            ov.show() if overlays_visible else ov.hide()

    def _start_tray(self):
        img  = self._make_icon()
        menu = pystray.Menu(
            pystray.MenuItem("Show / Hide", self._tray_toggle, default=True),
            pystray.MenuItem("Quit",        self._tray_quit),
        )
        self.tray = pystray.Icon("LowerGaze", img, "Lower Gaze", menu)
        threading.Thread(target=self.tray.run, daemon=True).start()

    def _make_icon(self):
        """Haram blur style: dark pill with coloured bars + glow."""
        sz = 72
        img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Outer glow
        glow = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.rounded_rectangle([4, 4, sz-4, sz-4], radius=16,
                             fill=(0, 0, 0, 0), outline=(100, 200, 200, 180), width=4)
        glow = glow.filter(ImageFilter.GaussianBlur(radius=4))
        img.paste(glow, (0, 0), glow)

        # Dark pill background
        draw.rounded_rectangle([6, 6, sz-6, sz-6], radius=14, fill=TRAY_BG)

        # Coloured bars
        bars = ["#E84545", "#FF8C42", "#F5E03A", "#7BE07B", "#4ECDC4", "#6EB5FF"]
        bar_w = 6
        total_w = len(bars) * bar_w + (len(bars)-1)*2
        x0 = (sz - total_w) // 2
        y_top = 18
        y_bot = 44
        for col in bars:
            draw.rectangle([x0, y_top, x0+bar_w, y_bot], fill=col)
            x0 += bar_w + 2

        # Red dot
        draw.ellipse([28, 46, 44, 62], fill=TRAY_DOT)

        return img

    def _tray_toggle(self, *_):
        r = self.root
        if r.winfo_viewable():
            r.after(0, r.withdraw)
        else:
            r.after(0, lambda: (r.deiconify(), r.lift()))

    def _tray_quit(self, *_):
        self.root.after(0, self.quit)

    def quit(self):
        for ov in overlays[:]:
            ov.destroy()
        if HAS_TRAY and hasattr(self, "tray"):
            self.tray.stop()
        self.root.destroy()
        sys.exit(0)


if __name__ == "__main__":
    ControlPanel()
