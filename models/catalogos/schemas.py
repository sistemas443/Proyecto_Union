"""Esquemas, constantes y validaciones para los catálogos con foto."""

# Mapa autorizado: clave en la URL -> tabla física.
# NUNCA se concatena un nombre de tabla que no esté aquí (anti SQL injection).
CATALOGOS_VALIDOS = {
    'nutricionista_lev':   'catalogo_nutricionistas_levante',
    'nutricionista_prod':  'catalogo_nutricionistas_produccion',
    'variedad':            'catalogo_variedades',
    'marca_galpon':        'catalogo_marcas_galpon',
}

# Etiquetas legibles para títulos del modal
CATALOGOS_ETIQUETAS = {
    'nutricionista_lev':   'Nutricionista (Levante)',
    'nutricionista_prod':  'Nutricionista (Producción)',
    'variedad':            'Variedad',
    'marca_galpon':        'Marca Galpón',
}

FOTO_PLACEHOLDER = 'img/placeholder-catalogo.png'   # relativo a static/
EXTENSIONES_PERMITIDAS = {'png', 'jpg', 'jpeg', 'webp'}
TAMANO_MAXIMO_BYTES = 5 * 1024 * 1024               # 5 MB
LARGO_MAXIMO_NOMBRE = 150


def obtener_tabla(tipo: str):
    """Devuelve el nombre físico de la tabla si el tipo es válido, o None."""
    return CATALOGOS_VALIDOS.get(tipo)


def validar_nombre(nombre) -> tuple:
    """Limpia y valida el nombre. Devuelve (nombre_ok | None, mensaje_error)."""
    if not nombre or not str(nombre).strip():
        return None, 'El nombre no puede estar vacío.'
    nombre_ok = ' '.join(str(nombre).strip().upper().split())
    if len(nombre_ok) > LARGO_MAXIMO_NOMBRE:
        return None, f'El nombre no puede superar {LARGO_MAXIMO_NOMBRE} caracteres.'
    return nombre_ok, None
