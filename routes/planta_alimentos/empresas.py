from flask import render_template, request, redirect, url_for, flash
from routes.planta_alimentos.catalogo_a import planta_bp  # O la ruta donde tengas definido el Blueprint
from routes.routes import login_requerido
from models.planta_alimentos.maestros   import Empresa

@planta_bp.route('/empresas-maquila', methods=['GET', 'POST'])
@login_requerido
def empresas_maquila():
    if request.method == 'POST':
        nombre = request.form.get('nombre').strip().upper()
        costo_maquila = request.form.get('costo_maquila', 0)
        
        try:
            Empresa.create(nombre, costo_maquila)
        except Exception as e:
            print(f"Error al guardar empresa: {e}") 
            
        return redirect(url_for('planta_alimentos.empresas_maquila'))
        
    lista_empresas = Empresa.get_all()
    return render_template('planta_alimentos/empresas_maquila.html', empresas=lista_empresas)

