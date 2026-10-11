"""
Flask server for waitstaff orders from a phone (local WiFi).
Includes:
    - Routes for the waitstaff web app (HTML + JS)
    - PIN authentication
    - REST API to get the menu, send orders, and query order history

"""

import threading
import sqlite3
import os
import re
import secrets
from functools import wraps
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, session
from ..impresora_cocina import agregar_comanda_cocina
import logging

logger = logging.getLogger(__name__)

# Recognizes "Mesa 5" (suffix=1, the "main" occupancy) or "Mesa 5-2",
# "Mesa 5-3"... (suffix=2, 3...) for a second/third time the
# same physical table is occupied before the first one is closed.
_RE_MESA = re.compile(r"^mesa\s*(\d+)(?:\s*-\s*(\d+))?$", re.IGNORECASE)


def _sufijo_si_coincide(nombre_mesa, numero_buscado):
    """If `nombre_mesa` is a variant of the physical table `numero_buscado`,
    returns its suffix (1 for 'Mesa N' without suffix, 2+ for 'Mesa N-2'...);
    if it does not correspond to that table, returns None."""
    m = _RE_MESA.match((nombre_mesa or "").strip())
    if not m or int(m.group(1)) != numero_buscado:
        return None
    return int(m.group(2)) if m.group(2) else 1


def _numero_base_mesa(nombre_mesa):
    """Physical table number (1-15) from 'Mesa 5' or 'Mesa 5-2'; None if the
    name does not follow that pattern (free-named table, e.g. 'Terraza')."""
    m = _RE_MESA.match((nombre_mesa or "").strip())
    return int(m.group(1)) if m else None


from .constantes import PIN_ACCESO, PUERTO, GRUPOS_VARIANTES_WEB, _NOMBRES_EN_GRUPO_WEB
from .plantilla_html import HTML_MESERO


class FlaskServer:
    def __init__(self, db, callback_comanda=None, callback_impresora=None):
        self.db = db
        self.callback_comanda = callback_comanda
        self.callback_impresora = callback_impresora or self._callback_impresora_default

        self.db_path = db.path
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        self.app = Flask(__name__, static_folder=static_dir, static_url_path="/static")
        self.app.config['JSON_AS_ASCII'] = False
        self.app.secret_key = secrets.token_hex(32)
        self.app.config.update(
            SESSION_PERMANENT=True,
            PERMANENT_SESSION_LIFETIME = timedelta(days=365),
            SESSION_REFRESH_EACH_REQUEST=False
        )
        self._registrar_rutas()
        self._thread = None
        self.activo = False

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _callback_impresora_default(self, pedido_id, numero_ronda=1):
        """Default callback to send the order to the printer when creating an order"""
        try:
            exito, mensaje = agregar_comanda_cocina(pedido_id)
            if exito:
                logger.info(f"Comanda {pedido_id} enviada a cocina automáticamente")
            else:
                logger.warning(f"No se pudo enviar comanda {pedido_id} a cocina: {mensaje}")
        except Exception as e:
            logger.error(f"Error en callback de impresora: {e}")

    @staticmethod
    def _login_required(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not session.get("autenticado"):
                return jsonify({"ok": False, "error": "No autenticado"}), 401
            return f(*args, **kwargs)
        return wrapper
    
    def _obtener_comentarios_dinamicos(self, categorias, productos, grupos):
        comentarios = {}

        for nombre_categoria in categorias:
            nombre = nombre_categoria.lower()

            if "bebida" in nombre:
                comentarios[nombre_categoria] = [
                    "Con leche", "Negro", "Frío", "Caliente", 
                    "Sin azúcar", "Poco azúcar", "Sin hielo", "Con hielo"
                ]
            elif "bandeja" in nombre:
                comentarios[nombre_categoria] = [
                    "Sin arroz", "Sin chimichurri", "Sin ensalada", 
                    "Con más arroz", "Con yuca", "Con papa", "Bien asado"
                ]
            elif "carta" in nombre:
                comentarios[nombre_categoria] = [
                    "Sin ensalada", "Sin francesa", "Cambiar francesa por yuca", 
                    "Cambiar francesa por patacón", "Término medio", "Bien cocido"
                ]
            elif "desayuno" in nombre:
                comentarios[nombre_categoria] = [
                    "Sin arepa", "Arepa bien asada", "Huevos blandos", 
                    "Huevos duros", "Sin cebolla", "Sin tomate"
                ]
            elif "almuerzo" in nombre:
                comentarios[nombre_categoria] = [
                    "Sin sopa", "Sin principio", "Poca sopa", 
                    "Para llevar", "Bebida fría"
                ]
            else:
                # Universal/standard suggestions
                comentarios[nombre_categoria] = [
                    "Sin cebolla", "Aparte", "Para llevar"
                ]

        return comentarios

    def _registrar_rutas(self):
        app = self.app
        login_required = self._login_required

        @app.route("/")
        def index():
            return HTML_MESERO

        @app.route("/api/login", methods=["POST"])
        def api_login():
            data = request.get_json(force=True, silent=True) or {}
            pin = str(data.get("pin", "")).strip()
            nombre_mesera = str(data.get("nombre_mesera", "")).strip()

            if pin != PIN_ACCESO:
                return jsonify({"ok": False, "error": "PIN incorrecto"}), 401

            if not nombre_mesera:
                return jsonify({"ok": False, "error": "Nombre de mesera requerido"}), 400

            session.clear()
            session["autenticado"] = True
            session["nombre_mesera"] = nombre_mesera
            session.permanent = True
            return jsonify({"ok": True, "nombre_mesera": nombre_mesera})
        

        @app.route("/api/admin/comentarios-producto", methods=["POST"])
        @login_required
        def api_guardar_comentario_producto():
            data = request.get_json(force=True, silent=True) or {}
            producto_id = data.get("producto_id")
            comentario = (data.get("comentario") or "").strip()

            if not producto_id or not comentario:
                return jsonify({"ok": False, "error": "Datos incompletos"}), 400

            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT INTO comentarios_producto (producto_id, comentario) VALUES (?, ?)",
                    (producto_id, comentario)
                )
                conn.commit()
                return jsonify({"ok": True})
            except Exception as e:
                conn.rollback()
                return jsonify({"ok": False, "error": str(e)}), 500
            finally:
                conn.close()

        @app.route("/api/mesas")
        @login_required
        def api_mesas():
            """
            State of tables 1 to 15 for the waitress's initial screen.

            A physical table can have several open orders at once if
            it was occupied more than once (see /api/mesa-variantes): "Mesa 5",
            "Mesa 5-2", "Mesa 5-3"... Here they are all grouped under the same
            number so that the grid shows the table as occupied
            while ANY of those variants is still open, using the oldest
            opening to compute the minutes.
            """
            conn = self._get_conn()
            try:
                filas = conn.execute(
                    "SELECT mesa, fecha_apertura FROM pedidos WHERE estado='abierto'"
                ).fetchall()

                aperturas = {}
                for f in filas:
                    numero = _numero_base_mesa((f["mesa"] or ""))
                    fecha = f["fecha_apertura"]
                    if numero is None or not fecha:
                        continue
                    if numero not in aperturas or fecha < aperturas[numero]:
                        aperturas[numero] = fecha

                ahora = datetime.now()
                mesas = []
                for n in range(1, 16):
                    atendida = n in aperturas
                    minutos = None
                    if atendida:
                        try:
                            apertura = datetime.fromisoformat(aperturas[n])
                            minutos = max(0, int((ahora - apertura).total_seconds() // 60))
                        except Exception:
                            minutos = None
                    mesas.append({"numero": n, "atendida": atendida, "minutos": minutos})

                return jsonify({"mesas": mesas})
            finally:
                conn.close()

        @app.route("/api/mesa-variantes")
        @login_required
        def api_mesa_variantes():
            """
            For when a table that already has an open order is selected:
            returns ALL the open orders of that physical table
            ("Mesa 5", "Mesa 5-2", ...) so that the app asks "Current order
            or new table?", and computes what the next available name would be
            if "new table" is chosen (as long as the base table or the previous one
            are still open; if they are closed, the numbering simply
            starts again from "Mesa N").
            """
            numero_str = (request.args.get("numero") or "").strip()
            if not numero_str.isdigit():
                return jsonify({"ok": False, "error": "Número de mesa inválido"}), 400
            numero = int(numero_str)

            conn = self._get_conn()
            try:
                filas = conn.execute(
                    "SELECT mesa, fecha_apertura FROM pedidos WHERE estado='abierto'"
                ).fetchall()

                abiertas = []  # [(suffix:int, table_name)], suffix 1 = "Mesa N" without suffix
                for f in filas:
                    sufijo = _sufijo_si_coincide(f["mesa"] or "", numero)
                    if sufijo is not None:
                        abiertas.append((sufijo, f["mesa"], f["fecha_apertura"]))

                abiertas.sort(key=lambda x: x[0])
                variantes = [{"mesa": nombre, "fecha_apertura": fecha} for _, nombre, fecha in abiertas]

                siguiente_sufijo = (max(s for s, _, _ in abiertas) + 1) if abiertas else 1
                siguiente_nombre = f"Mesa {numero}" if siguiente_sufijo <= 1 else f"Mesa {numero}-{siguiente_sufijo}"

                return jsonify({
                    "ok": True,
                    "numero": numero,
                    "variantes": variantes,
                    "siguiente": siguiente_nombre,
                })
            finally:
                conn.close()

        @app.route("/api/menu")
        @login_required
        def api_menu():
            # 1. Get the available products
            rows = self.db.get_productos(solo_disponibles=True)

            # 2. Get custom quick comments per product.
            #    Main source: menu.json ("comentarios" field), which is
            #    what is edited from the admin panel (Menu > Quick
            #    comments). It is also merged with the comentarios_producto table
            #    in case there are comments saved there (alternative admin endpoint).
            comentarios_db = {}
            for r in rows:
                lista_json = r.get("comentarios") or []
                if lista_json:
                    comentarios_db[r["id"]] = list(lista_json)

            conn = self._get_conn()
            try:
                filas_c = conn.execute("SELECT producto_id, comentario FROM comentarios_producto").fetchall()
                for f in filas_c:
                    pid = f["producto_id"]
                    comentarios_db.setdefault(pid, [])
                    if f["comentario"] not in comentarios_db[pid]:
                        comentarios_db[pid].append(f["comentario"])
            finally:
                conn.close()

            # 3. Categories and ordering
            cats_raw = list(dict.fromkeys(r["categoria"] for r in rows if r["categoria"]))
            _orden = ["carta", "desayunos", "almuerzos", "bebidas"]
            cats = sorted(
                cats_raw,
                key=lambda c: next((i for i, k in enumerate(_orden) if k in c.lower()), len(_orden))
            )

            # Helper map for the group logic
            prod_por_nombre = {r["nombre"]: r for r in rows}

            # 4. Processing groups and variants
            grupos_out = {}
            for ng, gdata in GRUPOS_VARIANTES_WEB.items():
                # Only the variants that have a real product
                # loaded in the menu are included (avoids "dead" buttons with no price).
                variantes_validas = []
                nombres_validos = {}
                precios_por_variante = {}
                ids_por_variante = {}
                precios = []
                categoria_ref = ""

                for v in gdata["variantes"]:
                    nombre_real = gdata["nombres"].get(v)
                    ref = prod_por_nombre.get(nombre_real)
                    if not ref:
                        continue
                    variantes_validas.append(v)
                    nombres_validos[v] = nombre_real
                    precios_por_variante[v] = ref["precio"]
                    ids_por_variante[v] = ref["id"]
                    precios.append(ref["precio"])
                    if not categoria_ref:
                        categoria_ref = ref["categoria"] or ""

                if not variantes_validas:
                    continue

                grupos_out[ng] = {
                    "variantes": variantes_validas,
                    "nombres":   nombres_validos,
                    "precios":   precios_por_variante,
                    "ids":       ids_por_variante,
                    "precio":    min(precios),
                    "precio_max": max(precios),
                    "categoria": categoria_ref,
                }

            # 5. Format the product list
            productos = [
                {
                    "id": r["id"], 
                    "nombre": r["nombre"], 
                    "precio": r["precio"],
                    "categoria": r["categoria"] or "", 
                    "descripcion": r["descripcion"] or "",
                    "comentarios_rapidos": comentarios_db.get(r["id"], [])  # List of the product's comments
                }
                for r in rows
                if r["nombre"] not in _NOMBRES_EN_GRUPO_WEB
            ]

            # 6. Comments per category
            comentarios_categoria = self._obtener_comentarios_dinamicos(cats, productos, grupos_out)

            # 7. JSON response
            return jsonify({
                "categorias": cats,
                "productos": productos,
                "grupos": grupos_out,
                "comentarios_dinamicos": comentarios_categoria,
                "comentarios_por_producto": comentarios_db
            })

        
        @app.route("/api/historial-comandas")
        @login_required
        def api_historial_comandas():
            """
            Returns the last 3 orders of the current waitress
            """
            nombre_mesera = session.get("nombre_mesera", "")
            if not nombre_mesera:
                return jsonify({"ok": False, "error": "Mesera no identificada"}), 400

            conn = self._get_conn()
            try:
                # Get this waitress's last 3 orders
                comandas = conn.execute(
                    """
                    SELECT id, mesa, fecha_apertura, total, estado
                    FROM pedidos
                    WHERE notas LIKE ?
                    ORDER BY fecha_apertura DESC
                    LIMIT 3
                    """,
                    (f"%mesera: {nombre_mesera}%",)
                ).fetchall()

                resultado = []
                for cmd in comandas:
                    items = conn.execute(
                        """
                        SELECT nombre_producto, cantidad, precio_unitario, notas
                        FROM lineas_pedido
                        WHERE pedido_id = ?
                        """,
                        (cmd["id"],)
                    ).fetchall()

                    resultado.append({
                        "id": cmd["id"],
                        "mesa": cmd["mesa"],
                        "fecha": cmd["fecha_apertura"],
                        "total": cmd["total"],
                        "estado": cmd["estado"],
                        "items": [
                            {
                                "nombre": i["nombre_producto"],
                                "cantidad": i["cantidad"],
                                "precio": i["precio_unitario"],
                                "comentario": i["notas"] or ""
                            }
                            for i in items
                        ]
                    })

                return jsonify({"ok": True, "comandas": resultado})
            finally:
                conn.close()

        @app.route("/api/comanda", methods=["POST"])
        @login_required
        def api_comanda():
            data = request.get_json(force=True, silent=True) or {}
            mesa = (data.get("mesa") or "").strip()
            items = data.get("items", [])
            nombre_mesera = session.get("nombre_mesera", "")

            if not mesa or not items:
                return jsonify({"ok": False, "error": "Datos incompletos"}), 400

            conn = self._get_conn()

            try:
                ahora = datetime.now().isoformat()

                mesa_norm = mesa.strip().lower()
                existente = conn.execute(
                    """
                    SELECT * FROM pedidos
                    WHERE estado='abierto' AND LOWER(TRIM(mesa))=?
                    ORDER BY fecha_apertura DESC
                    LIMIT 1
                    """,
                    (mesa_norm,)
                ).fetchone()

                if existente:
                    pedido_id = existente["id"]
                    fila_ronda = conn.execute(
                        "SELECT COALESCE(MAX(numero_ronda),0) FROM rondas_pedido WHERE pedido_id=?",
                        (pedido_id,)
                    ).fetchone()
                    numero_ronda = (fila_ronda[0] or 0) + 1
                    conn.execute(
                        """
                        INSERT INTO rondas_pedido (pedido_id, numero_ronda, fecha, origen)
                        VALUES (?,?,?,?)
                        """,
                        (pedido_id, numero_ronda, ahora, "mesera")
                    )
                else:
                    notas = f"Comanda mesera (movil) - mesera: {nombre_mesera}"
                    cur = conn.execute(
                        """
                        INSERT INTO pedidos
                        (mesa, fecha_apertura, notas, estado)
                        VALUES (?,?,?,?)
                        """,
                        (mesa, ahora, notas, "abierto")
                    )
                    pedido_id = cur.lastrowid
                    numero_ronda = 1
                    conn.execute(
                        """
                        INSERT INTO rondas_pedido (pedido_id, numero_ronda, fecha, origen)
                        VALUES (?,?,?,?)
                        """,
                        (pedido_id, numero_ronda, ahora, "mesera")
                    )

                from modules.caja import recalcular_bebidas_pedido

                agrupados = {}
                orden_grupos = []
                for item in items:
                    nombre = item["nombre"]
                    precio = float(item["precio"])
                    cantidad = int(item["cantidad"])
                    prod_id = item.get("producto_id")
                    comentario = (item.get("comentario") or "").strip()
                    clave = (nombre, comentario)
                    if clave in agrupados:
                        agrupados[clave]["cantidad"] += cantidad
                    else:
                        agrupados[clave] = {
                            "nombre": nombre,
                            "precio": precio,
                            "cantidad": cantidad,
                            "producto_id": prod_id,
                            "comentario": comentario,
                        }
                        orden_grupos.append(clave)

                for clave in orden_grupos:
                    item = agrupados[clave]
                    nombre = item["nombre"]
                    precio = item["precio"]
                    cantidad = item["cantidad"]
                    prod_id = item["producto_id"]
                    comentario = item["comentario"]

                    conn.execute(
                        """
                        INSERT INTO lineas_pedido
                        (
                            pedido_id,
                            producto_id,
                            nombre_producto,
                            precio_unitario,
                            cantidad,
                            subtotal,
                            notas,
                            es_bebida_incluida,
                            ronda
                        )
                        VALUES (?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            pedido_id,
                            prod_id,
                            nombre,
                            precio,
                            cantidad,
                            precio * cantidad,
                            comentario,
                            0,
                            numero_ronda
                        )
                    )

                recalcular_bebidas_pedido(conn, self.db, pedido_id)

                row = conn.execute(
                    """
                    SELECT COALESCE(SUM(subtotal),0)
                    FROM lineas_pedido
                    WHERE pedido_id=?
                    """,
                    (pedido_id,)
                ).fetchone()

                conn.execute(
                    "UPDATE pedidos SET total=? WHERE id=?",
                    (row[0], pedido_id)
                )

                conn.commit()

                if self.callback_comanda:
                    self.callback_comanda(pedido_id)
                
                if self.callback_impresora:
                    self.callback_impresora(pedido_id, numero_ronda)

                return jsonify({
                    "ok": True,
                    "pedido_id": pedido_id,
                    "ronda": numero_ronda,
                    "acumulado": bool(existente)
                })

            except Exception as e:
                conn.rollback()
                return jsonify({
                    "ok": False,
                    "error": str(e)
                }), 500

            finally:
                conn.close()

    def iniciar(self):
        if self.activo:
            return
        self.activo = True
        self._thread = threading.Thread(
            target=lambda: self.app.run(
                host="0.0.0.0", port=PUERTO, debug=False, use_reloader=False
            ),
            daemon=True
        )
        self._thread.start()

    def detener(self):
        self.activo = False