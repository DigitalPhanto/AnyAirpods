@echo off
rem Crea dist\AnyAirpods.exe (un solo file con dentro Python e tutte le librerie).
rem Serve: pip install bleak comtypes pillow pystray cryptography pyinstaller
rem Per pubblicare un aggiornamento usare pubblica.py (crea l'exe e lo firma).
cd /d "%~dp0"
python icona.py
python -m PyInstaller --noconfirm --onefile --windowed --name AnyAirpods ^
  --icon icona.ico --collect-all winrt --collect-submodules bleak ^
  --hidden-import pystray._win32 notifica.py
