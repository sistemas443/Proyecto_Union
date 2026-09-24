from flask import Blueprint, render_template, request, redirect, url_for, flash
from routes.routes import login_requerido  # Importa tu decorador propio en lugar de flask_login
from models.planta_alimentos.maestros import CatalogoAlimento  # Ajusta a tu modelo de catálogo
from models.planta_alimentos.formulas import FormulaDetalle

planta_bp = Blueprint('planta_alimentos', __name__)

@planta_bp.route('/planta_alimentos/catalogo-alimentos', methods=['GET', 'POST'])
@login_requerido
def catalogo_alimentos():
    if request.method == 'POST':
        item_id = request.form.get('item_id')
        nombre = request.form.get('nombre').strip().upper()
        rango_semanas = request.form.get('rango_semanas').strip()
        
        try:
            CatalogoAlimento.create(item_id, nombre, rango_semanas)
        except Exception as e:
            print(f"Error al guardar dieta: {e}") 
            
        return redirect(url_for('planta_alimentos.catalogo_alimentos'))
        
    lista_alimentos = CatalogoAlimento.get_all()
    return render_template('planta_alimentos/catalogo_alimentos.html', alimentos=lista_alimentos)

# Actualiza la importación
from models.planta_alimentos.maestros import MateriaPrima, CatalogoAlimento, Empresa


@planta_bp.route('/recetario-formulas')
@login_requerido
def recetario_formulas():
    # Redirige directamente al catálogo, que es donde ahora gestionamos las recetas
    return redirect(url_for('planta_alimentos.catalogo_alimentos'))

@planta_bp.route('/catalogo-alimentos/eliminar/<int:item_id>', methods=['POST'])
@login_requerido
def eliminar_dieta(item_id):
    exito = FormulaDetalle.eliminar_dieta(item_id)
    if exito:
        flash('Dieta eliminada del catálogo correctamente.', 'success')
    else:
        flash('Error al eliminar. Es posible que esta dieta ya tenga fórmulas o lotes asociados y no se pueda borrar.', 'error')
        
    return redirect(url_for('planta_alimentos.catalogo_alimentos'))

@planta_bp.route('/catalogo-alimentos/editar/<int:item_id>', methods=['POST'])
@login_requerido
def editar_dieta(item_id):
    nombre = request.form.get('nombre')
    rango = request.form.get('rango_semanas')
    
    if nombre:
        exito = FormulaDetalle.actualizar_dieta(item_id, nombre, rango)
        if exito:
            flash('Dieta actualizada correctamente.', 'success')
        else:
            flash('Hubo un error al actualizar la dieta en la base de datos.', 'error')
    else:
        flash('El nombre de la dieta es obligatorio.', 'error')
        
    return redirect(url_for('planta_alimentos.catalogo_alimentos'))