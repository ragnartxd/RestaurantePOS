"""
Tiled view of the 8 HiLook cameras with
double-click to enlarge any of them in a large window.

Each camera is read in its own background thread (so the rest of
the app does not freeze while it connects or if a camera goes down), and the
UI only picks up the latest available frame at regular intervals.
"""

import os
import threading
import time
import collections

import cv2
import tkinter as tk
from PIL import Image, ImageTk

try:
    from modules.camaras_config import DELAY_SEGUNDOS
except ImportError:
    DELAY_SEGUNDOS = 10 

os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|buffer_size;1024000"
)

INTERVALO_MUESTREO = 0.15  
THUMB_W, THUMB_H = 260, 146
GRANDE_W, GRANDE_H = 800, 450

BG_DARK = "#1a1a2e"
BG_PANEL = "#16213e"
BG_CARD = "#0f3460"
ACCENT = "#e94560"
TEXT_MUTED = "#a0a8c0"
WARN = "#f39c12"


class CameraStream:

    def __init__(self, nombre, url, delay_segundos=None):
        self.nombre = nombre
        self.url = url
        self.delay_segundos = DELAY_SEGUNDOS if delay_segundos is None else delay_segundos

        self._buffer = collections.deque()
        self._frame_actual = None            
        self._lock = threading.Lock()
        self._running = True
        self.conectada = False
        self._ultimo_guardado = 0.0
        self._inicio_buffer = time.monotonic()

        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        cap = None
        while self._running:
            if cap is None or not cap.isOpened():
                try:
                    cap = cv2.VideoCapture(self.url)
                except Exception:
                    cap = None
                if cap is None or not cap.isOpened():
                    self.conectada = False
                    time.sleep(3)
                    continue

            ret, frame = cap.read()
            if ret:
                self.conectada = True
                ahora = time.monotonic()

                if ahora - self._ultimo_guardado >= INTERVALO_MUESTREO:
                    self._ultimo_guardado = ahora
                    with self._lock:
                        self._buffer.append((ahora, frame))
                        self._avanzar_frame_retrasado(ahora)
            else:
                self.conectada = False
                try:
                    cap.release()
                except Exception:
                    pass
                cap = None

                with self._lock:
                    self._buffer.clear()
                    self._frame_actual = None
                self._inicio_buffer = time.monotonic()
                time.sleep(2)

        if cap is not None:
            cap.release()

    def _avanzar_frame_retrasado(self, ahora):
        """Must be called with self._lock already held."""
        objetivo = ahora - self.delay_segundos
        while self._buffer and self._buffer[0][0] <= objetivo:
            self._frame_actual = self._buffer.popleft()[1]

    def esta_cargando(self):
        """True while the full delay has not yet elapsed since
        the buffer started filling."""
        return (time.monotonic() - self._inicio_buffer) < self.delay_segundos

    def segundos_restantes(self):
        restante = self.delay_segundos - (time.monotonic() - self._inicio_buffer)
        return max(0, int(restante) + 1)

    def get_frame(self):

        if self.esta_cargando():
            return None
        with self._lock:
            return None if self._frame_actual is None else self._frame_actual.copy()

    def detener(self):
        self._running = False


def _frame_a_imagetk(frame_bgr, ancho, alto):
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(frame_rgb).resize((ancho, alto))
    return ImageTk.PhotoImage(image=img)


class CamarasModule:
    def __init__(self, parent, camaras_config):
        self.parent = parent

        self.streams = [
            CameraStream(c["nombre"], c.get("url_secundaria", c.get("url")))
            for c in camaras_config
        ]
        self._imgtk_refs = {}
        self._ventanas_ampliadas = {}  
        self._activo = True
        self._build_ui()
        self.parent.after(200, self._actualizar_mosaico)

    # ── UI ──────────────────────────────────────────────────────
    def _build_ui(self):
        cont = tk.Frame(self.parent, bg=BG_DARK)
        cont.pack(fill="both", expand=True, padx=8, pady=8)

        titulo = "📷 CÁMARAS EN VIVO — doble clic para ampliar"
        if self.streams and self.streams[0].delay_segundos > 0:
            titulo += f"  (retraso ~{self.streams[0].delay_segundos:.0f}s para mayor fluidez)"
        tk.Label(cont, text=titulo,
                 font=("Segoe UI", 11, "bold"),
                 bg=BG_DARK, fg=ACCENT).pack(pady=(2, 8))

        grid_frame = tk.Frame(cont, bg=BG_DARK)
        grid_frame.pack(fill="both", expand=True)

        self._labels = {}
        self._estado_labels = {}

        cols = 4
        for idx, stream in enumerate(self.streams):
            fila, col = divmod(idx, cols)
            grid_frame.columnconfigure(col, weight=1)
            grid_frame.rowconfigure(fila, weight=1)

            card = tk.Frame(grid_frame, bg=BG_PANEL, bd=1, relief="flat")
            card.grid(row=fila, column=col, padx=5, pady=5, sticky="nsew")

            header = tk.Frame(card, bg=BG_CARD)
            header.pack(fill="x")
            tk.Label(header, text=stream.nombre, font=("Segoe UI", 9, "bold"),
                     bg=BG_CARD, fg="white").pack(side="left", padx=6, pady=3)
            estado_lbl = tk.Label(header, text="●", font=("Segoe UI", 10),
                                   bg=BG_CARD, fg=WARN)
            estado_lbl.pack(side="right", padx=6)
            self._estado_labels[stream.nombre] = estado_lbl

            video_lbl = tk.Label(card, bg="black", width=THUMB_W, height=THUMB_H,
                                  text="Conectando…", fg=TEXT_MUTED,
                                  font=("Segoe UI", 9))
            video_lbl.pack(fill="both", expand=True)
            video_lbl.bind("<Double-Button-1>",
                           lambda e, s=stream: self._abrir_ampliada(s))

            self._labels[stream.nombre] = video_lbl

    # ── Periodic mosaic refresh ─────────────────────────────────
    def _actualizar_mosaico(self):
        if not self._activo:
            return
        for stream in self.streams:
            lbl = self._labels[stream.nombre]
            estado_lbl = self._estado_labels[stream.nombre]
            frame = stream.get_frame()

            if frame is not None:
                photo = _frame_a_imagetk(frame, THUMB_W, THUMB_H)
                self._imgtk_refs[stream.nombre] = photo
                lbl.configure(image=photo, text="")
                estado_lbl.configure(fg="#27ae60")
            elif stream.conectada and stream.esta_cargando():
                lbl.configure(image="",
                              text=f"⏳ Cargando buffer…\n{stream.segundos_restantes()}s",
                              fg=TEXT_MUTED)
                estado_lbl.configure(fg=WARN)
            else:
                lbl.configure(image="", text="Sin señal", fg=TEXT_MUTED)
                estado_lbl.configure(fg=ACCENT)

        self.parent.after(200, self._actualizar_mosaico)

    # ── Enlarged window (double click) ──────────────────────────
    def _abrir_ampliada(self, stream_mosaico):
        nombre = stream_mosaico.nombre
        existente = self._ventanas_ampliadas.get(nombre)
        if existente is not None and existente.winfo_exists():
            existente.lift()
            existente.focus_force()
            return

        top = tk.Toplevel(self.parent)
        top.title(f"📷 {nombre}")
        top.configure(bg=BG_DARK)
        self._ventanas_ampliadas[nombre] = top

        video_lbl = tk.Label(top, bg="black", width=GRANDE_W, height=GRANDE_H,
                              text="Conectando…", fg=TEXT_MUTED, font=("Segoe UI", 11))
        video_lbl.pack(fill="both", expand=True, padx=6, pady=6)
        video_lbl.bind("<Double-Button-1>", lambda e: al_cerrar())

        tk.Label(top, text="Doble clic en la imagen para cerrar",
                 font=("Segoe UI", 8), bg=BG_DARK, fg=TEXT_MUTED).pack(pady=(0, 6))

        refs = {}

        def refrescar():
            if not top.winfo_exists():
                return
            frame = stream_mosaico.get_frame()
            if frame is not None:
                photo = _frame_a_imagetk(frame, GRANDE_W, GRANDE_H)
                refs["img"] = photo
                video_lbl.configure(image=photo, text="")
            elif stream_mosaico.conectada and stream_mosaico.esta_cargando():
                video_lbl.configure(
                    image="", text=f"⏳ Cargando buffer…\n{stream_mosaico.segundos_restantes()}s")
            else:
                video_lbl.configure(image="", text="Sin señal")
            top.after(150, refrescar)

        def al_cerrar():
            self._ventanas_ampliadas.pop(nombre, None)
            top.destroy()

        top.protocol("WM_DELETE_WINDOW", al_cerrar)
        refrescar()

    # ── Clean shutdown ──────────────────────────────────────────
    def detener(self):
        self._activo = False
        for stream in self.streams:
            stream.detener()