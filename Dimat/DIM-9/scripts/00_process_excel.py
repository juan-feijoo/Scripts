# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT 00: EXTRACCIÓN Y LIMPIEZA DEL EXCEL A JSON
================================================================================
No requiere librerías externas (usa standard library: zipfile y xml.etree).
Convierte 'Precios para costos.xlsx' (o cualquier archivo que le pases)
en 'precios_procesados.json'.
================================================================================
"""
import sys
import os
import json
import zipfile
import xml.etree.ElementTree as ET

def process_excel(excel_path="Precios para costos.xlsx", output_json="scripts/precios_procesados.json"):
    if not os.path.exists(excel_path):
        # Intentar en el directorio padre
        alt_path = os.path.join("..", excel_path)
        if os.path.exists(alt_path):
            excel_path = alt_path
        else:
            raise FileNotFoundError(f"No se encontró el archivo Excel: {excel_path}")

    print(f"Leyendo '{excel_path}'...")
    with zipfile.ZipFile(excel_path, 'r') as z:
        # 1. Cargar cadenas compartidas
        shared_strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
            ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            for si in tree.findall('.//main:si', ns):
                shared_strings.append(''.join([t.text for t in si.findall('.//main:t', ns) if t.text]))

        # 2. Hoja 1: Precios para costos
        target_file = 'xl/worksheets/sheet1.xml'
        ns_wb = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        sheet_tree = ET.fromstring(z.read(target_file))
        rows = sheet_tree.findall('.//main:sheetData/main:row', ns_wb)

        items = []
        for row in rows[1:]:  # Omitir cabecera
            row_dict = {}
            for c in row.findall('main:c', ns_wb):
                r_ref = c.attrib.get('r')
                col_letter = ''.join([ch for ch in r_ref if ch.isalpha()])
                val = c.find('main:v', ns_wb)
                cell_type = c.attrib.get('t')
                cell_val = val.text if val is not None else ''
                if cell_type == 's' and cell_val != '':
                    cell_val = shared_strings[int(cell_val)]
                row_dict[col_letter] = cell_val

            code = row_dict.get('A', '').strip()
            name = row_dict.get('B', '').strip()
            brand = row_dict.get('C', '').strip()
            curr = row_dict.get('D', '').strip()
            try:
                p_rep = float(row_dict.get('E', 0) or 0)
            except:
                p_rep = 0.0
            tag = row_dict.get('F', '').strip()
            try:
                p_uc = float(row_dict.get('H', 0) or 0)
            except:
                p_uc = 0.0

            if code:
                items.append({
                    'code': code,
                    'name': name,
                    'brand': brand,
                    'currency': 'ARS' if curr == 'Corriente' else 'USD',
                    'price_reposicion': p_rep,
                    'price_ultima_compra': p_uc,
                    'tag': tag
                })

    # Asegurar directorio de destino
    os.makedirs(os.path.dirname(output_json) or '.', exist_ok=True)
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"Procesados {len(items)} registros exitosamente -> {output_json}")

if __name__ == '__main__':
    excel_file = sys.argv[1] if len(sys.argv) > 1 else "Precios para costos.xlsx"
    process_excel(excel_file)
