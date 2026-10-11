"""
OWNER DASHBOARD Flask server — summary of the day, read-only.

It is a completely separate server from the waitstaff one:
- It runs on another port (PUERTO_DASHBOARD).
- It has its own password (DASHBOARD_PASSWORD), different from the waitstaff PIN.
- It exposes no route to create/edit orders or see the capture menu.
- Waitstaff never receive the URL of this server nor know its password.

It is designed to be exposed to the internet with Tailscale Funnel (free, no domain),
while the waitstaff port stays only on the local WiFi network.
"""

import threading
import sqlite3
import re
import hmac
import time

try:
    from flask import Flask, request, jsonify, session, redirect, url_for, send_file  # type: ignore[import]
except ImportError as e:
    raise ImportError(
        "Flask is required to run dashboard_server.py. Install it with 'pip install flask'"
    ) from e
from datetime import datetime, timedelta

from .config import get as _env
from modules.cierres_excel import ruta_excel_dia


# The real password lives in the .env file (key DASHBOARD_PASSWORD),
# next to the program. If that .env does not exist, this value is used as
# a fallback, but ideally it should ALWAYS be defined in the .env.
# 
# IMPORTANT: We do not assign it directly here because that would cause it to
# be loaded before config.py has read the .env correctly.
# Instead, we use a _obtener_password() function that reads it dynamically.

def _obtener_password():
    """Reads the password from the .env dynamically, not when the module starts."""
    return _env("DASHBOARD_PASSWORD")

PUERTO_DASHBOARD = 5051

# Key used to sign the session cookie. It is generated once and saved to
# disk so the session survives program restarts, so you do not have to
# log in again on the phone every time the PC is turned on.

import os as _os
from modules.rutas_base import carpeta_base as _carpeta_base
_SECRET_PATH = _os.path.join(_carpeta_base(), "data", ".dashboard_secret")


def _obtener_secret():
    if _os.path.exists(_SECRET_PATH):
        with open(_SECRET_PATH, "r") as f:
            return f.read().strip()
    _os.makedirs(_os.path.dirname(_SECRET_PATH), exist_ok=True)
    secret = _os.urandom(32).hex()
    with open(_SECRET_PATH, "w") as f:
        f.write(secret)
    return secret

HTML_DASHBOARD = r"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>Demo Restaurant — Resumen y Cierre de Caja</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #e0e0e0; min-height: 100vh; }
  .header { background: #16213e; padding: 14px 16px; display: flex; align-items: center; gap: 10px; border-bottom: 2px solid #e94560; position: sticky; top: 0; z-index: 100; }
  .header h1 { font-size: 17px; color: #e94560; flex: 1; }
  .btn-refresh { background: #34495e; color: white; border: none; border-radius: 8px; padding: 8px 12px; font-size: 13px; }
  .btn-logout { background: none; color: #a0a8c0; border: none; font-size: 13px; text-decoration: underline; }
  .login-box { max-width: 340px; margin: 60px auto; background: #16213e; border-radius: 12px; padding: 32px 24px; text-align: center; }
  .login-box h2 { color: #e94560; margin-bottom: 24px; font-size: 20px; }
  .login-box input { width: 100%; padding: 12px; background: #0f3460; color: white; border: none; border-radius: 8px; font-size: 16px; text-align: center; margin-bottom: 16px; }
  .btn-primary { width: 100%; padding: 13px; background: #e94560; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; }
  .err-msg { color: #e94560; font-size: 13px; margin-bottom: 12px; }
  .cards { display: flex; gap: 10px; padding: 10px 16px; flex-wrap: wrap; }
  .card { flex: 1; min-width: 120px; background: #16213e; border-radius: 10px; padding: 12px; text-align: center; }
  .card .lbl { font-size: 11px; color: #a0a8c0; text-transform: uppercase; }
  .card .val { font-size: 18px; font-weight: bold; color: #27ae60; margin-top: 4px; }
  .section-title { font-size: 12px; color: #e94560; font-weight: bold; padding: 14px 16px 6px; text-transform: uppercase; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid #0f3460; }
  th { color: #a0a8c0; font-size: 11px; text-transform: uppercase; }
  .tbl-wrap { margin: 0 16px 8px; background: #16213e; border-radius: 10px; overflow: hidden; }
  .footer-note { text-align: center; font-size: 11px; color: #555a75; padding: 20px 16px 40px; }
  .hidden { display: none !important; }
  .btn-descarga { display:block; width: calc(100% - 32px); margin: 4px 16px 12px; padding: 12px; background:#27ae60; color:white; border:none; border-radius:8px; font-size:14px; font-weight:bold; text-align:center; text-decoration:none; }
  .btn-descarga:active { opacity:0.85; }
  .alerta-banner { display:none; margin: 10px 16px; background:#c0392b; color:white; border-radius:10px; padding:12px 14px; font-size:13px; line-height:1.5; border:2px solid #e94560; animation: pulso 1.4s infinite; }
  .alerta-banner.show { display:block; }
  .alerta-banner b { display:block; font-size:14px; margin-bottom:4px; }
  @keyframes pulso { 0%,100% { box-shadow:0 0 0 0 rgba(233,69,96,0.5); } 50% { box-shadow:0 0 0 8px rgba(233,69,96,0); } }
  .badge-pendiente { background:#c0392b; color:white; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:bold; }
  .badge-ok { color:#a0a8c0; }
</style>
</head>
<body>

<div id="pag-login">
  <div class="login-box">
    <div style="font-size:44px;margin-bottom:10px">📊</div>
    <h2>Demo Restaurant<br><span style="font-size:14px;color:#a0a8c0">Dashboard Encargada</span></h2>
    <div id="err-login" class="err-msg hidden">Contraseña incorrecta</div>
    <input type="password" id="inp-pass" placeholder="Contraseña">
    <button class="btn-primary" id="btn-login">Entrar</button>
  </div>
</div>

<div id="pag-app" class="hidden">
  <div class="header">
    <h1>📊 Dashboard & Cierre de Caja</h1>
    <button class="btn-refresh" id="btn-refresh">🔄</button>
    <button class="btn-logout" id="btn-logout">Salir</button>
  </div>

  <div id="alerta-banner" class="alerta-banner"></div>

  <div class="cards">
    <div class="card"><div class="lbl">Pedidos hoy</div><div class="val" id="c-pedidos">—</div></div>
    <div class="card"><div class="lbl">Cerrados</div><div class="val" id="c-cerrados">—</div></div>
    <div class="card"><div class="lbl">Total Comandas</div><div class="val" id="c-total">—</div></div>
  </div>

  <div class="section-title">🔒 Desglose Cierre de Caja Registrado</div>
  <div class="cards" id="cards-cierre">
    <div class="card"><div class="lbl">1. Efectivo</div><div class="val" id="c-efectivo">—</div></div>
    <div class="card"><div class="lbl">2. Transferencias</div><div class="val" id="c-trans">—</div></div>
    <div class="card"><div class="lbl">3. Gastos</div><div class="val" id="c-gastos" style="color:#e67e22">—</div></div>
    <div class="card"><div class="lbl">4. Primicia</div><div class="val" id="c-primicia" style="color:#f1c40f">—</div></div>
  </div>
  <a href="#" class="btn-descarga" id="btn-descarga-excel">📥 Descargar Excel del cierre de hoy</a>
  <div id="lista-gastos-cierre" style="margin: -4px 16px 14px; font-size: 12px; color: #a0a8c0;"></div>

  <div class="section-title">🚫 Cancelaciones de hoy</div>
  <div class="tbl-wrap">
    <table>
      <thead><tr><th>Hora</th><th>Mesa</th><th>Total</th><th>Productos cancelados</th><th>Motivo</th></tr></thead>
      <tbody id="tbl-cancelaciones"></tbody>
    </table>
  </div>

  <div class="section-title">💸 Gastos Detallados del Día</div>
  <div class="tbl-wrap">
    <table>
      <thead><tr><th>Hora / Fecha</th><th>Motivo</th><th>Valor</th></tr></thead>
      <tbody id="tbl-gastos"></tbody>
    </table>
  </div>

  <div class="section-title">Pedidos de hoy</div>
  <div class="tbl-wrap">
    <table>
      <thead><tr><th>Mesa</th><th>Estado</th><th>Total</th><th>Pago</th><th>Hora</th></tr></thead>
      <tbody id="tbl-pedidos"></tbody>
    </table>
  </div>

  <div class="footer-note" id="ultima-act">Actualizado —</div>
</div>

<script>
(function() {
  function el(id) { return document.getElementById(id); }
  function show(id) { el(id).classList.remove('hidden'); }
  function hide(id) { el(id).classList.add('hidden'); }
  function fmt(n) { return '$' + Math.round(n || 0).toLocaleString('es-CO'); }
  function esc(s) {
    // Escapes any text that comes from data (table, reason, product...)
    // before inserting it with innerHTML, so that it is never interpreted as
    // HTML/JS even if the cashier typed something odd in a text field.
    var d = document.createElement('div');
    d.textContent = (s === null || s === undefined) ? '' : String(s);
    return d.innerHTML;
  }

  function iniciarSesionApp() {
    hide('pag-login');
    show('pag-app');
    if (window.Notification && Notification.permission === 'default') {
      Notification.requestPermission();
    }
    var hoy = new Date().toISOString().slice(0, 10);
    el('btn-descarga-excel').href = '/api/descargar-excel-dia?fecha=' + hoy;
    cargarResumen();
    revisarAlertas();
    setInterval(cargarResumen, 30000);
    setInterval(revisarAlertas, 30000);
  }

  function revisarAlertas() {
    fetch('/api/alertas').then(function(r) {
      if (r.status === 401) return null;
      return r.json();
    }).then(function(data) {
      if (!data || !data.alertas || !data.alertas.length) return;
      var banner = el('alerta-banner');
      data.alertas.forEach(function(a) {
        var linea = '<b>🚨 Cancelación sin justificar</b>Mesa ' + esc(a.mesa) +
          ' · ' + fmt(a.total) + ' · pedido #' + esc(a.pedido_id) +
          '<br><i>' + esc(a.resumen_productos || '') + '</i>' +
          ' — pasaron 10+ min sin motivo.';
        banner.innerHTML += '<div style="margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.3)">' + linea + '</div>';
        if (window.Notification && Notification.permission === 'granted') {
          new Notification('🚨 Cancelación sin justificar', {
            body: 'Mesa ' + a.mesa + ' · ' + fmt(a.total) + '\n' + (a.resumen_productos || ''),
          });
        }
      });
      banner.classList.add('show');
    }).catch(function() {});
  }

  function login() {
    var pass = el('inp-pass').value;
    fetch('/api/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({password: pass})
    }).then(function(r) { return r.json(); }).then(function(data) {
      if (data.ok) {
        iniciarSesionApp();
      } else {
        show('err-login');
        el('inp-pass').value = '';
      }
    });
  }
  el('btn-login').addEventListener('click', login);
  el('inp-pass').addEventListener('keydown', function(e) { if (e.key === 'Enter') login(); });
  el('btn-refresh').addEventListener('click', cargarResumen);
  el('btn-logout').addEventListener('click', function() {
    fetch('/api/logout', {method: 'POST'}).then(function() { location.reload(); });
  });

  function cargarResumen() {
    fetch('/api/resumen').then(function(r) {
      if (r.status === 401) { location.reload(); throw new Error('no-auth'); }
      return r.json();
    }).then(function(data) {
      el('c-pedidos').textContent = data.total_pedidos;
      el('c-cerrados').textContent = data.total_cerrados;
      el('c-total').textContent = fmt(data.total_cobrado);

      if (data.cierre_hoy) {
        el('c-efectivo').textContent = fmt(data.cierre_hoy.efectivo);
        el('c-trans').textContent = fmt(data.cierre_hoy.transferencias);
        el('c-gastos').textContent = fmt(data.cierre_hoy.gastos);
        el('c-primicia').textContent = fmt(data.cierre_hoy.primicia);
      } else {
        el('c-efectivo').textContent = "Sin cierre";
        el('c-trans').textContent = "Sin cierre";
        el('c-gastos').textContent = "Sin cierre";
        el('c-primicia').textContent = "Sin cierre";
      }

      var filasG = '';
      (data.gastos || []).forEach(function(g) {
        filasG += '<tr><td>' + esc(g.fecha) + '</td><td>' + esc(g.motivo) + '</td><td>' + fmt(g.valor) + '</td></tr>';
      });
      el('tbl-gastos').innerHTML = filasG || '<tr><td colspan="3" style="text-align:center;color:#a0a8c0">Sin gastos registrados hoy</td></tr>';

      var filasP = '';
      data.pedidos.forEach(function(p) {
        filasP += '<tr><td>' + esc(p.mesa) + '</td><td>' + esc(p.estado) + '</td><td>' + fmt(p.total) + '</td><td>' + esc(p.metodo_pago || '—') + '</td><td>' + esc(p.hora) + '</td></tr>';
      });
      el('tbl-pedidos').innerHTML = filasP || '<tr><td colspan="5" style="text-align:center;color:#a0a8c0">Sin pedidos aún</td></tr>';

      var filasC = '';
      (data.cancelaciones || []).forEach(function(c) {
        var hora = (c.fecha || '').replace('T', ' ').slice(11, 16);
        var motivoTxt = c.motivo && c.motivo.trim()
          ? esc(c.motivo)
          : '<span class="badge-pendiente">⏳ sin motivo</span>';
        var productosTxt = esc(c.resumen_productos || '—');
        filasC += '<tr><td>' + esc(hora) + '</td><td>' + esc(c.mesa) + '</td><td>' + fmt(c.total) + '</td><td>' + productosTxt + '</td><td>' + motivoTxt + '</td></tr>';
      });
      el('tbl-cancelaciones').innerHTML = filasC || '<tr><td colspan="5" style="text-align:center;color:#a0a8c0">Sin cancelaciones hoy</td></tr>';

      var listaGastos = el('lista-gastos-cierre');
      if (data.gastos && data.gastos.length) {
        listaGastos.innerHTML = '<b style="color:#e0e0e0">Desglose de gastos:</b><br>' +
          data.gastos.map(function(g) {
            return '• ' + esc(g.motivo) + ': ' + fmt(g.valor);
          }).join('<br>');
      } else {
        listaGastos.innerHTML = 'Sin gastos registrados hoy.';
      }

      el('ultima-act').textContent = 'Actualizado ' + new Date().toLocaleTimeString('es-CO');
    }).catch(function(err) {
      el('ultima-act').textContent = '⚠️ No se pudo cargar el resumen (revisa la consola / el servidor)';
      console.error('Error cargando /api/resumen:', err);
    });
  }

  fetch('/api/resumen').then(function(r) {
    if (r.ok) {
      iniciarSesionApp();
    }
  });
})();
</script>
</body>
</html>
"""


class DashboardServer:
    
    _MAX_INTENTOS = 5
    _BLOQUEO_SEGUNDOS = 15 * 60  # 15 minutes

    def __init__(self, db):
        self.db = db
        self.db_path = db.path
        self.app = Flask(__name__)
        self.app.config['JSON_AS_ASCII'] = False
        self.app.secret_key = _obtener_secret()
        self.app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
        self.app.config['SESSION_COOKIE_HTTPONLY'] = True

        if _env("DASHBOARD_COOKIE_SECURE", "0") == "1":
            self.app.config['SESSION_COOKIE_SECURE'] = True

        self._intentos_fallidos = {}  # ip -> [timestamps of recent failed attempts]

        self._registrar_rutas()
        self._thread = None
        self.activo = False

    def _ip_bloqueada(self, ip):
        ahora = time.time()
        intentos = [t for t in self._intentos_fallidos.get(ip, []) if ahora - t < self._BLOQUEO_SEGUNDOS]
        self._intentos_fallidos[ip] = intentos
        return len(intentos) >= self._MAX_INTENTOS

    def _registrar_intento_fallido(self, ip):
        self._intentos_fallidos.setdefault(ip, []).append(time.time())

    def _limpiar_intentos(self, ip):
        self._intentos_fallidos.pop(ip, None)

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _registrar_rutas(self):
        app = self.app

        @app.after_request
        def _cabeceras_seguridad(resp):
            resp.headers["X-Content-Type-Options"] = "nosniff"
            resp.headers["X-Frame-Options"] = "DENY"
            resp.headers["Referrer-Policy"] = "no-referrer"
            resp.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                "frame-ancestors 'none'; object-src 'none'"
            )
            return resp

        @app.route("/")
        def index():
            return HTML_DASHBOARD

        @app.route("/api/login", methods=["POST"])
        def api_login():
            ip = request.remote_addr or "desconocida"
            if self._ip_bloqueada(ip):
                return jsonify({
                    "ok": False,
                    "error": "Demasiados intentos fallidos. Espera unos minutos e intenta de nuevo."
                }), 429

            data = request.get_json(force=True, silent=True) or {}
            password_ingresada = str(data.get("password") or "")
            # Read the password DYNAMICALLY every time, do not use the global variable
            password_correcta = _obtener_password()

            if hmac.compare_digest(password_ingresada.encode("utf-8"),
                                    password_correcta.encode("utf-8")):
                self._limpiar_intentos(ip)
                session.permanent = True
                app.permanent_session_lifetime = timedelta(days=90)
                session["autenticado"] = True
                return jsonify({"ok": True})

            self._registrar_intento_fallido(ip)
            return jsonify({"ok": False}), 401

        @app.route("/api/logout", methods=["POST"])
        def api_logout():
            session.clear()
            return jsonify({"ok": True})

        @app.route("/api/resumen")
        def api_resumen():
            if not session.get("autenticado"):
                return jsonify({"error": "no autenticado"}), 401

            pedidos = self.db.get_pedidos_hoy()
            cerrados = [p for p in pedidos if p["estado"] == "cerrado"]
            gastos = [dict(g) for g in self.db.get_gastos_hoy()]
            cancelaciones = []
            for c in self.db.get_cancelaciones_hoy():
                c_dict = dict(c)
                c_dict["resumen_productos"] = self.db.resumen_detalle_cancelacion(c["detalle"])
                cancelaciones.append(c_dict)

            # LIVE calculation of the payment methods of closed orders
            efectivo_en_vivo = 0.0
            transferencias_en_vivo = 0.0
            for p in cerrados:
                metodo = (p["metodo_pago"] or "").lower()
                total = p["total"] or 0.0
                if "efectivo" in metodo:
                    efectivo_en_vivo += total
                else:
                    transferencias_en_vivo += total

            # Get the last official close if it has already been done
            hoy = datetime.now().strftime("%Y-%m-%d")
            conn = self._get_conn()
            cierre = conn.execute(
                "SELECT * FROM cierres_caja WHERE fecha LIKE ? ORDER BY id DESC LIMIT 1",
                (f"{hoy}%",)
            ).fetchone()
            conn.close()

            if cierre:
                # If the register has already been closed, show the frozen close data
                cierre_info = {
                    "efectivo": cierre["total_efectivo"],
                    "transferencias": cierre["total_transferencias"],
                    "gastos": cierre["total_gastos"],
                    "primicia": cierre["total_primicia"],
                    "oficial": True
                }
            else:
                # If the register has NOT been closed, show the running LIVE totals
                total_gastos_hoy = sum(g["valor"] for g in gastos)
                cierre_info = {
                    "efectivo": efectivo_en_vivo,
                    "transferencias": transferencias_en_vivo,
                    "gastos": total_gastos_hoy,
                    "primicia": cerrados[0]["total"] if cerrados else 0.0, # First sale as a provisional scoop
                    "oficial": False
                }

            out_pedidos = [{
                "mesa": p["mesa"],
                "estado": p["estado"],
                "total": p["total"] or 0,
                "metodo_pago": p["metodo_pago"],
                "hora": p["fecha_apertura"][11:16],
            } for p in pedidos]

            return jsonify({
                "total_pedidos": len(pedidos),
                "total_cerrados": len(cerrados),
                "total_cobrado": sum(p["total"] or 0 for p in cerrados),
                "pedidos": out_pedidos,
                "gastos": gastos,
                "cancelaciones": cancelaciones,
                "cierre_hoy": cierre_info,
            })

        @app.route("/api/alertas")
        def api_alertas():
            """
            Cancellations that have gone 10+ minutes without a reason. Each one is
            returned ONLY once (it is marked as notified when read), so the
            same alert is not repeated on every 30s refresh.
            """
            if not session.get("autenticado"):
                return jsonify({"error": "no autenticado"}), 401

            pendientes = self.db.get_cancelaciones_pendientes_alerta(minutos=10)
            alertas = []
            for c in pendientes:
                alertas.append({
                    "id": c["id"],
                    "pedido_id": c["pedido_id"],
                    "mesa": c["mesa"],
                    "total": c["total"] or 0,
                    "fecha": c["fecha"],
                    "resumen_productos": self.db.resumen_detalle_cancelacion(c["detalle"]),
                })
                self.db.marcar_cancelacion_notificada(c["id"])
            return jsonify({"alertas": alertas})

        @app.route("/api/descargar-excel-dia")
        def api_descargar_excel_dia():
            """
            Downloads the detailed Excel of a day's close (today by default).
            That file is generated automatically by reportes.py when the
            Cash Close is done; here it is only served for download.
            """
            if not session.get("autenticado"):
                return jsonify({"error": "no autenticado"}), 401

            fecha = request.args.get("fecha") or datetime.now().strftime("%Y-%m-%d")

            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
                return jsonify({"error": "Formato de fecha inválido, debe ser AAAA-MM-DD."}), 400

            ruta = ruta_excel_dia(fecha)
            if not _os.path.exists(ruta):
                return jsonify({
                    "error": f"Aún no hay Excel generado para {fecha}. "
                             f"Se crea automáticamente al hacer el Cierre de Caja de ese día."
                }), 404
            return send_file(ruta, as_attachment=True,
                              download_name=_os.path.basename(ruta))

    def iniciar(self):
        if self.activo:
            return
        self.activo = True

        if _obtener_password() == "cambia_esta_contraseña":
            print("\n" + "=" * 64)
            print("⚠️  ADVERTENCIA DE SEGURIDAD — DASHBOARD_PASSWORD")
            print("El dashboard remoto sigue usando la contraseña de fábrica.")
            print("Si lo vas a exponer a internet (Tailscale Funnel u otro),")
            print("cambia DASHBOARD_PASSWORD en el archivo .env ANTES de eso.")
            print("=" * 64 + "\n")

        self._thread = threading.Thread(
            target=lambda: self.app.run(
                host="0.0.0.0", port=PUERTO_DASHBOARD, debug=False, use_reloader=False
            ),
            daemon=True
        )
        self._thread.start()

    def detener(self):
        self.activo = False