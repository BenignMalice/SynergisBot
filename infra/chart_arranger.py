# =====================================
# infra/chart_arranger.py
# =====================================
from __future__ import annotations
from io import BytesIO
from pathlib import Path
import subprocess
import pygetwindow as gw
import pyautogui
from dataclasses import dataclass


@dataclass
class ChartArranger:
    window_title: str
    ahk_exe: str
    ahk_script: str
    auto_arrange: bool = True

    def arrange(self) -> None:
        if not self.auto_arrange:
            return
        if not Path(self.ahk_exe).exists() or not Path(self.ahk_script).exists():
            return
        try:
            subprocess.Popen([self.ahk_exe, self.ahk_script], shell=False)
        except Exception:
            pass

    def screenshot(self) -> BytesIO:
        wins = [
            w
            for w in gw.getAllWindows()
            if self.window_title.lower() in w.title.lower()
        ]
        if wins:
            w = wins[0]
            img = pyautogui.screenshot(region=(w.left, w.top, w.width, w.height))
        else:
            img = pyautogui.screenshot()
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
