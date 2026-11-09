"""
Importacion de insumos a una receta desde texto pegado (Excel) o desde una imagen.

- Texto: se pega el rango de Excel (nombre + cantidad) y se parsea.
- Imagen: se aplica OCR local (RapidOCR si esta instalado; si no, pytesseract).
- En ambos casos se intenta asociar cada nombre con una materia prima existente.
"""

import io
import re
import unicodedata
from difflib import SequenceMatcher

from models.base import get_db_connection
from models.planta_alimentos.maestros import MateriaPrima

# Palabras que suelen ser encabezados, totales o notas: se descartan
PALABRAS_IGNORAR = (
    'TOTAL', 'SUBTOTAL', 'MATERIA PRIMA', 'MATERIAS PRIMAS', 'INSUMO', 'INSUMOS',
    'CANTIDAD', 'KG', 'KILOS', 'KG/BACHE', 'PRECIO', 'COSTO', 'BACHE', 'BACHES',
    'NUCLEO', 'NUCLEO PREMEZCLA', 'OBSERVACION', 'OBSERVACIONES',
)


def normalizar(texto):
    """Mayusculas, sin acentos y sin signos, para comparar nombres."""
    t = unicodedata.normalize('NFKD', str(texto or ''))
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = t.upper()
    t = re.sub(r'[^A-Z0-9 ]+', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def parsear_numero(texto):
    """Convierte '566.011', '566,011', '1.234,5' o '1,234.5' a float."""
    s = str(texto or '').strip()
    if not s:
        return None
    s = re.sub(r'[^0-9\.,\-]', '', s)
    if not s:
        return None

    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        partes = s.split(',')
        if len(partes) == 2 and len(partes[1]) == 3:
            s = ''.join(partes)
        else:
            s = s.replace(',', '.')
    elif '.' in s:
        partes = s.split('.')
        if len(partes) > 2 or (len(partes) == 2 and len(partes[1]) == 3):
            s = ''.join(partes)

    try:
        return float(s)
    except ValueError:
        return None


def parsear_texto(texto):
    """Convierte texto (una linea por insumo) en filas {texto, cantidad, es_nucleo}."""
    filas = []
    en_nucleo = False

    for linea in str(texto or '').splitlines():
        limpio = linea.strip()
        if not limpio:
            continue

        norm = normalizar(limpio)
        if not norm:
            continue

        if norm in ('NUCLEO', 'NUCLEO PREMEZCLA', 'NUCLEO / PREMEZCLA', 'PREMEZCLA'):
            en_nucleo = True
            continue

        numeros = list(re.finditer(r'-?\d[\d\.,]*', limpio))
        if not numeros:
            continue

        # La cantidad suele ser el primer numero de la fila (despues del nombre)
        primero = numeros[0]
        cantidad = parsear_numero(primero.group(0))
        if cantidad is None or cantidad <= 0:
            continue

        nombre = limpio[:primero.start()].strip(' \t;|,.-')
        nombre = re.sub(r'\s{2,}', ' ', nombre).strip()
        if not nombre:
            continue

        mayus = nombre.upper()
        if any(mayus == p or mayus.startswith(p) for p in PALABRAS_IGNORAR):
            continue

        fila = {'texto': nombre, 'cantidad': cantidad, 'es_nucleo': en_nucleo}
        if len(numeros) > 1:
            fila['aviso'] = 'Se detectaron varios números; se usó el primero.'
        filas.append(fila)

    return filas


def buscar_materia(nombre, catalogo):
    """Busca la materia prima mas parecida. Devuelve (materia | None, puntaje)."""
    objetivo = normalizar(nombre)
    if not objetivo:
        return None, 0.0

    for materia in catalogo:
        if normalizar(materia['nombre']) == objetivo:
            return materia, 1.0

    mejor = None
    puntaje = 0.0
    for materia in catalogo:
        ratio = SequenceMatcher(None, objetivo, normalizar(materia['nombre'])).ratio()
        if ratio > puntaje:
            mejor, puntaje = materia, ratio

    if puntaje >= 0.72:
        return mejor, puntaje
    return None, puntaje


def _agrupar_lineas_ocr(resultado):
    """Agrupa los bloques de OCR por filas usando la coordenada Y."""
    items = []
    for caja, texto, _score in resultado:
        ys = [p[1] for p in caja]
        xs = [p[0] for p in caja]
        items.append({
            'y': sum(ys) / len(ys),
            'alto': max(ys) - min(ys),
            'x': min(xs),
            'texto': str(texto).strip(),
        })

    items.sort(key=lambda i: (i['y'], i['x']))

    lineas = []
    for item in items:
        if lineas:
            ultima = lineas[-1]
            umbral = max(8, min(item['alto'], ultima['alto']) * 0.6)
            if abs(item['y'] - ultima['y']) <= umbral:
                ultima['partes'].append(item)
                ultima['y'] = (ultima['y'] + item['y']) / 2
                continue
        lineas.append({'y': item['y'], 'alto': item['alto'], 'partes': [item]})

    texto = []
    for linea in lineas:
        partes = sorted(linea['partes'], key=lambda p: p['x'])
        texto.append(' '.join(p['texto'] for p in partes))
    return '\n'.join(texto)


def extraer_texto_imagen(datos):
    """
    Devuelve (texto, aviso). Intenta RapidOCR y luego pytesseract.
    Si no hay motor disponible, texto='' y un aviso explicando que instalar.
    """
    try:
        from PIL import Image
    except ImportError:
        return '', 'Falta Pillow para leer imagenes.'

    try:
        imagen = Image.open(io.BytesIO(datos)).convert('RGB')
    except Exception:
        return '', 'No se pudo abrir la imagen.'

    # 1) RapidOCR (ONNX, solo pip)
    try:
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR

        motor = RapidOCR()
        resultado, _ = motor(np.array(imagen))
        if not resultado:
            return '', 'No se detectó texto en la imagen.'
        return _agrupar_lineas_ocr(resultado), None
    except ImportError:
        pass
    except Exception as e:
        return '', f'El OCR no pudo procesar la imagen ({type(e).__name__}).'

    # 2) pytesseract (requiere el binario de Tesseract)
    try:
        import pytesseract

        return pytesseract.image_to_string(imagen, lang='spa'), None
    except ImportError:
        return '', ('OCR no disponible: instale rapidocr-onnxruntime '
                    '(pip install rapidocr-onnxruntime) en el servidor.')
    except Exception as e:
        return '', f'El OCR no pudo procesar la imagen ({type(e).__name__}).'


def analizar(texto=None, archivo=None):
    """Parsea texto y/o imagen y devuelve las filas con la materia prima asociada."""
    avisos = []
    contenido = texto or ''

    if archivo is not None:
        datos = archivo.read()
        texto_ocr, aviso = extraer_texto_imagen(datos)
        if aviso:
            avisos.append(aviso)
        if texto_ocr:
            contenido = (contenido + '\n' + texto_ocr).strip()

    filas = parsear_texto(contenido)
    catalogo = [dict(m) for m in MateriaPrima.get_all()]

    resultado = []
    for fila in filas:
        materia, puntaje = buscar_materia(fila['texto'], catalogo)
        aviso = fila.get('aviso')
        if not materia:
            aviso = 'Sin coincidencia en el maestro'
        elif puntaje < 0.999:
            aviso = f'Coincidencia aproximada ({int(puntaje * 100)}%)'

        resultado.append({
            'texto': fila['texto'],
            'cantidad': fila['cantidad'],
            'es_nucleo': fila['es_nucleo'],
            'materia_prima_id': materia['id'] if materia else None,
            'materia_nombre': materia['nombre'] if materia else '',
            'puntaje': round(puntaje, 3),
            'aviso': aviso,
        })

    return {'filas': resultado, 'avisos': avisos}


def insertar_insumos(item_id, lote_id, version, filas, baches_nucleo=6):
    """
    Inserta los insumos revisados en la receta.

    Cada fila: {materia_prima_id | nuevo_nombre, cantidad, es_nucleo}.
    Si trae 'nuevo_nombre', crea la materia prima con el precio indicado.
    Usa los precios actuales del maestro (igual que "Agregar insumo").
    """
    insertados = 0
    creadas = []
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            for fila in filas:
                materia_prima_id = fila.get('materia_prima_id')
                cantidad = float(fila.get('cantidad') or 0)
                if cantidad <= 0:
                    continue

                if not materia_prima_id:
                    nombre_nuevo = (fila.get('nuevo_nombre') or '').strip()
                    if not nombre_nuevo:
                        continue
                    cur.execute("""
                        INSERT INTO materias_primas
                            (nombre, precio_actual_kg, iva, flete, fecha_actualizacion)
                        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                        RETURNING id
                    """, (
                        nombre_nuevo.upper(),
                        float(fila.get('nuevo_precio') or 0),
                        float(fila.get('nuevo_iva') or 1),
                        float(fila.get('nuevo_flete') or 0),
                    ))
                    materia_prima_id = cur.fetchone()[0]
                    creadas.append(nombre_nuevo.upper())

                cur.execute("""
                    INSERT INTO formula_detalle
                        (item_id, lote_id, materia_prima_id, cantidad_kg, es_nucleo,
                         baches_nucleo, precio_guardado, iva_guardado, flete_guardado, version)
                    SELECT %s, %s, %s, %s, %s, %s, precio_actual_kg, iva, flete, %s
                    FROM materias_primas
                    WHERE id = %s
                """, (
                    item_id, lote_id, materia_prima_id, cantidad,
                    bool(fila.get('es_nucleo')), baches_nucleo, version, materia_prima_id,
                ))
                insertados += cur.rowcount

        conn.commit()
        if creadas:
            MateriaPrima.invalidar_cache()
        return {'insertados': insertados, 'creadas': creadas}
    except Exception as e:
        conn.rollback()
        print(f"Error al importar insumos: {e}")
        raise
    finally:
        conn.close()
