<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AutoStock Mayab - Cancún</title>
    <link rel="manifest" href="/static/manifest.json">
    <meta name="theme-color" content="#0f172a">
    <script src="https://tailwindcss.com"></script>
    <script>
      const lucideScript = document.createElement('script');
      lucideScript.src = 'https://jsdelivr.net';
      lucideScript.onload = () => { if (window.lucide) lucide.createIcons(); };
      document.head.appendChild(lucideScript);

      const h2cScript = document.createElement('script');
      h2cScript.src = 'https://jsdelivr.net';
      document.head.appendChild(h2cScript);
    </script>
    <link rel="icon" type="image/png" href="/static/logo.png">
    <link rel="apple-touch-icon" href="/static/logo.png">
    <style>
      @keyframes spinRing { to { transform: rotate(360deg); } }
      .spinner-ring {
        display: inline-block; width: 14px; height: 14px;
        border: 2px solid currentColor; border-right-color: transparent;
        border-radius: 9999px; animation: spinRing 0.65s linear infinite;
      }
      @media print {
        body * { visibility: hidden !important; }
        #tarjeta-cotizacion-export, #tarjeta-cotizacion-export * {
          visibility: visible !important;
        }
        #tarjeta-cotizacion-export {
          position: fixed !important; left: 0 !important; top: 0 !important;
          width: 100% !important; background: #0f172a !important;
          color: #ffffff !important; -webkit-print-color-adjust: exact;
          print-color-adjust: exact;
        }
      }
    </style>
</head>
<body class="bg-slate-100 text-slate-900 font-sans min-h-screen pb-24">
    <!-- BARRA DE PROGRESO SUPERIOR ULTRA-MODERNA -->
    <div id="top-progress-bar" class="fixed top-0 left-0 h-[3px] bg-gradient-to-r from-orange-500 via-amber-400 to-orange-500 z-[100] transition-all duration-300 pointer-events-none shadow-[0_0_8px_rgba(249,115,22,0.85)]" style="width: 0%; opacity: 0;"></div>

    {% set rol_actual = (usuario.rol.value if usuario and usuario.rol.value else (usuario.rol if usuario else 'Publico')) %}
    {% set es_admin = (rol_actual == 'Administrador') %}
    {% set es_vendedor = (rol_actual == 'Vendedor') %}
    {% set es_mecanico = (rol_actual == 'Mecanico') %}
    {% set es_operador = (es_admin or es_vendedor) %}

    <!-- HEADER COMPACTO -->
    <header class="bg-slate-900 text-white shadow-lg sticky top-0 z-40 border-b-4 border-orange-500">
        <div class="max-w-7xl mx-auto px-3 py-2.5 flex justify-between items-center gap-2">
            <div class="flex items-center space-x-2 cursor-pointer shrink-0" onclick="cambiarVista('inicio')">
                <img src="/static/logo.png" alt="Logo AutoStock Mayab" class="h-9 w-9 rounded-xl object-cover shadow border border-slate-700">
                <div>
                    <span class="text-base font-extrabold tracking-tight block leading-none">AutoStock <span class="text-orange-400">Mayab</span></span>
                    <span class="text-[9px] text-slate-400 font-semibold tracking-wider uppercase">
                        {% if es_admin %}Bodega Admin{% elif es_vendedor %}Mostrador{% elif es_mecanico %}Taller Afiliado{% else %}Cancún • Refacciones{% endif %}
                    </span>
                </div>
            </div>

            <div class="flex items-center gap-1.5">
                <!-- PÍLDORA MI GARAJE (VISIBLE EN MÓVIL Y DESKTOP) -->
                <button type="button" onclick="cambiarVista('garaje')" class="px-2.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-extrabold text-orange-400 flex items-center gap-1 transition" title="Mi Garaje">
                    <i data-lucide="car" class="w-4 h-4 shrink-0"></i>
                    <span id="label-garaje-top" class="max-w-[95px] truncate text-[11px]">Mi Garaje</span>
                </button>

                <!-- INTERRUPTOR VISTA TALLER / VISTA CLIENTE (MECÁNICOS) -->
                {% if es_mecanico or es_admin %}
                <button type="button" id="btn-modo-cliente" onclick="toggleModoCliente()" class="px-2.5 py-2 rounded-xl bg-emerald-600/20 border border-emerald-500/40 text-emerald-300 text-xs font-extrabold flex items-center gap-1 transition" title="Alternar Vista Taller / Vista Cliente">
                    <i data-lucide="wrench" class="w-4 h-4"></i>
                    <span id="texto-modo-cliente" class="text-[10px] uppercase">Taller</span>
                </button>
                {% endif %}

                <!-- MENÚ LATERAL -->
                <button type="button" onclick="toggleMenuLateral()" class="relative p-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-white transition" aria-label="Menú">
                    <i data-lucide="menu" class="w-5 h-5"></i>
                    {% if es_admin and solicitudes_ids %}
                        <span class="absolute -top-1 -right-1 w-2.5 h-2.5 bg-orange-500 rounded-full animate-pulse"></span>
                    {% endif %}
                </button>
            </div>
        </div>
    </header>
    
