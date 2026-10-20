"""Firma degli aggiornamenti (Ed25519).

L'app accetta un aggiornamento solo se il file è firmato con la TUA chiave privata.
La chiave privata resta SOLO sul tuo PC (chiave_privata.pem): non va mai pubblicata né
messa su GitHub. Se la perdi, gli utenti non potranno più ricevere aggiornamenti
automatici (dovrebbero scaricare a mano una versione con la nuova chiave): fanne un backup
in un posto sicuro (es. chiavetta USB).

Uso:  python firma.py genera            crea la coppia di chiavi (una volta sola)
      python firma.py firma FILE        crea FILE.sig
"""
import base64
import os
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

CARTELLA = os.path.dirname(os.path.abspath(__file__))
CHIAVE_PRIVATA = os.path.join(CARTELLA, "chiave_privata.pem")
CHIAVE_PUBBLICA = os.path.join(CARTELLA, "chiave_pubblica.txt")


def genera():
    if os.path.exists(CHIAVE_PRIVATA):
        print("La chiave esiste già: non la sovrascrivo (", CHIAVE_PRIVATA, ")")
        return
    chiave = Ed25519PrivateKey.generate()
    with open(CHIAVE_PRIVATA, "wb") as f:
        f.write(chiave.private_bytes(serialization.Encoding.PEM,
                                     serialization.PrivateFormat.PKCS8,
                                     serialization.NoEncryption()))
    pubblica = chiave.public_key().public_bytes(serialization.Encoding.Raw,
                                                serialization.PublicFormat.Raw)
    with open(CHIAVE_PUBBLICA, "w") as f:
        f.write(base64.b64encode(pubblica).decode())
    print("Chiavi create. Fai un BACKUP di", CHIAVE_PRIVATA)


def firma(percorso):
    with open(CHIAVE_PRIVATA, "rb") as f:
        chiave = serialization.load_pem_private_key(f.read(), password=None)
    with open(percorso, "rb") as f:
        firma_ = chiave.sign(f.read())
    with open(percorso + ".sig", "wb") as f:
        f.write(firma_)
    print("Firmato:", percorso + ".sig")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "genera":
        genera()
    elif len(sys.argv) >= 3 and sys.argv[1] == "firma":
        firma(sys.argv[2])
    else:
        print(__doc__)
