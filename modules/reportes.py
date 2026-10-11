"""
Updated reports and cash close module
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import os
import re
from tkinter import simpledialog
from dotenv import load_dotenv

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    _OPENPYXL_OK = True
except ImportError:
    _OPENPYXL_OK = False

from modules.cierres_excel import ruta_excel_dia, carpeta_cierres_excel
load_dotenv()


def _parsear_monto(texto):
    texto = (texto or "").strip().replace("$", "").replace(" ", "")
    if not texto:
        return 0.0

    tiene_punto = "." in texto
    tiene_coma = "," in texto

    if tiene_punto and tiene_coma:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif tiene_coma:
        partes = texto.split(",")
        if len(partes) > 1 and len(partes[-1]) == 3:
            texto = texto.replace(",", "")
        else:
            texto = texto.replace(",", ".")
    elif tiene_punto:
        partes = texto.split(".")
        if len(partes) > 1 and len(partes[-1]) == 3:
            texto = texto.replace(".", "")

    return float(texto)


class ReportesModule:
    def __init__(self, parent, db):
        self.parent_original = parent
        self.db = db
        self._build_scroll_container()
        self._build_ui()

    def _build_scroll_container(self):
        contenedor = tk.Frame(self.parent_original, bg="#1a1a2e")
        contenedor.pack(fill="both", expand=True)
        contenedor.rowconfigure(0, weight=1)
        contenedor.columnconfigure(0, weight=1)

        canvas = tk.Canvas(contenedor, bg="#1a1a2e", highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(contenedor, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        self.parent = tk.Frame(canvas, bg="#1a1a2e")
        ventana_id = canvas.create_window((0, 0), window=self.parent, anchor="nw")

        def _actualizar_scrollregion(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        self.parent.bind("<Configure>", _actualizar_scrollregion)

        def _ajustar_ancho(event):
            canvas.itemconfig(ventana_id, width=event.width)
        canvas.bind("<Configure>", _ajustar_ancho)

        def _rueda_mouse(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _rueda_mouse))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

    def _build_ui(self):
        self.parent.columnconfigure(0, weight=1)
        self.parent.columnconfigure(1, weight=1)
        self.parent.rowconfigure(1, weight=1)
        self.parent.rowconfigure(2, weight=1)

        self._build_resumen()
        self._build_ventas_hoy()
        self._build_mas_vendidos()
        self._build_historial_precios()

    def _build_resumen(self):
        frame = tk.Frame(self.parent, bg="#16213e")
        frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))

        tk.Label(frame, text="RESUMEN DEL DÍA",
                 font=("Segoe UI", 11, "bold"), bg="#16213e", fg="#e94560").pack(side="left", padx=12, pady=8)

        self.lbl_hoy_pedidos = tk.Label(frame, text="Pedidos: —",
                                         font=("Segoe UI", 10), bg="#16213e", fg="#a0a8c0")
        self.lbl_hoy_pedidos.pack(side="left", padx=20)

        self.lbl_hoy_total = tk.Label(frame, text="Total Comandas: —",
                                       font=("Segoe UI", 14, "bold"), bg="#16213e", fg="#27ae60")
        self.lbl_hoy_total.pack(side="left", padx=10)

        tk.Button(frame, text="📜 Historial de Cierre de Caja",
                  bg="#8e44ad", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2",
                  command=self._abrir_carpeta_cierres).pack(side="right", padx=6)

        tk.Button(frame, text="🔄 Actualizar",
                  bg="#34495e", fg="white", font=("Segoe UI", 9),
                  relief="flat", cursor="hand2",
                  command=self.refresh_todo).pack(side="right", padx=12)

        self.parent.after(100, self.refresh_todo)

    def _build_ventas_hoy(self):
        frame = tk.Frame(self.parent, bg="#0f3460")
        frame.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=4)

        tk.Label(frame, text="PEDIDOS DE HOY",
                 font=("Segoe UI", 10, "bold"), bg="#0f3460", fg="#e94560").pack(pady=(8, 4))

        list_frame = tk.Frame(frame, bg="#0f3460")
        list_frame.pack(fill="both", expand=True, padx=8)

        cols = ("ID", "Mesa", "Estado", "Total", "Pago", "Hora")
        self.tree_hoy = ttk.Treeview(list_frame, columns=cols, show="headings", height=12)
        for col in cols:
            self.tree_hoy.heading(col, text=col)
        self.tree_hoy.column("ID", width=35, anchor="center")
        self.tree_hoy.column("Mesa", width=70)
        self.tree_hoy.column("Estado", width=80, anchor="center")
        self.tree_hoy.column("Total", width=80, anchor="e")
        self.tree_hoy.column("Pago", width=90, anchor="center")
        self.tree_hoy.column("Hora", width=55, anchor="center")
        self.tree_hoy.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree_hoy.yview)
        sb.pack(side="right", fill="y")
        self.tree_hoy.configure(yscrollcommand=sb.set)

    def _build_mas_vendidos(self):
        frame = tk.Frame(self.parent, bg="#16213e")
        frame.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=4)

        tk.Label(frame, text="MÁS VENDIDOS (histórico)",
                 font=("Segoe UI", 10, "bold"), bg="#16213e", fg="#e94560").pack(pady=(8, 4))

        list_frame = tk.Frame(frame, bg="#16213e")
        list_frame.pack(fill="both", expand=True, padx=8)

        cols = ("Producto", "Unidades", "Total $")
        self.tree_vendidos = ttk.Treeview(list_frame, columns=cols, show="headings", height=8)
        for col in cols:
            self.tree_vendidos.heading(col, text=col)
        self.tree_vendidos.column("Producto", width=180)
        self.tree_vendidos.column("Unidades", width=70, anchor="center")
        self.tree_vendidos.column("Total $", width=90, anchor="e")
        self.tree_vendidos.pack(side="left", fill="both", expand=True)

        sb2 = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree_vendidos.yview)
        sb2.pack(side="right", fill="y")
        self.tree_vendidos.configure(yscrollcommand=sb2.set)

        # Expenses and Cash Close module incorporated here
        self._build_gastos_section(frame)
        self._build_cierre_inline(frame)

    def _build_gastos_section(self, parent_frame):
        frame = tk.Frame(parent_frame, bg="#0f3460")
        frame.pack(fill="x", padx=8, pady=(8, 4))

        tk.Label(frame, text="REGISTRO DE GASTOS DEL DÍA",
                 font=("Segoe UI", 10, "bold"), bg="#0f3460", fg="#f39c12").pack(pady=(6, 4))

        form = tk.Frame(frame, bg="#0f3460")
        form.pack(fill="x", padx=8, pady=2)

        tk.Label(form, text="Motivo:", bg="#0f3460", fg="white", font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.var_gasto_motivo = tk.StringVar()
        tk.Entry(form, textvariable=self.var_gasto_motivo, width=15, bg="#16213e", fg="white", insertbackground="white").pack(side="left", padx=(0, 8))

        tk.Label(form, text="Valor ($):", bg="#0f3460", fg="white", font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.var_gasto_valor = tk.StringVar(value="0")
        tk.Entry(form, textvariable=self.var_gasto_valor, width=10, bg="#16213e", fg="white", insertbackground="white").pack(side="left", padx=(0, 8))

        tk.Button(form, text="➕ Agregar Gasto", bg="#e67e22", fg="white", font=("Segoe UI", 8, "bold"),
                  relief="flat", cursor="hand2", command=self._agregar_gasto).pack(side="left")

        # Quick table of the day's expenses
        self.tree_gastos = ttk.Treeview(frame, columns=("Motivo", "Valor"), show="headings", height=3)
        self.tree_gastos.heading("Motivo", text="Motivo")
        self.tree_gastos.heading("Valor", text="Valor")
        self.tree_gastos.column("Motivo", width=180)
        self.tree_gastos.column("Valor", width=80, anchor="e")
        self.tree_gastos.pack(fill="x", padx=8, pady=4)
        self.tree_gastos.bind("<Double-1>", self._eliminar_gasto_seleccionado)

    def _build_cierre_inline(self, parent_frame):
        frame = tk.Frame(parent_frame, bg="#0f3460")
        frame.pack(fill="x", padx=8, pady=8)

        tk.Label(frame, text="CIERRE DE CAJA",
                 font=("Segoe UI", 10, "bold"), bg="#0f3460", fg="#e94560").pack(pady=(8, 4))

        tk.Button(frame, text="📊 Cargar datos automáticos del día",
                  bg="#0f3460", fg="#a0a8c0", font=("Segoe UI", 8),
                  relief="flat", cursor="hand2",
                  command=self._cargar_totales_dia).pack(pady=(0, 6))

        form = tk.Frame(frame, bg="#0f3460")
        form.pack(fill="x", padx=12)

        def campo(label, var):
            f = tk.Frame(form, bg="#0f3460")
            f.pack(fill="x", pady=2)
            tk.Label(f, text=label, font=("Segoe UI", 9),
                     bg="#0f3460", fg="#a0a8c0", width=22, anchor="w").pack(side="left")
            tk.Entry(f, textvariable=var, width=12,
                     bg="#16213e", fg="white", insertbackground="white",
                     relief="flat").pack(side="left")

        self.var_ef = tk.StringVar(value="0")
        self.var_trans = tk.StringVar(value="0")
        self.var_gastos_cierre = tk.StringVar(value="0")

        campo("1. Efectivo ($):", self.var_ef)
        campo("2. Transferencias ($):", self.var_trans)
        campo("3. Gastos del día ($):", self.var_gastos_cierre)

        tk.Button(frame, text="🔒 Realizar Cierre de Caja",
                  bg="#e94560", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", cursor="hand2", pady=6,
                  command=self._cerrar_caja).pack(fill="x", padx=12, pady=8)

        tk.Button(frame, text="📂 Abrir Excel del día",
                  bg="#0f3460", fg="#27ae60", font=("Segoe UI", 8, "bold"),
                  relief="flat", cursor="hand2",
                  command=self._abrir_excel_dia).pack(fill="x", padx=12, pady=(0, 8))

    def _build_historial_precios(self):
        frame = tk.Frame(self.parent, bg="#16213e")
        frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=8, pady=(4, 8))

        tk.Label(frame, text="🔒 HISTORIAL DE PRECIOS EDITADOS (auditoría)",
                 font=("Segoe UI", 10, "bold"), bg="#16213e", fg="#e67e22").pack(pady=(8, 4))

        list_frame = tk.Frame(frame, bg="#16213e")
        list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        cols = ("Fecha", "Pedido", "Producto", "Cant.", "Precio real", "Precio cobrado", "Diferencia", "Motivo")
        self.tree_historial = ttk.Treeview(list_frame, columns=cols, show="headings", height=6)
        for col in cols:
            self.tree_historial.heading(col, text=col)
        self.tree_historial.column("Fecha", width=130, anchor="center")
        self.tree_historial.column("Pedido", width=55, anchor="center")
        self.tree_historial.column("Producto", width=200)
        self.tree_historial.column("Cant.", width=45, anchor="center")
        self.tree_historial.column("Precio real", width=90, anchor="e")
        self.tree_historial.column("Precio cobrado", width=100, anchor="e")
        self.tree_historial.column("Diferencia", width=90, anchor="e")
        self.tree_historial.column("Motivo", width=180)
        self.tree_historial.pack(side="left", fill="both", expand=True)

        sb3 = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree_historial.yview)
        sb3.pack(side="right", fill="y")
        self.tree_historial.configure(yscrollcommand=sb3.set)

    def _agregar_gasto(self):
        motivo = self.var_gasto_motivo.get().strip()
        try:
            valor = _parsear_monto(self.var_gasto_valor.get())
        except ValueError:
            messagebox.showerror("Error", "El valor del gasto debe ser numérico.")
            return

        if not motivo or valor <= 0:
            messagebox.showwarning("Atención", "Escriba un motivo y un valor válido para el gasto.")
            return

        self.db.add_gasto(motivo, valor)
        self.var_gasto_motivo.set("")
        self.var_gasto_valor.set("0")
        self._refresh_gastos()
        self._cargar_totales_dia()

    def _refresh_gastos(self):
        self.tree_gastos.delete(*self.tree_gastos.get_children())
        gastos = self.db.get_gastos_hoy()
        total_gastos = 0.0
        for g in gastos:
            self.tree_gastos.insert("", "end", iid=str(g["id"]),
                                    values=(g["motivo"], f"${g['valor']:,.0f}"))
            total_gastos += g["valor"]
        self.var_gastos_cierre.set(str(int(total_gastos)))

    def _eliminar_gasto_seleccionado(self, event=None):
        sel = self.tree_gastos.selection()
        if not sel:
            return
        gasto_id = int(sel[0]) 

        if not messagebox.askyesno("Autorización Requerida", "⚠️ ¿Desea eliminar este gasto?\n\nEsta acción requiere autorización del administrador."):
            return
        
        CLAVE_CORRECTA = os.environ.get("SUPERVISOR_PASSWORD")
        
        clave_ingresada = simpledialog.askstring(
            "Seguridad de Caja", 
            "Ingrese la contraseña de supervisor para autorizar:", 
            show="*"
        )

        if not clave_ingresada:
            return 
            
        if clave_ingresada != CLAVE_CORRECTA:
            messagebox.showerror("Acceso Denegado", "❌ Contraseña INCORRECTA.\nNo tiene permisos para eliminar gastos. El intento ha sido bloqueado.")
            return

        if messagebox.askyesno("Confirmar", "¿Eliminar este gasto de forma definitiva?"):
            self.db.delete_gasto(gasto_id)
            messagebox.showinfo("Éxito", "✅ Gasto eliminado correctamente por el supervisor.")
            self._cargar_totales_dia()

    def _cargar_totales_dia(self):
        
        totales = self.db.get_totales_pagos_hoy()
        ef_bruto = totales["efectivo"]
        trans = totales["transferencia"]

        self._refresh_gastos()  # updates self.var_gastos_cierre with today's total
        total_gastos = _parsear_monto(self.var_gastos_cierre.get())

        ef_neto = ef_bruto - total_gastos
        self.var_ef.set(str(int(ef_neto)))
        self.var_trans.set(str(int(trans)))

    def refresh_todo(self):
        self._refresh_resumen()
        self._refresh_hoy()
        self._refresh_vendidos()
        self._refresh_gastos()
        self._refresh_historial_precios()

    def _refresh_resumen(self):
        pedidos = self.db.get_pedidos_hoy()
        cerrados = [p for p in pedidos if p["estado"] == "cerrado"]
        total = sum(p["total"] for p in cerrados)
        self.lbl_hoy_pedidos.config(
            text=f"Pedidos hoy: {len(pedidos)} (cerrados: {len(cerrados)})")
        self.lbl_hoy_total.config(text=f"Total comandas: ${total:,.0f}")

    def _refresh_hoy(self):
        self.tree_hoy.delete(*self.tree_hoy.get_children())
        pedidos_editados = {h["pedido_id"] for h in self.db.get_historial_precios()}
        for p in self.db.get_pedidos_hoy():
            hora = p["fecha_apertura"][11:16]
            estado_emoji = {"abierto": "🟡 abierto",
                            "cerrado": "✅ cerrado",
                            "cancelado": "❌ cancelado"}.get(p["estado"], p["estado"])
            if p["id"] in pedidos_editados:
                estado_emoji += "  ✏️"
            self.tree_hoy.insert("", "end",
                                  values=(p["id"], p["mesa"], estado_emoji,
                                          f"${p['total']:,.0f}", p["metodo_pago"] or "—", hora))

    def _refresh_vendidos(self):
        self.tree_vendidos.delete(*self.tree_vendidos.get_children())
        for row in self.db.get_productos_mas_vendidos():
            self.tree_vendidos.insert("", "end",
                                       values=(row["nombre_producto"],
                                               row["total_uds"],
                                               f"${row['total_euros']:,.0f}"))

    def _refresh_historial_precios(self):
        self.tree_historial.delete(*self.tree_historial.get_children())
        for h in self.db.get_historial_precios():
            fecha = h["fecha"].replace("T", " ")[:16]
            diferencia = (h["precio_nuevo"] - h["precio_original"]) * h["cantidad"]
            self.tree_historial.insert("", "end", values=(
                fecha, h["pedido_id"], h["nombre_producto"], h["cantidad"],
                f"${h['precio_original']:,.0f}", f"${h['precio_nuevo']:,.0f}",
                f"${diferencia:,.0f}", h["motivo"] or "—"
            ))

    def _cerrar_caja(self):
        try:
            ef = _parsear_monto(self.var_ef.get())
            trans = _parsear_monto(self.var_trans.get())
            gastos = _parsear_monto(self.var_gastos_cierre.get())
        except ValueError:
            messagebox.showerror("Error", "Los montos deben ser valores numéricos válidos.")
            return

        # Total actually charged today according to the payment audit (includes
        # partial charges and split bills), to compare against what was
        # declared by the cashier.
        total_comandas = self.db.get_totales_pagos_hoy()["total"]

        total_declarado = ef + trans + gastos
        diferencia = total_declarado - total_comandas

        msg_cuadre = "✅ La caja cuadra perfectamente con las comandas." if diferencia == 0 else \
                     f"⚠️ Hay una diferencia de ${diferencia:,.0f} con respecto a las comandas."

        confirm = messagebox.askyesno(
            "Confirmar Cierre de Caja",
            f"¿Desea registrar el Cierre de Caja?\n\n"
            f"  1. Efectivo (neto):  ${ef:,.0f}\n"
            f"  2. Transferencias:   ${trans:,.0f}\n"
            f"  3. Gastos del día:   ${gastos:,.0f}\n"
            f"─────────────────────────────\n"
            f"  TOTAL DECLARADO:     ${total_declarado:,.0f}\n"
            f"  TOTAL COMANDAS:      ${total_comandas:,.0f}\n\n"
            f"{msg_cuadre}"
        )

        if confirm:
            self.db.add_cierre_caja(ef, trans, gastos, total_comandas)

            mensaje = ("Cierre registrado correctamente en la base de datos "
                       f"y disponible en el Dashboard.\nTotal: ${total_declarado:,.0f}")

            if _OPENPYXL_OK:
                try:
                    cierre_row = self.db.get_cierres_caja()[-1]
                    ruta_excel = self._generar_excel_dia(cierre_row)
                    mensaje += f"\n\n📁 Excel del día guardado automáticamente en:\n{ruta_excel}"
                except Exception as e:
                    mensaje += f"\n\n⚠️ No se pudo generar el Excel automático del día ({e})."
            else:
                mensaje += ("\n\n⚠️ No se generó el Excel automático porque falta la librería "
                            "'openpyxl' (pip install openpyxl).")

            messagebox.showinfo("✅ Cierre de Caja Exitoso", mensaje)
            self.refresh_todo()

    def _abrir_excel_dia(self):
        """Opens (or reveals, depending on the system) today's Excel."""
        ruta = ruta_excel_dia()
        if not os.path.exists(ruta):
            messagebox.showinfo(
                "Aún no hay Excel de hoy",
                "El Excel del día se genera automáticamente al hacer el "
                "'Cierre de Caja'. Todavía no se ha hecho el cierre de hoy."
            )
            return
        try:
            if os.name == "nt":
                os.startfile(ruta)
            else:
                import subprocess
                subprocess.Popen(["xdg-open", ruta])
        except Exception as e:
            messagebox.showerror("No se pudo abrir el archivo", str(e))

    # ── Automatic, detailed Excel of the day (one per close) ──────
    def _generar_excel_dia(self, cierre_row):
        """
        Generates (or replaces) the detailed Excel of the current day, with:
          1. Cash close summary
          2. Orders of the day: each complete ticket, one below the other,
             with its order number, table, waitress/origin, each product
             with its message/note, price and the round it was ordered in
          3. Orders and lines (flat table, one row per product)
          4. Cancellations of the day, with their reason (or pending) and which
             products the cancelled ticket had
          5. Expenses of the day
          6. Prices manually edited during the day (audit)

        It is always saved in the same folder and with the same name per
        date (`Cierre_AAAA-MM-DD.xlsx`), so if the register is closed more
        than once on the same day, the file is updated with the latest data.
        """
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        ruta = ruta_excel_dia(fecha_hoy)

        titulo_font = Font(bold=True, size=14, color="FFFFFF")
        titulo_fill = PatternFill("solid", fgColor="E94560")
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="0F3460")
        total_font = Font(bold=True)
        total_fill = PatternFill("solid", fgColor="D6EAF8")
        pendiente_font = Font(bold=True, color="C0392B")
        borde = Border(*(Side(style="thin", color="B0B0B0"),) * 4)
        moneda = '"$"#,##0'

        def _titulo(ws, texto, span, fila=1):
            ws.merge_cells(f"A{fila}:{get_column_letter(span)}{fila}")
            c = ws.cell(row=fila, column=1, value=texto)
            c.font = titulo_font
            c.fill = titulo_fill
            c.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[fila].height = 24
            return fila + 1

        def _encabezados(ws, headers, fila):
            for col, h in enumerate(headers, start=1):
                c = ws.cell(row=fila, column=col, value=h)
                c.font = header_font
                c.fill = header_fill
                c.border = borde
                c.alignment = Alignment(horizontal="center", vertical="center")
            return fila + 1

        wb = openpyxl.Workbook()

        # ── Sheet 1: Close summary ──
        ws1 = wb.active
        ws1.title = "Resumen del cierre"
        fila = _titulo(ws1, f"CIERRE DE CAJA — {fecha_hoy}", 2)
        ws1.cell(row=fila, column=1, value=f"Generado el {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        ws1.cell(row=fila, column=1).font = Font(italic=True, color="666666")
        fila += 2

        estado = "✅ Cuadra" if abs(cierre_row["diferencia"]) < 1 else "⚠️ Descuadre"
        filas_resumen = [
            ("Efectivo neto", cierre_row["total_efectivo"]),
            ("Transferencias", cierre_row["total_transferencias"]),
            ("Gastos del día", cierre_row["total_gastos"]),
            ("Total cuadrado (declarado)", cierre_row["total_cuadrado"]),
            ("Total comandas (auditoría de pagos)", cierre_row["total_comandas"]),
            ("Diferencia", cierre_row["diferencia"]),
        ]
        for etiqueta, valor in filas_resumen:
            ws1.cell(row=fila, column=1, value=etiqueta).font = Font(bold=True)
            c = ws1.cell(row=fila, column=2, value=valor)
            c.number_format = moneda
            c.alignment = Alignment(horizontal="right")
            fila += 1
        ws1.cell(row=fila, column=1, value="Estado").font = Font(bold=True)
        ws1.cell(row=fila, column=2, value=estado)
        fila += 3

        # Breakdown of expenses, right here in the close summary (not just
        # the total): this way "expense for X and for Y" is clear at a glance,
        # without having to go to the separate Expenses sheet.
        gastos_hoy = self.db.get_gastos_hoy()
        if gastos_hoy:
            ws1.cell(row=fila, column=1, value="Desglose de gastos del día").font = Font(bold=True, italic=True)
            fila += 1
            for g in gastos_hoy:
                ws1.cell(row=fila, column=1, value=f"• {g['motivo']}")
                cv = ws1.cell(row=fila, column=2, value=g["valor"])
                cv.number_format = moneda
                cv.alignment = Alignment(horizontal="right")
                fila += 1

        ws1.column_dimensions["A"].width = 34
        ws1.column_dimensions["B"].width = 18

        # ── Sheet 2: Orders of the day (each complete ticket, one below the other) ──
        ws_tickets = wb.create_sheet("Comandas del día")
        estado_color = {"cerrado": "27AE60", "cancelado": "C0392B", "abierto": "F1C40F"}
        estado_texto = {"cerrado": "✅ CERRADO", "cancelado": "❌ CANCELADO", "abierto": "🟡 ABIERTO"}

        def _mesera_de(pedido):
            notas = pedido["notas"] or ""
            m = re.search(r"mesera:\s*(.+)$", notas, re.IGNORECASE)
            return m.group(1).strip() if m else "Caja central"

        fila_t = _titulo(ws_tickets, f"COMANDAS DEL DÍA — {fecha_hoy}", 6)
        fila_t += 1

        pedidos_para_tickets = self.db.get_pedidos_hoy()
        if not pedidos_para_tickets:
            ws_tickets.cell(row=fila_t, column=1, value="Sin pedidos hoy").font = Font(italic=True, color="666666")

        for p in pedidos_para_tickets:
            color = estado_color.get(p["estado"], "7F8C8D")
            ws_tickets.merge_cells(f"A{fila_t}:F{fila_t}")
            c = ws_tickets.cell(
                row=fila_t, column=1,
                value=f"🧾 PEDIDO #{p['id']}   ·   {p['mesa']}   ·   {estado_texto.get(p['estado'], p['estado'])}"
            )
            c.font = Font(bold=True, size=12, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor=color)
            c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
            ws_tickets.row_dimensions[fila_t].height = 20
            fila_t += 1

            apertura = (p["fecha_apertura"] or "").replace("T", " ")[:16]
            cierre = (p["fecha_cierre"] or "").replace("T", " ")[:16] or "—"
            info = (f"Apertura: {apertura}    Cierre: {cierre}    "
                    f"Mesera/origen: {_mesera_de(p)}    Pago: {p['metodo_pago'] or '—'}")
            ws_tickets.merge_cells(f"A{fila_t}:F{fila_t}")
            ic = ws_tickets.cell(row=fila_t, column=1, value=info)
            ic.font = Font(italic=True, size=9, color="555555")
            fila_t += 1

            fila_t = _encabezados(
                ws_tickets, ["Producto", "Cant.", "Precio unit.", "Subtotal", "Mensaje / Nota", "Ronda"], fila_t)

            lineas_p = self.db.get_lineas(p["id"])
            if not lineas_p:
                ws_tickets.cell(row=fila_t, column=1, value="(ticket sin productos)").border = borde
                for col in range(2, 7):
                    ws_tickets.cell(row=fila_t, column=col).border = borde
                fila_t += 1
            for l in lineas_p:
                valores = [l["nombre_producto"], l["cantidad"], l["precio_unitario"],
                           l["subtotal"], l["notas"] or "—", l["ronda"] or 1]
                for col, v in enumerate(valores, start=1):
                    cell = ws_tickets.cell(row=fila_t, column=col, value=v)
                    cell.border = borde
                    if col in (3, 4):
                        cell.number_format = moneda
                        cell.alignment = Alignment(horizontal="right")
                    if col == 2:
                        cell.alignment = Alignment(horizontal="center")
                    if col == 6:
                        cell.alignment = Alignment(horizontal="center")
                fila_t += 1

            ws_tickets.cell(row=fila_t, column=1, value="TOTAL DEL TICKET").font = total_font
            ws_tickets.cell(row=fila_t, column=1).fill = total_fill
            for col in range(1, 4):
                ws_tickets.cell(row=fila_t, column=col).fill = total_fill
                ws_tickets.cell(row=fila_t, column=col).border = borde
            ct = ws_tickets.cell(row=fila_t, column=4, value=p["total"])
            ct.font = total_font
            ct.fill = total_fill
            ct.number_format = moneda
            ct.border = borde
            for col in (5, 6):
                ws_tickets.cell(row=fila_t, column=col).fill = total_fill
                ws_tickets.cell(row=fila_t, column=col).border = borde
            fila_t += 2  # blank separator row before the next ticket

        anchos_t = [30, 8, 14, 14, 32, 8]
        for i, a in enumerate(anchos_t, start=1):
            ws_tickets.column_dimensions[get_column_letter(i)].width = a

        # ── Sheet 2: Orders and lines of the day ──
        ws2 = wb.create_sheet("Pedidos y líneas")
        fila = _titulo(ws2, f"PEDIDOS Y LÍNEAS — {fecha_hoy}", 8)
        fila += 1
        headers = ["Pedido", "Mesa", "Estado", "Hora", "Producto", "Cant.", "Precio unit.", "Subtotal"]
        fila_header = _encabezados(ws2, headers, fila)
        fila = fila_header

        pedidos_hoy = self.db.get_pedidos_hoy()
        total_vendido = 0.0
        for p in pedidos_hoy:
            lineas = self.db.get_lineas(p["id"])
            hora = (p["fecha_apertura"] or "")[11:16]
            estado_p = {"abierto": "🟡 abierto", "cerrado": "✅ cerrado",
                        "cancelado": "❌ cancelado"}.get(p["estado"], p["estado"])
            if not lineas:
                valores = [p["id"], p["mesa"], estado_p, hora, "(sin líneas)", "", "", ""]
                for col, v in enumerate(valores, start=1):
                    ws2.cell(row=fila, column=col, value=v).border = borde
                fila += 1
                continue
            for l in lineas:
                valores = [p["id"], p["mesa"], estado_p, hora,
                           l["nombre_producto"], l["cantidad"],
                           l["precio_unitario"], l["subtotal"]]
                for col, v in enumerate(valores, start=1):
                    cell = ws2.cell(row=fila, column=col, value=v)
                    cell.border = borde
                    if col in (7, 8):
                        cell.number_format = moneda
                        cell.alignment = Alignment(horizontal="right")
                if p["estado"] == "cerrado":
                    total_vendido += l["subtotal"]
                fila += 1

        ws2.cell(row=fila, column=1, value="TOTAL VENDIDO (pedidos cerrados)").font = total_font
        ws2.cell(row=fila, column=1).fill = total_fill
        ws2.cell(row=fila, column=1).border = borde
        for col in range(2, 8):
            ws2.cell(row=fila, column=col).fill = total_fill
            ws2.cell(row=fila, column=col).border = borde
        cv = ws2.cell(row=fila, column=8, value=total_vendido)
        cv.font = total_font
        cv.fill = total_fill
        cv.number_format = moneda
        cv.border = borde

        anchos2 = [10, 12, 12, 8, 30, 8, 14, 14]
        for i, a in enumerate(anchos2, start=1):
            ws2.column_dimensions[get_column_letter(i)].width = a
        ws2.freeze_panes = f"A{fila_header + 1}"
        if fila > fila_header:
            ws2.auto_filter.ref = f"A{fila_header}:H{fila - 1}"

        # ── Sheet 3: Cancellations of the day ──
        ws3 = wb.create_sheet("Cancelaciones")
        fila = _titulo(ws3, f"CANCELACIONES — {fecha_hoy}", 6)
        fila += 1
        fila_header = _encabezados(
            ws3, ["Hora", "Pedido", "Mesa", "Total", "Productos cancelados", "Motivo"], fila)
        fila = fila_header
        cancelaciones = self.db.get_cancelaciones_hoy()
        for c in cancelaciones:
            hora = (c["fecha"] or "").replace("T", " ")[11:16]
            motivo = c["motivo"] or ""
            productos = self.db.resumen_detalle_cancelacion(c["detalle"])
            valores = [hora, c["pedido_id"], c["mesa"], c["total"], productos, motivo or "⏳ SIN MOTIVO"]
            for col, v in enumerate(valores, start=1):
                cell = ws3.cell(row=fila, column=col, value=v)
                cell.border = borde
                if col == 4:
                    cell.number_format = moneda
                    cell.alignment = Alignment(horizontal="right")
                if col == 6 and not motivo:
                    cell.font = pendiente_font
            fila += 1
        if not cancelaciones:
            ws3.cell(row=fila, column=1, value="Sin cancelaciones hoy").font = Font(italic=True, color="666666")
        anchos3 = [10, 10, 14, 14, 46, 32]
        for i, a in enumerate(anchos3, start=1):
            ws3.column_dimensions[get_column_letter(i)].width = a

        # ── Sheet 4: Expenses of the day ──
        ws4 = wb.create_sheet("Gastos")
        fila = _titulo(ws4, f"GASTOS — {fecha_hoy}", 3)
        fila += 1
        fila_header = _encabezados(ws4, ["Fecha", "Motivo", "Valor"], fila)
        fila = fila_header
        total_gastos = 0.0
        for g in self.db.get_gastos_hoy():
            ws4.cell(row=fila, column=1, value=g["fecha"]).border = borde
            ws4.cell(row=fila, column=2, value=g["motivo"]).border = borde
            cv = ws4.cell(row=fila, column=3, value=g["valor"])
            cv.number_format = moneda
            cv.border = borde
            total_gastos += g["valor"]
            fila += 1
        ws4.cell(row=fila, column=1, value="TOTAL").font = total_font
        ws4.cell(row=fila, column=1).fill = total_fill
        ws4.cell(row=fila, column=1).border = borde
        ws4.cell(row=fila, column=2).fill = total_fill
        ws4.cell(row=fila, column=2).border = borde
        cv = ws4.cell(row=fila, column=3, value=total_gastos)
        cv.font = total_font
        cv.fill = total_fill
        cv.number_format = moneda
        cv.border = borde
        anchos4 = [20, 32, 16]
        for i, a in enumerate(anchos4, start=1):
            ws4.column_dimensions[get_column_letter(i)].width = a

        # ── Sheet 5: Prices edited during the day (audit) ──
        ws5 = wb.create_sheet("Precios editados")
        fila = _titulo(ws5, f"PRECIOS EDITADOS — {fecha_hoy}", 7)
        fila += 1
        fila_header = _encabezados(
            ws5, ["Hora", "Pedido", "Producto", "Cant.", "Precio real", "Precio cobrado", "Motivo"], fila)
        fila = fila_header
        historial_hoy = [h for h in self.db.get_historial_precios()
                          if (h["fecha"] or "").startswith(fecha_hoy)]
        for h in historial_hoy:
            hora = (h["fecha"] or "").replace("T", " ")[11:16]
            valores = [hora, h["pedido_id"], h["nombre_producto"], h["cantidad"],
                       h["precio_original"], h["precio_nuevo"], h["motivo"] or "—"]
            for col, v in enumerate(valores, start=1):
                cell = ws5.cell(row=fila, column=col, value=v)
                cell.border = borde
                if col in (5, 6):
                    cell.number_format = moneda
                    cell.alignment = Alignment(horizontal="right")
            fila += 1
        if not historial_hoy:
            ws5.cell(row=fila, column=1, value="Sin ediciones de precio hoy").font = Font(italic=True, color="666666")
        anchos5 = [10, 10, 28, 8, 14, 14, 30]
        for i, a in enumerate(anchos5, start=1):
            ws5.column_dimensions[get_column_letter(i)].width = a

        wb.save(ruta)
        return ruta

    # ── Cash close history: open the folder ───────────────────────
    def _abrir_carpeta_cierres(self):
        """
        Opens the folder where the Excel files of each day are already saved
        automatically (one per date, generated by themselves when doing the Cash
        Close). It does not generate or save anything new, it only opens what already exists.
        """
        carpeta = carpeta_cierres_excel()
        try:
            if os.name == "nt":
                os.startfile(carpeta)
            else:
                import subprocess
                subprocess.Popen(["xdg-open", carpeta])
        except Exception as e:
            messagebox.showerror("No se pudo abrir la carpeta", str(e))