import xlrd

# Abrir el archivo .xls
workbook = xlrd.open_workbook(r"C:\Users\Lider sistemas\Documents\Proyecciones\PROYECCION.xls")

print("=== HOJAS ===")
for sheet_name in workbook.sheet_names():
    print(f"\n--- Hoja: {sheet_name} ---")
    sheet = workbook.sheet_by_name(sheet_name)
    print(f"Filas: {sheet.nrows}, Columnas: {sheet.ncols}")
    
    # Mostrar primeras 10 filas
    for row_idx in range(min(sheet.nrows, 15)):
        row_data = []
        for col_idx in range(sheet.ncols):
            cell = sheet.cell(row_idx, col_idx)
            row_data.append(str(cell.value))
        print(f"  Fila {row_idx}: {' | '.join(row_data)}")

print("\n=== FIN ===")