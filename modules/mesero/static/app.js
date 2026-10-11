(function() {
  function fmt(n) { return '$' + Math.round(n).toLocaleString('es-CO'); }
  function el(id) { return document.getElementById(id); }
  function show(id) { el(id).classList.remove('hidden'); }
  function hide(id) { el(id).classList.add('hidden'); }

  var menu = [];
  var grupos = {};
  var carrito = {};
  var catActiva = '';
  var prodModal = null;
  var qtyModal = 1;
  var grupoModal = null;
  var varianteElegida = null;
  var qtyVariante = 1;
  var comentariosDinamicos = {};
  var nombreMeseraActual = '';
  var comentariosPorProducto = {};

  fetch('/api/mesas')
  .then(function(r){
      if(r.status === 401){
          show('pag-login');
          return null;
      }

      hide('pag-login');
      cargarMenu();
      mostrarPagMesas();
      return r.json();
  })
  .catch(function(){
      show('pag-login');
  });

  // ── LOGIN ──────────────────────────────────────────────────
  function login() {
    var pin = el('inp-pin').value.trim();
    var nombre = el('inp-nombre-mesera').value.trim();
    el('btn-login').disabled = true;
    
    if (!nombre) {
      el('err-pin').textContent = 'Ingresa tu nombre';
      el('err-pin').style.display = 'block';
      el('btn-login').disabled = false;
      return;
    }

    fetch('/api/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({pin: pin, nombre_mesera: nombre})
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.ok) {
          nombreMeseraActual = data.nombre_mesera;
          el('err-pin').style.display = 'none';
          hide('pag-login');
          cargarMenu();
          mostrarPagMesas();
          actualizarNombreMesera();
        } else {
          el('err-pin').textContent = data.error || 'Error en login';
          el('err-pin').style.display = 'block';
          el('inp-pin').value = '';
        }
      })
      .catch(function() {
        el('err-pin').textContent = 'No se pudo conectar con el servidor';
        el('err-pin').style.display = 'block';
      })
      .finally(function() {
        el('btn-login').disabled = false;
      });
  }

  function actualizarNombreMesera() {
    var elementos = document.querySelectorAll('[id$="-mesera"]');
    elementos.forEach(function(e) {
      e.textContent = 'Mesera: ' + nombreMeseraActual;
    });
  }

  el('btn-login').addEventListener('click', login);
  el('inp-pin').addEventListener('keydown', function(e) { if (e.key === 'Enter') login(); });
  el('inp-nombre-mesera').addEventListener('keydown', function(e) { if (e.key === 'Enter') login(); });

  function sesionExpirada() {
    hide('pag-mesas');
    hide('pag-app');
    show('pag-login');
    el('err-pin').textContent = 'Sesión expirada, ingresa el PIN otra vez.';
    el('err-pin').style.display = 'block';
    el('inp-pin').value = '';
    el('inp-nombre-mesera').value = '';
  }

  // ── TABLES SCREEN ─────────────────────────────────────────
  var intervaloMesas = null;
  function mostrarPagMesas() {
    hide('pag-app');
    show('pag-mesas');
    cargarMesas();
    if (intervaloMesas) clearInterval(intervaloMesas);
    intervaloMesas = setInterval(cargarMesas, 30000);
  }

  function cargarMesas() {
    fetch('/api/mesas')
      .then(function(r) {
        if (r.status === 401) { sesionExpirada(); return null; }
        return r.json();
      })
      .then(function(data) {
        if (!data) return;
        renderMesas(data.mesas || []);
      })
      .catch(function() {
        el('mesas-grid').innerHTML = '<p style="color:#e94560;text-align:center;grid-column:1/-1">Error cargando mesas</p>';
      });
  }

  function formatTiempoMesa(min) {
    if (min == null) return '';
    if (min < 1) return 'Recién';
    if (min < 60) return min + ' min';
    var h = Math.floor(min / 60), m = min % 60;
    return h + 'h' + (m ? ' ' + m + 'min' : '');
  }

  function renderMesas(mesas) {
    var html = '';
    mesas.forEach(function(m) {
      var clase = m.atendida ? 'atendida' : 'libre';
      var texto = m.atendida ? 'En atención' : 'Libre';
      var tiempoHtml = '';
      if (m.atendida && m.minutos != null) {
        var claseTiempo = 'mesa-tiempo' + (m.minutos >= 30 ? ' alerta' : '');
        tiempoHtml = '<span class="' + claseTiempo + '">' + formatTiempoMesa(m.minutos) + '</span>';
      }
      html += '<button type="button" class="mesa-cell ' + clase + '" data-n="' + m.numero + '" data-atendida="' + (m.atendida ? '1' : '0') + '">' +
                '<span class="mesa-num">' + m.numero + '</span>' +
                '<span class="mesa-estado">' + texto + '</span>' +
                tiempoHtml +
              '</button>';
    });
    el('mesas-grid').innerHTML = html;
    el('mesas-grid').querySelectorAll('.mesa-cell').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var numero = this.getAttribute('data-n');
        var atendida = this.getAttribute('data-atendida') === '1';
        if (atendida) {
          abrirModalMesaOcupada(numero);
        } else {
          seleccionarMesa('Mesa ' + numero);
        }
      });
    });
  }

  // ── Table already occupied: ask "current order" or "new table" ──
  function abrirModalMesaOcupada(numero) {
    fetch('/api/mesa-variantes?numero=' + encodeURIComponent(numero))
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (!data.ok) {
          // If the lookup fails, we do not block the waitress: we continue
          // with the previous behavior (add a round to "Mesa N").
          seleccionarMesa('Mesa ' + numero);
          return;
        }
        var opciones = '';
        data.variantes.forEach(function(v) {
          opciones += '<button type="button" class="btn-opcion-mesa continuar" data-mesa="' +
            v.mesa.replace(/"/g, '&quot;') + '">▶ Continuar pedido<small>' + v.mesa + '</small></button>';
        });
        opciones += '<button type="button" class="btn-opcion-mesa nueva" data-mesa="' +
          data.siguiente.replace(/"/g, '&quot;') + '">🆕 Nueva mesa<small>Se abrirá como "' + data.siguiente + '"</small></button>';

        el('mo-titulo').textContent = 'Mesa ' + numero + ' ya tiene pedido';
        el('mo-opciones').innerHTML = opciones;
        el('mo-opciones').querySelectorAll('.btn-opcion-mesa').forEach(function(btn) {
          btn.addEventListener('click', function() {
            var mesaElegida = this.getAttribute('data-mesa');
            hide('modal-mesa-ocupada');
            seleccionarMesa(mesaElegida);
          });
        });
        show('modal-mesa-ocupada');
      })
      .catch(function() {
        seleccionarMesa('Mesa ' + numero);
      });
  }
  el('mo-cancel').addEventListener('click', function() { hide('modal-mesa-ocupada'); });
  el('modal-mesa-ocupada').addEventListener('click', function(e) {
    if (e.target === el('modal-mesa-ocupada')) hide('modal-mesa-ocupada');
  });

  function seleccionarMesa(nombreMesa) {
    if (intervaloMesas) { clearInterval(intervaloMesas); intervaloMesas = null; }
    el('inp-mesa').value = nombreMesa;
    el('badge-mesa').textContent = nombreMesa || 'Sin mesa';
    hide('pag-mesas');
    show('pag-app');
  }

  el('btn-otra-mesa').addEventListener('click', function() {
    seleccionarMesa('');
    el('inp-mesa').focus();
  });
  el('badge-mesa').addEventListener('click', mostrarPagMesas);

  // ── ORDER HISTORY ─────────────────────────────────────────
  function abrirHistorial() {
    el('historial-overlay').classList.add('abierto');
    el('historial-panel').classList.add('abierto');
    cargarHistorial();
  }

  function cerrarHistorial() {
    el('historial-overlay').classList.remove('abierto');
    el('historial-panel').classList.remove('abierto');
  }

  function cargarHistorial() {
    el('historial-lista').innerHTML = '<div style="text-align:center;color:#a0a8c0;padding:20px">Cargando...</div>';
    
    fetch('/api/historial-comandas')
      .then(function(r) {
        if (r.status === 401) { sesionExpirada(); return null; }
        return r.json();
      })
      .then(function(data) {
        if (!data || !data.ok) {
          el('historial-lista').innerHTML = '<div style="color:#e94560;text-align:center;padding:20px">Error al cargar historial</div>';
          return;
        }
        renderHistorial(data.comandas || []);
      })
      .catch(function() {
        el('historial-lista').innerHTML = '<div style="color:#e94560;text-align:center;padding:20px">Error de conexión</div>';
      });
  }

  function renderHistorial(comandas) {
    if (!comandas.length) {
      el('historial-lista').innerHTML = '<div style="color:#a0a8c0;text-align:center;padding:20px">No hay comandas anteriores</div>';
      return;
    }

    var html = '';
    comandas.forEach(function(cmd) {
      var fecha = new Date(cmd.fecha);
      var fechaStr = fecha.toLocaleDateString('es-CO') + ' ' + fecha.toLocaleTimeString('es-CO', {hour: '2-digit', minute: '2-digit'});
      
      html += '<div class="historial-item">' +
                '<div class="historial-item-header">' +
                  '<div><span class="historial-mesa">' + cmd.mesa + '</span></div>' +
                  '<div><span class="historial-fecha">' + fechaStr + '</span></div>' +
                  '<div class="historial-total">' + fmt(cmd.total) + '</div>' +
                '</div>';
      
      cmd.items.forEach(function(item) {
        var nota = item.comentario ? ' — <span class="historial-linea-nota">' + item.comentario + '</span>' : '';
        html += '<div class="historial-linea">' +
                  '<span class="historial-linea-cant">x' + item.cantidad + '</span>' +
                  item.nombre +
                  nota +
                '</div>';
      });
      
      html += '</div>';
    });

    el('historial-lista').innerHTML = html;
  }

  // Buttons to view history
  if (el('btn-ver-historial')) {
    el('btn-ver-historial').addEventListener('click', abrirHistorial);
  }
  if (el('btn-ver-historial-app')) {
    el('btn-ver-historial-app').addEventListener('click', abrirHistorial);
  }
  el('btn-cerrar-historial').addEventListener('click', cerrarHistorial);
  el('historial-overlay').addEventListener('click', cerrarHistorial);

  // ── MENU ───────────────────────────────────────────────────
  function normalizarTexto(txt) {
    return txt
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g,"");
  }

  var categoriasCargadas = [];
  function cargarMenu() {
    fetch('/api/menu')
      .then(function(r) {
        if (r.status === 401) { sesionExpirada(); return null; }
        return r.json();
      })
      .then(function(data) {
        if (!data) return;
        menu = data.productos;
        grupos = data.grupos || {};
        categoriasCargadas = data.categorias || [];
        comentariosDinamicos = data.comentarios_dinamicos || {};
        
        // Build a map of comments per product
        construirComentariosPorProducto();
        
        renderCats(data.categorias);
        var primerBtn = el('lista-cats').querySelector('.cat-btn');
        if (primerBtn) {
          catActiva = primerBtn.getAttribute('data-cat');
          primerBtn.classList.add('active');
        }
        filtrar();
      })
      .catch(function() {
        el('lista-prods').innerHTML = '<p style="color:#e94560;text-align:center;margin-top:30px">Error cargando menu</p>';
      });
  }

  function construirComentariosPorProducto() {
  comentariosPorProducto = {};
  
  menu.forEach(function(prod) {
    var cat = prod.categoria || '';
    if (prod.comentarios_rapidos && prod.comentarios_rapidos.length > 0) {
      comentariosPorProducto[prod.id] = prod.comentarios_rapidos;
    } else {
      comentariosPorProducto[prod.id] = comentariosDinamicos[cat] || [];
    }
  });

  Object.keys(grupos).forEach(function(nombre_grupo) {
    var g = grupos[nombre_grupo];
    var cat = g.categoria || '';
    Object.values(g.nombres).forEach(function(nombre_prod) {
      var prod = menu.find(function(p) { return p.nombre === nombre_prod; }); 
      if (prod) {
        if (prod.comentarios_rapidos && prod.comentarios_rapidos.length > 0) {
          comentariosPorProducto[prod.id] = prod.comentarios_rapidos;
        } else {
          comentariosPorProducto[prod.id] = comentariosDinamicos[cat] || [];
        }
      }
    });
  });
}

  function renderCats(cats) {
    var html = '';
    cats.forEach(function(c) {
      html += '<button class="cat-btn" data-cat="' + c + '">' + c + '</button>';
    });
    html += '<button class="cat-btn" data-cat="todas">Todas</button>';
    el('lista-cats').innerHTML = html;

    el('lista-cats').addEventListener('click', function(e) {
      var btn = e.target.closest('.cat-btn');
      if (!btn) return;
      document.querySelectorAll('.cat-btn').forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
      catActiva = btn.getAttribute('data-cat');
      el('inp-buscar').value = "";
      document.activeElement.blur();
      filtrar();
    });
  }

  function filtrar() {
    var texto = el('inp-buscar').value.trim().toLowerCase();

    if (texto !== "") {
        var filtrados = menu.filter(function(p){
            return normalizarTexto(p.nombre).includes(normalizarTexto(texto))
        });

        var gruposFiltrados = {};
        Object.keys(grupos).forEach(function(nombre){
            if(normalizarTexto(nombre).includes(normalizarTexto(texto))){
                gruposFiltrados[nombre] = grupos[nombre];
            }
        });

        renderProds(filtrados, gruposFiltrados);
        return;
    }

    var filtrados = menu.filter(function(p){
        return catActiva==="todas" || p.categoria===catActiva;
    });

    var gruposFiltrados = {};
    Object.keys(grupos).forEach(function(nombre){
        var g = grupos[nombre];
        if(catActiva==="todas" || g.categoria===catActiva){
            gruposFiltrados[nombre]=g;
        }
    });

    renderProds(filtrados, gruposFiltrados);
  }

  el('inp-buscar').addEventListener('input', filtrar);
  el('inp-buscar').addEventListener('keydown', function(e){
    if(e.key==="Enter"){
        e.preventDefault();
        this.blur();
    }
  });

  function sumaProducto(id) {
    return Object.keys(carrito).reduce(function(s, k) {
      var it = carrito[k];
      return (!it.grupo && it.producto_id === id) ? s + it.cantidad : s;
    }, 0);
  }

  function renderProds(prods, gruposFiltrados) {
    gruposFiltrados = gruposFiltrados || grupos;
    var html = '';

    Object.keys(gruposFiltrados).forEach(function(ng) {
      var g = gruposFiltrados[ng];
      var enCarrito = Object.values(carrito).filter(function(i) { return i.grupo === ng; });
      var totalEnCarrito = enCarrito.reduce(function(s, i) { return s + i.cantidad; }, 0);
      var badge = totalEnCarrito ? ' <span class="prod-qty">(x' + totalEnCarrito + ')</span>' : '';
      var sel = totalEnCarrito ? ' selected' : '';
      var precioTxt = (g.precio_max && g.precio_max > g.precio)
        ? 'Desde ' + fmt(g.precio)
        : fmt(g.precio);
      var esCombo = ng.toLowerCase().indexOf('combo') === 0;
      var lineaVariantes = esCombo
        ? ''
        : '<div class="prod-variante">Elige: ' + g.variantes.join(' / ') + '</div>';
      html += '<div class="prod-card grupo' + sel + '" data-grupo="' + ng + '">' +
                '<div><div class="prod-name">▼ ' + ng + badge + '</div>' +
                lineaVariantes + '</div>' +
                '<div class="prod-price">' + precioTxt + '</div>' +
              '</div>';
    });

    if (!prods.length && !Object.keys(gruposFiltrados).length) {
      el('lista-prods').innerHTML = '<p style="text-align:center;color:#a0a8c0;margin-top:30px">Sin resultados</p>';
      return;
    }

    prods.forEach(function(p) {
      var totalQty = sumaProducto(p.id);
      var qtyBadge = totalQty ? ' <span class="prod-qty">(x' + totalQty + ')</span>' : '';
      var sel = totalQty ? ' selected' : '';
      var desc = p.descripcion ? '<div class="prod-desc">' + p.descripcion + '</div>' : '';
      html += '<div class="prod-card' + sel + '" data-id="' + p.id + '">' +
                '<div><div class="prod-name">' + p.nombre + qtyBadge + '</div>' + desc + '</div>' +
                '<div class="prod-price">' + fmt(p.precio) + '</div>' +
              '</div>';
    });

    el('lista-prods').innerHTML = html;
    el('lista-prods').addEventListener('click', function(e) {
      var card = e.target.closest('.prod-card');
      if (!card) return;
      var ng = card.getAttribute('data-grupo');
      if (ng) { abrirModalVariante(ng); return; }
      var id = parseInt(card.getAttribute('data-id'));
      var prod = menu.find(function(p) { return p.id === id; });
      if (prod) abrirModal(prod);
    });
  }

  // ── MODALS ─────────────────────────────────────────────────
  function abrirModal(prod) {
    prodModal = prod;
    qtyModal = sumaProducto(prod.id) || 1;
    el('modal-nombre').textContent = prod.nombre;
    el('modal-precio').textContent = fmt(prod.precio) + ' c/u';
    el('modal-qty').textContent = qtyModal;
    show('modal');
  }

  function cerrarModal() { hide('modal'); prodModal = null; }
  el('btn-menos').addEventListener('click', function() {
    qtyModal = Math.max(0, qtyModal - 1);
    el('modal-qty').textContent = qtyModal;
  });
  el('btn-mas').addEventListener('click', function() {
    qtyModal += 1;
    el('modal-qty').textContent = qtyModal;
  });
  el('btn-modal-cancel').addEventListener('click', cerrarModal);
  el('modal').addEventListener('click', function(e) { if (e.target === el('modal')) cerrarModal(); });

  function clavesProducto(id) {
    return Object.keys(carrito).filter(function(k) {
      var it = carrito[k];
      return !it.grupo && it.producto_id === id;
    });
  }

  function separarEnUnidades(claves) {
    claves.forEach(function(k) {
      var it = carrito[k];
      if (!it || it.cantidad <= 1) return;
      var extra = it.cantidad - 1;
      it.cantidad = 1;
      for (var i = 0; i < extra; i++) {
        var nuevaClave = k + '__u' + Date.now() + Math.floor(Math.random() * 100000) + '_' + i;
        carrito[nuevaClave] = {
          nombre: it.nombre, precio: it.precio, cantidad: 1,
          producto_id: it.producto_id, comentario: '', grupo: it.grupo
        };
      }
    });
  }

  function ajustarUnidadesProducto(nombre, precio, prodId, deseado, obtenerClaves, crearLinea) {
    var claves = obtenerClaves();
    separarEnUnidades(claves);
    claves = obtenerClaves();
    var actual = claves.length;

    if (deseado <= 0) {
      claves.forEach(function(k) { delete carrito[k]; });
      return;
    }
    if (deseado > actual) {
      var faltan = deseado - actual;
      for (var i = 0; i < faltan; i++) {
        var nuevaClave = crearLinea(i);
        carrito[nuevaClave] = {
          nombre: nombre, precio: precio, cantidad: 1,
          producto_id: prodId, comentario: ''
        };
      }
    } else if (deseado < actual) {
      var sobran = actual - deseado;
      var ordenBorrado = claves.slice().sort(function(a, b) {
        var ca = carrito[a].comentario ? 1 : 0;
        var cb = carrito[b].comentario ? 1 : 0;
        return ca - cb;
      });
      for (var j = 0; j < sobran; j++) {
        delete carrito[ordenBorrado[j]];
      }
    }
  }

  el('btn-modal-ok').addEventListener('click', function() {
    if (!prodModal) return;
    var pid = prodModal.id;
    ajustarUnidadesProducto(
      prodModal.nombre,
      prodModal.precio,
      pid,
      qtyModal,
      function() { return clavesProducto(pid); },
      function(i) { return pid + '__u' + Date.now() + Math.floor(Math.random() * 100000) + '_' + i; }
    );
    cerrarModal();
    actualizarCarrito();
    filtrar();
  });

  // ── VARIANT MODAL ────────────────────────────────────────────
  function abrirModalVariante(ng) {
    grupoModal = ng;
    varianteElegida = null;
    var g = grupos[ng];
    el('mv-nombre').textContent = ng;
    el('mv-precio').textContent = (g.precio_max && g.precio_max > g.precio)
      ? 'Desde ' + fmt(g.precio) + ' c/u'
      : fmt(g.precio) + ' c/u';
    var html = '';
    g.variantes.forEach(function(v) {
      html += '<button class="variante-btn" data-v="' + v + '">' + v + '</button>';
    });
    el('mv-variantes').innerHTML = html;
    el('mv-variantes').querySelectorAll('.variante-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        varianteElegida = this.getAttribute('data-v');
        hide('modal-variante');
        abrirModalCantidadVariante();
      });
    });
    show('modal-variante');
  }

  el('mv-cancel').addEventListener('click', function() { hide('modal-variante'); grupoModal = null; });
  el('modal-variante').addEventListener('click', function(e) {
    if (e.target === el('modal-variante')) { hide('modal-variante'); grupoModal = null; }
  });

  function clavesVariante(ng, nombreReal) {
    return Object.keys(carrito).filter(function(k) {
      var it = carrito[k];
      return it.grupo === ng && it.nombre === nombreReal;
    });
  }

  function abrirModalCantidadVariante() {
    var g = grupos[grupoModal];
    var nombreReal = g.nombres[varianteElegida];
    qtyVariante = clavesVariante(grupoModal, nombreReal).reduce(function(s, k) {
      return s + carrito[k].cantidad;
    }, 0) || 1;
    el('mcv-nombre').textContent = nombreReal;
    el('mcv-qty').textContent = qtyVariante;
    show('modal-comentario-v');
  }

  el('mcv-menos').addEventListener('click', function() {
    qtyVariante = Math.max(0, qtyVariante - 1);
    el('mcv-qty').textContent = qtyVariante;
  });
  el('mcv-mas').addEventListener('click', function() {
    qtyVariante += 1;
    el('mcv-qty').textContent = qtyVariante;
  });
  el('mcv-cancel').addEventListener('click', function() { hide('modal-comentario-v'); grupoModal = null; varianteElegida = null; });
  el('modal-comentario-v').addEventListener('click', function(e) {
    if (e.target === el('modal-comentario-v')) { hide('modal-comentario-v'); grupoModal = null; varianteElegida = null; }
  });

  function ajustarUnidadesVariante(nombre, precio, prodId, ng, deseado, obtenerClaves) {
    var claves = obtenerClaves();
    separarEnUnidades(claves);
    claves = obtenerClaves();
    var actual = claves.length;

    if (deseado <= 0) {
      claves.forEach(function(k) { delete carrito[k]; });
      return;
    }
    if (deseado > actual) {
      var faltan = deseado - actual;
      for (var i = 0; i < faltan; i++) {
        var nuevaClave = ng + '::' + nombre + '__u' + Date.now() + Math.floor(Math.random() * 100000) + '_' + i;
        carrito[nuevaClave] = {
          nombre: nombre, precio: precio, cantidad: 1,
          producto_id: prodId, comentario: '', grupo: ng
        };
      }
    } else if (deseado < actual) {
      var sobran = actual - deseado;
      var ordenBorrado = claves.slice().sort(function(a, b) {
        var ca = carrito[a].comentario ? 1 : 0;
        var cb = carrito[b].comentario ? 1 : 0;
        return ca - cb;
      });
      for (var j = 0; j < sobran; j++) {
        delete carrito[ordenBorrado[j]];
      }
    }
  }

  el('mcv-ok').addEventListener('click', function() {
    if (!grupoModal || !varianteElegida) return;
    var g = grupos[grupoModal];
    var nombreReal = g.nombres[varianteElegida];
    var prodId = (g.ids && g.ids[varianteElegida] != null) ? g.ids[varianteElegida] : null;
    var precioReal = (g.precios && g.precios[varianteElegida] != null) ? g.precios[varianteElegida] : g.precio;
    var ng = grupoModal;

    ajustarUnidadesVariante(
      nombreReal, precioReal, prodId, ng, qtyVariante,
      function() { return clavesVariante(ng, nombreReal); }
    );

    hide('modal-comentario-v');
    grupoModal = null;
    varianteElegida = null;
    actualizarCarrito();
    filtrar();
  });

  // ── ITEM COMMENT IN THE CART ─────────────────────────────────
  var claveComentarioActual = null;

  function obtenerComentariosParaItem(item) {
    if (item.producto_id && comentariosPorProducto[item.producto_id]) {
      return comentariosPorProducto[item.producto_id];
    }
    // By default, generic comments
    return ['Sin ingrediente', 'Aparte', 'Bien servido', 'Para llevar'];
  }

  function abrirModalComentarioCarrito(clave) {
    var item = carrito[clave];
    if (!item) return;
    claveComentarioActual = clave;
    el('mcc-nombre').textContent = 'Comentario — ' + item.nombre;
    el('mcc-texto').value = item.comentario || '';
    
    // Get specific comments for this item
    var comentarios = obtenerComentariosParaItem(item);
    
    var chipsHtml = '';
    comentarios.forEach(function(c) {
      chipsHtml += '<button type="button" class="chip-rapido" data-c="' + c + '">' + c + '</button>';
    });
    el('mcc-chips').innerHTML = chipsHtml;
    el('mcc-chips').querySelectorAll('.chip-rapido').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var frase = this.getAttribute('data-c');
        var actual = el('mcc-texto').value;
        if (actual.toLowerCase().indexOf(frase.toLowerCase()) === -1) {
          el('mcc-texto').value = actual ? (actual + ', ' + frase) : frase;
        }
      });
    });
    show('modal-comentario-carrito');
  }

  function cerrarModalComentarioCarrito() {
    hide('modal-comentario-carrito');
    claveComentarioActual = null;
  }

  el('mcc-cancel').addEventListener('click', cerrarModalComentarioCarrito);
  el('modal-comentario-carrito').addEventListener('click', function(e) {
    if (e.target === el('modal-comentario-carrito')) cerrarModalComentarioCarrito();
  });
  el('mcc-ok').addEventListener('click', function() {
    if (!claveComentarioActual || !carrito[claveComentarioActual]) { cerrarModalComentarioCarrito(); return; }
    carrito[claveComentarioActual].comentario = el('mcc-texto').value.trim();
    cerrarModalComentarioCarrito();
    actualizarCarrito();
  });

  // ── DRINK NOTICE AND CART ──────────────────────────────────
  function categoriaDeItem(item) {
    if (item.grupo && grupos[item.grupo]) return grupos[item.grupo].categoria || '';
    if (item.producto_id != null) {
      var p = menu.find(function(m) { return m.id === item.producto_id; });
      if (p) return p.categoria || '';
    }
    return '';
  }

  function desayunoIncluyeBebida(nombre) {
    var n = nombre.toLowerCase().trim();
    if (n.indexOf('porcion') !== -1 || n.indexOf('porción') !== -1) {
      return false;
    }
    if (n.indexOf('huevos') !== -1 || n.indexOf('caldo pequeño') !== -1 || 
        n.indexOf('bandeja') !== -1 || n.indexOf('combo') !== -1) {
      return true;
    }
    return false;
  }

  var ALMUERZOS_LIMONADA = {
    "ejecutivo turista":  1,
    "ejecutivo mulero":   1,
    "del día turista":    1,
    "del día mulero":     1,
  };

  function almuerzoIncluyeBebida(nombre) {
    var n = nombre.toLowerCase().trim();
    for (var clave in ALMUERZOS_LIMONADA) {
      var palabras = clave.split(' ');
      var todasPresentes = true;
      for (var i = 0; i < palabras.length; i++) {
        if (n.indexOf(palabras[i]) === -1) {
          todasPresentes = false;
          break;
        }
      }
      if (todasPresentes) {
        return true;
      }
    }
    return false;
  }

  function tieneBebida() {
    var tieneBebidaDirecta = false;
    var tieneBebidaIncluida = false;
    
    Object.values(carrito).forEach(function(item) {
      var cat = categoriaDeItem(item);
      if (cat.toLowerCase().indexOf('bebida') !== -1) {
        tieneBebidaDirecta = true;
      }
      if (desayunoIncluyeBebida(item.nombre) || almuerzoIncluyeBebida(item.nombre)) {
        tieneBebidaIncluida = true;
      }
    });
    
    return tieneBebidaDirecta || tieneBebidaIncluida;
  }

  function categoriaBebidas() {
    return categoriasCargadas.find(function(c) { return c.toLowerCase().indexOf('bebida') !== -1; }) || '';
  }

  el('btn-ir-bebidas').addEventListener('click', function() {
    var catBeb = categoriaBebidas();
    if (catBeb) {
      catActiva = catBeb;
      document.querySelectorAll('.cat-btn').forEach(function(b) {
        b.classList.toggle('active', b.getAttribute('data-cat') === catBeb);
      });
      filtrar();
    }
    cerrarTicket();
  });

  // ── TICKET PANEL ─────────────────────────────────────────────

  function abrirTicket() {
    el('ticket-bar').classList.add('abierto');
    el('ticket-overlay').classList.add('abierto');
  }

  function cerrarTicket() {
    el('ticket-bar').classList.remove('abierto');
    el('ticket-overlay').classList.remove('abierto');
  }

  el('fab-carrito').addEventListener('click', abrirTicket);
  el('ticket-overlay').addEventListener('click', cerrarTicket);

  // ── CART ─────────────────────────────────────────────────────
  function actualizarCarrito() {
    var items = Object.values(carrito);
    var total = items.reduce(function(s, i) { return s + i.precio * i.cantidad; }, 0);
    var count = items.reduce(function(s, i) { return s + i.cantidad; }, 0);

    if (count > 0) {
      el('fab-carrito').classList.remove('hidden');
      el('fab-total').textContent = fmt(total);
      el('fab-count').textContent = count;
    } else {
      el('fab-carrito').classList.add('hidden');
      cerrarTicket();
    }

    el('ticket-count').textContent = count > 0 ? count + ' item(s)' : 'Carrito vacío';
    el('ticket-total').textContent = fmt(total);
    el('btn-enviar').disabled = count === 0;

    if (count > 0 && !tieneBebida()) {
      show('ticket-aviso-bebida');
    } else {
      hide('ticket-aviso-bebida');
    }

    if (!items.length) {
      el('ticket-lista').innerHTML = '<div class="ticket-vacio">Agrega productos tocandolos</div>';
      return;
    }

    var html = '';
    items.forEach(function(item, idx) {
      var claveItem = Object.keys(carrito)[idx];
      var notaHtml = item.comentario ? '<div class="ticket-item-nota">✎ ' + item.comentario + '</div>' : '';
      var comentarHtml = '<div class="ticket-item-comentar" data-action="comentario" data-key="' + claveItem + '">' +
                            (item.comentario ? 'Editar comentario' : '+ Agregar comentario') +
                          '</div>';
      html += '<div class="ticket-item">' +
                '<div class="ticket-item-info">' +
                  '<div class="ticket-item-nombre">' + item.nombre + '</div>' +
                  '<div class="ticket-item-precio">' + fmt(item.precio) + '</div>' +
                  notaHtml +
                  comentarHtml +
                '</div>' +
                '<div class="ticket-item-ctrl">' +
                  '<button class="t-btn" data-action="duplicar" data-key="' + claveItem + '" title="Agregar otra unidad igual">&#43;1</button>' +
                '</div>' +
                '<button class="t-del" data-action="del" data-key="' + claveItem + '">&#10005;</button>' +
              '</div>';
    });
    el('ticket-lista').innerHTML = html;

    el('ticket-lista').querySelectorAll('[data-action]').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var key = this.getAttribute('data-key');
        var action = this.getAttribute('data-action');
        if (!carrito[key]) return;
        if (action === 'del') {
          delete carrito[key];
        } else if (action === 'comentario') {
          abrirModalComentarioCarrito(key);
          return;
        } else if (action === 'duplicar') {
          var base = carrito[key];
          var nuevaClave = key + '__u' + Date.now() + Math.floor(Math.random() * 100000);
          carrito[nuevaClave] = {
            nombre: base.nombre,
            precio: base.precio,
            cantidad: 1,
            producto_id: base.producto_id,
            comentario: '',
            grupo: base.grupo
          };
        }
        actualizarCarrito();
        filtrar();
      });
    });
  }

  el('btn-lupa').addEventListener('click', function() {
    var sb = el('search-bar');
    var abierto = sb.classList.toggle('visible');
    el('btn-lupa').classList.toggle('activa', abierto);
    if (abierto) {
      el('inp-buscar').focus();
    } else {
      el('inp-buscar').value = '';
      filtrar();
    }
  });

  el('inp-mesa').addEventListener('input', function() {
    el('badge-mesa').textContent = el('inp-mesa').value.trim() || 'Sin mesa';
  });

  // ── SEND ──────────────────────────────────────────────────────
  el('btn-enviar').addEventListener('click', function() {
    var mesa = el('inp-mesa').value.trim();
    if (!mesa) { alert('Escribe el numero de mesa primero.'); return; }
    var items = Object.values(carrito);
    if (!items.length) return;

    el('btn-enviar').disabled = true;
    el('btn-enviar').textContent = 'Enviando...';

    fetch('/api/comanda', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({mesa: mesa, items: items})
    })
    .then(function(r) {
      if (r.status === 401) { sesionExpirada(); return null; }
      return r.json();
    })
    .then(function(data) {
      if (!data) return;
      if (data.ok) {
        carrito = {};
        actualizarCarrito();
        el('inp-mesa').value = '';
        el('badge-mesa').textContent = 'Sin mesa';
        filtrar();
        alert('Comanda enviada a caja!');
        mostrarPagMesas();
      } else {
        alert('Error: ' + (data.error || 'desconocido'));
      }
    })
    .catch(function(e) {
      alert('No se pudo conectar: ' + e.message);
    })
    .finally(function() {
      el('btn-enviar').disabled = false;
      el('btn-enviar').textContent = 'Enviar Comanda a Caja';
    });
  });

})();