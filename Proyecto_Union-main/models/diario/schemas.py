# models/diario/schemas.py

MAPA_COLUMNAS = {
    'fecha': 'fecha_dia', 
    'semana': 'sem',
    'kilos': 'consumo_kg',
    'tab': 'consumo_gr_a_tab'
}

# Agregamos las nuevas columnas calculadas a la lista permitida
COLUMNAS_PERMITIDAS = {
    'fecha_dia', 'dias', 'sem', 'mortalidad', 'sel', 'otros', 
    'produccion', 'consumo_kg', 'observaciones', 'consumo_agua',
    'peso_tabla', 'peso_real', 'unif_10_menos', 'porc_uniformidad', 
    'unif_10_mas', 'coef_variacion', 'saldo_aves', 'consumo_gr_a_d',
    'consumo_gr_a_tab', 'percent_diario_prod', 'prom_ave_dia_cc',
    'cons_k_acum', 'cons_gr_ave_tab_acum', 'cons_gr_ave_ac' # Nuevas
}