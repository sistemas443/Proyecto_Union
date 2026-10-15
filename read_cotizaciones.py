import openpyxl

workbook = openpyxl.load_workbook(r"C:\Users\Lider sistemas\Documents\cotizaciones\Cotizaciones.xlsx")

print("=== HOJAS ===")
for sheet_name in workbook.sheet_names():
    print(f"\n--- Hoja: {sheet_name} ---")
    sheet = workbook[sheet_name]
    print(f"Filas: {sheet.max_row}, Columnas: {sheet.max_column}")
    
    # Mostrar primeras 10 filas
    for row_idx in range(1, min(sheet.max_row + 1, 15)):
        row_data = []
        for col_idx in range(1, sheet.max_column + 1):
            cell = sheet.cell(row=row_idx, column=col_idx)
            row_data.append(str(cell.value))
        print(f"  Fila {row_idx}: {' | '.join(row_data)}")
    
    if sheet.max_row > 15:
        print(f"  ... ({sheet.max_row - 15} filas más)")

print("\n=== FIN ===")