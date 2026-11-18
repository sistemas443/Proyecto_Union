# -*- coding: utf-8 -*-
"""Series para el grafico de % de produccion vs dia (Primer Huevo)."""


def get_series_primer_huevo(matriz, objetivos=(0.01, 0.05, 0.20, 0.50, 0.90)):
    """
    Devuelve una serie por lote con:
      - dias / valores (% de produccion)
      - media movil de 2 periodos
      - hitos: el dia mas cercano a cada objetivo (1%, 5%, 20%, 50%, 90%)

    El objetivo se evalua sobre el % real (0-100). Cada punto se usa una sola vez,
    igual que el coloreado de la matriz.
    """
    lotes = matriz.get('lotes') or []
    filas = matriz.get('filas') or []

    series = []

    for lote in lotes:
        dias = []
        valores = []

        for fila in filas:
            celda = (fila.get('celdas') or {}).get(lote)
            valor = celda.get('valor') if celda else None
            if valor is None:
                continue
            dias.append(fila.get('dia'))
            valores.append(round(float(valor) * 100, 2))

        if not dias:
            continue

        # Media movil de 2 periodos (valor actual y anterior)
        media = []
        for i, v in enumerate(valores):
            base = valores[max(0, i - 1): i + 1]
            media.append(round(sum(base) / len(base), 2))

        # Un hito por objetivo: el punto mas cercano que no se haya usado
        usados = set()
        hitos = []
        for objetivo in objetivos:
            meta = objetivo * 100
            mejor_i = None
            mejor_dif = None
            for i, v in enumerate(valores):
                if i in usados:
                    continue
                dif = abs(v - meta)
                if mejor_dif is None or dif < mejor_dif:
                    mejor_dif = dif
                    mejor_i = i
            if mejor_i is not None:
                usados.add(mejor_i)
                hitos.append({
                    'dia': dias[mejor_i],
                    'valor': valores[mejor_i],
                    'objetivo': round(meta),
                })

        series.append({
            'lote': lote,
            'dias': dias,
            'valores': valores,
            'media': media,
            'hitos': hitos,
        })

    return series
