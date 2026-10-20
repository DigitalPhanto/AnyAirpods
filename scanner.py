"""Passo 1: scanner BLE in sola lettura per AirPods.

Ascolta gli annunci Bluetooth LE con dati produttore Apple (0x004C) e, se sono di tipo
"proximity pairing" (0x07, quelli delle AirPods), li stampa grezzi + una decodifica.
Non si collega a niente e non invia niente.

Uso:  python scanner.py            (ascolta 30 secondi)
      python scanner.py 60         (ascolta 60 secondi)
      python scanner.py 30 tutti   (stampa anche gli altri annunci Apple, per debug)

La decodifica segue il formato noto dai progetti open source (OpenPods, AirPodsDesktop,
LibrePods): va VERIFICATA sui dati reali, per questo stampiamo sempre anche i byte grezzi.
"""
import asyncio
import sys
import time

from bleak import BleakScanner

APPLE_ID = 0x004C
TIPO_PROXIMITY = 0x07
# Sotto questo segnale ignoriamo (le proprie AirPods vicine stanno intorno a -45..-60)
RSSI_MIN = -70

# ID modello (byte 3-4 del messaggio). Fonte: progetti open source, da verificare.
MODELLI = {
    0x0220: "AirPods 1",
    0x0F20: "AirPods 2",
    0x1320: "AirPods 3",
    0x1920: "AirPods 4",
    0x1B20: "AirPods 4 ANC",
    0x0E20: "AirPods Pro",
    0x1420: "AirPods Pro 2",
    0x2420: "AirPods Pro 2 (USB-C)",
    0x0A20: "AirPods Max",
}


def batteria(nibble):
    """0-10 -> 0-100%, 15 = non disponibile (auricolare non collegato/in custodia chiusa)."""
    if nibble <= 10:
        return f"{nibble * 10}%"
    return "--"


def analizza(d):
    """Come decodifica() ma restituisce un dizionario (usato da notifica.py).
    Batterie in percentuale (None = non disponibile), coperchio None se non noto."""
    if len(d) < 9 or d[0] != TIPO_PROXIMITY:
        return None
    modello_id = (d[3] << 8) | d[4]
    stato = d[5]
    invertito = (stato & 0x20) == 0
    alto, basso = d[6] >> 4, d[6] & 0x0F
    sx, dx = (alto, basso) if invertito else (basso, alto)
    carica = d[7] >> 4
    in_custodia = bool(stato & 0x40)
    def perc(n):
        return n * 10 if n <= 10 else None
    return {
        "modello_id": modello_id,
        "modello": MODELLI.get(modello_id, f"AirPods (0x{modello_id:04X})"),
        "sx": perc(sx), "dx": perc(dx), "custodia": perc(d[7] & 0x0F),
        "carica_sx": bool(carica & (0b10 if invertito else 0b01)),
        "carica_dx": bool(carica & (0b01 if invertito else 0b10)),
        "carica_custodia": bool(carica & 0b100),
        "in_custodia": in_custodia,
        "coperchio_aperto": (not (d[8] & 0x08)) if in_custodia else None,
    }


def decodifica(d):
    """d = dati produttore Apple SENZA il company ID (inizia col tipo 0x07)."""
    if len(d) < 9:
        return "messaggio troppo corto"
    modello_id = (d[3] << 8) | d[4]
    modello = MODELLI.get(modello_id, f"sconosciuto (0x{modello_id:04X})")
    stato = d[5]
    # Se il bit 0x20 è 0 i due nibble sono invertiti (dipende da quale auricolare trasmette)
    invertito = (stato & 0x20) == 0
    alto, basso = d[6] >> 4, d[6] & 0x0F
    sx, dx = (alto, basso) if invertito else (basso, alto)
    carica = d[7] >> 4
    custodia = d[7] & 0x0F
    carica_sx = bool(carica & (0b10 if invertito else 0b01))
    carica_dx = bool(carica & (0b01 if invertito else 0b10))
    carica_cust = bool(carica & 0b100)
    # Verificati sulle AirPods 3 (prova 2026-10-20):
    #   stato 0x20 = chi trasmette è il SINISTRO (0 = destro)
    #   stato 0x40 = chi trasmette è nella custodia
    #   byte 8, bit 0x08 = coperchio CHIUSO (vale solo se chi trasmette è in custodia)
    chi = "SX" if stato & 0x20 else "DX"
    in_custodia = bool(stato & 0x40)
    coperchio = d[8]
    if in_custodia:
        cop = "chiuso" if coperchio & 0x08 else "aperto"
    else:
        cop = "?"
    # In-ear (prova 2026-10-20): 0x02+0x08 = entrambi in orecchio, nessuno = entrambi fuori.
    # Ipotesi da confermare: 0x02 = SX in orecchio, 0x08 = DX in orecchio.
    # Nota: con le AirPods in orecchio i messaggi arrivano di rado (anche ogni 20 s).
    def c(x):
        return "+" if x else " "
    return (
        f"{modello} | SX {batteria(sx):>4}{c(carica_sx)} DX {batteria(dx):>4}{c(carica_dx)} "
        f"Custodia {batteria(custodia):>4}{c(carica_cust)} | "
        f"trasmette {chi} ({'in custodia' if in_custodia else 'fuori'}) coperchio {cop} | "
        f"stato=0x{stato:02X} bit-orecchio 0x02={int(bool(stato & 0x02))} "
        f"0x08={int(bool(stato & 0x08))}"
    )


async def main():
    durata = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    tutti = len(sys.argv) > 2 and sys.argv[2] == "tutti"
    ultimo = {}  # indirizzo -> ultimi dati, per stampare solo quando cambiano

    def ricevuto(device, adv):
        dati = adv.manufacturer_data.get(APPLE_ID)
        if not dati:
            return
        if dati[0] != TIPO_PROXIMITY and not tutti:
            return
        if adv.rssi < RSSI_MIN and not tutti:
            return  # troppo lontano: probabilmente AirPods di qualcun altro
        if ultimo.get(device.address) == dati:
            return
        ultimo[device.address] = dati
        t = time.monotonic() - inizio
        scrivi(f"{t:5.1f}s [{device.address} RSSI {adv.rssi:>4}] grezzo: {dati.hex(' ')}")
        if dati[0] == TIPO_PROXIMITY:
            scrivi("       -> " + decodifica(dati))

    # Stampa a schermo e salva anche in scansione.txt (così si può rileggere dopo)
    log = open("scansione.txt", "w", encoding="utf-8")
    def scrivi(riga):
        print(riga, flush=True)
        log.write(riga + "\n")
        log.flush()

    scrivi(f"Ascolto per {durata} s... apri la custodia delle AirPods vicino al PC.")
    if len(sys.argv) > 2 and sys.argv[2] == "orecchio":
        scrivi("PROVA: 0s tutti e due in orecchio / 10s togli DX / 20s rimetti DX / "
               "30s togli SX / 40s togli anche DX")
    inizio = time.monotonic()
    async with BleakScanner(detection_callback=ricevuto):
        # Una riga ogni 5 secondi, per sapere a che punto si è durante le prove
        for s in range(5, durata + 1, 5):
            await asyncio.sleep(max(0, s - (time.monotonic() - inizio)))
            scrivi(f"----- {s} s -----")
    if not any(d[0] == TIPO_PROXIMITY for d in ultimo.values()):
        scrivi("Nessun annuncio AirPods ricevuto. Custodia aperta? Bluetooth acceso?")
    scrivi("Fine.")
    log.close()


if __name__ == "__main__":
    asyncio.run(main())
