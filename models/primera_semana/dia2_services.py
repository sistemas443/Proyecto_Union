# models/primera_semana/dia2_services.py
"""Lógica del Día 2 visual de Primera Semana.

La tabla primera_semana_dia2 es independiente de primera_semana: guarda una
segunda tabla con la misma estructura, pero no participa en los cálculos
oficiales, reportes ni consolidados.
"""
import traceback
import unicodedata
from datetime import datetime, timedelta

from models.base import get_db_connection, parse_empty
from models.primera_semana import dia2

ROLES_DIA2 = {'superadmin', 'director de planta', 'produccion'}

# En el Día 2 solo se digitan los datos de peso y uniformidad.
# Las demás columnas se copian/calculan desde la tabla oficial.
COLUMNAS_EDITABLES_DIA2 = {
    'peso_real',
    'unif_10_menos',
    'porc_uniformidad',
    'unif_10_mas',
    'coef_variacion',
}


def normalizar_rol(rol):
    """Normaliza mayúsculas y tildes para comparar roles."""
    texto = unicodedata.normalize('NFKD', str(rol or ''))
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    return ' '.join(texto.lower().split())


def roles_pueden_dia2(rol):
    """Indica si el rol puede generar/eliminar la tabla del Día 2."""
    return normalizar_rol(rol) in ROLES_DIA2


def puede_editar_dia2(rol):
    """El Día 2 se edita con la misma regla que la tabla oficial: todo menos Lector."""
    return normalizar_rol(rol) != 'lector'


def _formatear_filas(filas):
    """Aplica los mismos formatos de presentación que la tabla oficial."""
    for f in filas:
        if f['mortalidad'] is not None:
            f['mortalidad'] = str(int(float(f['mortalidad'])))
        if f['sel'] is not None:
            f['sel'] = str(int(float(f['sel'])))
        if f['consumo_kg'] is not None:
            f['consumo_kg'] = str(int(round(float(f['consumo_kg']))))
        if f['cons_k_acum'] is not None:
            f['cons_k_acum'] = str(int(round(float(f['cons_k_acum']))))
        if f['peso_tabla'] is not None:
            f['peso_tabla'] = str(int(round(float(f['peso_tabla']))))
        if f['peso_real'] is not None:
            f['peso_real'] = f"{float(f['peso_real']):.2f}"
        if f['unif_10_menos'] is not None:
            f['unif_10_menos'] = f"{float(f['unif_10_menos']):.1f}"
        if f['porc_uniformidad'] is not None:
            f['porc_uniformidad'] = f"{float(f['porc_uniformidad']):.2f}"
        if f['unif_10_mas'] is not None:
            f['unif_10_mas'] = f"{float(f['unif_10_mas']):.1f}"
        if f['coef_variacion'] is not None:
            f['coef_variacion'] = f"{float(f['coef_variacion']):.2f}"
        if f['cons_gr_ave_ac'] is not None:
            f['cons_gr_ave_ac'] = f"{float(f['cons_gr_ave_ac']):.2f}"
        if f['consumo_gr_a_d'] is not None:
            f['consumo_gr_a_d'] = f"{float(f['consumo_gr_a_d']):.2f}"
        if f['consumo_gr_a_tab'] is not None:
            f['consumo_gr_a_tab'] = f"{float(f['consumo_gr_a_tab']):.1f}"
        # Estos valores también se devuelven por JSON al editar.
        if f['porc_mort_sem'] is not None:
            f['porc_mort_sem'] = float(f['porc_mort_sem'])
        if f['porc_mort_acum'] is not None:
            f['porc_mort_acum'] = float(f['porc_mort_acum'])
        if f['cons_gr_ave_tab_acum'] is not None:
            f['cons_gr_ave_tab_acum'] = float(f['cons_gr_ave_tab_acum'])
        # La fecha se devuelve en ISO para el input type="date" y el JS.
        if f.get('fecha_dia') is not None and hasattr(f['fecha_dia'], 'isoformat'):
            f['fecha_dia'] = f['fecha_dia'].isoformat()
    return filas


def tiene_dia2(lote_nombre):
    """Indica si el lote ya tiene generada la tabla del Día 2."""
    if not lote_nombre:
        return False
    return dia2.count_dia2(lote_nombre) > 0


def get_dia2_by_lote(lote_nombre):
    """Devuelve las filas del Día 2 listas para la plantilla."""
    if not lote_nombre:
        return []
    filas = dia2.fetch_dia2_by_lote(lote_nombre)
    return _formatear_filas(filas)


def generar_estructura_dia2(lote_nombre, usuario_id=None, usuario_nombre=None):
    """Crea las 8 filas del Día 2 copiando la estructura teórica de la tabla oficial."""
    if not lote_nombre:
        return False, "Debes seleccionar un lote válido."

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, fecha_recepcion, no_pollitas_recibidas FROM cabecera_lotes WHERE lote = %s",
            (lote_nombre,),
        )
        cab = cur.fetchone()
        if not cab:
            return False, f"El lote '{lote_nombre}' no existe."

        id_lote, _fecha_recepcion, pollitas = cab
        aves_iniciales = float(pollitas) if pollitas else 10000.0
        if aves_iniciales <= 0:
            aves_iniciales = 1.0

        cur.execute("SELECT COUNT(*) FROM primera_semana_dia2 WHERE lote = %s", (lote_nombre,))
        if cur.fetchone()[0] > 0:
            return True, "La tabla del Día 2 ya existe para este lote."

        cur.execute(
            """
            SELECT fecha, semana, mortalidad, sel, consumo_gr_a_tab, consumo_kg,
                   peso_tabla, peso_real, unif_10_menos, porc_uniformidad,
                   unif_10_mas, coef_variacion, observaciones
            FROM primera_semana
            WHERE lote = %s
            ORDER BY id ASC
            """,
            (lote_nombre,),
        )
        oficiales = cur.fetchall()
        if not oficiales:
            return False, "Primero debe existir la tabla oficial de Primera Semana."

        valores = []
        for (_fecha, semana, mortalidad, sel, consumo_tab, consumo_kg,
             peso_tabla, peso_real, unif_10_menos, porc_uniformidad,
             unif_10_mas, coef_variacion, observaciones) in oficiales:
            valores.append((
                lote_nombre, id_lote, None, semana,
                mortalidad, sel, 0, 0, int(aves_iniciales),
                peso_tabla, peso_real, unif_10_menos, porc_uniformidad, unif_10_mas,
                coef_variacion, observaciones or '',
                consumo_tab, consumo_kg, 0, 0, 0, 0,
            ))

        dia2.insertar_estructura_dia2(valores, cur)
        recalcular_dia2_cascada_interna(lote_nombre, aves_iniciales, cur)
        conn.commit()
        return True, "Tabla del Día 2 generada correctamente."
    except Exception as e:
        conn.rollback()
        print(f"[ERROR GENERAR DÍA 2]: {e}")
        traceback.print_exc()
        return False, str(e)
    finally:
        cur.close()
        conn.close()


def recalcular_dia2_cascada_interna(lote_nombre, aves_iniciales, cur,
                                    id_reg=None, columna_editada=None, valor_manual=None):
    """Recalcula saldo, consumos y porcentajes del Día 2 en cascada."""
    filas = dia2.fetch_dia2_para_calculo(lote_nombre, cur)

    saldo_actual = float(aves_iniciales)
    acum_mort = 0.0
    acum_kilos = 0.0
    acum_gr_tab = 0.0
    acum_gr_real_ave = 0.0

    valores_update = []
    campos_reg_actualizado = {}

    for f in filas:
        if isinstance(f, dict):
            f_id = f['id']
            m_dia = float(f['mortalidad'] or 0)
            s_dia = float(f['sel'] or 0)
            c_kg = float(f['consumo_kg'] or 0)
            c_tab = float(f['consumo_gr_a_tab'] or 0)
        else:
            f_id = f[0]
            m_dia = float(f[1] or 0)
            s_dia = float(f[2] or 0)
            c_kg = float(f[3] or 0)
            c_tab = float(f[4] or 0)

        acum_mort += m_dia
        acum_kilos += c_kg
        acum_gr_tab += c_tab

        saldo_actual -= (m_dia + s_dia)
        if saldo_actual < 0:
            saldo_actual = 0
        saldo_entero = int(saldo_actual)

        porc_mort_sem = round((m_dia / aves_iniciales) * 100, 2)
        porc_mort_acum = round((acum_mort / aves_iniciales) * 100, 2)

        if (id_reg and int(f_id) == int(id_reg)
                and columna_editada == 'consumo_gr_a_d'
                and valor_manual is not None):
            real_diaria = round(float(valor_manual), 2)
        else:
            real_diaria = round((c_kg * 1000.0) / float(saldo_entero), 2) if saldo_entero > 0 else 0.0

        acum_gr_real_ave += real_diaria
        c_gr_ac = round(acum_gr_real_ave, 2)
        c_k_acum = round(acum_kilos, 2)
        c_gr_tab_acum = int(round(acum_gr_tab))

        valores_update.append((
            porc_mort_sem, porc_mort_acum, saldo_entero,
            real_diaria, c_k_acum, c_gr_tab_acum, c_gr_ac, f_id
        ))

        if id_reg and int(f_id) == int(id_reg):
            campos_reg_actualizado = {
                'porc_mort_sem': porc_mort_sem,
                'porc_mort_acum': porc_mort_acum,
                'saldo_aves': saldo_entero,
                'consumo_gr_a_d': real_diaria,
                'cons_k_acum': c_k_acum,
                'cons_gr_ave_tab_acum': c_gr_tab_acum,
                'cons_gr_ave_ac': c_gr_ac,
            }

    if valores_update:
        cur.executemany(
            """
            UPDATE primera_semana_dia2
            SET porc_mort_sem = %s, porc_mort_acum = %s, saldo_aves = %s,
                consumo_gr_a_d = %s, cons_k_acum = %s,
                cons_gr_ave_tab_acum = %s, cons_gr_ave_ac = %s
            WHERE id = %s
            """,
            valores_update,
        )

    return valores_update, campos_reg_actualizado


def update_dia2_field(id_reg: int, columna: str, valor: str,
                      usuario_id=None, usuario_nombre=None) -> tuple[bool, dict, str]:
    """Guarda una edición en línea del Día 2 y dispara el recálculo."""
    from models.auditoria.services import registrar_cambio

    if columna not in COLUMNAS_EDITABLES_DIA2:
        return False, {}, f"La columna '{columna}' no es editable en el Día 2."

    val_final = parse_empty(valor)
    if val_final is not None and columna != 'observaciones':
        val_final = float(val_final)
        if columna in ['peso_real', 'porc_uniformidad', 'coef_variacion']:
            val_final = round(val_final, 2)
        elif columna in ['unif_10_menos', 'unif_10_mas']:
            val_final = round(val_final, 1)
        elif columna in ['peso_tabla', 'consumo_kg']:
            val_final = int(round(val_final))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            'SELECT "{}" FROM primera_semana_dia2 WHERE id = %s'.format(columna),
            (id_reg,),
        )
        fila_anterior = cur.fetchone()
        if not fila_anterior:
            return False, {}, "La fila del Día 2 no existe."
        valor_anterior = fila_anterior[0]

        dia2.actualizar_campo_dia2(id_reg, columna, val_final, cur)

        registrar_cambio(
            usuario_id=usuario_id,
            usuario_nombre=usuario_nombre or 'Desconocido',
            tabla='primera_semana_dia2',
            id_registro=id_reg,
            campo=columna,
            valor_anterior=valor_anterior,
            valor_nuevo=val_final,
            accion='UPDATE',
            cursor=cur,
        )

        cur.execute("SELECT lote FROM primera_semana_dia2 WHERE id = %s", (id_reg,))
        lote_nombre = cur.fetchone()[0]

        cur.execute(
            "SELECT no_pollitas_recibidas FROM cabecera_lotes WHERE lote = %s",
            (lote_nombre,),
        )
        cab_info = cur.fetchone()
        aves_iniciales = float(cab_info[0]) if cab_info and cab_info[0] else 10000.0
        if aves_iniciales <= 0:
            aves_iniciales = 1.0

        _valores, campos_actualizados = recalcular_dia2_cascada_interna(
            lote_nombre, aves_iniciales, cur, id_reg,
            columna_editada=columna, valor_manual=val_final,
        )
        campos_actualizados['_lote'] = lote_nombre

        conn.commit()
        return True, campos_actualizados, "Ok"
    except Exception as e:
        conn.rollback()
        return False, {}, str(e)
    finally:
        cur.close()
        conn.close()


def actualizar_fecha_inicio_dia2(lote_nombre, fecha_inicio,
                                 usuario_id=None, usuario_nombre=None):
    """Cambia la fecha del Día 0 y desplaza las 8 fechas del Día 2."""
    if not lote_nombre:
        return False, "Lote inválido."
    try:
        fecha_base = datetime.strptime(str(fecha_inicio)[:10], '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return False, "Fecha inválida."

    from models.auditoria.services import registrar_cambio

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, fecha FROM primera_semana_dia2 WHERE lote = %s ORDER BY id ASC",
            (lote_nombre,),
        )
        filas = cur.fetchall()
        if not filas:
            return False, "La tabla del Día 2 no existe para este lote."

        for indice, (id_reg, _fecha_anterior) in enumerate(filas):
            cur.execute(
                "UPDATE primera_semana_dia2 SET fecha = %s WHERE id = %s",
                (fecha_base + timedelta(days=indice), id_reg),
            )

        registrar_cambio(
            usuario_id=usuario_id,
            usuario_nombre=usuario_nombre or 'Desconocido',
            tabla='primera_semana_dia2',
            id_registro=filas[0][0],
            campo='fecha',
            valor_anterior=filas[0][1],
            valor_nuevo=fecha_base,
            accion='UPDATE',
            cursor=cur,
        )

        conn.commit()
        return True, "Fecha actualizada correctamente."
    except Exception as e:
        conn.rollback()
        print(f"[ERROR FECHA DÍA 2]: {e}")
        return False, str(e)
    finally:
        cur.close()
        conn.close()


def eliminar_dia2(lote_nombre):
    """Elimina la tabla del Día 2 de un lote."""
    if not lote_nombre:
        return False, "Lote inválido."
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        filas = dia2.eliminar_dia2_por_lote(lote_nombre, cur)
        cur.execute(
            "UPDATE cabecera_lotes SET tabla_primera_activa = 'dia1' "
            "WHERE lote = %s AND tabla_primera_activa = 'dia2'",
            (lote_nombre,),
        )
        conn.commit()
        return True, f"Se eliminaron {filas} filas del Día 2."
    except Exception as e:
        conn.rollback()
        print(f"[ERROR ELIMINAR DÍA 2]: {e}")
        return False, str(e)
    finally:
        cur.close()
        conn.close()


def recalcular_dia2_si_existe(lote_nombre, aves_iniciales, cur):
    """Recalcula el Día 2 solo si el lote ya lo tiene generado.

    Se usa cuando cambia la cabecera del lote para mantener el saldo coherente.
    No hace commit; lo controla el llamador.
    """
    cur.execute("SELECT 1 FROM primera_semana_dia2 WHERE lote = %s LIMIT 1", (lote_nombre,))
    if cur.fetchone():
        recalcular_dia2_cascada_interna(lote_nombre, aves_iniciales, cur)
