"""
Per-machine activation.

The first time the program is opened on a PC it asks for an ACTIVATION
KEY that is unique to that machine. Without that key, the program does not start.

How it works:
  1. The program computes a "machine code" from data specific to
     that PC (network MAC + machine name). Each PC has a different code.
  2. That code is shown to the person on screen the first time.

  3. That code is sent to the owner of the program, who runs an
     activation script that generates a key for it.

  4. They send that key back, it is typed in just once, and the program
     saves it in data/.licencia.

  5. Every time the program is opened, it re-checks that the
     code of THAT machine is still valid for the saved key.
     If someone copies the whole folder to another PC, the machine code
     changes and it asks for a key again, which only the owner can generate.


Note: I am aware that this is not a foolproof system, but at least
it makes someone have to do a bit of digging.
"""

import hashlib
import hmac
import os
import platform
import socket
import uuid

from .rutas_base import carpeta_base
from .config import get as _env

# Activation secret, loaded from the .env file (LICENSE_SECRET). It must be identical
# to the one used by the key-generator script (kept private, NOT part of this repository).
_SECRETO = _env("LICENSE_SECRET", "REPLACE_WITH_YOUR_OWN_SECRET")

_ARCHIVO_LICENCIA = os.path.join(carpeta_base(), "data", ".licencia")


def _guid_windows():
    """Windows MachineGuid: unique identifier per installation,
       it does not change if WiFi is disconnected, the router is changed, etc.
       It only exists on Windows."""
    try:
        import winreg
        clave = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
        )
        valor, _ = winreg.QueryValueEx(clave, "MachineGuid")
        return valor
    except Exception:
        return None


def codigo_de_equipo():
    """Stable identifier for this PC.

    On Windows it uses the system MachineGuid (fixed per installation).
    If it is not available, it falls back to the network MAC + machine name.
    """
    base = _guid_windows()
    if not base:
        base = f"{uuid.getnode()}"
    datos = f"{base}-{platform.node()}-{socket.gethostname()}"
    h = hashlib.sha256(datos.encode()).hexdigest()[:16].upper()
    return "-".join(h[i:i + 4] for i in range(0, 16, 4))


def _clave_esperada(codigo_equipo):
    """Computes the valid activation key for a given machine code.
    """
    h = hmac.new(
        _SECRETO.encode(), codigo_equipo.encode(), hashlib.sha256
    ).hexdigest()[:16].upper()
    return "-".join(h[i:i + 4] for i in range(0, 16, 4))


def _leer_licencia_guardada():
    if not os.path.exists(_ARCHIVO_LICENCIA):
        return None
    with open(_ARCHIVO_LICENCIA, "r", encoding="utf-8") as f:
        return f.read().strip()


def _guardar_licencia(clave):
    os.makedirs(os.path.dirname(_ARCHIVO_LICENCIA), exist_ok=True)
    with open(_ARCHIVO_LICENCIA, "w", encoding="utf-8") as f:
        f.write(clave)


def licencia_valida():
    """True if a key is already saved and it matches the current machine."""
    guardada = _leer_licencia_guardada()
    if not guardada:
        return False
    return guardada == _clave_esperada(codigo_de_equipo())


def activar_con_clave(clave_ingresada):
    """Tries to activate with the key the user typed.

    If it matches what is expected for this machine, it saves it and returns
    True. If it is not what is expected... it returns False without saving anything.
    """
    clave_ingresada = clave_ingresada.strip().upper()
    if clave_ingresada == _clave_esperada(codigo_de_equipo()):
        _guardar_licencia(clave_ingresada)
        return True
    return False
