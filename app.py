import csv
import io
import json
import random
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st
from babel.dates import format_date

APP_TITLE = "Sabores de Guatemala"
DB_PATH = Path("sabores_guatemala.db")
TIME_FMT = "%Y-%m-%d %H:%M:%S"

ROLES = [
    "Gerente General",
    "Gerente de Operaciones",
    "Gerente de Compras e Inventario",
    "Gerente de Cocina",
    "Gerente de Servicio al Cliente",
    "Gerente Financiero",
    "Gerente de Marketing",
    "Gerente de RRHH",
]

TASK_STATES = ["pendiente", "en_progreso", "bloqueada", "completada"]
TASK_PRIORITIES = ["baja", "media", "alta", "critica"]
AGENT_STATES = ["activo", "inactivo", "ocupado"]
TABLE_STATES = ["disponible", "ocupada", "reservada", "fuera_servicio"]
NOTIF_TYPES = [
    "nueva_tarea",
    "inicio",
    "avance",
    "bloqueo",
    "finalizacion",
    "recordatorio",
    "sistema",
    "autopiloto",
]

SPANISH_WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def now_local() -> datetime:
    return datetime.now()


def fmt_dt(dt: datetime) -> str:
    return dt.strftime(TIME_FMT)


def parse_dt(value: str) -> datetime:
    return datetime.strptime(value, TIME_FMT)


def spanish_date(dt: Optional[datetime] = None) -> str:
    dt = dt or now_local()
    try:
        return format_date(dt, format="full", locale="es")
    except Exception:
        weekday = SPANISH_WEEKDAYS[dt.weekday()]
        return f"{weekday.capitalize()}, {dt.day:02d}/{dt.month:02d}/{dt.year}"


def money_q(value: float) -> str:
    return f"Q{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def exec_sql(query: str, params: Tuple = ()) -> None:
    conn = get_conn()
    with conn:
        conn.execute(query, params)
    conn.close()


def query_df(query: str, params: Tuple = ()) -> pd.DataFrame:
    conn = get_conn()
    try:
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()


def query_one(query: str, params: Tuple = ()) -> Optional[sqlite3.Row]:
    conn = get_conn()
    try:
        cur = conn.execute(query, params)
        return cur.fetchone()
    finally:
        conn.close()


def query_all(query: str, params: Tuple = ()) -> List[sqlite3.Row]:
    conn = get_conn()
    try:
        cur = conn.execute(query, params)
        return cur.fetchall()
    finally:
        conn.close()


def init_db() -> None:
    conn = get_conn()
    with conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS restaurantes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                ubicacion TEXT NOT NULL,
                tipo TEXT NOT NULL,
                capacidad INTEGER NOT NULL,
                mesas INTEGER NOT NULL,
                horarioApertura TEXT NOT NULL,
                horarioCierre TEXT NOT NULL,
                diasOperacion TEXT NOT NULL,
                logo TEXT,
                descripcion TEXT
            );

            CREATE TABLE IF NOT EXISTS agentes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                rol TEXT NOT NULL,
                funcion TEXT NOT NULL,
                prompt TEXT NOT NULL,
                estado TEXT NOT NULL,
                avatar TEXT,
                color TEXT NOT NULL,
                orden INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agenteId INTEGER NOT NULL,
                usuarioId TEXT,
                titulo TEXT,
                ultimoMensaje TEXT,
                ultimaActividad TEXT,
                FOREIGN KEY (agenteId) REFERENCES agentes(id)
            );
            CREATE INDEX IF NOT EXISTS by_agente ON conversaciones(agenteId);

            CREATE TABLE IF NOT EXISTS mensajes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversacionId INTEGER NOT NULL,
                rol TEXT NOT NULL,
                contenido TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                taskCreated INTEGER DEFAULT 0,
                FOREIGN KEY (conversacionId) REFERENCES conversaciones(id)
            );
            CREATE INDEX IF NOT EXISTS by_conversacion ON mensajes(conversacionId);

            CREATE TABLE IF NOT EXISTS tareas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                responsableId INTEGER,
                prioridad TEXT NOT NULL,
                estado TEXT NOT NULL,
                fechaCreacion TEXT NOT NULL,
                fechaLimite TEXT,
                observaciones TEXT,
                parentTaskId INTEGER,
                dependencias TEXT,
                autopilotoTo TEXT,
                conversacionId INTEGER
            );
            CREATE INDEX IF NOT EXISTS by_responsable ON tareas(responsableId);
            CREATE INDEX IF NOT EXISTS by_estado ON tareas(estado);
            CREATE INDEX IF NOT EXISTS by_prioridad ON tareas(prioridad);

            CREATE TABLE IF NOT EXISTS historialTareas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tareaId INTEGER NOT NULL,
                campo TEXT NOT NULL,
                valorAnterior TEXT,
                valorNuevo TEXT NOT NULL,
                usuario TEXT,
                timestamp TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS by_tarea ON historialTareas(tareaId);

            CREATE TABLE IF NOT EXISTS notificaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                mensaje TEXT NOT NULL,
                tipo TEXT NOT NULL,
                leida INTEGER DEFAULT 0,
                tareaId INTEGER,
                agenteId INTEGER,
                timestamp TEXT NOT NULL,
                emailEnviado INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS by_leida ON notificaciones(leida);

            CREATE TABLE IF NOT EXISTS metasDiarias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                titulo TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                agenteId INTEGER,
                completada INTEGER DEFAULT 0,
                autoGenerada INTEGER DEFAULT 0,
                tareas TEXT
            );
            CREATE INDEX IF NOT EXISTS by_fecha_metas ON metasDiarias(fecha);

            CREATE TABLE IF NOT EXISTS diagnosticos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                resumen TEXT NOT NULL,
                areas TEXT NOT NULL,
                metasGeneradas INTEGER DEFAULT 0,
                tareasGeneradas INTEGER DEFAULT 0,
                estado TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS by_fecha_diagnosticos ON diagnosticos(fecha);

            CREATE TABLE IF NOT EXISTS inventario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto TEXT NOT NULL,
                categoria TEXT NOT NULL,
                unidad TEXT NOT NULL,
                cantidad REAL NOT NULL,
                costoUnitario REAL NOT NULL,
                proveedor TEXT,
                stockMinimo REAL NOT NULL,
                estado TEXT NOT NULL,
                ultimaActualizacion TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS by_estado_inventario ON inventario(estado);

            CREATE TABLE IF NOT EXISTS finanzas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                tipo TEXT NOT NULL,
                categoria TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                monto REAL NOT NULL,
                responsable TEXT
            );
            CREATE INDEX IF NOT EXISTS by_fecha_finanzas ON finanzas(fecha);
            CREATE INDEX IF NOT EXISTS by_tipo_finanzas ON finanzas(tipo);

            CREATE TABLE IF NOT EXISTS menu (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                categoria TEXT NOT NULL,
                precio REAL NOT NULL,
                costoEstimado REAL NOT NULL,
                disponible INTEGER DEFAULT 1,
                descripcion TEXT,
                imagen TEXT
            );
            CREATE INDEX IF NOT EXISTS by_categoria_menu ON menu(categoria);

            CREATE TABLE IF NOT EXISTS personal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                puesto TEXT NOT NULL,
                turno TEXT NOT NULL,
                salario REAL NOT NULL,
                estado TEXT NOT NULL,
                fechaIngreso TEXT,
                contacto TEXT
            );
            CREATE INDEX IF NOT EXISTS by_estado_personal ON personal(estado);

            CREATE TABLE IF NOT EXISTS mesas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero INTEGER NOT NULL,
                ubicacion TEXT NOT NULL,
                capacidad INTEGER NOT NULL,
                estado TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS by_estado_mesas ON mesas(estado);

            CREATE TABLE IF NOT EXISTS cargasMasivas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                archivo TEXT,
                estado TEXT NOT NULL,
                registrosTotales INTEGER NOT NULL,
                registrosProcesados INTEGER NOT NULL,
                errores TEXT,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS historialGeneral (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                entidadTipo TEXT,
                entidadId TEXT,
                usuario TEXT,
                timestamp TEXT NOT NULL,
                metadata TEXT
            );
            CREATE INDEX IF NOT EXISTS by_tipo_historial ON historialGeneral(tipo);
            """
        )
    conn.close()


def table_has_rows(table: str) -> bool:
    row = query_one(f"SELECT COUNT(*) AS c FROM {table}")
    return bool(row and row["c"] > 0)


def log_general(tipo: str, descripcion: str, entidad_tipo: Optional[str] = None, entidad_id: Optional[str] = None, usuario: Optional[str] = None, metadata: Optional[dict] = None) -> None:
    exec_sql(
        "INSERT INTO historialGeneral (tipo, descripcion, entidadTipo, entidadId, usuario, timestamp, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            tipo,
            descripcion,
            entidad_tipo,
            entidad_id,
            usuario,
            fmt_dt(now_local()),
            json.dumps(metadata or {}, ensure_ascii=False),
        ),
    )


def seed_if_needed() -> None:
    if table_has_rows("restaurantes"):
        return

    exec_sql(
        "INSERT INTO restaurantes (nombre, ubicacion, tipo, capacidad, mesas, horarioApertura, horarioCierre, diasOperacion, logo, descripcion) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "Sabores de Guatemala",
            "Zona 10, Ciudad de Guatemala",
            "Comida guatemalteca",
            80,
            15,
            "09:00",
            "22:00",
            "Lunes a domingo",
            None,
            "Sistema de gerencia inteligente para un restaurante guatemalteco con enfoque en operaciones, finanzas, personal y atención al cliente.",
        ),
    )

    agents = [
        ("Carlos Mendez", "Gerente General", "Coordina todas las áreas", "Coordina todas las áreas. Conoce a cada gerente. Responde profesional y amigable.", "activo", "CM", "#1a6b4a", 1),
        ("Ana López", "Gerente de Operaciones", "Apertura, cierre, turnos, logística", "Apertura, cierre, turnos y logística del restaurante. Responde con foco operativo.", "activo", "AL", "#2563eb", 2),
        ("Roberto Soto", "Gerente de Compras e Inventario", "Inventario, compras, proveedores", "Gestiona inventario, compras y proveedores con enfoque preventivo.", "activo", "RS", "#7c3aed", 3),
        ("María Ajú", "Gerente de Cocina", "Producción, calidad, tiempos", "Supervisa producción, calidad, tiempos y consistencia de platillos.", "activo", "MA", "#dc2626", 4),
        ("Pedro Tzul", "Gerente de Servicio al Cliente", "Atención, quejas, reservas", "Atiende reservas, quejas y experiencia del cliente con calidez.", "activo", "PT", "#0891b2", 5),
        ("Lucía Gramajo", "Gerente Financiero", "Caja, gastos, presupuestos", "Controla caja, gastos, presupuestos y utilidad con precisión.", "activo", "LG", "#059669", 6),
        ("Diego Herrera", "Gerente de Marketing", "Publicidad, redes, promociones", "Impulsa publicidad, redes sociales y promociones con creatividad.", "activo", "DH", "#d97706", 7),
        ("Isabel Pérez", "Gerente de RRHH", "Personal, contrataciones, horarios", "Gestiona personal, contrataciones, turnos y clima laboral.", "activo", "IP", "#be185d", 8),
    ]
    for a in agents:
        exec_sql(
            "INSERT INTO agentes (nombre, rol, funcion, prompt, estado, avatar, color, orden) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            a,
        )

    inventory_seed = [
        ("Tomate", "Verduras", "lb", 8, 3.50, "Mercado La Terminal", 15, "critico"),
        ("Cebolla", "Verduras", "lb", 10, 2.20, "Mercado La Terminal", 18, "bajo"),
        ("Arroz", "Granos", "lb", 40, 4.10, "Distribuidora Centro", 20, "suficiente"),
        ("Frijoles negros", "Granos", "lb", 25, 5.25, "Distribuidora Centro", 15, "suficiente"),
        ("Aceite vegetal", "Insumos", "lt", 30, 18.0, "Mayorista del Centro", 12, "suficiente"),
        ("Pollo entero", "Proteinas", "unidad", 18, 48.0, "Avicola Guatemala", 10, "suficiente"),
        ("Res molida", "Proteinas", "lb", 7, 32.0, "Carnes del Valle", 12, "bajo"),
        ("Tortillas de maiz", "Panaderia", "docena", 50, 8.5, "Tortilleria Doña Luisa", 25, "suficiente"),
        ("Chiles pimientos", "Verduras", "lb", 6, 6.75, "Mercado La Terminal", 10, "bajo"),
        ("Sal", "Insumos", "lb", 24, 1.5, "Mayorista del Centro", 8, "suficiente"),
    ]
    for p, c, u, cant, costo, prov, stock, estado in inventory_seed:
        exec_sql(
            "INSERT INTO inventario (producto, categoria, unidad, cantidad, costoUnitario, proveedor, stockMinimo, estado, ultimaActualizacion) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (p, c, u, cant, costo, prov, stock, estado, fmt_dt(now_local())),
        )

    menu_seed = [
        ("Pepián de pollo", "Plato fuerte", 65, 26, 1, "Clásico guatemalteco con pollo.", None),
        ("Kak'ik", "Plato fuerte", 70, 28, 1, "Sopa tradicional de alta cocina regional.", None),
        ("Hilachas", "Plato fuerte", 60, 24, 1, "Carne deshebrada con salsa de tomate.", None),
        ("Jocon", "Plato fuerte", 65, 25, 1, "Pollo en salsa verde.", None),
        ("Frijoles volteados", "Acompañamiento", 25, 9, 1, "Frijoles cremosos tradicionales.", None),
        ("Tamales colorados", "Antojito", 15, 5, 1, "Tamal rojo guatemalteco.", None),
        ("Chuchitos", "Antojito", 12, 4, 1, "Masa con salsa y carne.", None),
        ("Ensalada guatemalteca", "Entrada", 35, 12, 1, "Vegetales frescos con toque local.", None),
        ("Limonada", "Bebida", 20, 6, 1, "Refrescante y natural.", None),
        ("Atol de elote", "Bebida", 18, 5, 1, "Tradición dulce y caliente.", None),
        ("Café", "Bebida", 15, 3, 1, "Café nacional.", None),
        ("Tres leches", "Postre", 30, 11, 1, "Postre cremoso y ligero.", None),
    ]
    for row in menu_seed:
        exec_sql(
            "INSERT INTO menu (nombre, categoria, precio, costoEstimado, disponible, descripcion, imagen) VALUES (?, ?, ?, ?, ?, ?, ?)",
            row,
        )

    personnel_seed = [
        ("Juan Pérez", "Chef", "Noche", 5500, "activo", "2024-08-10", "5555-1001"),
        ("Luis García", "Sous Chef", "Día", 4200, "activo", "2024-09-15", "5555-1002"),
        ("María López", "Mesera", "Día", 3200, "activo", "2024-10-01", "5555-1003"),
        ("Carmen Díaz", "Mesera", "Noche", 3200, "vacaciones", "2024-10-20", "5555-1004"),
        ("Pedro Ramírez", "Cajero", "Día", 3600, "activo", "2024-11-05", "5555-1005"),
        ("Andrea Morales", "Hostess", "Día", 3000, "activo", "2024-11-12", "5555-1006"),
        ("Miguel Torres", "Lavaplatos", "Noche", 2400, "activo", "2024-12-01", "5555-1007"),
        ("Ricardo Castillo", "Bartender", "Noche", 3800, "activo", "2024-12-08", "5555-1008"),
    ]
    for row in personnel_seed:
        exec_sql(
            "INSERT INTO personal (nombre, puesto, turno, salario, estado, fechaIngreso, contacto) VALUES (?, ?, ?, ?, ?, ?, ?)",
            row,
        )

    tables_seed = [
        (1, "Interior", 4, "disponible"),
        (2, "Interior", 4, "ocupada"),
        (3, "Interior", 6, "disponible"),
        (4, "Interior", 2, "reservada"),
        (5, "Interior", 2, "disponible"),
        (6, "Interior", 8, "ocupada"),
        (7, "Terraza", 4, "disponible"),
        (8, "Terraza", 4, "reservada"),
        (9, "Terraza", 6, "disponible"),
        (10, "Terraza", 2, "disponible"),
        (11, "VIP", 6, "disponible"),
        (12, "VIP", 8, "reservada"),
        (13, "Barra", 2, "ocupada"),
        (14, "Barra", 2, "disponible"),
        (15, "Exterior", 4, "fuera_servicio"),
    ]
    for n, loc, cap, state in tables_seed:
        exec_sql("INSERT INTO mesas (numero, ubicacion, capacidad, estado) VALUES (?, ?, ?, ?)", (n, loc, cap, state))

    # Financial seed: December 2024
    fin_rows = [
        ("2024-12-01", "ingreso", "Ventas", "Ventas del día", 2800, "Caja"),
        ("2024-12-02", "ingreso", "Ventas", "Ventas del día", 3250, "Caja"),
        ("2024-12-03", "ingreso", "Ventas", "Ventas del día", 4100, "Caja"),
        ("2024-12-04", "ingreso", "Ventas", "Ventas del día", 4500, "Caja"),
        ("2024-12-05", "egreso", "Insumos", "Compra de insumos", 1250, "Roberto Soto"),
        ("2024-12-06", "egreso", "Nómina", "Pago parcial de nómina", 8200, "Lucía Gramajo"),
        ("2024-12-07", "egreso", "Servicios", "Electricidad y agua", 1450, "Lucía Gramajo"),
        ("2024-12-08", "ingreso", "Ventas", "Ventas del día", 3650, "Caja"),
    ]
    for row in fin_rows:
        exec_sql("INSERT INTO finanzas (fecha, tipo, categoria, descripcion, monto, responsable) VALUES (?, ?, ?, ?, ?, ?)", row)

    today = fmt_dt(now_local())
    task_rows = [
        ("Revisar apertura de cocina", "Verificar insumos críticos antes del servicio.", 4, "alta", "en_progreso", today, (now_local() + timedelta(days=1)).strftime("%Y-%m-%d"), "Primera revisión del día", None, json.dumps(["inventario", "produccion"]), None, None),
        ("Actualizar reservas VIP", "Confirmar reservas de la noche.", 5, "media", "pendiente", today, (now_local() + timedelta(days=1)).strftime("%Y-%m-%d"), None, None, json.dumps([]), None, None),
        ("Auditar caja del cierre", "Comparar ventas y egresos del turno.", 6, "critica", "bloqueada", today, (now_local() + timedelta(days=1)).strftime("%Y-%m-%d"), "Esperando reporte de ventas", None, json.dumps(["finanzas"]), None, None),
        ("Reabastecer tomate", "Comprar tomate para evitar ruptura de stock.", 3, "critica", "pendiente", today, (now_local() + timedelta(days=1)).strftime("%Y-%m-%d"), None, None, json.dumps(["proveedor"]), None, None),
        ("Actualizar menú en redes", "Publicar especialidades de fin de semana.", 7, "media", "completada", today, None, None, None, json.dumps([]), None, None),
    ]
    for row in task_rows:
        exec_sql(
            "INSERT INTO tareas (titulo, descripcion, responsableId, prioridad, estado, fechaCreacion, fechaLimite, observaciones, parentTaskId, dependencias, autopilotoTo, conversacionId) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )

    goals = [
        (today[:10], "Mantener servicio fluido", "Reducir tiempos de espera y asegurar mesas disponibles.", 2, 0, 0, json.dumps([1, 2, 3])),
        (today[:10], "Proteger inventario crítico", "Revisar tomate, cebolla y res molida.", 3, 0, 0, json.dumps([3, 4])),
    ]
    for row in goals:
        exec_sql("INSERT INTO metasDiarias (fecha, titulo, descripcion, agenteId, completada, autoGenerada, tareas) VALUES (?, ?, ?, ?, ?, ?, ?)", row)

    notifications = [
        ("Nueva tarea crítica", "Se creó una tarea crítica para reabastecer tomate.", "nueva_tarea", 0, 4, 3, today, 0),
        ("Bloqueo en finanzas", "La auditoría de caja está bloqueada por reporte pendiente.", "bloqueo", 0, 3, 6, today, 0),
        ("Resumen del sistema", "Se cargaron los datos semilla iniciales.", "sistema", 1, None, None, today, 0),
    ]
    for row in notifications:
        exec_sql("INSERT INTO notificaciones (titulo, mensaje, tipo, leida, tareaId, agenteId, timestamp, emailEnviado) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", row)

    diag_areas = [
        {"area": "Inventario", "estado": "alerta", "problemas": ["Tomate crítico", "Cebolla bajo", "Res molida bajo"], "recomendaciones": ["Comprar hoy tomate y cebolla", "Programar orden de res"]},
        {"area": "Finanzas", "estado": "estable", "problemas": ["Egresos altos en nómina"], "recomendaciones": ["Revisar costo laboral por turno"]},
        {"area": "Personal", "estado": "estable", "problemas": ["1 colaborador en vacaciones"], "recomendaciones": ["Cubrir turno con apoyo temporal"]},
    ]
    exec_sql(
        "INSERT INTO diagnosticos (fecha, resumen, areas, metasGeneradas, tareasGeneradas, estado) VALUES (?, ?, ?, ?, ?, ?)",
        (today, "Diagnóstico inicial con alertas operativas y de inventario.", json.dumps(diag_areas, ensure_ascii=False), 2, 3, "aplicada"),
    )

    exec_sql(
        "INSERT INTO conversaciones (agenteId, usuarioId, titulo, ultimoMensaje, ultimaActividad) VALUES (?, ?, ?, ?, ?)",
        (1, "admin", "Arranque operativo", "Listo para gestionar el restaurante.", today),
    )
    conv_id = query_one("SELECT id FROM conversaciones ORDER BY id DESC LIMIT 1")["id"]
    exec_sql(
        "INSERT INTO mensajes (conversacionId, rol, contenido, timestamp, taskCreated) VALUES (?, ?, ?, ?, ?)",
        (conv_id, "assistant", "Listo para apoyar la gerencia general.", today, 0),
    )

    log_general("sistema", "Se ejecutó el seed inicial de Sabores de Guatemala.")


@st.cache_data(show_spinner=False)
def load_agents() -> pd.DataFrame:
    return query_df("SELECT * FROM agentes ORDER BY orden ASC")


@st.cache_data(show_spinner=False)
def load_restaurante() -> pd.DataFrame:
    return query_df("SELECT * FROM restaurantes LIMIT 1")


def invalidate_caches() -> None:
    load_agents.clear()
    load_restaurante.clear()


def build_contexto_restaurante(agent_role: str) -> Dict[str, Any]:
    restaurante = query_one("SELECT * FROM restaurantes LIMIT 1")
    total_inventario = query_df("SELECT * FROM inventario")
    fin = query_df("SELECT * FROM finanzas")
    tareas = query_df("SELECT * FROM tareas")
    mesas = query_df("SELECT * FROM mesas")
    personal = query_df("SELECT * FROM personal")
    metas = query_df("SELECT * FROM metasDiarias WHERE fecha = ?", (date.today().isoformat(),))
    notifications = query_df("SELECT * FROM notificaciones ORDER BY timestamp DESC LIMIT 10")
    recent_diag = query_df("SELECT * FROM diagnosticos ORDER BY fecha DESC LIMIT 3")

    base = {
        "restaurante": dict(restaurante) if restaurante else {},
        "inventario": total_inventario.to_dict(orient="records"),
        "finanzas": fin.to_dict(orient="records"),
        "tareas": tareas.to_dict(orient="records"),
        "mesas": mesas.to_dict(orient="records"),
        "personal": personal.to_dict(orient="records"),
        "metas": metas.to_dict(orient="records"),
        "notificaciones": notifications.to_dict(orient="records"),
        "diagnosticos": recent_diag.to_dict(orient="records"),
    }

    role = agent_role.lower()
    if "general" in role:
        return base
    if "operaciones" in role:
        return {"restaurante": base["restaurante"], "mesas": base["mesas"], "personal": base["personal"], "metas": base["metas"], "tareas": base["tareas"]}
    if "inventario" in role or "compras" in role:
        return {"inventario": base["inventario"], "finanzas": [x for x in base["finanzas"] if x["categoria"].lower() == "insumos"], "tareas": base["tareas"]}
    if "cocina" in role:
        menu = query_df("SELECT * FROM menu WHERE disponible = 1")
        return {"inventario": base["inventario"], "menu": menu.to_dict(orient="records"), "tareas": base["tareas"]}
    if "servicio" in role:
        menu = query_df("SELECT * FROM menu WHERE disponible = 1")
        return {"mesas": base["mesas"], "menu": menu.to_dict(orient="records"), "tareas": base["tareas"]}
    if "financ" in role:
        grouped = fin.groupby(["tipo", "categoria"], as_index=False)["monto"].sum() if not fin.empty else pd.DataFrame()
        return {"finanzas": base["finanzas"], "resumen": grouped.to_dict(orient="records") if not grouped.empty else [], "tareas": base["tareas"]}
    if "marketing" in role:
        menu = query_df("SELECT * FROM menu WHERE disponible = 1")
        daily = fin.groupby("fecha", as_index=False)["monto"].sum() if not fin.empty else pd.DataFrame()
        return {"menu": menu.to_dict(orient="records"), "ingresos_por_dia": daily.to_dict(orient="records") if not daily.empty else [], "metas": base["metas"]}
    if "rrhh" in role:
        payroll = personal.groupby("estado", as_index=False)["salario"].sum() if not personal.empty else pd.DataFrame()
        return {"personal": base["personal"], "nomina": payroll.to_dict(orient="records") if not payroll.empty else [], "tareas": base["tareas"]}
    return base


def heuristic_ai_response(messages: List[Dict[str, str]], system_prompt: str, agente_rol: str) -> str:
    ctx = build_contexto_restaurante(agente_rol)
    ult_msg = messages[-1]["content"] if messages else ""
    if "gerente general" in agente_rol.lower():
        inv = pd.DataFrame(ctx["inventario"])
        low = inv[inv["estado"].isin(["bajo", "critico"])] if not inv.empty else pd.DataFrame()
        fin = pd.DataFrame(ctx["finanzas"])
        ingresos = fin[fin["tipo"] == "ingreso"]["monto"].sum() if not fin.empty else 0
        egresos = fin[fin["tipo"] == "egreso"]["monto"].sum() if not fin.empty else 0
        utilidad = ingresos - egresos
        tasks = pd.DataFrame(ctx["tareas"])
        crit = tasks[(tasks["prioridad"] == "critica") & (tasks["estado"] != "completada")] if not tasks.empty else pd.DataFrame()
        parts = [
            f"Situación general: el restaurante opera con base estable, aunque hay frentes que exigen seguimiento inmediato. Ingresos acumulados: {money_q(float(ingresos))}; egresos: {money_q(float(egresos))}; utilidad estimada: {money_q(float(utilidad))}.",
            f"Puntos de atención: {', '.join(low['producto'].tolist()) if not low.empty else 'sin alertas críticas de inventario en este momento'}. {len(crit)} tarea(s) crítica(s) siguen activas.",
            f"Recomendación: priorizar compras de insumos críticos, destrabar tareas bloqueadas y revisar cobertura de turnos antes del cierre.",
        ]
        return "\n\n".join(parts[:4])
    if "inventario" in agente_rol.lower() or "compras" in agente_rol.lower():
        low = [x["producto"] for x in ctx["inventario"] if x["estado"] in {"bajo", "critico"}]
        return f"Inventario bajo vigilancia. Productos en alerta: {', '.join(low) if low else 'ninguno'}. Recomiendo revisar compras hoy mismo y priorizar reposición de los artículos críticos. Mensaje del usuario: {ult_msg}"
    if "cocina" in agente_rol.lower():
        return "La cocina debe sostener calidad y tiempos. Verifica insumos críticos, confirma mise en place y ajusta producción según la demanda prevista."
    if "financ" in agente_rol.lower():
        return "La lectura financiera debe enfocarse en ventas, egresos y utilidad por categoría. Recomiendo vigilar nómina e insumos para proteger margen."
    if "rrhh" in agente_rol.lower():
        return "RRHH debe validar cobertura de turnos, vacaciones y cualquier vacío operativo. Sugiero revisar la nómina y redistribuir turnos si hace falta."
    if "marketing" in agente_rol.lower():
        return "Marketing puede impulsar platos con mayor margen y reforzar promociones digitales con foco en horario pico y productos estrella."
    return f"Entendido. Tomo en cuenta el contexto del restaurante y el mensaje: {ult_msg}"


def maybe_call_external_ai(messages: List[Dict[str, str]], system_prompt: str, agente_rol: str) -> str:
    api_url = st.secrets.get("HERCULES_API_URL", "").strip()
    api_key = st.secrets.get("HERCULES_API_KEY", "").strip()
    model = st.secrets.get("HERCULES_MODEL", "openai/gpt-5-mini")

    if not api_url or not api_key:
        return heuristic_ai_response(messages, system_prompt, agente_rol)

    try:
        import requests

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "system", "content": json.dumps(build_contexto_restaurante(agente_rol), ensure_ascii=False)},
                *messages,
            ],
            "temperature": 0.4,
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        r = requests.post(api_url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            if "choices" in data and data["choices"]:
                choice = data["choices"][0]
                if isinstance(choice, dict):
                    return choice.get("message", {}).get("content") or choice.get("text") or heuristic_ai_response(messages, system_prompt, agente_rol)
            if "content" in data:
                return str(data["content"])
        return heuristic_ai_response(messages, system_prompt, agente_rol)
    except Exception:
        return heuristic_ai_response(messages, system_prompt, agente_rol)


def detect_task_from_text(text: str) -> Optional[Tuple[str, str, str]]:
    lower = text.lower()
    keywords = ["tarea", "pendiente", "hacer", "comprar", "revisar", "coordinar", "actualizar", "llamar", "confirmar", "auditar", "resolver", "aplicar", "crear"]
    if any(k in lower for k in keywords) and len(text) > 25:
        title = text.strip().split(".")[0][:70]
        return (title if title else "Tarea desde chat", text.strip(), "media")
    return None


def add_notification(titulo: str, mensaje: str, tipo: str, tarea_id: Optional[int] = None, agente_id: Optional[int] = None, leida: int = 0) -> None:
    exec_sql(
        "INSERT INTO notificaciones (titulo, mensaje, tipo, leida, tareaId, agenteId, timestamp, emailEnviado) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (titulo, mensaje, tipo, leida, tarea_id, agente_id, fmt_dt(now_local()), 0),
    )


def add_history(task_id: int, field: str, old: Any, new: Any, user: str = "Sistema") -> None:
    exec_sql(
        "INSERT INTO historialTareas (tareaId, campo, valorAnterior, valorNuevo, usuario, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (task_id, field, None if old is None else str(old), str(new), user, fmt_dt(now_local())),
    )


def get_sidebar_unread_count() -> int:
    row = query_one("SELECT COUNT(*) AS c FROM notificaciones WHERE leida = 0")
    return int(row["c"] if row else 0)


def page_dashboard() -> None:
    st.title(APP_TITLE)
    st.caption(f"Zona 10, Ciudad de Guatemala · {spanish_date()}")
    rest = query_one("SELECT * FROM restaurantes LIMIT 1")
    agents = load_agents()

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Informe ejecutivo del Gerente General")
        if "dashboard_report" not in st.session_state:
            st.session_state.dashboard_report = maybe_call_external_ai(
                [{"role": "user", "content": "Genera un informe ejecutivo del restaurante."}],
                "Eres Carlos Mendez, Gerente General.",
                "Gerente General",
            )
        st.markdown(st.session_state.dashboard_report)
        if st.button("Refrescar informe", use_container_width=True):
            st.session_state.dashboard_report = maybe_call_external_ai(
                [{"role": "user", "content": "Actualiza el informe ejecutivo del restaurante."}],
                "Eres Carlos Mendez, Gerente General.",
                "Gerente General",
            )
            st.rerun()
        if st.link_button("Hablar con Carlos", "?page=chat&agente=1"):
            pass

    with col2:
        if rest is not None:
            st.metric("Capacidad", rest["capacidad"])
            st.metric("Mesas", rest["mesas"])
        st.metric("Gerentes", len(agents))
        st.metric("No leídas", get_sidebar_unread_count())

    tasks = query_df("SELECT * FROM tareas")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Pendientes", int((tasks["estado"] == "pendiente").sum()) if not tasks.empty else 0)
    k2.metric("En progreso", int((tasks["estado"] == "en_progreso").sum()) if not tasks.empty else 0)
    k3.metric("Bloqueadas", int((tasks["estado"] == "bloqueada").sum()) if not tasks.empty else 0)
    k4.metric("Completadas", int((tasks["estado"] == "completada").sum()) if not tasks.empty else 0)

    st.divider()
    left, right = st.columns(2)
    with left:
        st.subheader("Metas del día")
        metas = query_df("SELECT m.*, a.nombre AS agenteNombre FROM metasDiarias m LEFT JOIN agentes a ON a.id = m.agenteId WHERE fecha = ? ORDER BY id DESC", (date.today().isoformat(),))
        for _, row in metas.iterrows():
            label = f"{'✅' if row['completada'] else '⬜'} {row['titulo']}"
            with st.expander(label, expanded=False):
                st.write(row["descripcion"])
                st.caption(f"Agente: {row['agenteNombre'] or 'Sin asignar'}")
                st.caption(f"Tareas vinculadas: {row['tareas'] or '[]'}")
    with right:
        st.subheader("Tareas críticas activas")
        crit = query_df("SELECT t.*, a.nombre AS responsableNombre FROM tareas t LEFT JOIN agentes a ON a.id = t.responsableId WHERE t.prioridad = 'critica' AND t.estado != 'completada' ORDER BY t.fechaCreacion DESC")
        if crit.empty:
            st.info("No hay tareas críticas activas.")
        else:
            st.dataframe(crit[["titulo", "responsableNombre", "estado", "fechaLimite"]], use_container_width=True, hide_index=True)

    st.subheader("Estado del equipo")
    grid = st.columns(4)
    for i, (_, ag) in enumerate(agents.iterrows()):
        with grid[i % 4]:
            active_tasks = query_one("SELECT COUNT(*) AS c FROM tareas WHERE responsableId = ? AND estado != 'completada'", (int(ag["id"]),))
            st.markdown(f"**{ag['nombre']}**")
            st.caption(ag["rol"])
            st.write(f"Estado: {ag['estado']}")
            st.write(f"Tareas activas: {active_tasks['c'] if active_tasks else 0}")

    st.subheader("Resumen financiero")
    fin = query_df("SELECT * FROM finanzas")
    ingresos = float(fin[fin["tipo"] == "ingreso"]["monto"].sum()) if not fin.empty else 0
    egresos = float(fin[fin["tipo"] == "egreso"]["monto"].sum()) if not fin.empty else 0
    utilidad = ingresos - egresos
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", money_q(ingresos))
    c2.metric("Egresos", money_q(egresos))
    c3.metric("Utilidad", money_q(utilidad))

    st.subheader("Alertas de inventario")
    inv = query_df("SELECT * FROM inventario WHERE estado IN ('bajo', 'critico') ORDER BY CASE estado WHEN 'critico' THEN 1 ELSE 2 END, producto")
    if inv.empty:
        st.success("Inventario sin alertas.")
    else:
        st.dataframe(inv[["producto", "cantidad", "stockMinimo", "estado", "proveedor"]], use_container_width=True, hide_index=True)

    st.subheader("Últimas notificaciones")
    notif = query_df("SELECT * FROM notificaciones ORDER BY timestamp DESC LIMIT 8")
    if notif.empty:
        st.info("Sin notificaciones recientes.")
    else:
        st.dataframe(notif[["titulo", "tipo", "leida", "timestamp"]], use_container_width=True, hide_index=True)


def page_agentes() -> None:
    st.header("Agentes")
    agents = load_agents()
    cols = st.columns(2)
    for idx, (_, ag) in enumerate(agents.iterrows()):
        with cols[idx % 2]:
            with st.container(border=True):
                st.markdown(f"### {ag['avatar'] or ag['nombre'][0]}")
                st.write(f"**{ag['nombre']}**")
                st.caption(f"{ag['rol']} · {ag['funcion']}")
                st.write(f"Estado actual: `{ag['estado']}`")
                new_state = st.selectbox(
                    "Cambiar estado",
                    AGENT_STATES,
                    index=AGENT_STATES.index(ag["estado"]) if ag["estado"] in AGENT_STATES else 0,
                    key=f"state_{ag['id']}",
                )
                if new_state != ag["estado"] and st.button("Guardar estado", key=f"save_{ag['id']}", use_container_width=True):
                    exec_sql("UPDATE agentes SET estado = ? WHERE id = ?", (new_state, int(ag["id"])))
                    log_general("agente", f"Estado del agente {ag['nombre']} cambiado a {new_state}.", "agente", str(int(ag["id"])), "usuario")
                    invalidate_caches()
                    st.rerun()
                if st.button("Ir al chat", key=f"chat_{ag['id']}", use_container_width=True):
                    st.query_params["page"] = "chat"
                    st.query_params["agente"] = str(int(ag["id"]))
                    st.rerun()


def get_or_create_conversation(agent_id: int, title_hint: str = "Chat activo") -> int:
    row = query_one("SELECT id FROM conversaciones WHERE agenteId = ? ORDER BY ultimaActividad DESC, id DESC LIMIT 1", (agent_id,))
    if row:
        return int(row["id"])
    exec_sql(
        "INSERT INTO conversaciones (agenteId, usuarioId, titulo, ultimoMensaje, ultimaActividad) VALUES (?, ?, ?, ?, ?)",
        (agent_id, "admin", title_hint, None, fmt_dt(now_local())),
    )
    return int(query_one("SELECT id FROM conversaciones ORDER BY id DESC LIMIT 1")["id"])


def page_chat() -> None:
    st.header("Chat")
    agents = load_agents()
    query_agent = st.query_params.get("agente")
    agent_id_default = int(query_agent) if query_agent and str(query_agent).isdigit() else int(agents.iloc[0]["id"])
    agent_names = {int(r.id): f"{r.nombre} · {r.rol}" for _, r in agents.iterrows()}
    selected_agent_id = st.sidebar.selectbox("Agente", list(agent_names.keys()), index=list(agent_names.keys()).index(agent_id_default) if agent_id_default in agent_names else 0, format_func=lambda x: agent_names[x], key="chat_agent_select")
    agent = query_one("SELECT * FROM agentes WHERE id = ?", (selected_agent_id,))
    convs = query_df("SELECT * FROM conversaciones WHERE agenteId = ? ORDER BY ultimaActividad DESC", (selected_agent_id,))
    conv_id = get_or_create_conversation(selected_agent_id, f"Conversación con {agent['nombre']}")

    top_l, top_r = st.columns([2, 1])
    with top_l:
        st.subheader(f"Historial con {agent['nombre']}")
        if not convs.empty:
            conv_choice = st.selectbox("Conversaciones previas", convs["id"].tolist(), format_func=lambda cid: f"#{cid} · {convs.loc[convs['id']==cid, 'titulo'].iloc[0] if not convs.loc[convs['id']==cid].empty else 'Sin título'}", key="conversation_choice")
            conv_id = int(conv_choice)
        msgs = query_df("SELECT * FROM mensajes WHERE conversacionId = ? ORDER BY id ASC", (conv_id,))
        box = st.container(border=True)
        with box:
            for _, m in msgs.iterrows():
                st.markdown(f"**{m['rol'].capitalize()}** · {m['timestamp']}")
                st.write(m["contenido"])
                st.divider()
    with top_r:
        st.subheader("Contexto del agente")
        st.write(agent["funcion"])
        st.caption(agent["prompt"])
        st.markdown("**Estado:** `" + agent["estado"] + "`")

    user_msg = st.text_area("Escribe tu mensaje", height=120, placeholder="Describe la instrucción o consulta para el agente...")
    if st.button("Enviar", type="primary") and user_msg.strip():
        timestamp = fmt_dt(now_local())
        exec_sql("INSERT INTO mensajes (conversacionId, rol, contenido, timestamp, taskCreated) VALUES (?, ?, ?, ?, ?)", (conv_id, "user", user_msg, timestamp, 0))
        system_prompt = f"Eres {agent['nombre']}, {agent['rol']}. {agent['prompt']}"
        response = maybe_call_external_ai(
            [
                {"role": "user", "content": user_msg},
            ],
            system_prompt,
            agent["rol"],
        )
        exec_sql("INSERT INTO mensajes (conversacionId, rol, contenido, timestamp, taskCreated) VALUES (?, ?, ?, ?, ?)", (conv_id, "assistant", response, fmt_dt(now_local()), 0))
        exec_sql("UPDATE conversaciones SET ultimoMensaje = ?, ultimaActividad = ?, titulo = COALESCE(titulo, ?) WHERE id = ?", (response[:180], fmt_dt(now_local()), f"Chat con {agent['nombre']}", conv_id))
        task = detect_task_from_text(response)
        if task:
            st.session_state.pending_task_from_chat = {"conv_id": conv_id, "agent_id": int(agent["id"]), "task": task}
        log_general("chat", f"Se envió mensaje al agente {agent['nombre']}", "conversacion", str(conv_id), "usuario")
        st.rerun()

    pending = st.session_state.get("pending_task_from_chat")
    if pending and pending.get("conv_id") == conv_id:
        st.warning("El asistente parece haber sugerido una tarea.")
        title, desc, prio = pending["task"]
        if st.button("Crear tarea desde el chat"):
            exec_sql(
                "INSERT INTO tareas (titulo, descripcion, responsableId, prioridad, estado, fechaCreacion, conversacionId) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (title, desc, pending["agent_id"], prio, "pendiente", fmt_dt(now_local()), conv_id),
            )
            task_id = query_one("SELECT id FROM tareas ORDER BY id DESC LIMIT 1")["id"]
            add_notification("Tarea creada desde chat", title, "nueva_tarea", int(task_id), pending["agent_id"])
            add_history(int(task_id), "creacion", None, title)
            st.session_state.pending_task_from_chat = None
            st.success("Tarea creada y vinculada a la conversación.")
            st.rerun()


def task_editor(task_id: Optional[int] = None) -> None:
    agents = load_agents()
    task = None
    if task_id:
        task = query_one("SELECT * FROM tareas WHERE id = ?", (task_id,))
    with st.form(key=f"task_form_{task_id or 'new'}"):
        titulo = st.text_input("Título", value=(task["titulo"] if task else ""))
        descripcion = st.text_area("Descripción", value=(task["descripcion"] if task else ""))
        responsable_options = {0: "Sin asignar", **{int(r.id): r.nombre for _, r in agents.iterrows()}}
        responsable_id = st.selectbox("Responsable", list(responsable_options.keys()), index=list(responsable_options.keys()).index(int(task["responsableId"]) if task and task["responsableId"] else 0), format_func=lambda x: responsable_options[x])
        prioridad = st.selectbox("Prioridad", TASK_PRIORITIES, index=TASK_PRIORITIES.index(task["prioridad"]) if task else 1)
        estado = st.selectbox("Estado", TASK_STATES, index=TASK_STATES.index(task["estado"]) if task else 0)
        fecha_limite = st.text_input("Fecha límite (YYYY-MM-DD)", value=(task["fechaLimite"] if task and task["fechaLimite"] else ""))
        observaciones = st.text_area("Observaciones", value=(task["observaciones"] if task and task["observaciones"] else ""))
        dependencias = st.text_input("Dependencias (JSON o texto)", value=(task["dependencias"] if task and task["dependencias"] else ""))
        autopiloto_to = st.text_input("Autopiloto To", value=(task["autopilotoTo"] if task and task["autopilotoTo"] else ""))
        submitted = st.form_submit_button("Guardar")
    if submitted:
        if task:
            old = dict(task)
            exec_sql(
                "UPDATE tareas SET titulo=?, descripcion=?, responsableId=?, prioridad=?, estado=?, fechaLimite=?, observaciones=?, dependencias=?, autopilotoTo=? WHERE id=?",
                (titulo, descripcion, None if responsable_id == 0 else responsable_id, prioridad, estado, fecha_limite or None, observaciones or None, dependencias or None, autopiloto_to or None, task_id),
            )
            add_history(task_id, "edicion", old.get("estado"), estado)
            add_notification("Tarea actualizada", f"Se actualizó la tarea {titulo}.", "avance", task_id, None)
            log_general("tarea", f"Tarea {task_id} actualizada.", "tarea", str(task_id), "usuario")
            st.success("Tarea actualizada.")
            st.rerun()
        else:
            exec_sql(
                "INSERT INTO tareas (titulo, descripcion, responsableId, prioridad, estado, fechaCreacion, fechaLimite, observaciones, dependencias, autopilotoTo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (titulo, descripcion, None if responsable_id == 0 else responsable_id, prioridad, estado, fmt_dt(now_local()), fecha_limite or None, observaciones or None, dependencias or None, autopiloto_to or None),
            )
            new_id = int(query_one("SELECT id FROM tareas ORDER BY id DESC LIMIT 1")["id"])
            add_notification("Nueva tarea", titulo, "nueva_tarea", new_id, None)
            add_history(new_id, "creacion", None, titulo)
            log_general("tarea", f"Tarea {new_id} creada.", "tarea", str(new_id), "usuario")
            st.success("Tarea creada.")
            st.rerun()


def page_tareas() -> None:
    st.header("Tareas")
    filters = st.columns(3)
    estados = ["(todos)"] + TASK_STATES
    prioridades = ["(todas)"] + TASK_PRIORITIES
    agents = load_agents()
    responsables = {0: "(todos)"}
    responsables.update({int(r.id): r.nombre for _, r in agents.iterrows()})
    with filters[0]:
        estado_f = st.selectbox("Estado", estados)
    with filters[1]:
        prio_f = st.selectbox("Prioridad", prioridades)
    with filters[2]:
        resp_f = st.selectbox("Responsable", list(responsables.keys()), format_func=lambda x: responsables[x])

    df = query_df("SELECT t.*, a.nombre AS responsableNombre FROM tareas t LEFT JOIN agentes a ON a.id = t.responsableId ORDER BY id DESC")
    if not df.empty:
        if estado_f != "(todos)":
            df = df[df["estado"] == estado_f]
        if prio_f != "(todas)":
            df = df[df["prioridad"] == prio_f]
        if resp_f != 0:
            df = df[df["responsableId"] == resp_f]

    st.subheader("Crear nueva tarea")
    task_editor(None)

    st.divider()
    st.subheader("Listado")
    if df.empty:
        st.info("No hay tareas con los filtros actuales.")
    else:
        for _, row in df.iterrows():
            with st.expander(f"{row['titulo']} · {row['estado']} · {row['prioridad']}", expanded=False):
                st.write(row["descripcion"])
                st.caption(f"Responsable: {row['responsableNombre'] or 'Sin asignar'}")
                st.caption(f"Creada: {row['fechaCreacion']} · Límite: {row['fechaLimite'] or '-'}")
                st.write(f"Observaciones: {row['observaciones'] or '-'}")
                cols = st.columns(4)
                for i, state in enumerate(TASK_STATES):
                    if cols[i].button(f"Mover a {state}", key=f"move_{row['id']}_{state}"):
                        old = row["estado"]
                        exec_sql("UPDATE tareas SET estado = ? WHERE id = ?", (state, int(row["id"])))
                        add_history(int(row["id"]), "estado", old, state)
                        add_notification("Estado de tarea cambiado", f"{row['titulo']} pasó a {state}.", "avance", int(row["id"]), None)
                        st.rerun()
                task_editor(int(row["id"]))
                hist = query_df("SELECT * FROM historialTareas WHERE tareaId = ? ORDER BY timestamp DESC LIMIT 10", (int(row["id"]),))
                if not hist.empty:
                    st.dataframe(hist[["campo", "valorAnterior", "valorNuevo", "usuario", "timestamp"]], use_container_width=True, hide_index=True)


def page_kanban() -> None:
    st.header("Kanban")
    tasks = query_df("SELECT t.*, a.nombre AS responsableNombre FROM tareas t LEFT JOIN agentes a ON a.id = t.responsableId ORDER BY id DESC")
    cols = st.columns(4)
    for idx, state in enumerate(TASK_STATES):
        with cols[idx]:
            st.subheader(state.replace("_", " ").title())
            subset = tasks[tasks["estado"] == state] if not tasks.empty else pd.DataFrame()
            for _, row in subset.iterrows():
                with st.container(border=True):
                    st.markdown(f"**{row['titulo']}**")
                    st.caption(f"{row['responsableNombre'] or 'Sin asignar'} · {row['prioridad']}")
                    next_states = [s for s in TASK_STATES if s != state]
                    chosen = st.selectbox("Mover a", next_states, key=f"kb_{row['id']}")
                    if st.button("Actualizar", key=f"kb_btn_{row['id']}"):
                        old = row["estado"]
                        exec_sql("UPDATE tareas SET estado = ? WHERE id = ?", (chosen, int(row["id"])))
                        add_history(int(row["id"]), "estado", old, chosen)
                        add_notification("Kanban actualizado", f"{row['titulo']} pasó a {chosen}.", "avance", int(row["id"]), None)
                        st.rerun()


def page_notificaciones() -> None:
    st.header("Notificaciones")
    df = query_df("SELECT * FROM notificaciones ORDER BY timestamp DESC")
    tipos = ["(todos)"] + sorted(df["tipo"].dropna().unique().tolist()) if not df.empty else ["(todos)"]
    tipo_f = st.selectbox("Filtrar por tipo", tipos)
    if not df.empty and tipo_f != "(todos)":
        df = df[df["tipo"] == tipo_f]
    top = st.columns(2)
    if top[0].button("Marcar todas como leídas"):
        exec_sql("UPDATE notificaciones SET leida = 1 WHERE leida = 0")
        st.rerun()
    st.caption(f"No leídas: {get_sidebar_unread_count()}")
    if df.empty:
        st.info("No hay notificaciones.")
        return
    for _, row in df.iterrows():
        with st.container(border=True):
            st.markdown(f"**{'🔵' if not row['leida'] else '⚪'} {row['titulo']}**")
            st.write(row["mensaje"])
            st.caption(f"Tipo: {row['tipo']} · {row['timestamp']}")
            if not row["leida"] and st.button("Marcar como leída", key=f"read_{row['id']}"):
                exec_sql("UPDATE notificaciones SET leida = 1 WHERE id = ?", (int(row["id"]),))
                st.rerun()


def report_ai_narrative(report_type: str, df: pd.DataFrame) -> str:
    if report_type == "Inventario":
        low = df[df["estado"].isin(["bajo", "critico"])] if not df.empty else pd.DataFrame()
        return f"El inventario muestra {len(low)} alerta(s) relevantes. Conviene reponer los productos en estado bajo o crítico antes del siguiente servicio."
    if report_type == "Finanzas":
        return "Las finanzas reflejan actividad comercial saludable, pero la utilidad debe protegerse revisando insumos y nómina con frecuencia."
    if report_type == "Personal":
        return "La plantilla está operativa, con cobertura por turnos. La prioridad es sostener continuidad sin sobrecargar al equipo."
    if report_type == "Tareas":
        return "La cartera de tareas muestra frentes distribuidos entre gerencias. La atención debe concentrarse en bloqueos y prioridades críticas."
    return "El estado general requiere coordinación entre áreas, con foco en inventario, servicio y control financiero."


def page_reportes() -> None:
    st.header("Reportes")
    report_type = st.selectbox("Tipo", ["Inventario", "Finanzas", "Personal", "Tareas", "Estado General"])

    if report_type == "Inventario":
        df = query_df("SELECT * FROM inventario")
        st.write(report_ai_narrative(report_type, df))
        by_cat = df.groupby("categoria", as_index=False)["cantidad"].sum() if not df.empty else pd.DataFrame(columns=["categoria", "cantidad"])
        by_state = df.groupby("estado", as_index=False)["producto"].count().rename(columns={"producto": "conteo"}) if not df.empty else pd.DataFrame(columns=["estado", "conteo"])
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.bar(by_cat, x="categoria", y="cantidad", title="Inventario por categoría"), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(by_state, names="estado", values="conteo", title="Inventario por estado"), use_container_width=True)
    elif report_type == "Finanzas":
        df = query_df("SELECT * FROM finanzas ORDER BY fecha ASC")
        st.write(report_ai_narrative(report_type, df))
        if not df.empty:
            pivot = df.groupby(["fecha", "tipo"], as_index=False)["monto"].sum()
            fig = px.line(pivot, x="fecha", y="monto", color="tipo", title="Ingresos vs egresos")
            st.plotly_chart(fig, use_container_width=True)
            i = float(df[df["tipo"] == "ingreso"]["monto"].sum())
            e = float(df[df["tipo"] == "egreso"]["monto"].sum())
            st.metric("Utilidad", money_q(i - e))
            st.dataframe(df, use_container_width=True, hide_index=True)
    elif report_type == "Personal":
        df = query_df("SELECT * FROM personal")
        st.write(report_ai_narrative(report_type, df))
        turn = df.groupby("turno", as_index=False)["nombre"].count().rename(columns={"nombre": "conteo"}) if not df.empty else pd.DataFrame(columns=["turno", "conteo"])
        sal = df.sort_values("salario", ascending=False) if not df.empty else df
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.pie(turn, names="turno", values="conteo", title="Personal por turno"), use_container_width=True)
        with c2:
            st.plotly_chart(px.bar(sal, x="nombre", y="salario", title="Salarios"), use_container_width=True)
    elif report_type == "Tareas":
        df = query_df("SELECT * FROM tareas")
        st.write(report_ai_narrative(report_type, df))
        state = df.groupby("estado", as_index=False)["titulo"].count().rename(columns={"titulo": "conteo"}) if not df.empty else pd.DataFrame(columns=["estado", "conteo"])
        prio = df.groupby("prioridad", as_index=False)["titulo"].count().rename(columns={"titulo": "conteo"}) if not df.empty else pd.DataFrame(columns=["prioridad", "conteo"])
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.pie(state, names="estado", values="conteo", title="Tareas por estado"), use_container_width=True)
        with c2:
            st.plotly_chart(px.bar(prio, x="prioridad", y="conteo", title="Tareas por prioridad"), use_container_width=True)
    else:
        data = pd.DataFrame([
            {"area": "Inventario", "valor": int((query_df("SELECT * FROM inventario WHERE estado IN ('bajo','critico')").shape[0]))},
            {"area": "Finanzas", "valor": int((query_df("SELECT * FROM finanzas").shape[0]))},
            {"area": "Personal", "valor": int((query_df("SELECT * FROM personal").shape[0]))},
            {"area": "Tareas", "valor": int((query_df("SELECT * FROM tareas").shape[0]))},
            {"area": "Mesas", "valor": int((query_df("SELECT * FROM mesas WHERE estado != 'disponible'").shape[0]))},
        ])
        st.write(report_ai_narrative(report_type, data))
        st.plotly_chart(px.bar(data, x="area", y="valor", title="Estado general por área"), use_container_width=True)


def page_historial() -> None:
    st.header("Historial")
    tipos = query_df("SELECT DISTINCT tipo FROM historialGeneral ORDER BY tipo")
    tipo_f = st.selectbox("Tipo", ["(todos)"] + (tipos["tipo"].tolist() if not tipos.empty else []))
    q = "SELECT * FROM historialGeneral ORDER BY timestamp DESC"
    if tipo_f != "(todos)":
        q = "SELECT * FROM historialGeneral WHERE tipo = ? ORDER BY timestamp DESC"
        df = query_df(q, (tipo_f,))
    else:
        df = query_df(q)
    if df.empty:
        st.info("Sin eventos.")
        return
    for _, row in df.iterrows():
        with st.container(border=True):
            st.markdown(f"**{row['tipo'].title()}**")
            st.write(row["descripcion"])
            st.caption(row["timestamp"])
            if row["metadata"]:
                st.code(row["metadata"], language="json")


def parse_upload_file(uploaded) -> pd.DataFrame:
    if uploaded.name.lower().endswith(".csv"):
        return pd.read_csv(uploaded)
    if uploaded.name.lower().endswith(".json"):
        raw = json.load(uploaded)
        return pd.DataFrame(raw if isinstance(raw, list) else [raw])
    raise ValueError("Formato no soportado")


def page_carga_masiva() -> None:
    st.header("Carga Masiva")
    tipo = st.selectbox("Tipo de importación", ["inventario", "personal", "menu", "finanzas"])
    uploaded = st.file_uploader("Sube CSV o JSON", type=["csv", "json"])
    if uploaded:
        try:
            df = parse_upload_file(uploaded)
            st.subheader("Previsualización")
            st.dataframe(df.head(20), use_container_width=True, hide_index=True)
            if st.button("Confirmar importación"):
                inserted = 0
                errors: List[str] = []
                for _, row in df.iterrows():
                    try:
                        if tipo == "inventario":
                            exec_sql(
                                "INSERT INTO inventario (producto, categoria, unidad, cantidad, costoUnitario, proveedor, stockMinimo, estado, ultimaActualizacion) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (
                                    row.get("producto"),
                                    row.get("categoria", "General"),
                                    row.get("unidad", "unidad"),
                                    float(row.get("cantidad", 0)),
                                    float(row.get("costoUnitario", 0)),
                                    row.get("proveedor"),
                                    float(row.get("stockMinimo", 0)),
                                    row.get("estado", "suficiente"),
                                    fmt_dt(now_local()),
                                ),
                            )
                        elif tipo == "personal":
                            exec_sql(
                                "INSERT INTO personal (nombre, puesto, turno, salario, estado, fechaIngreso, contacto) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (row.get("nombre"), row.get("puesto"), row.get("turno", "Día"), float(row.get("salario", 0)), row.get("estado", "activo"), row.get("fechaIngreso"), row.get("contacto")),
                            )
                        elif tipo == "menu":
                            exec_sql(
                                "INSERT INTO menu (nombre, categoria, precio, costoEstimado, disponible, descripcion, imagen) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (row.get("nombre"), row.get("categoria", "General"), float(row.get("precio", 0)), float(row.get("costoEstimado", 0)), int(row.get("disponible", 1)), row.get("descripcion"), row.get("imagen")),
                            )
                        else:
                            exec_sql(
                                "INSERT INTO finanzas (fecha, tipo, categoria, descripcion, monto, responsable) VALUES (?, ?, ?, ?, ?, ?)",
                                (row.get("fecha", date.today().isoformat()), row.get("tipo", "egreso"), row.get("categoria", "General"), row.get("descripcion", ""), float(row.get("monto", 0)), row.get("responsable")),
                            )
                        inserted += 1
                    except Exception as e:
                        errors.append(str(e))
                exec_sql(
                    "INSERT INTO cargasMasivas (tipo, archivo, estado, registrosTotales, registrosProcesados, errores, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (tipo, uploaded.name, "completado" if not errors else "error", len(df), inserted, json.dumps(errors, ensure_ascii=False), fmt_dt(now_local())),
                )
                log_general("carga_masiva", f"Carga masiva de {tipo} procesada: {inserted}/{len(df)}", tipo, uploaded.name, "usuario", {"errores": errors[:5]})
                st.success(f"Importación terminada: {inserted} registros.")
                if errors:
                    st.warning("Errores encontrados: " + "; ".join(errors[:5]))
                st.rerun()
        except Exception as e:
            st.error(f"No se pudo leer el archivo: {e}")
    st.subheader("Historial de cargas")
    loads = query_df("SELECT * FROM cargasMasivas ORDER BY timestamp DESC")
    if not loads.empty:
        st.dataframe(loads, use_container_width=True, hide_index=True)


def autopilot_context() -> str:
    context = build_contexto_restaurante("Gerente General")
    return json.dumps(context, ensure_ascii=False, indent=2)


def page_autopiloto() -> None:
    st.header("Autopiloto")
    st.write("Ejecuta un diagnóstico completo y genera propuestas de metas y tareas.")
    if st.button("Ejecutar diagnóstico completo", type="primary"):
        diag = maybe_call_external_ai(
            [{"role": "user", "content": "Realiza un diagnóstico completo del restaurante y propone metas y tareas."}],
            "Eres Carlos Mendez, Gerente General.",
            "Gerente General",
        )
        areas = [
            {"area": "Inventario", "estado": "alerta", "problemas": ["Tomate bajo", "Cebolla baja"], "recomendaciones": ["Comprar insumos críticos hoy"]},
            {"area": "Finanzas", "estado": "estable", "problemas": ["Egresos relevantes"], "recomendaciones": ["Revisar gasto de nómina"]},
            {"area": "Personal", "estado": "estable", "problemas": [], "recomendaciones": ["Confirmar cobertura de turnos"]},
        ]
        exec_sql(
            "INSERT INTO diagnosticos (fecha, resumen, areas, metasGeneradas, tareasGeneradas, estado) VALUES (?, ?, ?, ?, ?, ?)",
            (fmt_dt(now_local()), diag, json.dumps(areas, ensure_ascii=False), 3, 4, "propuesta"),
        )
        diag_id = int(query_one("SELECT id FROM diagnosticos ORDER BY id DESC LIMIT 1")["id"])
        st.session_state.pending_autopilot = {"diag_id": diag_id, "areas": areas}
        st.success("Diagnóstico generado.")
        st.rerun()

    pending = st.session_state.get("pending_autopilot")
    if pending:
        st.info("Hay propuestas pendientes de aprobación.")
        if st.button("Aprobar propuestas y aplicar"):
            for area in pending["areas"]:
                titulo = f"Acción autopiloto: {area['area']}"
                desc = "; ".join(area.get("recomendaciones", [])) or "Acción generada por autopiloto."
                exec_sql(
                    "INSERT INTO tareas (titulo, descripcion, responsableId, prioridad, estado, fechaCreacion, autopilotoTo) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (titulo, desc, None, "alta", "pendiente", fmt_dt(now_local()), area["area"]),
                )
            add_notification("Autopiloto aplicado", "Se aprobaron las propuestas del diagnóstico.", "autopiloto", None, None)
            log_general("autopiloto", "Se aprobaron propuestas del diagnóstico.")
            st.session_state.pending_autopilot = None
            st.success("Propuestas aplicadas.")
            st.rerun()
        if st.button("Rechazar propuestas"):
            exec_sql("UPDATE diagnosticos SET estado = 'parcial' WHERE id = ?", (pending["diag_id"],))
            add_notification("Autopiloto rechazado", "Las propuestas no fueron aplicadas.", "autopiloto", None, None)
            st.session_state.pending_autopilot = None
            st.warning("Propuestas rechazadas.")
            st.rerun()

    st.subheader("Historial de diagnósticos")
    diags = query_df("SELECT * FROM diagnosticos ORDER BY fecha DESC")
    if diags.empty:
        st.info("Sin diagnósticos.")
    else:
        for _, row in diags.iterrows():
            with st.expander(f"{row['fecha']} · {row['estado']}"):
                st.write(row["resumen"])
                try:
                    areas = json.loads(row["areas"])
                    st.json(areas)
                except Exception:
                    st.code(row["areas"])


def page_configuracion() -> None:
    st.header("Configuración")
    rest = query_one("SELECT * FROM restaurantes LIMIT 1")
    st.subheader("Datos del restaurante")
    with st.form("rest_form"):
        nombre = st.text_input("Nombre", value=rest["nombre"] if rest else APP_TITLE)
        ubicacion = st.text_input("Ubicación", value=rest["ubicacion"] if rest else "Zona 10, Ciudad de Guatemala")
        tipo = st.text_input("Tipo", value=rest["tipo"] if rest else "Comida guatemalteca")
        capacidad = st.number_input("Capacidad", min_value=1, value=int(rest["capacidad"] if rest else 80))
        mesas = st.number_input("Mesas", min_value=1, value=int(rest["mesas"] if rest else 15))
        ha = st.text_input("Horario apertura", value=rest["horarioApertura"] if rest else "09:00")
        hc = st.text_input("Horario cierre", value=rest["horarioCierre"] if rest else "22:00")
        dias = st.text_input("Días operación", value=rest["diasOperacion"] if rest else "Lunes a domingo")
        descripcion = st.text_area("Descripción", value=rest["descripcion"] if rest else "")
        submit = st.form_submit_button("Guardar cambios")
    if submit:
        exec_sql(
            "UPDATE restaurantes SET nombre=?, ubicacion=?, tipo=?, capacidad=?, mesas=?, horarioApertura=?, horarioCierre=?, diasOperacion=?, descripcion=? WHERE id=?",
            (nombre, ubicacion, tipo, int(capacidad), int(mesas), ha, hc, dias, descripcion, int(rest["id"])),
        )
        invalidate_caches()
        log_general("configuracion", "Se actualizaron los datos del restaurante.")
        st.success("Configuración guardada.")
        st.rerun()

    st.subheader("Prompts de agentes")
    agents = load_agents()
    agent_pick = st.selectbox("Selecciona un agente", agents["id"].tolist(), format_func=lambda aid: f"{agents.loc[agents['id']==aid, 'nombre'].iloc[0]} · {agents.loc[agents['id']==aid, 'rol'].iloc[0]}")
    ag = query_one("SELECT * FROM agentes WHERE id = ?", (int(agent_pick),))
    with st.form("agent_prompt_form"):
        prompt = st.text_area("Prompt", value=ag["prompt"])
        func = st.text_input("Función", value=ag["funcion"])
        color = st.text_input("Color", value=ag["color"])
        order = st.number_input("Orden", min_value=1, value=int(ag["orden"]))
        submitted = st.form_submit_button("Actualizar agente")
    if submitted:
        exec_sql("UPDATE agentes SET prompt=?, funcion=?, color=?, orden=? WHERE id=?", (prompt, func, color, int(order), int(agent_pick)))
        invalidate_caches()
        log_general("configuracion", f"Se actualizó el prompt del agente {ag['nombre']}.")
        st.success("Agente actualizado.")
        st.rerun()

    st.subheader("Navegación y notificaciones")
    st.write("El sidebar ya contiene la navegación principal del sistema y el badge de notificaciones no leídas.")
    st.write("Para Streamlit Cloud, usa secretos para HERCULES_API_URL, HERCULES_API_KEY y HERCULES_MODEL.")


def render_sidebar() -> str:
    unread = get_sidebar_unread_count()
    st.sidebar.markdown("### 🍴 Sabores de Guatemala")
    st.sidebar.caption("Sistema de gestión con IA")
    pages = [
        "Dashboard",
        "Agentes",
        "Chat",
        "Tareas",
        "Kanban",
        f"Notificaciones ({unread})",
        "Reportes",
        "Historial",
        "Carga Masiva",
        "Autopiloto",
        "Configuración",
    ]
    selection = st.sidebar.radio("Navegación", pages, label_visibility="collapsed")
    return selection


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🍴", layout="wide", initial_sidebar_state="expanded")
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Outfit:wght@400;500;600;700&display=swap');
        html, body, [class*="css"]  {
            font-family: 'Plus Jakarta Sans', 'Outfit', sans-serif;
        }
        :root {
            --verde: oklch(0.38 0.12 155);
            --dorado: oklch(0.75 0.13 75);
        }
        .stApp {
            background: linear-gradient(180deg, rgba(14, 52, 36, 0.95), rgba(8, 28, 20, 0.98));
            color: white;
        }
        section[data-testid="stSidebar"] {
            background: #0b2318;
            border-right: 1px solid rgba(255,255,255,0.06);
        }
        h1, h2, h3, h4, h5, h6 { letter-spacing: -0.02em; }
        .stMetric, .stDataFrame, .stContainer { border-radius: 18px; }
        .block-container { padding-top: 1.5rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    init_db()
    seed_if_needed()
    invalidate_caches()
    page = render_sidebar()

    if page == "Dashboard":
        page_dashboard()
    elif page == "Agentes":
        page_agentes()
    elif page == "Chat":
        page_chat()
    elif page == "Tareas":
        page_tareas()
    elif page == "Kanban":
        page_kanban()
    elif page.startswith("Notificaciones"):
        page_notificaciones()
    elif page == "Reportes":
        page_reportes()
    elif page == "Historial":
        page_historial()
    elif page == "Carga Masiva":
        page_carga_masiva()
    elif page == "Autopiloto":
        page_autopiloto()
    elif page == "Configuración":
        page_configuracion()

    st.sidebar.divider()
    st.sidebar.caption("Moneda: Quetzales (Q)")
    st.sidebar.caption("Fechas en español · Respaldo local con SQLite")


if __name__ == "__main__":
    main()
