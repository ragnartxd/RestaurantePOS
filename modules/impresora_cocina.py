"""
Kitchen printer: print queue and smart retries

Manages a print queue to avoid blocking the thermal printer.
Orders are sent from two sources:
  1. Central Register: manual sending via a button
  2. Waitstaff (phone): automatic sending when registered

Business rules:
  - Only kitchen products are printed (configurable by category)
  - Drinks and products that need no preparation are filtered out
  - Duplicate prevention guaranteed
  - Smart retries in case of connection failure
  - Paper cut after each order
"""

import threading
import time
import logging
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
import re

try:
    from escpos.printer import Network
except ImportError:
    Network = None

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - ImpresoCocina - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ConfiguracionImpresora:
    """Kitchen printer configuration"""
    ip_impresora: str = "192.168.1.100" # Default IP of the kitchen printers, at least as far as I could find out.
    puerto: int = 9100
    timeout: int = 5
    ancho_papel: int = 80  # mm
    
    # Categories that are printed in the kitchen
    categorias_cocina: List[str] = None
    
    # Categories that are NOT printed
    categorias_excluidas: List[str] = None
    
    # Retry parameters
    max_reintentos: int = 3
    tiempo_espera_reintento: int = 2  # seconds
    
    # Queue parameters
    timeout_cola: int = 300  # seconds
    max_tamaño_cola: int = 100
    
    # Font sizes: double width / double height (ESC ! command — the most
    # compatible across thermal printers).
    # (double_width, double_height) per section.
    doble_encabezado: Tuple[bool, bool] = (True, True)   # "KITCHEN ORDER"
    doble_info: Tuple[bool, bool] = (True, True)         # Table / Order / Time
    doble_nota: Tuple[bool, bool] = (True, False)        # NOTA: ...
    # (The product line uses a fixed size defined directly in
    #  _imprimir_en_cocina — there is also, commented out, size 5 with
    #  GS! in case an even bigger one is wanted.)
    
    def __post_init__(self):
        """Initialize default lists"""
        if self.categorias_cocina is None:
            self.categorias_cocina = [
                "desayunos", "almuerzos", "carta", "platos principales",
                "arroces", "pastas", "sándwiches", "soups"
            ]
        if self.categorias_excluidas is None:
            self.categorias_excluidas = ["bebidas", "tinto", "café", "refrescos"]


class ColaPrinter:
    """Sequential print queue manager"""
    
    def __init__(self, db_path: str, config: ConfiguracionImpresora = None):
        """
        Initializes the queue manager.
        
        Args:
            db_path: Path to the SQLite database
            config: Printer configuration
        """
        self.db_path = db_path
        self.config = config or ConfiguracionImpresora()
        
        # Queue control
        self._cola = []
        self._lock = threading.RLock()
        self._evento_trabajo = threading.Event()
        self._ejecutor_thread: Optional[threading.Thread] = None
        self._activo = False
        
        # Statistics
        self.stats = {
            "total_procesados": 0,
            "total_errores": 0,
            "ultima_impresion": None,
        }
        
        # Initialize DB
        self._inicializar_bd()
        
    def _inicializar_bd(self):
        """Create the necessary tables if they do not exist"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cola_impresion (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pedido_id INTEGER NOT NULL,
                    ronda INTEGER,
                    estado TEXT DEFAULT 'pendiente',
                    fecha_creacion TEXT NOT NULL,
                    fecha_procesamiento TEXT,
                    intentos INTEGER DEFAULT 0,
                    error_mensaje TEXT,
                    hash_comanda TEXT UNIQUE NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS impresiones_realizadas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pedido_id INTEGER NOT NULL,
                    ronda INTEGER,
                    hash_comanda TEXT UNIQUE NOT NULL,
                    fecha_impresion TEXT NOT NULL,
                    contenido TEXT
                )
            """)
            
            conn.commit()
            logger.info("Tablas de cola de impresión inicializadas correctamente")
        except Exception as e:
            logger.error(f"Error inicializando BD: {e}")
        finally:
            conn.close()
    
    def iniciar(self):
        """Start the queue executor thread"""
        if self._activo:
            logger.warning("Cola de impresión ya está activa")
            return
        
        self._activo = True
        self._ejecutor_thread = threading.Thread(
            target=self._ejecutar_cola,
            daemon=True,
            name="EjecutorColaPrinter"
        )
        self._ejecutor_thread.start()
        logger.info("Cola de impresión iniciada")
    
    def detener(self):
        """Stop the queue manager"""
        self._activo = False
        self._evento_trabajo.set()
        if self._ejecutor_thread:
            self._ejecutor_thread.join(timeout=5)
        logger.info("Cola de impresión detenida")
    
    def _ejecutar_cola(self):
        """Main thread that processes the queue"""
        while self._activo:
            try:
                # Wait for work or timeout
                self._evento_trabajo.wait(timeout=self.config.timeout_cola)
                self._evento_trabajo.clear()
                
                with self._lock:
                    if not self._cola:
                        # Look in the DB for pending jobs
                        self._cargar_trabajos_pendientes()
                    
                    if self._cola:
                        trabajo = self._cola[0]
                        self._procesar_trabajo(trabajo)
                        self._cola.pop(0)
                    
            except Exception as e:
                logger.error(f"Error en hilo ejecutor: {e}")
                time.sleep(1)
    
    def _cargar_trabajos_pendientes(self):
        """Load pending jobs from the DB"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            
            filas = conn.execute("""
                SELECT * FROM cola_impresion
                WHERE estado = 'pendiente'
                ORDER BY fecha_creacion ASC
                LIMIT 10
            """).fetchall()
            
            for fila in filas:
                self._cola.append({
                    "id": fila["id"],
                    "pedido_id": fila["pedido_id"],
                    "ronda": fila["ronda"],
                    "hash": fila["hash_comanda"],
                    "intentos": fila["intentos"],
                })
            
            conn.close()
        except Exception as e:
            logger.error(f"Error cargando trabajos pendientes: {e}")
    
    def _procesar_trabajo(self, trabajo: Dict):
        """
        Processes a print job.
        
        Args:
            trabajo: Dictionary with the job data
        """
        pedido_id = trabajo["pedido_id"]
        ronda = trabajo.get("ronda")
        hash_comanda = trabajo["hash"]
        intentos = trabajo["intentos"]
        
        logger.info(f"Procesando comanda pedido_id={pedido_id}, ronda={ronda}, "
                   f"intento={intentos + 1}/{self.config.max_reintentos}")
        
        # Get the order data
        contenido = self._construir_contenido_comanda(pedido_id, ronda)
        
        if not contenido:
            logger.warning(f"Comanda {pedido_id} no tiene productos para cocina")
            self._marcar_completado(trabajo["id"], pedido_id, ronda, hash_comanda)
            return
        
        # Try to print
        exito = False
        try:
            exito = self._imprimir_en_cocina(contenido)
        except Exception as e:
            logger.error(f"Error imprimiendo: {e}")
        
        # Handle the result
        if exito:
            self._marcar_completado(trabajo["id"], pedido_id, ronda, hash_comanda, contenido["texto"])
            self.stats["total_procesados"] += 1
            self.stats["ultima_impresion"] = datetime.now().isoformat()
        else:
            if intentos < self.config.max_reintentos - 1:
                # Retry
                self._reprogramar_trabajo(trabajo["id"], intentos + 1)
                time.sleep(self.config.tiempo_espera_reintento)
            else:
                # Permanent error
                self._marcar_error(trabajo["id"], "Máximo de reintentos alcanzado")
                self.stats["total_errores"] += 1
    
    def _construir_contenido_comanda(self, pedido_id: int, ronda: Optional[int]) -> Optional[Dict]:
        """
        Builds the order content, filtering by category.
        
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            
            # Get the order
            pedido = conn.execute(
                "SELECT * FROM pedidos WHERE id = ?",
                (pedido_id,)
            ).fetchone()
            
            if not pedido:
                logger.warning(f"Pedido {pedido_id} no encontrado")
                conn.close()
                return None

            pedido = dict(pedido)
            
            # Get the order lines
            query = "SELECT * FROM lineas_pedido WHERE pedido_id = ?"
            params = [pedido_id]
            
            if ronda:
                query += " AND ronda = ?"
                params.append(ronda)
            
            query += " ORDER BY id ASC"
            
            lineas = conn.execute(query, params).fetchall()
            conn.close()
            
            if not lineas:
                return None
            
            # Filter products: kitchen only, exclude drinks
            productos_cocina = self._filtrar_productos_cocina(lineas)
            
            if not productos_cocina:
                return None
            
            # Build content (styled segments for large sizes)
            segmentos = self._formatear_comanda(
                pedido_id,
                ronda,
                pedido,
                productos_cocina
            )
            
            texto_plano = "\n".join(texto for texto, _estilo in segmentos)
            
            return {"texto": texto_plano, "segmentos": segmentos}
            
        except Exception as e:
            logger.error(f"Error construyendo contenido: {e}")
            return None
    
    def _filtrar_productos_cocina(self, lineas: List) -> List[Dict]:
        """
        Filters products that must go to the kitchen.
        
        Excludes:
        - Drinks (specific category)
        - Products with no category or with an excluded category
        - Included (free) drinks
        
        Returns: List of products for the kitchen
        """
        productos = []
        
        for linea in lineas:
            linea = dict(linea)

            # Exclude included (free) drinks
            if linea.get("es_bebida_incluida"):
                continue
            
            nombre = linea["nombre_producto"].lower()
            categoria = linea.get("categoria", "").lower()
            
            # Check whether it is a drink by name
            es_bebida_por_nombre = any(
                palabra in nombre
                for palabra in ["bebida", "tinto", "café", "chocolate", "refresco",
                              "gaseosa", "jugo", "agua", "limonada","Jarra Limonada"]
            )
            
            if es_bebida_por_nombre:
                continue
            
            # Check the category
            en_exclusion = any(
                exc.lower() in categoria
                for exc in self.config.categorias_excluidas
            )
            
            if en_exclusion:
                continue
            
            # Include kitchen product
            productos.append({
                "nombre": linea["nombre_producto"],
                "cantidad": linea["cantidad"],
                "notas": linea.get("notas", ""),
            })
        
        return productos
    
    @staticmethod
    def _mesera_de_pedido(pedido: Dict) -> Optional[str]:
        """
        Extracts the waitress's name from the order notes, where
        it is stored as '...- mesera: Alex' when the order is created
        from the phone. Returns None if it does not apply (order taken
        directly at the central register), and in that case the order is printed
        exactly as before, with no extra line.
        """
        notas = (pedido or {}).get("notas") or ""
        m = re.search(r"mesera:\s*(.+)$", notas, re.IGNORECASE)
        return m.group(1).strip() or None if m else None

    @staticmethod
    def limpiar_nombre_impresion(nombre_original: str) -> str:
        """
        Cleans internal labels or prefixes for the printed order
        without altering the name stored in the database or the menu.
        """
        texto = nombre_original

        # 1. Remove the word "Combo " or "combo " at the start
        texto = re.sub(r'^(combo|Combo)\s+', '', texto)

        # 2. Remove the word "transportador" or "Transportador" anywhere
        texto = re.sub(r'\b(transportador|Transportador)\b', '', texto, flags=re.IGNORECASE)

        # 3. Clean up double or leftover spaces
        return ' '.join(texto.split())
    
    def _formatear_comanda(
        self,
        pedido_id: int,
        ronda: Optional[int],
        pedido,
        productos: List[Dict]
    ) -> List[Tuple[str, str]]:
        """
        Formats the order for printing.

        """
        segmentos: List[Tuple[str, str]] = []
        
        # Header
        segmentos.append(("=" * 40, "separador"))
        segmentos.append(("COMANDA DE COCINA", "encabezado"))
        segmentos.append(("=" * 40, "separador"))
        
        # Info
        mesa = pedido.get("mesa", "N/A")
        segmentos.append((f"MESA: {mesa}", "info"))
        segmentos.append((f"Pedido: #{pedido_id}", "info"))

        # Waitress (only if the order comes from the waitstaff app via phone;
        # if it was taken directly at the central register, the notes do not mention her and
        # this line simply does not appear, without affecting anything else).
        mesera = self._mesera_de_pedido(pedido)
        if mesera:
            segmentos.append((f"Mesera: {mesera}", "info"))

        segmentos.append((f"Fecha: {datetime.now().strftime('%d-%m-%Y')}", "info"))
        segmentos.append((f"Hora: {datetime.now().strftime('%H:%M:%S')}", "info"))
        
        # Products
        segmentos.append(("-" * 40, "separador"))
        for prod in productos:
            cantidad = prod["cantidad"]
            nombre = self.limpiar_nombre_impresion(prod["nombre"])

            notas = prod["notas"]
            
            segmentos.append((f"{cantidad}x {nombre}", "producto"))
            if notas:
                segmentos.append((f"NOTA: {notas}", "nota"))
            # Space between products
            segmentos.append(("", "separador"))
        
        segmentos.append(("-" * 40, "separador"))
        
        return segmentos
    
    def _doble_para_estilo(self, estilo: str) -> Tuple[bool, bool]:
        """Returns (double_width, double_height) for each line style
        (does not include 'producto', which is handled separately in _imprimir_en_cocina)"""
        return {
            "separador": (False, False),
            "encabezado": self.config.doble_encabezado,
            "info": self.config.doble_info,
            "nota": self.config.doble_nota,
        }.get(estilo, (False, False))
    
    def _imprimir_en_cocina(self, contenido: Dict) -> bool:
        """
        Prints on the kitchen printer, with each section in its own
        font size (large/giant so it is easy to read).
        
        Uses the ESC ! command (double width/height) as a base because it is the most
        compatible across thermal printers. For the product line it
        also tries the GS ! command (free 1-8 multiplier) in case the
        printer supports it, for an even larger size.
        
        Args:
            contenido: dict with "texto" (plain) and "segmentos" (styled)
        
        Returns True if successful, False otherwise.
        """
        if Network is None:
            logger.warning("Librería escpos no disponible, simulando impresión")
            # In tests, log instead of printing
            logger.info(f"CONTENIDO DE IMPRESIÓN:\n{contenido['texto']}")
            return True
        
        cocina = None
        try:
            # Connect
            cocina = Network(
                self.config.ip_impresora,
                port=self.config.puerto,
                timeout=self.config.timeout
            )

            # Sound (beep) to alert
            try:
                cocina._raw(b'\x1b\x42\x09\x03')  # Beep
            except Exception:
                pass  # Not critical if it does not work
            
            # Print each line with the size that corresponds to it
            logger.info("SEGMENTOS A IMPRIMIR:")
            for s in contenido["segmentos"]:
                logger.info(s)
            for texto, estilo in contenido["segmentos"]:
                if estilo == "producto":
                    # --- Product line (quantity x name) ---
                    #
                    # SIZE 4 (ACTIVE): ESC! double width + double height.
                    # The most compatible, tested and working on the target printer.
                    try:
                        cocina.set(align="left", bold=True, double_width=True, double_height=True)
                    except Exception as e:
                        logger.warning(f"No se pudo aplicar tamaño 4 (ESC!) a producto: {e}")
                    
                    # SIZE 5 (COMMENTED OUT): GS! with free 3x3 multiplier.
                    # Already confirmed that the printer DOES support it and it is even
                    # bigger than size 4. To enable it: comment out the
                    # block above (SIZE 4) and uncomment this one below.
                    #
                    # try:
                    #     cocina.set(align="left", bold=True, custom_size=True, width=3, height=3)
                    # except Exception as e:
                    #     logger.warning(f"No se pudo aplicar tamaño 5 (GS!) a producto: {e}")
                    
                    cocina.text(texto + "\n")
                    continue
                
                doble_ancho, doble_alto = self._doble_para_estilo(estilo)
                
                try:
                    if doble_ancho or doble_alto:
                        cocina.set(
                            align="left",
                            bold=(estilo == "encabezado"),
                            double_width=doble_ancho,
                            double_height=doble_alto,
                        )
                    else:
                        cocina.set(align="left", bold=False, normal_textsize=True)
                except Exception as e:
                    logger.warning(f"No se pudo aplicar tamaño para '{estilo}': {e}")
                
                cocina.text(texto + "\n")
            
            # Back to normal size before cutting
            try:
                cocina.set(align="left", bold=False, normal_textsize=True)
            except Exception:
                pass
            
            # Sound (beep) to alert
            try:
                cocina._raw(b'\x1b\x42\x04\x01')  # Beep
            except Exception:
                pass  # Not critical if it does not work
            
            time.sleep(0.2)
            # Paper cut
            cocina.cut()
            
            logger.info("Comanda impresa exitosamente en cocina")
            return True
            
        except Exception as e:
            logger.error(f"Error de impresión: {e}")
            return False
        finally:
            # Always close the socket, or the printer stays "busy"
            # and the next connection times out (Device not found)
            if cocina is not None:
                try:
                    cocina.close()
                except Exception:
                    pass
    
    def _marcar_completado(
        self,
        trabajo_id: int,
        pedido_id: int,
        ronda: Optional[int],
        hash_comanda: str,
        contenido: str = ""
    ):
        """Marks a job as completed"""
        try:
            conn = sqlite3.connect(self.db_path)
            ahora = datetime.now().isoformat()
            
            # Update queue
            conn.execute(
                """UPDATE cola_impresion
                   SET estado = 'completado', fecha_procesamiento = ?
                   WHERE id = ?""",
                (ahora, trabajo_id)
            )
            
            # Record in completed prints (to avoid duplicates)
            conn.execute(
                """INSERT OR IGNORE INTO impresiones_realizadas
                   (pedido_id, ronda, hash_comanda, fecha_impresion, contenido)
                   VALUES (?, ?, ?, ?, ?)""",
                (pedido_id, ronda, hash_comanda, ahora, contenido)
            )
            
            conn.commit()
            conn.close()
            logger.info(f"Comanda {pedido_id} marcada como completada")
            
        except Exception as e:
            logger.error(f"Error marcando completado: {e}")
    
    def _reprogramar_trabajo(self, trabajo_id: int, nuevo_intento: int):
        """Reschedules a job to retry it"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "UPDATE cola_impresion SET intentos = ? WHERE id = ?",
                (nuevo_intento, trabajo_id)
            )
            conn.commit()
            conn.close()
            logger.info(f"Trabajo {trabajo_id} reprogramado para reintento {nuevo_intento}")
        except Exception as e:
            logger.error(f"Error reprogramando: {e}")
    
    def _marcar_error(self, trabajo_id: int, mensaje: str):
        """Marks a job as failed"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "UPDATE cola_impresion SET estado = 'error', error_mensaje = ? WHERE id = ?",
                (mensaje, trabajo_id)
            )
            conn.commit()
            conn.close()
            logger.error(f"Trabajo {trabajo_id} marcado con error: {mensaje}")
        except Exception as e:
            logger.error(f"Error marcando error: {e}")
    
    def agregar_comanda(
        self,
        pedido_id: int,
        ronda: Optional[int] = None,
        forzar: bool = False
    ) -> Tuple[bool, str]:
        """
        Adds an order to the print queue.
        
        Args:
            pedido_id: Order ID
            ronda: Round number (None = all rounds)
            forzar: If True, ignores whether it was already printed
        
        Returns: (success, message)
        """
        if len(self._cola) >= self.config.max_tamaño_cola:
            msg = "Cola de impresión llena"
            logger.warning(msg)
            return False, msg
        
        # Generate a hash to avoid duplicates
        hash_comanda = self._generar_hash(pedido_id, ronda)
        
        # Check whether it was already printed
        if not forzar and self._ya_fue_impresa(hash_comanda):
            msg = f"Comanda {pedido_id} ya fue impresa"
            logger.info(msg)
            return False, msg
        
        # Check whether it is already in the queue
        if any(t.get("hash") == hash_comanda for t in self._cola):
            msg = f"Comanda {pedido_id} ya está en la cola"
            logger.info(msg)
            return False, msg
        
        try:
            conn = sqlite3.connect(self.db_path)
            ahora = datetime.now().isoformat()
            
            # Insert into the queue
            cursor = conn.execute(
                """INSERT INTO cola_impresion
                   (pedido_id, ronda, estado, fecha_creacion, hash_comanda)
                   VALUES (?, ?, 'pendiente', ?, ?)""",
                (pedido_id, ronda, ahora, hash_comanda)
            )
            
            trabajo_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Add to the in-memory queue
            with self._lock:
                self._cola.append({
                    "id": trabajo_id,
                    "pedido_id": pedido_id,
                    "ronda": ronda,
                    "hash": hash_comanda,
                    "intentos": 0,
                })
            
            # Signal the executor
            self._evento_trabajo.set()
            
            msg = f"Comanda {pedido_id} agregada a la cola"
            logger.info(msg)
            return True, msg
            
        except sqlite3.IntegrityError:
            msg = f"Comanda {pedido_id} ya existe en la cola"
            logger.warning(msg)
            return False, msg
        except Exception as e:
            msg = f"Error agregando a cola: {e}"
            logger.error(msg)
            return False, msg
    
    def _generar_hash(self, pedido_id: int, ronda: Optional[int]) -> str:
        """Generates a unique hash to avoid duplicates"""
        import hashlib
        contenido = f"{pedido_id}:{ronda}".encode()
        return hashlib.md5(contenido).hexdigest()
    
    def _ya_fue_impresa(self, hash_comanda: str) -> bool:
        """Checks whether an order was already printed"""
        try:
            conn = sqlite3.connect(self.db_path)
            existe = conn.execute(
                "SELECT 1 FROM impresiones_realizadas WHERE hash_comanda = ?",
                (hash_comanda,)
            ).fetchone() is not None
            conn.close()
            return existe
        except Exception as e:
            logger.error(f"Error verificando impresión: {e}")
            return False
    
    def obtener_estado_cola(self) -> Dict:
        """Returns the current state of the queue"""
        return {
            "en_cola": len(self._cola),
            "activo": self._activo,
            "estadísticas": self.stats.copy(),
        }


# Global instance for ease of use
_instancia_global: Optional[ColaPrinter] = None


def inicializar(db_path: str, config: ConfiguracionImpresora = None):
    """Initializes the global printer queue"""
    global _instancia_global
    _instancia_global = ColaPrinter(db_path, config)
    _instancia_global.iniciar()
    return _instancia_global


def obtener_instancia() -> Optional[ColaPrinter]:
    """Gets the global instance"""
    return _instancia_global


def agregar_comanda_cocina(pedido_id: int, ronda: Optional[int] = None) -> Tuple[bool, str]:
    """Adds an order to the queue (simplified API)"""
    if _instancia_global is None:
        return False, "Impresora no inicializada"
    return _instancia_global.agregar_comanda(pedido_id, ronda)