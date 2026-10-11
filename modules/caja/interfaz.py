"""
Cash register visual panel + module orchestration

Contains the CajaModule class: the Tkinter cash register interface (menu, ticket,
tables, buttons, colors, icons) together with order and payment
orchestration. Included drinks and variant groups are computed elsewhere.

"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
from venv import logger

from modules.impresora_cocina import agregar_comanda_cocina

from .logica import (
    GRUPOS_VARIANTES,
    _NOMBRES_EN_GRUPO,
    ALMUERZOS_LIMONADA,
    BEBIDAS_DESAYUNO,
    BEBIDAS_ALMUERZO,
    _desayuno_incluye_bebida,
    recalcular_bebidas_pedido,
    calcular_bebidas_incluidas,
    es_bebida_desayuno,
    es_bebida_almuerzo,
)
from .dialogos import CobroVentana, DividirCuentaVentana, EditarPrecioVentana, MotivoCancelacionVentana

class CajaModule:
    def __init__(self, parent, db):
        self.parent = parent
        self.db = db
        self.pedido_actual_id = None
        self._build_ui()

    def _build_ui(self):
        self.parent.columnconfigure(0, weight=3)
        self.parent.columnconfigure(1, weight=2)
        self.parent.columnconfigure(2, weight=2)
        self.parent.rowconfigure(0, weight=1)

        self._build_panel_menu()
        self._build_panel_ticket()
        self._build_panel_mesas()

    # ── Left panel: menu ──────────────────────────────────────
    def _build_panel_menu(self):
        frame = tk.Frame(self.parent, bg="#16213e")
        frame.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)

        tk.Label(frame, text="MENÚ", font=("Segoe UI", 11, "bold"),
                 bg="#16213e", fg="#e94560").pack(pady=(8, 4))

        search_frame = tk.Frame(frame, bg="#16213e")
        search_frame.pack(fill="x", padx=8, pady=(0, 6))
        tk.Label(search_frame, text="🔍", bg="#16213e", fg="#a0a8c0").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._filtrar_menu())
        tk.Entry(search_frame, textvariable=self.search_var,
                 bg="#0f3460", fg="white", insertbackground="white",
                 relief="flat", font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True, padx=4)

        self.cat_var = tk.StringVar(value="Todas")
        self.cat_combo = ttk.Combobox(frame, textvariable=self.cat_var, state="readonly",
                                      font=("Segoe UI", 9))
        self.cat_combo.pack(fill="x", padx=8, pady=(0, 6))
        self.cat_combo.bind("<<ComboboxSelected>>", lambda e: self._filtrar_menu())

        list_frame = tk.Frame(frame, bg="#16213e")
        list_frame.pack(fill="both", expand=True, padx=8)

        cols = ("Producto", "Precio", "Categoría")
        self.tree_menu = ttk.Treeview(list_frame, columns=cols, show="headings",
                                      selectmode="browse", height=20)
        for col in cols:
            self.tree_menu.heading(col, text=col)
        self.tree_menu.column("Producto", width=180)
        self.tree_menu.column("Precio", width=90, anchor="e")
        self.tree_menu.column("Categoría", width=100)
        self.tree_menu.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree_menu.yview)
        sb.pack(side="right", fill="y")
        self.tree_menu.configure(yscrollcommand=sb.set)
        self.tree_menu.bind("<Double-1>", self._agregar_desde_menu)

        btn_frame = tk.Frame(frame, bg="#16213e")
        btn_frame.pack(fill="x", padx=8, pady=6)
        tk.Button(btn_frame, text="➕ Agregar al pedido",
                  bg="#e94560", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2",
                  command=self._agregar_desde_menu_btn).pack(fill="x")

        self.refresh_menu()

    # ── Center panel: ticket ──────────────────────────────────
    def _build_panel_ticket(self):
        frame = tk.Frame(self.parent, bg="#0f3460")
        frame.grid(row=0, column=1, sticky="nsew", padx=4, pady=8)

        h = tk.Frame(frame, bg="#e94560", height=40)
        h.pack(fill="x")
        h.pack_propagate(False)
        self.lbl_ticket_title = tk.Label(h, text="TICKET — sin pedido",
                                         font=("Segoe UI", 10, "bold"),
                                         bg="#e94560", fg="white")
        self.lbl_ticket_title.pack(side="left", padx=12, pady=8)

        list_frame = tk.Frame(frame, bg="#0f3460")
        list_frame.pack(fill="both", expand=True, padx=8, pady=4)

        cols = ("Producto", "Cant.", "Precio", "Total")
        self.tree_ticket = ttk.Treeview(list_frame, columns=cols, show="tree headings",
                                        selectmode="extended", height=10)
        
        self.tree_ticket.heading("Producto", text="Producto")
        self.tree_ticket.heading("Cant.", text="Cant.")
        self.tree_ticket.heading("Precio", text="P.Unit.")
        self.tree_ticket.heading("Total", text="Total")
        self.tree_ticket.column("Producto", width=200, minwidth=120, stretch=True)
        self.tree_ticket.column("#0", width=0, minwidth=0, stretch=False)  # hide the tree column
        self.tree_ticket.column("Cant.", width=45, anchor="center")
        self.tree_ticket.column("Precio", width=80, anchor="e")
        self.tree_ticket.column("Total", width=80, anchor="e")
        self.tree_ticket.pack(side="left", fill="both", expand=True)

        sb2 = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree_ticket.yview)
        sb2.pack(side="right", fill="y")
        self.tree_ticket.configure(yscrollcommand=sb2.set)

        self.lbl_bebidas = tk.Label(frame, text="",
                                    font=("Segoe UI", 8, "italic"),
                                    bg="#0f3460", fg="#f39c12", wraplength=280)
        self.lbl_bebidas.pack(fill="x", padx=8)

        total_frame = tk.Frame(frame, bg="#16213e")
        total_frame.pack(fill="x", padx=8, pady=6)
        tk.Label(total_frame, text="TOTAL:", font=("Segoe UI", 14, "bold"),
                 bg="#16213e", fg="#a0a8c0").pack(side="left")
        self.lbl_total = tk.Label(total_frame, text="$ 0",
                                  font=("Segoe UI", 18, "bold"),
                                  bg="#16213e", fg="#e94560")
        self.lbl_total.pack(side="right", padx=8)

        btn_frame = tk.Frame(frame, bg="#0f3460")
        btn_frame.pack(fill="x", padx=8, pady=6)

        tk.Button(btn_frame, text="💬 Agregar comentario",
                  bg="#8e44ad", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2",
                  command=self._agregar_comentario_linea).pack(fill="x", pady=2)

        tk.Button(btn_frame, text="✏️ Editar precio unitario",
                  bg="#e67e22", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2",
                  command=self._editar_precio_linea).pack(fill="x", pady=2)

        tk.Button(btn_frame, text="🗑️ Quitar línea",
                  bg="#c0392b", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2",
                  command=self._quitar_linea).pack(fill="x", pady=2)
        
        tk.Button(btn_frame, text="🖨️ Enviar Comanda",
                  bg="#ff32b1", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2",
                  command=self._enviar_comanda_cocina).pack(fill="x", padx=2)

        tk.Button(btn_frame, text="💳 COBRAR",
                  bg="#27ae60", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2",
                  command=self._cobrar).pack(fill="x", pady=2)

        tk.Button(btn_frame, text="❌ Cancelar pedido",
                  bg="#7f8c8d", fg="white", font=("Segoe UI", 9),
                  relief="flat", cursor="hand2",
                  command=self._cancelar_pedido).pack(fill="x", pady=2)

    
    # ── Right panel: open orders ──────────────────────────────
    def _build_panel_mesas(self):
        frame = tk.Frame(self.parent, bg="#16213e")
        frame.grid(row=0, column=2, sticky="nsew", padx=(4, 8), pady=8)

        tk.Label(frame, text="PEDIDOS ABIERTOS", font=("Segoe UI", 11, "bold"),
                 bg="#16213e", fg="#e94560").pack(pady=(8, 4))

        tk.Button(frame, text="➕ Nuevo Pedido",
                  bg="#e94560", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", cursor="hand2",
                  command=self._nuevo_pedido).pack(fill="x", padx=10, pady=4)

        # Scrollable canvas for the grid of cards
        canvas_wrapper = tk.Frame(frame, bg="#16213e")
        canvas_wrapper.pack(fill="both", expand=True, padx=8, pady=4)

        self._canvas_mesas = tk.Canvas(canvas_wrapper, bg="#16213e",
                                        highlightthickness=0)
        sb3 = ttk.Scrollbar(canvas_wrapper, orient="vertical",
                             command=self._canvas_mesas.yview)
        self._canvas_mesas.configure(yscrollcommand=sb3.set)
        sb3.pack(side="right", fill="y")
        self._canvas_mesas.pack(side="left", fill="both", expand=True)

        # Inner frame that lives inside the canvas
        self._frame_mesas = tk.Frame(self._canvas_mesas, bg="#16213e")
        self._canvas_window = self._canvas_mesas.create_window(
            (0, 0), window=self._frame_mesas, anchor="nw")

        # Update the scroll region when the size changes
        def _on_frame_configure(event):
            self._canvas_mesas.configure(
                scrollregion=self._canvas_mesas.bbox("all"))
        self._frame_mesas.bind("<Configure>", _on_frame_configure)

        # Expand the inner frame to the canvas width
        def _on_canvas_resize(event):
            self._canvas_mesas.itemconfig(
                self._canvas_window, width=event.width)
        self._canvas_mesas.bind("<Configure>", _on_canvas_resize)

        # Keep a reference to the orders for selection
        self._pedido_cards = {}

        tk.Button(frame, text="🔄 Actualizar",
                  bg="#34495e", fg="white", font=("Segoe UI", 9),
                  relief="flat", cursor="hand2",
                  command=self.refresh_pedidos).pack(fill="x", padx=10, pady=4)

        self.refresh_pedidos()

    # ── Included drinks logic ─────────────────────────────────
    def _calcular_cupo_bebidas(self):
        if not self.pedido_actual_id:
            return 0, 0

        lineas = self.db.get_lineas(self.pedido_actual_id)

        print("LINEAS:")
        for l in lineas:
            print(vars(l) if hasattr(l, "__dict__") else l)

        return calcular_bebidas_incluidas(lineas)

    def _actualizar_info_bebidas(self):
        d, a = self._calcular_cupo_bebidas()
        partes = []
        if d > 0:
            partes.append(f"☕ {d} bebida(s) de desayuno incluida(s)")
        if a > 0:
            partes.append(f"🍋 {a} limonada(s) de almuerzo incluida(s)")
        self.lbl_bebidas.config(text="  |  ".join(partes) if partes else "")

    def _resolver_precio_bebida(self, nombre_producto, precio_original):
        nombre = nombre_producto.lower().strip()
        cupo_d, cupo_a = self._calcular_cupo_bebidas()

        if nombre in BEBIDAS_ALMUERZO and cupo_a > 0:
            return 0.0, True
        if nombre in BEBIDAS_DESAYUNO and cupo_d > 0:
            return 0.0, True
        return precio_original, False

    # ── Variant selection ─────────────────────────────────────
    def _pedir_variante(self, nombre_grupo, variantes, precio, cant, precio_max=None):

        win = tk.Toplevel(self.parent)
        win.title(nombre_grupo)
        win.configure(bg="#1a1a2e")
        win.grab_set()
        win.resizable(False, False)

        tk.Label(win, text=nombre_grupo,
                 font=("Segoe UI", 13, "bold"),
                 bg="#1a1a2e", fg="#e94560").pack(pady=(18, 4), padx=24)
        precio_txt = (f"Cantidad: {cant}  •  desde ${precio:,.0f} c/u"
                      if precio_max and precio_max > precio
                      else f"Cantidad: {cant}  •  ${precio:,.0f} c/u")
        tk.Label(win, text=precio_txt,
                 font=("Segoe UI", 10),
                 bg="#1a1a2e", fg="#a0a8c0").pack(pady=(0, 12))

        resultado = {"nombre": None}

        def elegir(nombre_real):
            resultado["nombre"] = nombre_real
            win.destroy()

        n_variantes = len(variantes)
        columnas = 1 if n_variantes <= 6 else (2 if n_variantes <= 16 else 3)
        ancho_boton = 20 if columnas == 1 else 16

        win.update_idletasks()
        alto_pantalla = win.winfo_screenheight()
        alto_max_lista = max(200, int(alto_pantalla * 0.55))

        contenedor = tk.Frame(win, bg="#1a1a2e")
        contenedor.pack(padx=16, pady=(0, 8), fill="both", expand=True)

        canvas = tk.Canvas(contenedor, bg="#1a1a2e", highlightthickness=0,
                            width=(ancho_boton * 10 + 20) * columnas)
        scrollbar = tk.Scrollbar(contenedor, orient="vertical", command=canvas.yview)
        frame_botones = tk.Frame(canvas, bg="#1a1a2e")

        frame_botones.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=frame_botones, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for i, (etiqueta, nombre_real) in enumerate(variantes):
            fila, col = divmod(i, columnas)
            tk.Button(frame_botones, text=etiqueta,
                      bg="#0f3460", fg="white",
                      font=("Segoe UI", 12, "bold"),
                      relief="flat", cursor="hand2", width=ancho_boton, pady=10,
                      wraplength=140 if columnas > 1 else 0,
                      command=lambda nr=nombre_real: elegir(nr)
                      ).grid(row=fila, column=col, padx=4, pady=3, sticky="nsew")

        # Only show the scrollbar / limit the height if the content does not fit
        frame_botones.update_idletasks()
        alto_contenido = frame_botones.winfo_reqheight()
        if alto_contenido > alto_max_lista:
            canvas.configure(height=alto_max_lista)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            def _on_mousewheel(event):
                delta = event.delta
                if delta == 0:
                    delta = 120 if getattr(event, "num", 0) == 4 else -120
                canvas.yview_scroll(int(-delta / 120), "units")
            canvas.bind_all("<MouseWheel>", _on_mousewheel)   # Windows
            canvas.bind_all("<Button-4>", _on_mousewheel)     # Linux scroll up
            canvas.bind_all("<Button-5>", _on_mousewheel)     # Linux scroll down
            win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))
        else:
            canvas.configure(height=alto_contenido)
            canvas.pack(fill="both", expand=True)

        tk.Button(win, text="Cancelar",
                  bg="#7f8c8d", fg="white",
                  relief="flat", cursor="hand2",
                  command=win.destroy).pack(pady=(8, 16))

        self.parent.wait_window(win)
        return resultado["nombre"]

    # ── Ask for a comment ─────────────────────────────────────
    def _pedir_comentario(self, nombre_producto=""):
        """Returns a string with the comment (may be empty)."""
        win = tk.Toplevel(self.parent)
        win.title("Comentario")
        win.configure(bg="#1a1a2e")
        win.grab_set()
        win.resizable(False, False)

        tk.Label(win, text="Comentario / instrucción especial",
                 font=("Segoe UI", 11, "bold"),
                 bg="#1a1a2e", fg="#e94560").pack(pady=(16, 4), padx=20)
        if nombre_producto:
            tk.Label(win, text=nombre_producto,
                     font=("Segoe UI", 9, "italic"),
                     bg="#1a1a2e", fg="#a0a8c0").pack(pady=(0, 8))

        txt = tk.Text(win, width=32, height=4,
                      bg="#0f3460", fg="white",
                      insertbackground="white",
                      font=("Segoe UI", 11),
                      relief="flat", wrap="word")
        txt.pack(padx=20, pady=4)
        txt.focus_set()

        resultado = {"comentario": ""}

        def confirmar():
            resultado["comentario"] = txt.get("1.0", "end").strip()
            win.destroy()

        def on_enter(e):
            confirmar()
            return "break"

        txt.bind("<Return>", on_enter)

        tk.Button(win, text="✔ Aceptar",
                  bg="#27ae60", fg="white",
                  font=("Segoe UI", 11, "bold"),
                  relief="flat", cursor="hand2", width=18,
                  command=confirmar).pack(pady=(8, 4))
        tk.Button(win, text="Sin comentario",
                  bg="#7f8c8d", fg="white",
                  relief="flat", cursor="hand2",
                  command=win.destroy).pack(pady=(0, 14))

        self.parent.wait_window(win)
        return resultado["comentario"]

    # ── Actions ───────────────────────────────────────────────
    def _nuevo_pedido(self):
        mesa = simpledialog.askstring("Nuevo Pedido", "Número/Nombre de mesa:",
                                      parent=self.parent)
        if not mesa:
            return
        mesa = mesa.strip()

        # If that table already has an open order (created from the central
        # station or from a waitress's phone), a new ticket is not created: the
        # same order is reopened and anything added from here on is recorded
        # as a separate round/addition within it. This avoids sending the
        # whole order to the kitchen again.

        existente = self.db.get_pedido_abierto_por_mesa(mesa)
        if existente:
            pid = existente["id"]
            nueva_ronda =self.db.nueva_ronda_pedido(pid, origen="central")
            messagebox.showinfo(
                "Mesa ya abierta",
                f"La mesa {existente['mesa']} ya tiene un pedido abierto (#{pid}).\n"
                "Se usará ese mismo ticket y lo que agregues se sumará como un añadido."
            )
            self.ronda_actual = nueva_ronda
        else:
            pid = self.db.crear_pedido(mesa)

        self.refresh_pedidos()
        self._cargar_pedido(pid)

    def _seleccionar_pedido(self, event=None):
        sel = self.tree_pedidos.selection()
        if not sel:
            return
        pid = int(self.tree_pedidos.item(sel[0])["values"][3])
        self._cargar_pedido(pid)

    def _seleccionar_pedido_por_id(self, pid):
        """Selects an order from the visual table cards."""
        self.pedido_actual_id = pid
        # Update the colors of all the cards
        for card_pid, card in self._pedido_cards.items():
            color = "#e94560" if card_pid == pid else "#0f3460"
            card.config(bg=color)
            for child in card.winfo_children():
                child.config(bg=color)
        # Load the ticket as before.
        # Note: selecting/viewing a table must NOT create a new round; that
        # should only happen when an addition is explicitly made
        # (see _nuevo_pedido). Here we only sync with the current round
        # in the database, so that "Send order" prints the correct round
        # and not an empty one created by a simple click.
        pedido = self.db.get_pedido(pid)
        if pedido:
            self.ronda_actual = self.db.get_ronda_actual(pid)

            self.lbl_ticket_title.config(
                text=self._texto_titulo_ticket(pedido, pid)
            )
        self._refresh_ticket()

    def _cargar_pedido(self, pedido_id):
        self.pedido_actual_id = pedido_id
        pedido = self.db.get_pedido(pedido_id)

        self.ronda_actual = self.db.get_ronda_actual(pedido_id)

        self.lbl_ticket_title.config(
            text=self._texto_titulo_ticket(pedido, pedido_id))
        self._refresh_ticket()

    def _texto_titulo_ticket(self, pedido, pedido_id):
        """
        Ticket bar text: 'TICKET — Mesa 5-2 (#12) · 🧍 Alex'
        when the order comes from the waitstaff app; without the name if it was
        taken directly at the register (no change in that case).

        The table name coming from the waitstaff app already arrives as
        'Mesa 5' or 'Mesa 5-2', so 'Mesa' is NOT prepended again here
        (avoids the 'Mesa Mesa 5' that used to show up). If instead it was
        created at the register by typing just a number or a loose name
        (e.g. 'Terraza'), 'Mesa' is still prepended as always.
        """
        nombre_mesa = (pedido["mesa"] or "").strip()
        etiqueta_mesa = nombre_mesa if nombre_mesa.lower().startswith("mesa") else f"Mesa {nombre_mesa}"
        base = f"TICKET — {etiqueta_mesa} (#{pedido_id})"
        mesera = self.db.mesera_de_pedido(pedido)
        return f"{base}  ·  🧍 {mesera}" if mesera else base

    def _refresh_ticket(self):
        self.tree_ticket.delete(*self.tree_ticket.get_children())
        if not self.pedido_actual_id:
            self.lbl_total.config(text="$ 0")
            self.lbl_bebidas.config(text="")
            return

        lineas = self.db.get_lineas(self.pedido_actual_id)
        total = 0.0
        for l in lineas:
            incluida = l["es_bebida_incluida"]
            precio_txt = "INCLUIDA" if incluida else f"${l['precio_unitario']:,.0f}"
            total_txt  = "—" if incluida else f"${l['subtotal']:,.0f}"
            tag = "incluida" if incluida else ""
            # Show the comment in the name if there is one
            nombre_mostrar = l["nombre_producto"]
            self.tree_ticket.insert("", "end", iid=str(l["id"]),
                                    values=(nombre_mostrar, l["cantidad"],
                                            precio_txt, total_txt),
                                    tags=(tag,))
            # Comment in a separate child row, never overlaps
            if l["notas"] and l["notas"] not in ("incluida",):
                self.tree_ticket.insert(str(l["id"]), "end",
                                        values=(f"    ✎ {l['notas']}", "", "", ""),
                                        tags=("nota",))
                self.tree_ticket.item(str(l["id"]), open=True)

            total += l["subtotal"]

        self.tree_ticket.tag_configure("incluida", foreground="#27ae60")
        self.tree_ticket.tag_configure("nota", foreground="#f39c12", font=("Segoe UI", 9, "italic"))
        self.lbl_total.config(text=f"$ {total:,.0f}")
        self._actualizar_info_bebidas()

    def refresh_pedidos(self):
        # Clear previous cards
        for w in self._frame_mesas.winfo_children():
            w.destroy()
        self._pedido_cards.clear()

        pedidos = self.db.get_pedidos_abiertos()

        COLS = 2 
        CARD_BG = "#0f3460"
        CARD_SEL = "#e94560"

        for idx, p in enumerate(pedidos):
            row, col = divmod(idx, COLS)
            hora = p["fecha_apertura"][11:16]
            pid  = p["id"]

            card = tk.Frame(self._frame_mesas, bg=CARD_BG,
                            relief="ridge", bd=2, cursor="hand2")
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            self._frame_mesas.columnconfigure(col, weight=1)

            # Large table number/name
            tk.Label(card, text=str(p["mesa"]),
                     font=("Segoe UI", 16, "bold"),
                     bg=CARD_BG, fg="#ffffff",
                     wraplength=110).pack(pady=(10, 2), padx=8)

            # Total
            tk.Label(card, text=f"${p['total']:,.0f}",
                     font=("Segoe UI", 11),
                     bg=CARD_BG, fg="#27ae60").pack(pady=1)

            # Time
            tk.Label(card, text=hora,
                     font=("Segoe UI", 9),
                     bg=CARD_BG, fg="#a0a8c0").pack(pady=(1, 8))

            self._pedido_cards[pid] = card

            # Highlight if it is the currently selected order
            if pid == self.pedido_actual_id:
                card.config(bg=CARD_SEL)
                for child in card.winfo_children():
                    child.config(bg=CARD_SEL)

            # Click on the card → select the order
            def _on_click(event, pid=pid):
                self._seleccionar_pedido_por_id(pid)
            card.bind("<Button-1>", _on_click)
            for child in card.winfo_children():
                child.bind("<Button-1>", _on_click)

    def refresh_menu(self):
        cats = ["Todas"] + [c["nombre"] for c in self.db.get_categorias()]
        if hasattr(self, "cat_combo"):
            self.cat_combo["values"] = cats
        self._filtrar_menu()

    def _filtrar_menu(self):
        if not hasattr(self, "tree_menu"):
            return
        self.tree_menu.delete(*self.tree_menu.get_children())
        productos = self.db.get_productos()
        texto = self.search_var.get().lower() if hasattr(self, "search_var") else ""
        cat_sel = self.cat_var.get() if hasattr(self, "cat_var") else "Todas"

        nombres_en_grupo = _NOMBRES_EN_GRUPO
        grupos_insertados = set()
        prod_por_nombre = {p["nombre"].lower(): p for p in productos}

        for p in productos:
            # Skip products that are variants of a group
            if p["nombre"] in nombres_en_grupo:
                continue

            if texto and texto not in p["nombre"].lower():
                # Check whether it matches any group
                pass
            if cat_sel != "Todas" and p["categoria"] != cat_sel:
                continue
            if texto and texto not in p["nombre"].lower():
                continue

            self.tree_menu.insert("", "end", iid=str(p["id"]),
                                  values=(p["nombre"],
                                          f"${p['precio']:,.0f}",
                                          p["categoria"] or "—"))

        # Insert groups at the end of each matching category
        for nombre_grupo, variantes in GRUPOS_VARIANTES.items():
            if not variantes:
                continue
            variantes_validas = [
                (etq, nr) for etq, nr in variantes
                if prod_por_nombre.get(nr.lower())
            ]
            if not variantes_validas:
                continue

            precios = [prod_por_nombre[nr.lower()]["precio"] for _, nr in variantes_validas]
            prod_ref = prod_por_nombre[variantes_validas[0][1].lower()]

            if cat_sel != "Todas" and prod_ref["categoria"] != cat_sel:
                continue
            if texto and texto not in nombre_grupo.lower():
                continue

            precio_min, precio_max = min(precios), max(precios)
            precio_txt = f"desde ${precio_min:,.0f}" if precio_max > precio_min else f"${precio_min:,.0f}"

            self.tree_menu.insert("", "end",
                                  iid=f"grupo::{nombre_grupo}",
                                  values=(f"▼ {nombre_grupo}",
                                          precio_txt,
                                          prod_ref["categoria"] or "—"))

    def _agregar_desde_menu(self, event=None):
        self._agregar_desde_menu_btn()

    def _agregar_desde_menu_btn(self):
        if not self.pedido_actual_id:
            messagebox.showwarning("Sin pedido",
                                   "Selecciona o crea un pedido primero.")
            return
        sel = self.tree_menu.selection()
        if not sel:
            return
        iid = sel[0]

        # Is it a group?
        if iid.startswith("grupo::"):
            nombre_grupo = iid[len("grupo::"):]
            variantes = GRUPOS_VARIANTES.get(nombre_grupo, [])
            if not variantes:
                return
            productos = self.db.get_productos()
            prod_por_nombre = {p["nombre"]: p for p in productos}
            variantes_validas = [
                (etq, nr) for etq, nr in variantes if nr in prod_por_nombre
            ]
            if not variantes_validas:
                return
            precios = [prod_por_nombre[nr]["precio"] for _, nr in variantes_validas]
            precio_min, precio_max = min(precios), max(precios)

            cant = simpledialog.askinteger(
                "Cantidad",
                f"¿Cuántas unidades de '{nombre_grupo}'?",
                minvalue=1, maxvalue=99, initialvalue=1,
                parent=self.parent)
            if not cant:
                return

            nombre_real = self._pedir_variante(
                nombre_grupo, variantes_validas, precio_min, cant,
                precio_max=precio_max)
            if not nombre_real:
                return

            prod_real = prod_por_nombre.get(nombre_real)
            if not prod_real:
                return
            precio = prod_real["precio"]
            prod_id = prod_real["id"]

            comentario = self._pedir_comentario(nombre_real)

            self._agregar_producto(nombre_real, precio, cant, prod_id, comentario)
        else:
            pid_prod = int(iid)
            productos = self.db.get_productos()
            prod = next((p for p in productos if p["id"] == pid_prod), None)
            if not prod:
                return

            cant = simpledialog.askinteger(
                "Cantidad",
                f"¿Cuántas unidades de '{prod['nombre']}'?",
                minvalue=1, maxvalue=99, initialvalue=1,
                parent=self.parent)
            if not cant:
                return

            comentario = self._pedir_comentario(prod["nombre"])
            self._agregar_producto(prod["nombre"], prod["precio"], cant, prod["id"], comentario)

    def _agregar_producto(self, nombre, precio, cantidad, producto_id=None, comentario=""):

        ronda = getattr(self, "ronda_actual", None) or \
            self.db.get_ronda_actual(self.pedido_actual_id)
        self.db.add_linea(self.pedido_actual_id, nombre, precio,
                          cantidad, producto_id, notas=comentario, ronda=ronda)
        recalcular_bebidas_pedido(self.db.conn, self.db, self.pedido_actual_id)

        self._refresh_ticket()
        self.refresh_pedidos()

    def _agregar_comentario_linea(self):
        """Adds or edits the comment of a line selected in the ticket."""
        sel = self.tree_ticket.selection()
        if not sel:
            messagebox.showinfo("Sin selección", "Selecciona una línea del ticket primero.")
            return
        linea_id = int(sel[0])
        lineas = self.db.get_lineas(self.pedido_actual_id)
        linea = next((l for l in lineas if l["id"] == linea_id), None)
        if not linea:
            return

        comentario = self._pedir_comentario(linea["nombre_producto"])
        # Update the note directly in the DB
        self.db.conn.execute(
            "UPDATE lineas_pedido SET notas=? WHERE id=?",
            (comentario, linea_id)
        )
        self.db.conn.commit()
        self._refresh_ticket()

    def _editar_precio_linea(self):

        sel = self.tree_ticket.selection()
        if not sel:
            messagebox.showinfo("Sin selección", "Selecciona una línea del ticket primero.")
            return
        linea_id_str = sel[0]
        if not linea_id_str.isdigit():
            messagebox.showinfo("Selección inválida", "Selecciona la línea del producto, no una nota.")
            return
        linea_id = int(linea_id_str)
        lineas = self.db.get_lineas(self.pedido_actual_id)
        linea = next((l for l in lineas if l["id"] == linea_id), None)
        if not linea:
            return
        if linea["es_bebida_incluida"]:
            messagebox.showinfo("No editable", "Esta línea es una bebida incluida sin costo, no tiene precio para editar.")
            return

        precio_real = linea["precio_original"] if linea["precio_original"] is not None else linea["precio_unitario"]

        ventana = EditarPrecioVentana(self.parent, linea["nombre_producto"],
                                      precio_real, linea["precio_unitario"], linea["cantidad"])
        self.parent.wait_window(ventana.top)
        if ventana.resultado is None:
            return

        nuevo_precio, motivo = ventana.resultado
        self.db.editar_precio_linea(linea_id, self.pedido_actual_id, nuevo_precio, motivo=motivo)
        self._refresh_ticket()
        self.refresh_pedidos()

    def agregar_linea_externa(self, nombre_producto, precio, cantidad=1, producto_id=None):
        if not self.pedido_actual_id:
            messagebox.showwarning("Sin pedido",
                                   "Selecciona o crea un pedido primero en la pestaña Caja.")
            return False
        self._agregar_producto(nombre_producto, precio, cantidad, producto_id)
        return True

    def _quitar_linea(self):
        sel = self.tree_ticket.selection()
        if not sel:
            return
        linea_id = int(sel[0])
        self.db.delete_linea(linea_id, self.pedido_actual_id)
        recalcular_bebidas_pedido(self.db.conn, self.db, self.pedido_actual_id)
        self._refresh_ticket()
        self.refresh_pedidos()

    def _cobrar(self):
        if not self.pedido_actual_id:
            messagebox.showwarning("Sin pedido", "No hay pedido activo.")
            return
        lineas = self.db.get_lineas(self.pedido_actual_id)
        if not lineas:
            messagebox.showwarning("Pedido vacío", "El pedido está vacío.")
            return

        lineas_sel, es_parcial = self._obtener_lineas_seleccionadas(lineas)
        if es_parcial:
            self._cobrar_parcial(lineas_sel)
        else:
            self._cobrar_completo(lineas)

    def _obtener_lineas_seleccionadas(self, lineas):
        """
        Checks the current ticket selection (supports Ctrl+click / Shift+click
        thanks to selectmode='extended').
        """
        ids_validos = {l["id"] for l in lineas}
        ids_sel = {int(iid) for iid in self.tree_ticket.selection()
                   if iid.isdigit() and int(iid) in ids_validos}
        if not ids_sel or ids_sel == ids_validos:
            return lineas, False
        seleccionadas = [l for l in lineas if l["id"] in ids_sel]
        return seleccionadas, True

    def _cobrar_completo(self, lineas):
        pedido = self.db.get_pedido(self.pedido_actual_id)
        ventana = CobroVentana(self.parent, pedido["total"])
        self.parent.wait_window(ventana.top)
        if not ventana.resultado:
            return

        self.db.cerrar_pedido(self.pedido_actual_id, ventana.resultado)
        self.db.descontar_inventario_por_lineas(lineas)
        self._registrar_pago_auditoria(self.pedido_actual_id, lineas,
                                       pedido["total"], ventana.resultado, ventana.detalle)

        msg = (f"Pedido #{self.pedido_actual_id} cobrado por ${pedido['total']:,.0f}\n"
               f"Método: {ventana.resultado}")
        if ventana.detalle:
            msg += (f"\n  💵 Efectivo: ${ventana.detalle['efectivo']:,.0f}"
                    f"\n  📱 Transferencia: ${ventana.detalle['transferencia']:,.0f}")
        messagebox.showinfo("✅ Cobrado", msg)

        self.pedido_actual_id = None
        self.lbl_ticket_title.config(text="TICKET — sin pedido")
        self._refresh_ticket()
        self.refresh_pedidos()

    def _cobrar_parcial(self, lineas_sel):
        """
        Charges only the subset of lines selected in the ticket.
        The rest of the order stays open. If after charging these lines
        nothing is left pending, the order is closed automatically.
        """
        total_parcial = sum(l["subtotal"] for l in lineas_sel)
        n = len(lineas_sel)

        if not messagebox.askyesno(
            "Cobro parcial",
            f"Vas a cobrar {n} producto(s) seleccionados por ${total_parcial:,.0f}, "
            "dejando el resto del pedido abierto.\n\n¿Continuar?"
        ):
            return

        ventana = CobroVentana(self.parent, total_parcial,
                               titulo="Cobrar productos seleccionados")
        self.parent.wait_window(ventana.top)
        if not ventana.resultado:
            return

        self._registrar_pago_auditoria(self.pedido_actual_id, lineas_sel,
                                       total_parcial, ventana.resultado, ventana.detalle)
        self.db.descontar_inventario_por_lineas(lineas_sel)
        for l in lineas_sel:
            self.db.delete_linea(l["id"], self.pedido_actual_id)

        msg = f"Cobrados {n} producto(s) por ${total_parcial:,.0f}\nMétodo: {ventana.resultado}"
        if ventana.detalle:
            msg += (f"\n  💵 Efectivo: ${ventana.detalle['efectivo']:,.0f}"
                    f"\n  📱 Transferencia: ${ventana.detalle['transferencia']:,.0f}")

        restante = self.db.get_lineas(self.pedido_actual_id)
        if not restante:
            # Nothing left to charge: the order is closed
            self.db.cerrar_pedido(self.pedido_actual_id, ventana.resultado)
            messagebox.showinfo("✅ Cobrado", msg +
                                "\n\nEra lo último del pedido: el pedido queda cerrado.")
            self.pedido_actual_id = None
            self.lbl_ticket_title.config(text="TICKET — sin pedido")
        else:
            total_restante = sum(l["subtotal"] for l in restante)
            messagebox.showinfo("✅ Cobro parcial registrado", msg +
                                f"\n\nQuedan ${total_restante:,.0f} pendientes en el pedido.")

        self._refresh_ticket()
        self.refresh_pedidos()

    def _registrar_pago_auditoria(self, pedido_id, lineas, monto, metodo, detalle):
        """
        Leaves an audit record of each payment (full or partial),
        including the cash/transfer breakdown when it is a split
        bill.
        """
        productos_txt = ", ".join(
            f"{l['nombre_producto']} x{l['cantidad']}" for l in lineas)
        if detalle:
            efectivo = detalle.get("efectivo", 0)
            transferencia = detalle.get("transferencia", 0)
        elif metodo == "efectivo":
            efectivo, transferencia = monto, 0
        else:
            efectivo, transferencia = 0, monto
        try:
            self.db.registrar_pago(pedido_id, metodo, monto, efectivo, transferencia, productos_txt)
        except Exception as e:
            logger.warning(f"No se pudo registrar auditoría de pago: {e}")

    def _cancelar_pedido(self):
        if not self.pedido_actual_id:
            return
        pedido = self.db.get_pedido(self.pedido_actual_id)
        mesa = pedido["mesa"] if pedido else ""
        dlg = MotivoCancelacionVentana(self.parent, self.pedido_actual_id, mesa)
        self.parent.wait_window(dlg.top)
        if dlg.resultado is None:
            return  # they changed their mind / closed the window: nothing is cancelled
        self.db.cancelar_pedido(self.pedido_actual_id, motivo=dlg.resultado)
        self.pedido_actual_id = None
        self.lbl_ticket_title.config(text="TICKET — sin pedido")
        self._refresh_ticket()
        self.refresh_pedidos()

    def _enviar_comanda_cocina(self):
        """Sends the current order to the kitchen printer"""
        if not self.pedido_actual_id:
            messagebox.showwarning(
                "Sin pedido",
                "Selecciona o crea un pedido primero."
            )
            return
        
        # Get the current round if rounds exist
        ronda = getattr(self, 'ronda_actual', None)
        
        # Send to the print queue
        exito, mensaje = agregar_comanda_cocina(self.pedido_actual_id, ronda)
        
        if exito:
            messagebox.showinfo(
                "Éxito",
                f"Comanda enviada a cocina.\n{mensaje}"
            )
            # Log to file/database if you wish
            logger.info(f"Comanda {self.pedido_actual_id} enviada a cocina")
        else:
            messagebox.showerror(
                "Error",
                f"No se pudo enviar la comanda:\n{mensaje}"
            )