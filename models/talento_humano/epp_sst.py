# models/talento_humano/epp_sst.py
"""
Consulta de solo lectura a la base master_sst (Seguridad y Salud en el Trabajo).

Devuelve el historial de entregas de Elementos de Protección Personal (EPP)
de un colaborador, cruzando por su número de documento.

Fuente: cabecera `entrega_h_epp` + detalle `entrega_d_epp`.
Llave de cruce: data_vargas.colaboradores.num_doc  <->  master_sst.colaborador.nro_de_identificacion
"""
import psycopg2
import psycopg2.extras
from models.base import get_master_sst_connection


class EppSST:
    """Acceso de solo lectura a las entregas EPP en master_sst."""

    # Mapa de palabras clave -> icono Font Awesome (coincide con iconoEPP() en colaboradores.js)
    _ICONOS = [
        ('casco', 'fa-solid fa-helmet-safety'),
        ('tapaboca', 'fa-solid fa-head-side-mask'),
        ('cofia', 'fa-solid fa-head-side-mask'),
        ('mascarilla', 'fa-solid fa-head-side-mask'),
        ('mascara', 'fa-solid fa-head-side-mask'),
        ('respirador', 'fa-solid fa-head-side-mask'),
        ('careta', 'fa-solid fa-head-side-mask'),
        ('guante', 'fa-solid fa-hand'),
        ('gafa', 'fa-solid fa-glasses'),
        ('lente', 'fa-solid fa-glasses'),
        ('visual', 'fa-solid fa-glasses'),
        ('audit', 'fa-solid fa-headphones'),
        ('oido', 'fa-solid fa-headphones'),
        ('orejera', 'fa-solid fa-headphones'),
        ('ruido', 'fa-solid fa-headphones'),
        ('bot', 'fa-solid fa-shoe-prints'),
        ('zapato', 'fa-solid fa-shoe-prints'),
        ('calzado', 'fa-solid fa-shoe-prints'),
        ('dielectric', 'fa-solid fa-shoe-prints'),
        ('chaleco', 'fa-solid fa-vest'),
        ('reflect', 'fa-solid fa-vest'),
        ('overol', 'fa-solid fa-shirt'),
        ('pantal', 'fa-solid fa-shirt'),
        ('camis', 'fa-solid fa-shirt'),
        ('uniforme', 'fa-solid fa-shirt'),
        ('ropa', 'fa-solid fa-shirt'),
        ('delantal', 'fa-solid fa-shirt'),
        ('arnes', 'fa-solid fa-shield-halved'),
        ('eslinga', 'fa-solid fa-shield-halved'),
        ('anclaje', 'fa-solid fa-shield-halved'),
        ('filtro', 'fa-solid fa-wind'),
    ]

    @staticmethod
    def icono_elemento(nombre):
        n = (nombre or '').lower()
        for kw, icono in EppSST._ICONOS:
            if kw in n:
                return icono
        return 'fa-solid fa-box-open'

    @staticmethod
    def agrupar_por_elemento(entregas):
        """Agrupa las entregas por elemento EPP, con icono y totales."""
        grupos = {}
        for e in entregas:
            nombre = e.get('nombre_elemento_epp') or e.get('elemento_epp') or 'Otros'
            g = grupos.setdefault(nombre, {
                'elemento': nombre,
                'icono': EppSST.icono_elemento(nombre),
                'entregas': [],
                'total_cantidad': 0.0,
            })
            g['entregas'].append(e)
            try:
                g['total_cantidad'] += float(e.get('cantidad') or 0)
            except (TypeError, ValueError):
                pass
        return [grupos[k] for k in sorted(grupos.keys(), key=str.lower)]

    @staticmethod
    def get_entregas_por_documento(num_doc):
        """Retorna lista de dicts con las entregas EPP del documento dado."""
        if not num_doc:
            return []

        conn = get_master_sst_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT h.entrega_epp_h_id,
                           h.fecha,
                           h.hora,
                           h.nombre_colaborador,
                           h.area,
                           d.elemento_epp,
                           d.nombre_elemento_epp,
                           d.detalle_epp,
                           d.cantidad,
                           d.observacion
                    FROM colaborador c
                    JOIN entrega_h_epp h ON h.colaborador_id = c.id_colaborador
                    LEFT JOIN entrega_d_epp d ON d.entrega_epp_h_id = h.entrega_epp_h_id
                    WHERE c.nro_de_identificacion = %s
                    ORDER BY h.fecha DESC, h.hora DESC, h.entrega_epp_h_id
                """, (num_doc,))
                rows = cur.fetchall()

            entregas = []
            for r in rows:
                d = dict(r)
                if d.get('fecha') is not None:
                    d['fecha'] = d['fecha'].isoformat()
                if d.get('hora') is not None:
                    d['hora'] = d['hora'].strftime('%H:%M:%S')
                if d.get('cantidad') is not None:
                    d['cantidad'] = float(d['cantidad'])
                entregas.append(d)
            return entregas
        finally:
            conn.close()
