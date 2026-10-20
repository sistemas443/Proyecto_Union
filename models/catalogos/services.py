"""Lógica de negocio de los catálogos con foto: validación + imágenes en BD."""
import io
import os
from flask import url_for
from PIL import Image, ImageOps
from models.catalogos import model, schemas


def listar_catalogo(tipo: str) -> list:
    """Lista los valores activos de un catálogo validando el tipo."""
    tabla = schemas.obtener_tabla(tipo)
    if not tabla:
        return []
    return model.listar(tabla)


def _procesar_archivo(archivo):
    """Procesa la imagen a JPEG 300x300 y devuelve los bytes en memoria.
    Devuelve (bytes | None, mensaje_error | None)."""
    if archivo is None or not archivo.filename:
        return None, 'La foto es obligatoria.'

    extension = archivo.filename.rsplit('.', 1)[-1].lower() if '.' in archivo.filename else ''
    if extension not in schemas.EXTENSIONES_PERMITIDAS:
        return None, 'Formato no permitido. Use JPG, JPEG, PNG o WEBP.'

    # Límite de 5 MB
    archivo.seek(0, os.SEEK_END)
    tamano = archivo.tell()
    archivo.seek(0)
    if tamano > schemas.TAMANO_MAXIMO_BYTES:
        return None, 'La imagen es demasiado pesada. El máximo permitido es 5 MB.'

    try:
        img = Image.open(archivo)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img_cuadrada = ImageOps.fit(img, (300, 300), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        img_cuadrada.save(buffer, format='JPEG', optimize=True, quality=85)
        return buffer.getvalue(), None
    except Exception as e:
        print(f"[ERROR PROCESANDO FOTO CATALOGO]: {e}")
        return None, 'El archivo no es una imagen válida.'


def crear_catalogo(tipo: str, nombre, archivo_foto) -> tuple:
    """Crea un valor con foto obligatoria (guardada en BD). Devuelve (ok, mensaje, datos)."""
    tabla = schemas.obtener_tabla(tipo)
    if not tabla:
        return False, 'Tipo de catálogo inválido.', None

    nombre_ok, error = schemas.validar_nombre(nombre)
    if error:
        return False, error, None

    existente = model.buscar_por_nombre(tabla, nombre_ok)
    if existente and existente['activo']:
        return False, 'Este valor ya existe en el catálogo.', None

    foto_bytes, error = _procesar_archivo(archivo_foto)
    if error:
        return False, error, None

    try:
        if existente:  # Existía borrado lógicamente -> se reactiva
            model.reactivar(tabla, existente['id'], nombre_ok, foto_bytes)
            nuevo_id = existente['id']
        else:
            nuevo_id = model.insertar(tabla, nombre_ok, foto_bytes)
    except Exception as e:
        print(f"[ERROR CREANDO CATALOGO]: {e}")
        return False, 'Error interno al guardar.', None

    return True, 'Guardado exitosamente.', {'nombre': nombre_ok, 'id': nuevo_id}


def editar_catalogo(tipo: str, id_item: int, nombre, archivo_foto) -> tuple:
    """Edita nombre y/o foto. Si no se envía foto, conserva la actual."""
    tabla = schemas.obtener_tabla(tipo)
    if not tabla:
        return False, 'Tipo de catálogo inválido.', None

    actual = model.buscar_por_id(tabla, id_item)
    if not actual or not actual['activo']:
        return False, 'El valor no existe.', None

    nombre_ok, error = schemas.validar_nombre(nombre)
    if error:
        return False, error, None

    duplicado = model.buscar_por_nombre(tabla, nombre_ok)
    if duplicado and duplicado['activo'] and duplicado['id'] != id_item:
        return False, 'Otro valor del catálogo ya usa ese nombre.', None

    foto_actual = actual.get('foto_data')
    foto_final = foto_actual

    if archivo_foto is not None and archivo_foto.filename:
        foto_nueva, error = _procesar_archivo(archivo_foto)
        if error:
            return False, error, None
        foto_final = foto_nueva

    try:
        model.actualizar(tabla, id_item, nombre_ok, foto_final)
    except Exception as e:
        print(f"[ERROR EDITANDO CATALOGO]: {e}")
        return False, 'Error interno al guardar.', None

    return True, 'Actualizado exitosamente.', {'nombre': nombre_ok, 'id': id_item}


def eliminar_catalogo(tipo: str, id_item: int) -> tuple:
    """Borrado LÓGICO (la foto vive en la BD y se conserva para historicos)."""
    tabla = schemas.obtener_tabla(tipo)
    if not tabla:
        return False, 'Tipo de catálogo inválido.', None

    actual = model.buscar_por_id(tabla, id_item)
    if not actual:
        return False, 'El valor no existe.', None

    try:
        model.borrar_logico(tabla, id_item)
    except Exception as e:
        print(f"[ERROR BORRANDO CATALOGO]: {e}")
        return False, 'Error interno al eliminar.', None

    return True, 'Valor eliminado.', {'nombre': actual['nombre']}


def url_foto_por_id(tipo: str, id_item) -> str:
    """URL de la foto servida desde la BD. Si no hay id, devuelve el placeholder."""
    if id_item is None:
        return url_for('static', filename=schemas.FOTO_PLACEHOLDER)
    return url_for('catalogos.foto_catalogo', tipo=tipo, id_item=id_item)


def foto_por_nombre(tipo: str, nombre):
    """Busca la foto de un valor en su catálogo.
    Devuelve (nombre_mostrado, foto_url) con fallback al placeholder."""
    tabla = schemas.obtener_tabla(tipo)
    nombre_limpio = (nombre or '').strip()
    item = model.buscar_por_nombre(tabla, nombre_limpio.upper()) if (tabla and nombre_limpio) else None
    if not item:
        return (nombre_limpio or '---'), url_for('static', filename=schemas.FOTO_PLACEHOLDER)
    # Prioridad: bytes en BD. Respaldo: ruta de archivo antigua (migracion).
    if item.get('foto_data'):
        return (nombre_limpio or '---'), url_foto_por_id(tipo, item['id'])
    if item.get('foto'):
        return (nombre_limpio or '---'), url_for('static', filename=item['foto'])
    return (nombre_limpio or '---'), url_for('static', filename=schemas.FOTO_PLACEHOLDER)


def info_lote_para_grafico(cabecera: dict, campo_nutri: str, etiqueta_nutri: str) -> dict:
    """Arma el diccionario info_lote para la franja de fotos de los gráficos."""
    cab = cabecera or {}
    tipo_nutri = 'nutricionista_lev' if campo_nutri == 'nutricionista' else 'nutricionista_prod'
    n_nutri, f_nutri = foto_por_nombre(tipo_nutri, cab.get(campo_nutri))
    n_var, f_var = foto_por_nombre('variedad', cab.get('variedad'))
    n_marca, f_marca = foto_por_nombre('marca_galpon', cab.get('marca_galpon'))
    return {
        'nutricionista': {'etiqueta': etiqueta_nutri, 'nombre': n_nutri, 'foto': f_nutri},
        'variedad': {'etiqueta': 'Variedad', 'nombre': n_var, 'foto': f_var},
        'marca': {'etiqueta': 'Marca Galpón', 'nombre': n_marca, 'foto': f_marca},
    }
