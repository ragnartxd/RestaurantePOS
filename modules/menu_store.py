"""
Manages the menu as a single JSON
file on disk.

Both the central system and the waitstaff Flask server
read and write this SAME file. Since each operation re-reads the JSON
from disk before responding, any change made from the
central system is immediately available to the waitstaff
system — and vice versa.

The file is human-readable and can be edited by hand if needed
(for example, to restore a backup), but normally it is
always edited from the app ("Menú" tab of the central system).
"""

import json
import os
import threading
from datetime import datetime

from modules.rutas_base import carpeta_base


class MenuStore:
    def __init__(self, path=None):
        if path is None:
            base = carpeta_base()
            path = os.path.join(base, "data", "menu.json")
        self.path = path
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self._escribir({"categorias": [], "productos": [], "siguiente_id": 1})

    # ── Low-level I/O ──────────────────────────────────────────────
    def _leer(self):
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                data = {"categorias": [], "productos": [], "siguiente_id": 1}
            data.setdefault("categorias", [])
            data.setdefault("productos", [])
            data.setdefault("siguiente_id", 1)
            return data

    def _escribir(self, data):
        with self._lock:
            tmp_path = self.path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.path)  # atomic write

    # ── Migration from SQLite (first time only) ─────────────────────
    def migrar_desde_sqlite_si_hace_falta(self, conn):
        """
        If the JSON is empty but the old SQLite DB has products
        (previous app version), imports EVERYTHING so nothing is lost
        from the existing menu.
        """
        data = self._leer()
        if data["productos"]:
            return  # the JSON already has data, do not touch anything

        try:
            cur = conn.execute("""
                SELECT p.id, p.nombre, p.precio, p.disponible, p.descripcion,
                       c.nombre as categoria
                FROM productos p
                LEFT JOIN categorias c ON p.categoria_id = c.id
                ORDER BY p.id
            """)
            filas = cur.fetchall()
        except Exception:
            filas = []

        if not filas:
            return

        categorias = []
        productos = []
        max_id = 0
        for f in filas:
            cat = f["categoria"] or ""
            if cat and cat not in categorias:
                categorias.append(cat)
            productos.append({
                "id": f["id"],
                "nombre": f["nombre"],
                "precio": float(f["precio"]),
                "categoria": cat,
                "descripcion": f["descripcion"] or "",
                "disponible": bool(f["disponible"]),
            })
            max_id = max(max_id, f["id"])

        self._escribir({
            "categorias": categorias,
            "productos": productos,
            "siguiente_id": max_id + 1,
        })

    # ── Categories ─────────────────────────────────────────────────
    def get_categorias(self):
        return list(self._leer()["categorias"])

    def _asegurar_categoria(self, data, categoria):
        categoria = (categoria or "").strip()
        if categoria and categoria not in data["categorias"]:
            data["categorias"].append(categoria)
        return categoria

    # ── Products ───────────────────────────────────────────────────
    def get_productos(self, solo_disponibles=True):
        data = self._leer()
        prods = data["productos"]
        if solo_disponibles:
            prods = [p for p in prods if p.get("disponible", True)]
        return sorted(prods, key=lambda p: ((p.get("categoria") or ""), p.get("nombre") or ""))

    def get_producto(self, pid):
        data = self._leer()
        return next((p for p in data["productos"] if p["id"] == pid), None)

    def get_producto_by_name(self, nombre):
        nombre = (nombre or "").lower().strip()
        data = self._leer()
        return [
            p for p in data["productos"]
            if p.get("disponible", True) and nombre in p["nombre"].lower()
        ]

    def add_producto(self, nombre, precio, categoria, descripcion="", comentarios=None):
        with self._lock:
            data = self._leer()
            categoria = self._asegurar_categoria(data, categoria)

            ids = [p["id"] for p in data["productos"]]
            pid = (max(ids) + 1) if ids else 1

            data["productos"].append({
                "id": pid,
                "nombre": nombre,
                "precio": float(precio),
                "categoria": categoria,
                "descripcion": descripcion or "",
                "disponible": True,
                "comentarios": comentarios or []  # <-- Save the list of comments
            })

            data["siguiente_id"] = pid + 1
            self._escribir(data)
            return pid

    def update_producto(self, pid, nombre, precio, categoria, disponible, descripcion, comentarios=None):
        with self._lock:
            data = self._leer()
            categoria = self._asegurar_categoria(data, categoria)
            for p in data["productos"]:
                if p["id"] == pid:
                    p["nombre"] = nombre
                    p["precio"] = float(precio)
                    p["categoria"] = categoria
                    p["disponible"] = bool(disponible)
                    p["descripcion"] = descripcion or ""
                    p["comentarios"] = comentarios if comentarios is not None else p.get("comentarios", []) # <-- Update
                    break
            self._escribir(data)

    def actualizar_precio(self, pid, nuevo_precio):
        """Updates ONLY the product's base price in the menu (does not affect orders already taken)."""
        with self._lock:
            data = self._leer()
            for p in data["productos"]:
                if p["id"] == pid:
                    p["precio"] = float(nuevo_precio)
                    break
            self._escribir(data)

    def delete_producto(self, pid):
        with self._lock:
            data = self._leer()
            data["productos"] = [p for p in data["productos"] if p["id"] != pid]
            self._escribir(data)