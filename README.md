<p align="center">
  <img src="icon.png" alt="RTSS Python Crosshair" width="128" height="128">
</p>

# RTSS Python Crosshair

[![Python](https://img.shields.io/badge/python-3.x-blue?logo=python)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows-blue?logo=windows)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Support-yellow?logo=buymeacoffee)](https://buymeacoffee.com/izu_x)

Crosshair overlay for [RivaTuner Statistics Server](https://www.guru3d.com/files-details/rtss-rivatuner-statistics-server-download.html), written in Python.

**Zero dependencies** — no compiler, no Visual Studio, no external packages. Just Python 3.

## Requirements

- Windows with RTSS running
- Python 3.x (any version with tkinter)

## Usage

```powershell
python rtss_crosshair.py
```

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
