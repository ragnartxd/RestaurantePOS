import os
import sys
import shutil


NOMBRE_APP = "RestaurantePOS"


def _carpeta_datos_persistente():

    base_appdata = os.environ.get("LOCALAPPDATA")
    if not base_appdata:
        base_appdata = os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base_appdata, NOMBRE_APP)


def _migrar_datos_legacy_si_hace_falta(carpeta_exe, destino):
    destino_data = os.path.join(destino, "data")
    origen_data = os.path.join(carpeta_exe, "data")

    ya_tiene_datos = os.path.exists(os.path.join(destino_data, "menu.json"))
    if ya_tiene_datos:
        return  # the persistent destination already has its own data: do not touch

    if os.path.isdir(origen_data):
        os.makedirs(destino_data, exist_ok=True)
        for nombre in os.listdir(origen_data):
            origen_item = os.path.join(origen_data, nombre)
            destino_item = os.path.join(destino_data, nombre)
            if not os.path.exists(destino_item):
                try:
                    if os.path.isdir(origen_item):
                        shutil.copytree(origen_item, destino_item)
                    else:
                        shutil.copy2(origen_item, destino_item)
                except OSError:
                    pass  # if copying something specific fails, we carry on anyway


def carpeta_base():
    if getattr(sys, "frozen", False):
        carpeta_exe = os.path.dirname(os.path.abspath(sys.executable))
        destino = _carpeta_datos_persistente()
        os.makedirs(destino, exist_ok=True)
        _migrar_datos_legacy_si_hace_falta(carpeta_exe, destino)
        return destino
    # Development mode: project root (one level above modules/)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def carpeta_ejecutable():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))