"""
Pure cash register business logic

Contains the included-drinks rules, the product variant groups
and the functions that recalculate which drinks are included
or charged in an order.
"""

# ── Included drinks rules ─────────────────────────────────────────────────────
def _desayuno_incluye_bebida(nombre_lower):
    """
    Determines whether a Breakfast dish comes with 1 included drink, according to the
    menu descriptions "Includes 1 drink":
      - Eggs (scrambled/ranchero/pericos/omelette/fried/boiled) at 19000  -> included
      - Egg portion (12,000, no drink) -> NOT included
      - Large broth (rib/egg/changua/rib w/ egg) -> included
      - Small broth alone or + arepa (no combo or platter) -> NOT included
      - Broth + eggs / broth + platter combos -> included
      - Platter (beef/pork/chicken breast) -> included
      - Loose portions (rib, chicken breast, pork, beef, rice, bread,
        arepa, cheese)                                                   -> NOT included
    """
    n = nombre_lower
    if "porcion" in n or "porción" in n:
        return False
    if "caldo pequeño" in n and "combo" not in n and "bandeja" not in n and "transportador" not in n:
        return False
    if "huevos" in n or "caldo grande" in n or "bandeja" in n or "combo" in n or "transportador" in n:
        return True
    return False


ALMUERZOS_LIMONADA = {
    "ejecutivo turista":  1,
    "ejecutivo mulero":   1,
    "del día turista":    1,
    "del día mulero":     1,
}

BEBIDAS_DESAYUNO = {"café", "chocolate", "tinto", "limonada"}
BEBIDAS_ALMUERZO = {"limonada"}

# ── Variant groups ────────────────────────────────────────────────────────────

GRUPOS_VARIANTES = {
    # Lunches
    "Ejecutivo turista": [
        ("Res",     "Ejecutivo res turista"),
        ("Cerdo",   "Ejecutivo cerdo turista"),
        ("Pechuga", "Ejecutivo pechuga turista"),
    ],
    "Ejecutivo mulero": [
        ("Res",     "Ejecutivo res mulero"),
        ("Cerdo",   "Ejecutivo cerdo mulero"),
        ("Pechuga", "Ejecutivo pechuga mulero"),
    ],
    "Del día turista": [
        ("Res",     "Del día res turista"),
        ("Cerdo",   "Del día cerdo turista"),
        ("Pechuga", "Del día pechuga turista"),
    ],
    "Del día mulero": [
        ("Res",     "Del día res mulero"),
        ("Cerdo",   "Del día cerdo mulero"),
        ("Pechuga", "Del día pechuga mulero"),
    ],
    # Breakfast – platters
    "Bandeja": [
        ("Res",    "Bandeja de res"),
        ("Cerdo",  "Bandeja de cerdo"),
        ("pechuga",  "Bandeja de pechuga"),
    ],
    "Bandeja de huevos": [
        ("Pericos",       "Bandeja de huevos pericos"),
        ("Revueltos",     "Bandeja de huevos revueltos"),
        ("Rancheros",     "Bandeja de huevos rancheros"),
        ("Fritos",        "Bandeja de huevos fritos"),
        ("Tortilla",      "Bandeja de huevos tortilla"),
        ("Duros/cocidos", "Bandeja de huevos duros/cocidos"),
        ("Omelet",        "Bandeja de huevos omelet"),
    ],
    # Combos
    "Combo turista": [
        ("Costilla + Revueltos", "Combo caldo pequeño costilla + huevos revueltos"),
        ("Costilla + Rancheros", "Combo caldo pequeño costilla + huevos rancheros"),
        ("Costilla + Pericos",   "Combo caldo pequeño costilla + huevos pericos"),
        ("Huevo + Revueltos",    "Combo caldo pequeño huevo + huevos revueltos"),
        ("Huevo + Rancheros",    "Combo caldo pequeño huevo + huevos rancheros"),
        ("Huevo + Pericos",      "Combo caldo pequeño huevo + huevos pericos"),
        ("Changua + Revueltos",  "Combo caldo pequeño changua + huevos revueltos"),
        ("Changua + Rancheros",  "Combo caldo pequeño changua + huevos rancheros"),
        ("Changua + Pericos",    "Combo caldo pequeño changua + huevos pericos"),
        ("Costilla c/huevo + Revueltos", "Combo caldo pequeño costilla con huevo + huevos revueltos"),
        ("Costilla c/huevo + Rancheros", "Combo caldo pequeño costilla con huevo + huevos rancheros"),
        ("Costilla c/huevo + Pericos",   "Combo caldo pequeño costilla con huevo + huevos pericos"),
        ("Costilla + Bandeja res",     "Combo caldo pequeño de costilla + bandeja de res"),
        ("Costilla + Bandeja cerdo",   "Combo caldo pequeño de costilla + bandeja de cerdo"),
        ("Costilla + Bandeja pechuga", "Combo caldo pequeño de costilla + bandeja de pechuga"),
    ],
    # Transporter combo
    "Combo transportador": [
        ("Costilla + Revueltos", "Transportador caldo pequeño costilla + huevos revueltos"),
        ("Costilla + Rancheros", "Transportador caldo pequeño costilla + huevos rancheros"),
        ("Costilla + Pericos",   "Transportador caldo pequeño costilla + huevos pericos"),
        ("Costilla + Tortilla",  "Transportador caldo pequeño costilla + huevos tortilla"),
        ("Costilla + Fritos",    "Transportador caldo pequeño costilla + huevos fritos"),
        ("Costilla + Duros/cocidos", "Transportador caldo pequeño costilla + huevos duros/cocidos"),
        ("Costilla + Omelet",    "Transportador caldo pequeño costilla + huevos omelet"),
        ("Huevo + Revueltos",    "Transportador caldo pequeño huevo + huevos revueltos"),
        ("Huevo + Rancheros",    "Transportador caldo pequeño huevo + huevos rancheros"),
        ("Huevo + Pericos",      "Transportador caldo pequeño huevo + huevos pericos"),
        ("Huevo + Tortilla",     "Transportador caldo pequeño huevo + huevos tortilla"),
        ("Huevo + Fritos",       "Transportador caldo pequeño huevo + huevos fritos"),
        ("Huevo + Duros/cocidos", "Transportador caldo pequeño huevo + huevos duros/cocidos"),
        ("Huevo + Omelet",       "Transportador caldo pequeño huevo + huevos omelet"),
        ("Changua + Revueltos",  "Transportador caldo pequeño changua + huevos revueltos"),
        ("Changua + Rancheros",  "Transportador caldo pequeño changua + huevos rancheros"),
        ("Changua + Pericos",    "Transportador caldo pequeño changua + huevos pericos"),
        ("Changua + Tortilla",   "Transportador caldo pequeño changua + huevos tortilla"),
        ("Changua + Fritos",     "Transportador caldo pequeño changua + huevos fritos"),
        ("Changua + Duros/cocidos", "Transportador caldo pequeño changua + huevos duros/cocidos"),
        ("Changua + Omelet",     "Transportador caldo pequeño changua + huevos omelet"),
        ("Costilla + Bandeja res",     "Transportador caldo pequeño costilla + res"),
        ("Costilla + Bandeja cerdo",   "Transportador caldo pequeño costilla + cerdo"),
        ("Costilla + Bandeja pechuga", "Transportador caldo pequeño costilla + pechuga"),
        ("Huevo + Bandeja res",     "Transportador caldo pequeño huevo + res"),
        ("Huevo + Bandeja cerdo",   "Transportador caldo pequeño huevo + cerdo"),
        ("Huevo + Bandeja pechuga", "Transportador caldo pequeño huevo + pechuga"),
        ("Changua + Bandeja res",     "Transportador caldo pequeño changua + res"),
        ("Changua + Bandeja cerdo",   "Transportador caldo pequeño changua + cerdo"),
        ("Changua + Bandeja pechuga", "Transportador caldo pequeño changua + pechuga"),
    ],
    # Broths
    "Caldo grande": [
        ("Costilla", "Caldo grande costilla"),
        ("Huevo", "Caldo grande de huevo"),
        ("Changua", "Caldo grande de changua"),
        ("Costilla c/huevo", "Caldo grande de costilla con huevo"),
    ],

    "Caldo pequeño + arepa": [
        ("Costilla", "Caldo pequeño costilla + arepa"),
        ("Huevo", "Caldo pequeño de huevo + arepa"),
        ("Changua", "Caldo pequeño de changua + arepa"),
        ("Costilla c/huevo", "Caldo pequeño de costilla con huevo + arepa"),
    ],

    "Caldo pequeño": [
        ("Costilla", "Caldo pequeño costilla"),
        ("Huevo", "Caldo pequeño de huevo"),
        ("Changua", "Caldo pequeño de changua"),
        ("Costilla c/huevo", "Caldo pequeño de costilla con huevo"),
    ],
}

# Real names that belong to a group; with this they get hidden
_NOMBRES_EN_GRUPO = {
    nombre_real
    for variantes in GRUPOS_VARIANTES.values()
    for _, nombre_real in variantes
}


def recalcular_bebidas_pedido(conn, menu_db, pedido_id):
    """
    Reassigns which drinks in the order are included (free) and which are charged,
    based on ALL the dishes and drinks already added to the order,
    regardless of whether the drink was registered before or after the dish that includes it.
 
    `conn` is the active sqlite3 connection (the one from CajaModule or the one
    the waitstaff Flask server opens for each order). `menu_db` is the
    Database instance, used only to look up the current menu price
    of each drink.
 
    Drink lines with a manually edited price are
    left untouched, so that edit and its audit trail are not lost.
    """
    lineas = conn.execute(
        "SELECT * FROM lineas_pedido WHERE pedido_id=? ORDER BY id", (pedido_id,)
    ).fetchall()
 
    comidas = []
    bebidas = {}
    for l in lineas:
        nombre_lower = l["nombre_producto"].lower().strip()
        editado = bool(l["precio_editado"]) if "precio_editado" in l.keys() else False
        if (nombre_lower in BEBIDAS_DESAYUNO or nombre_lower in BEBIDAS_ALMUERZO) and not editado:
            info = bebidas.setdefault(nombre_lower, {
                "nombre_real": l["nombre_producto"],
                "producto_id": None,
                "precio_menu": 0.0,
                "cantidad": 0,
                "comentario": "",
                "primer_id": l["id"],
                "ids": [],
            })
            info["cantidad"] += l["cantidad"]
            info["ids"].append(l["id"])
            info["primer_id"] = min(info["primer_id"], l["id"])
            linea_ronda = l["ronda"] if "ronda" in l.keys() and l["ronda"] else 1
            info["ronda"] = max(info.get("ronda", 1), linea_ronda)
            if l["producto_id"]:
                info["producto_id"] = l["producto_id"]
            if not l["es_bebida_incluida"] and l["precio_unitario"]:
                info["precio_menu"] = l["precio_unitario"]
            nota = l["notas"] or ""
            if nota and nota != "incluida" and not info["comentario"]:
                info["comentario"] = nota
        else:
            comidas.append(l)
 
    # Allowances granted by the food dishes already in the order
    cupo_desayuno = 0
    cupo_almuerzo = 0
    ronda_maxima = 1
    for l in comidas:
        nombre = l["nombre_producto"].lower().strip()
        cantidad = l["cantidad"]
        if _desayuno_incluye_bebida(nombre):
            cupo_desayuno += cantidad
        for clave, bebidas_incl in ALMUERZOS_LIMONADA.items():
            palabras = clave.split()
            if all(p in nombre for p in palabras):
                cupo_almuerzo += bebidas_incl * cantidad
                break
        # Keep the highest round to use for automatically generated drinks
        linea_ronda = l["ronda"] if "ronda" in l.keys() and l["ronda"] else 1
        ronda_maxima = max(ronda_maxima, linea_ronda)
 
    # If there is drink allowance but the waitress/customer did NOT add any
    # explicit drink to the order, NOTHING is assigned by default (neither coffee
    # nor lemonade). The allowance simply stays available/pending: the
    # person can ask for a drink later and it will then be assigned
    # for free according to the combo/dish allowance. The waitstaff frontend already
    # warns ("This order has no drinks") so they do not forget
    # to ask, without forcing a drink the customer did not choose.
    if not bebidas:
        return
 
    productos_menu = menu_db.get_productos(solo_disponibles=False)
    for info in bebidas.values():
        if not info["precio_menu"]:
            match = next((p for p in productos_menu
                          if p["nombre"].lower().strip() == info["nombre_real"].lower().strip()), None)
            if match:
                info["precio_menu"] = match["precio"]
                if not info["producto_id"]:
                    info["producto_id"] = match["id"]
 
    orden = sorted(bebidas.items(), key=lambda kv: kv[1]["primer_id"])
    restante = {nombre_lower: info["cantidad"] for nombre_lower, info in orden}
    gratis = {nombre_lower: 0 for nombre_lower, _info in orden}
 
    if "limonada" in restante:
        otorgadas = min(restante["limonada"], cupo_almuerzo)
        gratis["limonada"] += otorgadas
        restante["limonada"] -= otorgadas
        cupo_almuerzo -= otorgadas
 
    for nombre_lower, _info in orden:
        if cupo_desayuno <= 0:
            break
        disponible = restante[nombre_lower]
        if disponible <= 0:
            continue
        otorgadas = min(disponible, cupo_desayuno)
        gratis[nombre_lower] += otorgadas
        restante[nombre_lower] -= otorgadas
        cupo_desayuno -= otorgadas
 
    for info in bebidas.values():
        conn.executemany("DELETE FROM lineas_pedido WHERE id=?",
                          [(lid,) for lid in info["ids"]])
 
    for nombre_lower, info in bebidas.items():
        n_gratis = gratis[nombre_lower]
        n_pagadas = restante[nombre_lower]
        ronda_info = info.get("ronda", 1)
        if n_gratis > 0:
            conn.execute(
                """INSERT INTO lineas_pedido
                   (pedido_id, producto_id, nombre_producto, precio_unitario,
                    cantidad, subtotal, notas, es_bebida_incluida, ronda)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (pedido_id, info["producto_id"], info["nombre_real"], 0,
                 n_gratis, 0, "incluida", 1, ronda_info)
            )
        if n_pagadas > 0:
            conn.execute(
                """INSERT INTO lineas_pedido
                   (pedido_id, producto_id, nombre_producto, precio_unitario,
                    cantidad, subtotal, notas, es_bebida_incluida, ronda)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (pedido_id, info["producto_id"], info["nombre_real"],
                 info["precio_menu"], n_pagadas,
                 info["precio_menu"] * n_pagadas, info["comentario"], 0, ronda_info)
            )
 
    conn.execute(
        """UPDATE pedidos SET total=(
               SELECT COALESCE(SUM(subtotal),0) FROM lineas_pedido WHERE pedido_id=?
           ) WHERE id=?""",
        (pedido_id, pedido_id)
    )
    conn.commit()

def calcular_bebidas_incluidas(lineas):
    cupo_desayuno = 0
    cupo_almuerzo = 0
    usadas_desayuno = 0
    usadas_almuerzo = 0

    for l in lineas:
        nombre = l["nombre_producto"].lower().strip()
        print("NOMBRE:", repr(nombre))
        cantidad = l["cantidad"]
        incluida = l["es_bebida_incluida"]

        if _desayuno_incluye_bebida(nombre):
            cupo_desayuno += 1 * cantidad
        for clave, bebidas in ALMUERZOS_LIMONADA.items():
            palabras = clave.split()

            if all(p in nombre for p in palabras):
                cupo_almuerzo += bebidas * cantidad
                break

        if incluida:
            if nombre in BEBIDAS_ALMUERZO and nombre not in BEBIDAS_DESAYUNO - BEBIDAS_ALMUERZO:
                usadas_almuerzo += cantidad
            elif nombre in BEBIDAS_DESAYUNO:
                usadas_desayuno += cantidad

    disponibles_desayuno = max(0, cupo_desayuno - usadas_desayuno)
    disponibles_almuerzo = max(0, cupo_almuerzo - usadas_almuerzo)
    return disponibles_desayuno, disponibles_almuerzo


def es_bebida_desayuno(nombre):
    return nombre.lower().strip() in BEBIDAS_DESAYUNO


def es_bebida_almuerzo(nombre):
    return nombre.lower().strip() in BEBIDAS_ALMUERZO