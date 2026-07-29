# models/primera_semana/schemas.py

COLUMNAS_PERMITIDAS = {
    # Identificadores de fila
    'lote', 'fecha', 'semana',
    
    # Consumo de Alimento (Guías y Reales)
    'consumo_gr_a_tab', 'consumo_kg', 'consumo_gr_a_d', 
    'cons_k_acum', 'cons_gr_ave_tab_acum', 'cons_gr_ave_ac',
    
    # Inventario y Bajas
    'mortalidad', 'sel', 'porc_mort_sem', 'porc_mort_acum', 'saldo_aves',
    
    # Pesos y Uniformidad del lote
    'peso_tabla', 'peso_real', 'unif_10_menos', 'porc_uniformidad', 'unif_10_mas',
    'coef_variacion', 
    
    # Notas de campo
    'observaciones'
}