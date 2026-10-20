"""Passo 2: popup stile iPhone quando apri la custodia delle AirPods.

Resta in ascolto (sola lettura, come scanner.py). Quando la custodia passa da chiusa ad
aperta, in basso a destra compare una finestrella con le batterie di sinistro, destro e
custodia (a ruota, stile Apple). Si chiude da sola quando chiudi la custodia, dopo qualche
secondo senza dati, o cliccandoci sopra.

In basso il popup cambia in base allo stato:
- AirPods mai abbinate al PC -> pulsante "Come collegarle" (istruzioni)
- driver Bluetooth Microsoft (stato affidabile):
    non collegate -> "Connetti" (collega con un clic, connetti.py)
    collegate     -> "Collegate al PC"
- altri driver (es. Broadcom): pulsante "Bluetooth" (apre le impostazioni), perché lì non
  si può sapere in modo affidabile se sono collegate

Uso:  python notifica.py      (Ctrl+C nel terminale per uscire)
      pythonw notifica.py     (senza finestra; log in %LOCALAPPDATA%\\AnyAirpods)
Gira una sola copia alla volta. Avvio automatico: vedi avvio_automatico.py
"""
import asyncio
import ctypes
import math
import os
import sys
import queue
import threading
import time
import tkinter as tk

import pystray
from bleak import BleakScanner
from PIL import Image, ImageDraw, ImageTk
from winrt.windows.devices.bluetooth import BluetoothConnectionStatus, BluetoothDevice

import aggiornamento
from avvio_automatico import attiva as attiva_avvio
from avvio_automatico import disattiva as disattiva_avvio
from avvio_automatico import e_attivo
from connetti import connetti, ha_uscita_dedicata, trova_airpods_abbinate
from icona import crea_icona
from versione import VERSIONE
from scanner import APPLE_ID, analizza

# Solo le AirPods con questo modello (es. 0x1320 = AirPods 3). None = qualsiasi modello
# (app universale: tutte le AirPods/Beats che mandano il messaggio "proximity pairing")
MIO_MODELLO = None
# Solo segnali forti: le AirPods dei vicini arrivano sotto -80
RSSI_VICINO = -65
# Se non arriva niente per questo tempo, la custodia si considera chiusa
SILENZIO_S = 15
# Il popup si chiude se non arrivano dati nuovi per questo tempo
DURATA_POPUP_S = 10
# Tempo minimo tra due popup
PAUSA_POPUP_S = 20

NON_ABBINATE, NON_COLLEGATE, COLLEGATE = "non abbinate", "non collegate", "collegate"

messaggi = queue.Queue()
# "stato" aggiornato dal thread Bluetooth; "preciso" = il driver permette di sapere se sono
# collegate e di collegarle con un clic (driver Microsoft). Vedi connetti.ha_uscita_dedicata
collegamento = {"stato": NON_ABBINATE, "preciso": False}


async def controlla_collegamento():
    """Ogni 3 secondi guarda se le AirPods sono abbinate e collegate al PC."""
    while True:
        indirizzi = trova_airpods_abbinate()
        if not indirizzi:
            collegamento["stato"] = NON_ABBINATE
        else:
            ok = False  # collegate se almeno una delle voci "AirPods" lo è
            for indirizzo in indirizzi:
                try:
                    d = await BluetoothDevice.from_bluetooth_address_async(indirizzo)
                    if d is not None and \
                            d.connection_status == BluetoothConnectionStatus.CONNECTED:
                        ok = True
                except OSError:
                    pass
            collegamento["stato"] = COLLEGATE if ok else NON_COLLEGATE
        await asyncio.sleep(3)


def ascolta_ble():
    """Gira in un thread separato: mette in coda i messaggi delle AirPods vicine."""
    def ricevuto(device, adv):
        dati = adv.manufacturer_data.get(APPLE_ID)
        if not dati or adv.rssi < RSSI_VICINO:
            return
        info = analizza(dati)
        if info and (MIO_MODELLO is None or info["modello_id"] == MIO_MODELLO):
            messaggi.put(info)

    async def principale():
        async with BleakScanner(detection_callback=ricevuto):
            await controlla_collegamento()

    asyncio.run(principale())


class Popup:
    SFONDO = "#1c1c1e"
    TESTO = "#ffffff"
    GRIGIO = "#8e8e93"
    ANELLO = "#3a3a3c"
    VERDE = "#30d158"
    GIALLO = "#ffd60a"
    ROSSO = "#ff453a"
    W, H = 340, 230
    D = 58  # diametro delle ruote

    def __init__(self, root):
        self.root = root
        self.win = None
        self.ultimo_aggiornamento = 0
        self.stato_mostrato = None

    def aperto(self):
        return self.win is not None

    def mostra(self, info):
        if not self.win:
            self._crea(info["modello"])
            print(time.strftime("%H:%M:%S"), "popup aperto")
        self.aggiorna(info)

    def _crea(self, modello):
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)  # niente barra del titolo
        win.attributes("-topmost", True)
        win.configure(bg=self.SFONDO)
        x = win.winfo_screenwidth() - self.W - 16
        y = win.winfo_screenheight() - self.H - 56  # sopra la barra delle applicazioni
        win.geometry(f"{self.W}x{self.H}+{x}+{y}")

        tk.Label(win, text=modello, bg=self.SFONDO, fg=self.TESTO,
                 font=("Segoe UI", 13, "bold")).pack(pady=(10, 4))
        riga = tk.Frame(win, bg=self.SFONDO)
        riga.pack()
        self.ruote = {}
        for chiave, nome in (("sx", "Sinistro"), ("dx", "Destro"), ("custodia", "Custodia")):
            col = tk.Frame(riga, bg=self.SFONDO)
            col.pack(side="left", padx=14)
            tk.Label(col, text=nome, bg=self.SFONDO, fg=self.GRIGIO,
                     font=("Segoe UI", 9)).pack()
            ruota = tk.Canvas(col, width=self.D + 4, height=self.D + 4, bg=self.SFONDO,
                              highlightthickness=0)
            ruota.pack(pady=2)
            ruota.percentuale = tk.Label(col, text="--", bg=self.SFONDO, fg=self.TESTO,
                                         font=("Segoe UI", 11, "bold"))
            ruota.percentuale.pack()
            self.ruote[chiave] = ruota
        self.basso = tk.Frame(win, bg=self.SFONDO)
        self.basso.pack(fill="both", expand=True)
        self.stato_mostrato = None
        self.win = win
        # Mentre le AirPods si collegano, il driver Bluetooth può aprire finestre sue:
        # riportiamo il popup in primo piano un paio di volte
        for ritardo in (300, 1500, 3000):
            win.after(ritardo, self._in_primo_piano)

    def _in_primo_piano(self):
        if self.win:
            self.win.attributes("-topmost", True)
            self.win.lift()

    def _immagine_anello(self, perc, colore):
        """Anello liscio: disegnato 4 volte più grande con Pillow e poi rimpicciolito
        (il canvas di tkinter su Windows non ha l'antialiasing: cerchi "a segmenti")."""
        k = 4
        lato = (self.D + 4) * k
        spessore = 6 * k
        img = Image.new("RGBA", (lato, lato), self.SFONDO)
        disegno = ImageDraw.Draw(img)
        box = (2 * k, 2 * k, lato - 2 * k, lato - 2 * k)
        disegno.ellipse(box, outline=self.ANELLO, width=spessore)
        if perc:
            if perc >= 100:
                disegno.ellipse(box, outline=colore, width=spessore)
            else:
                # Pillow: angoli in senso orario da ore 3; partiamo da ore 12 (-90)
                fine = -90 + 3.6 * perc
                disegno.arc(box, -90, fine, fill=colore, width=spessore)
                # estremità arrotondate, come nelle ruote Apple
                c = lato / 2
                raggio = (lato - 4 * k - spessore) / 2
                for angolo in (-90, fine):
                    x = c + raggio * math.cos(math.radians(angolo))
                    y = c + raggio * math.sin(math.radians(angolo))
                    s = spessore / 2
                    disegno.ellipse((x - s, y - s, x + s, y + s), fill=colore)
        img = img.resize((self.D + 4, self.D + 4), Image.LANCZOS)
        return ImageTk.PhotoImage(img)

    def _disegna_ruota(self, ruota, perc, in_carica):
        ruota.delete("all")
        c = (self.D + 4) / 2
        colore = self.VERDE if perc is None or in_carica or perc > 20 else (
            self.GIALLO if perc > 10 else self.ROSSO)
        ruota.immagine = self._immagine_anello(perc, colore)  # tenere il riferimento
        ruota.create_image(0, 0, image=ruota.immagine, anchor="nw")
        if perc is None:
            ruota.percentuale.config(text="--", fg=self.GRIGIO)
            return
        ruota.percentuale.config(text=f"{perc}%", fg=self.TESTO)
        if in_carica:  # fulmine al centro della ruota
            ruota.create_text(c, c, text="⚡", fill=self.VERDE, font=("Segoe UI", 14))

    def aggiorna(self, info):
        self.ultimo_aggiornamento = time.monotonic()
        for chiave, ruota in self.ruote.items():
            self._disegna_ruota(ruota, info[chiave], info["carica_" + chiave])
        self.aggiorna_stato()

    def aggiorna_stato(self):
        """Ricostruisce la parte bassa solo se lo stato di collegamento è cambiato."""
        stato = collegamento["stato"]
        if not collegamento["preciso"] and stato != NON_ABBINATE:
            stato = "abbinate"  # driver non Microsoft: lo stato collegate/no non è affidabile
        if not self.win or stato == self.stato_mostrato:
            return
        self.stato_mostrato = stato
        for w in self.basso.winfo_children():
            w.destroy()
        if stato == COLLEGATE:
            self._scritta("✓ Collegate al PC", self.VERDE)
            self._bottoni(("Chiudi", self.chiudi))
        elif stato == NON_COLLEGATE:
            self._scritta("Non collegate al PC", self.GRIGIO)
            self._bottoni(("Connetti", self._connetti), ("Chiudi", self.chiudi))
        elif stato == NON_ABBINATE:
            self._scritta("Non ancora abbinate a questo PC", self.GRIGIO)
            self._bottoni(("Come collegarle", self._istruzioni), ("Chiudi", self.chiudi))
        else:
            # Versione semplice (driver come Broadcom): batterie + pagina Bluetooth
            self._bottoni(("Bluetooth", self._impostazioni), ("Chiudi", self.chiudi))

    def _scritta(self, testo, colore):
        tk.Label(self.basso, text=testo, bg=self.SFONDO, fg=colore,
                 font=("Segoe UI", 9)).pack(pady=(6, 2))

    def _bottoni(self, *bottoni):
        riga = tk.Frame(self.basso, bg=self.SFONDO)
        riga.pack(pady=(8, 0))
        for testo, azione in bottoni:
            tk.Button(riga, text=testo, command=azione, bg=self.ANELLO, fg=self.TESTO,
                      activebackground="#48484a", activeforeground=self.TESTO,
                      relief="flat", font=("Segoe UI", 9), padx=10, pady=2
                      ).pack(side="left", padx=6)

    def _istruzioni(self):
        for w in self.basso.winfo_children():
            w.destroy()
        tk.Label(self.basso, bg=self.SFONDO, fg=self.TESTO, font=("Segoe UI", 8),
                 justify="left", text=(
                     "1. AirPods nella custodia, coperchio aperto\n"
                     "2. Tieni premuto il tasto dietro la custodia finché la luce\n"
                     "    lampeggia bianca\n"
                     "3. Su Windows: Aggiungi dispositivo > Bluetooth > AirPods"
                 )).pack(pady=(4, 2))
        self._bottoni(("Apri Bluetooth", self._impostazioni), ("Chiudi", self.chiudi))
        # Le istruzioni restano aperte più a lungo
        self.ultimo_aggiornamento = time.monotonic() + 30

    def _connetti(self):
        """Collega con un clic (connetti.py), in un thread per non bloccare il popup."""
        for w in self.basso.winfo_children():
            w.destroy()
        self._scritta("Collegamento in corso...", self.GRIGIO)
        self.ultimo_aggiornamento = time.monotonic() + 10  # tieni aperto il popup

        def lavoro():
            try:
                fatti = connetti(indirizzi=trova_airpods_abbinate())
            except Exception as e:  # errori COM di Windows
                print("Errore collegamento:", e)
                fatti = []
            self.root.after(0, lambda: self._esito_connetti(fatti))

        threading.Thread(target=lavoro, daemon=True).start()

    def _esito_connetti(self, fatti):
        if not self.win:
            return
        if fatti:
            print("Collegamento richiesto per:", ", ".join(fatti))
            # la scritta "Collegate" arriva da sola quando Windows le vede collegate
            self.stato_mostrato = None
            return
        # Windows non ha un'uscita audio per le AirPods: abbinamento da rifare
        for w in self.basso.winfo_children():
            w.destroy()
        tk.Label(self.basso, bg=self.SFONDO, fg=self.GIALLO, font=("Segoe UI", 8),
                 justify="center", text=(
                     "Windows non ha l'audio delle AirPods installato.\n"
                     "Rimuovile in Impostazioni Bluetooth e riabbinale."
                 )).pack(pady=(4, 2))
        self._bottoni(("Apri Bluetooth", self._impostazioni), ("Chiudi", self.chiudi))
        self.ultimo_aggiornamento = time.monotonic() + 30

    def _impostazioni(self):
        os.startfile("ms-settings:bluetooth")
        self.chiudi()

    def chiudi(self, motivo="tasto"):
        if self.win:
            print(time.strftime("%H:%M:%S"), "popup chiuso:", motivo)
            self.win.destroy()
            self.win = None


def gia_in_esecuzione(attesa_s=0):
    """Un solo popup alla volta: un 'mutex' di Windows col nome del programma.
    attesa_s: dopo un aggiornamento la versione vecchia sta ancora chiudendo: aspettiamo."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    fine = time.monotonic() + attesa_s
    while True:
        handle = kernel32.CreateMutexW(None, False, "AnyAirpods_notifica")
        if ctypes.get_last_error() != 183:  # ERROR_ALREADY_EXISTS
            return False
        kernel32.CloseHandle(handle)
        if time.monotonic() > fine:
            return True
        time.sleep(0.5)


class Finestrella:
    """Piccola finestra stile popup per messaggi (aggiornamenti), in basso a destra."""

    def __init__(self, root, titolo, testo, bottoni=(), durata_ms=None):
        S = Popup
        self.win = win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=S.SFONDO)
        tk.Label(win, text=titolo, bg=S.SFONDO, fg=S.TESTO,
                 font=("Segoe UI", 12, "bold")).pack(padx=16, pady=(12, 4))
        self.testo = tk.Label(win, text=testo, bg=S.SFONDO, fg=S.GRIGIO,
                              font=("Segoe UI", 9), justify="center", wraplength=300)
        self.testo.pack(padx=16)
        self.riga = tk.Frame(win, bg=S.SFONDO)
        self.riga.pack(pady=(10, 12))
        self.imposta_bottoni(bottoni)
        win.update_idletasks()
        w, h = max(win.winfo_reqwidth(), 340), win.winfo_reqheight()
        win.geometry(f"{w}x{h}+{win.winfo_screenwidth() - w - 16}"
                     f"+{win.winfo_screenheight() - h - 56}")
        if durata_ms:
            win.after(durata_ms, self.chiudi)

    def imposta_bottoni(self, bottoni):
        for b in self.riga.winfo_children():
            b.destroy()
        for testo, azione in bottoni:
            tk.Button(self.riga, text=testo, command=azione, bg=Popup.ANELLO, fg=Popup.TESTO,
                      activebackground="#48484a", activeforeground=Popup.TESTO,
                      relief="flat", font=("Segoe UI", 9), padx=10, pady=2
                      ).pack(side="left", padx=6)

    def chiudi(self):
        if self.win:
            self.win.destroy()
            self.win = None


def main():
    if sys.stdout is None:
        # Avviato con pythonw (senza finestra): i messaggi vanno in un file di log
        cartella = os.path.join(os.environ["LOCALAPPDATA"], "AnyAirpods")
        os.makedirs(cartella, exist_ok=True)
        sys.stdout = sys.stderr = open(os.path.join(cartella, "notifica.log"), "a",
                                       encoding="utf-8", buffering=1)
    aggiornato = "--aggiornato" in sys.argv
    if aggiornamento.installa_se_serve():
        return  # è partita la copia nella cartella fissa
    if gia_in_esecuzione(attesa_s=15 if aggiornato else 0):
        print("notifica.py è già in esecuzione: esco.")
        return
    primo_avvio_exe = aggiornamento.e_exe() and not os.path.exists(
        os.path.join(aggiornamento.CARTELLA_INSTALLAZIONE, "avviato.txt"))
    if aggiornamento.e_exe():
        try:
            if primo_avvio_exe or e_attivo():
                # avvio automatico attivo di default; e deve puntare a questo exe
                attiva_avvio()
            with open(os.path.join(aggiornamento.CARTELLA_INSTALLAZIONE, "avviato.txt"),
                      "w") as f:
                f.write(VERSIONE)
        except Exception as e:
            print("Avvio automatico, errore:", e)

    root = tk.Tk()
    root.withdraw()  # finestra principale nascosta: si vede solo il popup
    popup = Popup(root)
    stato = {"coperchio": None, "ultimo_msg": 0.0, "ultimo_popup": 0.0, "ultimo_info": None,
             "finestra_agg": None}
    comandi = queue.Queue()  # da altri thread (menu, aggiornamenti) al thread di tkinter

    def proponi_aggiornamento(agg):
        if stato["finestra_agg"] and stato["finestra_agg"].win:
            return  # già mostrata
        note = agg["note"].strip().splitlines()
        testo = f"Versione {agg['versione']} (hai la {VERSIONE})"
        if note:
            testo += "\n" + "\n".join(note[:3])
        f = Finestrella(root, "Aggiornamento disponibile", testo)
        stato["finestra_agg"] = f

        def aggiorna():
            f.testo.config(text="Scaricamento e controllo della firma...")
            f.imposta_bottoni(())

            def lavoro():
                try:
                    nuovo = aggiornamento.scarica_e_verifica(agg)
                    comandi.put(("applica", nuovo))
                except Exception as e:
                    print("Aggiornamento non riuscito:", e)
                    comandi.put(("errore_agg", str(e)))

            threading.Thread(target=lavoro, daemon=True).start()

        f.imposta_bottoni((("Aggiorna", aggiorna), ("Più tardi", f.chiudi)))

    def esegui_comandi():
        while not comandi.empty():
            comando = comandi.get()
            nome, dato = comando if isinstance(comando, tuple) else (comando, None)
            if nome == "mostra":
                info = stato["ultimo_info"] or {
                    "modello": "AirPods", "sx": None, "dx": None, "custodia": None,
                    "carica_sx": False, "carica_dx": False, "carica_custodia": False}
                popup.mostra(info)
            elif nome == "aggiornamento":
                proponi_aggiornamento(dato)
            elif nome == "nessun_aggiornamento":
                Finestrella(root, "Nessun aggiornamento",
                            f"Hai già l'ultima versione ({VERSIONE}).",
                            durata_ms=4000)
            elif nome == "applica":
                try:
                    aggiornamento.applica(dato)
                    print(time.strftime("%H:%M:%S"), "aggiornamento applicato, riavvio")
                    root.quit()
                except Exception as e:
                    comandi.put(("errore_agg", str(e)))
            elif nome == "errore_agg":
                if stato["finestra_agg"]:
                    stato["finestra_agg"].chiudi()
                Finestrella(root, "Aggiornamento non riuscito",
                            "Riproverò più tardi.\n" + dato[:120], durata_ms=8000)
            elif nome == "esci":
                root.quit()

    def controlla_aggiornamenti(manuale=False):
        agg = aggiornamento.controlla()
        if agg:
            comandi.put(("aggiornamento", agg))
        elif manuale:
            comandi.put("nessun_aggiornamento")

    def aggiornamenti_periodici():
        time.sleep(60)  # non appesantire l'avvio del PC
        while True:
            controlla_aggiornamenti()
            time.sleep(24 * 3600)

    def controlla_coda():
        esegui_comandi()
        adesso = time.monotonic()
        while not messaggi.empty():
            info = messaggi.get()
            stato["ultimo_info"] = info
            silenzio = adesso - stato["ultimo_msg"] > SILENZIO_S
            stato["ultimo_msg"] = adesso
            aperto = info["coperchio_aperto"]
            if aperto is True:
                appena_aperta = stato["coperchio"] is False or silenzio
                if popup.aperto():
                    popup.aggiorna(info)
                elif appena_aperta and adesso - stato["ultimo_popup"] > PAUSA_POPUP_S:
                    print(time.strftime("%H:%M:%S"), "custodia aperta -> popup",
                          f"({collegamento['stato']})")
                    popup.mostra(info)
                    stato["ultimo_popup"] = adesso
            elif aperto is False:
                popup.chiudi("custodia chiusa")
            elif popup.aperto():
                popup.aggiorna(info)
            if aperto is not None:
                stato["coperchio"] = aperto
        popup.aggiorna_stato()
        if popup.aperto() and adesso - popup.ultimo_aggiornamento > DURATA_POPUP_S:
            popup.chiudi("nessun dato nuovo")
        root.after(200, controlla_coda)

    def controlla_driver():
        """In background ogni 30 s: il driver permette lo stato preciso? (vedi connetti.py)
        Fuori dal thread principale perché mentre le AirPods si collegano può bloccarsi."""
        while True:
            try:
                collegamento["preciso"] = ha_uscita_dedicata(trova_airpods_abbinate())
            except Exception as e:
                print("Controllo driver fallito:", e)
                collegamento["preciso"] = False
            time.sleep(30)

    threading.Thread(target=ascolta_ble, daemon=True).start()
    threading.Thread(target=controlla_driver, daemon=True).start()
    if aggiornamento.e_exe():
        threading.Thread(target=aggiornamenti_periodici, daemon=True).start()
    icona = crea_icona_vassoio(
        comandi, lambda: threading.Thread(target=controlla_aggiornamenti, args=(True,),
                                          daemon=True).start())
    print(time.strftime("%Y-%m-%d %H:%M:%S"), f"Versione {VERSIONE}.",
          "In ascolto. Apri la custodia delle AirPods. Ctrl+C per uscire.")
    if aggiornato:
        Finestrella(root, "AnyAirpods aggiornato",
                    f"Ora hai la versione {VERSIONE}.", durata_ms=6000)
    root.after(200, controlla_coda)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    icona.stop()
    print(time.strftime("%Y-%m-%d %H:%M:%S"), "Uscita.")


def crea_icona_vassoio(comandi, controlla_aggiornamenti):
    """Icona vicino all'orologio con il menu dell'app (gira in un thread suo)."""
    def cambia_avvio(icon, voce):
        try:
            disattiva_avvio() if e_attivo() else attiva_avvio()
        except Exception as e:
            print("Avvio automatico, errore:", e)

    def esci(icon, voce):
        comandi.put("esci")

    menu = pystray.Menu(
        pystray.MenuItem(f"AnyAirpods {VERSIONE}", None, enabled=False),
        pystray.MenuItem("Mostra batterie", lambda icon, voce: comandi.put("mostra"),
                         default=True),  # anche doppio clic sull'icona
        pystray.MenuItem("Avvia con Windows", cambia_avvio,
                         checked=lambda voce: e_attivo()),
        pystray.MenuItem("Controlla aggiornamenti",
                         lambda icon, voce: controlla_aggiornamenti()),
        pystray.MenuItem("Esci", esci),
    )
    icona = pystray.Icon("AnyAirpods", crea_icona(64), "AnyAirpods", menu)
    icona.run_detached()
    return icona


if __name__ == "__main__":
    main()
