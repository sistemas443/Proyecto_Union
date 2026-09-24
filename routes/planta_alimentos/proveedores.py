from flask import render_template, request, redirect, url_for, flash
from routes.planta_alimentos.catalogo_a import planta_bp
from routes.routes import login_requerido
from models.planta_alimentos.maestros import Proveedor  # Ajusta la ruta a tu modelo
# ==========================================
# 3. PROVEEDORES
# ==========================================

@planta_bp.route('/planta_alimentos/proveedores', methods=['GET', 'POST'])
@login_requerido
def proveedores():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '')
        if nombre:
            Proveedor.create(nombre)
            flash('Proveedor guardado correctamente.', 'success')
        return redirect(url_for('planta_alimentos.proveedores'))
        
    lista_proveedores = Proveedor.get_all()
    return render_template('planta_alimentos/proveedores.html', proveedores=lista_proveedores)


@planta_bp.route('/planta_alimentos/proveedores/editar/<int:id_prov>', methods=['POST'])
@login_requerido
def editar_proveedor(id_prov):
    nombre = request.form.get('nombre', '')
    if nombre:
        Proveedor.update(id_prov, nombre)
        flash('Proveedor actualizado.', 'success')
    return redirect(url_for('planta_alimentos.proveedores'))


@planta_bp.route('/planta_alimentos/proveedores/eliminar/<int:id_prov>', methods=['POST'])
@login_requerido
def eliminar_proveedor(id_prov):
    Proveedor.delete(id_prov)
    flash('Proveedor eliminado.', 'warning')
    return redirect(url_for('planta_alimentos.proveedores'))