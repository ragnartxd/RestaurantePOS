"""
Loads sensitive credentials (passwords, IPs, PIN) from a
.env file that lives next to the program (same folder as data/), instead of
having them written directly in the source code.

It uses no external library (python-dotenv, etc.) so as not to complicate
packaging with PyInstaller: it simply reads the .env file by hand.

It looks for the .env in this priority order:
1. Persistent data folder (%LOCALAPPDATA% on Windows)
2. Executable folder (where the .exe or main.py is)
3. data/ folder

"""

import os
import sys

from .rutas_base import carpeta_ejecutable, carpeta_base

_valores = None


def _obtener_rutas_posibles():
    """
    Returns a list of locations where to look for the .env,
    in priority order.
    """
    rutas = []
    
    # 1. Persistent data folder (the most important when packaged)
    carpeta_datos = carpeta_base()
    rutas.append(os.path.join(carpeta_datos, ".env"))
    
    # 2. data/ folder
    rutas.append(os.path.join(carpeta_datos, "data", ".env"))
    
    # 3. Executable folder
    carpeta_exe = carpeta_ejecutable()
    if carpeta_exe != carpeta_datos:  # Avoid duplicates
        rutas.append(os.path.join(carpeta_exe, ".env"))
    
    return rutas


def _encontrar_env():
    """
    Looks for the .env file in the possible paths.
    Returns the path of the first .env found, or None if none exists.
    """
    for ruta in _obtener_rutas_posibles():
        if os.path.exists(ruta):
            return ruta
    return None


def _cargar():
    global _valores
    if _valores is not None:
        return _valores

    encontrados = {}
    env_path = _encontrar_env()
    
    if env_path:
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for linea in f:
                    linea = linea.strip()
                    if not linea or linea.startswith("#") or "=" not in linea:
                        continue
                    clave, _, valor = linea.partition("=")
                    encontrados[clave.strip()] = valor.strip().strip('"').strip("'")
        except Exception as e:
            print(f"\u26a0\ufe0f  Error leyendo {env_path}: {e}")
    else:
        rutas_buscadas = "\n    ".join(_obtener_rutas_posibles())
        print(
            "\u26a0\ufe0f  No se encontró el archivo .env en ninguna de estas ubicaciones:\n"
            f"    {rutas_buscadas}\n"
            "    Se están usando las contraseñas por defecto del código.\n"
            "    Crea un .env en cualquiera de esas carpetas con tus contraseñas reales."
        )

    _valores = encontrados
    return encontrados


def get(clave, valor_por_defecto=None):
    """Reads a variable from the .env; if it is not there, looks at the system environment;
    if it is not there either, returns valor_por_defecto."""
    valores = _cargar()
    if clave in valores:
        return valores[clave]
    if clave in os.environ:
        return os.environ[clave]
    return valor_por_defecto