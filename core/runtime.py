"""Detect the production WebView2 prerequisite before opening the desktop."""
import sys


def webview2_available():
    if sys.platform!='win32':return True
    import winreg
    key=r'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
    for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY,winreg.KEY_WOW64_64KEY):
            try:
                with winreg.OpenKey(hive,key,0,winreg.KEY_READ|view) as handle:
                    value=winreg.QueryValueEx(handle,'pv')[0]
                    if isinstance(value,str) and value and value!='0.0.0.0':return True
            except OSError:pass
    return False


def require_webview2():
    if webview2_available():return True
    import ctypes
    ctypes.windll.user32.MessageBoxW(None,
        'CareWare needs Microsoft Edge WebView2 Runtime. Install the Evergreen Runtime from https://developer.microsoft.com/microsoft-edge/webview2/ and reopen CareWare.',
        'CareWare — runtime required',0x10)
    return False
