"""
HiLook camera configuration.

Edit this file only to change the IP, user, password, or
the number/order of cameras. There is no need to touch modules/camaras.py.

It assumes the 8 cameras are connected to a single HiLook/Hikvision NVR
recorder, since that is how the deployment site is set up, so they
share the same IP, user and password, and each one is a different
NVR "channel".

Each channel N has TWO streams available on the NVR:
  - "N01" = mainstream: maximum resolution/quality, heavy.
  - "N02" = substream: low resolution/bitrate, lightweight.

"""

from .config import get as _env

# When the .env does not exist.
NVR_IP = _env("NVR_IP", "192.168.1.2")
NVR_USUARIO = _env("NVR_USUARIO", "admin")
NVR_PASSWORD = _env("NVR_PASSWORD", "cambia_esta_contraseña")
NVR_PUERTO = 554

# Delay (in seconds) applied to the live video to absorb
# network hiccups so it looks smooth instead of jerky. The more
# seconds, the more margin to absorb drops, but the more "behind"
# real time it is.
DELAY_SEGUNDOS = 5


def _url_canal(canal, sub):
    return (f"rtsp://{NVR_USUARIO}:{NVR_PASSWORD}@{NVR_IP}:{NVR_PUERTO}"
            f"/Streaming/Channels/{canal}0{sub}")


def _camara(numero, nombre):
    return {
        "nombre": nombre,
        "url_principal":  _url_canal(numero, 1),  # mainstream (enlarged view)
        "url_secundaria": _url_canal(numero, 2),  # substream  (mosaic)
    }


CAMARAS = [
    _camara(1, "Cámara 1"),
    _camara(2, "Cámara 2"),
    _camara(3, "Cámara 3"),
    _camara(4, "Cámara 4"),
    _camara(5, "Cámara 5"),
    _camara(7, "Cámara 7"),
    _camara(8, "Cámara 8"),
]