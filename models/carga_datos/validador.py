# models/carga_datos/validador.py
"""Validación del lote real dentro de un archivo Excel antes de cargarlo."""
import re
import unicodedata

import pandas as pd

# Celdas conocidas de las plantillas (fila y columna en base 1, como Excel).
CELDAS_LOTE = [
    ('Sem-Levante', 8, 8),       # H8
    ('Sem-Prod', 5, 16),         # P5
    ('Clasificación', 5, 16),    # P5
    ('DIARIO', 2, 11),           # K2 (solo lote base)
]

# Hojas que no deben intervenir en la validación.
HOJAS_IGNORADAS = {
    'tabvariablesfinales',
    'etiquetadatos',
}


def _normalizar_texto(valor):
    texto = unicodedata.normalize('NFKD', str(valor or ''))
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    return ' '.join(texto.lower().strip().split())


def _normalizar_nombre_hoja(nombre):
    texto = _normalizar_texto(nombre)
    return re.sub(r'[^a-z0-9]', '', texto)


def _extraer_lote(valor):
    """Devuelve el lote encontrado en un valor, o None."""
    if valor is None:
        return None
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        if pd.isna(valor):
            return None
        numero = int(valor)
        return str(numero) if numero > 0 else None

    texto = str(valor).strip()
    if not texto or texto.lower() in {'nan', 'none', 'lote', 'lote:'}:
        return None

    # Busca algo como 72-2, 69-10, 70-14 o el lote base 72.
    coincidencia = re.search(r'(\d{1,4}(?:-\d{1,4})?)', texto.upper())
    return coincidencia.group(1) if coincidencia else None


def _agregar(candidatos_full, candidatos_base, valor):
    lote = _extraer_lote(valor)
    if not lote:
        return
    if '-' in lote:
        candidatos_full.add(lote)
    else:
        candidatos_base.add(lote)


def _extraer_lote_nombre(nombre):
    """Extrae el lote completo desde el nombre del archivo, ej. Lote 69-10.xlsm."""
    base = str(nombre or '').rsplit('.', 1)[0]
    coincidencia = re.search(r'(\d{1,3}-\d{1,3})', base)
    if coincidencia:
        return coincidencia.group(1)
    coincidencia = re.search(r'(\d{1,3})', base)
    return coincidencia.group(1) if coincidencia else None


def _valor_celda(hoja, fila, columna):
    if hoja.shape[0] < fila or hoja.shape[1] < columna:
        return None
    valor = hoja.iat[fila - 1, columna - 1]
    return None if pd.isna(valor) else valor


def _recolectar_lotes(hojas):
    """Recorre las hojas y devuelve (lotes_full, lotes_base)."""
    full = set()
    base = set()

    for nombre_hoja, hoja in hojas.items():
        nombre_norm = _normalizar_nombre_hoja(nombre_hoja)
        if nombre_norm in HOJAS_IGNORADAS or nombre_norm.startswith('grafico'):
            continue
        if hoja is None or hoja.empty:
            continue

        # Celdas conocidas de las plantillas.
        for nombre_celda, fila, columna in CELDAS_LOTE:
            if _normalizar_nombre_hoja(nombre_celda) == nombre_norm:
                _agregar(full, base, _valor_celda(hoja, fila, columna))

        # Hojas de primera semana: C4 contiene "Lote 72-2".
        if '1rasemana' in nombre_norm or nombre_norm.startswith('primera'):
            _agregar(full, base, _valor_celda(hoja, 4, 3))

        # Búsqueda flexible: celdas que dicen "Lote" y su valor al lado.
        max_filas = min(hoja.shape[0], 40)
        max_columnas = min(hoja.shape[1], 60)
        for fila in range(max_filas):
            for columna in range(max_columnas):
                valor = hoja.iat[fila, columna]
                if not isinstance(valor, str) or 'lote' not in valor.lower():
                    continue
                _agregar(full, base, valor)
                if columna + 1 < hoja.shape[1]:
                    _agregar(full, base, hoja.iat[fila, columna + 1])

    return full, base


def validar_lote_archivo(archivo, lote_seleccionado, modulo=None):
    """Verifica que el lote del Excel coincida con el lote seleccionado.

    Retorna (ok, mensaje, lote_detectado).
    """
    seleccionado = _extraer_lote(lote_seleccionado)
    if not seleccionado:
        return False, "No se pudo interpretar el lote seleccionado.", None

    try:
        hojas = pd.read_excel(archivo, sheet_name=None, header=None, nrows=40)
    except Exception as e:
        return False, f"No se pudo leer el archivo Excel para verificar el lote: {e}", None

    lotes_full, lotes_base = _recolectar_lotes(hojas)

    if len(lotes_full) == 1:
        detectado = next(iter(lotes_full))
        if detectado == seleccionado:
            return True, "Lote verificado correctamente.", detectado
        return False, (
            f"El archivo corresponde al lote {detectado}, pero seleccionaste "
            f"el lote {seleccionado}. Verifica el archivo o cambia el lote."
        ), detectado

    if len(lotes_full) > 1:
        detectados = ', '.join(sorted(lotes_full))
        return False, (
            f"El archivo contiene varios lotes ({detectados}). "
            "Sube un archivo que corresponda a un solo lote."
        ), detectados

    # Si el contenido solo trae el lote base, el nombre del archivo puede
    # aportar la variante completa (por ejemplo, Lote 69-10.xlsm).
    lote_nombre = _extraer_lote_nombre(getattr(archivo, 'filename', ''))
    base_seleccionada = seleccionado.split('-')[0]
    if lote_nombre and '-' in lote_nombre:
        if lotes_base and base_seleccionada not in lotes_base:
            bases_detectadas = ', '.join(sorted(lotes_base))
            return False, (
                f"El contenido del archivo indica el lote base {bases_detectadas}, "
                f"pero seleccionaste el lote {seleccionado}."
            ), bases_detectadas
        if lote_nombre == seleccionado:
            return True, "Lote verificado correctamente.", lote_nombre
        return False, (
            f"El nombre del archivo indica el lote {lote_nombre}, pero "
            f"seleccionaste el lote {seleccionado}. Verifica el archivo o cambia el lote."
        ), lote_nombre

    if len(lotes_base) == 1 and '-' not in seleccionado:
        detectado = next(iter(lotes_base))
        if detectado == seleccionado:
            return True, "Lote verificado correctamente.", detectado
        return False, (
            f"El archivo corresponde al lote {detectado}, pero seleccionaste "
            f"el lote {seleccionado}."
        ), detectado

    if lotes_base:
        detectados = ', '.join(sorted(lotes_base))
        return False, (
            "No se pudo verificar el lote completo dentro del archivo. "
            f"Se encontró solo el lote base {detectados}. "
            "El archivo debe incluir el lote completo, por ejemplo 69-10."
        ), detectados

    return False, (
        "No se pudo detectar el lote dentro del archivo. "
        "Verifica que sea el archivo correcto y que contenga el nombre del lote."
    ), None
