"""
inventory.

Maintains two groups of stock, each in its own grid:

  - "menu"  → the meats of the Lunch dishes (Ejecutivo / Del día):
             Beef, Chicken breast, Pork.
  - "carta" → the meats of the A-la-carte dishes:
             Baby, Churrasco, Pechuga Carta, Punta, Lomo, Lengua, Mojarra.

"""

import tkinter as tk
from tkinter import ttk, messagebox


# ── Meat identification rules by dish name ─────────────────────
def identificar_carne(nombre_producto):
    """
    Given the name of an already sold dish (nombre_producto of an order
    line), returns a tuple (tipo, nombre_carne) indicating which
    inventory meat must be deducted.
    """
    nombre = (nombre_producto or "").lower()

    # 1. A-la-carte meats (They take priority because they are specific dishes)
    if "churrasco" in nombre:
        return ("carta", "Churrasco")
    if "churrasco búfalo" in nombre:
        return ("carta", "Churrasco Búfalo")
    if "punta" in nombre:
        return ("carta", "Punta")
    if "baby" in nombre or "baby camarón" in nombre or "baby salsa champiñon" in nombre:
        return ("carta", "Baby")
    if "pechuga carta" in nombre or "pechuga parrilla" in nombre or "pechuga bbq" in nombre or "pechuga hawaiana" in nombre or "pechuga champiñón" in nombre or "pechuga camarón" in nombre:
        return ("carta", "Pechuga Carta")
    if "lomo" in nombre:
        return ("carta", "Lomo")
    if "lengua" in nombre:
        return ("carta", "Lengua")
    if "mojarra" in nombre:
        return ("carta", "Mojarra")

    # 2. Menu meats (Executive Lunches / Del día / Platters / Breakfast Portions)
    # If it contains executive menu, del día, platter or portion words:
    if any(k in nombre for k in ["ejecutivo", "del día", "del dia", "bandeja", "porcion", "porción", "combo", "transportador"]):
        if "cerdo" in nombre:
            return ("menu", "Cerdo")
        if "pechuga" in nombre or "pollo" in nombre:
            return ("menu", "Pechuga")
        if "res" in nombre:
            return ("menu", "Res")

    # 3. General fallback rule for simple Menu meats ("Res", "Cerdo", "Pechuga")
    if "cerdo" in nombre:
        return ("menu", "Cerdo")
    if "pechuga" in nombre or "pollo" in nombre:
        return ("menu", "Pechuga")
    if "res" in nombre:
        return ("menu", "Res")

    return None

class InventarioModule:
    def __init__(self, parent, db):
        self.parent = parent
        self.db = db
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        self.parent.columnconfigure(0, weight=1)
        self.parent.columnconfigure(1, weight=1)
        self.parent.rowconfigure(0, weight=1)

        self.tree_menu = self._build_rejilla(
            columna=0,
            titulo="🥩 CARNES DE MENÚ",
            subtitulo="",
            tipo="menu",
        )
        self.tree_carta = self._build_rejilla(
            columna=1,
            titulo="🥘 CARNES DE CARTA",
            subtitulo="",
            tipo="carta",
        )

    def _build_rejilla(self, columna, titulo, subtitulo, tipo):
        frame = tk.Frame(self.parent, bg="#16213e")
        frame.grid(row=0, column=columna, sticky="nsew",
                   padx=(8, 4) if columna == 0 else (4, 8), pady=8)

        tk.Label(frame, text=titulo,
                 font=("Segoe UI", 11, "bold"), bg="#16213e", fg="#e94560").pack(pady=(8, 4))
        tk.Label(frame, text=subtitulo,
                 font=("Segoe UI", 8), bg="#16213e", fg="#a0a8c0", justify="center").pack(pady=(0, 4))

        list_frame = tk.Frame(frame, bg="#16213e")
        list_frame.pack(fill="both", expand=True, padx=8)

        cols = ("Carne", "Stock", "Unidad")
        tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=14)
        for col in cols:
            tree.heading(col, text=col)
        tree.column("Carne", width=140)
        tree.column("Stock", width=80, anchor="e")
        tree.column("Unidad", width=90, anchor="center")
        tree.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        sb.pack(side="right", fill="y")
        tree.configure(yscrollcommand=sb.set)

        btn_frame = tk.Frame(frame, bg="#16213e")
        btn_frame.pack(fill="x", padx=8, pady=(6, 2))
        tk.Button(btn_frame, text="➕ Agregar stock",
                  bg="#27ae60", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2",
                  command=lambda t=tree: self._agregar_stock(t)).pack(side="left")
        tk.Button(btn_frame, text="✏️ Ajustar cantidad",
                  bg="#0f3460", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2",
                  command=lambda t=tree: self._ajustar_cantidad(t)).pack(side="left", padx=(6, 0))
        tk.Button(btn_frame, text="🔄",
                  bg="#34495e", fg="white", font=("Segoe UI", 9),
                  relief="flat", cursor="hand2",
                  command=self.refresh).pack(side="right")

        btn_frame2 = tk.Frame(frame, bg="#16213e")
        btn_frame2.pack(fill="x", padx=8, pady=(2, 6))
        tk.Button(btn_frame2, text="🆕 Nuevo insumo",
                  bg="#8e44ad", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2",
                  command=lambda tp=tipo: self._nuevo_insumo(tp)).pack(side="left")
        tk.Button(btn_frame2, text="🔗 Vincular productos",
                  bg="#16a085", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2",
                  command=lambda t=tree: self._vincular_productos(t)).pack(side="left", padx=(6, 0))
        tk.Button(btn_frame2, text="🗑️ Quitar del inventario",
                  bg="#c0392b", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2",
                  command=lambda t=tree: self._quitar_insumo(t)).pack(side="left", padx=(6, 0))

        return tree

    # ── Actions ───────────────────────────────────────────────
    def _agregar_stock(self, tree):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Sin selección", "Selecciona primero una carne de la lista.")
            return
        nombre = tree.item(sel[0])["values"][0]
        ventana = AjustarStockVentana(self.parent, nombre, modo="agregar")
        self.parent.wait_window(ventana.top)
        if ventana.resultado is not None:
            self.db.ajustar_stock_inventario(nombre, ventana.resultado)
            self.refresh()

    def _ajustar_cantidad(self, tree):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Sin selección", "Selecciona primero una carne de la lista.")
            return
        nombre = tree.item(sel[0])["values"][0]
        actual = tree.item(sel[0])["values"][1]
        ventana = AjustarStockVentana(self.parent, nombre, modo="fijar", valor_actual=actual)
        self.parent.wait_window(ventana.top)
        if ventana.resultado is not None:
            self.db.set_stock_inventario(nombre, ventana.resultado)
            self.refresh()

    def _nuevo_insumo(self, tipo):
        ventana = NuevoInsumoVentana(self.parent, tipo)
        self.parent.wait_window(ventana.top)
        if ventana.resultado is None:
            return
        nombre, unidad, cantidad_inicial = ventana.resultado
        try:
            self.db.agregar_item_inventario(nombre, tipo, unidad, cantidad_inicial)
        except Exception as e:
            if "UNIQUE" in str(e):
                messagebox.showerror("Ya existe", f"Ya hay un insumo llamado '{nombre}' en el inventario.")
            else:
                messagebox.showerror("Error", f"No se pudo crear el insumo:\n{e}")
            return
        self.refresh()
        messagebox.showinfo("✅ Insumo creado", f"'{nombre}' se agregó al inventario.")

    def _quitar_insumo(self, tree):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Sin selección", "Selecciona primero un insumo de la lista.")
            return
        nombre = tree.item(sel[0])["values"][0]
        if messagebox.askyesno(
            "Quitar del inventario",
            f"¿Quitar '{nombre}' del inventario?\n\n"
            "Se perderá su stock registrado y cualquier vínculo con\n"
            "productos del menú. Esta acción no se puede deshacer."
        ):
            self.db.eliminar_item_inventario(nombre)
            self.refresh()

    def _vincular_productos(self, tree):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Sin selección", "Selecciona primero un insumo de la lista.")
            return
        nombre_item = tree.item(sel[0])["values"][0]
        productos = [p["nombre"] for p in self.db.get_productos(solo_disponibles=False)]
        vinculados_actuales = self.db.get_vinculos_item(nombre_item)
        ventana = VincularProductosVentana(self.parent, nombre_item, productos, vinculados_actuales)
        self.parent.wait_window(ventana.top)
        if ventana.resultado is not None:
            self.db.set_vinculos_item(nombre_item, ventana.resultado)
            messagebox.showinfo(
                "✅ Vínculos guardados",
                f"'{nombre_item}' ahora se descuenta automáticamente al vender:\n\n"
                + ("\n".join(ventana.resultado) if ventana.resultado else "(ningún producto vinculado)")
            )

    def refresh(self):
        self._llenar(self.tree_menu, "menu")
        self._llenar(self.tree_carta, "carta")

    def _llenar(self, tree, tipo):
        tree.delete(*tree.get_children())
        for fila in self.db.get_inventario(tipo=tipo):
            cantidad = fila["cantidad"]
            texto_cantidad = f"{cantidad:g}"
            tag = "bajo" if cantidad <= 0 else ""
            tree.insert("", "end", values=(fila["nombre"], texto_cantidad, fila["unidad"]),
                        tags=(tag,) if tag else ())
        tree.tag_configure("bajo", foreground="#e94560")


class AjustarStockVentana:
    """
    Simple dialog to add stock.
    """
    def __init__(self, parent, nombre_carne, modo="agregar", valor_actual=0):
        self.resultado = None
        self.top = tk.Toplevel(parent)
        self.top.title("Inventario")
        self.top.grab_set()
        self.top.configure(bg="#1a1a2e")
        self.top.resizable(False, False)

        titulo = f"Agregar stock — {nombre_carne}" if modo == "agregar" else f"Ajustar cantidad — {nombre_carne}"
        tk.Label(self.top, text=titulo,
                 font=("Segoe UI", 13, "bold"),
                 bg="#1a1a2e", fg="#e94560", wraplength=280).pack(pady=(18, 8), padx=24)

        form = tk.Frame(self.top, bg="#1a1a2e")
        form.pack(fill="x", padx=24)

        etiqueta = "Cantidad a agregar" if modo == "agregar" else "Nueva cantidad exacta"
        tk.Label(form, text=etiqueta,
                 font=("Segoe UI", 9), bg="#1a1a2e", fg="#a0a8c0", anchor="w").pack(fill="x")

        valor_inicial = "" if modo == "agregar" else str(valor_actual)
        self.var_cantidad = tk.StringVar(value=valor_inicial)
        entry = tk.Entry(form, textvariable=self.var_cantidad,
                         bg="#16213e", fg="white", insertbackground="white",
                         relief="flat", font=("Segoe UI", 12))
        entry.pack(fill="x", pady=(2, 14))
        entry.focus_set()
        entry.select_range(0, "end")

        btns = tk.Frame(self.top, bg="#1a1a2e")
        btns.pack(fill="x", padx=24, pady=(0, 18))
        tk.Button(btns, text="✅ Confirmar",
                  bg="#27ae60", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", cursor="hand2", pady=8,
                  command=self._confirmar).pack(fill="x", pady=2)
        tk.Button(btns, text="Cancelar",
                  bg="#7f8c8d", fg="white",
                  relief="flat", cursor="hand2",
                  command=self.top.destroy).pack(fill="x", pady=2)

        entry.bind("<Return>", lambda e: self._confirmar())

    def _confirmar(self):
        texto = self.var_cantidad.get().strip().replace(",", ".")
        try:
            valor = float(texto)
        except ValueError:
            messagebox.showerror("Error", "Ingresa un número válido.")
            return
        self.resultado = valor
        self.top.destroy()


class NuevoInsumoVentana:
    """
    Dialog to add a new item to the inventory (besides the base
    meats). Asks for name, unit and initial stock quantity.
    Returns a tuple (name, unit, initial_quantity) in
    self.resultado, or None if cancelled.
    """
    def __init__(self, parent, tipo):
        self.resultado = None
        self.top = tk.Toplevel(parent)
        self.top.title("Nuevo insumo")
        self.top.grab_set()
        self.top.configure(bg="#1a1a2e")
        self.top.resizable(False, False)

        grupo = "Carnes de Menú" if tipo == "menu" else "Carnes de Carta" if tipo == "carta" else tipo.title()
        tk.Label(self.top, text=f"Nuevo insumo — {grupo}",
                 font=("Segoe UI", 13, "bold"),
                 bg="#1a1a2e", fg="#e94560", wraplength=280).pack(pady=(18, 8), padx=24)

        form = tk.Frame(self.top, bg="#1a1a2e")
        form.pack(fill="x", padx=24)

        def campo(etiqueta, var, valor_inicial=""):
            tk.Label(form, text=etiqueta, font=("Segoe UI", 9),
                     bg="#1a1a2e", fg="#a0a8c0", anchor="w").pack(fill="x", pady=(8, 0))
            var.set(valor_inicial)
            e = tk.Entry(form, textvariable=var,
                         bg="#16213e", fg="white", insertbackground="white",
                         relief="flat", font=("Segoe UI", 11))
            e.pack(fill="x", pady=(2, 0))
            return e

        self.var_nombre = tk.StringVar()
        self.var_unidad = tk.StringVar()
        self.var_cantidad = tk.StringVar()

        entry_nombre = campo("Nombre del insumo (ej: Papa, Gaseosa, Arroz)", self.var_nombre)
        campo("Unidad (ej: unidades, kg, litros, porciones)", self.var_unidad, "unidades")
        campo("Cantidad inicial de stock", self.var_cantidad, "0")

        btns = tk.Frame(self.top, bg="#1a1a2e")
        btns.pack(fill="x", padx=24, pady=(16, 18))
        tk.Button(btns, text="✅ Crear insumo",
                  bg="#27ae60", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", cursor="hand2", pady=8,
                  command=self._confirmar).pack(fill="x", pady=2)
        tk.Button(btns, text="Cancelar",
                  bg="#7f8c8d", fg="white",
                  relief="flat", cursor="hand2",
                  command=self.top.destroy).pack(fill="x", pady=2)

        entry_nombre.focus_set()

    def _confirmar(self):
        nombre = self.var_nombre.get().strip()
        unidad = self.var_unidad.get().strip() or "unidades"
        cantidad_texto = self.var_cantidad.get().strip().replace(",", ".") or "0"

        if not nombre:
            messagebox.showerror("Error", "El nombre del insumo es obligatorio.")
            return
        try:
            cantidad = float(cantidad_texto)
        except ValueError:
            messagebox.showerror("Error", "La cantidad inicial debe ser un número.")
            return

        self.resultado = (nombre, unidad, cantidad)
        self.top.destroy()


class VincularProductosVentana:
    """
    Dialog to choose which menu products, when sold, automatically
    deduct 1 unit of an inventory item. Shows a
    multiple-selection list of ALL the menu products.
    """
    def __init__(self, parent, nombre_item, productos, vinculados_actuales):
        self.resultado = None
        self.top = tk.Toplevel(parent)
        self.top.title("Vincular productos")
        self.top.grab_set()
        self.top.configure(bg="#1a1a2e")
        self.top.geometry("360x480")
        self.top.resizable(False, False)

        tk.Label(self.top, text=f"Vincular productos — {nombre_item}",
                 font=("Segoe UI", 13, "bold"),
                 bg="#1a1a2e", fg="#e94560", wraplength=320).pack(pady=(18, 4), padx=20)
        tk.Label(self.top,
                 text="Al vender cualquiera de los productos marcados,\n"
                      "se descontará automáticamente 1 unidad de este\n"
                      "insumo por cada unidad vendida.",
                 font=("Segoe UI", 8.5), bg="#1a1a2e", fg="#a0a8c0",
                 justify="center").pack(pady=(0, 10), padx=20)

        list_frame = tk.Frame(self.top, bg="#1a1a2e")
        list_frame.pack(fill="both", expand=True, padx=20)

        sb = ttk.Scrollbar(list_frame, orient="vertical")
        self.listbox = tk.Listbox(
            list_frame, selectmode="multiple", activestyle="none",
            bg="#16213e", fg="white", selectbackground="#e94560",
            selectforeground="white", relief="flat", font=("Segoe UI", 10),
            yscrollcommand=sb.set, exportselection=False
        )
        sb.config(command=self.listbox.yview)
        sb.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)

        vinculados_set = set(vinculados_actuales)
        self._productos = sorted(productos)
        for i, nombre_prod in enumerate(self._productos):
            self.listbox.insert("end", nombre_prod)
            if nombre_prod in vinculados_set:
                self.listbox.selection_set(i)

        btns = tk.Frame(self.top, bg="#1a1a2e")
        btns.pack(fill="x", padx=20, pady=(12, 18))
        tk.Button(btns, text="✅ Guardar vínculos",
                  bg="#27ae60", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", cursor="hand2", pady=8,
                  command=self._confirmar).pack(fill="x", pady=2)
        tk.Button(btns, text="Cancelar",
                  bg="#7f8c8d", fg="white",
                  relief="flat", cursor="hand2",
                  command=self.top.destroy).pack(fill="x", pady=2)

    def _confirmar(self):
        seleccionados = [self._productos[i] for i in self.listbox.curselection()]
        self.resultado = seleccionados
        self.top.destroy()