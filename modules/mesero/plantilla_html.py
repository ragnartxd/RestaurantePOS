"""
Improved HTML template with:
- Login with waitress name
- History section of the last 3 orders
- Dynamic comments per category
"""

HTML_MESERO = r"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>Demo Restaurant — Comanda</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #e0e0e0; min-height: 100vh; }
  .header { background: #16213e; padding: 14px 16px; display: flex; align-items: center; gap: 10px; border-bottom: 2px solid #e94560; position: sticky; top: 0; z-index: 100; }
  .header h1 { font-size: 18px; color: #e94560; }
  .header-info { margin-left: auto; display: flex; gap: 10px; align-items: center; }
  .mesera-name { font-size: 12px; color: #a0a8c0; }
  .btn-historial { background: #f39c12; color: white; border: none; border-radius: 6px; padding: 6px 12px; font-size: 12px; cursor: pointer; font-weight: bold; }
  .mesa-badge { background: #e94560; color: white; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: bold; cursor: pointer; }
  .login-box { max-width: 340px; margin: 60px auto; background: #16213e; border-radius: 12px; padding: 32px 24px; text-align: center; }
  .login-box h2 { color: #e94560; margin-bottom: 24px; font-size: 22px; }
  .login-box input { width: 100%; padding: 12px; background: #0f3460; color: white; border: none; border-radius: 8px; font-size: 15px; margin-bottom: 16px; }
  .login-box input[type="password"] { font-size: 18px; letter-spacing: 8px; text-align: center; }
  .btn-primary { width: 100%; padding: 13px; background: #e94560; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; }
  .err-msg { color: #e94560; font-size: 13px; margin-bottom: 12px; display: none; }
  .section { padding: 14px 16px; }
  .section label { display: block; margin-bottom: 6px; color: #a0a8c0; font-size: 13px; }
  .section input, .section textarea { width: 100%; padding: 11px; background: #0f3460; color: white; border: none; border-radius: 8px; font-size: 15px; }
  .section textarea { resize: none; height: 64px; font-family: inherit; }
  .mesas-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; padding: 6px 16px 24px; }
  .mesa-cell { aspect-ratio: 1; border: none; border-radius: 12px; color: white; font-family: inherit; display: flex; flex-direction: column; align-items: center; justify-content: center; cursor: pointer; }
  .mesa-cell .mesa-num { font-size: 26px; font-weight: bold; }
  .mesa-cell .mesa-estado { font-size: 11px; margin-top: 4px; opacity: .9; }
  .mesa-cell.libre { background: #27ae60; }
  .mesa-cell.atendida { background: #f39c12; }
  .mesa-tiempo { font-size: 11px; margin-top: 2px; background: rgba(0,0,0,.2); padding: 1px 8px; border-radius: 10px; }
  .mesa-tiempo.alerta { background: #e94560; font-weight: bold; }
  .cats { display: flex; gap: 8px; overflow-x: auto; padding: 10px 16px; scrollbar-width: none; }
  .cats::-webkit-scrollbar { display: none; }
  .cat-btn { white-space: nowrap; padding: 8px 16px; background: #16213e; color: #a0a8c0; border: 1px solid #2a2a4e; border-radius: 20px; font-size: 13px; cursor: pointer; flex-shrink: 0; }
  .cat-btn.active { background: #e94560; color: white; border-color: #e94560; }
  .search-bar { padding: 8px 16px; }
  .search-bar input { width: 100%; padding: 10px; background: #0f3460; color: white; border: none; border-radius: 8px; font-size: 14px; }
  .productos { padding: 0 16px 300px; display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .prod-card { background: #16213e; border-radius: 10px; padding: 12px 14px; display: flex; flex-direction: column; align-items: flex-start; gap: 4px; cursor: pointer; border: 1px solid transparent; }
  .prod-card.selected { border-color: #e94560; }
  .prod-card.grupo { border-left: 3px solid #f39c12; }
  .prod-name { font-size: 14px; font-weight: 600; }
  .prod-price { color: #27ae60; font-size: 13px; font-weight: bold; }
  .prod-desc { font-size: 11px; color: #a0a8c0; }
  .prod-qty { color: #e94560; }
  .prod-variante { font-size: 11px; color: #f39c12; }
  .fab-carrito { position: fixed; bottom: 24px; right: 20px; z-index: 200; background: #e94560; color: white; border: none; border-radius: 50px; padding: 14px 20px; font-size: 15px; font-weight: bold; cursor: pointer; display: flex; align-items: center; gap: 10px; box-shadow: 0 4px 16px rgba(0,0,0,.5); transition: transform .15s; }
  .fab-carrito:active { transform: scale(.95); }
  .fab-badge { background: white; color: #e94560; border-radius: 50%; width: 22px; height: 22px; font-size: 12px; font-weight: bold; display: flex; align-items: center; justify-content: center; }
  .ticket-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.6); z-index: 300; display: none; }
  .ticket-overlay.abierto { display: block; }
  .ticket-bar { position: fixed; bottom: 0; left: 0; right: 0; background: #0f3460; border-top: 2px solid #e94560; padding: 10px 16px; z-index: 301; max-height: 75vh; display: flex; flex-direction: column; transform: translateY(100%); transition: transform .25s ease; }
  .ticket-bar.abierto { transform: translateY(0); }
  .ticket-handle { width: 40px; height: 4px; background: #a0a8c0; border-radius: 2px; margin: 0 auto 10px; flex-shrink: 0; }
  .ticket-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-shrink: 0; }
  .ticket-total { font-size: 16px; font-weight: bold; color: #e94560; }
  .ticket-aviso-bebida {
  background: rgba(243,156,18,.15);
  border: 1px solid #f39c12;
  color: #f39c12;
  font-size: 12px;
  padding: 8px 10px;
  border-radius: 8px;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-shrink: 0;
}

.btn-ir-bebidas {
  background: #f39c12;
  color: white;
  border: none;
  border-radius: 14px;
  padding: 5px 10px;
  font-size: 11px;
  font-weight: bold;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
}
  .btn-ir-bebidas { background: #f39c12; color: white; border: none; border-radius: 14px; padding: 5px 10px; font-size: 11px; font-weight: bold; cursor: pointer; white-space: nowrap; flex-shrink: 0; }
  .ticket-lista { overflow-y: auto; flex: 1; margin-bottom: 8px; }
  .ticket-item { display: flex; align-items: center; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #1a1a3e; font-size: 13px; }
  .ticket-item-info { flex: 1; min-width: 0; }
  .ticket-item-nombre { font-weight: 600; white-space: normal; word-break: break-word; }
  .ticket-item-precio { color: #27ae60; font-size: 12px; }
  .ticket-item-nota { color: #f39c12; font-size: 11px; font-style: italic; white-space: normal; word-break: break-word; }
  .ticket-item-comentar { color: #a0a8c0; font-size: 11px; margin-top: 3px; cursor: pointer; text-decoration: underline; }
  .ticket-item-ctrl { display: flex; align-items: center; gap: 8px; margin: 0 10px; flex-shrink: 0; }
  .t-btn { width: 28px; height: 28px; background: #16213e; color: white; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-weight: bold; }
  .t-del { width: 28px; height: 28px; background: #c0392b; color: white; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .btn-enviar { width: 100%; padding: 13px; background: #27ae60; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; flex-shrink: 0; }
  .btn-enviar:disabled { background: #4a4a4a; cursor: default; }
  .ticket-vacio { color: #a0a8c0; font-size: 13px; text-align: center; padding: 8px 0; }
  .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.75); z-index: 400; display: flex; align-items: center; justify-content: center; }
  .modal { background: #16213e; border-radius: 14px; padding: 24px; width: 300px; text-align: center; max-height: 80vh; overflow-y: auto; }
  .modal h3 { color: #e94560; margin-bottom: 8px; }
  .modal-precio { color: #27ae60; font-size: 14px; margin-bottom: 14px; }
  .qty-ctrl { display: flex; align-items: center; justify-content: center; gap: 24px; margin: 12px 0 16px; }
  .qty-btn { width: 48px; height: 48px; background: #0f3460; color: white; border: none; border-radius: 10px; font-size: 26px; cursor: pointer; }
  .qty-num { font-size: 32px; font-weight: bold; min-width: 40px; }
  .modal-btns { display: flex; gap: 10px; }
  .btn-cancel-modal { flex: 1; padding: 12px; background: #7f8c8d; color: white; border: none; border-radius: 8px; font-size: 14px; cursor: pointer; }
  .btn-add-modal { flex: 2; padding: 12px; background: #e94560; color: white; border: none; border-radius: 8px; font-size: 15px; font-weight: bold; cursor: pointer; }
  .btn-opcion-mesa { width: 100%; padding: 14px; border: none; border-radius: 10px; font-size: 15px; font-weight: bold; cursor: pointer; text-align: left; }
  .btn-opcion-mesa.continuar { background: #0f3460; color: #f1c40f; }
  .btn-opcion-mesa.nueva { background: #27ae60; color: white; }
  .btn-opcion-mesa small { display: block; font-weight: normal; font-size: 11px; opacity: .8; margin-top: 2px; }
  .variante-btn { width: 100%; padding: 13px; background: #0f3460; color: white; border: none; border-radius: 8px; font-size: 15px; font-weight: bold; cursor: pointer; margin-bottom: 8px; }
  .variante-btn:hover { background: #e94560; }
  .modal textarea { width: 100%; padding: 10px; background: #0f3460; color: white; border: none; border-radius: 8px; font-size: 14px; resize: none; height: 70px; font-family: inherit; margin-bottom: 12px; }
  .chips-rapidos { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; text-align: left; }
  .chip-rapido { padding: 6px 12px; background: #0f3460; color: #e0e0e0; border: 1px solid #2a2a4e; border-radius: 16px; font-size: 12px; cursor: pointer; }
  .chip-rapido:active { background: #e94560; border-color: #e94560; }
  .btn-lupa { background: none; border: none; color: #a0a8c0; font-size: 20px; cursor: pointer; padding: 4px 8px; line-height: 1; }
  .btn-lupa.activa { color: #e94560; }
  .search-bar { padding: 0 16px; overflow: hidden; max-height: 0; transition: max-height .2s ease, padding .2s ease; }
  .search-bar.visible { max-height: 60px; padding: 8px 16px; }
  .hidden { display: none !important; }
  
  /* Styles for order history */
  .historial-panel { position: fixed; bottom: 0; left: 0; right: 0; background: #0f3460; border-top: 2px solid #27ae60; padding: 10px 16px; z-index: 301; max-height: 75vh; display: flex; flex-direction: column; transform: translateY(100%); transition: transform .25s ease; }
  .historial-panel.abierto { transform: translateY(0); }
  .historial-handle { width: 40px; height: 4px; background: #a0a8c0; border-radius: 2px; margin: 0 auto 10px; flex-shrink: 0; }
  .historial-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-shrink: 0; }
  .historial-header h3 { color: #27ae60; font-size: 16px; }
  .btn-cerrar-historial { background: #7f8c8d; color: white; border: none; border-radius: 6px; padding: 6px 12px; cursor: pointer; font-size: 12px; }
  .historial-lista { overflow-y: auto; flex: 1; }
  .historial-item { background: #16213e; border: 1px solid #2a2a4e; border-radius: 8px; padding: 10px; margin-bottom: 8px; }
  .historial-item-header { display: flex; justify-content: space-between; margin-bottom: 6px; }
  .historial-mesa { font-weight: bold; color: #e94560; }
  .historial-fecha { font-size: 11px; color: #a0a8c0; }
  .historial-total { color: #27ae60; font-weight: bold; }
  .historial-linea { font-size: 12px; padding: 4px 0; color: #e0e0e0; }
  .historial-linea-cant { color: #f39c12; margin-right: 6px; }
  .historial-linea-nota { color: #a0a8c0; font-style: italic; margin-left: 4px; }
</style>
</head>
<body>

<div id="pag-login">
  <div class="login-box">
    <div style="font-size:48px;margin-bottom:12px">&#127869;</div>
    <h2>Demo Restaurant<br><span style="font-size:15px;color:#a0a8c0">Comandas</span></h2>
    <input type="text" id="inp-nombre-mesera" placeholder="Tu nombre" maxlength="30">
    <input type="password" id="inp-pin" placeholder="PIN" inputmode="numeric" maxlength="8">
    <div id="err-pin" class="err-msg">Error en login</div>
    <button class="btn-primary" id="btn-login">Entrar</button>
  </div>
</div>

<div id="pag-mesas" class="hidden">
  <div class="header">
    <span style="font-size:22px">&#127869;</span>
    <h1>Demo Restaurant</h1>
    <div class="header-info">
      <span class="mesera-name" id="header-mesera"></span>
      <button class="btn-historial" id="btn-ver-historial">📋 Historial</button>
    </div>
  </div>
  <div class="section">
    <label>Toca una mesa para tomar el pedido</label>
  </div>
  <div class="mesas-grid" id="mesas-grid"></div>
  <div class="section">
    <button class="btn-primary" id="btn-otra-mesa" style="background:#0f3460">Otra mesa / Barra</button>
  </div>
</div>

<div id="pag-app" class="hidden">
  <div class="header">
    <span style="font-size:22px">&#127869;</span>
    <h1>Demo Restaurant</h1>
    <div class="header-info">
      <span class="mesera-name" id="header-mesera-app"></span>
      <button class="btn-lupa" id="btn-lupa" title="Buscar">🔍</button>
      <button class="btn-historial" id="btn-ver-historial-app">📋</button>
      <span class="mesa-badge" id="badge-mesa">Sin mesa</span>
    </div>
  </div>
  <div class="section">
    <label>Mesa / Cliente</label>
    <input type="text" id="inp-mesa" placeholder="Ej: Mesa 3, Barra...">
  </div>
  <div class="search-bar" id="search-bar">
    <input type="text" id="inp-buscar" placeholder="Buscar producto...">
  </div>
  <div class="cats" id="lista-cats"></div>
  <div class="productos" id="lista-prods"></div>

  <button class="fab-carrito hidden" id="fab-carrito">
    <span>🛒</span>
    <span id="fab-total">$0</span>
    <span class="fab-badge" id="fab-count">0</span>
  </button>

  <div class="ticket-overlay" id="ticket-overlay"></div>

  <div class="ticket-bar" id="ticket-bar">
    <div class="ticket-handle"></div>
    <div class="ticket-header">
      <span style="font-size:13px;color:#a0a8c0" id="ticket-count">Carrito vacío</span>
      <span class="ticket-total" id="ticket-total">$0</span>
    </div>
    <div class="ticket-aviso-bebida hidden" id="ticket-aviso-bebida">
      <span>&#9888; Este pedido no lleva bebidas</span>
      <button type="button" class="btn-ir-bebidas" id="btn-ir-bebidas">Ver bebidas</button>
    </div>
    <div class="ticket-lista" id="ticket-lista">
      <div class="ticket-vacio">Agrega productos tocándolos</div>
    </div>
    <button class="btn-enviar" id="btn-enviar" disabled>Enviar Comanda a Caja</button>
  </div>
</div>

<!-- Order history panel -->
<div class="ticket-overlay" id="historial-overlay"></div>
<div class="historial-panel" id="historial-panel">
  <div class="historial-handle"></div>
  <div class="historial-header">
    <h3>Tus últimas comandas</h3>
    <button class="btn-cerrar-historial" id="btn-cerrar-historial">✕ Cerrar</button>
  </div>
  <div class="historial-lista" id="historial-lista">
    <div style="text-align:center;color:#a0a8c0;padding:20px">Cargando...</div>
  </div>
</div>

<!-- Quantity modal (simple products) -->
<div class="modal-overlay hidden" id="modal">
  <div class="modal">
    <h3 id="modal-nombre">Producto</h3>
    <div class="modal-precio" id="modal-precio"></div>
    <div class="qty-ctrl">
      <button class="qty-btn" id="btn-menos">&#8722;</button>
      <span class="qty-num" id="modal-qty">1</span>
      <button class="qty-btn" id="btn-mas">&#43;</button>
    </div>
    <div class="modal-btns">
      <button class="btn-cancel-modal" id="btn-modal-cancel">Cancelar</button>
      <button class="btn-add-modal" id="btn-modal-ok">Agregar</button>
    </div>
  </div>
</div>

<!-- Modal: table already has an open order -->
<div class="modal-overlay hidden" id="modal-mesa-ocupada">
  <div class="modal">
    <h3 id="mo-titulo">Mesa ocupada</h3>
    <p style="color:#a0a8c0; font-size:13px; margin-bottom:16px;">
      Ya hay un pedido abierto en esta mesa. ¿Qué quieres hacer?
    </p>
    <div id="mo-opciones" style="display:flex; flex-direction:column; gap:10px;"></div>
    <button class="btn-cancel-modal" style="width:100%;margin-top:14px" id="mo-cancel">Cancelar</button>
  </div>
</div>

<!-- Variant modal -->
<div class="modal-overlay hidden" id="modal-variante">
  <div class="modal">
    <h3 id="mv-nombre"></h3>
    <div class="modal-precio" id="mv-precio"></div>
    <div id="mv-variantes"></div>
    <button class="btn-cancel-modal" style="width:100%;margin-top:4px" id="mv-cancel">Cancelar</button>
  </div>
</div>

<!-- Quantity modal for variant -->
<div class="modal-overlay hidden" id="modal-comentario-v">
  <div class="modal">
    <h3 id="mcv-nombre" style="font-size:14px;margin-bottom:8px"></h3>
    <div class="qty-ctrl">
      <button class="qty-btn" id="mcv-menos">&#8722;</button>
      <span class="qty-num" id="mcv-qty">1</span>
      <button class="qty-btn" id="mcv-mas">&#43;</button>
    </div>
    <div class="modal-btns">
      <button class="btn-cancel-modal" id="mcv-cancel">Cancelar</button>
      <button class="btn-add-modal" id="mcv-ok">Agregar</button>
    </div>
  </div>
</div>

<!-- Comment for a product -->
<div class="modal-overlay hidden" id="modal-comentario-carrito">
  <div class="modal">
    <h3 id="mcc-nombre" style="font-size:15px;margin-bottom:10px"></h3>
    <div class="chips-rapidos" id="mcc-chips"></div>
    <textarea id="mcc-texto" placeholder="Comentario (ej: sin cebolla)..."></textarea>
    <div class="modal-btns">
      <button class="btn-cancel-modal" id="mcc-cancel">Cancelar</button>
      <button class="btn-add-modal" id="mcc-ok">Guardar</button>
    </div>
  </div>
</div>


<script src="/static/app.js"></script>
</body>
</html>
"""