# AnyAirpods

**Il popup delle AirPods, ma su Windows.** Apri la custodia vicino al PC e compare una
finestrella in basso a destra con la batteria di auricolare sinistro, destro e custodia,
come su iPhone.

*English summary below.*

![Windows 10 e 11](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6)
![Versione](https://img.shields.io/github/v/release/DigitalPhanto/AnyAirpods)

---

## Cosa fa

- **Popup all'apertura della custodia**: batterie di sinistro, destro e custodia, con ruote
  colorate stile Apple (verde, giallo sotto il 20%, rosso sotto il 10%) e un fulmine ⚡
  quando un auricolare o la custodia è in carica. Si chiude da solo quando chiudi la custodia.
- **Icona vicino all'orologio** con il menu: *Mostra batterie* (anche doppio clic),
  *Avvia con Windows*, *Controlla aggiornamenti*, *Esci*.
- **Collegamento**:
  - AirPods mai abbinate al PC: il pulsante *Come collegarle* spiega i passaggi.
  - Con il driver Bluetooth di Microsoft: mostra se sono collegate e il pulsante *Connetti*
    le collega con un clic, senza passare dalle impostazioni.
  - Con altri driver (per esempio Broadcom), dove Windows non dice in modo affidabile se
    sono collegate, il popup mostra le batterie e un pulsante che apre le impostazioni
    Bluetooth. L'app riconosce da sola il caso giusto.
- **Parte con Windows** in background, senza finestre, e usa circa 55 MB di RAM.
- **Si aggiorna da sola**: quando esce una nuova versione te lo chiede (*Aggiorna / Più
  tardi*). Gli aggiornamenti sono firmati digitalmente e l'app scarta qualsiasi file non
  firmato dall'autore.

## Requisiti

- Windows 10 o Windows 11.
- Un adattatore Bluetooth 4.0 o più recente, con Bluetooth Low Energy (quasi tutti i PC
  dal 2012 in poi).
- AirPods di qualsiasi generazione: AirPods 1, 2, 3, 4, Pro, Pro 2, Max, e molte cuffie
  Beats. Il formato dei dati è lo stesso per tutti i modelli; **è stata provata davvero
  solo con AirPods 3**. Se usi un altro modello, apri una segnalazione e dimmi se funziona.
- Niente Python, niente installazioni: è un unico file `.exe`.

## Installazione

1. Scarica `AnyAirpods.exe` dall'ultima
   [release](https://github.com/DigitalPhanto/AnyAirpods/releases/latest).
2. Avvialo. Windows SmartScreen potrebbe avvisare che l'app è sconosciuta, perché non è
   firmata con un certificato a pagamento: *Ulteriori informazioni → Esegui comunque*.
3. L'app si copia in `%LOCALAPPDATA%\AnyAirpods`, si attiva all'avvio di Windows e
   compare l'icona vicino all'orologio.
4. Apri la custodia delle AirPods vicino al PC.

**Disinstallare**: menu dell'icona → togli *Avvia con Windows* → *Esci*, poi cancella la
cartella `%LOCALAPPDATA%\AnyAirpods`.

## Come funziona

Le AirPods trasmettono di continuo, soprattutto a custodia aperta, un breve messaggio
Bluetooth Low Energy pubblico (dati produttore Apple `0x004C`, tipo `0x07`,
"proximity pairing"). È lo stesso messaggio che fa comparire il popup sull'iPhone. Dentro
ci sono il modello, le batterie a passi del 10%, lo stato di carica, il coperchio aperto o
chiuso e se gli auricolari sono nelle orecchie. AnyAirpods lo **ascolta e basta**: non si
collega alle AirPods e non invia niente.

| Byte | Contenuto |
|---|---|
| 0 | tipo `0x07` (proximity pairing) |
| 3-4 | modello (es. `13 20` = AirPods 3) |
| 5 | stato: `0x20` = trasmette il sinistro, `0x40` = chi trasmette è in custodia, `0x02`/`0x08` = in orecchio |
| 6 | batterie dei due auricolari (un numero da 0 a 10 per metà byte, 15 = non disponibile) |
| 7 | carica (metà alta) + batteria custodia (metà bassa) |
| 8 | coperchio: bit `0x08` acceso = chiuso |
| 11-26 | parte cifrata con chiavi Apple: **non viene toccata** |

Il collegamento con un clic usa la stessa richiesta del pulsante *Connetti* di Windows
(`KSPROPERTY_ONESHOT_RECONNECT` del driver audio Bluetooth Microsoft), con le API
pubbliche di Windows e senza driver aggiuntivi.

## Cosa non fa (ancora), e perché

La **pausa automatica** quando togli un auricolare, la **batteria all'1%** e i comandi
ANC/trasparenza passano da un canale privato Apple (AAP) su Bluetooth L2CAP. Windows non
permette alle normali applicazioni di aprire canali L2CAP: serve un driver del kernel
firmato da Microsoft. Su Linux e Android questo canale è stato ricostruito dal progetto
[LibrePods](https://github.com/librepods-org/librepods), che è stato la fonte di
ispirazione. Il passaggio automatico tra dispositivi Apple e la sincronizzazione iCloud non
si possono replicare.

## Privacy

- Nessun dato lascia il PC. L'unica connessione a Internet è il controllo degli
  aggiornamenti verso l'API pubblica di GitHub.
- Vengono letti solo messaggi Bluetooth pubblici. Le parti cifrate con chiavi Apple non
  vengono toccate.

## Per sviluppatori

```
pip install bleak comtypes pillow pystray cryptography pyinstaller
python notifica.py          # avvia l'app da sorgente
python scanner.py 30        # stampa i messaggi BLE delle AirPods (debug)
crea_exe.bat                # crea dist\AnyAirpods.exe
python pubblica.py          # crea e firma una nuova versione da pubblicare
```

| File | Ruolo |
|---|---|
| `notifica.py` | app: popup, icona vicino all'orologio, aggiornamenti |
| `scanner.py` | lettura e decodifica dei messaggi BLE |
| `connetti.py` | collegamento con un clic e rilevamento del driver |
| `aggiornamento.py` | installazione e aggiornamenti firmati da GitHub Releases |
| `firma.py` | firma Ed25519 delle versioni (la chiave privata non è nel repository) |
| `avvio_automatico.py`, `icona.py`, `versione.py` | avvio con Windows, icona, versione |
---

## English summary

**AnyAirpods** brings the iPhone-style AirPods popup to Windows 10/11. Open the case near
your PC and a small window shows left, right and case battery levels. It also adds a tray
icon, one-click connect (with the Microsoft Bluetooth driver), start with Windows and
signed auto-updates. It only *listens* to the public Bluetooth LE "proximity pairing"
advertisement (Apple manufacturer data, type `0x07`) and never touches encrypted data.
Ear-detection auto-pause and ANC need Apple's private L2CAP channel, which Windows doesn't
expose to normal apps (a signed kernel driver would be required). Inspired by
[LibrePods](https://github.com/librepods-org/librepods).

---

*AnyAirpods è un progetto personale indipendente per l'interoperabilità e non è affiliato,
approvato o sponsorizzato da Apple Inc. AirPods e Beats sono marchi di Apple Inc.*
