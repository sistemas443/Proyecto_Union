import psycopg2
from psycopg2.extras import DictCursor  
from models.base import get_db_connection


class FormulaDetalle:
    
    @staticmethod
    def obtener_consolidado_costos(desde=None, hasta=None, solo_vigentes=False):
        """
        Costos consolidados por dieta y lote para un rango de fechas.

        La vigencia se decide SOLO con fecha_vencimiento:
          - Rango de varios dias: la dieta entra si su fecha_vencimiento cae
            dentro del rango consultado.
          - Un solo dia (solo_vigentes): la dieta entra si no estaba vencida
            en esa fecha (fecha_vencimiento >= dia).

        Los precios salen del costo congelado en la version (precio_guardado /
        iva_guardado / flete_guardado); si no existe, se usa el precio actual
        de la materia prima.
        """
        from datetime import date

        if not desde:
            desde = date.today()
        if not hasta:
            hasta = desde

        if solo_vigentes:
            condicion = "fecha_vencimiento >= %s::date"
            parametros = (hasta,)
        else:
            condicion = "fecha_vencimiento BETWEEN %s::date AND %s::date"
            parametros = (desde, hasta)

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                consulta = f"""
                    WITH EnsayosBase AS (
                        -- Insumos de ensayo activos en la fecha de referencia
                        SELECT e.item_id, e.lote_id,
                               COUNT(DISTINCT e.id) AS n_ensayos,
                               SUM(e.cantidad_kg) AS e_kg,
                               SUM(e.cantidad_kg * COALESCE(NULLIF(e.precio_guardado, 0), mp.precio_actual_kg)) AS e_base,
                               SUM(e.cantidad_kg * COALESCE(e.flete_guardado, mp.flete, 0)) AS e_flete,
                               SUM(e.cantidad_kg * (COALESCE(NULLIF(e.precio_guardado, 0), mp.precio_actual_kg)
                                                   * COALESCE(e.iva_guardado, mp.iva, 1))) AS e_iva
                        FROM formula_ensayos e
                        JOIN materias_primas mp ON mp.id = e.materia_prima_id
                        WHERE e.eliminado_en IS NULL
                          AND EXISTS (
                              SELECT 1 FROM formula_ensayo_rangos r
                              WHERE r.ensayo_id = e.id
                                AND %s::date BETWEEN r.desde AND r.hasta
                          )
                        GROUP BY e.item_id, e.lote_id
                    ),
                    VersionesVigentes AS (
                        -- Version de cada receta cuya fecha de vencimiento cae en el rango
                        SELECT item_id, lote_id, MAX(version) AS version
                        FROM formula_detalle
                        WHERE {condicion}
                        GROUP BY item_id, lote_id
                    ),
                    CostosBase AS (
                        SELECT 
                            fd.item_id,
                            fd.lote_id,
                            MAX(vv.version) AS version,
                            -- Las cantidades de la receta estan en gramos por tonelada y los
                            -- precios en $/kg: el total representa el costo de 1.000 toneladas,
                            -- la misma escala que la pantalla "Costos por dieta".
                            SUM(fd.cantidad_kg * COALESCE(NULLIF(fd.precio_guardado, 0), mp.precio_actual_kg)) AS total_precio_base,
                            SUM(fd.cantidad_kg * COALESCE(fd.flete_guardado, mp.flete, 0)) AS total_flete,
                            SUM(fd.cantidad_kg * (COALESCE(NULLIF(fd.precio_guardado, 0), mp.precio_actual_kg)
                                                  * COALESCE(fd.iva_guardado, mp.iva, 1))) AS total_con_iva
                        FROM formula_detalle fd
                        JOIN VersionesVigentes vv 
                            ON fd.item_id = vv.item_id AND fd.lote_id = vv.lote_id AND fd.version = vv.version
                        JOIN materias_primas mp ON fd.materia_prima_id = mp.id
                        GROUP BY fd.item_id, fd.lote_id
                    )
                    SELECT 
                        cb.item_id,
                        cb.lote_id AS lote,
                        cb.version,
                        COALESCE(ca.nombre, 'Sin etapa en catálogo') AS etapa, 
                        e.nombre AS nombre_empresa,
                        cl.empresa_id,
                        COALESCE(dce.maquila_ton, e.costo_maquila, 0) AS maquila_ton,
                        COALESCE(dce.flete_ton, 0) AS flete_ton,
                        cb.total_precio_base,
                        cb.total_flete,
                        cb.total_con_iva,
                        COALESCE(eb.e_kg, 0)          AS kg_ensayo,
                        COALESCE(eb.n_ensayos, 0)     AS n_ensayos,
                        COALESCE(eb.e_base, 0)        AS total_ensayo_base,
                        COALESCE(eb.e_flete, 0)       AS total_ensayo_flete,
                        COALESCE(eb.e_iva, 0)         AS total_ensayo_iva,

                        -- Motivo por el cual la dieta no se puede ubicar en la empresa
                        CASE
                            WHEN cl.lote IS NULL THEN 'Lote no registrado en cabecera_lotes'
                            WHEN cl.empresa_id IS NULL THEN 'Lote sin empresa asignada'
                            WHEN e.id IS NULL THEN 'Empresa no encontrada'
                            ELSE NULL
                        END AS motivo_sin_empresa

                    FROM CostosBase cb
                    LEFT JOIN EnsayosBase eb
                           ON eb.item_id = cb.item_id AND eb.lote_id = cb.lote_id
                    LEFT JOIN catalogo_alimentos ca ON cb.item_id = ca.item_id 
                    LEFT JOIN cabecera_lotes cl ON cb.lote_id = cl.lote 
                    LEFT JOIN empresas e ON cl.empresa_id = e.id
                    LEFT JOIN dieta_costos_extra dce
                           ON dce.item_id = cb.item_id
                          AND dce.lote_id = cb.lote_id
                          AND dce.version = cb.version
                    ORDER BY e.nombre NULLS FIRST, cb.lote_id;
                """
                cur.execute(consulta, (hasta,) + tuple(parametros))
                columnas = [desc[0] for desc in cur.description]
                filas = [dict(zip(columnas, fila)) for fila in cur.fetchall()]

                # Cada dieta se devuelve en dos filas: con maquila y sin maquila.
                # La maquila entra en las columnas de IVA; el flete nuevo solo en PRECIO + FLETE.
                resultado = []
                for fila in filas:
                    maquila = float(fila.get('maquila_ton') or 0) * 1000      # por 1.000 t
                    flete_extra = float(fila.get('flete_ton') or 0) * 1000   # por 1.000 t

                    base = float(fila['total_precio_base'] or 0) + float(fila.get('total_ensayo_base') or 0)
                    flete_insumos = float(fila['total_flete'] or 0) + float(fila.get('total_ensayo_flete') or 0)
                    con_iva = float(fila['total_con_iva'] or 0) + float(fila.get('total_ensayo_iva') or 0)

                    con_maquila = dict(fila)
                    con_maquila['tipo_maquila'] = 'Con maquila'
                    con_maquila['precio_iva_maquila'] = con_iva + maquila
                    con_maquila['precio_flete_maquila'] = base + flete_insumos + flete_extra
                    con_maquila['precio_flete_iva_maquila'] = con_iva + flete_insumos + maquila

                    sin_maquila = dict(fila)
                    sin_maquila['tipo_maquila'] = 'Sin maquila'
                    sin_maquila['precio_iva_maquila'] = con_iva
                    # En la fila sin maquila el flete ingresado NO se suma
                    sin_maquila['precio_flete_maquila'] = base + flete_insumos
                    sin_maquila['precio_flete_iva_maquila'] = con_iva + flete_insumos

                    resultado.append(con_maquila)
                    resultado.append(sin_maquila)

                return resultado
        except Exception as e:
            print(f"Error al generar consolidado de costos: {e}")
            return []
        finally:
            conn.close()

    @staticmethod
    def obtener_precios_historicos(desde=None, hasta=None, solo_vigentes=False):
        """
        Precios de materias primas congelados en las versiones de receta cuya
        fecha_vencimiento cae en el rango consultado (o que no estaban vencidas
        en el dia, cuando solo_vigentes). Devuelve {materia_prima_id: {...}}.
        """
        from datetime import date

        if not desde:
            desde = date.today()
        if not hasta:
            hasta = desde

        if solo_vigentes:
            condicion = "fd.fecha_vencimiento >= %s::date"
            parametros = (hasta,)
        else:
            condicion = "fd.fecha_vencimiento BETWEEN %s::date AND %s::date"
            parametros = (desde, hasta)

        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(f"""
                    SELECT DISTINCT ON (fd.materia_prima_id)
                           fd.materia_prima_id,
                           fd.precio_guardado,
                           fd.iva_guardado,
                           fd.flete_guardado
                    FROM formula_detalle fd
                    WHERE {condicion}
                      AND COALESCE(fd.precio_guardado, 0) > 0
                    ORDER BY fd.materia_prima_id, fd.fecha_vencimiento DESC, fd.version DESC
                """, parametros)

                resultado = {
                    fila['materia_prima_id']: {
                        'precio': float(fila['precio_guardado'] or 0),
                        'iva': float(fila['iva_guardado'] or 1),
                        'flete': float(fila['flete_guardado'] or 0),
                    }
                    for fila in cur.fetchall()
                }

                # Precios de materias primas que solo aparecen en ensayos
                cur.execute("""
                    SELECT DISTINCT ON (e.materia_prima_id)
                           e.materia_prima_id,
                           e.precio_guardado, e.iva_guardado, e.flete_guardado
                    FROM formula_ensayos e
                    JOIN formula_ensayo_rangos r ON r.ensayo_id = e.id
                    WHERE e.eliminado_en IS NULL
                      AND r.desde <= %s::date AND r.hasta >= %s::date
                      AND COALESCE(e.precio_guardado, 0) > 0
                    ORDER BY e.materia_prima_id, r.desde DESC
                """, (hasta, desde))
                for fila in cur.fetchall():
                    if fila['materia_prima_id'] not in resultado:
                        resultado[fila['materia_prima_id']] = {
                            'precio': float(fila['precio_guardado'] or 0),
                            'iva': float(fila['iva_guardado'] or 1),
                            'flete': float(fila['flete_guardado'] or 0),
                        }
                return resultado
        except Exception as e:
            print(f"Error al obtener precios historicos: {e}")
            return {}
        finally:
            conn.close()
    

    @staticmethod
    def lotes_con_formulas():
        """Lista los lotes que tienen al menos una formula registrada."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT lote_id
                    FROM formula_detalle
                    WHERE lote_id IS NOT NULL AND TRIM(lote_id) <> ''
                    ORDER BY lote_id
                """)
                return [r[0] for r in cur.fetchall()]
        except Exception as e:
            print(f"Error al listar lotes con formulas: {e}")
            return []
        finally:
            conn.close()

    @staticmethod
    def costos_por_lote(lote):
        """
        Devuelve las dietas registradas de un lote con el detalle de costos de cada
        version: cantidad en gramos y costo a escala de 1.000 toneladas
        (cantidad_kg tal como esta guardada x precio por kg).

        Cada dieta incluye sus insumos y los totales con y sin maquila.
        """
        if not lote:
            return []

        MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("""
                    SELECT
                        fd.item_id,
                        fd.version,
                        COALESCE(ca.nombre, 'Dieta ' || fd.item_id) AS nombre_dieta,
                        MIN(fd.fecha_creacion) OVER (PARTITION BY fd.item_id, fd.version)    AS fecha_creacion,
                        MIN(fd.fecha_vencimiento) OVER (PARTITION BY fd.item_id, fd.version) AS fecha_vencimiento,
                        mp.nombre                 AS materia,
                        fd.cantidad_kg,
                        COALESCE(NULLIF(fd.precio_guardado, 0), mp.precio_actual_kg) AS precio,
                        COALESCE(fd.iva_guardado, mp.iva, 1)   AS iva,
                        COALESCE(fd.flete_guardado, mp.flete, 0) AS flete,
                        COALESCE(mp.es_maquila, FALSE) AS es_maquila
                    FROM formula_detalle fd
                    JOIN materias_primas mp ON mp.id = fd.materia_prima_id
                    LEFT JOIN catalogo_alimentos ca ON ca.item_id = fd.item_id
                    WHERE fd.lote_id = %s
                    ORDER BY MIN(fd.fecha_vencimiento) OVER (PARTITION BY fd.item_id, fd.version) DESC NULLS LAST,
                             fd.item_id, fd.version DESC, mp.nombre
                """, (lote,))
                filas = cur.fetchall()
        except Exception as e:
            print(f"Error al obtener costos por lote: {e}")
            return []
        finally:
            conn.close()

        dietas = {}
        for f in filas:
            clave = (f['item_id'], f['version'])
            if clave not in dietas:
                vencimiento = f['fecha_vencimiento']
                if vencimiento:
                    mes = f"{MESES[vencimiento.month - 1]} {vencimiento.year}"
                else:
                    mes = 'Sin fecha'
                dietas[clave] = {
                    'item_id': f['item_id'],
                    'version': f['version'],
                    'nombre_dieta': f['nombre_dieta'],
                    'lote': lote,
                    'fecha_creacion': f['fecha_creacion'],
                    'fecha_vencimiento': vencimiento,
                    'mes': mes,
                    'insumos': [],
                    'total_cantidad': 0.0,
                    'total_iva': 0.0,
                    'total_flete': 0.0,
                    'total_iva_flete': 0.0,
                    'sin_maquila_iva': 0.0,
                    'sin_maquila_flete': 0.0,
                    'sin_maquila_iva_flete': 0.0,
                }

            cantidad = float(f['cantidad_kg'] or 0)
            precio = float(f['precio'] or 0)
            iva = float(f['iva'] or 1)
            flete = float(f['flete'] or 0)

            costo_iva = cantidad * precio * iva
            costo_flete = cantidad * (precio + flete)
            costo_iva_flete = cantidad * ((precio * iva) + flete)

            dietas[clave]['insumos'].append({
                'materia': f['materia'],
                'cantidad': cantidad,
                'precio': precio,
                'iva': iva,
                'flete': flete,
                'es_maquila': bool(f['es_maquila']),
                'costo_iva': costo_iva,
                'costo_flete': costo_flete,
                'costo_iva_flete': costo_iva_flete,
            })

            dieta = dietas[clave]
            dieta['total_cantidad'] += cantidad
            dieta['total_iva'] += costo_iva
            dieta['total_flete'] += costo_flete
            dieta['total_iva_flete'] += costo_iva_flete
            if not f['es_maquila']:
                dieta['sin_maquila_iva'] += costo_iva
                dieta['sin_maquila_flete'] += costo_flete
                dieta['sin_maquila_iva_flete'] += costo_iva_flete

        # --- Insumos de ensayo: se muestran en la version segun su vencimiento ---
        from datetime import date
        from models.planta_alimentos.ensayos import Ensayo
        for dieta in dietas.values():
            fecha_ref = dieta['fecha_vencimiento'] or date.today()
            hoy = date.today()
            if fecha_ref > hoy:
                fecha_ref = hoy
            for ens in Ensayo.vigentes_en(dieta['item_id'], lote, fecha_ref):
                cantidad = float(ens['cantidad_kg'] or 0)
                costo_iva = float(ens['costo_iva'] or 0)
                costo_flete = float(ens['costo_flete'] or 0)
                costo_iva_flete = float(ens['costo_iva_flete'] or 0)
                dieta['insumos'].append({
                    'materia': ens['insumo'],
                    'cantidad': cantidad,
                    'precio': float(ens['precio'] or 0),
                    'iva': float(ens['iva'] or 1),
                    'flete': float(ens['flete'] or 0),
                    'es_maquila': False,
                    'es_ensayo': True,
                    'costo_iva': costo_iva,
                    'costo_flete': costo_flete,
                    'costo_iva_flete': costo_iva_flete,
                })
                dieta['total_cantidad'] += cantidad
                dieta['total_iva'] += costo_iva
                dieta['total_flete'] += costo_flete
                dieta['total_iva_flete'] += costo_iva_flete
                dieta['sin_maquila_iva'] += costo_iva
                dieta['sin_maquila_flete'] += costo_flete
                dieta['sin_maquila_iva_flete'] += costo_iva_flete

        return list(dietas.values())

    @staticmethod
    def replicar_formula(item_id, lote_origen, version, lotes_destino, usuario=None):
        """
        Copia una version de la formula a otros lotes.

        Se copian insumos, cantidades, precios congelados (precio/IVA/flete),
        el nucleo (es_nucleo y baches_nucleo) y las fechas de vigencia.
        Los lotes que ya tienen esa dieta se omiten.
        """
        resultado = {'creados': [], 'omitidos': [], 'filas': 0, 'origen': 0}
        if not lotes_destino:
            return resultado

        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("""
                    SELECT materia_prima_id, cantidad_kg, es_nucleo, baches_nucleo,
                           precio_guardado, iva_guardado, flete_guardado,
                           fecha_creacion, fecha_vencimiento
                    FROM formula_detalle
                    WHERE item_id = %s AND lote_id = %s AND version = %s
                """, (item_id, lote_origen, version))
                origen = cur.fetchall()
                resultado['origen'] = len(origen)
                if not origen:
                    return resultado

                cur.execute("""
                    SELECT DISTINCT lote_id
                    FROM formula_detalle
                    WHERE item_id = %s AND lote_id = ANY(%s)
                """, (item_id, list(lotes_destino)))
                ya_tienen = {fila['lote_id'] for fila in cur.fetchall()}

                for lote in lotes_destino:
                    if lote == lote_origen or lote in ya_tienen:
                        resultado['omitidos'].append(lote)
                        continue

                    valores = [(
                        item_id,
                        lote,
                        fila['materia_prima_id'],
                        fila['cantidad_kg'],
                        fila['es_nucleo'],
                        fila['baches_nucleo'],
                        fila['precio_guardado'],
                        fila['iva_guardado'],
                        fila['flete_guardado'],
                        fila['fecha_creacion'],
                        fila['fecha_vencimiento'],
                        1,
                    ) for fila in origen]

                    cur.executemany("""
                        INSERT INTO formula_detalle
                            (item_id, lote_id, materia_prima_id, cantidad_kg, es_nucleo, baches_nucleo,
                             precio_guardado, iva_guardado, flete_guardado,
                             fecha_creacion, fecha_vencimiento, version)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, valores)

                    resultado['filas'] += len(valores)
                    resultado['creados'].append(lote)

            conn.commit()

            # Los insumos de ensayo se replican aparte (aunque el lote ya tenga la dieta)
            from models.planta_alimentos.ensayos import Ensayo
            resultado['ensayos'] = Ensayo.replicar(item_id, lote_origen, lotes_destino,
                                                    usuario or 'Sistema')
            return resultado
        except Exception as e:
            conn.rollback()
            print(f"Error al replicar formula: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def crear_nueva_version(item_id, lote_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COALESCE(MAX(version), 1) 
                    FROM formula_detalle 
                    WHERE item_id = %s AND lote_id = %s;
                """, (item_id, lote_id))
                version_actual = cur.fetchone()[0]
                nueva_version = version_actual + 1

                cur.execute("""
                    UPDATE formula_detalle 
                    SET fecha_vencimiento = CURRENT_DATE 
                    WHERE item_id = %s AND lote_id = %s AND version = %s;
                """, (item_id, lote_id, version_actual))

                cur.execute("""
                    INSERT INTO formula_detalle 
                    (item_id, lote_id, materia_prima_id, cantidad_kg, precio_guardado, iva_guardado, flete_guardado, fecha_creacion, fecha_vencimiento, version)
                    SELECT 
                        item_id, lote_id, materia_prima_id, cantidad_kg, precio_guardado, iva_guardado, flete_guardado, 
                        CURRENT_DATE, CURRENT_DATE + INTERVAL '7 days', %s
                    FROM formula_detalle
                    WHERE item_id = %s AND lote_id = %s AND version = %s;
                """, (nueva_version, item_id, lote_id, version_actual))
                
            conn.commit()
            return nueva_version
        except Exception as e:
            print(f"Error al crear nueva versión de dieta: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
    @staticmethod
    def modificar_fecha_vencimiento(item_id, lote_id, version, nueva_fecha):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                consulta = """
                    UPDATE formula_detalle 
                    SET fecha_vencimiento = %s 
                    WHERE item_id = %s AND lote_id = %s AND version = %s;
                """
                cur.execute(consulta, (nueva_fecha, item_id, lote_id, version))
                afectadas = cur.rowcount
            conn.commit()
            return afectadas > 0
        except Exception as e:
            print(f"Error al modificar fecha de vencimiento: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    @staticmethod
    def obtener_info_versiones(item_id, lote_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Obtenemos la lista de versiones y sus fechas
                consulta = """
                    SELECT version, MAX(fecha_vencimiento) as fecha_vencimiento 
                    FROM formula_detalle 
                    WHERE item_id = %s AND lote_id = %s
                    GROUP BY version
                    ORDER BY version ASC;
                """
                cur.execute(consulta, (item_id, lote_id))
                resultados = cur.fetchall()
                
                versiones = []
                # Si no hay registros aún, asumimos la versión 1
                if not resultados:
                    return [{'version': 1, 'fecha_vencimiento': None}]
                    
                columnas = [desc[0] for desc in cur.description]
                for fila in resultados:
                    versiones.append(dict(zip(columnas, fila)))
                return versiones
        except Exception as e:
            print(f"Error al obtener versiones: {e}")
            return [{'version': 1, 'fecha_vencimiento': None}]
        finally:
            conn.close()
    @staticmethod
    def obtener_costos_detallados(item_id, lote_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                consulta = """
                    SELECT 
                        mp.nombre AS insumo,
                        fd.cantidad_kg AS cantidad,
                        COALESCE(fd.precio_guardado, mp.precio_actual_kg) AS precio,
                        COALESCE(fd.iva_guardado, mp.iva, 1.00) AS iva,
                        COALESCE(fd.flete_guardado, mp.flete, 0) AS flete,
                        COALESCE(mp.es_maquila, false) AS es_maquila,
                        ca.nombre AS nombre_dieta
                    FROM 
                        formula_detalle fd
                    JOIN 
                        materias_primas mp ON fd.materia_prima_id = mp.id
                    JOIN 
                        catalogo_alimentos ca ON fd.item_id = ca.item_id
                    WHERE 
                        fd.item_id = %s AND fd.lote_id = %s
                    ORDER BY 
                        mp.nombre;
                """
                cur.execute(consulta, (item_id, lote_id))
                columnas = [desc[0] for desc in cur.description]
                filas = [dict(zip(columnas, fila)) for fila in cur.fetchall()]

            from datetime import date
            from models.planta_alimentos.ensayos import Ensayo
            for ens in Ensayo.vigentes_en(item_id, lote_id, date.today()):
                filas.append({
                    'insumo': ens['insumo'],
                    'cantidad': float(ens['cantidad_kg'] or 0),
                    'precio': float(ens['precio'] or 0),
                    'iva': float(ens['iva'] or 1),
                    'flete': float(ens['flete'] or 0),
                    'es_maquila': False,
                    'nombre_dieta': (filas[0]['nombre_dieta'] if filas else ''),
                    'es_ensayo': True,
                })
            return filas
        except Exception as e:
            print(f"Error al obtener detalle de costos: {e}")
            return []
        finally:
            conn.close()
            
    @staticmethod
    def eliminar_insumos_version(item_id, lote_id, version):
        """Elimina todos los insumos de una version de la receta. Devuelve cuantas filas borro."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM formula_detalle
                    WHERE item_id = %s AND lote_id = %s AND version = %s
                """, (item_id, lote_id, version))
                eliminados = cur.rowcount
            conn.commit()
            return eliminados
        except Exception as e:
            conn.rollback()
            print(f"Error al eliminar insumos de la version: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def eliminar_formula_lote(item_id, lote_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Borramos todos los registros que coincidan con el item y el lote
                consulta = """
                    DELETE FROM formula_detalle 
                    WHERE item_id = %s AND lote_id = %s;
                """
                cur.execute(consulta, (item_id, lote_id))
            
            # ¡Muy importante hacer commit cuando modificamos/borramos datos!
            conn.commit() 
            return True
            
        except Exception as e:
            print(f"Error al eliminar la fórmula del lote: {e}")
            conn.rollback()  # Revertir cambios si algo sale mal
            return False
            
        finally:
            conn.close()
    
    @staticmethod
    def obtener_receta(item_id, lote_id, version):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Incluimos fd.materia_prima_id explícitamente
                consulta = """
                    SELECT 
                        fd.id, 
                        fd.materia_prima_id,
                        mp.nombre AS insumo, 
                        fd.cantidad_kg, 
                        COALESCE(fd.es_nucleo, true) AS es_nucleo,
                        COALESCE(fd.baches_nucleo, 6.0) AS baches_nucleo
                    FROM formula_detalle fd
                    JOIN materias_primas mp ON fd.materia_prima_id = mp.id
                    WHERE fd.item_id = %s AND fd.lote_id = %s AND fd.version = %s
                    ORDER BY mp.nombre ASC;
                """
                cur.execute(consulta, (item_id, lote_id, version))
                columnas = [desc[0] for desc in cur.description]
                return [dict(zip(columnas, fila)) for fila in cur.fetchall()]
        except Exception as e:
            print(f"Error al obtener receta: {e}")
            return []
        finally:
            conn.close()
    @staticmethod
    def alternar_nucleo(id_registro, estado_nucleo):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE formula_detalle SET es_nucleo = %s WHERE id = %s;", (estado_nucleo, id_registro))
                conn.commit()
        finally:
            conn.close()

    @staticmethod
    def actualizar_baches_nucleo(id_registro, baches):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE formula_detalle SET baches_nucleo = %s WHERE id = %s;", (baches, id_registro))
                conn.commit()
        finally:
            conn.close()

    @staticmethod
    def obtener_resumen_totales(item_id, lote_id, version):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Se agregó: AND fd.version = %s
                consulta = """
                    SELECT 
                        COALESCE(SUM(fd.cantidad_kg), 0) AS total_kg,
                        COALESCE(SUM(fd.cantidad_kg * COALESCE(fd.precio_guardado, mp.precio_actual_kg)), 0) AS total_costo
                    FROM formula_detalle fd
                    JOIN materias_primas mp ON fd.materia_prima_id = mp.id
                    WHERE fd.item_id = %s AND fd.lote_id = %s AND fd.version = %s;
                """
                cur.execute(consulta, (item_id, lote_id, version))
                columnas = [desc[0] for desc in cur.description]
                resultado = cur.fetchone()
                return dict(zip(columnas, resultado)) if resultado else {'total_kg': 0, 'total_costo': 0}
        except Exception as e:
            print(f"Error al obtener resumen de totales: {e}")
            return {'total_kg': 0, 'total_costo': 0}
        finally:
            conn.close()

    @staticmethod
    def agregar_insumo(item_id, lote_id, materia_prima_id, cantidad_kg, version):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Agregamos la columna version al INSERT y al SELECT
                consulta = """
                    INSERT INTO formula_detalle 
                        (item_id, lote_id, materia_prima_id, cantidad_kg, precio_guardado, iva_guardado, flete_guardado, version) 
                    SELECT 
                        %s, %s, %s, %s, precio_actual_kg, iva, flete, %s
                    FROM 
                        materias_primas
                    WHERE 
                        id = %s;
                """
                # Pasamos 'version' en el orden correcto
                cur.execute(consulta, (item_id, lote_id, materia_prima_id, cantidad_kg, version, materia_prima_id))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error al agregar insumo con precios congelados: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    @staticmethod
    def actualizar_insumo(id_registro, nueva_cantidad_kg):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE formula_detalle SET cantidad_kg = %s WHERE id = %s",
                    (nueva_cantidad_kg, id_registro),
                )
                conn.commit()
        finally:
            conn.close()

    @staticmethod
    def eliminar_insumo(detalle_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM formula_detalle WHERE id = %s;", (detalle_id,))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error al eliminar insumo: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    @staticmethod
    def obtener_lotes_disponibles():
        """Obtiene todos los lotes de la tabla maestra para el selector."""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                # Consulta directa a la tabla maestra de lotes
                cur.execute("""
                    SELECT lote 
                    FROM cabecera_lotes 
                    WHERE lote IS NOT NULL 
                    ORDER BY lote ASC;
                """)
                lotes_db = cur.fetchall()
                
                # Agregamos 'LOTE GENERAL' como primera opción y luego todos los lotes de la BD
                lotes_lista = [{'lote': 'LOTE GENERAL'}] + [dict(l) for l in lotes_db]
                
                return lotes_lista
        finally:
            conn.close()
            
    @staticmethod
    def obtener_formulas_por_lote(lote_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                consulta = """
                    WITH ResumenVersiones AS (
                        SELECT 
                            fd.item_id,
                            fd.version,
                            COUNT(fd.materia_prima_id) AS num_insumos,
                            SUM(fd.cantidad_kg) AS peso_version,
                            SUM(fd.cantidad_kg * mp.precio_actual_kg) AS costo_version
                        FROM formula_detalle fd
                        JOIN materias_primas mp ON fd.materia_prima_id = mp.id
                        WHERE fd.lote_id = %s
                        GROUP BY fd.item_id, fd.version
                    ),
                    UltimaVersion AS (
                        SELECT item_id, MAX(version) AS max_version
                        FROM ResumenVersiones
                        GROUP BY item_id
                    )
                    SELECT 
                        rv.item_id,
                        uv.max_version AS ultima_version,
                        ca.nombre AS nombre_dieta,
                        
                        STRING_AGG(
                            '<span class="badge bg-primary me-1">V-' || rv.version || '</span>' ||
                            '<span class="badge bg-secondary me-2">' || rv.num_insumos || ' insumos</span>',
                            ' ' ORDER BY rv.version ASC
                        ) AS resumen_insumos_html,
                        
                        MAX(CASE WHEN rv.version = uv.max_version THEN rv.peso_version ELSE 0 END) AS total_peso,
                        MAX(CASE WHEN rv.version = uv.max_version THEN rv.costo_version ELSE 0 END) AS costo_bache

                    FROM ResumenVersiones rv
                    JOIN UltimaVersion uv ON rv.item_id = uv.item_id
                    JOIN catalogo_alimentos ca ON rv.item_id = ca.item_id
                    GROUP BY rv.item_id, uv.max_version, ca.nombre;
                """
                cur.execute(consulta, (lote_id,))
                columnas = [desc[0] for desc in cur.description]
                return [dict(zip(columnas, fila)) for fila in cur.fetchall()]
        except Exception as e:
            print(f"Error al obtener resumen de fórmulas por lote: {e}")
            return []
        finally:
            conn.close()
    @staticmethod
    def actualizar_dieta(item_id, nombre, rango_semanas):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Usamos item_id porque vimos antes que así se llama tu llave primaria en esta tabla
                consulta = """
                    UPDATE catalogo_alimentos 
                    SET nombre = %s, rango_semanas = %s 
                    WHERE item_id = %s;
                """
                cur.execute(consulta, (nombre, rango_semanas, item_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error al actualizar dieta: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    @staticmethod
    def eliminar_dieta(item_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                consulta = "DELETE FROM catalogo_alimentos WHERE item_id = %s;"
                cur.execute(consulta, (item_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error al eliminar dieta: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
            
class FormulaProduccion:

    @staticmethod
    def obtener_produccion_por_lote(item_id, lote_id, version):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Filtramos por versión - INCLUYE CAMPOS DE VENTA EXTERNA + CAL/CALCIO
                consulta = """
                    SELECT id, fecha, toneladas, novedad, es_venta, empresa_cliente, remision, cal_kg, calcio_kg
                    FROM formula_produccion_diaria 
                    WHERE item_id = %s AND lote_id = %s AND version = %s
                    ORDER BY fecha ASC;
                """
                cur.execute(consulta, (item_id, lote_id, version))
                columnas = [desc[0] for desc in cur.description]
                return [dict(zip(columnas, fila)) for fila in cur.fetchall()]
        except Exception as e:
            print(f"Error al obtener registros de producción: {e}")
            return []
        finally:
            conn.close()

    @staticmethod
    def registrar_produccion(item_id, lote_id, fecha, toneladas, novedad, version, es_venta=False, empresa_cliente=None, remision=None, cal_kg=0, calcio_kg=0):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # 1. Insertar registro de producción con nuevos campos
                cur.execute(
                    """INSERT INTO formula_produccion_diaria 
                       (item_id, lote_id, fecha, toneladas, novedad, version, es_venta, empresa_cliente, remision, cal_kg, calcio_kg) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (item_id, lote_id, fecha, toneladas, novedad, version, es_venta, empresa_cliente, remision, cal_kg, calcio_kg)
                )
                
                # 2. Descuento en Kárdex para la receta base (producción normal)
                receta_base = FormulaDetalle.obtener_receta(item_id, lote_id, version)
                
                for insumo in receta_base:
                    item = dict(insumo)
                    mp_id = item.get('materia_prima_id') or item.get('id_materia_prima')
                    cant_kg = float(item.get('cantidad_kg') or 0)
                    
                    if mp_id is not None and cant_kg > 0:
                        gramos_descontar = (toneladas * cant_kg) * 1000
                        obs = f"Venta {empresa_cliente} (Rem. {remision})" if es_venta else f"Producción Dieta {item_id} | Lote {lote_id}"
                        
                        cur.execute("""
                            INSERT INTO movimientos_inventario 
                            (materia_prima_id, tipo_movimiento, cantidad, fecha, observacion)
                            VALUES (%s, 'SALIDA_PRODUCCION', %s, %s, %s);
                        """, (mp_id, gramos_descontar, fecha, f"{obs} | {toneladas} Ton"))
                
                # 2b. Descuento de los insumos de ensayo vigentes en la fecha
                from models.planta_alimentos.ensayos import Ensayo
                for ens in Ensayo.vigentes_en(item_id, lote_id, fecha):
                    gramos_ensayo = (toneladas * float(ens['cantidad_kg'] or 0)) * 1000
                    if gramos_ensayo > 0:
                        cur.execute("""
                            INSERT INTO movimientos_inventario
                            (materia_prima_id, tipo_movimiento, cantidad, fecha, observacion)
                            VALUES (%s, 'SALIDA_PRODUCCION', %s, %s, %s);
                        """, (ens['materia_prima_id'], gramos_ensayo, fecha,
                              f"Producción Dieta {item_id} | Lote {lote_id} | ENSAYO {ens['insumo']} | {toneladas} Ton"))

                # 3. Descuento adicional para CAL (ID=7) y CALCIO (ID=4) si es venta y hay cantidades
                if es_venta:
                    if cal_kg and float(cal_kg) > 0:
                        gramos_cal = float(cal_kg) * 1000
                        cur.execute("""
                            INSERT INTO movimientos_inventario 
                            (materia_prima_id, tipo_movimiento, cantidad, fecha, observacion)
                            VALUES (%s, 'SALIDA_VENTA_CAL', %s, %s, %s);
                        """, (7, gramos_cal, fecha, f"Venta Cal {empresa_cliente} (Rem. {remision}) | {cal_kg} Kg"))
                    
                    if calcio_kg and float(calcio_kg) > 0:
                        gramos_calcio = float(calcio_kg) * 1000
                        cur.execute("""
                            INSERT INTO movimientos_inventario 
                            (materia_prima_id, tipo_movimiento, cantidad, fecha, observacion)
                            VALUES (%s, 'SALIDA_VENTA_CALCIO', %s, %s, %s);
                        """, (4, gramos_calcio, fecha, f"Venta Calcio {empresa_cliente} (Rem. {remision}) | {calcio_kg} Kg"))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"Error al registrar producción diaria: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    @staticmethod
    def eliminar_produccion(id_registro):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM formula_produccion_diaria WHERE id = %s;", (id_registro,))
                conn.commit()
        finally:
            conn.close()

    @staticmethod
    def eliminar_produccion(id_registro):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM formula_produccion_diaria WHERE id = %s;", (id_registro,))
                conn.commit()
        finally:
            conn.close()
    @staticmethod
    def actualizar_produccion(id_registro, toneladas, novedad='', cal_kg=0, calcio_kg=0, nueva_fecha=None):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Obtener valores actuales para calcular diferencias de inventario
                cur.execute("""
                    SELECT cal_kg, calcio_kg, fecha, empresa_cliente, remision, es_venta 
                    FROM formula_produccion_diaria 
                    WHERE id = %s
                """, (id_registro,))
                row = cur.fetchone()

                if not row:
                    print(f"[ERROR] No se encontró registro con id={id_registro}")
                    return False
                
                # Acceso seguro por índice con valores por defecto
                cal_kg_actual = float(row[0]) if row[0] is not None else 0.0
                calcio_kg_actual = float(row[1]) if row[1] is not None else 0.0
                fecha = row[2]
                empresa_cliente = row[3] if row[3] else ''
                remision = row[4] if row[4] else ''
                es_venta = bool(row[5]) if row[5] is not None else False
                
                cal_kg_nuevo = float(cal_kg or 0)
                calcio_kg_nuevo = float(calcio_kg or 0)
                
                # Actualizar registro. La fecha solo cambia si viene informada; de lo
                # contrario se conserva la actual (guardada en la variable 'fecha').
                consulta = """
                    UPDATE formula_produccion_diaria 
                    SET fecha = %s, toneladas = %s, novedad = %s, cal_kg = %s, calcio_kg = %s 
                    WHERE id = %s;
                """
                cur.execute(consulta, (nueva_fecha or fecha, toneladas, novedad, cal_kg_nuevo, calcio_kg_nuevo, id_registro))
                
                # Ajustar inventario si es venta y hay cambios en cal/calcio
                if es_venta:
                    # CAL (ID=7)
                    diff_cal = (cal_kg_nuevo - cal_kg_actual) * 1000
                    if diff_cal != 0:
                        tipo = 'SALIDA_VENTA_CAL' if diff_cal > 0 else 'ENTRADA_AJUSTE_CAL'
                        cur.execute("""
                            INSERT INTO movimientos_inventario 
                            (materia_prima_id, tipo_movimiento, cantidad, fecha, observacion)
                            VALUES (%s, %s, %s, %s, %s);
                        """, (7, tipo, abs(diff_cal), fecha, f"Ajuste Cal venta {empresa_cliente} (Rem. {remision}) | Diff {diff_cal/1000} Kg"))
                    
                    # CALCIO (ID=4)
                    diff_calcio = (calcio_kg_nuevo - calcio_kg_actual) * 1000
                    if diff_calcio != 0:
                        tipo = 'SALIDA_VENTA_CALCIO' if diff_calcio > 0 else 'ENTRADA_AJUSTE_CALCIO'
                        cur.execute("""
                            INSERT INTO movimientos_inventario 
                            (materia_prima_id, tipo_movimiento, cantidad, fecha, observacion)
                            VALUES (%s, %s, %s, %s, %s);
                        """, (4, tipo, abs(diff_calcio), fecha, f"Ajuste Calcio venta {empresa_cliente} (Rem. {remision}) | Diff {diff_calcio/1000} Kg"))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"Error al actualizar BD: {e}")
            import traceback
            traceback.print_exc()
            conn.rollback()
            return False
        finally:
            conn.close()

    @staticmethod
    def eliminar_produccion(id_registro):
        """Elimina un registro de producción por su ID."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM formula_produccion_diaria WHERE id = %s;", (id_registro,))
                conn.commit()
        finally:
            conn.close()
    
    

    
    