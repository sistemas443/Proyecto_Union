import xlrd
import sys

# Redirect stdout to file
sys.stdout = open('excel_output.txt', 'w', encoding='utf-8')

workbook = xlrd.open_workbook(r"C:\Users\Lider sistemas\Documents\Proyecciones\PROYECCION.xls")

for sheet_name in workbook.sheet_names():
    print("=== Hoja: " + sheet_name + " ===")
    sheet = workbook.sheet_by_name(sheet_name)
    print("Filas: " + str(sheet.nrows) + ", Columnas: " + str(sheet.ncols))
    for row_idx in range(min(sheet.nrows, 30)):
        row_data = []
        for col_idx in range(sheet.ncols):
            cell = sheet.cell(row_idx, col_idx)
            row_data.append(str(cell.value))
        print("  Fila " + str(row_idx) + ": " + " | ".join(row_data))

sys.stdout.close()
print("Done - output saved to excel_output.txt")