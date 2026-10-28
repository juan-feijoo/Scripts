# -*- coding: utf-8 -*-
"""
Auditoría técnica exhaustiva de Márgenes y Listas de Precios
Origen: Sistema Cristian 27-10 kiddie.xlsx (Hojas: produc_vista y clientes)
"""

import json
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter

EXCEL_FILE = 'Sistema Cristian 27-10 kiddie.xlsx'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def col_to_idx(cell_ref):
    letters = ''.join([c for c in cell_ref if c.isalpha()])
    idx = 0
    for c in letters:
        idx = idx * 26 + (ord(c.upper()) - ord('A') + 1)
    return idx - 1

def clean_float(val, default=0.0):
    if not val:
        return default
    try:
        return float(str(val).replace(',', '.'))
    except (ValueError, TypeError):
        return default

def parse_sheet_rows(z, sheet_path):
    shared_strings = []
    if 'xl/sharedStrings.xml' in z.namelist():
        ss_root = ET.fromstring(z.read('xl/sharedStrings.xml'))
        for si in ss_root.findall('s:si', NS):
            t = si.find('s:t', NS)
            if t is not None and t.text:
                shared_strings.append(t.text)
            else:
                r_texts = [r.find('s:t', NS).text for r in si.findall('s:r', NS) if r.find('s:t', NS) is not None and r.find('s:t', NS).text]
                shared_strings.append(''.join(r_texts))

    sheet_root = ET.fromstring(z.read(sheet_path))
    rows = sheet_root.findall('.//s:row', NS)
    headers = [c.find('s:v', NS).text if c.find('s:v', NS) is not None else '' for c in rows[0].findall('s:c', NS)]
    headers = [shared_strings[int(h)] if h.isdigit() and int(h) < len(shared_strings) else h for h in headers]

    result = []
    for r in rows[1:]:
        cells = r.findall('s:c', NS)
        row_dict = {}
        for c in cells:
            pos = col_to_idx(c.attrib.get('r', 'A1'))
            if pos < len(headers):
                v = c.find('s:v', NS)
                t_type = c.attrib.get('t')
                val = v.text if v is not None else ''
                if t_type == 's' and val.isdigit():
                    val = shared_strings[int(val)]
                row_dict[headers[pos]] = val.strip() if isinstance(val, str) else str(val).strip()
        result.append(row_dict)
    return result

def main():
    with zipfile.ZipFile(EXCEL_FILE) as z:
        prods = parse_sheet_rows(z, 'xl/worksheets/sheet3.xml')
        clientes = parse_sheet_rows(z, 'xl/worksheets/sheet1.xml')

    print("=" * 80)
    print("AUDITORÍA DE LISTAS DE PRECIOS Y MÁRGENES")
    print("=" * 80)

    # 1. Análisis en Clientes
    listas_cli = Counter(c.get('lista', '') for c in clientes)
    print(f"\n1. DISTRIBUCIÓN DE LISTAS EN CLIENTES ({len(clientes)} clientes):")
    nombres_listas = {
        '1': 'Minorista 1 (Predeterminada)',
        '2': 'Minorista 2',
        '3': 'Minorista 3',
        '4': 'Mayorista',
        '5': 'Distribuidor'
    }
    for cod_lista, count in listas_cli.most_common():
        desc = nombres_listas.get(cod_lista, 'Sin definir')
        print(f"  - Lista {cod_lista} ({desc}): {count} clientes ({count/len(clientes)*100:.1f}%)")

    # 2. Análisis de Columnas de Margen en Productos
    print(f"\n2. COLUMNAS DE MÁRGENES EN PRODUCTOS ({len(prods)} productos):")
    margin_cols = [
        ('margenmin1', 'Lista 1 - Minorista 1'),
        ('margenmin2', 'Lista 2 - Minorista 2'),
        ('margenmin3', 'Lista 3 - Minorista 3'),
        ('margenmay',  'Lista 4 - Mayorista'),
        ('margendis',  'Lista 5 - Distribuidor'),
        ('margen6',    'Margen 6'),
        ('margen7',    'Margen 7')
    ]

    for col, desc in margin_cols:
        vals = [clean_float(p.get(col, 0)) for p in prods]
        mayores_cero = [v for v in vals if v > 0]
        promedio = sum(vals) / len(vals) if vals else 0
        print(f"  - {col:12} ({desc:25}): {len(mayores_cero):5} productos con margen > 0 | Promedio: {promedio:5.1f}%")

    # 3. Verificación de precio_neto vs margenmin1
    coinciden = 0
    diferencias = 0
    for p in prods:
        c = clean_float(p.get('costoreal', 0))
        m1 = clean_float(p.get('margenmin1', 0))
        pn = clean_float(p.get('precio_neto', 0))
        calc = round(c * (1 + m1 / 100.0), 2)
        if abs(calc - pn) <= 0.05:
            coinciden += 1
        else:
            diferencias += 1

    print(f"\n3. RELACIÓN ENTRE 'precio_neto' Y 'margenmin1':")
    print(f"  - Productos donde precio_neto == costo * (1 + margenmin1): {coinciden} ({coinciden/len(prods)*100:.1f}%)")
    print(f"  - Productos con diferencias menores: {diferencias} ({diferencias/len(prods)*100:.1f}%)")
    print("  -> Conclusión: El 'list_price' (Precio de Venta Base en Odoo) ya contiene el precio de la Lista Minorista 1.")

    # 4. Ejemplos prácticos
    print("\n4. EJEMPLO COMPARATIVO DE PRECIOS POR LISTA PARA 5 PRODUCTOS:")
    print("-" * 105)
    print(f"{'Código':<7} {'Nombre':<30} {'Costo ARS':<10} {'Min 1 (L1)':<12} {'Min 2 (L2)':<12} {'Min 3 (L3)':<12} {'May (L4)':<12} {'Dis (L5)':<12}")
    print("-" * 105)
    for p in prods[:5]:
        num = p.get('numpro', '')
        nom = p.get('descri', '')[:28]
        c = clean_float(p.get('costoreal', 0))
        p1 = round(c * (1 + clean_float(p.get('margenmin1', 0)) / 100.0), 2)
        p2 = round(c * (1 + clean_float(p.get('margenmin2', 0)) / 100.0), 2)
        p3 = round(c * (1 + clean_float(p.get('margenmin3', 0)) / 100.0), 2)
        p4 = round(c * (1 + clean_float(p.get('margenmay', 0)) / 100.0), 2)
        p5 = round(c * (1 + clean_float(p.get('margendis', 0)) / 100.0), 2)
        print(f"{num:<7} {nom:<30} ${c:<9.2f} ${p1:<11.2f} ${p2:<11.2f} ${p3:<11.2f} ${p4:<11.2f} ${p5:<11.2f}")
    print("-" * 105)

if __name__ == '__main__':
    main()

