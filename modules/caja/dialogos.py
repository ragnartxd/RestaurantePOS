"""
Cash register popup windows

Tkinter dialogs used by CajaModule:

    - CobroVentana: normal / split payment (cash + transfer)
    - DividirCuentaVentana: split a payment between cash and transfer
    - EditarPrecioVentana: manual edit of a line's unit price
    - MotivoCancelacionVentana: mandatory reason when cancelling an order

"""

import tkinter as tk
from tkinter import ttk, messagebox


class MotivoCancelacionVentana:
    """
    Shown when an order is cancelled. Asks for the cancellation reason.

    `self.resultado` ends up as:
        - the text typed, if the cashier filled it in and confirmed
        - ""  (empty string) if they chose "Cancel without a reason for now" — the
          order is cancelled anyway, but it is left pending justification and
          if 10 minutes pass the manager is notified on the dashboard.
        - None if they closed the window without deciding (the order is not cancelled)
    """
    def __init__(self, parent, pedido_id, mesa=""):
        self.resultado = None
        self.top = tk.Toplevel(parent)
        self.top.title("Cancelar pedido")
        self.top.grab_set()
        self.top.configure(bg="#1a1a2e")
        self.top.resizable(False, False)

        tk.Label(self.top,
                 text=f"❌ Cancelar pedido #{pedido_id} ({mesa})",
                 font=("Segoe UI", 13, "bold"),
                 bg="#1a1a2e", fg="#e94560").pack(pady=(16, 4), padx=24)

        tk.Label(self.top, text="¿Por qué se cancela? (obligatorio)",
                 font=("Segoe UI", 10),
                 bg="#1a1a2e", fg="#e0e0e0").pack(pady=(4, 6))

        self.txt = tk.Text(self.top, width=34, height=4,
                            bg="#0f3460", fg="white",
                            insertbackground="white", relief="flat",
                            font=("Segoe UI", 10))
        self.txt.pack(padx=24, pady=(0, 10))
        self.txt.focus_set()

        tk.Button(self.top, text="✅ Confirmar cancelación",
                  bg="#e94560", fg="white", font=("Segoe UI", 11, "bold"),
                  relief="flat", cursor="hand2", pady=8,
                  command=self._confirmar).pack(fill="x", padx=24, pady=(0, 6))

        tk.Button(self.top,
                  text="⚠️ Cancelar sin motivo ahora (se avisará a la jefe)",
                  bg="#0f3460", fg="#f1c40f", font=("Segoe UI", 8),
                  relief="flat", cursor="hand2",
                  command=self._sin_motivo).pack(fill="x", padx=24, pady=(0, 4))

        tk.Button(self.top, text="Volver (no cancelar)",
                  bg="#1a1a2e", fg="#a0a8c0", font=("Segoe UI", 8),
                  relief="flat", cursor="hand2",
                  command=self.top.destroy).pack(pady=(0, 14))

        self.top.protocol("WM_DELETE_WINDOW", self.top.destroy)

    def _confirmar(self):
        motivo = self.txt.get("1.0", "end").strip()
        if not motivo:
            messagebox.showwarning(
                "Falta el motivo",
                "Escribe el motivo, o usa el botón de abajo para cancelar "
                "sin motivo (se le notificará a la jefe si no se justifica "
                "en los próximos 10 minutos)."
            )
            return
        self.resultado = motivo
        self.top.destroy()

    def _sin_motivo(self):
        if messagebox.askyesno(
            "Cancelar sin motivo",
            "El pedido se cancelará ya mismo, pero si en 10 minutos nadie "
            "escribe el motivo, se le notificará automáticamente a la jefe "
            "en el dashboard.\n\n¿Continuar sin motivo?"
        ):
            self.resultado = ""
            self.top.destroy()

class CobroVentana:
    def __init__(self, parent, total, titulo="Cobrar pedido"):
        self.resultado = None
        self.detalle = None
        self.total = total
        self.top = tk.Toplevel(parent)
        self.top.title(titulo)
        self.top.grab_set()
        self.top.configure(bg="#1a1a2e")
        self.top.resizable(False, False)

        tk.Label(self.top, text=f"Total a cobrar: ${total:,.0f}",
                 font=("Segoe UI", 16, "bold"),
                 bg="#1a1a2e", fg="#e94560").pack(pady=16, padx=24)
        tk.Label(self.top, text="Método de pago:",
                 font=("Segoe UI", 11),
                 bg="#1a1a2e", fg="#e0e0e0").pack()

        for label, metodo in [("💵 Efectivo",              "efectivo"),
                               ("📱 Transferencia", "Bancolombia")]:
            tk.Button(self.top, text=label,
                      bg="#0f3460", fg="white",
                      font=("Segoe UI", 12, "bold"),
                      relief="flat", cursor="hand2", width=24, pady=8,
                      command=lambda m=metodo: self._seleccionar(m)).pack(pady=4)

        tk.Button(self.top, text="🔀 Cuenta dividida",
                  bg="#8e44ad", fg="white",
                  font=("Segoe UI", 12, "bold"),
                  relief="flat", cursor="hand2", width=24, pady=8,
                  command=self._cuenta_dividida).pack(pady=4)

        tk.Button(self.top, text="Cancelar",
                  bg="#7f8c8d", fg="white",
                  relief="flat", cursor="hand2",
                  command=self.top.destroy).pack(pady=8)

    def _seleccionar(self, metodo):
        self.resultado = metodo
        self.top.destroy()

    def _cuenta_dividida(self):
        ventana = DividirCuentaVentana(self.top, self.total)
        self.top.wait_window(ventana.top)
        if ventana.resultado:
            efectivo, transferencia = ventana.resultado
            self.detalle = {"efectivo": efectivo, "transferencia": transferencia}
            self.resultado = "Cuenta dividida"
            self.top.destroy()


class DividirCuentaVentana:
    """
    Dialog to charge a bill split between cash and transfer
    (e.g. two people each pay part, one in cash and the other by
    transfer). Validates live that the sum of both amounts matches
    the total to charge, but allows forcing the charge with an extra
    confirmation if the cashier decides to close it that way anyway.
    """
    def __init__(self, parent, total):
        self.resultado = None
        self.total = total
        self.top = tk.Toplevel(parent)
        self.top.title("Cuenta dividida")
        self.top.grab_set()
        self.top.configure(bg="#1a1a2e")
        self.top.resizable(False, False)

        tk.Label(self.top, text=f"Total a cobrar: ${total:,.0f}",
                 font=("Segoe UI", 14, "bold"),
                 bg="#1a1a2e", fg="#e94560").pack(pady=(16, 8), padx=24)

        form = tk.Frame(self.top, bg="#1a1a2e")
        form.pack(fill="x", padx=24)

        tk.Label(form, text="💵 Monto en efectivo ($)",
                 font=("Segoe UI", 9), bg="#1a1a2e", fg="#a0a8c0", anchor="w").pack(fill="x")
        self.var_efectivo = tk.StringVar(value="0")
        entry_efectivo = tk.Entry(form, textvariable=self.var_efectivo,
                                  bg="#16213e", fg="white", insertbackground="white",
                                  relief="flat", font=("Segoe UI", 12))
        entry_efectivo.pack(fill="x", pady=(2, 10))

        tk.Label(form, text="📱 Monto en transferencia ($)",
                 font=("Segoe UI", 9), bg="#1a1a2e", fg="#a0a8c0", anchor="w").pack(fill="x")
        self.var_transferencia = tk.StringVar(value=str(int(total)))
        entry_transferencia = tk.Entry(form, textvariable=self.var_transferencia,
                                       bg="#16213e", fg="white", insertbackground="white",
                                       relief="flat", font=("Segoe UI", 12))
        entry_transferencia.pack(fill="x", pady=(2, 6))

        self.lbl_estado = tk.Label(self.top, text="",
                                   font=("Segoe UI", 9, "bold"),
                                   bg="#1a1a2e", fg="#f39c12")
        self.lbl_estado.pack(pady=(0, 8))

        self.var_efectivo.trace_add("write", lambda *a: self._actualizar_estado())
        self.var_transferencia.trace_add("write", lambda *a: self._actualizar_estado())

        btns = tk.Frame(self.top, bg="#1a1a2e")
        btns.pack(fill="x", padx=24, pady=(4, 18))
        tk.Button(btns, text="✅ Confirmar cobro dividido",
                  bg="#27ae60", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", cursor="hand2", pady=8,
                  command=self._confirmar).pack(fill="x", pady=2)
        tk.Button(btns, text="Cancelar",
                  bg="#7f8c8d", fg="white",
                  relief="flat", cursor="hand2",
                  command=self.top.destroy).pack(fill="x", pady=2)

        self.top.bind("<Return>", lambda e: self._confirmar())
        entry_efectivo.focus_set()
        entry_efectivo.select_range(0, "end")
        self._actualizar_estado()

    def _leer_monto(self, var):
        texto = var.get().strip().replace("$", "").replace(",", "").replace(" ", "")
        if not texto:
            return 0.0
        try:
            return float(texto)
        except ValueError:
            return None

    def _actualizar_estado(self):
        efectivo = self._leer_monto(self.var_efectivo)
        transferencia = self._leer_monto(self.var_transferencia)
        if efectivo is None or transferencia is None:
            self.lbl_estado.config(text="⚠️ Ingresa solo números.", fg="#e94560")
            return
        diferencia = round(self.total - (efectivo + transferencia), 2)
        if abs(diferencia) < 1:
            self.lbl_estado.config(text="✅ Los montos cuadran con el total.", fg="#27ae60")
        elif diferencia > 0:
            self.lbl_estado.config(text=f"Faltan ${diferencia:,.0f} por asignar.", fg="#f39c12")
        else:
            self.lbl_estado.config(text=f"Sobran ${-diferencia:,.0f} sobre el total.", fg="#e94560")

    def _confirmar(self):
        efectivo = self._leer_monto(self.var_efectivo)
        transferencia = self._leer_monto(self.var_transferencia)
        if efectivo is None or transferencia is None or efectivo < 0 or transferencia < 0:
            messagebox.showerror("Error", "Los montos deben ser números válidos mayores o iguales a 0.",
                                 parent=self.top)
            return
        diferencia = round(self.total - (efectivo + transferencia), 2)
        if abs(diferencia) >= 1:
            if not messagebox.askyesno(
                "Los montos no cuadran",
                f"Efectivo (${efectivo:,.0f}) + Transferencia (${transferencia:,.0f}) = "
                f"${efectivo + transferencia:,.0f}, pero el total es ${self.total:,.0f} "
                f"(diferencia de ${abs(diferencia):,.0f}).\n\n¿Cobrar de todas formas con estos montos?",
                parent=self.top
            ):
                return
        self.resultado = (efectivo, transferencia)
        self.top.destroy()


class EditarPrecioVentana:
    """
    Dialog to lower/edit the unit price of a ticket line.
    Returns (new_price, reason) in self.resultado, or None if cancelled.
    """
    def __init__(self, parent, nombre_producto, precio_real, precio_actual, cantidad):
        self.resultado = None
        self.top = tk.Toplevel(parent)
        self.top.title("Editar precio unitario")
        self.top.grab_set()
        self.top.configure(bg="#1a1a2e")
        self.top.resizable(False, False)

        tk.Label(self.top, text=nombre_producto,
                 font=("Segoe UI", 13, "bold"),
                 bg="#1a1a2e", fg="#e94560", wraplength=280).pack(pady=(18, 4), padx=24)

        tk.Label(self.top,
                 text=f"Precio real de menú: ${precio_real:,.0f}   •   Cantidad: {cantidad}",
                 font=("Segoe UI", 9),
                 bg="#1a1a2e", fg="#a0a8c0").pack(pady=(0, 4), padx=24)
        tk.Label(self.top,
                 text=f"Precio actual en el ticket: ${precio_actual:,.0f}",
                 font=("Segoe UI", 9),
                 bg="#1a1a2e", fg="#a0a8c0").pack(pady=(0, 12), padx=24)

        form = tk.Frame(self.top, bg="#1a1a2e")
        form.pack(fill="x", padx=24)

        tk.Label(form, text="Nuevo precio unitario ($)",
                 font=("Segoe UI", 9), bg="#1a1a2e", fg="#a0a8c0", anchor="w").pack(fill="x")
        self.var_precio = tk.StringVar(value=str(int(precio_actual)))
        entry_precio = tk.Entry(form, textvariable=self.var_precio,
                                bg="#16213e", fg="white", insertbackground="white",
                                relief="flat", font=("Segoe UI", 12))
        entry_precio.pack(fill="x", pady=(2, 10))
        entry_precio.focus_set()
        entry_precio.select_range(0, "end")

        tk.Label(form, text="Motivo (opcional, ej. 'descuento por promoción')",
                 font=("Segoe UI", 9), bg="#1a1a2e", fg="#a0a8c0", anchor="w").pack(fill="x")
        self.var_motivo = tk.StringVar()
        tk.Entry(form, textvariable=self.var_motivo,
                 bg="#16213e", fg="white", insertbackground="white",
                 relief="flat", font=("Segoe UI", 10)).pack(fill="x", pady=(2, 10))

        tk.Label(form,
                 text="⚠️ El precio real y el precio modificado quedan\n"
                      "registrados en el historial de auditoría.",
                 font=("Segoe UI", 8, "italic"), bg="#1a1a2e", fg="#f39c12",
                 justify="left").pack(fill="x", pady=(0, 10))

        btns = tk.Frame(self.top, bg="#1a1a2e")
        btns.pack(fill="x", padx=24, pady=(0, 18))
        tk.Button(btns, text="✅ Confirmar cambio",
                  bg="#27ae60", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", cursor="hand2", pady=8,
                  command=self._confirmar).pack(fill="x", pady=2)
        tk.Button(btns, text="Cancelar",
                  bg="#7f8c8d", fg="white",
                  relief="flat", cursor="hand2",
                  command=self.top.destroy).pack(fill="x", pady=2)

        self.top.bind("<Return>", lambda e: self._confirmar())

    def _confirmar(self):
        texto = self.var_precio.get().strip().replace("$", "").replace(",", "").replace(" ", "")
        try:
            nuevo_precio = float(texto)
            if nuevo_precio < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "El precio debe ser un número válido mayor o igual a 0.",
                                 parent=self.top)
            return
        self.resultado = (nuevo_precio, self.var_motivo.get().strip())
        self.top.destroy()