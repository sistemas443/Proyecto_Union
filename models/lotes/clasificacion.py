"""Clasificación de lotes en ACTIVO o CONCLUIDO."""
from datetime import date, datetime

from models.base import get_db_connection

SAN_MARTIN = "SAN MARTIN"


def _a_fecha(valor):
    """Convierte date, datetime o texto ISO a date."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor).strip()[:10])
    except (TypeError, ValueError):
        return None


def clasificar_lote(empresa, levante_externo, fecha_sem82, estado_manual=None, hoy=None):
    """Devuelve CONCLUIDO o ACTIVO según las reglas del lote.

    - Si estado_manual es ACTIVO o CONCLUIDO, manda el valor manual.
    - Empresa distinta a SAN MARTIN y Levante externo = SI -> CONCLUIDO.
    - Empresa distinta a SAN MARTIN y Levante externo = NO -> ACTIVO.
    - SAN MARTIN: si la semana 82 ya terminó (fecha <= hoy) -> CONCLUIDO;
      si aún no termina (fecha > hoy) o no hay fecha -> ACTIVO.
    """
    manual = (estado_manual or "").strip().upper()
    if manual in ("ACTIVO", "CONCLUIDO"):
        return manual

    hoy = hoy or date.today()
    nombre = (empresa or "").strip().upper()
    if nombre != SAN_MARTIN:
        return "CONCLUIDO" if levante_externo else "ACTIVO"
    fecha = _a_fecha(fecha_sem82)
    if fecha is None:
        return "ACTIVO"
    return "CONCLUIDO" if fecha <= hoy else "ACTIVO"


def fetch_clasificacion_lotes(nombres=None):
    """Devuelve {lote: {empresa, levante_externo, fecha_sem82, estado}}."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        sql = """
            SELECT c.lote, e.nombre, c.levante_externo, c.variedad, c.estado_manual,
                   (SELECT b.fecha_fin_sem
                      FROM bd_vargas b
                     WHERE b.id_lote = c.id AND b.sem_prod = 82
                     ORDER BY b.id_sem_prod DESC
                     LIMIT 1)
              FROM cabecera_lotes c
              LEFT JOIN empresas e ON e.id = c.empresa_id
        """
        params = None
        if nombres:
            sql += " WHERE c.lote = ANY(%s)"
            params = (list(nombres),)
        sql += " ORDER BY c.lote"
        cur.execute(sql, params)

        resultado = {}
        for lote, empresa, levante_externo, variedad, estado_manual, fecha in cur.fetchall():
            resultado[lote] = {
                'empresa': empresa,
                'levante_externo': bool(levante_externo),
                'variedad': variedad,
                'estado_manual': estado_manual,
                'fecha_sem82': fecha,
                'estado': clasificar_lote(
                    empresa, levante_externo, fecha, estado_manual
                ),
            }
        return resultado
    finally:
        cur.close()
        conn.close()
