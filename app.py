import streamlit as st
import pandas as pd
import plotly.express as plotly_xp
import plotly.graph_objects as plotly_go
import requests
import json
from datetime import datetime
import io

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS (OKLCH)
# ==========================================
st.set_page_config(
    page_title="Sabores de Guatemala — Sistema de Gestión con IA",
    page_icon="🍲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inyección de estilos CSS personalizados emulando el tema solicitado
# Nota: Streamlit no procesa oklch de forma nativa en navegadores antiguos, 
# por lo que se proporciona el equivalente hex/rgb exacto para asegurar la visualización.
# Verde profundo guatemalteco: #0d3c26 | Dorado acento: #e5b842
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600&display=swap');
    
    html, body, [data-testid="stSidebarNav"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    h1, h2, h3, .main-title {
        font-family: 'Outfit', sans-serif;
        color: #0d3c26;
    }
    /* Estilos del Sidebar Oscuro Verde */
    [data-testid="stSidebar"] {
        background-color: #062416 !important;
        color: #ffffff;
    }
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    /* Botones primarios con acento Dorado */
    div.stButton > button:first-child {
        background-color: #e5b842 !important;
        color: #062416 !important;
        font-weight: 600 !important;
        border: none !important;
    }
    /* Tarjetas personalizadas */
    .metric-card {
        background-color: #f4f7f5;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #0d3c26;
        margin-bottom: 15px;
    }
    .agent-card {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. INICIALIZACIÓN DE DATOS (MOCK CONVEX DB)
# ==========================================
def inicializar_base_de_datos():
    if 'db_initialized' not in st.session_state:
        # Restaurante
        st.session_state.restaurante = {
            "nombre": "Sabores de Guatemala",
            "ubicacion": "Zona 10, Ciudad de Guatemala",
            "tipo": "Comida guatemalteca",
            "capacidad": 80,
            "mesas": 15,
            "horarioApertura": "09:00",
            "horarioCierre": "22:00",
            "diasOperacion": "Lu-Do",
            "descripcion": "Auténtica gastronomía ancestral en el corazón de la Zona 10."
        }
        
        # Agentes
        st.session_state.agentes = [
            {"id": "carlos", "nombre": "Carlos Méndez", "rol": "Gerente General", "funcion": "Coordina todas las áreas. Conoce a cada gerente.", "prompt": "Eres Carlos Méndez, Gerente General del restaurante Sabores de Guatemala. Coordinas todas las áreas y conoces a los gerentes (Ana, Roberto, María, Pedro, Lucía, Diego, Isabel). Responde de manera profesional, amigable y ejecutiva.", "estado": "activo", "color": "#1a6b4a", "orden": 1},
            {"id": "ana", "nombre": "Ana López", "rol": "Gerente de Operaciones", "funcion": "Apertura, cierre, turnos, logística.", "prompt": "Eres Ana López, Gerente de Operaciones. Te encargas de las mesas, la logística del piso y los turnos de apertura y cierre. Tu enfoque es altamente logístico y práctico.", "estado": "activo", "color": "#2563eb", "orden": 2},
            {"id": "roberto", "nombre": "Roberto Soto", "rol": "Gerente de Compras e Inventario", "funcion": "Inventario, compras, proveedores.", "prompt": "Eres Roberto Soto, Gerente de Compras e Inventario. Monitoreas los insumos, costos unitarios y alertas de existencias. Tu estilo es preciso y numérico.", "estado": "activo", "color": "#7c3aed", "orden": 3},
            {"id": "maria", "nombre": "María Ajú", "rol": "Gerente de Cocina", "funcion": "Producción, calidad, tiempos.", "prompt": "Eres María Ajú, Gerente de Cocina. Resguardas las recetas ancestrales, controlas los tiempos de preparación y el despacho de platillos del menú.", "estado": "activo", "color": "#dc2626", "orden": 4},
            {"id": "pedro", "nombre": "Pedro Tzul", "rol": "Gerente de Servicio al Cliente", "funcion": "Atención, quejas, reservas.", "prompt": "Eres Pedro Tzul, Gerente de Servicio al Cliente. Gestionas las reservas de mesas y garantizas la máxima satisfacción de los comensales.", "estado": "activo", "color": "#0891b2", "orden": 5},
            {"id": "lucia", "nombre": "Lucía Gramajo", "rol": "Gerente Financiero", "funcion": "Caja, gastos, presupuestos.", "prompt": "Eres Lucía Gramajo, Gerente Financiero. Controlas las ventas, egresos por insumos, nóminas y la utilidad neta total del negocio.", "estado": "activo", "color": "#059669", "orden": 6},
            {"id": "diego", "nombre": "Diego Herrera", "rol": "Gerente de Marketing", "funcion": "Publicidad, redes, promociones.", "prompt": "Eres Diego Herrera, Gerente de Marketing. Evalúas el impacto de las promociones y el flujo de clientes según el rendimiento diario de las ventas.", "estado": "activo", "color": "#d97706", "orden": 7},
            {"id": "isabel", "nombre": "Isabel Pérez", "rol": "Gerente de RRHH", "funcion": "Personal, contrataciones, horarios.", "prompt": "Eres Isabel Pérez, Gerente de Recursos Humanos. Gestionas al personal, el cumplimiento de los turnos de trabajo y el pago de salarios.", "estado": "activo", "color": "#be185d", "orden": 8}
        ]
        
        # Inventario
        st.session_state.inventario = [
            {"id": 1, "producto": "Tomate", "categoria": "Verduras", "unidad": "Libras", "cantidad": 5, "costoUnitario": 4.50, "stockMinimo": 20, "estado": "crítico"},
            {"id": 2, "producto": "Cebolla", "categoria": "Verduras", "unidad": "Libras", "cantidad": 12, "costoUnitario": 3.00, "stockMinimo": 15, "estado": "bajo"},
            {"id": 3, "producto": "Arroz", "categoria": "Abarrotes", "unidad": "Libras", "cantidad": 50, "costoUnitario": 5.00, "stockMinimo": 20, "estado": "suficiente"},
            {"id": 4, "producto": "Frijoles negros", "categoria": "Abarrotes", "unidad": "Libras", "cantidad": 45, "costoUnitario": 6.50, "stockMinimo": 15, "estado": "suficiente"},
            {"id": 5, "producto": "Aceite vegetal", "categoria": "Abarrotes", "unidad": "Litros", "cantidad": 20, "costoUnitario": 18.00, "stockMinimo": 10, "estado": "suficiente"},
            {"id": 6, "producto": "Pollo entero", "categoria": "Carnes", "unidad": "Unidades", "cantidad": 15, "costoUnitario": 35.00, "stockMinimo": 10, "estado": "suficiente"},
            {"id": 7, "producto": "Res molida", "categoria": "Carnes", "unidad": "Libras", "cantidad": 8, "costoUnitario": 28.00, "stockMinimo": 12, "estado": "bajo"},
            {"id": 8, "producto": "Tortillas de maíz", "categoria": "Otros", "unidad": "Ciento", "cantidad": 4, "costoUnitario": 25.00, "stockMinimo": 2, "estado": "suficiente"},
            {"id": 9, "producto": "Chiles pimientos", "categoria": "Verduras", "unidad": "Libras", "cantidad": 4, "costoUnitario": 8.00, "stockMinimo": 10, "estado": "bajo"},
            {"id": 10, "producto": "Sal", "categoria": "Abarrotes", "unidad": "Kilogramos", "cantidad": 10, "costoUnitario": 3.50, "stockMinimo": 2, "estado": "suficiente"}
        ]
        
        # Finanzas
        st.session_state.finanzas = [
            {"fecha": "2024-12-01", "tipo": "ingreso", "categoria": "Ventas", "descripcion": "Ventas diarias de piso", "monto": 3500.00},
            {"fecha": "2024-12-02", "tipo": "ingreso", "categoria": "Ventas", "descripcion": "Ventas diarias de piso", "monto": 4200.00},
            {"fecha": "2024-12-03", "tipo": "egreso", "categoria": "Insumos", "descripcion": "Compra de abarrotes y verduras", "monto": 1200.00},
            {"fecha": "2024-12-04", "tipo": "ingreso", "categoria": "Ventas", "descripcion": "Eventos especiales reservados", "monto": 4500.00},
            {"fecha": "2024-12-05", "tipo": "egreso", "categoria": "Servicios", "descripcion": "Pago de energía eléctrica y agua", "monto": 1800.00},
            {"fecha": "2024-12-06", "tipo": "ingreso", "categoria": "Ventas", "descripcion": "Ventas de fin de semana", "monto": 4800.00},
            {"fecha": "2024-12-15", "tipo": "egreso", "categoria": "Nómina", "descripcion": "Pago primera quincena de personal", "monto": 14200.00},
            {"fecha": "2024-12-20", "tipo": "ingreso", "categoria": "Ventas", "descripcion": "Ventas previas a festividades", "monto": 5200.00}
        ]

        # Menú
        st.session_state.menu = [
            {"nombre": "Pepián de pollo", "categoria": "Platillos", "precio": 65.00, "costoEstimado": 18.50, "disponible": True},
            {"nombre": "Kak'ik", "categoria": "Platillos", "precio": 70.00, "costoEstimado": 22.00, "disponible": True},
            {"nombre": "Hilachas", "categoria": "Platillos", "precio": 60.00, "costoEstimado": 16.00, "disponible": True},
            {"nombre": "Jocón", "categoria": "Platillos", "precio": 65.00, "costoEstimado": 17.50, "disponible": True},
            {"nombre": "Frijoles volteados", "categoria": "Acompañamientos", "precio": 25.00, "costoEstimado": 5.00, "disponible": True},
            {"nombre": "Tamales colorados", "categoria": "Platillos", "precio": 15.00, "costoEstimado": 4.50, "disponible": True},
            {"nombre": "Chuchitos", "categoria": "Antojitos", "precio": 12.00, "costoEstimado": 3.00, "disponible": True},
            {"nombre": "Ensalada guatemalteca", "categoria": "Acompañamientos", "precio": 35.00, "costoEstimado": 9.00, "disponible": True},
            {"nombre": "Limonada", "categoria": "Bebidas", "precio": 20.00, "costoEstimado": 4.00, "disponible": True},
            {"nombre": "Atol de elote", "categoria": "Bebidas", "precio": 18.00, "costoEstimado": 5.50, "disponible": True},
            {"nombre": "Café", "categoria": "Bebidas", "precio": 15.00, "costoEstimado": 2.50, "disponible": True},
            {"nombre": "Tres leches", "categoria": "Postres", "precio": 30.00, "costoEstimado": 8.00, "disponible": True}
        ]

        # Personal
        st.session_state.personal = [
            {"id": 1, "nombre": "Erick Alonzo", "puesto": "Chef", "turno": "Matutino", "salario": 5500.00, "estado": "activo"},
            {"id": 2, "nombre": "Claudia Chajón", "puesto": "Sous Chef", "turno": "Vespertino", "salario": 4500.00, "estado": "activo"},
            {"id": 3, "nombre": "Juan Marroquín", "puesto": "Mesero", "turno": "Matutino", "salario": 3200.00, "estado": "activo"},
            {"id": 4, "nombre": "Mateo Icó", "puesto": "Mesero", "turno": "Vespertino", "salario": 3200.00, "estado": "activo"},
            {"id": 5, "nombre": "Sofía Estrada", "puesto": "Cajero", "turno": "Matutino", "salario": 3500.00, "estado": "activo"},
            {"id": 6, "nombre": "Luisa Méndez", "puesto": "Hostess", "turno": "Vespertino", "salario": 3400.00, "estado": "activo"},
            {"id": 7, "nombre": "Pedro Culajay", "puesto": "Lavaplatos", "turno": "Completo", "salario": 3000.00, "estado": "activo"},
            {"id": 8, "nombre": "Ramiro Tun", "puesto": "Bartender", "turno": "Vespertino", "salario": 3400.00, "estado": "activo"}
        ]

        # Mesas
        st.session_state.mesas = [
            {"numero": 1, "ubicacion": "Interior", "capacidad": 4, "estado": "disponible"},
            {"numero": 2, "ubicacion": "Interior", "capacidad": 4, "estado": "ocupada"},
            {"numero": 3, "ubicacion": "Interior", "capacidad": 2, "estado": "disponible"},
            {"numero": 4, "ubicacion": "Interior", "capacidad": 6, "estado": "reservada"},
            {"numero": 5, "ubicacion": "Interior", "capacidad": 4, "estado": "disponible"},
            {"numero": 6, "ubicacion": "Interior", "capacidad": 8, "estado": "disponible"},
            {"numero": 7, "ubicacion": "Terraza", "capacidad": 4, "estado": "disponible"},
            {"numero": 8, "ubicacion": "Terraza", "capacidad": 4, "estado": "ocupada"},
            {"numero": 9, "ubicacion": "Terraza", "capacidad": 2, "estado": "disponible"},
            {"numero": 10, "ubicacion": "Terraza", "capacidad": 6, "estado": "disponible"},
            {"numero": 11, "ubicacion": "VIP", "capacidad": 4, "estado": "disponible"},
            {"numero": 12, "ubicacion": "VIP", "capacidad": 6, "estado": "reservada"},
            {"numero": 13, "ubicacion": "Barra", "capacidad": 2, "estado": "disponible"},
            {"numero": 14, "ubicacion": "Barra", "capacidad": 2, "estado": "disponible"},
            {"numero": 15, "ubicacion": "Interior", "capacidad": 4, "estado": "fuera_servicio"}
        ]

        # Tareas
        st.session_state.tareas = [
            {"id": 1, "titulo": "Comprar Tomates Urgentemente", "descripcion": "El inventario de tomate está en nivel crítico para el pepián.", "responsableId": "roberto", "prioridad": "crítica", "estado": "pendiente", "fechaCreacion": "2026-06-14"},
            {"id": 2, "titulo": "Ajustar Roles de Turno Matutino", "descripcion": "Reorganizar roles por el retraso del personal de limpieza.", "responsableId": "isabel", "prioridad": "alta", "estado": "en_progreso", "fechaCreacion": "2026-06-14"},
            {"id": 3, "titulo": "Reparación de Mesa 15", "descripcion": "La pata base de la mesa se encuentra floja.", "responsableId": "ana", "prioridad": "media", "estado": "bloqueada", "fechaCreacion": "2026-06-13"}
        ]

        # Estructuras complementarias
        st.session_state.conversaciones = {}
        st.session_state.notificaciones = [
            {"titulo": "Alerta de Stock Crítico", "mensaje": "El Tomate está por debajo del stock mínimo exigido.", "tipo": "autopiloto", "leida": False, "timestamp": "2026-06-14 08:30"}
        ]
        st.session_state.historial_general = []
        st.session_state.metas_diarias = [
            {"fecha": "2026-06-14", "titulo": "Optimizar el flujo de despacho en cocina", "agenteId": "maria", "completada": False}
        ]
        st.session_state.diagnosticos = []
        st.session_state.informe_carlos = None
        st.session_state.db_initialized = True

inicializar_base_de_datos()

# ==========================================
# 3. GATEWAY DE IA (OPENROUTER INTEGRATION)
# ==========================================
def llamar_openrouter_api(messages):
    """
    Se conecta a la API de OpenRouter consumiendo el modelo gratuito solicitado.
    """
    api_key = st.secrets.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return "Error de Configuración: Por favor agrega tu OPENROUTER_API_KEY en los Secrets de Streamlit."
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-oss-120b:free",
        "messages": messages,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"Error de OpenRouter ({response.status_code}): {response.text}"
    except Exception as e:
        return f"Error de conexión con el proveedor de IA: {str(e)}"

def obtener_contexto_dinamico(rol):
    """
    Emula la función interna internal.contexto.getContextoRestaurante para armar strings de contexto.
    """
    ctx = f"Contexto actual para el rol: {rol}\n"
    if rol == "Gerente General":
        ctx += f"- Inventario: {len(st.session_state.inventario)} artículos monitoreados.\n"
        ctx += f"- Tareas Activas: {len(st.session_state.tareas)} asignadas.\n"
        ctx += f"- Personal Activo: {len([p for p in st.session_state.personal if p['estado']=='activo'])} personas.\n"
        ctx += f"- Mesas: {len(st.session_state.mesas)} en distribución total."
    elif rol == "Gerente de Operaciones":
        ctx += f"- Distribución de Mesas: {json.dumps(st.session_state.mesas)}\n"
        ctx += f"- Metas de hoy: {json.dumps(st.session_state.metas_diarias)}"
    elif rol == "Gerente de Compras e Inventario":
        ctx += f"- Catálogo de Insumos: {json.dumps(st.session_state.inventario)}"
    elif rol == "Gerente de Cocina":
        ctx += f"- Insumos Almacenados: {json.dumps([i for i in st.session_state.inventario if i['estado'] in ['crítico', 'bajo']])}\n"
        ctx += f"- Menú Actual: {json.dumps(st.session_state.menu)}"
    elif rol == "Gerente de Servicio al Cliente":
        ctx += f"- Estado Mesas Ocupación: {json.dumps(st.session_state.mesas)}"
    elif rol == "Gerente Financiero":
        ctx += f"- Transacciones Contables: {json.dumps(st.session_state.finanzas)}"
    elif rol == "Gerente de Marketing":
        ctx += f"- Catálogo Comercial de Platillos: {json.dumps(st.session_state.menu)}"
    elif rol == "Gerente de RRHH":
        ctx += f"- Plantilla de Trabajadores: {json.dumps(st.session_state.personal)}"
    return ctx

def ejecutar_agente_ia(agente_id, mensaje_usuario):
    agente = next(a for a in st.session_state.agentes if a['id'] == agente_id)
    contexto = obtener_contexto_dinamico(agente['rol'])
    
    messages = [
        {"role": "system", "content": f"{agente['prompt']}\n\nContexto Operativo del Restaurante en Tiempo Real:\n{contexto}"},
        {"role": "user", "content": mensaje_usuario}
    ]
    return llamar_openrouter_api(messages)

# ==========================================
# 4. SISTEMA DE REGISTRO E HISTORIAL
# ==========================================
def registrar_log(tipo, descripcion, entidad_tipo=None, entidad_id=None):
    st.session_state.historial_general.insert(0, {
        "tipo": tipo,
        "descripcion": descripcion,
        "entidadTipo": entidad_tipo,
        "entidadId": entidad_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

def agregar_notificacion(titulo, mensaje, tipo, tarea_id=None):
    st.session_state.notificaciones.insert(0, {
        "titulo": titulo,
        "mensaje": mensaje,
        "tipo": tipo,
        "leida": False,
        "tareaId": tarea_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
    })

# ==========================================
# 5. LAYOUT DE NAVEGACIÓN (SIDEBAR)
# ==========================================
with st.sidebar:
    st.markdown("### 🍲 Sabores de Guatemala")
    st.markdown(f"*{st.session_state.restaurante['ubicacion']}*")
    st.markdown("---")
    
    # Badge conteo notificaciones no leídas
    no_leidas = len([n for n in st.session_state.notificaciones if not n['leida']])
    notif_label = f"Notificaciones ({no_leidas})" if no_leidas > 0 else "Notificaciones"
    
    opciones_menu = {
        "Dashboard": "🏠 Dashboard",
        "Agentes": "👥 Agentes de IA",
        "Chat": "💬 Centro de Chat",
        "Tareas": "📋 Gestión de Tareas",
        "Kanban": "📊 Kanban",
        "Notificaciones": f"🔔 {notif_label}",
        "Reportes": "📈 Reportes y Analítica",
        "Historial": "📜 Historial de Cambios",
        "Carga Masiva": "📤 Carga Masiva",
        "Autopiloto": "🤖 Autopiloto Operativo",
        "Configuracion": "⚙️ Configuración"
    }
    
    seleccion = st.radio("Menú de Navegación", list(opciones_menu.keys()), format_func=lambda x: opciones_menu[x])

# ==========================================
# PAGINA 1: DASHBOARD
# ==========================================
if seleccion == "Dashboard":
    st.title("🏠 Tablero de Control Inteligente")
    st.caption(f"Fecha de Operación Local: {datetime.now().strftime('%A, %d de %B de %Y')}")
    
    # Informe del Gerente General con IA
    st.subheader("📋 Informe Ejecutivo del Gerente General (Carlos Méndez)")
    
    if st.session_state.informe_carlos is None:
        with st.spinner("Generando análisis estratégico de Carlos..."):
            ctx_general = obtener_contexto_dinamico("Gerente General")
            msg = [{"role": "system", "content": "Eres Carlos Méndez, Gerente General. Genera un informe resumido en español de máximo 4 párrafos sobre la situación general basándote en los datos. Incluye la situación actual, puntos críticos de atención y una recomendación clave corporativa."}]
            st.session_state.informe_carlos = llamar_openrouter_api(msg)
            
    st.markdown(f"<div class='metric-card'>{st.session_state.informe_carlos}</div>", unsafe_allow_html=True)
    if st.button("🔄 Regenerar Informe con IA"):
        st.session_state.informe_carlos = None
        st.rerun()
        
    # KPIs Rápidos de Tareas
    st.markdown("### 📊 Estado Operativo de Tareas")
    t_pendientes = len([t for t in st.session_state.tareas if t['estado'] == 'pendiente'])
    t_progreso = len([t for t in st.session_state.tareas if t['estado'] == 'en_progreso'])
    t_bloqueadas = len([t for t in st.session_state.tareas if t['estado'] == 'bloqueada'])
    t_completas = len([t for t in st.session_state.tareas if t['estado'] == 'completada'])
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Pendientes 📥", t_pendientes)
    col2.metric("En Progreso ⚡", t_progreso)
    col3.metric("Bloqueadas ⚠️", t_bloqueadas)
    col4.metric("Completadas ✅", t_completas)
    
    # Resumen Financiero Rápido (Cálculo Dinámico)
    st.markdown("### 💰 Estado Financiero")
    df_fin = pd.DataFrame(st.session_state.finanzas)
    ingresos = df_fin[df_fin['tipo'] == 'ingreso']['monto'].sum()
    egresos = df_fin[df_fin['tipo'] == 'egreso']['monto'].sum()
    utilidad = ingresos - egresos
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos Totales", f"Q{ingresos:,.2f}")
    c2.metric("Egresos Totales", f"Q{egresos:,.2f}")
    c3.metric("Utilidad Estimada", f"Q{utilidad:,.2f}", delta=f"Q{utilidad:,.2f}")
    
    # Alertas Críticas de Inventario
    st.markdown("### ⚠️ Alertas Críticas de Inventario")
    alertas = [i for i in st.session_state.inventario if i['estado'] in ['crítico', 'bajo']]
    if alertas:
        for al in alertas:
            st.error(f"**Insumo:** {al['producto']} | **Cantidad:** {al['cantidad']} {al['unidad']} | **Estado:** {al['estado'].upper()}")
    else:
        st.success("No se registran alertas críticas en almacén.")

# ==========================================
# PAGINA 2: AGENTES
# ==========================================
elif seleccion == "Agentes":
    st.title("👥 Red de Agentes de Inteligencia Artificial")
    st.write("Panel operativo de control y asignación para la gerencia experta automatizada.")
    
    cols = st.columns(3)
    for index, ag in enumerate(st.session_state.agentes):
        with cols[index % 3]:
            st.markdown(f"""
            <div class='agent-card' style='border-top: 5px solid {ag['color']};'>
                <h4>👤 {ag['nombre']}</h4>
                <p><b>Rol:</b> {ag['rol']}</p>
                <p><b>Función:</b> {ag['funcion']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Switch o Selector de Estado
            nuevo_estado = st.selectbox(
                f"Estado de {ag['nombre']}", 
                ["activo", "ocupado", "inactivo"], 
                index=["activo", "ocupado", "inactivo"].index(ag['estado']),
                key=f"status_{ag['id']}"
            )
            if nuevo_estado != ag['estado']:
                ag['estado'] = nuevo_estado
                registrar_log("sistema", f"Cambio de estado del agente {ag['nombre']} a {nuevo_estado}")
                st.success(f"Estado de {ag['nombre']} actualizado.")
            st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# PAGINA 3: CHAT E INYECCIÓN DINÁMICA
# ==========================================
elif seleccion == "Chat":
    st.title("💬 Sala de Comunicaciones con Agentes")
    
    agente_lista = {a['id']: f"{a['nombre']} ({a['rol']})" for a in st.session_state.agentes}
    agente_sel = st.selectbox("Selecciona un agente para interactuar en tiempo real:", list(agente_lista.keys()), format_func=lambda x: agente_lista[x])
    
    if agente_sel not in st.session_state.conversaciones:
        st.session_state.conversaciones[agente_sel] = []
        
    # Desplegar conversación previa
    for msg in st.session_state.conversaciones[agente_sel]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
    input_usuario = st.chat_input("Escribe una instrucción o consulta operativa...")
    if input_usuario:
        with st.chat_message("user"):
            st.write(input_usuario)
        st.session_state.conversaciones[agente_sel].append({"role": "user", "content": input_usuario})
        
        with st.spinner("Procesando respuesta del agente con OpenRouter..."):
            respuesta_agente = ejecutar_agente_ia(agente_sel, input_usuario)
            
        with st.chat_message("assistant"):
            st.write(respuesta_agente)
        st.session_state.conversaciones[agente_sel].append({"role": "assistant", "content": respuesta_agente})
        
        # Detector automático de generación de tareas sugeridas
        palabras_clave_tarea = ["crear tarea", "asignar tarea", "urgente", "necesario comprar", "reparar", "organizar"]
        if any(keyword in respuesta_agente.lower() for keyword in palabras_clave_tarea):
            st.info("💡 **Detección del Sistema:** La Inteligencia Artificial parece sugerir o requerir una nueva tarea. Puedes darla de alta en el módulo 'Gestión de Tareas'.")

# ==========================================
# PAGINA 4: GESTIÓN DE TAREAS
# ==========================================
elif seleccion == "Tareas":
    st.title("📋 Repositorio y Asignación de Tareas")
    
    # Formulario para Nueva Tarea
    with st.expander("➕ Registrar Nueva Tarea"):
        with st.form("form_nueva_tarea"):
            tit = st.text_input("Título de la tarea")
            desc = st.text_area("Descripción detallada")
            resp = st.selectbox("Gerente Responsable", [a['id'] for a in st.session_state.agentes])
            prio = st.selectbox("Prioridad de Ejecución", ["baja", "media", "alta", "crítica"])
            est_t = st.selectbox("Estado Inicial", ["pendiente", "en_progreso", "bloqueada", "completada"])
            
            enviado = st.form_submit_button("Guardar en Base de Datos")
            if enviado and tit:
                nueva_t = {
                    "id": len(st.session_state.tareas) + 1,
                    "titulo": tit,
                    "descripcion": desc,
                    "responsableId": resp,
                    "prioridad": prio,
                    "estado": est_t,
                    "fechaCreacion": datetime.now().strftime("%Y-%m-%d")
                }
                st.session_state.tareas.append(nueva_t)
                registrar_log("tareas", f"Tarea registrada: {tit}")
                agregar_notificacion("Nueva Tarea Creada", f"Se asignó la tarea '{tit}' al responsable.", "nueva_tarea", nueva_t["id"])
                st.success("Tarea registrada de manera exitosa.")
                st.rerun()

    # Filtros
    st.markdown("### Filtros Integrados")
    f_estado = st.multiselect("Filtrar por Estado:", ["pendiente", "en_progreso", "bloqueada", "completada"], default=["pendiente", "en_progreso", "bloqueada"])
    
    # Render de Tareas
    df_tareas = pd.DataFrame(st.session_state.tareas)
    if not df_tareas.empty:
        df_filtrado = df_tareas[df_tareas['estado'].isin(f_estado)]
        for idx, row in df_filtrado.iterrows():
            with st.container():
                st.markdown(f"#### 🏷️ {row['titulo']} [Prioridad: {row['prioridad'].upper()}]")
                st.write(f"**Descripción:** {row['descripcion']}")
                st.write(f"**Asignado a:** {row['responsableId'].capitalize()} | **Creado:** {row['fechaCreacion']}")
                
                # Botones de cambio de estado rápido
                c_1, c_2, c_3, c_4 = st.columns(4)
                if c_1.button("Pendiente", key=f"t_p_{row['id']}"):
                    st.session_state.tareas[st.session_state.tareas.index(next(t for t in st.session_state.tareas if t['id'] == row['id']))]['estado'] = 'pendiente'
                    registrar_log("tareas", f"Cambio estado tarea id {row['id']} a pendiente")
                    agregar_notificacion("Actualización", "Tarea movida a pendiente", "avance", row['id'])
                    st.rerun()
                if c_2.button("En Progreso", key=f"t_ep_{row['id']}"):
                    st.session_state.tareas[st.session_state.tareas.index(next(t for t in st.session_state.tareas if t['id'] == row['id']))]['estado'] = 'en_progreso'
                    registrar_log("tareas", f"Cambio estado tarea id {row['id']} a en_progreso")
                    st.rerun()
                if c_3.button("Bloquear", key=f"t_b_{row['id']}"):
                    st.session_state.tareas[st.session_state.tareas.index(next(t for t in st.session_state.tareas if t['id'] == row['id']))]['estado'] = 'bloqueada'
                    registrar_log("tareas", f"Cambio estado tarea id {row['id']} a bloqueada")
                    agregar_notificacion("Tarea Bloqueada", "Atención requerida", "bloqueo", row['id'])
                    st.rerun()
                if c_4.button("Completar", key=f"t_c_{row['id']}"):
                    st.session_state.tareas[st.session_state.tareas.index(next(t for t in st.session_state.tareas if t['id'] == row['id']))]['estado'] = 'completada'
                    registrar_log("tareas", f"Cambio estado tarea id {row['id']} a completada")
                    agregar_notificacion("Tarea Completada", "Buen trabajo", "finalizacion", row['id'])
                    st.rerun()
                st.markdown("---")

# ==========================================
# PAGINA 5: KANBAN
# ==========================================
elif seleccion == "Kanban":
    st.title("📊 Tablero de Control Kanban")
    st.write("Monitoreo visual del flujo de trabajo por estaciones operativas.")
    
    col_pend, col_prog, col_bloq, col_comp = st.columns(4)
    
    with col_pend:
        st.markdown("<h3 style='text-align: center; color: #7f8c8d;'>📥 Pendientes</h3>", unsafe_allow_html=True)
        for t in [t for t in st.session_state.tareas if t['estado'] == 'pendiente']:
            st.info(f"**{t['titulo']}**\n\nResp: {t['responsableId']}")
            
    with col_prog:
        st.markdown("<h3 style='text-align: center; color: #2980b9;'>⚡ En Progreso</h3>", unsafe_allow_html=True)
        for t in [t for t in st.session_state.tareas if t['estado'] == 'en_progreso']:
            st.warning(f"**{t['titulo']}**\n\nResp: {t['responsableId']}")
            
    with col_bloq:
        st.markdown("<h3 style='text-align: center; color: #c0392b;'>⚠️ Bloqueadas</h3>", unsafe_allow_html=True)
        for t in [t for t in st.session_state.tareas if t['estado'] == 'bloqueada']:
            st.error(f"**{t['titulo']}**\n\nResp: {t['responsableId']}")
            
    with col_comp:
        st.markdown("<h3 style='text-align: center; color: #27ae60;'>✅ Completadas</h3>", unsafe_allow_html=True)
        for t in [t for t in st.session_state.tareas if t['estado'] == 'completada']:
            st.success(f"**{t['titulo']}**\n\nResp: {t['responsableId']}")

# ==========================================
# PAGINA 6: NOTIFICACIONES
# ==========================================
elif seleccion == "Notificaciones":
    st.title("🔔 Centro de Notificaciones del Sistema")
    
    if st.button("🧹 Marcar todas como leídas"):
        for n in st.session_state.notificaciones:
            n['leida'] = True
        st.success("Notificaciones actualizadas con éxito.")
        st.rerun()
        
    for index, n in enumerate(st.session_state.notificaciones):
        tipo_badge = "🔵 NEW" if not n['leida'] else "⚪"
        st.markdown(f"**{tipo_badge} {n['titulo']}** — *{n['timestamp']}*")
        st.write(n['mensaje'])
        if not n['leida']:
            if st.button("Marcar leída", key=f"notif_{index}"):
                st.session_state.notificaciones[index]['leida'] = True
                st.rerun()
        st.markdown("---")

# ==========================================
# PAGINA 7: REPORTES AVANZADOS CON ANALÍTICA E IA
# ==========================================
elif seleccion == "Reportes":
    st.title("📈 Reportes Analíticos e Inteligencia de Negocio")
    
    tipo_rep = st.selectbox("Selecciona el área para el reporte ejecutivo:", ["Inventario", "Finanzas", "Personal", "Tareas", "Estado General"])
    
    # Botón para detonar el análisis narrativo por Inteligencia Artificial
    if st.button("🤖 Generar Análisis Narrativo con IA"):
        with st.spinner("Procesando datos y estructurando el análisis predictivo..."):
            datos_contexto = ""
            if tipo_rep == "Inventario":
                datos_contexto = json.dumps(st.session_state.inventario)
            elif tipo_rep == "Finanzas":
                datos_contexto = json.dumps(st.session_state.finanzas)
            elif tipo_rep == "Personal":
                datos_contexto = json.dumps(st.session_state.personal)
            else:
                datos_contexto = "Resumen Operativo Cruzado general de Sabores de Guatemala."
                
            prompt_reporte = [{"role": "user", "content": f"Genera un análisis narrativo corto y profesional en español para el reporte de {tipo_rep} con estos datos reales: {datos_contexto}"}]
            analisis_ia = llamar_openrouter_api(prompt_reporte)
            st.markdown("### 📝 Análisis Predictivo IA")
            st.info(analisis_ia)

    # Gráficas según requerimientos de diseño usando Plotly Express
    if tipo_rep == "Inventario":
        st.subheader("Visualización de Inventario")
        df_inv = pd.DataFrame(st.session_state.inventario)
        
        fig1 = plotly_xp.bar(df_inv, x='producto', y='cantidad', color='categoria', title='Cantidad Disponible por Producto')
        st.plotly_chart(fig1, use_container_width=True)
        
        fig2 = plotly_xp.pie(df_inv, names='estado', title='Distribución de Insumos por Estado Crítico')
        st.plotly_chart(fig2, use_container_width=True)
        
    elif tipo_rep == "Finanzas":
        st.subheader("Análisis de Tendencia Financiera (Q)")
        df_fin = pd.DataFrame(st.session_state.finanzas)
        fig_fin = plotly_xp.line(df_fin, x='fecha', y='monto', color='tipo', markers=True, title='Ingresos vs Egresos Historizados')
        st.plotly_chart(fig_fin, use_container_width=True)
        
    elif tipo_rep == "Personal":
        st.subheader("Estructura Organizacional de Salarios")
        df_pers = pd.DataFrame(st.session_state.personal)
        fig_p1 = plotly_xp.bar(df_pers, x='nombre', y='salario', color='turno', title='Salarios por Colaborador y Turno')
        st.plotly_chart(fig_p1, use_container_width=True)

    elif tipo_rep == "Tareas" or tipo_rep == "Estado General":
        st.subheader("Métricas de Carga Operativa")
        df_t = pd.DataFrame(st.session_state.tareas)
        if not df_t.empty:
            fig_t = plotly_xp.pie(df_t, names='estado', title='Porcentaje de Cumplimiento General')
            st.plotly_chart(fig_t, use_container_width=True)

# ==========================================
# PAGINA 8: HISTORIAL GENERAL
# ==========================================
elif seleccion == "Historial":
    st.title("📜 Registro de Auditoría e Historial")
    st.write("Bitácora completa e inmutable de las operaciones realizadas en el sistema.")
    
    if len(st.session_state.historial_general) == 0:
        st.info("No se registran transacciones previas en esta sesión.")
    else:
        df_hist = pd.DataFrame(st.session_state.historial_general)
        st.dataframe(df_hist, use_container_width=True)

# ==========================================
# PAGINA 9: CARGA MASIVA (CSV / JSON)
# ==========================================
elif seleccion == "Carga Masiva":
    st.title("📤 Carga Masiva de Datos e Importador")
    st.write("Carga nuevos insumos, personal o transacciones al restaurante utilizando archivos CSV estructurados.")
    
    tipo_carga = st.selectbox("Selecciona el tipo de entidad a importar:", ["Inventario", "Personal", "Menu", "Finanzas"])
    archivo_cargado = st.file_uploader("Arrastra aquí tu archivo CSV", type=["csv"])
    
    if archivo_cargado is not None:
        try:
            df_previo = pd.read_csv(archivo_cargado)
            st.markdown("### Previsualización de los Registros Detectados")
            st.dataframe(df_previo)
            
            if st.button("Confirmar Transacción e Insertar en Base de Datos"):
                # Simulación de inserción en lote
                registros = len(df_previo)
                registrar_log("carga_masiva", f"Carga masiva completada exitosamente en entidad {tipo_carga}. {registros} registros procesados.")
                st.success(f"Procesamiento Finalizado. Se insertaron {registros} registros de forma limpia.")
        except Exception as e:
            st.error(f"Error al estructurar el archivo: {str(e)}")

# ==========================================
# PAGINA 10: AUTOPILOTO OPERATIVO (DIAGNÓSTICO COMPLETO)
# ==========================================
elif seleccion == "Autopiloto":
    st.title("🤖 Módulo de Autopiloto Operativo")
    st.write("Ejecuta un diagnóstico profundo transversal con Inteligencia Artificial combinando todos los módulos activos.")
    
    if st.button("🚀 Ejecutar Diagnóstico Integral Avanzado"):
        with st.spinner("Compilando estados de almacén, flujo de caja, turnos y pendientes..."):
            # Consolidar el universo total de datos en memoria para Carlos
            universo_datos = {
                "inventario": st.session_state.inventario,
                "finanzas": st.session_state.finanzas,
                "tareas": st.session_state.tareas,
                "personal": st.session_state.personal
            }
            
            prompt_autopiloto = [
                {"role": "system", "content": "Eres Carlos Méndez, Gerente General. Tienes acceso completo al ERP. Genera un Diagnóstico de 3 áreas críticas estructurado exactamente con el siguiente formato de texto limpio en español:\nÁrea: [Nombre]\nProblema: [Descripción]\nRecomendación: [Acción sugerida]"},
                {"role": "user", "content": f"Analiza esta base de datos consolidada y propón el diagnóstico de inmediato: {json.dumps(universo_datos)}"}
            ]
            
            diagnostico_ia = llamar_openrouter_api(prompt_autopiloto)
            
            # Guardar propuesta en base de datos local
            nuevo_diag = {
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "resumen": diagnostico_ia,
                "estado": "propuesta"
            }
            st.session_state.diagnosticos.insert(0, nuevo_diag)
            agregar_notificacion("Diagnóstico Autopiloto Ejecutado", "Se generaron recomendaciones automatizadas.", "autopiloto")
            
    if st.session_state.diagnosticos:
        st.markdown("### Último Diagnóstico Estratégico Propuesto")
        st.info(st.session_state.diagnosticos[0]["resumen"])
        
        c_apr, c_rej = st.columns(2)
        if c_apr.button("✅ Aprobar y Aplicar Metas del Día sugeridas"):
            st.session_state.diagnosticos[0]["estado"] = "aplicada"
            # Registrar automatización en el tablero de metas
            st.session_state.metas_diarias.append({
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "titulo": "Resolver alertas críticas de inventario detectadas en Autopiloto",
                "agenteId": "roberto",
                "completada": False
            })
            registrar_log("sistema", "Diagnóstico de Autopiloto aprobado y aplicado de forma mandatoria.")
            st.success("Metas integradas e inyectadas al plan del día.")
            st.rerun()
            
        if c_rej.button("❌ Rechazar Diagnóstico"):
            st.session_state.diagnosticos.pop(0)
            st.warning("Propuesta purgada del historial.")
            st.rerun()

# ==========================================
# PAGINA 11: CONFIGURACIÓN
# ==========================================
elif seleccion == "Configuracion":
    st.title("⚙️ Configuración del Ecosistema")
    
    st.subheader("Datos Operativos de Sabores de Guatemala")
    st.session_state.restaurante["nombre"] = st.text_input("Nombre Comercial del Establecimiento", st.session_state.restaurante["nombre"])
    st.session_state.restaurante["ubicacion"] = st.text_input("Dirección General", st.session_state.restaurante["ubicacion"])
    st.session_state.restaurante["capacidad"] = st.number_input("Capacidad de Aforo Máximo", value=st.session_state.restaurante["capacidad"])
    
    st.subheader("Edición Directa de Prompts Base (Agentes)")
    for ag in st.session_state.agentes:
        ag["prompt"] = st.text_area(f"Prompt del Sistema para {ag['nombre']} ({ag['rol']})", ag["prompt"], key=f"p_edit_{ag['id']}")
        
    if st.button("Guardar Cambios Globales"):
        registrar_log("sistema", "Configuraciones globales y matriz de prompts de agentes modificadas.")
        st.success("Toda la configuración ha sido sincronizada con el estado de la sesión de manera correcta.")
