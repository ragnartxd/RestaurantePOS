"""
Code split into:

    caja/logica.py    -> business rules (drinks, variants, DB)
    caja/dialogos.py  -> popup windows (design / Tkinter)
    caja/interfaz.py  -> CajaModule, the main panel (design + orchestration)

"""

from .logica import (
    GRUPOS_VARIANTES,
    ALMUERZOS_LIMONADA,
    BEBIDAS_DESAYUNO,
    BEBIDAS_ALMUERZO,
    recalcular_bebidas_pedido,
    calcular_bebidas_incluidas,
    es_bebida_desayuno,
    es_bebida_almuerzo,
)
from .dialogos import CobroVentana, DividirCuentaVentana, EditarPrecioVentana
from .interfaz import CajaModule

__all__ = [
    "GRUPOS_VARIANTES",
    "ALMUERZOS_LIMONADA",
    "BEBIDAS_DESAYUNO",
    "BEBIDAS_ALMUERZO",
    "recalcular_bebidas_pedido",
    "calcular_bebidas_incluidas",
    "es_bebida_desayuno",
    "es_bebida_almuerzo",
    "CobroVentana",
    "DividirCuentaVentana",
    "EditarPrecioVentana",
    "CajaModule",
]