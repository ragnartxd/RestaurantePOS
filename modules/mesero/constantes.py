"""
Constants and configuration data for the order web server
(PIN, port, and the product variant groups shared
with the logic in caja.py).
"""

from ..config import get as _env

PIN_ACCESO = _env("PIN_ACCESO", "1234")
PUERTO     = 5050

# Variant groups (logic shared with caja.py)
GRUPOS_VARIANTES_WEB = {
    "Ejecutivo turista": {
        "variantes": ["Res", "Cerdo", "Pechuga"],
        "nombres": {
            "Res":     "Ejecutivo res turista",
            "Cerdo":   "Ejecutivo cerdo turista",
            "Pechuga": "Ejecutivo pechuga turista",
        }
    },
    "Ejecutivo mulero": {
        "variantes": ["Res", "Cerdo", "Pechuga"],
        "nombres": {
            "Res":     "Ejecutivo res mulero",
            "Cerdo":   "Ejecutivo cerdo mulero",
            "Pechuga": "Ejecutivo pechuga mulero",
        }
    },
    "Del día turista": {
        "variantes": ["Res", "Cerdo", "Pechuga"],
        "nombres": {
            "Res":     "Del día res turista",
            "Cerdo":   "Del día cerdo turista",
            "Pechuga": "Del día pechuga turista",
        }
    },
    "Del día mulero": {
        "variantes": ["Res", "Cerdo", "Pechuga"],
        "nombres": {
            "Res":     "Del día res mulero",
            "Cerdo":   "Del día cerdo mulero",
            "Pechuga": "Del día pechuga mulero",
        }
    },
    "Bandeja": {
        "variantes": ["Res", "Cerdo", "pechuga"],
        "nombres": {
            "Res":   "Bandeja de res",
            "Cerdo": "Bandeja de cerdo",
            "pechuga": "Bandeja de pechuga",
        }
    },
    "Bandeja de huevos": {
        "variantes": [
            "Pericos",
            "Revueltos",
            "Rancheros",
            "Fritos",
            "Tortilla",
            "Duros/cocidos",
            "Omelet",
        ],
        "nombres": {
            "Pericos":       "Bandeja de huevos pericos",
            "Revueltos":     "Bandeja de huevos revueltos",
            "Rancheros":     "Bandeja de huevos rancheros",
            "Fritos":        "Bandeja de huevos fritos",
            "Tortilla":      "Bandeja de huevos tortilla",
            "Duros/cocidos": "Bandeja de huevos duros/cocidos",
            "Omelet":        "Bandeja de huevos omelet",
        }
    },
    # Combos
    "Combo turista": {
        "variantes": [
            "Costilla + Revueltos", "Costilla + Rancheros", "Costilla + Pericos",
            "Huevo + Revueltos", "Huevo + Rancheros", "Huevo + Pericos",
            "Changua + Revueltos", "Changua + Rancheros", "Changua + Pericos",
            "Costilla c/huevo + Revueltos", "Costilla c/huevo + Rancheros", "Costilla c/huevo + Pericos",
            "Costilla + Bandeja res", "Costilla + Bandeja cerdo", "Costilla + Bandeja pechuga",
        ],
        "nombres": {
            "Costilla + Revueltos": "Combo caldo pequeño costilla + huevos revueltos",
            "Costilla + Rancheros": "Combo caldo pequeño costilla + huevos rancheros",
            "Costilla + Pericos":   "Combo caldo pequeño costilla + huevos pericos",
            "Huevo + Revueltos":    "Combo caldo pequeño huevo + huevos revueltos",
            "Huevo + Rancheros":    "Combo caldo pequeño huevo + huevos rancheros",
            "Huevo + Pericos":      "Combo caldo pequeño huevo + huevos pericos",
            "Changua + Revueltos":  "Combo caldo pequeño changua + huevos revueltos",
            "Changua + Rancheros":  "Combo caldo pequeño changua + huevos rancheros",
            "Changua + Pericos":    "Combo caldo pequeño changua + huevos pericos",
            "Costilla c/huevo + Revueltos": "Combo caldo pequeño costilla con huevo + huevos revueltos",
            "Costilla c/huevo + Rancheros": "Combo caldo pequeño costilla con huevo + huevos rancheros",
            "Costilla c/huevo + Pericos":   "Combo caldo pequeño costilla con huevo + huevos pericos",
            "Costilla + Bandeja res":     "Combo caldo pequeño de costilla + bandeja de res",
            "Costilla + Bandeja cerdo":   "Combo caldo pequeño de costilla + bandeja de cerdo",
            "Costilla + Bandeja pechuga": "Combo caldo pequeño de costilla + bandeja de pechuga",
        }
    },
    # Transporter combo
    "Combo transportador": {
        "variantes": [
            "Costilla + Revueltos", "Costilla + Rancheros", "Costilla + Pericos",
            "Costilla + Tortilla", "Costilla + Fritos", "Costilla + Duros/cocidos", "Costilla + Omelet",
            "Huevo + Revueltos", "Huevo + Rancheros", "Huevo + Pericos",
            "Huevo + Tortilla", "Huevo + Fritos", "Huevo + Duros/cocidos", "Huevo + Omelet",
            "Changua + Revueltos", "Changua + Rancheros", "Changua + Pericos",
            "Changua + Tortilla", "Changua + Fritos", "Changua + Duros/cocidos", "Changua + Omelet",
            "Costilla + Bandeja res", "Costilla + Bandeja cerdo", "Costilla + Bandeja pechuga",
            "Huevo + Bandeja res", "Huevo + Bandeja cerdo", "Huevo + Bandeja pechuga",
            "Changua + Bandeja res", "Changua + Bandeja cerdo", "Changua + Bandeja pechuga",
        ],
        "nombres": {
            "Costilla + Revueltos": "Transportador caldo pequeño costilla + huevos revueltos",
            "Costilla + Rancheros": "Transportador caldo pequeño costilla + huevos rancheros",
            "Costilla + Pericos":   "Transportador caldo pequeño costilla + huevos pericos",
            "Costilla + Tortilla":  "Transportador caldo pequeño costilla + huevos tortilla",
            "Costilla + Fritos":    "Transportador caldo pequeño costilla + huevos fritos",
            "Costilla + Duros/cocidos": "Transportador caldo pequeño costilla + huevos duros/cocidos",
            "Costilla + Omelet":    "Transportador caldo pequeño costilla + huevos omelet",
            "Huevo + Revueltos":    "Transportador caldo pequeño huevo + huevos revueltos",
            "Huevo + Rancheros":    "Transportador caldo pequeño huevo + huevos rancheros",
            "Huevo + Pericos":      "Transportador caldo pequeño huevo + huevos pericos",
            "Huevo + Tortilla":     "Transportador caldo pequeño huevo + huevos tortilla",
            "Huevo + Fritos":       "Transportador caldo pequeño huevo + huevos fritos",
            "Huevo + Duros/cocidos": "Transportador caldo pequeño huevo + huevos duros/cocidos",
            "Huevo + Omelet":       "Transportador caldo pequeño huevo + huevos omelet",
            "Changua + Revueltos":  "Transportador caldo pequeño changua + huevos revueltos",
            "Changua + Rancheros":  "Transportador caldo pequeño changua + huevos rancheros",
            "Changua + Pericos":    "Transportador caldo pequeño changua + huevos pericos",
            "Changua + Tortilla":   "Transportador caldo pequeño changua + huevos tortilla",
            "Changua + Fritos":     "Transportador caldo pequeño changua + huevos fritos",
            "Changua + Duros/cocidos": "Transportador caldo pequeño changua + huevos duros/cocidos",
            "Changua + Omelet":     "Transportador caldo pequeño changua + huevos omelet",
            "Costilla + Bandeja res":     "Transportador caldo pequeño costilla + res",
            "Costilla + Bandeja cerdo":   "Transportador caldo pequeño costilla + cerdo",
            "Costilla + Bandeja pechuga": "Transportador caldo pequeño costilla + pechuga",
            "Huevo + Bandeja res":     "Transportador caldo pequeño huevo + res",
            "Huevo + Bandeja cerdo":   "Transportador caldo pequeño huevo + cerdo",
            "Huevo + Bandeja pechuga": "Transportador caldo pequeño huevo + pechuga",
            "Changua + Bandeja res":     "Transportador caldo pequeño changua + res",
            "Changua + Bandeja cerdo":   "Transportador caldo pequeño changua + cerdo",
            "Changua + Bandeja pechuga": "Transportador caldo pequeño changua + pechuga",
        }
    },
    # Broths
    "Caldo grande + arepa": {
        "variantes": ["Costilla", "Huevo", "Changua", "Costilla c/huevo"],
        "nombres": {
            "Costilla":         "Caldo grande costilla",
            "Huevo":            "Caldo grande de huevo",
            "Changua":          "Caldo grande de changua",
            "Costilla c/huevo": "Caldo grande de costilla con huevo",
        }
    },

    "Caldo pequeño + arepa": {
        "variantes": ["Costilla", "Huevo", "Changua", "Costilla c/huevo"],
        "nombres": {
            "Costilla":         "Caldo pequeño costilla + arepa",
            "Huevo":            "Caldo pequeño de huevo + arepa",
            "Changua":          "Caldo pequeño de changua + arepa",
            "Costilla c/huevo": "Caldo pequeño de costilla con huevo + arepa",
        }
    },

    "Caldo pequeño": {
        "variantes": ["Costilla", "Huevo", "Changua", "Costilla c/huevo"],
        "nombres": {
            "Costilla":         "Caldo pequeño costilla",
            "Huevo":            "Caldo pequeño de huevo",
            "Changua":          "Caldo pequeño de changua",
            "Costilla c/huevo": "Caldo pequeño de costilla con huevo",
        }
    },
}

_NOMBRES_EN_GRUPO_WEB = {
    nombre_real
    for g in GRUPOS_VARIANTES_WEB.values()
    for nombre_real in g["nombres"].values()
}