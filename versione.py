"""Versione dell'app e repository GitHub da cui arrivano gli aggiornamenti.

Per pubblicare una nuova versione: aumentare VERSIONE, poi lanciare pubblica.bat.
"""
VERSIONE = "1.0.0"

# "utente/nome-repository" su GitHub (pubblico). Le release devono avere il tag "vX.Y.Z"
# e contenere AirPodsSuWindows.exe + AirPodsSuWindows.exe.sig (creati da pubblica.bat).
REPO = "DigitalPhanto/AnyAirpods"
