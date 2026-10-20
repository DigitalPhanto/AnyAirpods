"""Collega (o scollega) con un clic delle cuffie Bluetooth GIÀ ABBINATE a Windows.

Fa la stessa cosa del pulsante "Connetti" nelle impostazioni audio di Windows: cerca le
uscite audio con "AirPods" nel nome e manda al driver Bluetooth audio il comando
KSPROPERTY_ONESHOT_RECONNECT (è anche il metodo usato dal progetto open source ToothTray).
Usa solo API pubbliche di Windows (Core Audio + Kernel Streaming), niente driver.

Uso:  python connetti.py            (collega le AirPods)
      python connetti.py scollega   (scollega)
      python connetti.py elenco     (mostra solo cosa trova, non manda comandi)
"""
import sys
import winreg
from ctypes import (POINTER, Structure, Union, byref, c_ulong, c_ushort, c_void_p, c_wchar_p,
                    sizeof, windll)
from ctypes.wintypes import BOOL, DWORD, LPWSTR, UINT, ULONG

import comtypes
from comtypes import CLSCTX_ALL, COMMETHOD, GUID, HRESULT, IUnknown

# ---------------------------------------------------------------- tipi di Windows

class PROPERTYKEY(Structure):
    _fields_ = [("fmtid", GUID), ("pid", DWORD)]


class _PV_VALORE(Union):
    _fields_ = [("pwszVal", c_wchar_p), ("_spazio", c_void_p * 2)]


class PROPVARIANT(Structure):
    _fields_ = [("vt", c_ushort), ("r1", c_ushort), ("r2", c_ushort), ("r3", c_ushort),
                ("valore", _PV_VALORE)]


class KSPROPERTY(Structure):
    _fields_ = [("Set", GUID), ("Id", c_ulong), ("Flags", c_ulong)]


PKEY_Device_FriendlyName = PROPERTYKEY(GUID("{A45C254E-DF1C-4EFD-8020-67D146A850E0}"), 14)
KSPROPSETID_BtAudio = GUID("{7FA06C40-B8F6-4C7E-8556-E8C33A12E54D}")
KSPROPERTY_ONESHOT_RECONNECT = 0
KSPROPERTY_ONESHOT_DISCONNECT = 1
KSPROPERTY_TYPE_GET = 1
E_RENDER = 0                 # uscite audio
DEVICE_STATE_TUTTI = 0x0F    # anche quelle scollegate ("unplugged")
VT_LPWSTR = 31

# ---------------------------------------------------------------- interfacce COM
# L'ordine dei metodi deve essere identico a quello degli header di Windows.

class IPropertyStore(IUnknown):
    _iid_ = GUID("{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}")
    _methods_ = [
        COMMETHOD([], HRESULT, "GetCount", (["out"], POINTER(DWORD))),
        COMMETHOD([], HRESULT, "GetAt", (["in"], DWORD), (["out"], POINTER(PROPERTYKEY))),
        COMMETHOD([], HRESULT, "GetValue", (["in"], POINTER(PROPERTYKEY)),
                  (["in"], POINTER(PROPVARIANT))),
        COMMETHOD([], HRESULT, "SetValue", (["in"], POINTER(PROPERTYKEY)),
                  (["in"], POINTER(PROPVARIANT))),
        COMMETHOD([], HRESULT, "Commit"),
    ]


class IMMDevice(IUnknown):
    _iid_ = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
    _methods_ = [
        COMMETHOD([], HRESULT, "Activate", (["in"], POINTER(GUID)), (["in"], DWORD),
                  (["in"], c_void_p), (["out"], POINTER(POINTER(IUnknown)))),
        COMMETHOD([], HRESULT, "OpenPropertyStore", (["in"], DWORD),
                  (["out"], POINTER(POINTER(IPropertyStore)))),
        COMMETHOD([], HRESULT, "GetId", (["out"], POINTER(LPWSTR))),
        COMMETHOD([], HRESULT, "GetState", (["out"], POINTER(DWORD))),
    ]


class IMMDeviceCollection(IUnknown):
    _iid_ = GUID("{0BD7A1BE-7A1A-44DB-8397-CC5392387B5E}")
    _methods_ = [
        COMMETHOD([], HRESULT, "GetCount", (["out"], POINTER(UINT))),
        COMMETHOD([], HRESULT, "Item", (["in"], UINT), (["out"], POINTER(POINTER(IMMDevice)))),
    ]


class IMMDeviceEnumerator(IUnknown):
    _iid_ = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
    _methods_ = [
        COMMETHOD([], HRESULT, "EnumAudioEndpoints", (["in"], DWORD), (["in"], DWORD),
                  (["out"], POINTER(POINTER(IMMDeviceCollection)))),
        COMMETHOD([], HRESULT, "GetDefaultAudioEndpoint", (["in"], DWORD), (["in"], DWORD),
                  (["out"], POINTER(POINTER(IMMDevice)))),
        COMMETHOD([], HRESULT, "GetDevice", (["in"], LPWSTR),
                  (["out"], POINTER(POINTER(IMMDevice)))),
        # gli altri metodi non servono e non vengono chiamati
    ]


class IKsControl(IUnknown):
    _iid_ = GUID("{28F54685-06FD-11D2-B27A-00A0C9223196}")
    _methods_ = [
        COMMETHOD([], HRESULT, "KsProperty", (["in"], POINTER(KSPROPERTY)), (["in"], ULONG),
                  (["in"], c_void_p), (["in"], ULONG), (["in"], POINTER(ULONG))),
    ]


class IPart(IUnknown):
    _iid_ = GUID("{AE2DE0E4-5BCA-4F2D-AA46-5D13F8FDB3A9}")
    _methods_ = [
        COMMETHOD([], HRESULT, "GetName", (["out"], POINTER(LPWSTR))),
        COMMETHOD([], HRESULT, "GetLocalId", (["out"], POINTER(UINT))),
        COMMETHOD([], HRESULT, "GetGlobalId", (["out"], POINTER(LPWSTR))),
        COMMETHOD([], HRESULT, "GetPartType", (["out"], POINTER(DWORD))),
        COMMETHOD([], HRESULT, "GetSubType", (["out"], POINTER(GUID))),
        COMMETHOD([], HRESULT, "GetControlInterfaceCount", (["out"], POINTER(UINT))),
        COMMETHOD([], HRESULT, "GetControlInterface", (["in"], UINT),
                  (["out"], POINTER(c_void_p))),
        COMMETHOD([], HRESULT, "EnumPartsIncoming", (["out"], POINTER(c_void_p))),
        COMMETHOD([], HRESULT, "EnumPartsOutgoing", (["out"], POINTER(c_void_p))),
        COMMETHOD([], HRESULT, "GetTopologyObject", (["out"], POINTER(POINTER(IUnknown)))),
        COMMETHOD([], HRESULT, "Activate", (["in"], DWORD), (["in"], POINTER(GUID)),
                  (["out"], POINTER(POINTER(IUnknown)))),
    ]


class IConnector(IUnknown):
    _iid_ = GUID("{9C2C4058-23F5-41DE-877A-DF3AF236A09E}")
    _methods_ = [
        COMMETHOD([], HRESULT, "GetType", (["out"], POINTER(DWORD))),
        COMMETHOD([], HRESULT, "GetDataFlow", (["out"], POINTER(DWORD))),
        COMMETHOD([], HRESULT, "ConnectTo", (["in"], c_void_p)),
        COMMETHOD([], HRESULT, "Disconnect"),
        COMMETHOD([], HRESULT, "IsConnected", (["out"], POINTER(BOOL))),
        COMMETHOD([], HRESULT, "GetConnectedTo", (["out"], POINTER(POINTER(IUnknown)))),
    ]


class IDeviceTopology(IUnknown):
    _iid_ = GUID("{2A07407E-6497-4A18-9787-32F79BD0D98F}")
    _methods_ = [
        COMMETHOD([], HRESULT, "GetConnectorCount", (["out"], POINTER(UINT))),
        COMMETHOD([], HRESULT, "GetConnector", (["in"], UINT),
                  (["out"], POINTER(POINTER(IConnector)))),
        COMMETHOD([], HRESULT, "GetSubunitCount", (["out"], POINTER(UINT))),
        COMMETHOD([], HRESULT, "GetSubunit", (["in"], UINT), (["out"], POINTER(c_void_p))),
        COMMETHOD([], HRESULT, "GetPartById", (["in"], UINT), (["out"], POINTER(c_void_p))),
        COMMETHOD([], HRESULT, "GetDeviceId", (["out"], POINTER(LPWSTR))),
    ]


CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")

# ---------------------------------------------------------------- logica


def trova_airpods_abbinate():
    """Indirizzi Bluetooth di tutte le voci "AirPods" abbinate a Windows (lista, anche vuota).
    Windows tiene l'elenco dei dispositivi abbinati nel registro. Possono essere più d'una:
    dopo il riabbinamento è comparsa "AirPods di <nome> #2 - Find My", ed è quella che porta
    l'audio, nonostante il nome."""
    chiave = r"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices"
    trovati = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, chiave) as dispositivi:
            i = 0
            while True:
                try:
                    indirizzo = winreg.EnumKey(dispositivi, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(dispositivi, indirizzo) as d:
                        nome = winreg.QueryValueEx(d, "Name")[0]
                except OSError:
                    continue
                nome = bytes(nome).rstrip(b"\0").decode("utf-8", "replace")
                if "airpods" in nome.lower():
                    trovati.append(int(indirizzo, 16))
    except OSError:
        pass
    return trovati


def _nome(dispositivo):
    pv = PROPVARIANT()
    try:
        negozio = dispositivo.OpenPropertyStore(0)  # 0 = STGM_READ
        negozio.GetValue(byref(PKEY_Device_FriendlyName), byref(pv))
    except comtypes.COMError:
        return ""  # dispositivo "fantasma" (rimosso ma rimasto in elenco)
    nome = pv.valore.pwszVal if pv.vt == VT_LPWSTR else ""
    windll.ole32.PropVariantClear(byref(pv))
    return nome or ""


def _ks_control(enum, dispositivo):
    """Dall'uscita audio risale al driver Bluetooth audio (IKsControl):
    uscita -> connettore -> parte collegata -> sua topologia -> id del driver -> IKsControl."""
    topologia = dispositivo.Activate(byref(IDeviceTopology._iid_), CLSCTX_ALL, None)
    topologia = topologia.QueryInterface(IDeviceTopology)
    connettore = topologia.GetConnector(0)
    altro = connettore.GetConnectedTo().QueryInterface(IPart)
    topologia_driver = altro.GetTopologyObject().QueryInterface(IDeviceTopology)
    id_driver = topologia_driver.GetDeviceId()  # per il Bluetooth contiene l'indirizzo
    driver = enum.GetDevice(id_driver)
    ks = driver.Activate(byref(IKsControl._iid_), CLSCTX_ALL, None)
    return ks.QueryInterface(IKsControl), id_driver.lower()


def _connetti(parola, indirizzi, comando):
    enum = comtypes.CoCreateInstance(CLSID_MMDeviceEnumerator, IMMDeviceEnumerator,
                                     CLSCTX_ALL)
    uscite = enum.EnumAudioEndpoints(E_RENDER, DEVICE_STATE_TUTTI)
    fatti = []
    for i in range(uscite.GetCount()):
        dispositivo = uscite.Item(i)
        nome = _nome(dispositivo)
        try:
            ks, id_driver = _ks_control(enum, dispositivo)
        except comtypes.COMError:
            continue  # non è un'uscita Bluetooth (o è un dispositivo fantasma)
        # È lei se il nome contiene la parola, o l'id del driver contiene l'indirizzo.
        # Col driver Broadcom di questo PC c'è invece un'unica uscita generica
        # "Audio Bluetooth" (indirizzo 000000000000) per tutte le cuffie: si prova quella.
        generica = "bthenum" in id_driver and "000000000000" in id_driver
        if not (parola.lower() in nome.lower() or generica
                or any(f"{a:012x}" in id_driver for a in indirizzi)):
            continue
        if comando is None:  # solo elenco, non manda niente
            fatti.append(nome)
            continue
        prop = KSPROPERTY(KSPROPSETID_BtAudio, comando, KSPROPERTY_TYPE_GET)
        restituiti = ULONG(0)
        try:
            ks.KsProperty(byref(prop), sizeof(prop), None, 0, byref(restituiti))
            fatti.append(nome)
        except comtypes.COMError as e:
            print(f"{nome}: comando rifiutato ({e})")
    return fatti


def ha_uscita_dedicata(indirizzi):
    """True se Windows ha un'uscita audio legata proprio a queste AirPods (driver Bluetooth
    Microsoft): solo allora il collegamento con un clic e lo stato "collegate" sono
    affidabili. Con driver come Broadcom c'è solo un'uscita generica -> False."""
    def cerca():
        enum = comtypes.CoCreateInstance(CLSID_MMDeviceEnumerator, IMMDeviceEnumerator,
                                         CLSCTX_ALL)
        uscite = enum.EnumAudioEndpoints(E_RENDER, DEVICE_STATE_TUTTI)
        for i in range(uscite.GetCount()):
            try:
                _, id_driver = _ks_control(enum, uscite.Item(i))
            except comtypes.COMError:
                continue
            if any(f"{a:012x}" in id_driver for a in indirizzi):
                return True
        return False

    if not indirizzi:
        return False
    comtypes.CoInitialize()
    try:
        return cerca()
    finally:
        comtypes.CoUninitialize()


def connetti(parola="airpods", indirizzi=(), scollega=False, solo_elenco=False):
    """Restituisce l'elenco dei nomi delle uscite a cui è stato mandato il comando.
    indirizzi = indirizzi Bluetooth (interi) delle cuffie, se noti.
    Si può chiamare da qualsiasi thread (inizializza COM per conto suo)."""
    if solo_elenco:
        comando = None
    else:
        comando = KSPROPERTY_ONESHOT_DISCONNECT if scollega else KSPROPERTY_ONESHOT_RECONNECT
    comtypes.CoInitialize()
    try:
        # in una funzione separata: gli oggetti COM vengono rilasciati prima di CoUninitialize
        return _connetti(parola, indirizzi, comando)
    finally:
        comtypes.CoUninitialize()


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    scollega = arg == "scollega"
    fatti = connetti(indirizzi=trova_airpods_abbinate(), scollega=scollega,
                     solo_elenco=arg == "elenco")
    if fatti and arg == "elenco":
        print("Uscite audio Bluetooth 'AirPods' trovate (nessun comando mandato):")
        for n in fatti:
            print("  -", n)
    elif fatti:
        print(("Scollegamento" if scollega else "Collegamento") + " richiesto per:")
        for n in fatti:
            print("  -", n)
    else:
        print("Nessuna uscita audio delle AirPods in Windows: se sono abbinate, "
              "rimuovile dalle impostazioni Bluetooth e riabbinale.")
