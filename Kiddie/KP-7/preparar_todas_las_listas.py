# -*- coding: utf-8 -*-
"""
Preparación de todas las Listas de Precios de Kiddie:
- Lista 1: Minorista 1 (ARS) - 6.935 productos (precio_neto)
- Lista 2: Minorista 2 (ARS) - 6.887 productos (margenmin2)
- Lista 3: Minorista 3 (ARS) - 6.890 productos (margenmin3)
- Lista 4: Mayorista (ARS)   - 6.870 productos (margenmay)
- Lista 5: Distribuidor (ARS)- 5.604 productos (margendis)
- Lista USD: Dólares (USD)   - 972 productos (precio USD)
"""

import json
import zipfile
import xml.etree.ElementTree as ET

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

def main():
    print("Leyendo Excel...")
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

    print(f"Total productos: {len(parsed)}")

    listas_data = {
        'lista_min1': {
            'nombre': 'Lista 1 - Minorista 1 (Predeterminada ARS)',
            'moneda': 'ARS',
            'es_predeterminada': True,
            'items': []
        },
        'lista_min2': {
            'nombre': 'Lista 2 - Minorista 2 (ARS)',
            'moneda': 'ARS',
            'es_predeterminada': False,
            'items': []
        },
        'lista_may': {
            'nombre': 'Lista 4 - Mayorista (ARS)',
            'moneda': 'ARS',
            'es_predeterminada': False,
            'items': []
        },
        'lista_min3': {
            'nombre': 'Lista 3 - Minorista 3 (ARS)',
            'moneda': 'ARS',
            'es_predeterminada': False,
            'items': []
        },
        'lista_usd': {
            'nombre': 'Lista de Precios en Dólares (USD)',
            'moneda': 'USD',
            'es_predeterminada': False,
            'items': []
        }
    }

    for p in parsed:
        numpro = p.get('numpro', '')
        c = clean_float(p.get('costoreal', 0))
        pn = clean_float(p.get('precio_neto', 0))
        m1 = clean_float(p.get('margenmin1', 0))
        m2 = clean_float(p.get('margenmin2', 0))
        m3 = clean_float(p.get('margenmin3', 0))
        may = clean_float(p.get('margenmay', 0))
        moneda = p.get('moneda', '')
        vd = clean_float(p.get('valdolar', 0))
        cd = clean_float(p.get('cosdol', 0))

        # Lista 1: Minorista 1
        p1 = pn if pn > 0 else round(c * (1 + m1 / 100.0), 2)
        if p1 > 0:
            listas_data['lista_min1']['items'].append({'default_code': numpro, 'precio': p1})

        # Lista 2: Minorista 2
        p2 = round(c * (1 + m2 / 100.0), 2)
        if p2 > 0:
            listas_data['lista_min2']['items'].append({'default_code': numpro, 'precio': p2})

        # Lista 4: Mayorista
        p_may = round(c * (1 + may / 100.0), 2)
        if p_may > 0:
            listas_data['lista_may']['items'].append({'default_code': numpro, 'precio': p_may})

        # Lista 3: Minorista 3
        p3 = round(c * (1 + m3 / 100.0), 2)
        if p3 > 0:
            listas_data['lista_min3']['items'].append({'default_code': numpro, 'precio': p3})

        # Lista USD
        if moneda == 'D':
            p_usd = round(pn / vd, 2) if vd > 0 else round(cd * (1 + m1 / 100.0), 2)
            if p_usd > 0:
                listas_data['lista_usd']['items'].append({'default_code': numpro, 'precio': p_usd})

    with open('todas_las_listas_preparadas.json', 'w', encoding='utf-8') as f:
        json.dump(listas_data, f, indent=2, ensure_ascii=False)

    print("\nRESUMEN DE LISTAS PREPARADAS:")
    for k, v in listas_data.items():
        print(f"  - {v['nombre']}: {len(v['items'])} productos con precio calculado.")
    print("Archivo generado: todas_las_listas_preparadas.json")

if __name__ == '__main__':
    main()

