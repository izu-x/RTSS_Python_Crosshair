# RTSS Python Crosshair

Crosshair overlay for RivaTuner Statistics Server, written in Python.

**Zero dependencies** — no compiler, no Visual Studio, no external packages. Just Python 3.

## Usage

```powershell
python rtss_crosshair.py
```

Requires:
- Windows with [RivaTuner Statistics Server](https://www.guru3d.com/files-details/rtss-rivatuner-statistics-server-download.html) running
- Python 3.x (any version with tkinter)

## Controls

### Keyboard (numpad OR no-numpad alternatives)

| Action | Numpad | No Numpad |
|--------|--------|-----------|
| Move 1px | RCtrl + Num4/6/8/2 | RCtrl + **Arrow keys** |
| Move 50px | RShift + Num4/6/8/2 | RShift + **Arrow keys** |
| Center | RCtrl + Num5 | RCtrl + **5** |
| Reset | RCtrl + Num0 | RCtrl + **0** |
| Size + | RCtrl + Num+ | RCtrl + **=** |
| Size - | RCtrl + Num- | RCtrl + **-** |
| Save | RCtrl + Num. | RCtrl + **.** |

### GUI buttons

Clickable buttons in the window for all actions — fully mouse-driven if preferred.

### Custom symbol

Type any character in the text field and click **Apply** to change the crosshair symbol.

### Persistence

Click **Save** (or RCtrl + Num.) to store current position, size, and symbol to the Windows registry. Settings are auto-loaded on next launch.
