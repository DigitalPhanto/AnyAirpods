"""Prepara una nuova versione da pubblicare su GitHub.

1. Aumenta VERSIONE in versione.py (es. 1.0.0 -> 1.0.1)
2. python pubblica.py
3. Su GitHub: Releases -> "Draft a new release" -> tag "vX.Y.Z" -> trascina i due file
   della cartella rilascio\\vX.Y.Z -> scrivi le novità (le prime righe le vedono gli
   utenti nella finestra di aggiornamento) -> "Publish release".
Le app già installate la troveranno entro un giorno (o subito con "Controlla
aggiornamenti" nel menu dell'icona) e chiederanno se aggiornare.
"""
import os
import shutil
import subprocess
import sys

import firma
from versione import REPO, VERSIONE

CARTELLA = os.path.dirname(os.path.abspath(__file__))


def main():
    if REPO.startswith("DA_IMPOSTARE"):
        sys.exit("Prima imposta REPO in versione.py (utente/nome-repository di GitHub).")
    if not os.path.exists(firma.CHIAVE_PRIVATA):
        sys.exit("Manca chiave_privata.pem: senza, gli utenti scarterebbero l'aggiornamento.")
    print(f"Creo l'exe della versione {VERSIONE} (qualche minuto)...")
    subprocess.run(["cmd", "/c", os.path.join(CARTELLA, "crea_exe.bat")], check=True,
                   cwd=CARTELLA)
    destinazione = os.path.join(CARTELLA, "rilascio", f"v{VERSIONE}")
    os.makedirs(destinazione, exist_ok=True)
    exe = os.path.join(destinazione, "AnyAirpods.exe")
    shutil.copy2(os.path.join(CARTELLA, "dist", "AnyAirpods.exe"), exe)
    firma.firma(exe)
    print()
    print(f"Pronto: {destinazione}")
    print(f"Ora su https://github.com/{REPO}/releases/new crea il tag v{VERSIONE}")
    print("e carica AnyAirpods.exe e AnyAirpods.exe.sig")


if __name__ == "__main__":
    main()
