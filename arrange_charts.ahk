; arrange_charts.ahk
; Tiles charts in the MT5 terminal window using Alt+R → T

SetTitleMatchMode, 2   ; partial match anywhere in the title

; First, try matching by the MT5 executable itself (most robust)
if WinExist("ahk_exe terminal64.exe")
{
    WinActivate  ; activates the found window
    Sleep, 300
    Send, !r     ; Alt+R
    Sleep, 200
    Send, t      ; T
    return
}

; Fallback: partial-match on your broker string (no more hard-coding the “21”)
if WinExist("Exness-MT5Real")
{
    WinActivate
    Sleep, 300
    Send, !r
    Sleep, 200
    Send, t
    return
}

; If we get here, nothing was found
MsgBox, ❌ Could not find any MetaTrader 5 window.`n`n
(
    Tried matching:
    • ahk_exe terminal64.exe
    • title contains "Exness-MT5Real"
)
