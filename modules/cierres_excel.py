"""
Shared path of the daily cash-close Excel file.

Both `reportes.py` (which generates it when closing the register) and
`dashboard_server.py` (which serves it for download from the browser)
import these two functions, so that both always agree on where
the day's file lives — this prevents one from saving in one place and the other
looking in another.
"""

import os
from datetime import datetime

from modules.rutas_base import carpeta_base


def carpeta_cierres_excel():
    """Folder where the daily Excel files are saved (created if it does not exist)."""
    carpeta = os.path.join(carpeta_base(), "data", "cierres_excel")
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


def ruta_excel_dia(fecha=None):
    """Path of the day's Excel file. `fecha` in 'YYYY-MM-DD' format; if not
    given, uses today."""
    fecha = fecha or datetime.now().strftime("%Y-%m-%d")
    return os.path.join(carpeta_cierres_excel(), f"Cierre_{fecha}.xlsx")