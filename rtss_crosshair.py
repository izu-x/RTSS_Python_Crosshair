#!/usr/bin/env python3
"""RTSS Crosshair - Python port. No compiler, no dependencies, just Python."""

import sys
import ctypes
import ctypes.wintypes
import threading
import tkinter as tk
from tkinter import colorchooser, ttk
import winreg

if sys.platform != "win32":
    sys.exit("This program requires Windows with RivaTuner Statistics Server running.")

# ── Win32 API bindings ────────────────────────────────────────────────────

FILE_MAP_ALL_ACCESS = 0x000F001F

VK_LEFT, VK_UP, VK_RIGHT, VK_DOWN = 0x25, 0x26, 0x27, 0x28
VK_RCONTROL = 0xA3
VK_RSHIFT   = 0xA1
VK_NUMPAD0, VK_NUMPAD2, VK_NUMPAD4, VK_NUMPAD5 = 0x60, 0x62, 0x64, 0x65
VK_NUMPAD6, VK_NUMPAD8 = 0x66, 0x68
VK_DECIMAL, VK_ADD, VK_SUBTRACT = 0x6E, 0x6B, 0x6D
VK_OEM_PERIOD, VK_OEM_PLUS, VK_OEM_MINUS = 0xBE, 0xBB, 0xBD
VK_0, VK_5 = 0x30, 0x35
SM_CXSCREEN, SM_CYSCREEN = 0, 1

# ── RTSS shared memory structures ────────────────────────────────────────

class RECT(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]

class RTSS_SHARED_MEMORY_OSD_ENTRY(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("szOSD", ctypes.c_char * 256),
        ("szOSDOwner", ctypes.c_char * 256),
        ("szOSDEx", ctypes.c_char * 4096),
    ]

class RTSS_SHARED_MEMORY(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("dwSignature", ctypes.c_uint32),
        ("dwVersion", ctypes.c_uint32),
        ("dwAppEntrySize", ctypes.c_uint32),
        ("dwAppArrOffset", ctypes.c_uint32),
        ("dwAppArrSize", ctypes.c_uint32),
        ("dwOSDEntrySize", ctypes.c_uint32),
        ("dwOSDArrOffset", ctypes.c_uint32),
        ("dwOSDArrSize", ctypes.c_uint32),
        ("dwOSDFrame", ctypes.c_uint32),
        ("dwBusy", ctypes.c_int32),
    ]

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32   = ctypes.WinDLL("user32", use_last_error=True)

kernel32.OpenFileMappingW.restype = ctypes.wintypes.HANDLE
kernel32.OpenFileMappingW.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_wchar_p]
kernel32.MapViewOfFile.restype = ctypes.c_void_p
kernel32.MapViewOfFile.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_size_t]
kernel32.UnmapViewOfFile.restype = ctypes.c_bool
kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
kernel32.CloseHandle.restype = ctypes.c_bool
kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]

user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetForegroundWindow.restype = ctypes.wintypes.HWND
user32.GetForegroundWindow.argtypes = []
user32.GetClientRect.restype = ctypes.wintypes.BOOL
user32.GetClientRect.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.GetSystemMetrics.argtypes = [ctypes.c_int]

# ── Helpers ──────────────────────────────────────────────────────────────

def _smem_base(p_mem_ptr):
    """Return integer base address of the shared memory region."""
    return ctypes.cast(p_mem_ptr, ctypes.c_void_p).value or 0

def _dwBusy_ptr(p_mem_ptr):
    """Return pointer to the dwBusy field in shared memory."""
    base = _smem_base(p_mem_ptr)
    off = RTSS_SHARED_MEMORY.dwBusy.offset
    return ctypes.cast(ctypes.c_void_p(base + off), ctypes.POINTER(ctypes.c_int32))

def _entry_ptr(p_mem_ptr, i):
    """Return pointer to the i-th OSD entry in shared memory."""
    base = _smem_base(p_mem_ptr)
    return ctypes.cast(
        ctypes.c_void_p(base + p_mem_ptr.contents.dwOSDArrOffset
                        + i * p_mem_ptr.contents.dwOSDEntrySize),
        ctypes.POINTER(RTSS_SHARED_MEMORY_OSD_ENTRY))

def key_down(vk_code):
    return (user32.GetAsyncKeyState(vk_code) & 0x8000) != 0


def _osd_lock(p_mem_ptr):
    """Non-blocking try-lock of RTSS OSD busy flag. Returns True if acquired."""
    busy = _dwBusy_ptr(p_mem_ptr)
    if busy.contents.value == 0:
        busy.contents.value = 1
        return True
    return False


def _osd_unlock(p_mem_ptr):
    _dwBusy_ptr(p_mem_ptr).contents.value = 0


def update_osd(text: str, map_name: str) -> bool:
    h_map = kernel32.OpenFileMappingW(FILE_MAP_ALL_ACCESS, False, "RTSSSharedMemoryV2")
    if not h_map:
        return False

    result = False
    try:
        p_addr = kernel32.MapViewOfFile(h_map, FILE_MAP_ALL_ACCESS, 0, 0, 0)
        if not p_addr:
            return False
        try:
            p_mem_ptr = ctypes.cast(p_addr, ctypes.POINTER(RTSS_SHARED_MEMORY))
            p_mem = p_mem_ptr.contents
            if p_mem.dwSignature != 0x52545353 or p_mem.dwVersion < 0x00020000:
                return False

            text_bytes = text.encode("ascii", errors="replace")
            name_bytes = map_name.encode("ascii")
            entry_count = p_mem.dwOSDArrSize

            for dw_pass in range(2):
                for i in range(1, entry_count):
                    p_entry = _entry_ptr(p_mem_ptr, i)
                    e = p_entry.contents

                    if dw_pass:
                        sz = bytes(e.szOSDOwner).split(b"\x00")[0]
                        if not sz:
                            n = min(len(name_bytes), 255)
                            padded = name_bytes[:n] + b'\x00'
                            owner_addr = ctypes.cast(p_entry, ctypes.c_void_p).value + RTSS_SHARED_MEMORY_OSD_ENTRY.szOSDOwner.offset
                            ctypes.memmove(ctypes.c_void_p(owner_addr), padded, n + 1)

                    owner = bytes(e.szOSDOwner).split(b"\x00")[0].decode("ascii", errors="ignore")
                    if owner != map_name:
                        continue

                    # helpers for direct memory writes
                    entry_base = ctypes.cast(p_entry, ctypes.c_void_p).value
                    def _write_osd_ex(data):
                        addr = entry_base + RTSS_SHARED_MEMORY_OSD_ENTRY.szOSDEx.offset
                        ctypes.memmove(ctypes.c_void_p(addr), data, len(data))
                    def _write_osd(data):
                        addr = entry_base + RTSS_SHARED_MEMORY_OSD_ENTRY.szOSD.offset
                        ctypes.memmove(ctypes.c_void_p(addr), data, len(data))
                    def _inc_frame():
                        smem_base = ctypes.cast(p_mem_ptr, ctypes.c_void_p).value
                        frame_addr = smem_base + RTSS_SHARED_MEMORY.dwOSDFrame.offset
                        ctypes.c_uint32.from_address(frame_addr).value += 1

                    if p_mem.dwVersion >= 0x00020007:
                        if p_mem.dwVersion >= 0x0002000E:
                            if _osd_lock(p_mem_ptr):
                                ml = 4095
                                n = min(len(text_bytes), ml)
                                padded = text_bytes[:n] + b'\x00'
                                _write_osd_ex(padded)
                                _osd_unlock(p_mem_ptr)
                                _inc_frame()
                                result = True
                        else:
                            ml = 4095
                            n = min(len(text_bytes), ml)
                            padded = text_bytes[:n] + b'\x00'
                            _write_osd_ex(padded)
                            _inc_frame()
                            result = True
                    else:
                        ml = 255
                        n = min(len(text_bytes), ml)
                        padded = text_bytes[:n] + b'\x00'
                        _write_osd(padded)
                        _inc_frame()
                        result = True
                    break
                if result:
                    break
        finally:
            kernel32.UnmapViewOfFile(p_addr)
    finally:
        kernel32.CloseHandle(h_map)
    return result


def release_osd(map_name: str):
    h_map = kernel32.OpenFileMappingW(FILE_MAP_ALL_ACCESS, False, "RTSSSharedMemoryV2")
    if not h_map:
        return
    try:
        p_addr = kernel32.MapViewOfFile(h_map, FILE_MAP_ALL_ACCESS, 0, 0, 0)
        if not p_addr:
            return
        try:
            p_mem_ptr = ctypes.cast(p_addr, ctypes.POINTER(RTSS_SHARED_MEMORY))
            p_mem = p_mem_ptr.contents
            if p_mem.dwSignature != 0x52545353 or p_mem.dwVersion < 0x00020000:
                return

            entry_count = p_mem.dwOSDArrSize
            entry_stride = p_mem.dwOSDEntrySize

            for i in range(1, entry_count):
                p_entry = _entry_ptr(p_mem_ptr, i)
                owner = p_entry.contents.szOSDOwner[:].split(b"\x00")[0].decode("ascii", errors="ignore")
                if owner == map_name:
                    buf_addr = ctypes.cast(p_entry, ctypes.c_void_p).value
                    ctypes.memset(buf_addr, 0, entry_stride)
                    smem_base = ctypes.cast(p_mem_ptr, ctypes.c_void_p).value
                    frame_addr = smem_base + RTSS_SHARED_MEMORY.dwOSDFrame.offset
                    ctypes.c_uint32.from_address(frame_addr).value += 1
        finally:
            kernel32.UnmapViewOfFile(p_addr)
    finally:
        kernel32.CloseHandle(h_map)


# ── Registry helpers ──────────────────────────────────────────────────────

REG_KEY = r"Software\RTSS_Crosshair"


def reg_load():
    x, y, sz, ch, col = 0.0, 0.0, 100, b"+", "FFFFFF"
    persist = 0
    visible = 1
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as key:
            try:
                v = winreg.QueryValueEx(key, "x_coord")[0]
                x = float(v) if isinstance(v, str) else float(v)
            except (FileNotFoundError, ValueError): pass
            try:
                v = winreg.QueryValueEx(key, "y_coord")[0]
                y = float(v) if isinstance(v, str) else float(v)
            except (FileNotFoundError, ValueError): pass
            try: sz = winreg.QueryValueEx(key, "size")[0]
            except FileNotFoundError: pass
            try:
                v = winreg.QueryValueEx(key, "char")[0]
                ch = v.encode("ascii", errors="replace") if isinstance(v, str) else v
            except FileNotFoundError: pass
            try:
                v = winreg.QueryValueEx(key, "color")[0]
                col = v if isinstance(v, str) else v.decode("ascii", errors="replace")
            except FileNotFoundError: pass
            try: persist = winreg.QueryValueEx(key, "persist")[0]
            except FileNotFoundError: pass
            try: visible = winreg.QueryValueEx(key, "visible")[0]
            except FileNotFoundError: pass
    except FileNotFoundError:
        pass
    return x, y, sz, ch, col, bool(persist), bool(visible)


def reg_save(x, y, sz, ch, col, persist, visible):
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY)
    except OSError:
        return
    with key:
        winreg.SetValueEx(key, "x_coord", 0, winreg.REG_SZ, str(float(x)))
        winreg.SetValueEx(key, "y_coord", 0, winreg.REG_SZ, str(float(y)))
        winreg.SetValueEx(key, "size",    0, winreg.REG_DWORD, int(sz))
        s = ch.decode("ascii", errors="replace") if isinstance(ch, bytes) else str(ch)
        winreg.SetValueEx(key, "char",    0, winreg.REG_SZ, s)
        winreg.SetValueEx(key, "color",   0, winreg.REG_SZ, str(col))
        winreg.SetValueEx(key, "persist", 0, winreg.REG_DWORD, int(bool(persist)))
        winreg.SetValueEx(key, "visible", 0, winreg.REG_DWORD, int(bool(visible)))


# ── Shared state ──────────────────────────────────────────────────────────

cross_x = 0.0
cross_y = 0.0
cross_size = 100
crosshair_char = b"+"
crosshair_color = "FFFFFF"

persist = False
visible = True
state_lock = threading.Lock()
change_flag = False


def _move(dx, dy):
    global cross_x, cross_y
    with state_lock:
        cross_x = round(cross_x + dx, 1)
        cross_y = round(cross_y + dy, 1)
    trigger_update()


def trigger_update():
    global change_flag
    with state_lock:
        change_flag = True


def apply_state():
    global change_flag
    with state_lock:
        if not change_flag:
            return
        change_flag = False
        x = cross_x
        y = cross_y
        s = cross_size
        ch = crosshair_char
        col = crosshair_color
        vis = visible

    ch_s = ch.decode("ascii", errors="replace") if isinstance(ch, bytes) else str(ch)
    xi, yi = int(round(x)), int(round(y))
    if vis:
        update_osd(f"<P={xi},{yi}><S={s}><C={col}>{ch_s}", "RTSS_Crosshair_Overlay")
    else:
        update_osd("", "RTSS_Crosshair_Overlay")
    update_osd("<P=0,0><S=100>", "RTSS_Crosshair_Placeholder")


# ── Button actions ────────────────────────────────────────────────────────

def do_move_left_50():  _move(-50, 0)
def do_move_right_50(): _move(50, 0)
def do_move_up_50():    _move(0, -50)
def do_move_down_50():  _move(0, 50)

def do_move_left_1():   _move(-1, 0)
def do_move_right_1():  _move(1, 0)
def do_move_up_1():     _move(0, -1)
def do_move_down_1():   _move(0, 1)

def do_move_left_01():  _move(-0.5, 0)
def do_move_right_01(): _move(0.5, 0)
def do_move_up_01():    _move(0, -0.5)
def do_move_down_01():  _move(0, 0.5)


def do_center():
    global cross_x, cross_y
    with state_lock:
        cross_x = user32.GetSystemMetrics(SM_CXSCREEN) / 2.0
        cross_y = user32.GetSystemMetrics(SM_CYSCREEN) / 2.0
    trigger_update()


def do_reset(reset_char: bool = False):
    global cross_x, cross_y, cross_size, crosshair_char
    with state_lock:
        cross_x = 0; cross_y = 0; cross_size = 100
        if reset_char:
            crosshair_char = b"+"
    trigger_update()
    return reset_char


def do_size_plus():
    global cross_size
    with state_lock: cross_size += 5
    trigger_update()


def do_size_minus():
    global cross_size
    with state_lock: cross_size -= 5
    trigger_update()


def do_save():
    global cross_x, cross_y, cross_size, crosshair_char, crosshair_color, persist, visible
    with state_lock:
        reg_save(cross_x, cross_y, cross_size, crosshair_char, crosshair_color, persist, visible)


def do_apply_char(new_ch: str):
    global crosshair_char
    with state_lock:
        crosshair_char = new_ch.encode("ascii", errors="replace")
    trigger_update()


def do_apply_color(new_col: str):
    global crosshair_color
    c = new_col.strip().upper()
    if len(c) == 6 and all(ch in "0123456789ABCDEF" for ch in c):
        with state_lock:
            crosshair_color = c
        trigger_update()


def do_toggle_visible():
    global visible
    with state_lock:
        visible = not visible
    trigger_update()
    return visible


def do_toggle_persist():
    global persist
    with state_lock:
        persist = not persist
    trigger_update()
    return persist


# ── Keyboard polling thread ───────────────────────────────────────────────

def keyboard_loop():
    global cross_x, cross_y, cross_size, change_flag
    while True:
        rc = key_down(VK_RCONTROL)
        rs = key_down(VK_RSHIFT)

        if rc and (key_down(VK_DECIMAL) or key_down(VK_OEM_PERIOD)):
            with state_lock:
                reg_save(cross_x, cross_y, cross_size, crosshair_char, crosshair_color, persist, visible)

        if rc and (key_down(VK_NUMPAD5) or key_down(VK_5)):
            with state_lock:
                cross_x = user32.GetSystemMetrics(SM_CXSCREEN) / 2.0
                cross_y = user32.GetSystemMetrics(SM_CYSCREEN) / 2.0
                change_flag = True

        if rc and (key_down(VK_NUMPAD0) or key_down(VK_0)):
            with state_lock:
                cross_x = 0.0; cross_y = 0.0; cross_size = 100
                change_flag = True

        if rs and (key_down(VK_NUMPAD4) or key_down(VK_LEFT)):
            with state_lock: cross_x -= 50.0; change_flag = True
        if rs and (key_down(VK_NUMPAD6) or key_down(VK_RIGHT)):
            with state_lock: cross_x += 50.0; change_flag = True
        if rs and (key_down(VK_NUMPAD8) or key_down(VK_UP)):
            with state_lock: cross_y -= 50.0; change_flag = True
        if rs and (key_down(VK_NUMPAD2) or key_down(VK_DOWN)):
            with state_lock: cross_y += 50.0; change_flag = True

        if rc and (key_down(VK_NUMPAD4) or key_down(VK_LEFT)):
            with state_lock: cross_x -= 1.0; change_flag = True
        if rc and (key_down(VK_NUMPAD6) or key_down(VK_RIGHT)):
            with state_lock: cross_x += 1.0; change_flag = True
        if rc and (key_down(VK_NUMPAD8) or key_down(VK_UP)):
            with state_lock: cross_y -= 1.0; change_flag = True
        if rc and (key_down(VK_NUMPAD2) or key_down(VK_DOWN)):
            with state_lock: cross_y += 1.0; change_flag = True

        if rc and (key_down(VK_ADD) or key_down(VK_OEM_PLUS)):
            with state_lock: cross_size += 5; change_flag = True
        if rc and (key_down(VK_SUBTRACT) or key_down(VK_OEM_MINUS)):
            with state_lock: cross_size -= 5; change_flag = True

        apply_state()
        threading.Event().wait(0.1)


# ── GUI ───────────────────────────────────────────────────────────────────

def build_gui():
    # ── Dark theme ──
    BG = "#2b2b2b"
    FG = "#e0e0e0"
    BG_FRAME = "#323232"
    BG_ENTRY = "#1e1e1e"
    BG_BTN = "#3c3c3c"
    BG_BTN_ACTIVE = "#505050"

    root = tk.Tk()
    root.title("RTSS Crosshair")
    root.resizable(False, False)
    root.configure(padx=8, pady=8, bg=BG)
    try:
        root.iconbitmap("icon.ico")
    except tk.TclError:
        pass

    # ttk dark style for Combobox
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TCombobox", fieldbackground=BG_ENTRY, background=BG_BTN, foreground=FG)
    style.map("TCombobox", fieldbackground=[("readonly", BG_ENTRY)])

    def dark_label(parent, text, **kw):
        kw.setdefault('bg', BG)
        kw.setdefault('fg', FG)
        return tk.Label(parent, text=text, **kw)

    def dark_button(parent, text, command, **kw):
        kw.setdefault('bg', BG_BTN)
        kw.setdefault('fg', FG)
        kw.setdefault('activebackground', BG_BTN_ACTIVE)
        kw.setdefault('activeforeground', FG)
        kw.setdefault('relief', 'flat')
        return tk.Button(parent, text=text, command=command, **kw)

    def dark_entry(parent, textvariable, **kw):
        kw.setdefault('bg', BG_ENTRY)
        kw.setdefault('fg', FG)
        kw.setdefault('insertbackground', FG)
        kw.setdefault('relief', 'flat')
        return tk.Entry(parent, textvariable=textvariable, **kw)

    def dark_check(parent, text, variable, command):
        return tk.Checkbutton(parent, text=text, variable=variable, command=command,
                              bg=BG, fg=FG, activebackground=BG, activeforeground=FG,
                              selectcolor=BG_ENTRY, relief="flat")

    def dark_labelframe(parent, text):
        return tk.LabelFrame(parent, text=text, bg=BG_FRAME, fg=FG, padx=6, pady=6,
                             bd=1, highlightbackground="#444", highlightthickness=1)

    # ── Live preview of the crosshair ──
    preview_frame = dark_labelframe(root, "Preview")
    preview_frame.pack(fill="x", pady=(0, 6))

    preview_lbl = tk.Label(
        preview_frame,
        text=crosshair_char.decode("ascii", errors="replace"),
        font=("Arial", 36),
        fg=f"#{crosshair_color}",
        bg=BG_FRAME,
        width=4, height=1,
    )
    preview_lbl.pack()

    def refresh_preview():
        preview_lbl.config(
            text=crosshair_char.decode("ascii", errors="replace"),
            fg=f"#{crosshair_color}",
        )
        root.after(200, refresh_preview)

    refresh_preview()

    # ── Style (char, color) ──
    style_frame = dark_labelframe(root, "Style")
    style_frame.pack(fill="x", pady=(0, 6))

    # Character
    dark_label(style_frame, text="Char:").grid(row=0, column=0, sticky="w")
    char_var = tk.StringVar(value=crosshair_char.decode("ascii", errors="replace"))
    char_entry = dark_entry(style_frame, char_var, justify="center", width=4)
    char_entry.grid(row=0, column=1, padx=(4, 0))
    dark_button(style_frame, text="Apply", command=lambda: do_apply_char(char_var.get()),
                width=6).grid(row=0, column=2, padx=(4, 0))

    # Color
    dark_label(style_frame, text="Color:").grid(row=1, column=0, sticky="w", pady=(4, 0))
    color_preview = tk.Label(style_frame, text="  ", bg=f"#{crosshair_color}",
                             relief="sunken", width=3, cursor="hand2")
    color_preview.grid(row=1, column=1, padx=(4, 0), pady=(4, 0))
    color_label = dark_label(style_frame, text=crosshair_color)
    color_label.grid(row=1, column=2, sticky="w", padx=(4, 0), pady=(4, 0))

    def pick_color():
        rgb, hex_str = colorchooser.askcolor(color=f"#{crosshair_color}", title="Pick crosshair color")
        if hex_str:
            c = hex_str.lstrip("#").upper()
            do_apply_color(c)
            color_preview.config(bg=f"#{c}")
            color_label.config(text=c)

    color_preview.bind("<Button-1>", lambda e: pick_color())
    color_label.bind("<Button-1>", lambda e: pick_color())

    # ── Position ──
    pos_frame = dark_labelframe(root, "Position")
    pos_frame.pack(fill="x", pady=(0, 6))

    # Coordinate display
    coord_lbl = dark_label(pos_frame, text=f"X: {int(round(cross_x))}   Y: {int(round(cross_y))}   Size: {cross_size}")
    coord_lbl.pack()

    def refresh_coord():
        coord_lbl.config(text=f"X: {int(round(cross_x))}   Y: {int(round(cross_y))}   Size: {cross_size}")
        root.after(100, refresh_coord)

    refresh_coord()

    # D-pad frame
    dpad = tk.Frame(pos_frame, bg=BG_FRAME)
    dpad.pack(pady=(6, 0))

    def mk_btn(parent, txt, cmd, rw, cl, csp=1):
        dark_button(parent, text=txt, command=cmd, width=6).grid(
            row=rw, column=cl, columnspan=csp, padx=2, pady=2)

    dark_label(dpad, text="Step:").grid(row=0, column=0, sticky="e")
    step_var = tk.StringVar(value="1 px")
    step_combo = ttk.Combobox(dpad, textvariable=step_var,
                               values=["0.5 px", "1 px", "50 px"],
                               state="readonly", width=8)
    step_combo.grid(row=0, column=1, columnspan=2, sticky="w", padx=2)

    def get_step():
        s = step_var.get()
        if s == "0.5 px":
            return 0.5
        elif s == "50 px":
            return 50
        return 1

    mk_btn(dpad, "↑", lambda: _move(0, -get_step()), 1, 1)
    mk_btn(dpad, "←", lambda: _move(-get_step(), 0), 2, 0)
    mk_btn(dpad, "Center", do_center, 2, 1)
    mk_btn(dpad, "→", lambda: _move(get_step(), 0), 2, 2)
    mk_btn(dpad, "↓", lambda: _move(0, get_step()), 3, 1)

    # Size controls
    size_frame = tk.Frame(pos_frame, bg=BG_FRAME)
    size_frame.pack(pady=(4, 0))
    dark_button(size_frame, text="Size -", command=do_size_minus, width=8).pack(side="left", padx=2)
    dark_button(size_frame, text="Size +", command=do_size_plus, width=8).pack(side="left", padx=2)

    # ── Actions ──
    action_frame = tk.Frame(root, bg=BG)
    action_frame.pack(fill="x", pady=(0, 6))

    dark_button(action_frame, text="Reset", command=lambda: do_reset(reset_char=False),
                width=10).pack(side="left", padx=(0, 4))
    tk.Button(action_frame, text="Save", command=do_save,
              width=10, bg="#4a7", fg="white", activebackground="#5b8",
              activeforeground="white", relief="flat").pack(side="left", padx=(0, 4))

    # ── Settings ──
    settings_frame = dark_labelframe(root, "Settings")
    settings_frame.pack(fill="x")

    persist_var = tk.BooleanVar(value=persist)
    visible_var = tk.BooleanVar(value=visible)

    def on_persist_toggle():
        do_toggle_persist()
        persist_var.set(persist)

    def on_visible_toggle():
        do_toggle_visible()
        visible_var.set(visible)

    dark_check(settings_frame, text="Persistent", variable=persist_var,
               command=on_persist_toggle).pack(side="left", padx=(0, 12))
    dark_check(settings_frame, text="Visible", variable=visible_var,
               command=on_visible_toggle).pack(side="left")

    # ── Keyboard shortcuts hint ──
    hint = (
        "Shortcuts:  RCtrl+Arrows = move 1px  |  RShift+Arrows = 50px  |  "
        "Num5 = Center  |  Num0 = Reset  |  Num. = Save"
    )
    dark_label(root, text=hint, justify="center", fg="#888", font=("Segoe UI", 8)).pack(pady=(6, 0))

    def on_close():
        if not persist:
            release_osd("RTSS_Crosshair_Overlay")
            release_osd("RTSS_Crosshair_Placeholder")
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    return root


# ── Entry point ───────────────────────────────────────────────────────────

def main():
    global cross_x, cross_y, cross_size, crosshair_char, crosshair_color, persist, visible, change_flag

    cross_x, cross_y, cross_size, ch, col, per, vis = reg_load()
    crosshair_char = ch if isinstance(ch, bytes) else ch.encode("ascii", errors="replace")
    crosshair_color = col
    
    persist = per
    visible = vis

    change_flag = True
    apply_state()

    kb_thread = threading.Thread(target=keyboard_loop, daemon=True)
    kb_thread.start()

    root = build_gui()
    root.lift()
    root.focus_force()
    root.mainloop()


if __name__ == "__main__":
    main()
