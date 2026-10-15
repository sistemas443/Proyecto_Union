"""Lógica de negocio de los catálogos con foto: validación + subida de imágenes."""
import os
import uuid
from flask import current_app, url_for
from PIL import Image, ImageOps
from models.catalogos import model, schemas


def listar_catalogo(tipo: str) -> list:
    """Lista los valores activos de un catálogo validando el tipo."""
    tabla = schemas.obtener_tabla(tipo)
    if not tabla:
        return []
    return model.listar(tabla)


def _guardar_archivo(archivo, tipo: str):
    """Guarda la foto en static/uploads/catalogos/<tipo>/ como JPEG 300x300.
    Devuelve (ruta_relativa | None, mensaje_error | None)."""
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

    carpeta = os.path.join(current_app.root_path, 'static', 'uploads', 'catalogos', tipo)
    os.makedirs(carpeta, exist_ok=True)

    nombre_archivo = f"{tipo}_{uuid.uuid4().hex[:12]}.jpg"
    ruta_absoluta = os.path.join(carpeta, nombre_archivo)

    try:
        img = Image.open(archivo)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img_cuadrada = ImageOps.fit(img, (300, 300), Image.Resampling.LANCZOS)
        img_cuadrada.save(ruta_absoluta, format='JPEG', optimize=True, quality=85)
    except Exception as e:
        print(f"[ERROR GUARDANDO FOTO CATALOGO]: {e}")
        return None, 'El archivo no es una imagen válida.'

    return f"uploads/catalogos/{tipo}/{nombre_archivo}", None


def _borrar_archivo(ruta_relativa: str) -> None:
    """Borra la foto física SOLO si es nuestra (uploads/catalogos/).
    Nunca toca el placeholder."""
    if not ruta_relativa or ruta_relativa == schemas.FOTO_PLACEHOLDER:
        return
    if not ruta_relativa.replace('\\', '/').startswith('uploads/catalogos/'):
        return
    ruta_absoluta = os.path.join(current_app.root_path, 'static', *ruta_relativa.split('/'))
    if os.path.exists(ruta_absoluta):
        try:
            os.remove(ruta_absoluta)
        except Exception as e:
            print(f"[ADVERTENCIA] No se pudo borrar la foto: {e}")


def crear_catalogo(tipo: str, nombre, archivo_foto) -> tuple:
    """Crea un valor con foto obligatoria. Devuelve (ok, mensaje, datos)."""
    tabla = schemas.obtener_tabla(tipo)
    if not tabla:
        return False, 'Tipo de catálogo inválido.', None

    nombre_ok, error = schemas.validar_nombre(nombre)
    if error:
        return False, error, None

    existente = model.buscar_por_nombre(tabla, nombre_ok)
    if existente and existente['activo']:
        return False, 'Este valor ya existe en el catálogo.', None

    foto, error = _guardar_archivo(archivo_foto, tipo)
    if error:
        return False, error, None

    try:
        if existente:  # Existía borrado lógicamente -> se reactiva
            model.reactivar(tabla, existente['id'], nombre_ok, foto)
        else:
            model.insertar(tabla, nombre_ok, foto)
    except Exception as e:
        _borrar_archivo(foto)
        print(f"[ERROR CREANDO CATALOGO]: {e}")
        return False, 'Error interno al guardar.', None

    return True, 'Guardado exitosamente.', {'nombre': nombre_ok, 'foto': foto}


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

    foto_actual = actual['foto']
    foto_final = foto_actual

    if archivo_foto is not None and archivo_foto.filename:
        foto_nueva, error = _guardar_archivo(archivo_foto, tipo)
        if error:
            return False, error, None
        foto_final = foto_nueva

    try:
        model.actualizar(tabla, id_item, nombre_ok, foto_final)
    except Exception as e:
        print(f"[ERROR EDITANDO CATALOGO]: {e}")
        return False, 'Error interno al guardar.', None

    if foto_final != foto_actual:
        _borrar_archivo(foto_actual)  # Ahorro de espacio: fuera la foto vieja

    return True, 'Actualizado exitosamente.', {'nombre': nombre_ok, 'foto': foto_final}


def eliminar_catalogo(tipo: str, id_item: int) -> tuple:
    """Borrado LÓGICO + borra la foto física (salvo el placeholder)."""
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

    _borrar_archivo(actual['foto'])
    return True, 'Valor eliminado.', {'nombre': actual['nombre']}


def url_foto(ruta_relativa) -> str:
    """Convierte la ruta relativa a static/ en una URL servible."""
    return url_for('static', filename=ruta_relativa or schemas.FOTO_PLACEHOLDER)
