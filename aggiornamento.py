"""Installazione in una cartella fissa e aggiornamenti automatici da GitHub Releases.

- Al primo avvio l'exe si copia in %LOCALAPPDATA%\\AnyAirpods e riparte da lì
  (serve un posto fisso per potersi aggiornare).
- controlla(): chiede a GitHub l'ultima release; se è più nuova restituisce i dati.
- scarica_e_verifica(): scarica exe + firma e controlla la firma con la chiave pubblica
  qui sotto (la privata è solo sul PC dello sviluppatore, vedi firma.py).
- applica(): rinomina l'exe in uso (Windows lo permette anche mentre gira), mette il nuovo
  al suo posto e lo avvia. Il vecchio viene cancellato all'avvio successivo.
Funziona solo dal .exe (da script non fa niente).
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import urllib.request

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from versione import REPO, VERSIONE

CHIAVE_PUBBLICA = "DixQxUnUZPAvy/9A8dlTjRaD0OsQWsfrUuGy01WGfIw="
NOME_EXE = "AnyAirpods.exe"
CARTELLA_INSTALLAZIONE = os.path.join(os.environ["LOCALAPPDATA"], "AnyAirpods")
EXE_INSTALLATO = os.path.join(CARTELLA_INSTALLAZIONE, NOME_EXE)


def e_exe():
    return getattr(sys, "frozen", False)


def _numeri(versione):
    """"v1.2.3" -> (1, 2, 3), per confrontare le versioni."""
    return tuple(int(x) for x in versione.lstrip("vV").split("."))


def installa_se_serve():
    """Se l'exe non è nella cartella fissa, ci si copia e si riavvia da lì.
    Restituisce True se il chiamante deve uscire (è partita la copia installata)."""
    if not e_exe():
        return False
    # pulizia dopo un aggiornamento
    vecchio = EXE_INSTALLATO + ".vecchio"
    if os.path.exists(vecchio):
        try:
            os.remove(vecchio)
        except OSError:
            pass
    if os.path.normcase(os.path.abspath(sys.executable)) == os.path.normcase(EXE_INSTALLATO):
        return False
    os.makedirs(CARTELLA_INSTALLAZIONE, exist_ok=True)
    try:
        shutil.copy2(sys.executable, EXE_INSTALLATO)
    except OSError as e:  # es. la copia installata è già in esecuzione
        print("Installazione non riuscita:", e)
        return False
    print("Installato in", EXE_INSTALLATO)
    subprocess.Popen([EXE_INSTALLATO], close_fds=True)
    return True


def controlla():
    """Restituisce {"versione", "url_exe", "url_firma", "note"} se c'è una versione più
    nuova su GitHub, altrimenti None. Errori di rete -> None (si riproverà più tardi)."""
    if REPO.startswith("DA_IMPOSTARE"):
        return None
    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    richiesta = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "AnyAirpods"})
    try:
        with urllib.request.urlopen(richiesta, timeout=15) as r:
            release = json.load(r)
        if _numeri(release["tag_name"]) <= _numeri(VERSIONE):
            return None
        file = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
        if NOME_EXE not in file or NOME_EXE + ".sig" not in file:
            return None
        return {"versione": release["tag_name"].lstrip("vV"), "url_exe": file[NOME_EXE],
                "url_firma": file[NOME_EXE + ".sig"], "note": release.get("body") or ""}
    except Exception as e:
        print("Controllo aggiornamenti non riuscito:", e)
        return None


def _scarica(url):
    richiesta = urllib.request.Request(url, headers={"User-Agent": "AnyAirpods"})
    with urllib.request.urlopen(richiesta, timeout=120) as r:
        return r.read()


def scarica_e_verifica(aggiornamento):
    """Scarica e verifica la firma. Restituisce il percorso del nuovo exe.
    Solleva un'eccezione se qualcosa non va (firma sbagliata = file NON usato)."""
    dati = _scarica(aggiornamento["url_exe"])
    firma = _scarica(aggiornamento["url_firma"])
    chiave = Ed25519PublicKey.from_public_bytes(base64.b64decode(CHIAVE_PUBBLICA))
    try:
        chiave.verify(firma, dati)
    except InvalidSignature:
        raise RuntimeError("Firma non valida: aggiornamento scartato")
    nuovo = EXE_INSTALLATO + ".nuovo"
    with open(nuovo, "wb") as f:
        f.write(dati)
    return nuovo


def applica(nuovo):
    """Mette il nuovo exe al posto di quello in uso e lo avvia. Il chiamante deve uscire."""
    attuale = os.path.abspath(sys.executable)
    vecchio = attuale + ".vecchio"
    if os.path.exists(vecchio):
        os.remove(vecchio)
    os.replace(attuale, vecchio)  # rinominare un exe in esecuzione è permesso
    try:
        os.replace(nuovo, attuale)
    except OSError:
        os.replace(vecchio, attuale)  # rimetti a posto se non riesce
        raise
    subprocess.Popen([attuale, "--aggiornato"], close_fds=True)
