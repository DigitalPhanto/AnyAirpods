"""Fa partire (o no) il popup delle AirPods all'accensione del PC.

Mette un collegamento nella cartella "Esecuzione automatica" dell'utente
(shell:startup). Funziona sia da script (avvia notifica.py con pythonw, senza finestra
nera) sia dal .exe (avvia l'exe stesso). Non servono permessi di amministratore.

Uso:  python avvio_automatico.py attiva
      python avvio_automatico.py disattiva
Dall'app: menu dell'icona vicino all'orologio -> "Avvia con Windows".
"""
import os
import sys

import comtypes.client

NOME = "AnyAirpods.lnk"


def percorso_collegamento():
    esecuzione_automatica = os.path.join(
        os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
    return os.path.join(esecuzione_automatica, NOME)


def e_attivo():
    return os.path.exists(percorso_collegamento())


def attiva():
    shell = comtypes.client.CreateObject("WScript.Shell", dynamic=True)
    lnk = shell.CreateShortcut(percorso_collegamento())
    if getattr(sys, "frozen", False):  # siamo dentro il .exe
        lnk.TargetPath = sys.executable
        lnk.WorkingDirectory = os.path.dirname(sys.executable)
    else:
        cartella = os.path.dirname(os.path.abspath(__file__))
        lnk.TargetPath = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        lnk.Arguments = f'"{os.path.join(cartella, "notifica.py")}"'
        lnk.WorkingDirectory = cartella
    lnk.Description = "Popup batterie AirPods all'apertura della custodia"
    lnk.Save()
    print("Avvio automatico attivato:", percorso_collegamento())


def disattiva():
    try:
        os.remove(percorso_collegamento())
        print("Avvio automatico disattivato.")
    except FileNotFoundError:
        print("Non era attivo.")


if __name__ == "__main__":
    scelta = sys.argv[1] if len(sys.argv) > 1 else ""
    if scelta == "attiva":
        attiva()
    elif scelta == "disattiva":
        disattiva()
    else:
        print(__doc__)
