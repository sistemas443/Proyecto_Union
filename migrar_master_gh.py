# migrar_master_gh.py
"""
Migracion del AppSheet "AUTORIZACION SALIDA GH" (Google Sheets/Excel) a PostgreSQL.
Base destino: Master_gh

Capas:
  staging.*   -> copia fiel de cada hoja en JSONB (auditoria/reproceso)
  public.*    -> tablas tipadas con catalogos, FKs, checks e indices

Uso:  python migrar_master_gh.py
"""
import json
import math
import unicodedata
from datetime import date, datetime, time, timedelta

import pandas as pd
import psycopg2
import psycopg2.extras

from config import Config

EXCEL = r"C:\Users\Lider sistemas\Downloads\AUTORIZACION SALIDA GH.xlsx"
DB_NAME = "Master_gh"


def p(msg):
    print(msg, flush=True)


# ----------------------------------------------------------------------
# Conexion / creacion de base
# ----------------------------------------------------------------------
def conectar(dbname):
    return psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        dbname=dbname,
        connect_timeout=20,
    )


def crear_base():
    conn = conectar(Config.DB_NAME)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
            if cur.fetchone():
                p(f"[base] Ya existe: {DB_NAME}")
                return
            cur.execute('CREATE DATABASE "Master_gh" WITH ENCODING \'UTF8\' TEMPLATE template0')
            p(f"[base] Creada: {DB_NAME}")
    finally:
        conn.close()


# ----------------------------------------------------------------------
# Helpers de limpieza
# ----------------------------------------------------------------------
def txt(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    s = str(v).strip()
    s = " ".join(s.split())
    return s or None


def norm(s):
    s = txt(s)
    if not s:
        return None
    s = s.upper()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return " ".join(s.split())


def a_int(v):
    s = txt(v)
    if s is None:
        return None
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def a_decimal(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    s = str(v).strip().replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def a_fecha(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, time):
        return None
    try:
        return pd.to_datetime(str(v).strip(), dayfirst=True).date()
    except Exception:
        return None


def a_hora(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, time):
        return v
    if isinstance(v, datetime):
        return v.time()
    if isinstance(v, timedelta):
        total = int(v.total_seconds())
        return (datetime.min + timedelta(seconds=total)).time()
    s = str(v).strip().lower()
    if not s:
        return None
    s = s.split()[0]
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            pass
    return None


def a_horas(v):
    """Convierte time/timedelta/texto 'HH:MM:SS' a horas decimales."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, time):
        return round(v.hour + v.minute / 60 + v.second / 3600, 2)
    if isinstance(v, timedelta):
        return round(v.total_seconds() / 3600, 2)
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    s = str(v).strip()
    if ":" in s:
        partes = s.split(":")
        try:
            h = int(partes[0])
            m = int(partes[1]) if len(partes) > 1 else 0
            seg = int(float(partes[2])) if len(partes) > 2 else 0
            return round(h + m / 60 + seg / 3600, 2)
        except ValueError:
            pass
    try:
        return round(float(s.replace(",", ".")), 2)
    except ValueError:
        return None


MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def a_mes(v):
    s = norm(v)
    return MESES.get(s.lower()) if s else None


# ----------------------------------------------------------------------
# Esquema
# ----------------------------------------------------------------------
DDL = """
DROP SCHEMA IF EXISTS staging CASCADE;
CREATE SCHEMA staging;

CREATE TABLE staging.solicitud_salida (fila INTEGER, datos JSONB);
CREATE TABLE staging.colaborador       (fila INTEGER, datos JSONB);
CREATE TABLE staging.firma             (fila INTEGER, datos JSONB);
CREATE TABLE staging.area              (fila INTEGER, datos JSONB);
CREATE TABLE staging.cargo             (fila INTEGER, datos JSONB);

DROP TABLE IF EXISTS firma, solicitud_salida, colaborador, motivo,
                     tipo_permiso, estado, cargo, area, rechazos CASCADE;

CREATE TABLE area (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    nombre_normalizado TEXT NOT NULL,
    creado_en TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE cargo (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    nombre_normalizado TEXT NOT NULL,
    creado_en TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE motivo (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE
);

CREATE TABLE tipo_permiso (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE
);

CREATE TABLE estado (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE
);

CREATE TABLE colaborador (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    nombre_normalizado TEXT NOT NULL,
    area_id TEXT REFERENCES area(id),
    cargo_id TEXT REFERENCES cargo(id),
    imagen TEXT,
    permisos_solicitados INTEGER DEFAULT 0,
    tiempo_no_laborado_horas NUMERIC(10,2) DEFAULT 0,
    colaborador_id BIGINT,
    creado_en TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE solicitud_salida (
    id TEXT PRIMARY KEY,
    fecha_hora_solicitud TIMESTAMPTZ,
    anio SMALLINT,
    mes SMALLINT,
    mes_texto TEXT,
    colaborador_gh_id TEXT REFERENCES colaborador(id),
    nombre_colaborador TEXT,
    area_texto TEXT,
    motivo_id INTEGER REFERENCES motivo(id),
    descripcion_motivo TEXT,
    tipo_permiso_id INTEGER REFERENCES tipo_permiso(id),
    fecha_permiso DATE,
    fecha_permiso_final DATE,
    conversion_dias_horas NUMERIC(8,2),
    total_tiempo_transcurrido NUMERIC(8,2),
    hora_salida TIME,
    hora_regreso TIME,
    total_horas_permiso NUMERIC(8,2),
    total_horas_permiso_indicadores NUMERIC(8,2),
    nota TEXT,
    check_texto TEXT,
    reposicion_tiempo TEXT,
    observaciones TEXT,
    estado_id INTEGER REFERENCES estado(id),
    etiqueta TEXT,
    adjunto_documento TEXT,
    adjunto_imagen TEXT,
    origen TEXT DEFAULT 'AppSheet',
    creado_en TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_anio CHECK (anio BETWEEN 2000 AND 2100),
    CONSTRAINT chk_mes CHECK (mes BETWEEN 1 AND 12),
    CONSTRAINT chk_horas CHECK (total_horas_permiso IS NULL OR total_horas_permiso >= 0),
    CONSTRAINT chk_fechas CHECK (
        fecha_permiso_final IS NULL OR fecha_permiso IS NULL
        OR fecha_permiso_final >= fecha_permiso
    )
);

CREATE TABLE firma (
    id BIGSERIAL PRIMARY KEY,
    firma_appsheet_id TEXT NOT NULL,
    solicitud_id TEXT REFERENCES solicitud_salida(id),
    quien_firma TEXT,
    nombre_firma TEXT,
    firma TEXT,
    creado_en TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (firma_appsheet_id, solicitud_id)
);

CREATE TABLE rechazos (
    id BIGSERIAL PRIMARY KEY,
    tabla TEXT NOT NULL,
    fila INTEGER,
    motivo TEXT,
    datos JSONB,
    creado_en TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sol_col_fecha ON solicitud_salida(colaborador_gh_id, fecha_permiso);
CREATE INDEX idx_sol_fecha ON solicitud_salida(fecha_permiso);
CREATE INDEX idx_sol_anio_mes ON solicitud_salida(anio, mes);
CREATE INDEX idx_sol_motivo ON solicitud_salida(motivo_id);
CREATE INDEX idx_sol_tipo ON solicitud_salida(tipo_permiso_id);
CREATE INDEX idx_firma_solicitud ON firma(solicitud_id);
CREATE INDEX idx_firma_appsheet ON firma(firma_appsheet_id);
CREATE INDEX idx_col_area ON colaborador(area_id);
CREATE INDEX idx_col_cargo ON colaborador(cargo_id);
"""


# ----------------------------------------------------------------------
# Carga raw
# ----------------------------------------------------------------------
def cargar_raw(cur, df, tabla):
    registros = []
    for i, row in enumerate(df.to_dict(orient="records"), start=2):
        datos = {}
        for k, v in row.items():
            datos[str(k).strip()] = None if (v is None or (isinstance(v, float) and math.isnan(v)) or pd.isna(v)) else str(v)
        registros.append((i, psycopg2.extras.Json(datos)))
    psycopg2.extras.execute_values(
        cur,
        f"INSERT INTO staging.{tabla} (fila, datos) VALUES %s",
        registros,
        page_size=500,
    )
    p(f"[raw] {tabla}: {len(registros)} filas")


def log_rechazo(cur, tabla, fila, motivo, datos):
    cur.execute(
        "INSERT INTO rechazos (tabla, fila, motivo, datos) VALUES (%s, %s, %s, %s)",
        (tabla, fila, motivo, psycopg2.extras.Json(datos)),
    )


# ----------------------------------------------------------------------
# Transformacion
# ----------------------------------------------------------------------
def main():
    crear_base()

    p("[excel] Leyendo hojas...")
    sol = pd.read_excel(EXCEL, sheet_name="SOLICITUD_SALIDA")
    col = pd.read_excel(EXCEL, sheet_name="COLABORADOR_GH")
    fir = pd.read_excel(EXCEL, sheet_name="FIRMA_GH")
    area = pd.read_excel(EXCEL, sheet_name="AREA_GH")
    cargo = pd.read_excel(EXCEL, sheet_name="CARGO_GH")
    for df in (sol, col, fir, area, cargo):
        df.columns = [str(c).strip() for c in df.columns]

    conn = conectar(DB_NAME)
    try:
        with conn.cursor() as cur:
            p("[ddl] Creando esquema y tablas...")
            cur.execute(DDL)

            p("[raw] Cargando copia fiel del Excel...")
            cargar_raw(cur, sol, "solicitud_salida")
            cargar_raw(cur, col, "colaborador")
            cargar_raw(cur, fir, "firma")
            cargar_raw(cur, area, "area")
            cargar_raw(cur, cargo, "cargo")

            # --- Catalogos area / cargo ---
            for _, r in area.iterrows():
                id_ = txt(r.get("AREA GH ID"))
                nombre = txt(r.get("AREA"))
                if not id_ or not nombre:
                    continue
                cur.execute(
                    "INSERT INTO area (id, nombre, nombre_normalizado) VALUES (%s,%s,%s) "
                    "ON CONFLICT (id) DO UPDATE SET nombre=EXCLUDED.nombre, nombre_normalizado=EXCLUDED.nombre_normalizado",
                    (id_, nombre, norm(nombre)),
                )
            for _, r in cargo.iterrows():
                id_ = txt(r.get("CARGO GH ID"))
                nombre = txt(r.get("CARGO"))
                if not id_ or not nombre:
                    continue
                cur.execute(
                    "INSERT INTO cargo (id, nombre, nombre_normalizado) VALUES (%s,%s,%s) "
                    "ON CONFLICT (id) DO UPDATE SET nombre=EXCLUDED.nombre, nombre_normalizado=EXCLUDED.nombre_normalizado",
                    (id_, nombre, norm(nombre)),
                )

            # Catalogos simples
            for valor in sorted({txt(v) for v in sol["MOTIVO"].dropna()} - {None}):
                cur.execute("INSERT INTO motivo (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING", (valor,))
            for valor in sorted({txt(v) for v in sol["TIPO DE PERMISO"].dropna()} - {None}):
                cur.execute("INSERT INTO tipo_permiso (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING", (valor,))
            for valor in sorted({txt(v) for v in sol["ESTADO"].dropna()} - {None}):
                cur.execute("INSERT INTO estado (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING", (valor,))

            cur.execute("SELECT id, nombre FROM motivo")
            motivo_id = {norm(n): i for i, n in cur.fetchall()}
            cur.execute("SELECT id, nombre FROM tipo_permiso")
            tipo_id = {norm(n): i for i, n in cur.fetchall()}
            cur.execute("SELECT id, nombre FROM estado")
            estado_id = {norm(n): i for i, n in cur.fetchall()}

            # --- Colaboradores (lote) ---
            cur.execute("SELECT id FROM area")
            area_ids = {r[0] for r in cur.fetchall()}
            cur.execute("SELECT id FROM cargo")
            cargo_ids = {r[0] for r in cur.fetchall()}

            col_rows = []
            col_ids = set()
            for fila, r in col.iterrows():
                id_ = txt(r.get("COLABORADOR GH ID"))
                if not id_:
                    continue
                nombre = txt(r.get("NOMBRE DEL COLABORADOR")) or ""
                area_id = txt(r.get("ID_AREA"))
                cargo_id = txt(r.get("CARGO"))
                if area_id and area_id not in area_ids:
                    log_rechazo(cur, "colaborador", fila + 2, f"area_id inexistente: {area_id}", {k: str(v) for k, v in r.items()})
                    area_id = None
                if cargo_id and cargo_id not in cargo_ids:
                    log_rechazo(cur, "colaborador", fila + 2, f"cargo_id inexistente: {cargo_id}", {k: str(v) for k, v in r.items()})
                    cargo_id = None
                col_rows.append((
                    id_, nombre, norm(nombre), area_id, cargo_id,
                    txt(r.get("Imagen")),
                    a_int(r.get("Cantidad de permisos solicitados")) or 0,
                    a_decimal(r.get("Cantidad de tiempo no laborado en horas")) or 0,
                ))
                col_ids.add(id_)
            if col_rows:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO colaborador
                        (id, nombre, nombre_normalizado, area_id, cargo_id, imagen,
                         permisos_solicitados, tiempo_no_laborado_horas)
                    VALUES %s
                    ON CONFLICT (id) DO UPDATE SET
                        nombre=EXCLUDED.nombre,
                        nombre_normalizado=EXCLUDED.nombre_normalizado,
                        area_id=EXCLUDED.area_id,
                        cargo_id=EXCLUDED.cargo_id,
                        imagen=EXCLUDED.imagen,
                        permisos_solicitados=EXCLUDED.permisos_solicitados,
                        tiempo_no_laborado_horas=EXCLUDED.tiempo_no_laborado_horas
                    """,
                    col_rows, page_size=500,
                )
            p(f"[typed] colaborador: {len(col_rows)}")

            # --- Solicitudes (lote) ---
            sol_rows = []
            n_orf_col = 0
            for fila, r in sol.iterrows():
                id_ = txt(r.get("SOLICITUD SALIDA ID"))
                if not id_:
                    continue
                col_id = txt(r.get("COLABORADOR GH ID"))
                if col_id and col_id not in col_ids:
                    n_orf_col += 1
                    log_rechazo(cur, "solicitud_salida", fila + 2, f"colaborador inexistente: {col_id}", {k: str(v) for k, v in r.items()})
                    col_id = None
                m_id = motivo_id.get(norm(r.get("MOTIVO")))
                t_id = tipo_id.get(norm(r.get("TIPO DE PERMISO")))
                e_id = estado_id.get(norm(r.get("ESTADO")))
                mes_txt = txt(r.get("MES"))
                f_ini = a_fecha(r.get("FECHA DE PERMISO"))
                f_fin = a_fecha(r.get("FECHA DE PERMISO FINAL"))
                if f_ini and f_fin and f_fin < f_ini:
                    log_rechazo(cur, "solicitud_salida", fila + 2, "fecha_fin < fecha_inicio", {k: str(v) for k, v in r.items()})
                    f_fin = None
                fh = r.get("FECHA Y HORA SOLICITUD")
                if isinstance(fh, pd.Timestamp):
                    fh = fh.to_pydatetime()
                elif not isinstance(fh, datetime):
                    fh = None
                horas = a_horas(r.get("TOTAL HORAS DE PERMISO"))
                if horas is not None and horas < 0:
                    log_rechazo(cur, "solicitud_salida", fila + 2, f"horas negativas corregidas: {horas} + 24", {k: str(v) for k, v in r.items()})
                    horas = round(horas + 24, 2)
                sol_rows.append((
                    id_, fh, a_int(r.get("AÑO")), a_mes(mes_txt), mes_txt,
                    col_id, txt(r.get("NOMBRE COLABORADOR")), txt(r.get("AREA")),
                    m_id, txt(r.get("DESCRIPCION DEL MOTIVO")), t_id,
                    f_ini, f_fin,
                    a_decimal(r.get("CONVERSION DE DIAS A HORAS")),
                    a_decimal(r.get("TOTAL DE TIEMPO TRANSCURRIDO")),
                    a_hora(r.get("HORA DE SALIDA")), a_hora(r.get("HORA DE REGRESO")),
                    horas,
                    a_decimal(r.get("TOTAL HORAS PERMISO (Indicadores)")),
                    txt(r.get("NOTA")), txt(r.get("CHECK")),
                    txt(r.get("REPOSICION DEL TIEMPO")), txt(r.get("OBSERVACIONES")),
                    e_id, txt(r.get("ETIQUETA")),
                    txt(r.get("ADJUNTAR_CONSTANCIA_DOCUMENTO")),
                    txt(r.get("ADJUNTAR_CONSTANCIA_IMAGEN")),
                ))
            if sol_rows:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO solicitud_salida (
                        id, fecha_hora_solicitud, anio, mes, mes_texto,
                        colaborador_gh_id, nombre_colaborador, area_texto,
                        motivo_id, descripcion_motivo, tipo_permiso_id,
                        fecha_permiso, fecha_permiso_final,
                        conversion_dias_horas, total_tiempo_transcurrido,
                        hora_salida, hora_regreso,
                        total_horas_permiso, total_horas_permiso_indicadores,
                        nota, check_texto, reposicion_tiempo, observaciones,
                        estado_id, etiqueta, adjunto_documento, adjunto_imagen
                    ) VALUES %s
                    ON CONFLICT (id) DO NOTHING
                    """,
                    sol_rows, page_size=500,
                )
            p(f"[typed] solicitud_salida: {len(sol_rows)} (sin colaborador: {n_orf_col})")

            # --- Firmas (lote) ---
            cur.execute("SELECT id FROM solicitud_salida")
            sol_ids = {r[0] for r in cur.fetchall()}
            fir_rows = []
            n_orf_fir = 0
            for fila, r in fir.iterrows():
                firma_id = txt(r.get("FIRMA ID"))
                if not firma_id:
                    continue
                sol_id = txt(r.get("SOLICITUD SALIDA ID"))
                if sol_id and sol_id not in sol_ids:
                    n_orf_fir += 1
                    log_rechazo(cur, "firma", fila + 2, f"solicitud inexistente: {sol_id}", {k: str(v) for k, v in r.items()})
                    sol_id = None
                fir_rows.append((
                    firma_id, sol_id,
                    txt(r.get("¿QUIEN FIRMA?")),
                    txt(r.get("NOMBRE DE QUIEN FIRMA")),
                    txt(r.get("FIRMA")),
                ))
            if fir_rows:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO firma
                        (firma_appsheet_id, solicitud_id, quien_firma, nombre_firma, firma)
                    VALUES %s
                    ON CONFLICT (firma_appsheet_id, solicitud_id) DO NOTHING
                    """,
                    fir_rows, page_size=500,
                )
            p(f"[typed] firma: {len(fir_rows)} (huerfanas: {n_orf_fir})")

        conn.commit()
        p("[commit] Migracion confirmada.")

        # --- Validacion ---
        with conn.cursor() as cur:
            p("\n=== VALIDACION ===")
            for tabla in ("area", "cargo", "motivo", "tipo_permiso", "estado",
                          "colaborador", "solicitud_salida", "firma", "rechazos"):
                cur.execute(f"SELECT COUNT(*) FROM {tabla}")
                p(f"  {tabla:20} {cur.fetchone()[0]}")
            cur.execute("SELECT MIN(fecha_permiso), MAX(fecha_permiso), SUM(total_horas_permiso) FROM solicitud_salida")
            p(f"  rango/suma horas: {cur.fetchone()}")
            cur.execute("SELECT COUNT(*) FROM solicitud_salida WHERE colaborador_gh_id IS NULL")
            p(f"  solicitudes sin colaborador: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM firma WHERE solicitud_id IS NULL")
            p(f"  firmas sin solicitud: {cur.fetchone()[0]}")
    except Exception as e:
        conn.rollback()
        p(f"[ERROR] Se revirtio la transaccion: {type(e).__name__}: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
