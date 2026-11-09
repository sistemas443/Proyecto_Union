# -*- coding: utf-8 -*-
"""Utilidades comunes para el comparador de lotes de Producción.

El comparador reutiliza las vistas de cada módulo dentro de paneles (iframe)
en modo solo lectura. Aquí solo se arma la lista de lotes seleccionados.
"""
from models.cabecera.services import get_cabecera_info

LETRAS = ('A', 'B', 'C', 'D')
COLORES = ('#97271C', '#1f4e79', '#2f7d4f', '#a06a00')
CLAVES_EXTRA = ('lote_b', 'lote_c', 'lote_d')


def leer_cantidad(request):
    try:
        cantidad = int(request.args.get('cantidad', 2))
    except (TypeError, ValueError):
        cantidad = 2
    return max(2, min(4, cantidad))


def construir_paneles(request):
    """Devuelve (paneles, cantidad) cuando la URL pide comparación.

    paneles: lista de dicts con letra, color, lote y cabecera.
    Devuelve (None, 2) si no se está comparando.
    """
    if request.args.get('comparar') != '1':
        return None, 2

    cantidad = leer_cantidad(request)
    lote_a = (request.args.get('lote_a') or request.args.get('lote') or '').strip()
    if not lote_a or lote_a == 'VACIO':
        return None, cantidad

    cab_a = get_cabecera_info(lote_a)
    if not cab_a:
        return None, cantidad

    paneles = [{
        'letra': LETRAS[0],
        'color': COLORES[0],
        'lote': lote_a,
        'cabecera': cab_a,
    }]
    usados = {lote_a}

    for indice in range(1, cantidad):
        lote = (request.args.get(CLAVES_EXTRA[indice - 1]) or '').strip()
        cabecera = None
        if lote and lote != 'VACIO' and lote not in usados:
            cabecera = get_cabecera_info(lote)
            if cabecera:
                usados.add(lote)
            else:
                lote = ''
        else:
            lote = ''
        paneles.append({
            'letra': LETRAS[indice],
            'color': COLORES[indice],
            'lote': lote,
            'cabecera': cabecera,
        })

    return paneles, cantidad


def datos_lotes(lotes):
    """Datos mínimos de cabecera por lote para actualizar el comparador."""
    datos = {}
    for lote in lotes:
        cabecera = get_cabecera_info(lote) or {}
        datos[lote] = {
            'aves': cabecera.get('no_pollitas_recibidas'),
            'variedad': cabecera.get('variedad') or '',
        }
    return datos
