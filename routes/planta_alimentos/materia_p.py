from flask import render_template, request, redirect, url_for, flash
from models.planta_alimentos.maestros import MateriaPrima, Proveedor
from routes.routes import login_requerido  # Importa tu decorador propio en lugar de flask_login
from routes.planta_alimentos.catalogo_a import planta_bp

@planta_bp.route('/materias-primas', methods=['GET', 'POST'])
@login_requerido
def materias_primas():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip().upper()
        proveedor = request.form.get('proveedor', '').strip().upper()
        
        precio_raw = request.form.get('precio_actual_kg', '0').replace('.', '')
        flete_raw = request.form.get('flete', '0').replace('.', '')
        
        precio_actual_kg = float(precio_raw) if precio_raw else 0.0
        flete = float(flete_raw) if flete_raw else 0.0
        iva = float(request.form.get('iva', '1.00'))
        es_maquila = True if request.form.get('es_maquila') else False

        try:
            MateriaPrima.create(nombre, precio_actual_kg, proveedor, iva, flete, es_maquila)
            flash('Materia prima registrada exitosamente.', 'success')
        except Exception as e:
            print(f"Error al guardar materia prima: {e}")
            flash('Error al guardar la materia prima.', 'danger')
            
        return redirect(url_for('planta_alimentos.materias_primas'))
        
    lista_mp = MateriaPrima.get_all()
    lista_proveedores = Proveedor.get_all()  # <--- Consulta la lista de proveedores
    
    return render_template(
        '/planta_alimentos/materias_primas.html', 
        materias_primas=lista_mp, 
        proveedores=lista_proveedores  # <--- Envía la lista a Jinja2
    )


@planta_bp.route('/materias-primas/editar/<int:id_mp>', methods=['POST'])
@login_requerido
def editar_materia_prima(id_mp):
    nombre = request.form.get('nombre', '').strip().upper()
    proveedor = request.form.get('proveedor', '').strip().upper()
    
    precio_raw = request.form.get('precio_actual_kg', '0').replace('.', '')
    flete_raw = request.form.get('flete', '0').replace('.', '')
    
    precio_actual_kg = float(precio_raw) if precio_raw else 0.0
    flete = float(flete_raw) if flete_raw else 0.0
    iva = float(request.form.get('iva', '1.00'))
    es_maquila = True if request.form.get('es_maquila') else False

    try:
        MateriaPrima.update(id_mp, nombre, precio_actual_kg, proveedor, iva, flete, es_maquila)
        flash('Materia prima actualizada correctamente.', 'success')
    except Exception as e:
        print(f"Error al editar materia prima: {e}")
        flash('Error al actualizar la materia prima.', 'danger')

    return redirect(url_for('planta_alimentos.materias_primas'))


@planta_bp.route('/materias-primas/eliminar/<int:id_mp>', methods=['POST'])
@login_requerido
def eliminar_materia_prima(id_mp):
    try:
        MateriaPrima.delete(id_mp)
        flash('Materia prima eliminada correctamente.', 'success')
    except Exception as e:
        print(f"Error al eliminar materia prima: {e}")
        # Si viola la restricción de llave foránea (psycopg2.errors.ForeignKeyViolation)
        flash('No se puede eliminar la materia prima porque está asignada a una o más fórmulas activas.', 'danger')
        
    return redirect(url_for('planta_alimentos.materias_primas'))