# models/reporte_diario/model.py
"""Reporte Diario: captura operativa por lote y día (fase 1, solo lectura)."""

import calendar
import re
from datetime import date
from decimal import Decimal

import psycopg2.extras

from models.base import get_db_connection

MESES = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

# Campos que se pueden editar desde el grid
CAMPOS_NUMERICOS = {
    'produccion': 'int',
    'alimento': 'dec',
    'mort_m1': 'int',
    'mort_m2': 'int',
    'mort_m3': 'int',
    'mort_m4': 'int',
    'otras': 'int',
    'agua': 'dec',
    'silo': 'dec',
}

CAMPOS_TEXTO = (
    'otras_motivo',
    'entrada_tipo',
    'entrada_producto',
    'desinfeccion',
    'desinfeccion_producto',
    'gallinaza',
    'cierra_silo',
    'observaciones',
)


def tabla_disponible():
    """True si la migración de `reporte_diario` ya se ejecutó."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT to_regclass('public.reporte_diario')")
        fila = cur.fetchone()
        return bool(fila and fila[0])
    except Exception as e:
        print(f"[REPORTE DIARIO] No se pudo verificar la tabla: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def cabecera_lote(lote):
    """Datos del lote necesarios para el reporte (solo lectura, sin crear nada)."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT id, lote, fecha_recepcion, fecha_encasetamiento,
                   no_aves_encasetadas, no_pollitas_recibidas,
                   granja_prod, tipo_lote, variedad
            FROM cabecera_lotes
            WHERE lote = %s
            LIMIT 1
            """,
            (lote,),
        )
        return cur.fetchone()
    except Exception as e:
        print(f"[REPORTE DIARIO] Error leyendo la cabecera del lote: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def saldo_inicial(id_lote, anio, mes):
    """
    Saldo de aves con el que arranca el mes: el último que registró el
    módulo Diario antes del día 1. Si no hay histórico, devuelve None.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT saldo_aves
            FROM data_diario
            WHERE id_lote = %s
              AND fecha_dia < %s
              AND saldo_aves IS NOT NULL
            ORDER BY fecha_dia DESC
            LIMIT 1
            """,
            (id_lote, f'{anio:04d}-{mes:02d}-01'),
        )
        fila = cur.fetchone()
        return int(fila[0]) if fila and fila[0] is not None else None
    except Exception as e:
        print(f"[REPORTE DIARIO] No se pudo leer el saldo inicial: {e}")
        return None
    finally:
        cur.close()
        conn.close()


def _filas_del_mes(id_lote, anio, mes):
    """Trae las filas guardadas del lote para el mes indicado."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT id, fecha, produccion, alimento,
                   mort_m1, mort_m2, mort_m3, mort_m4, mort_total,
                   otras, otras_motivo, afecta_saldo, saldo_aves,
                   agua, silo,
                   entrada_tipo, entrada_producto, desinfeccion, desinfeccion_producto,
                   modulo_entrada,
                   gallinaza, cierra_silo, observaciones, registrado_por
            FROM reporte_diario
            WHERE id_lote = %s
              AND EXTRACT(YEAR  FROM fecha) = %s
              AND EXTRACT(MONTH FROM fecha) = %s
            ORDER BY fecha ASC
            """,
            (id_lote, anio, mes),
        )
        return cur.fetchall()
    except Exception as e:
        print(f"[REPORTE DIARIO] Error consultando el mes: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def listar_mes(id_lote, anio, mes, saldo_apertura=0):
    """
    Devuelve todos los días del mes con sus datos (o vacíos) y el saldo
    de aves arrastrado día a día, igual que la hoja de Excel.

    Regla del saldo:
        saldo_dia = saldo_anterior - muertes_del_dia
                    (- otras, si la fila marca afecta_saldo)
    Los días sin registro mantienen el saldo anterior.
    """
    registros = {fila['fecha']: dict(fila) for fila in _filas_del_mes(id_lote, anio, mes)}

    total_dias = calendar.monthrange(anio, mes)[1]
    saldo = int(saldo_apertura or 0)

    filas = []
    totales = {
        'produccion': 0, 'alimento': 0,
        'm1': 0, 'm2': 0, 'm3': 0, 'm4': 0, 'total': 0,
        'otras': 0, 'agua': 0, 'silo': 0, 'dias': 0,
    }

    for dia in range(1, total_dias + 1):
        fecha = date(anio, mes, dia)
        datos = registros.get(fecha)

        if datos:
            muertes = int(datos.get('mort_total') or 0)
            otras = int(datos.get('otras') or 0)
            descuenta = datos.get('afecta_saldo', True)
            saldo = saldo - muertes - (otras if descuenta else 0)

            totales['produccion'] += int(datos.get('produccion') or 0)
            totales['alimento'] += float(datos.get('alimento') or 0)
            totales['m1'] += int(datos.get('mort_m1') or 0)
            totales['m2'] += int(datos.get('mort_m2') or 0)
            totales['m3'] += int(datos.get('mort_m3') or 0)
            totales['m4'] += int(datos.get('mort_m4') or 0)
            totales['total'] += muertes
            totales['otras'] += otras
            totales['agua'] += float(datos.get('agua') or 0)
            totales['silo'] += float(datos.get('silo') or 0)
            totales['dias'] += 1

        filas.append({
            'fecha': fecha,
            'dia': fecha.strftime('%d-%m'),
            'datos': datos,
            'saldo': saldo,
        })

    totales['saldo_final'] = saldo
    return filas, totales


def guardar_campo(id_lote, lote, fecha, campo, valor):
    """
    Guarda (o crea) el valor de una celda del reporte para un lote y fecha.
    Solo acepta los campos de la lista blanca; el nombre de la columna nunca
    llega a la consulta sin haber sido validado.
    """
    if campo == 'modulo_entrada':
        texto = str(valor).strip() if valor is not None else ''
        valor_db = int(texto) if texto.isdigit() and 1 <= int(texto) <= 4 else None
    elif campo in CAMPOS_NUMERICOS:
        tipo = CAMPOS_NUMERICOS[campo]
        limpio = re.sub(r'[^0-9.\-]', '', str(valor if valor is not None else '') or '')
        if limpio in ('', '-', '.', '-.'):
            valor_db = 0
        else:
            try:
                valor_db = int(float(limpio)) if tipo == 'int' else float(limpio)
            except ValueError:
                raise ValueError('El valor no es un número válido')
        if valor_db < 0:
            valor_db = 0
    elif campo in CAMPOS_TEXTO:
        texto = str(valor).strip() if valor is not None else ''
        valor_db = texto or None
    else:
        raise ValueError('Campo no permitido')

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            INSERT INTO reporte_diario (id_lote, lote, fecha, {campo})
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id_lote, fecha)
            DO UPDATE SET {campo} = EXCLUDED.{campo}, actualizado_en = now()
            """,
            (id_lote, lote, fecha, valor_db),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    return valor_db


def mort_total_de(id_lote, fecha):
    """Total de muertes del día (columna generada por PostgreSQL)."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT mort_total FROM reporte_diario WHERE id_lote = %s AND fecha = %s",
            (id_lote, fecha),
        )
        fila = cur.fetchone()
        return int(fila[0]) if fila and fila[0] is not None else 0
    except Exception as e:
        print(f"[REPORTE DIARIO] No se pudo leer el total: {e}")
        return 0
    finally:
        cur.close()
        conn.close()


def estado_mes(id_lote, anio, mes, saldo_apertura):
    """
    Recalcula el mes y devuelve datos listos para JSON:
    saldos por día y totales.
    """
    filas, totales = listar_mes(id_lote, anio, mes, saldo_apertura)

    saldos = {f['fecha'].isoformat(): int(f['saldo']) for f in filas}

    totales_json = {}
    for clave, valor in totales.items():
        totales_json[clave] = float(valor) if isinstance(valor, Decimal) else valor

    return saldos, totales_json
