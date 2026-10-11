"""
SQLite database module for RestaurantePOS

Contains:
    - Database class: manages the SQLite connection, initializes the tables
    - Migration of old data from the menu tables to menu.json
    - Initial seeding of demo products (only if there is no prior data)
    - Functions to get products, categories, orders, expenses, cash closes, etc.
    
"""

import sqlite3
import os
import json
import re
from datetime import datetime, timedelta

from modules.menu_store import MenuStore
from modules.rutas_base import carpeta_base


class Database:
    def __init__(self, path=None):
        if path is None:
            base = carpeta_base()
            path = os.path.join(base, "data", "restaurante.db")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        menu_path = os.path.join(os.path.dirname(path), "menu.json")
        self.menu = MenuStore(menu_path)

    def inicializar(self):
        cursor = self.conn.cursor()

        # Old menu tables: kept ONLY if they already existed in a
        # previous installation, solely to be able to migrate their data to the
        # new menu.json one time. They are not used again afterwards.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                precio REAL NOT NULL,
                categoria_id INTEGER,
                disponible INTEGER DEFAULT 1,
                descripcion TEXT DEFAULT '',
                FOREIGN KEY (categoria_id) REFERENCES categorias(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mesa TEXT NOT NULL,
                estado TEXT DEFAULT 'abierto',
                total REAL DEFAULT 0,
                metodo_pago TEXT DEFAULT '',
                fecha_apertura TEXT NOT NULL,
                fecha_cierre TEXT,
                notas TEXT DEFAULT ''
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lineas_pedido (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER NOT NULL,
                producto_id INTEGER,
                nombre_producto TEXT NOT NULL,
                precio_unitario REAL NOT NULL,
                cantidad INTEGER NOT NULL DEFAULT 1,
                subtotal REAL NOT NULL,
                notas TEXT DEFAULT '',
                es_bebida_incluida INTEGER DEFAULT 0,
                precio_original REAL,
                precio_editado INTEGER DEFAULT 0,
                FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
                FOREIGN KEY (producto_id) REFERENCES productos(id)
            )
        """)

        # 1. Create the individual expenses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gastos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                motivo TEXT NOT NULL,
                valor REAL NOT NULL
            )
        """)

        # 2. Replace the cierres_caja table with the new fields
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cierres_caja (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                total_efectivo REAL DEFAULT 0,
                total_transferencias REAL DEFAULT 0,
                total_gastos REAL DEFAULT 0,
                total_primicia REAL DEFAULT 0,
                total_cuadrado REAL DEFAULT 0,
                total_comandas REAL DEFAULT 0,
                diferencia REAL DEFAULT 0
            )
        """)

        # ── Quick Comments per Product ───────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comentarios_producto (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id INTEGER NOT NULL,
                comentario TEXT NOT NULL
            )
        """)

        # ── Order cancellations (with reason and alert to the manager) ──
        # Every time an order is cancelled a record is left here. If the
        # cashier does not manage to type the reason at that moment, the row
        # is left with an empty reason and `notificado_jefe=0`; a check by the
        # remote dashboard (every 30s, see dashboard_server.py) takes care
        # of alerting the manager if 10 minutes pass without a justification.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cancelaciones_pedido (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER NOT NULL,
                mesa TEXT NOT NULL,
                total REAL DEFAULT 0,
                fecha TEXT NOT NULL,
                motivo TEXT DEFAULT '',
                detalle TEXT DEFAULT '[]',
                notificado_jefe INTEGER DEFAULT 0,
                FOREIGN KEY(pedido_id) REFERENCES pedidos(id)
            )
        """)
        # Soft migration: if the table already existed from a previous version
        # without the `detalle` column, it is added without losing cancellations
        # already recorded (they stay with an empty detail, which is the most honest:
        # that snapshot of the ticket was never saved at that time).
        cols_cancel = [r[1] for r in cursor.execute("PRAGMA table_info(cancelaciones_pedido)").fetchall()]
        if "detalle" not in cols_cancel:
            cursor.execute("ALTER TABLE cancelaciones_pedido ADD COLUMN detalle TEXT DEFAULT '[]'")

        # Soft migration in case the database already existed with the old columns
        cols_cierre = {row["name"] for row in cursor.execute("PRAGMA table_info(cierres_caja)")}
        if "total_transferencias" not in cols_cierre:
            cursor.execute("ALTER TABLE cierres_caja ADD COLUMN total_transferencias REAL DEFAULT 0")
        if "total_gastos" not in cols_cierre:
            cursor.execute("ALTER TABLE cierres_caja ADD COLUMN total_gastos REAL DEFAULT 0")
        if "total_primicia" not in cols_cierre:
            cursor.execute("ALTER TABLE cierres_caja ADD COLUMN total_primicia REAL DEFAULT 0")
        if "total_cuadrado" not in cols_cierre:
            cursor.execute("ALTER TABLE cierres_caja ADD COLUMN total_cuadrado REAL DEFAULT 0")
        if "total_comandas" not in cols_cierre:
            cursor.execute("ALTER TABLE cierres_caja ADD COLUMN total_comandas REAL DEFAULT 0")
        if "diferencia" not in cols_cierre:
            cursor.execute("ALTER TABLE cierres_caja ADD COLUMN diferencia REAL DEFAULT 0")

        # Soft migration: if the database comes from a previous version
        # without these columns, they are added without losing anything.
        cols_existentes = {row["name"] for row in cursor.execute("PRAGMA table_info(lineas_pedido)")}
        if "precio_original" not in cols_existentes:
            cursor.execute("ALTER TABLE lineas_pedido ADD COLUMN precio_original REAL")
        if "precio_editado" not in cols_existentes:
            cursor.execute("ALTER TABLE lineas_pedido ADD COLUMN precio_editado INTEGER DEFAULT 0")
        if "ronda" not in cols_existentes:
            cursor.execute("ALTER TABLE lineas_pedido ADD COLUMN ronda INTEGER DEFAULT 1")

        # Rounds of the same order: when a table that already has an open
        # order requests an addition (from the central station or from a
        # waitress's phone), a new order/ticket is NOT created — it is added as one more
        # round within the same order. Each round is recorded
        # here (with its origin and whether it was already sent/printed to the kitchen), so that
        # later the system can decide to print only what is new in
        # each round and not the whole order every time.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rondas_pedido (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER NOT NULL,
                numero_ronda INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                origen TEXT DEFAULT '',
                impreso INTEGER DEFAULT 0,
                FOREIGN KEY (pedido_id) REFERENCES pedidos(id)
            )
        """)

        # Meat inventory: split into two groups — "menu" (the meats
        # of the Lunch dishes: beef, chicken breast, pork) and "carta" (the
        # meats of the A-la-carte dishes: baby, churrasco, pechuga carta,
        # punta, lomo, lengua, mojarra). Every time an order is charged,
        # the corresponding amount is deducted automatically.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                tipo TEXT NOT NULL,
                cantidad REAL NOT NULL DEFAULT 0,
                unidad TEXT DEFAULT 'porciones'
            )
        """)

        # Links from menu product → inventory item. Allows linking
        # ANY product (not only meats) to an inventory item,
        # explicitly from the Inventory tab. Simple 1 product = 1 item
        # relationship: when charging, each unit sold of that
        # product deducts 1 unit of the linked item. It coexists with
        # the keyword-based meat system (identificar_carne), which
        # keeps working the same as a fallback if there is no manual link.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventario_vinculos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_inventario TEXT NOT NULL,
                producto_nombre TEXT NOT NULL,
                UNIQUE(item_inventario, producto_nombre)
            )
        """)

        # Payment audit: every charge (full or partial, simple or
        # "split bill" cash+transfer) is recorded here
        # with its exact breakdown. A single order can have several rows
        # here if it was charged in parts (e.g. partial charge by products
        # selected from the Register). This table is the reliable source
        # for the cash/transfer reports, because the single field
        # `pedidos.metodo_pago` cannot represent split
        # or partial payments.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pagos_pedido (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                metodo TEXT NOT NULL,
                monto_total REAL NOT NULL,
                monto_efectivo REAL DEFAULT 0,
                monto_transferencia REAL DEFAULT 0,
                productos TEXT DEFAULT ''
            )
        """)

        # Audit: every time the unit price of a line already added
        # to an order is edited (e.g. to lower it and close a sale),
        # the original real price and the price actually
        # charged are recorded here, so it is traceable in the report.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historial_precios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER NOT NULL,
                linea_id INTEGER NOT NULL,
                nombre_producto TEXT NOT NULL,
                precio_original REAL NOT NULL,
                precio_nuevo REAL NOT NULL,
                cantidad INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                motivo TEXT DEFAULT '',
                usuario TEXT DEFAULT ''
            )
        """)

        self.conn.commit()

        # Initial seeding of the meat inventory (only if those rows
        # do not exist yet; does not overwrite quantities already loaded by the user).
        self._insertar_inventario_demo()

        # If the menu JSON is empty but there were products in the old
        # tables (previous installation), they are imported one time only.
        self.menu.migrar_desde_sqlite_si_hace_falta(self.conn)

        # If it is a completely new installation (nothing anywhere),
        # the initial demo data is loaded into the JSON.
        if not self.menu.get_productos(solo_disponibles=False):
            self._insertar_datos_demo()

    def _insertar_datos_demo(self):
        productos = [
            # Breakfasts
            # EGGS
            ("Huevos revueltos",            19000, "Desayunos", "Incluye 1 bebida"),
            ("Huevos rancheros",            19000, "Desayunos", "Incluye 1 bebida"),
            ("Huevos pericos",            19000, "Desayunos", "Incluye 1 bebida"),
            ("Huevos tortilla",            19000, "Desayunos", "Incluye 1 bebida"),
            ("Huevos fritos",            19000, "Desayunos", "Incluye 1 bebida"),
            ("Huevos duros/cocidos",            19000, "Desayunos", "Incluye 1 bebida"),

            ("Porcion de huevos revueltos", 12000, "Desayunos", ""),
            ("Porcion de huevos rancheros", 12000, "Desayunos", ""),
            ("Porcion de huevos pericos", 12000, "Desayunos", ""),
            ("Porcion de huevos tortilla", 12000, "Desayunos", ""),
            ("Porcion de huevos fritos", 12000, "Desayunos", ""),
            ("Porcion de huevos duros/cocidos", 12000, "Desayunos", ""),

            # BROTHS
            ("Caldo grande costilla",                 18000, "Desayunos", "Incluye 1 bebida"),
            ("Caldo pequeño costilla + arepa",        15000, "Desayunos", ""),
            ("Caldo pequeño costilla",                12000, "Desayunos", ""),

            ("Caldo grande de huevo",                 18000, "Desayunos", "Incluye 1 bebida"),
            ("Caldo pequeño de huevo + arepa",        15000, "Desayunos", ""),
            ("Caldo pequeño de huevo",                12000, "Desayunos", ""),

            ("Caldo grande de changua",                 18000, "Desayunos", "Incluye 1 bebida"),
            ("Caldo pequeño de changua + arepa",        15000, "Desayunos", ""),
            ("Caldo pequeño de changua",                12000, "Desayunos", ""),

            ("Caldo grande de costilla con huevo",                 20000, "Desayunos", "Incluye 1 bebida"),
            ("Caldo pequeño de costilla con huevo + arepa",        17000, "Desayunos", ""),
            ("Caldo pequeño de costilla con huevo",                14000, "Desayunos", ""),

            # combos
            ("Combo caldo pequeño costilla + huevos revueltos", 25000, "Desayunos", "Incluye 1 bebidas"),
            ("Combo caldo pequeño costilla + huevos rancheros", 25000, "Desayunos", "Incluye 1 bebidas"),
            ("Combo caldo pequeño costilla + huevos pericos", 25000, "Desayunos", "Incluye 1 bebidas"),

            ("Combo caldo pequeño huevo + huevos revueltos", 25000, "Desayunos", "Incluye 1 bebidas"),
            ("Combo caldo pequeño huevo + huevos rancheros", 25000, "Desayunos", "Incluye 1 bebidas"),
            ("Combo caldo pequeño huevo + huevos pericos", 25000, "Desayunos", "Incluye 1 bebidas"),

            ("Combo caldo pequeño changua + huevos revueltos", 25000, "Desayunos", "Incluye 1 bebidas"),
            ("Combo caldo pequeño changua + huevos rancheros", 25000, "Desayunos", "Incluye 1 bebidas"),
            ("Combo caldo pequeño changua + huevos pericos", 25000, "Desayunos", "Incluye 1 bebidas"),

            ("Combo caldo pequeño costilla con huevo + huevos revueltos", 27000, "Desayunos", "Incluye 1 bebidas"),
            ("Combo caldo pequeño costilla con huevo + huevos rancheros", 27000, "Desayunos", "Incluye 1 bebidas"),
            ("Combo caldo pequeño costilla con huevo + huevos pericos", 27000, "Desayunos", "Incluye 1 bebidas"),

            ("Bandeja de res",             22000, "Desayunos", "Incluye 1 bebida"),
            ("Bandeja de cerdo", 22000, "Desayunos", "Incluye 1 bebida"),
            ("Bandeja de pollo", 22000, "Desayunos", "Incluye 1 bebida"),

            ("Combo caldo pequeño de costilla + bandeja de res", 28000, "Desayunos", "Incluye 1 bebida"),
            ("Combo caldo pequeño de costilla + bandeja de cerdo", 28000, "Desayunos", "Incluye 1 bebida"),
            ("Combo caldo pequeño de costilla + bandeja de pollo", 28000, "Desayunos", "Incluye 1 bebida"),

            ("Porcion costilla", 5000, "Desayunos", ""),
            ("porcion pollo", 7000, "Desayunos", ""),
            ("porcion cerdo", 7000, "Desayunos", ""),
            ("Porcion res", 7000, "Desayunos", ""),
            ("Porcion arroz", 5000, "Desayunos", ""),
            ("Porcion pan",                         2000, "Desayunos", ""),
            ("Porcion arepa",                        3000, "Desayunos", ""),
            ("Porcion queso",                        4000, "Desayunos", ""),

            # Lunches
            ("Sopa pequeña",                         10000, "Almuerzos", ""),
            ("Sopa grande", 16000, "Almuerzos", ""),
            ("Sanchoco", 20000, "Almuerzos", ""),

            ("Ejecutivo res turista",            25000, "Almuerzos", "Incluye limonada"),
            ("Ejecutivo cerdo turista", 25000, "Almuerzos", "Incluye limonada"),
            ("Ejecutivo pechuga turista", 25000, "Almuerzos", "Incluye limonada"),

            ("Ejecutivo res mulero",             22000, "Almuerzos", "Incluye limonada"),
            ("Ejecutivo cerdo mulero", 22000, "Almuerzos", "Incluye limonada"),
            ("Ejecutivo pechuga mulero", 22000, "Almuerzos", "Incluye limonada"),

            ("Del día res turista",              26000, "Almuerzos", "Incluye limonada"),
            ("Del día cerdo turista", 26000, "Almuerzos", "Incluye limonada"),
            ("Del día pechuga turista", 26000, "Almuerzos", "Incluye limonada"),

            ("Del día res mulero",               22000, "Almuerzos", "Incluye limonada"),
            ("Del día cerdo mulero", 22000, "Almuerzos", "Incluye limonada"),
            ("Del día pechuga mulero", 22000, "Almuerzos", "Incluye limonada"),

            # A-la-carte dishes
            ("Pechuga parrilla",             44000, "Platos Carta", ""),
            ("Pechuga hawaiana",             48000, "Platos Carta", ""),
            ("Pechuga BBQ",                  48000, "Platos Carta", ""),
            ("Pechuga champiñón",            48000, "Platos Carta", ""),
            ("Pechuga camarón",              60000, "Platos Carta", ""),
            ("Lomo cerdo plancha",           42000, "Platos Carta", ""),
            ("Lomo BBQ",                     44000, "Platos Carta", ""),
            ("Lengua salsa criolla",         52000, "Platos Carta", ""),
            ("Lengua salsa champiñón",       52000, "Platos Carta", ""),
            ("Baby champiñón",               68000, "Platos Carta", ""),
            ("Baby en salsa criolla",        65000, "Platos Carta", ""),
            ("Baby en camarón",              70000, "Platos Carta", ""),

            # Drinks
            ("Café",                          3000, "Bebidas", ""),
            ("Chocolate",                     3000, "Bebidas", ""),
            ("Tinto",                         3000, "Bebidas", ""),
            ("Limonada",                      4000, "Bebidas", ""),
            ("Jarra limonada",               15000, "Bebidas", ""),
            ("Gaseosa personal",              5000, "Bebidas", ""),
            ("Gatorade",                      7000, "Bebidas", ""),
            ("Agua",                          4000, "Bebidas", ""),
            ("Gaseosa litro",                15000, "Bebidas", ""),
            ("Jugo Hit",                      5000, "Bebidas", ""),
            ("Cola y Pola",                   6000, "Bebidas", ""),
            ("Vive100 pequeño",               5000, "Bebidas", ""),
            ("Vive100 grande",                7000, "Bebidas", ""),

            # Disposables
            ("Desechable pequeño",            1000, "Desechables", ""),
            ("Desechable grande",             2000, "Desechables", ""),
            ("Vaso",                          1000, "Desechables", ""),
        ]
        for nombre, precio, categoria, descripcion in productos:
            self.menu.add_producto(nombre, precio, categoria, descripcion)

    # ── Products / Categories (delegate to MenuStore → menu.json) ──
    def get_productos(self, solo_disponibles=True):
        return self.menu.get_productos(solo_disponibles=solo_disponibles)

    def get_categorias(self):
        return [{"nombre": nombre} for nombre in self.menu.get_categorias()]

    def add_producto(self, nombre, precio, categoria, descripcion="", comentarios=None):
        return self.menu.add_producto(nombre, precio, categoria, descripcion, comentarios=comentarios)

    def update_producto(self, pid, nombre, precio, categoria, disponible, descripcion, comentarios=None):
        self.menu.update_producto(pid, nombre, precio, categoria, disponible, descripcion, comentarios=comentarios)

    def delete_producto(self, pid):
        self.menu.delete_producto(pid)

    # ── Meat inventory ────────────────────────────────────────
    def _insertar_inventario_demo(self):
        """Creates the base inventory rows (quantity 0) the first
        time, both for menu meats and a-la-carte meats. Uses
        INSERT OR IGNORE so as not to overwrite quantities already loaded."""
        base = [
            ("Res", "menu"), ("Pechuga", "menu"), ("Cerdo", "menu"),
            ("Baby", "carta"), ("Churrasco", "carta"), ("Pechuga Carta", "carta"),
            ("Punta", "carta"), ("Lomo", "carta"), ("Lengua", "carta"),
            ("Mojarra", "carta"),
        ]
        for nombre, tipo in base:
            self.conn.execute(
                "INSERT OR IGNORE INTO inventario (nombre, tipo, cantidad) VALUES (?,?,0)",
                (nombre, tipo)
            )
        self.conn.commit()

    def get_inventario(self, tipo=None):
        if tipo:
            return self.conn.execute(
                "SELECT * FROM inventario WHERE tipo=? ORDER BY nombre", (tipo,)
            ).fetchall()
        return self.conn.execute("SELECT * FROM inventario ORDER BY tipo, nombre").fetchall()

    def set_stock_inventario(self, nombre, cantidad):
        self.conn.execute(
            "UPDATE inventario SET cantidad=? WHERE nombre=?", (float(cantidad), nombre)
        )
        self.conn.commit()

    def ajustar_stock_inventario(self, nombre, delta):
        """Adds (or subtracts, if delta is negative) `delta` to the current
        quantity of that meat in the inventory."""
        self.conn.execute(
            "UPDATE inventario SET cantidad = cantidad + ? WHERE nombre=?",
            (float(delta), nombre)
        )
        self.conn.commit()

    def agregar_item_inventario(self, nombre, tipo, unidad="unidades", cantidad_inicial=0):
        """Creates a new inventory item (besides the base
        meats). `tipo` determines in which grid it appears ('menu' or 'carta').
        Raises sqlite3.IntegrityError if an item with that name already exists."""
        nombre = (nombre or "").strip()
        if not nombre:
            raise ValueError("El nombre del insumo es obligatorio")
        tipo = (tipo or "otros").strip() or "otros"
        unidad = (unidad or "unidades").strip() or "unidades"
        self.conn.execute(
            "INSERT INTO inventario (nombre, tipo, cantidad, unidad) VALUES (?,?,?,?)",
            (nombre, tipo, float(cantidad_inicial or 0), unidad)
        )
        self.conn.commit()

    def eliminar_item_inventario(self, nombre):
        """Removes an inventory item completely, along with
        any link to menu products it had."""
        self.conn.execute("DELETE FROM inventario WHERE nombre=?", (nombre,))
        self.conn.execute("DELETE FROM inventario_vinculos WHERE item_inventario=?", (nombre,))
        self.conn.commit()

    # ── Links menu product → inventory item ───────────────────
    def get_vinculos_item(self, nombre_item):
        """Lists the menu product names linked to an inventory item."""
        filas = self.conn.execute(
            "SELECT producto_nombre FROM inventario_vinculos WHERE item_inventario=? ORDER BY producto_nombre",
            (nombre_item,)
        ).fetchall()
        return [f["producto_nombre"] for f in filas]

    def set_vinculos_item(self, nombre_item, productos):
        """Replaces the full list of products linked to an inventory item."""
        self.conn.execute("DELETE FROM inventario_vinculos WHERE item_inventario=?", (nombre_item,))
        for p in productos:
            p = (p or "").strip()
            if p:
                self.conn.execute(
                    "INSERT OR IGNORE INTO inventario_vinculos (item_inventario, producto_nombre) VALUES (?,?)",
                    (nombre_item, p)
                )
        self.conn.commit()

    def _item_inventario_por_producto(self, nombre_producto):
        """Checks whether the name of the sold product matches (case- and
        whitespace-insensitive) any manual link configured from
        the Inventory tab."""
        nombre_producto = (nombre_producto or "").strip().lower()
        if not nombre_producto:
            return None
        fila = self.conn.execute(
            "SELECT item_inventario FROM inventario_vinculos WHERE LOWER(TRIM(producto_nombre))=?",
            (nombre_producto,)
        ).fetchone()
        return fila["item_inventario"] if fila else None

    def descontar_inventario_por_lineas(self, lineas):
        """
        Goes through the lines of an already charged order and deducts from the
        inventory the item corresponding to each dish:

          1. First it looks for a manual link configured from the
             Inventory tab (works for ANY product that has been
             added and linked there, not just meats).
          2. If there is no manual link, it falls back to automatic
             keyword identification (identificar_carne), which is
             what the menu/carta meats had from the start.

        Dishes that do not correspond to any inventory item
        are simply ignored.
        """
        from modules.inventario import identificar_carne
        for linea in lineas:
            nombre_item = self._item_inventario_por_producto(linea["nombre_producto"])
            if nombre_item:
                self.ajustar_stock_inventario(nombre_item, -linea["cantidad"])
                continue

            resultado = identificar_carne(linea["nombre_producto"])
            if resultado:
                _, nombre_carne = resultado
                self.ajustar_stock_inventario(nombre_carne, -linea["cantidad"])

    # ── Orders ─────────────────────────────────────────────────
    def crear_pedido(self, mesa, notas="", origen="central"):
        cur = self.conn.execute(
            "INSERT INTO pedidos (mesa, fecha_apertura, notas) VALUES (?,?,?)",
            (mesa, datetime.now().isoformat(), notas)
        )
        pedido_id = cur.lastrowid
        # First round of the order.
        self.conn.execute(
            """INSERT INTO rondas_pedido (pedido_id, numero_ronda, fecha, origen)
               VALUES (?,?,?,?)""",
            (pedido_id, 1, datetime.now().isoformat(), origen)
        )
        self.conn.commit()
        return pedido_id

    def get_pedido_abierto_por_mesa(self, mesa):
        """
        Looks for an OPEN order for that table (comparing regardless of
        upper/lower case or extra spaces), regardless of whether
        the order was opened by the central station or by a waitress from the phone.

        It is used so that, when the same table orders something again (an
        addition), a new ticket/order is NOT created, but it accumulates
        within the same one.
        """
        mesa_norm = (mesa or "").strip().lower()
        if not mesa_norm:
            return None
        return self.conn.execute(
            """
            SELECT * FROM pedidos
            WHERE estado='abierto' AND LOWER(TRIM(mesa))=?
            ORDER BY fecha_apertura DESC
            LIMIT 1
            """,
            (mesa_norm,)
        ).fetchone()

    def nueva_ronda_pedido(self, pedido_id, origen="central"):
        """
        Registers a new round (an addition) within an order that already
        exists, instead of creating a separate order/ticket for the table.
        Returns the assigned round number, so that the lines that are
        added next are marked with that number and, later on, the system
        can decide to print only what is new in that round instead of the whole order.
        """
        row = self.conn.execute(
            "SELECT COALESCE(MAX(numero_ronda),0) FROM rondas_pedido WHERE pedido_id=?",
            (pedido_id,)
        ).fetchone()
        numero_ronda = (row[0] or 0) + 1
        self.conn.execute(
            """INSERT INTO rondas_pedido (pedido_id, numero_ronda, fecha, origen)
               VALUES (?,?,?,?)""",
            (pedido_id, numero_ronda, datetime.now().isoformat(), origen)
        )
        self.conn.commit()
        return numero_ronda

    def get_ronda_actual(self, pedido_id):
        row = self.conn.execute(
            "SELECT COALESCE(MAX(numero_ronda),1) FROM rondas_pedido WHERE pedido_id=?",
            (pedido_id,)
        ).fetchone()
        return row[0] or 1

    def get_pedidos_abiertos(self):
        return self.conn.execute(
            "SELECT * FROM pedidos WHERE estado='abierto' ORDER BY fecha_apertura"
        ).fetchall()

    def get_pedido(self, pid):
        return self.conn.execute("SELECT * FROM pedidos WHERE id=?", (pid,)).fetchone()

    def add_linea(self, pedido_id, nombre_producto, precio_unitario, cantidad=1,
                  producto_id=None, notas="", es_bebida_incluida=0, ronda=None):
        subtotal = precio_unitario * cantidad
        if ronda is None:
            ronda = self.get_ronda_actual(pedido_id)
        self.conn.execute(
            """INSERT INTO lineas_pedido
               (pedido_id, producto_id, nombre_producto, precio_unitario, cantidad, subtotal, notas, es_bebida_incluida, ronda)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (pedido_id, producto_id, nombre_producto, precio_unitario,
             cantidad, subtotal, notas, es_bebida_incluida, ronda)
        )
        self._recalcular_total(pedido_id)
        self.conn.commit()

    def get_lineas(self, pedido_id):
        return self.conn.execute(
            "SELECT * FROM lineas_pedido WHERE pedido_id=? ORDER BY id",
            (pedido_id,)
        ).fetchall()

    def delete_linea(self, linea_id, pedido_id):
        self.conn.execute("DELETE FROM lineas_pedido WHERE id=?", (linea_id,))
        self._recalcular_total(pedido_id)
        self.conn.commit()

    def _recalcular_total(self, pedido_id):
        row = self.conn.execute(
            "SELECT COALESCE(SUM(subtotal),0) FROM lineas_pedido WHERE pedido_id=?",
            (pedido_id,)
        ).fetchone()
        self.conn.execute("UPDATE pedidos SET total=? WHERE id=?", (row[0], pedido_id))

    # ── Real-time price edit (with audit) ──────────────────────
    def editar_precio_linea(self, linea_id, pedido_id, nuevo_precio, motivo="", usuario=""):
        """
        Changes the unit price of a line ALREADY added to an order
        (e.g. to lower the price and close a sale) and recalculates the
        subtotal of that line and the order total.

        For safety, the original real price and the price actually
        charged are recorded in `historial_precios`, no matter
        how many times the same line is edited.
        """
        linea = self.conn.execute(
            "SELECT * FROM lineas_pedido WHERE id=?", (linea_id,)
        ).fetchone()
        if not linea:
            return False

        # The "real price" that is audited is always the original
        # sale price, even if the line has been edited before.
        precio_original = (
            linea["precio_original"]
            if linea["precio_original"] is not None
            else linea["precio_unitario"]
        )
        cantidad = linea["cantidad"]
        nuevo_precio = float(nuevo_precio)
        nuevo_subtotal = nuevo_precio * cantidad

        self.conn.execute(
            """UPDATE lineas_pedido
               SET precio_unitario=?, subtotal=?, precio_original=?, precio_editado=1
               WHERE id=?""",
            (nuevo_precio, nuevo_subtotal, precio_original, linea_id)
        )
        self.conn.execute(
            """INSERT INTO historial_precios
               (pedido_id, linea_id, nombre_producto, precio_original, precio_nuevo,
                cantidad, fecha, motivo, usuario)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (pedido_id, linea_id, linea["nombre_producto"], precio_original, nuevo_precio,
             cantidad, datetime.now().isoformat(), motivo, usuario)
        )
        self._recalcular_total(pedido_id)
        self.conn.commit()
        return True

    def get_historial_precios(self, limit=300):
        return self.conn.execute(
            "SELECT * FROM historial_precios ORDER BY fecha DESC LIMIT ?", (limit,)
        ).fetchall()

    def cerrar_pedido(self, pedido_id, metodo_pago):
        self.conn.execute(
            "UPDATE pedidos SET estado='cerrado', metodo_pago=?, fecha_cierre=? WHERE id=?",
            (metodo_pago, datetime.now().isoformat(), pedido_id)
        )
        self.conn.commit()

    def cancelar_pedido(self, pedido_id, motivo=""):
        """
        Cancels an order and leaves a record in `cancelaciones_pedido`,
        including an EXACT SNAPSHOT of which products the ticket had at
        that moment (`detalle` column, in JSON) — that way, even if lines of that
        order are later edited or deleted, the cancellation record
        always shows what was actually being cancelled.

        If `motivo` is empty, the cancellation is left pending
        justification: after 10 minutes without a reason, the remote dashboard
        notifies the manager (see get_cancelaciones_pendientes_alerta).
        """
        motivo = (motivo or "").strip()
        pedido = self.get_pedido(pedido_id)
        lineas = self.get_lineas(pedido_id)
        detalle = json.dumps([
            {
                "nombre": l["nombre_producto"],
                "cantidad": l["cantidad"],
                "precio_unitario": l["precio_unitario"],
                "subtotal": l["subtotal"],
            }
            for l in lineas
        ], ensure_ascii=False)
        fecha = datetime.now().isoformat()

        self.conn.execute(
            "UPDATE pedidos SET estado='cancelado', fecha_cierre=? WHERE id=?",
            (fecha, pedido_id)
        )
        self.conn.execute(
            """INSERT INTO cancelaciones_pedido (pedido_id, mesa, total, fecha, motivo, detalle)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (pedido_id, pedido["mesa"] if pedido else "?",
             pedido["total"] if pedido else 0, fecha, motivo, detalle)
        )
        self.conn.commit()

    def agregar_motivo_cancelacion(self, cancelacion_id, motivo):
        """Allows justifying later a cancellation that was left without a reason."""
        self.conn.execute(
            "UPDATE cancelaciones_pedido SET motivo=? WHERE id=?",
            (motivo.strip(), cancelacion_id)
        )
        self.conn.commit()

    def get_cancelaciones_hoy(self):
        hoy = datetime.now().strftime("%Y-%m-%d")
        return self.conn.execute(
            "SELECT * FROM cancelaciones_pedido WHERE fecha LIKE ? ORDER BY fecha DESC",
            (f"{hoy}%",)
        ).fetchall()

    def get_cancelaciones_por_rango(self, fecha_inicio, fecha_fin):
        """fecha_inicio/fecha_fin in 'YYYY-MM-DD' format, both inclusive."""
        return self.conn.execute(
            """SELECT * FROM cancelaciones_pedido
               WHERE DATE(fecha) BETWEEN ? AND ?
               ORDER BY fecha ASC""",
            (fecha_inicio, fecha_fin)
        ).fetchall()

    def get_cancelaciones_pendientes_alerta(self, minutos=10):
        """
        Cancellations without a reason, with more than `minutos` since the
        cancellation was made, that have not yet been notified to the manager.
        They are not repeated: once returned here, marcar_cancelacion_notificada
        removes them from this list even if they still have no reason.
        """
        limite = (datetime.now() - timedelta(minutes=minutos)).isoformat()
        return self.conn.execute(
            """SELECT * FROM cancelaciones_pedido
               WHERE (motivo IS NULL OR TRIM(motivo)='')
                 AND fecha <= ?
                 AND notificado_jefe = 0
               ORDER BY fecha ASC""",
            (limite,)
        ).fetchall()

    def marcar_cancelacion_notificada(self, cancelacion_id):
        self.conn.execute(
            "UPDATE cancelaciones_pedido SET notificado_jefe=1 WHERE id=?",
            (cancelacion_id,)
        )
        self.conn.commit()

    @staticmethod
    def parsear_detalle_cancelacion(detalle_json):
        """[{'nombre':..,'cantidad':..,'precio_unitario':..,'subtotal':..}, ...]"""
        try:
            return json.loads(detalle_json or "[]")
        except (TypeError, ValueError):
            return []

    @staticmethod
    def resumen_detalle_cancelacion(detalle_json):
        """Short text like 'Bandeja paisa x2, Limonada x1' to show
        at a glance on the dashboard or in the Excel."""
        items = Database.parsear_detalle_cancelacion(detalle_json)
        if not items:
            return "(sin líneas registradas)"
        return ", ".join(f"{i['nombre']} x{i['cantidad']}" for i in items)

    _RE_MESERA_EN_NOTAS = re.compile(r"mesera:\s*(.+)$", re.IGNORECASE)

    @staticmethod
    def mesera_de_pedido(pedido):
        """
        Extracts the waitress's name from the order notes (where
        it is stored as '...- mesera: Alex' when the order is created
        from the phone). Returns None if the order has no associated waitress
        (for example, one taken directly at the central register) — that way
        each screen decides its own default text ("Central register",
        hide the line, etc.) instead of it being fixed here.
        """
        if not pedido:
            return None
        try:
            notas = pedido["notas"] or ""
        except (KeyError, IndexError, TypeError):
            notas = ""
        m = Database._RE_MESERA_EN_NOTAS.search(notas)
        return m.group(1).strip() or None if m else None

    # ── Payment audit (full, partial and split charges) ──
    def registrar_pago(self, pedido_id, metodo, monto_total,
                       monto_efectivo=0.0, monto_transferencia=0.0, productos=""):
        """
        Records a charge in the `pagos_pedido` audit table. It must be
        called once for each charge made (if an order is charged
        in several parts, it is called several times). It is the source the
        reports use to know how much cash/transfer came in today.
        """
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            """INSERT INTO pagos_pedido
               (pedido_id, fecha, metodo, monto_total, monto_efectivo, monto_transferencia, productos)
               VALUES (?,?,?,?,?,?,?)""",
            (pedido_id, fecha, metodo, float(monto_total),
             float(monto_efectivo), float(monto_transferencia), productos)
        )
        self.conn.commit()

    def get_totales_pagos_hoy(self):
        """Sum of cash/transfer/total actually charged today,
        according to the payment audit (includes partial charges and
        split bills correctly broken down)."""
        hoy = datetime.now().strftime("%Y-%m-%d")
        row = self.conn.execute(
            """SELECT COALESCE(SUM(monto_efectivo),0) as efectivo,
                      COALESCE(SUM(monto_transferencia),0) as transferencia,
                      COALESCE(SUM(monto_total),0) as total
               FROM pagos_pedido WHERE fecha LIKE ?""",
            (f"{hoy}%",)
        ).fetchone()
        return {"efectivo": row["efectivo"], "transferencia": row["transferencia"], "total": row["total"]}

    # ── Reports ────────────────────────────────────────────────
    def get_pedidos_hoy(self):
        hoy = datetime.now().strftime("%Y-%m-%d")
        return self.conn.execute(
            "SELECT * FROM pedidos WHERE fecha_apertura LIKE ? ORDER BY fecha_apertura DESC",
            (f"{hoy}%",)
        ).fetchall()

    def get_productos_mas_vendidos(self, limit=10):
        return self.conn.execute("""
            SELECT lp.nombre_producto,
                   SUM(lp.cantidad) as total_uds,
                   SUM(lp.subtotal) as total_euros
            FROM lineas_pedido lp
            JOIN pedidos p ON lp.pedido_id = p.id
            WHERE p.estado='cerrado'
            GROUP BY lp.nombre_producto
            ORDER BY total_uds DESC
            LIMIT ?
        """, (limit,)).fetchall()

    def add_cierre_caja(self, efectivo, transferencias, gastos, total_comandas):
        """
        Saves the cash close. The "scoop" is NO longer requested.

        `efectivo` must come as the day's NET cash, that is, already
        with expenses deducted (what should physically be left in
        the register). To rebuild the total actually sold (and be able to
        compare it against `total_comandas`), the expense is added back
        here, because that money also corresponds to sales already
        charged — it just left the register to pay for something:

            Balanced Total = Net cash + Expenses + Transfers
            Difference     = Balanced Total - Orders Total
        """
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_cuadrado = float(efectivo) + float(transferencias) + float(gastos)
        diferencia = total_cuadrado - float(total_comandas)

        self.conn.execute(
            """INSERT INTO cierres_caja
               (fecha, total_efectivo, total_transferencias, total_gastos, total_primicia, total_cuadrado, total_comandas, diferencia)
               VALUES (?, ?, ?, ?, 0, ?, ?, ?)""",
            (fecha, float(efectivo), float(transferencias), float(gastos),
             total_cuadrado, float(total_comandas), diferencia)
        )
        self.conn.commit()

    def get_cierres_caja(self, fecha_inicio=None, fecha_fin=None):
        """
        Returns the history of saved cash closes, sorted by
        date. If fecha_inicio/fecha_fin are given ('YYYY-MM-DD', both
        inclusive), it filters only that range; otherwise it returns everything.
        """
        if fecha_inicio and fecha_fin:
            return self.conn.execute(
                """SELECT * FROM cierres_caja
                   WHERE DATE(fecha) BETWEEN ? AND ?
                   ORDER BY fecha ASC""",
                (fecha_inicio, fecha_fin)
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM cierres_caja ORDER BY fecha ASC"
        ).fetchall()

    def get_gastos_por_rango(self, fecha_inicio, fecha_fin):
        """fecha_inicio/fecha_fin in 'YYYY-MM-DD' format, both inclusive."""
        return self.conn.execute(
            """SELECT * FROM gastos WHERE DATE(fecha) BETWEEN ? AND ? ORDER BY fecha ASC""",
            (fecha_inicio, fecha_fin)
        ).fetchall()
    
    # ── Expenses of the day ─────────────────────────────────────
    def add_gasto(self, motivo, valor):
        """Registers a new expense of the day."""
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            "INSERT INTO gastos (fecha, motivo, valor) VALUES (?, ?, ?)",
            (fecha, motivo, float(valor))
        )
        self.conn.commit()

    def get_gastos_hoy(self):
        """Returns the list of expenses recorded on the current date."""
        hoy = datetime.now().strftime("%Y-%m-%d")
        return self.conn.execute(
            "SELECT id, fecha, motivo, valor FROM gastos WHERE fecha LIKE ? ORDER BY id DESC",
            (f"{hoy}%",)
        ).fetchall()

    def delete_gasto(self, gasto_id):
        """Deletes an expense by ID."""
        self.conn.execute("DELETE FROM gastos WHERE id = ?", (gasto_id,))
        self.conn.commit()

    def cerrar(self):
        self.conn.close()