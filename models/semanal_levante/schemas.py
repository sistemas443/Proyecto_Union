# models/semanal_levante/schemas.py

COLUMNAS_PERMITIDAS = {
    'fecha_fin_sem', 
    'cons_tab', 'cons_real', 'cons_kilos_real', 'cons_k_acum', 'cons_gr_ave_tab', 'cons_gr_ave_ao',
    'conv_sem', 'conv_sem_tab', 
    'cons_agua_real', 'cons_agua_tab',
    'mort_sem', 'mort_select_sem', 'mort_venta', 'salidas_acum', 'saldo_ave', 'mort_tab',
    'percent_mort_sem', 'percent_mort_acum', 'percent_select_sem', 'percent_mort_and_select_acum',
    'peso_ave_real', 'peso_ave_tab', 'unif', 'cv', 'unif_porc_uni', 'unif_10_menos', 
    'unif_porc_unif', 'unif_10_mas', 'unif_cv', 't_tarso', 't_tarso_r',
    'ganancia_ave_dia', 'ganancia_ave', 'porc_cumpl_ganan', 'porc_cumpl_cons',
    'observaciones_lev', 'marca_tipo_de', 'lote'
}