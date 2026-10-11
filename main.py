#!/usr/bin/env python3
"""
RestaurantePOS - Point-of-sale system for restaurants
Includes a web server so waitstaff can take orders from their phones (local WiFi),
an admin panel, menu management, reports and security cameras.
It also prints order tickets and receipts on ESC/POS-compatible thermal printers.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sys
import os
import socket
from modules.impresora_cocina import (
    agregar_comanda_cocina,
    inicializar as inicializar_impresora,
)
import segno  # <-- Lightweight library used to generate the QR code natively

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.database import Database
from modules.caja import CajaModule
from modules.menu_manager import MenuManager
from modules.inventario import InventarioModule
from modules.reportes import ReportesModule
from modules.flask_server import FlaskServer
from modules.dashboard_server import DashboardServer
from modules.camaras import CamarasModule
from modules.camaras_config import CAMARAS
from modules.config import get as _env
from modules.licencia import licencia_valida, activar_con_clave, codigo_de_equipo


def obtener_ip_local():
    """Returns the PC's local IP address on the WiFi network."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def solicitar_activacion():
    """Window that asks for this machine's unique activation key.

    Returns True if activation succeeded, False if the user
    cancelled or ran out of attempts (in which case the program must not open).
    """
    ventana = tk.Tk()
    ventana.withdraw()  # do not show an empty background window

    codigo = codigo_de_equipo()
    messagebox.showinfo(
        "Activación requerida",
        "Este equipo necesita una clave de activación única antes de "
        "usar el programa por primera vez.\n\n"
        f"Código de este equipo:\n\n{codigo}\n\n"
        "Envía este código al proveedor del sistema para recibir tu "
        "clave de activación."
    )

    intentos_restantes = 3
    while intentos_restantes > 0:
        clave = simpledialog.askstring(
            "Activación",
            "Ingresa la clave de activación que te dieron:",
        )
        if clave is None:  # cancelled
            ventana.destroy()
            return False

        if activar_con_clave(clave):
            messagebox.showinfo("Activación exitosa", "¡Programa activado correctamente!")
            ventana.destroy()
            return True

        intentos_restantes -= 1
        messagebox.showerror(
            "Clave incorrecta",
            f"La clave no es válida para este equipo.\nIntentos restantes: {intentos_restantes}"
        )

    ventana.destroy()
    return False


class RestaurantePOS:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🍽️ RestaurantePOS — Sistema de Caja")
        self.root.attributes("-fullscreen", True)  # Enable full screen
        self.fullscreen_activo = True
        self.root.bind("<Escape>", self._salir_fullscreen)
        self.root.bind("<F11>", self._alternar_fullscreen)
        self.root.configure(bg="#1a1a2e")
        self.root.minsize(1000, 600)

        # Variable that stores the current URL of the waitstaff server
        self.url_meseras = ""

        # Database
        self.db = Database()
        self.db.inicializar()
        try:
            inicializar_impresora(self.db.path)
        except Exception as e:
            print(f"Error inicializando impresora de cocina: {e}")

        self._setup_styles()
        self._build_ui()

        # Flask server for the waitstaff
        self.flask = FlaskServer(self.db,callback_comanda=self._comanda_recibida,
            callback_impresora=agregar_comanda_cocina)
        self.flask.iniciar()

        # Separate read-only server for the owner's summary
        self.dashboard = DashboardServer(self.db)
        self.dashboard.iniciar()

        self._mostrar_info_servidor()

    def _mostrar_info_servidor(self):
        from modules.flask_server import PUERTO, PIN_ACCESO
        from modules.dashboard_server import PUERTO_DASHBOARD
        ip = obtener_ip_local()
        self.url_meseras = f"http://{ip}:{PUERTO}"
        
        # Update the label text and add the interactive QR button
        self.lbl_server_info.config(
            text=f"Meseras: {self.url_meseras} (PIN {PIN_ACCESO}) "
        )
        self.btn_qr.pack(side="right", padx=(0, 16), pady=5)

    def _mostrar_qr_ventana(self):
        """Generates and shows the QR code in a clean floating window."""
        if not self.url_meseras:
            messagebox.showwarning("Advertencia", "El servidor aún no ha inicializado su dirección IP.")
            return

        # Floating popup window setup
        ventana_qr = tk.Toplevel(self.root)
        ventana_qr.title("📱 Escanear Código QR")
        ventana_qr.configure(bg="#1a1a2e")
        ventana_qr.geometry("360x440")
        ventana_qr.resizable(False, False)
        ventana_qr.grab_set()  # Blocks the window behind until this one is closed
        ventana_qr.lift()
        ventana_qr.focus_force()

        # Title at the top of the popup window
        tk.Label(ventana_qr, text="CONEXIÓN MESERAS",
                 font=("Segoe UI", 14, "bold"),
                 bg="#1a1a2e", fg="#e94560").pack(pady=(20, 5))
        
        tk.Label(ventana_qr, text="Escanea desde el celular para abrir el menú",
                 font=("Segoe UI", 10),
                 bg="#1a1a2e", fg="#a0a8c0").pack(pady=(0, 15))

        # QR container (native Canvas for maximum speed and sharpness)
        canvas_size = 240
        canvas = tk.Canvas(ventana_qr, width=canvas_size, height=canvas_size, 
                           bg="white", bd=0, highlightthickness=0)
        canvas.pack()

        # Generate the QR code matrix using Segno
        qrcode = segno.make(self.url_meseras, error='M')
        matrix = list(qrcode.matrix)
        matrix_len = len(matrix)
        
        # Compute the best pixel scale to fit inside 240px
        scale = max(1, canvas_size // matrix_len)
        offset = (canvas_size - (matrix_len * scale)) // 2

        # Render the matrix directly onto the Tkinter canvas, with no intermediate files
        for r_idx, row in enumerate(matrix):
            for c_idx, byte in enumerate(row):
                if byte == 1:  # 1 means a dark module (black)
                    x1 = offset + (c_idx * scale)
                    y1 = offset + (r_idx * scale)
                    x2 = x1 + scale
                    y2 = y1 + scale
                    canvas.create_rectangle(x1, y1, x2, y2, fill="#1a1a2e", outline="#1a1a2e")

        # Informational text with the URL written below the QR
        tk.Label(ventana_qr, text=self.url_meseras,
                 font=("Segoe UI", 11, "bold"),
                 bg="#1a1a2e", fg="#27ae60").pack(pady=(15, 5))

        # Close button
        tk.Button(ventana_qr, text="Cerrar",
                  bg="#e94560", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", width=12,
                  command=ventana_qr.destroy).pack(pady=(10, 15))
        
        ventana_qr.after(10000, ventana_qr.destroy)

    def _comanda_recibida(self, pedido_id):
        """
        Called from the Flask thread when a new order arrives.
        Uses after() to update the UI on the main Tkinter thread.
        """
        self.root.after(0, lambda: self._notificar_comanda(pedido_id))

    def _notificar_comanda(self, pedido_id):
        pedido = self.db.get_pedido(pedido_id)
        mesa = pedido["mesa"] if pedido else f"#{pedido_id}"
        # Update the orders panel
        self.caja_mod.refresh_pedidos()
        # Show a visual alert
        ventana = tk.Toplevel(self.root)
        ventana.title("📱 Nueva Comanda")
        ventana.configure(bg="#1a1a2e")
        ventana.geometry("320x160")
        ventana.lift()
        ventana.focus_force()
        tk.Label(ventana, text="📱 NUEVA COMANDA",
                 font=("Segoe UI", 14, "bold"),
                 bg="#1a1a2e", fg="#27ae60").pack(pady=(20, 6))
        tk.Label(ventana, text=f"Mesa: {mesa}  (pedido #{pedido_id})",
                 font=("Segoe UI", 11),
                 bg="#1a1a2e", fg="#e0e0e0").pack(pady=4)
        tk.Button(ventana, text="OK",
                  bg="#27ae60", fg="white", font=("Segoe UI", 11, "bold"),
                  relief="flat", width=10,
                  command=ventana.destroy).pack(pady=16)
        ventana.after(5000, ventana.destroy)

    # ── Full screen ─────────────────────────────────────────
    def _salir_fullscreen(self, event=None):
        """Esc: leaves full screen (returns to a normal window)."""
        self.fullscreen_activo = False
        self.root.attributes("-fullscreen", False)

    def _alternar_fullscreen(self, event=None):
        """F11: goes back to full screen if in windowed mode,
        or leaves full screen if already in it."""
        self.fullscreen_activo = not self.fullscreen_activo
        self.root.attributes("-fullscreen", self.fullscreen_activo)

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background="#1a1a2e", borderwidth=0)
        style.configure("TNotebook.Tab",
                        background="#16213e",
                        foreground="#a0a8c0",
                        padding=[18, 10],
                        font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", "#e94560")],
                  foreground=[("selected", "white")])
        style.configure("TFrame", background="#1a1a2e")
        style.configure("TLabel", background="#1a1a2e", foreground="#e0e0e0")
        style.configure("TButton",
                        background="#e94560",
                        foreground="white",
                        font=("Segoe UI", 9, "bold"),
                        padding=[10, 6])
        style.map("TButton", background=[("active", "#c73652")])
        style.configure("Success.TButton",
                        background="#27ae60", foreground="white",
                        font=("Segoe UI", 9, "bold"), padding=[10, 6])
        style.configure("Warning.TButton",
                        background="#f39c12", foreground="white",
                        font=("Segoe UI", 9, "bold"), padding=[10, 6])

    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#16213e", height=45)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(header,
                 text="🍽️  DEMO RESTAURANT",
                 font=("Segoe UI", 18, "bold"),
                 bg="#16213e", fg="#e94560").pack(side="left", padx=20, pady=5)

        tk.Label(header,
                 text="Sistema de Caja y Gestión",
                 font=("Segoe UI", 10),
                 bg="#16213e", fg="#a0a8c0").pack(side="left", padx=5, pady=10)

        # Button to generate and interact with the QR (initially hidden until the IP is known)
        self.btn_qr = tk.Button(header,
                                text="🔍 Mostrar QR",
                                font=("Segoe UI", 9, "bold"),
                                bg="#27ae60", fg="white",
                                relief="flat", cursor="hand2",
                                command=self._mostrar_qr_ventana)

        # Server info (filled in later)
        self.lbl_server_info = tk.Label(header,
                                         text="⏳ Iniciando servidor...",
                                         font=("Segoe UI", 9),
                                         bg="#16213e", fg="#27ae60")
        self.lbl_server_info.pack(side="right", padx=(5, 10), pady=10)

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        self.caja_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.caja_frame, text="🧾  Caja / Pedidos")
        self.caja_mod = CajaModule(self.caja_frame, self.db)

        self.rep_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.rep_frame, text="📊  Reportes")
        self.rep_mod = ReportesModule(self.rep_frame, self.db)

        self.inv_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.inv_frame, text="📦  Inventario")
        self.inv_mod = InventarioModule(self.inv_frame, self.db)

        self.menu_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.menu_frame, text="📋  Menú")
        self.menu_mod = MenuManager(self.menu_frame, self.db, self.caja_mod.refresh_menu)

        self.cam_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.cam_frame, text="📷  Cámaras")
        self.cam_mod = CamarasModule(self.cam_frame, CAMARAS)

        # Refresh the inventory every time its tab is opened, so that
        # the most recent stock is always shown (for example, after
        # charging an order from the Cash Register tab).
        self.notebook.bind("<ButtonRelease-1>", self._validar_acceso_tabs)

    def _validar_acceso_tabs(self, event=None):
        indice = self.notebook.index("current")

        # Cameras tab (adjust the number if it changes)
        if indice == 4:
            import tkinter as tk
            
            # 1. Create a black screen that covers EVERYTHING inside cam_frame
            # We use self.notebook to access Tkinter's update method
            pantalla_bloqueo = tk.Frame(self.cam_frame, bg="black")
            pantalla_bloqueo.place(x=0, y=0, relwidth=1, relheight=1)
            
            # Force a visual update through the notebook widget
            self.notebook.update_idletasks()

            # 2. Ask for the password
            if not self._pedir_password():
                # If cancelled or failed, send them back to the first tab
                self.notebook.select(0)
                # Remove the lock for when they come back later
                pantalla_bloqueo.destroy()
            else:
                # 3. If the password is correct, destroy the black screen
                # The original cameras are still alive underneath, untouched
                pantalla_bloqueo.destroy()


    def _pedir_password(self):

        clave = simpledialog.askstring(
            "Acceso restringido",
            "Ingrese la contraseña:",
            show="*"
        )

        if clave is None:
            return False

        return clave == _env("CAMERAS_PASSWORD", "change_me")  # <-- Set CAMERAS_PASSWORD in .env
                
    def _on_tab_changed(self, event=None):
        if self.notebook.select() == str(self.inv_frame):
            self.inv_mod.refresh()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        if messagebox.askokcancel("Salir", "¿Desea cerrar RestaurantePOS?"):
            self.cam_mod.detener()
            self.flask.detener()
            self.dashboard.detener()
            self.db.cerrar()
            self.root.destroy()


if __name__ == "__main__":
    if not licencia_valida():
        if not solicitar_activacion():
            sys.exit(0)

    app = RestaurantePOS()
    app.run()