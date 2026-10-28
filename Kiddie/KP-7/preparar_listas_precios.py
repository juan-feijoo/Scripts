# -*- coding: utf-8 -*-
"""
Cálculo y preparación de Listas de Precios para Odoo Enterprise (17e/18e/19e).
Genera 'listas_precios_preparadas.json' para alimentar el script de Odoo Shell.
"""

import os
import json
import zipfile
import xml.etree.ElementTree as ET

EXCEL_FILE = "Sistema Cristian 27-10 kiddie.xlsx"
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

def main():
    print("Extrayendo datos de precios y márgenes desde el Excel...")
    with zipfile.ZipFile(EXCEL_FILE) as z:
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

        sheet_root = ET.fromstring(z.read('xl/worksheets/sheet3.xml'))
        rows = sheet_root.findall('.//s:row', NS)
        headers = [c.find('s:v', NS).text if c.find('s:v', NS) is not None else '' for c in rows[0].findall('s:c', NS)]
        headers = [shared_strings[int(h)] if h.isdigit() and int(h) < len(shared_strings) else h for h in headers]

        parsed = []
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
            parsed.append(row_dict)

    print(f"Total productos leídos: {len(parsed)}")

    # 1. Analizar productos en Dólares (USD)
    usd_items = []
    lista_may_items = []  # Mayorista (Lista 4)
    lista_min2_items = [] # Minorista 2 (Lista 2)
    lista_dis_items = []  # Distribuidor (Lista 5)

    for p in parsed:
        numpro = p.get('numpro', '')
        descri = p.get('descri', '')
        moneda = p.get('moneda', '')
        costo = clean_float(p.get('costoreal', 0))
        pn = clean_float(p.get('precio_neto', 0))
        vd = clean_float(p.get('valdolar', 0))
        cd = clean_float(p.get('cosdol', 0))
        m1 = clean_float(p.get('margenmin1', 0))
        m2 = clean_float(p.get('margenmin2', 0))
        m_may = clean_float(p.get('margenmay', 0))
        m_dis = clean_float(p.get('margendis', 0))

        # A. Si el producto es en Dólares
        if moneda == 'D':
            # Precio venta en USD: si valdolar existe, pn / valdolar; si no, cosdol * (1 + m1/100)
            if vd > 0:
                p_usd = round(pn / vd, 2)
            else:
                p_usd = round(cd * (1 + m1 / 100.0), 2)

            usd_items.append({
                'default_code': numpro,
                'name': descri,
                'costo_usd': cd,
                'precio_usd': p_usd,
                'valdolar': vd,
                'precio_neto_ars': pn
            })

        # B. Lista Mayorista (margenmay)
        p_may = round(costo * (1 + m_may / 100.0), 2)
        if p_may != pn and p_may > 0:
            lista_may_items.append({
                'default_code': numpro,
                'margen': m_may,
                'precio_fijo': p_may
            })

        # C. Lista Minorista 2 (margenmin2)
        p_min2 = round(costo * (1 + m2 / 100.0), 2)
        if p_min2 != pn and p_min2 > 0:
            lista_min2_items.append({
                'default_code': numpro,
                'margen': m2,
                'precio_fijo': p_min2
            })

    output_data = {
        'resumen': {
            'total_productos': len(parsed),
            'total_usd_items': len(usd_items),
            'total_mayorista_items': len(lista_may_items),
            'total_minorista2_items': len(lista_min2_items)
        },
        'lista_usd': {
            'nombre': 'Lista de Precios en Dólares (USD)',
            'moneda': 'USD',
            'items': usd_items
        },
        'lista_mayorista': {
            'nombre': 'Lista Mayorista (ARS)',
            'moneda': 'ARS',
            'items': lista_may_items
        },
        'lista_minorista_2': {
            'nombre': 'Lista Minorista 2 (ARS)',
            'moneda': 'ARS',
            'items': lista_min2_items
        }
    }

    with open('listas_precios_preparadas.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print("EXTRACCIÓN DE LISTAS DE PRECIOS COMPLETADA:")
    print(f"- Productos con precio en Dólares (USD): {len(usd_items)}")
    print(f"- Productos con precio Mayorista diferenciado: {len(lista_may_items)}")
    print(f"- Productos con precio Minorista 2 diferenciado: {len(lista_min2_items)}")
    print("Archivo generado: listas_precios_preparadas.json")
    print("=" * 60)

if __name__ == '__main__':
    main()
