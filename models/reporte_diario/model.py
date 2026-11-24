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
    'muertas': 'int',
    'mort_m1': 'int',
    'mort_m2': 'int',
    'mort_m3': 'int',
    'mort_m4': 'int',
    'otras': 'int',
    'agua': 'dec',
    'silo': 'dec',
}

CAMPOS_TEXTO = (
    'proceso',
    'otras_motivo',
    'entrada_tipo',
    'entrada_producto',
    'desinfeccion',
    'desinfeccion_producto',
    'gallinaza',
    'cierra_silo',
    'observaciones',
)

PROCESOS_VALIDOS = ('I. MEDICACION', 'F. MEDICACION', 'INYECCION')

# Paleta para procesos nuevos (colores claros, texto oscuro legible).
PROCESOS_PALETA = (
    '#35c6ea', '#ffe600', '#e8b8b8', '#a5d6a7', '#ce93d8',
    '#ffcc80', '#90caf9', '#f48fb1', '#b0bec5', '#c5e1a5',
)
COLOR_PROCESO_DEFECTO = '#35c6ea'


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


def listar_procesos(solo_activos=True):
    """Catalogo de procesos (nombre y color) para el Reporte Diario."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        sql = 'SELECT id, nombre, color, activo FROM procesos'
        if solo_activos:
            sql += ' WHERE activo = true'
        sql += ' ORDER BY id ASC'
        cur.execute(sql)
        return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"[REPORTE DIARIO] No se pudo leer el catalogo de procesos: {e}")
        return [
            {'id': i + 1, 'nombre': nombre, 'color': color, 'activo': True}
            for i, (nombre, color) in enumerate(zip(PROCESOS_VALIDOS, PROCESOS_PALETA))
        ]
    finally:
        cur.close()
        conn.close()


def _nombres_catalogo():
    """Nombres permitidos (incluye inactivos para no perder historicos)."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('SELECT nombre FROM procesos')
        nombres = {fila[0] for fila in cur.fetchall()}
        return nombres or set(PROCESOS_VALIDOS)
    except Exception as e:
        print(f"[REPORTE DIARIO] No se pudo validar el catalogo de procesos: {e}")
        return set(PROCESOS_VALIDOS)
    finally:
        cur.close()
        conn.close()


def _color_libre():
    """Primer color de la paleta que no este usado por un proceso activo."""
    usados = {p.get('color') for p in listar_procesos(solo_activos=True)}
    for color in PROCESOS_PALETA:
        if color not in usados:
            return color
    return PROCESOS_PALETA[len(usados) % len(PROCESOS_PALETA)]


def crear_proceso(nombre, color=None):
    """Crea (o recupera) un proceso del catalogo.

    Devuelve {'id', 'nombre', 'color', 'existente'}.
    """
    nombre = ' '.join(str(nombre or '').split()).upper()[:40]
    if not nombre:
        raise ValueError('Escribe el nombre del proceso')

    if not re.match(r'^#[0-9a-fA-F]{6}$', str(color or '')):
        color = _color_libre()
    color = color.lower()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            INSERT INTO procesos (nombre, color)
            VALUES (%s, %s)
            ON CONFLICT (nombre) DO NOTHING
            RETURNING id, nombre, color
            """,
            (nombre, color),
        )
        fila = cur.fetchone()
        existente = False
        if not fila:
            cur.execute(
                'SELECT id, nombre, color FROM procesos WHERE nombre = %s',
                (nombre,),
            )
            fila = cur.fetchone()
            existente = True
        conn.commit()
        salida = dict(fila)
        salida['existente'] = existente
        return salida
    except Exception:
        conn.rollback()
        raise
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


def _procesos_por_reporte(ids):
    """{id_reporte: [{proceso, modulos}]} para los ids indicados."""
    if not ids:
        return {}
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT id_reporte, proceso, modulos, orden
            FROM reporte_diario_procesos
            WHERE id_reporte = ANY(%s)
            ORDER BY orden ASC, id ASC
            """,
            (list(ids),),
        )
        resultado = {}
        for fila in cur.fetchall():
            resultado.setdefault(fila['id_reporte'], []).append({
                'proceso': fila['proceso'],
                'modulos': [int(m) for m in (fila['modulos'] or [])],
            })
        return resultado
    except Exception as e:
        print(f"[REPORTE DIARIO] No se pudieron leer los procesos: {e}")
        return {}
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
            SELECT id, fecha, produccion, alimento, muertas,
                   mort_m1, mort_m2, mort_m3, mort_m4, mort_total,
                   otras, otras_motivo, proceso, afecta_saldo, saldo_aves,
                   agua, silo,
                   entrada_tipo, entrada_producto, desinfeccion, desinfeccion_producto,
                   gallinaza, cierra_silo, observaciones, registrado_por
            FROM reporte_diario
            WHERE id_lote = %s
              AND EXTRACT(YEAR  FROM fecha) = %s
              AND EXTRACT(MONTH FROM fecha) = %s
            ORDER BY fecha ASC
            """,
            (id_lote, anio, mes),
        )
        filas = cur.fetchall()
    except Exception as e:
        print(f"[REPORTE DIARIO] Error consultando el mes: {e}")
        return []
    finally:
        cur.close()
        conn.close()

    procesos = _procesos_por_reporte([f['id'] for f in filas])
    for fila in filas:
        lista = procesos.get(fila['id'], [])
        fila['procesos'] = lista
        por_modulo = {}
        for p in lista:
            for m in p.get('modulos') or []:
                por_modulo.setdefault(int(m), []).append(p['proceso'])
        fila['procesos_por_modulo'] = por_modulo
    return filas


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
            muertes = int(datos.get('muertas') or 0)
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
    if campo in CAMPOS_NUMERICOS:
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


def guardar_procesos(id_lote, lote, fecha, procesos):
    """Guarda la lista de procesos del día y los módulos de cada uno.

    Reglas:
      - Solo los tres procesos válidos.
      - Un proceso no se repite en el mismo día.
      - Módulos entre 1 y 4, sin repetir.
      - Máximo 3 procesos.
      - El orden de la lista es el orden de captura.
    """
    if not isinstance(procesos, list):
        raise ValueError('La lista de procesos no es válida')

    limpios = []
    vistos = set()
    validos = _nombres_catalogo()
    for item in procesos:
        if not isinstance(item, dict):
            continue
        nombre = str(item.get('proceso') or '').strip()
        if not nombre:
            continue
        if nombre not in validos:
            raise ValueError(f'Proceso no válido: {nombre}')
        if nombre in vistos:
            raise ValueError(f'El proceso {nombre} ya está agregado')
        vistos.add(nombre)

        modulos = item.get('modulos') or []
        if not isinstance(modulos, (list, tuple)):
            modulos = [modulos]
        limpios_mods = []
        for m in modulos:
            try:
                numero = int(m)
            except (TypeError, ValueError):
                continue
            if 1 <= numero <= 4 and numero not in limpios_mods:
                limpios_mods.append(numero)
        limpios_mods.sort()
        limpios.append({'proceso': nombre, 'modulos': limpios_mods})

    if len(limpios) > 3:
        raise ValueError('Máximo 3 procesos por día')

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO reporte_diario (id_lote, lote, fecha)
            VALUES (%s, %s, %s)
            ON CONFLICT (id_lote, fecha)
            DO UPDATE SET actualizado_en = now()
            RETURNING id
            """,
            (id_lote, lote, fecha),
        )
        id_reporte = cur.fetchone()[0]

        cur.execute(
            'DELETE FROM reporte_diario_procesos WHERE id_reporte = %s',
            (id_reporte,),
        )
        for orden, p in enumerate(limpios):
            cur.execute(
                """
                INSERT INTO reporte_diario_procesos
                    (id_reporte, proceso, modulos, orden)
                VALUES (%s, %s, %s, %s)
                """,
                (id_reporte, p['proceso'], p['modulos'], orden),
            )

        # Compatibilidad: la columna vieja guarda el primer proceso.
        primero = limpios[0]['proceso'] if limpios else None
        cur.execute(
            'UPDATE reporte_diario SET proceso = %s, actualizado_en = now() WHERE id = %s',
            (primero, id_reporte),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    return limpios


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


def listar_desinfectantes(solo_activos=True):
    """Catalogo de productos de desinfeccion."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        sql = "SELECT id, nombre FROM desinfectantes"
        if solo_activos:
            sql += " WHERE activo = true"
        sql += " ORDER BY nombre ASC"
        cur.execute(sql)
        return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"[REPORTE DIARIO] No se pudo leer el catalogo de desinfectantes: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def crear_desinfectante(nombre):
    """Crea (o reactiva) un desinfectante. Devuelve {'id', 'nombre'}."""
    nombre = str(nombre or '').strip()
    if not nombre:
        raise ValueError('Escribe el nombre del producto')
    nombre = nombre[:120]

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            INSERT INTO desinfectantes (nombre)
            VALUES (%s)
            ON CONFLICT (nombre) DO UPDATE SET activo = true
            RETURNING id, nombre
            """,
            (nombre,),
        )
        fila = cur.fetchone()
        conn.commit()
        return dict(fila)
    finally:
        cur.close()
        conn.close()


def modulos_entrada(id_lote):
    """Módulos junto a los que está la puerta/entrada del galpón (1-4)."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT modulos_entrada FROM reporte_diario_config WHERE id_lote = %s",
            (id_lote,),
        )
        fila = cur.fetchone()
        if not fila or not fila[0]:
            return []
        return [int(x) for x in str(fila[0]).split(',') if str(x).strip().isdigit()]
    except Exception as e:
        print(f"[REPORTE DIARIO] No se pudo leer la configuración: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def guardar_modulos_entrada(id_lote, modulos):
    """Guarda el módulo donde está la puerta del galpón (solo uno)."""
    limpios = sorted({
        int(m) for m in modulos
        if str(m).strip().isdigit() and 1 <= int(m) <= 4
    })
    texto = str(limpios[0]) if limpios else ''

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO reporte_diario_config (id_lote, modulos_entrada)
            VALUES (%s, %s)
            ON CONFLICT (id_lote)
            DO UPDATE SET modulos_entrada = EXCLUDED.modulos_entrada,
                          actualizado_en = now()
            """,
            (id_lote, texto),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    return [int(texto)] if texto else []


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
