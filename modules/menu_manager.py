"""
Menu management module — products and categories
"""

import tkinter as tk
from tkinter import ttk, messagebox


class MenuManager:
    def __init__(self, parent, db, on_change_callback=None):
        self.parent = parent
        self.db = db
        self.on_change = on_change_callback
        self._build_ui()

    def _build_ui(self):
        self.parent.columnconfigure(0, weight=1)
        self.parent.columnconfigure(1, weight=1)
        self.parent.rowconfigure(0, weight=1)

        self._build_productos()
        self._build_form()
        self.refresh()

    # ── Product list ──────────────────────────────────────────
    def _build_productos(self):
        frame = tk.Frame(self.parent, bg="#16213e")
        frame.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)

        tk.Label(frame, text="PRODUCTOS DEL MENÚ",
                 font=("Segoe UI", 11, "bold"), bg="#16213e", fg="#e94560").pack(pady=(8, 4))

        filtro_frame = tk.Frame(frame, bg="#16213e")
        filtro_frame.pack(fill="x", padx=8, pady=(0, 6))
        tk.Label(filtro_frame, text="Categoría:", font=("Segoe UI", 9),
                 bg="#16213e", fg="#a0a8c0").pack(side="left", padx=(0, 6))
        self.var_filtro_cat = tk.StringVar(value="Todas")
        self.filtro_combo = ttk.Combobox(filtro_frame, textvariable=self.var_filtro_cat,
                                          state="readonly", width=22)
        self.filtro_combo.pack(side="left", fill="x", expand=True)
        self.filtro_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        tk.Button(filtro_frame, text="＋ / －", width=4,
                  bg="#34495e", fg="white", font=("Segoe UI", 8),
                  relief="flat", cursor="hand2",
                  command=self._alternar_todo).pack(side="right")

        list_frame = tk.Frame(frame, bg="#16213e")
        list_frame.pack(fill="both", expand=True, padx=8)

        cols = ("ID", "Nombre", "Precio", "Categoría", "Disponible")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="tree headings", height=22)
        self.tree.heading("#0", text="Categoría / Producto")
        self.tree.column("#0", width=170, anchor="w")
        for col in cols:
            self.tree.heading(col, text=col)
        self.tree.column("ID", width=35, anchor="center")
        self.tree.column("Nombre", width=0, stretch=False)  # the name already goes in the tree column (#0)
        self.tree.heading("Nombre", text="")
        self.tree.column("Precio", width=70, anchor="e")
        self.tree.column("Categoría", width=0, stretch=False)  # redundant: it already groups by category
        self.tree.heading("Categoría", text="")
        self.tree.column("Disponible", width=70, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._cargar_en_form)

        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

        btn_frame = tk.Frame(frame, bg="#16213e")
        btn_frame.pack(fill="x", padx=8, pady=6)
        tk.Button(btn_frame, text="🗑️ Eliminar",
                  bg="#c0392b", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2",
                  command=self._eliminar).pack(side="left")
        tk.Button(btn_frame, text="🔄 Actualizar lista",
                  bg="#34495e", fg="white", font=("Segoe UI", 9),
                  relief="flat", cursor="hand2",
                  command=self.refresh).pack(side="right")

    def _alternar_todo(self):
        """Expands all categories if any is collapsed; otherwise collapses them all."""
        hijos = self.tree.get_children("")
        hay_colapsada = any(not self.tree.item(h, "open") for h in hijos)
        for h in hijos:
            self.tree.item(h, open=hay_colapsada)


    # ── Form ──────────────────────────────────────────────────
    def _build_form(self):
        frame = tk.Frame(self.parent, bg="#0f3460")
        frame.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)

        tk.Label(frame, text="EDITAR / NUEVO PRODUCTO",
                 font=("Segoe UI", 11, "bold"), bg="#0f3460", fg="#e94560").pack(pady=(12, 8))

        form = tk.Frame(frame, bg="#0f3460")
        form.pack(fill="x", padx=16)

        self.form_id = None

        def row(label, var_or_widget, is_widget=False):
            tk.Label(form, text=label, font=("Segoe UI", 9),
                     bg="#0f3460", fg="#a0a8c0", anchor="w").pack(fill="x", pady=(8, 0))
            if is_widget:
                var_or_widget.pack(fill="x", pady=(2, 0))
            else:
                tk.Entry(form, textvariable=var_or_widget,
                         bg="#16213e", fg="white", insertbackground="white",
                         relief="flat", font=("Segoe UI", 10)).pack(fill="x", pady=(2, 0))

        self.var_nombre = tk.StringVar()
        self.var_precio = tk.StringVar()
        self.var_desc = tk.StringVar()
        self.var_comentarios = tk.StringVar() # <-- NEW VARIABLE
        self.var_disp = tk.BooleanVar(value=True)

        row("Nombre del producto", self.var_nombre)
        row("Precio ($)", self.var_precio)
        row("Descripción (opcional)", self.var_desc)
        
        # NEW FIELD FOR QUICK COMMENTS
        row("Comentarios rápidos (separados por coma)", self.var_comentarios)

        tk.Label(form, text="Categoría", font=("Segoe UI", 9),
                 bg="#0f3460", fg="#a0a8c0", anchor="w").pack(fill="x", pady=(8, 0))
        self.cat_var = tk.StringVar()
        self.cat_combo = ttk.Combobox(form, textvariable=self.cat_var, state="readonly")
        self.cat_combo.pack(fill="x", pady=(2, 0))

        tk.Label(form, text="Categoría nueva (si no existe)",
                 font=("Segoe UI", 9), bg="#0f3460", fg="#a0a8c0", anchor="w").pack(fill="x", pady=(8, 0))
        self.var_cat_nueva = tk.StringVar()
        tk.Entry(form, textvariable=self.var_cat_nueva,
                 bg="#16213e", fg="white", insertbackground="white",
                 relief="flat", font=("Segoe UI", 10)).pack(fill="x")

        tk.Checkbutton(form, text="Disponible", variable=self.var_disp,
                       bg="#0f3460", fg="white", selectcolor="#16213e",
                       activebackground="#0f3460", font=("Segoe UI", 9)).pack(anchor="w", pady=8)

        # Buttons
        tk.Button(frame, text="💾 Guardar",
                  bg="#27ae60", fg="white", font=("Segoe UI", 11, "bold"),
                  relief="flat", cursor="hand2", pady=8,
                  command=self._guardar).pack(fill="x", padx=16, pady=4)
        tk.Button(frame, text="🆕 Limpiar / Nuevo",
                  bg="#34495e", fg="white", font=("Segoe UI", 9),
                  relief="flat", cursor="hand2",
                  command=self._limpiar).pack(fill="x", padx=16, pady=2)

        self._actualizar_categorias()

    def _actualizar_categorias(self):
        cats = [c["nombre"] for c in self.db.get_categorias()]
        self.cat_combo["values"] = cats
        if cats:
            self.cat_combo.current(0)

        valores_filtro = ["Todas"] + cats
        actual = self.var_filtro_cat.get()
        self.filtro_combo["values"] = valores_filtro
        if actual not in valores_filtro:
            self.var_filtro_cat.set("Todas")

    def _cargar_en_form(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        item = self.tree.item(sel[0])
        if "producto" not in self.tree.item(sel[0], "tags"):
            return  # a category (grouping row) was selected, not a product
        pid = int(item["values"][0])
        productos = self.db.get_productos(solo_disponibles=False)
        prod = next((p for p in productos if p["id"] == pid), None)
        if not prod:
            return
        self.form_id = pid
        self.var_nombre.set(prod["nombre"])
        self.var_precio.set(str(prod["precio"]))
        self.var_desc.set(prod["descripcion"] or "")
        
        # LOAD COMMENTS INTO THE ENTRY
        comentarios_lista = prod.get("comentarios", [])
        if isinstance(comentarios_lista, list):
            self.var_comentarios.set(", ".join(comentarios_lista))
        else:
            self.var_comentarios.set("")

        self.var_disp.set(bool(prod["disponible"]))
        if prod["categoria"]:
            self.cat_var.set(prod["categoria"])
        self.var_cat_nueva.set("")

    def _guardar(self):
        nombre = self.var_nombre.get().strip()
        precio_str = self.var_precio.get().strip().replace(",", ".")
        if not nombre or not precio_str:
            messagebox.showwarning("Campos requeridos", "Nombre y precio son obligatorios.")
            return
        try:
            precio = float(precio_str)
        except ValueError:
            messagebox.showerror("Error", "El precio debe ser un número.")
            return

        # Handle category (the name is saved directly in the menu JSON;
        # if it is new, MenuStore adds it automatically to the category list)
        cat_nueva = self.var_cat_nueva.get().strip()
        cat_nombre = cat_nueva if cat_nueva else self.cat_var.get()

        # Convert text "Sin cebolla, Bien cocido, Con hielo" -> ["Sin cebolla", "Bien cocido", "Con hielo"]
        raw_comentarios = self.var_comentarios.get().split(",")
        lista_comentarios = [c.strip() for c in raw_comentarios if c.strip()]

        if self.form_id:
            self.db.update_producto(
                self.form_id, nombre, precio, cat_nombre,
                1 if self.var_disp.get() else 0,
                self.var_desc.get().strip(),
                comentarios=lista_comentarios # <-- Pass list when saving
            )
            messagebox.showinfo("✅ Guardado", f"Producto '{nombre}' actualizado.")
        else:
            self.db.add_producto(
                nombre, precio, cat_nombre, 
                self.var_desc.get().strip(),
                comentarios=lista_comentarios # <-- Pass list when creating
            )
            messagebox.showinfo("✅ Guardado", f"Producto '{nombre}' añadido al menú.")

        self._limpiar()
        self.refresh()
        if self.on_change:
            self.on_change()

    def _eliminar(self):
        sel = self.tree.selection()
        if not sel:
            return
        if "producto" not in self.tree.item(sel[0], "tags"):
            messagebox.showinfo("Selecciona un producto",
                                 "Esa fila es una categoría, no un producto. Despliégala y selecciona el producto que quieres eliminar.")
            return
        pid = int(self.tree.item(sel[0])["values"][0])
        nombre = self.tree.item(sel[0])["values"][1]
        if messagebox.askyesno("Eliminar", f"¿Eliminar '{nombre}'? Esta acción no se puede deshacer."):
            self.db.delete_producto(pid)
            self._limpiar()
            self.refresh()
            if self.on_change:
                self.on_change()

    def _limpiar(self):
        self.form_id = None
        self.var_nombre.set("")
        self.var_precio.set("")
        self.var_desc.set("")
        self.var_comentarios.set("")
        self.var_disp.set(True)
        self.var_cat_nueva.set("")

    def refresh(self):
        self.tree.delete(*self.tree.get_children())

        productos = self.db.get_productos(solo_disponibles=False)
        filtro = self.var_filtro_cat.get() if hasattr(self, "var_filtro_cat") else "Todas"

        grupos = {}
        for p in productos:
            cat = p["categoria"] or "Sin categoría"
            grupos.setdefault(cat, []).append(p)

        # Categories sorted alphabetically; "Sin categoría" always last
        nombres_cat = sorted(grupos.keys(), key=lambda c: (c == "Sin categoría", c.lower()))

        for cat in nombres_cat:
            if filtro != "Todas" and cat != filtro:
                continue
            productos_cat = sorted(grupos[cat], key=lambda p: p["nombre"].lower())
            cat_iid = f"cat::{cat}"
            self.tree.insert(
                "", "end", iid=cat_iid, text=f"📁 {cat} ({len(productos_cat)})",
                values=("", "", "", "", ""), tags=("categoria",), open=True
            )
            for p in productos_cat:
                disp = "✅" if p["disponible"] else "❌"
                self.tree.insert(
                    cat_iid, "end", iid=f"prod::{p['id']}",
                    text=f"   {p['nombre']}",
                    values=(p["id"], p["nombre"], f"${p['precio']:,.0f}", cat, disp),
                    tags=("producto",)
                )

        self._actualizar_categorias()