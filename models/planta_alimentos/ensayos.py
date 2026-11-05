# -*- coding: utf-8 -*-
"""
Insumos de ensayo de una dieta.

Un ensayo es una materia prima que se suma a la receta durante uno o varios
rangos de fechas. No forma parte de `formula_detalle`: vive en sus propias
tablas y solo se tiene en cuenta cuando la fecha evaluada cae dentro de
alguno de sus rangos.

Reglas:
- Varios ensayos por dieta/lote, incluso simultaneos (distinta materia prima).
- Un mismo insumo no puede tener rangos solapados en la misma dieta/lote.
- Inactivar = finalizar (cierra los rangos) o eliminar (baja logica).
- Nada se borra fisicamente.
"""
from datetime import date

from models.base import get_db_connection


def _fecha(valor):
    if isinstance(valor, date):
        return valor
    if not valor:
        return None
    texto = str(valor).strip()[:10]
    return date.fromisoformat(texto)


def _numero(valor, defecto=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def _costo(cantidad, precio, iva, flete):
    cantidad = _numero(cantidad)
    precio = _numero(precio)
    iva = _numero(iva, 1.0) or 1.0
    flete = _numero(flete)
    return {
        'costo_iva': cantidad * (precio * iva),
        'costo_flete': cantidad * (precio + flete),
        'costo_iva_flete': cantidad * ((precio * iva) + flete),
    }


def _estado(ensayo, rangos, hoy):
    if ensayo.get('eliminado_en'):
        return 'Eliminado'
    if not rangos:
        return 'Finalizado' if ensayo.get('finalizado_en') else 'Programado'
    if any(r['desde'] <= hoy <= r['hasta'] for r in rangos):
        return 'Activo'
    if all(r['desde'] > hoy for r in rangos):
        return 'Programado'
    if all(r['hasta'] < hoy for r in rangos):
        return 'Finalizado'
    return 'En pausa'


class Ensayo:

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    @staticmethod
    def listar(item_id, lote_id, incluir_eliminados=False):
        """Ensayos de una dieta/lote con sus rangos y costos calculados."""
        hoy = date.today()
        filtro = '' if incluir_eliminados else 'AND e.eliminado_en IS NULL'
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT e.id, e.item_id, e.lote_id, e.materia_prima_id,
                           mp.nombre AS insumo,
                           e.cantidad_kg, e.motivo, e.creado_por, e.creado_en,
                           e.finalizado_por, e.finalizado_en, e.eliminado_en, e.eliminado_por,
                           COALESCE(NULLIF(e.precio_guardado, 0), mp.precio_actual_kg) AS precio,
                           COALESCE(e.iva_guardado, mp.iva, 1) AS iva,
                           COALESCE(e.flete_guardado, mp.flete, 0) AS flete
                    FROM formula_ensayos e
                    JOIN materias_primas mp ON mp.id = e.materia_prima_id
                    WHERE e.item_id = %s AND e.lote_id = %s {filtro}
                    ORDER BY e.id
                """, (item_id, lote_id))
                columnas = [d[0] for d in cur.description]
                filas = [dict(zip(columnas, f)) for f in cur.fetchall()]

                ids = [f['id'] for f in filas]
                rangos_por_ensayo = {i: [] for i in ids}
                if ids:
                    cur.execute("""
                        SELECT id, ensayo_id, desde, hasta
                        FROM formula_ensayo_rangos
                        WHERE ensayo_id = ANY(%s)
                        ORDER BY desde
                    """, (ids,))
                    for r in cur.fetchall():
                        rangos_por_ensayo[r[1]].append({
                            'id': r[0],
                            'desde': r[2],
                            'hasta': r[3],
                            'dias': (r[3] - r[2]).days + 1,
                        })

            for f in filas:
                f['rangos'] = rangos_por_ensayo.get(f['id'], [])
                f['cantidad_kg'] = _numero(f['cantidad_kg'])
                f.update(_costo(f['cantidad_kg'], f['precio'], f['iva'], f['flete']))
                f['estado'] = _estado(f, f['rangos'], hoy)
                f['hoy_activo'] = any(r['desde'] <= hoy <= r['hasta'] for r in f['rangos'])
                futuros = [r['desde'] for r in f['rangos'] if r['desde'] > hoy]
                f['proximo'] = min(futuros) if futuros else None
                f['dias_total'] = sum(r['dias'] for r in f['rangos'])
            return filas
        finally:
            conn.close()

    @staticmethod
    def obtener(ensayo_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, item_id, lote_id, materia_prima_id, cantidad_kg, motivo,
                           creado_por, eliminado_en, finalizado_en
                    FROM formula_ensayos WHERE id = %s
                """, (ensayo_id,))
                fila = cur.fetchone()
                if not fila:
                    return None
                columnas = [d[0] for d in cur.description]
                return dict(zip(columnas, fila))
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Validaciones
    # ------------------------------------------------------------------
    @staticmethod
    def _rangos_normalizados(rangos):
        limpios = []
        for r in rangos or []:
            desde = _fecha(r.get('desde'))
            hasta = _fecha(r.get('hasta')) or desde
            if not desde:
                continue
            if hasta < desde:
                return None, 'La fecha final de un rango no puede ser anterior a la inicial.'
            limpios.append((desde, hasta))
        limpios.sort()
        if not limpios:
            return None, 'Debe indicar al menos un rango de fechas.'
        return limpios, None

    @staticmethod
    def _solapes(item_id, lote_id, materia_prima_id, rangos, excluir_id=None):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                for desde, hasta in rangos:
                    sql = """
                        SELECT e.id, mp.nombre, r.desde, r.hasta
                        FROM formula_ensayo_rangos r
                        JOIN formula_ensayos e ON e.id = r.ensayo_id
                        JOIN materias_primas mp ON mp.id = e.materia_prima_id
                        WHERE e.item_id = %s AND e.lote_id = %s
                          AND e.materia_prima_id = %s
                          AND e.eliminado_en IS NULL
                          AND r.desde <= %s AND r.hasta >= %s
                    """
                    params = [item_id, lote_id, materia_prima_id, hasta, desde]
                    if excluir_id:
                        sql += ' AND e.id <> %s'
                        params.append(excluir_id)
                    cur.execute(sql + ' LIMIT 1', tuple(params))
                    fila = cur.fetchone()
                    if fila:
                        return (f"El insumo {fila[1]} ya tiene un ensayo que se cruza "
                                f"({fila[2].strftime('%d/%m/%Y')} a {fila[3].strftime('%d/%m/%Y')}).")
            return None
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Altas y cambios
    # ------------------------------------------------------------------
    @staticmethod
    def crear(item_id, lote_id, materia_prima_id, cantidad_kg, motivo, rangos, usuario):
        cantidad = _numero(cantidad_kg)
        if cantidad <= 0:
            return {'ok': False, 'msg': 'La cantidad debe ser mayor a 0.'}

        limpios, error = Ensayo._rangos_normalizados(rangos)
        if error:
            return {'ok': False, 'msg': error}

        solape = Ensayo._solapes(item_id, lote_id, materia_prima_id, limpios)
        if solape:
            return {'ok': False, 'msg': solape}

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO formula_ensayos
                        (item_id, lote_id, materia_prima_id, cantidad_kg,
                         precio_guardado, iva_guardado, flete_guardado,
                         motivo, creado_por)
                    SELECT %s, %s, %s, %s, precio_actual_kg, iva, flete, %s, %s
                    FROM materias_primas WHERE id = %s
                    RETURNING id
                """, (item_id, lote_id, materia_prima_id, cantidad, motivo, usuario, materia_prima_id))
                fila = cur.fetchone()
                if not fila:
                    conn.rollback()
                    return {'ok': False, 'msg': 'La materia prima no existe.'}
                ensayo_id = fila[0]

                for desde, hasta in limpios:
                    cur.execute("""
                        INSERT INTO formula_ensayo_rangos (ensayo_id, desde, hasta)
                        VALUES (%s, %s, %s)
                    """, (ensayo_id, desde, hasta))
            conn.commit()
            return {'ok': True, 'id': ensayo_id}
        except Exception as e:
            conn.rollback()
            print(f'Error al crear ensayo: {e}')
            return {'ok': False, 'msg': 'No se pudo guardar el ensayo.'}
        finally:
            conn.close()

    @staticmethod
    def editar(ensayo_id, cantidad_kg, motivo, rangos, usuario):
        ensayo = Ensayo.obtener(ensayo_id)
        if not ensayo or ensayo['eliminado_en']:
            return {'ok': False, 'msg': 'El ensayo no existe o está eliminado.'}

        cantidad = _numero(cantidad_kg)
        if cantidad <= 0:
            return {'ok': False, 'msg': 'La cantidad debe ser mayor a 0.'}

        limpios, error = Ensayo._rangos_normalizados(rangos)
        if error:
            return {'ok': False, 'msg': error}

        solape = Ensayo._solapes(ensayo['item_id'], ensayo['lote_id'],
                                 ensayo['materia_prima_id'], limpios, excluir_id=ensayo_id)
        if solape:
            return {'ok': False, 'msg': solape}

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE formula_ensayos
                    SET cantidad_kg = %s, motivo = %s
                    WHERE id = %s
                """, (cantidad, motivo, ensayo_id))
                cur.execute("DELETE FROM formula_ensayo_rangos WHERE ensayo_id = %s", (ensayo_id,))
                for desde, hasta in limpios:
                    cur.execute("""
                        INSERT INTO formula_ensayo_rangos (ensayo_id, desde, hasta)
                        VALUES (%s, %s, %s)
                    """, (ensayo_id, desde, hasta))
            conn.commit()
            return {'ok': True}
        except Exception as e:
            conn.rollback()
            print(f'Error al editar ensayo: {e}')
            return {'ok': False, 'msg': 'No se pudo actualizar el ensayo.'}
        finally:
            conn.close()

    @staticmethod
    def finalizar(ensayo_id, usuario, hasta=None):
        """Cierra el ensayo: recorta los rangos a 'hasta' y borra los futuros."""
        hasta = _fecha(hasta) or date.today()
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM formula_ensayos WHERE id = %s", (ensayo_id,))
                if not cur.fetchone():
                    return {'ok': False, 'msg': 'El ensayo no existe.'}
                cur.execute("""
                    DELETE FROM formula_ensayo_rangos
                    WHERE ensayo_id = %s AND desde > %s
                """, (ensayo_id, hasta))
                cur.execute("""
                    UPDATE formula_ensayo_rangos
                    SET hasta = %s
                    WHERE ensayo_id = %s AND hasta > %s
                """, (hasta, ensayo_id, hasta))
                cur.execute("""
                    UPDATE formula_ensayos
                    SET finalizado_en = now(), finalizado_por = %s
                    WHERE id = %s
                """, (usuario, ensayo_id))
            conn.commit()
            return {'ok': True}
        except Exception as e:
            conn.rollback()
            print(f'Error al finalizar ensayo: {e}')
            return {'ok': False, 'msg': 'No se pudo finalizar el ensayo.'}
        finally:
            conn.close()

    @staticmethod
    def produccion_en_rangos(ensayo_id):
        """Cuantas producciones caen dentro de los rangos del ensayo."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*)
                    FROM formula_produccion_diaria fpd
                    JOIN formula_ensayos e
                      ON e.item_id = fpd.item_id AND e.lote_id = fpd.lote_id
                    JOIN formula_ensayo_rangos r ON r.ensayo_id = e.id
                    WHERE e.id = %s
                      AND fpd.fecha BETWEEN r.desde AND r.hasta
                """, (ensayo_id,))
                return cur.fetchone()[0] or 0
        finally:
            conn.close()

    @staticmethod
    def eliminar(ensayo_id, usuario, forzar=False):
        """Baja logica. Si ya hubo produccion, exige forzar=True."""
        produccion = Ensayo.produccion_en_rangos(ensayo_id)
        if produccion and not forzar:
            return {
                'ok': False,
                'produccion': produccion,
                'msg': (f'Este ensayo tiene {produccion} producción(es) registrada(s). '
                        'Finalízalo para conservar el histórico o elimínalo confirmando.'),
            }

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE formula_ensayos
                    SET eliminado_en = now(), eliminado_por = %s
                    WHERE id = %s AND eliminado_en IS NULL
                """, (usuario, ensayo_id))
                afectadas = cur.rowcount
            conn.commit()
            if not afectadas:
                return {'ok': False, 'msg': 'El ensayo ya estaba eliminado.'}
            return {'ok': True, 'produccion': produccion}
        except Exception as e:
            conn.rollback()
            print(f'Error al eliminar ensayo: {e}')
            return {'ok': False, 'msg': 'No se pudo eliminar el ensayo.'}
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Uso desde costos, inventario y proyecciones
    # ------------------------------------------------------------------
    @staticmethod
    def vigentes_en(item_id, lote_id, fecha):
        """Ensayos activos en una fecha, con precio congelado."""
        fecha = _fecha(fecha) or date.today()
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT e.id, e.materia_prima_id, mp.nombre AS insumo,
                           e.cantidad_kg,
                           COALESCE(NULLIF(e.precio_guardado, 0), mp.precio_actual_kg) AS precio,
                           COALESCE(e.iva_guardado, mp.iva, 1) AS iva,
                           COALESCE(e.flete_guardado, mp.flete, 0) AS flete
                    FROM formula_ensayos e
                    JOIN materias_primas mp ON mp.id = e.materia_prima_id
                    WHERE e.item_id = %s AND e.lote_id = %s
                      AND e.eliminado_en IS NULL
                      AND EXISTS (
                          SELECT 1 FROM formula_ensayo_rangos r
                          WHERE r.ensayo_id = e.id
                            AND %s::date BETWEEN r.desde AND r.hasta
                      )
                    ORDER BY mp.nombre
                """, (item_id, lote_id, fecha))
                columnas = [d[0] for d in cur.description]
                filas = [dict(zip(columnas, f)) for f in cur.fetchall()]
            for f in filas:
                f['cantidad_kg'] = _numero(f['cantidad_kg'])
                f.update(_costo(f['cantidad_kg'], f['precio'], f['iva'], f['flete']))
            return filas
        finally:
            conn.close()

    @staticmethod
    def resumen(item_id, lote_id, fecha):
        """Totales de ensayos activos: kg y costos (misma escala que la receta)."""
        filas = Ensayo.vigentes_en(item_id, lote_id, fecha)
        return {
            'kg': sum(f['cantidad_kg'] for f in filas),
            'costo_iva': sum(f['costo_iva'] for f in filas),
            'costo_flete': sum(f['costo_flete'] for f in filas),
            'costo_iva_flete': sum(f['costo_iva_flete'] for f in filas),
            'ensayos': filas,
        }

    @staticmethod
    def consumo_dia(ensayo, fecha, toneladas):
        """Consumo de un ensayo en una produccion (misma unidad que la tabla).

        Se usa cantidad_kg * toneladas, igual que los insumos de la receta.
        Devuelve None cuando la fecha no cae en ningun rango.
        """
        activo = any(r['desde'] <= fecha <= r['hasta'] for r in ensayo.get('rangos', []))
        if not activo:
            return None
        return _numero(ensayo.get('cantidad_kg')) * _numero(toneladas)

    # ------------------------------------------------------------------
    # Replicacion a otros lotes
    # ------------------------------------------------------------------
    @staticmethod
    def replicar(item_id, lote_origen, lotes_destino, usuario):
        """Copia los ensayos abiertos (no eliminados ni finalizados) a otros lotes.

        Omite los que ya existan con el mismo insumo y fechas solapadas.
        """
        resultado = {'creados': 0, 'omitidos': 0, 'lotes': []}
        if not lotes_destino:
            return resultado

        ensayos = [e for e in Ensayo.listar(item_id, lote_origen)
                   if e['estado'] in ('Activo', 'Programado', 'En pausa')]
        if not ensayos:
            return resultado

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                for lote in lotes_destino:
                    if lote == lote_origen:
                        continue
                    creados_lote = 0
                    for e in ensayos:
                        solape = Ensayo._solapes(
                            item_id, lote, e['materia_prima_id'],
                            [(r['desde'], r['hasta']) for r in e['rangos']])
                        if solape:
                            resultado['omitidos'] += 1
                            continue

                        cur.execute("""
                            INSERT INTO formula_ensayos
                                (item_id, lote_id, materia_prima_id, cantidad_kg,
                                 precio_guardado, iva_guardado, flete_guardado,
                                 motivo, creado_por, origen_id)
                            SELECT %s, %s, materia_prima_id, cantidad_kg,
                                   precio_guardado, iva_guardado, flete_guardado,
                                   motivo, %s, id
                            FROM formula_ensayos WHERE id = %s
                            RETURNING id
                        """, (item_id, lote, usuario, e['id']))
                        nuevo_id = cur.fetchone()[0]
                        for r in e['rangos']:
                            cur.execute("""
                                INSERT INTO formula_ensayo_rangos (ensayo_id, desde, hasta)
                                VALUES (%s, %s, %s)
                            """, (nuevo_id, r['desde'], r['hasta']))
                        creados_lote += 1
                    if creados_lote:
                        resultado['creados'] += creados_lote
                        resultado['lotes'].append(lote)
            conn.commit()
            return resultado
        except Exception as e:
            conn.rollback()
            print(f'Error al replicar ensayos: {e}')
            raise
        finally:
            conn.close()
