# -*- coding: utf-8 -*-
"""
================================================================================
PASO 1: PREPARACIÓN DE LISTAS DE PRECIOS BASADAS EN COSTO + % MARGEN Y DESGLOSE
Carpeta limpia: v2_listas_y_desglose
================================================================================

Mapeo exacto según las pantallas del sistema anterior ("Análisis de Precio"):
1. Publico (Predeterminada) -> Columna 'margenmin1' (% sobre Costo Neto)
2. Mayorista                -> Columna 'margenmin2' (% sobre Costo Neto)
3. 30 Dias                  -> Columna 'margenmin3' (% sobre Costo Neto)
4. Licitacion               -> Columna 'margenmay'  (% sobre Costo Neto)
5. Lista 5                  -> Columna 'margendis'  (% sobre Costo Neto)
6. Lista 6                  -> Columna 'margen6'    (% sobre Costo Neto)
7. Desglose (Por Unidad)    -> Columna 'margen7' dividida por 'uni_bulto' (cuando desglose == '1')
8. Lista en Dólares (USD)   -> Para productos con moneda == 'D'
"""

import os
import json
import zipfile
import xml.etree.ElementTree as ET

EXCEL_FILE = os.path.join("..", "Sistema Cristian 27-10 kiddie.xlsx")
if not os.path.exists(EXCEL_FILE):
    EXCEL_FILE = "Sistema Cristian 27-10 kiddie.xlsx"

OUTPUT_JSON = os.path.join(os.path.dirname(__file__), "listas_por_margen_y_desglose.json")
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
    print("=" * 80)
    print("PREPARANDO REGLAS DE LISTAS DE PRECIOS (% SOBRE COSTO + DESGLOSE)")
    print(f"Archivo origen: {EXCEL_FILE}")
    print("=" * 80)

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

        prods = []
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
            prods.append(row_dict)

    # Estructura de listas tal cual la ventana "Análisis de Precio" del cliente
    listas = {
        'publico': {
            'nombre': 'Público (ARS)',
            'moneda': 'ARS',
            'es_predeterminada': True,
            'columna_margen': 'margenmin1',
            'items': []
        },
        'mayorista': {
            'nombre': 'Mayorista (ARS)',
            'moneda': 'ARS',
            'es_predeterminada': False,
            'columna_margen': 'margenmin2',
            'items': []
        },
        '30_dias': {
            'nombre': '30 Días (ARS)',
            'moneda': 'ARS',
            'es_predeterminada': False,
            'columna_margen': 'margenmin3',
            'items': []
        },
        'licitacion': {
            'nombre': 'Licitación (ARS)',
            'moneda': 'ARS',
            'es_predeterminada': False,
            'columna_margen': 'margenmay',
            'items': []
        },
        'lista_5': {
            'nombre': 'Lista 5 (ARS)',
            'moneda': 'ARS',
            'es_predeterminada': False,
            'columna_margen': 'margendis',
            'items': []
        },
        'lista_6': {
            'nombre': 'Lista 6 (ARS)',
            'moneda': 'ARS',
            'es_predeterminada': False,
            'columna_margen': 'margen6',
            'items': []
        },
        'desglose': {
            'nombre': 'Desglose - Venta por Unidad (ARS)',
            'moneda': 'ARS',
            'es_predeterminada': False,
            'columna_margen': 'margen7',
            'items': []
        },
        'dolares': {
            'nombre': 'Lista en Dólares (USD)',
            'moneda': 'USD',
            'es_predeterminada': False,
            'columna_margen': 'margenmin1',
            'items': []
        }
    }

    for p in prods:
        numpro = p.get('numpro', '')
        costo = clean_float(p.get('costoreal', 0))
        pn = clean_float(p.get('precio_neto', 0))

        # 1 a 6: Listas por % de margen sobre el costo (base = 'standard_price')
        # En Odoo: price = standard_price * (1 - price_discount / 100)
        # Por lo tanto, para sumar +85% de margen, price_discount = -85.0
        for key in ['publico', 'mayorista', '30_dias', 'licitacion', 'lista_5', 'lista_6']:
            col = listas[key]['columna_margen']
            margen = clean_float(p.get(col, 0))
            if key == 'lista_6' and margen <= 0:
                continue
            listas[key]['items'].append({
                'default_code': numpro,
                'margen_porcentaje': margen,
                'price_discount': round(-margen, 4),
                'precio_calculado_ref': round(costo * (1 + margen / 100.0), 2)
            })

        # 7: Desglose (cuando desglose == '1')
        if p.get('desglose', '0') == '1':
            uni_bulto = clean_float(p.get('uni_bulto', 1), default=1.0)
            if uni_bulto <= 0:
                uni_bulto = 1.0
            margen_desg = clean_float(p.get('margen7', 0))
            # Precio Unidad = Costo_Bulto * ((1 + margen7/100) / uni_bulto)
            factor = (1.0 + (margen_desg / 100.0)) / uni_bulto
            # Equivalente en price_discount de Odoo: 1 - (price_discount / 100) = factor => price_discount = (1 - factor) * 100
            discount_odoo = round((1.0 - factor) * 100.0, 6)
            precio_unitario_ref = round(costo * factor, 2)

            listas['desglose']['items'].append({
                'default_code': numpro,
                'uni_bulto': uni_bulto,
                'margen_desglose': margen_desg,
                'price_discount': discount_odoo,
                'precio_fijo': precio_unitario_ref
            })

        # 8: Dólares
        if p.get('moneda', '') == 'D':
            vd = clean_float(p.get('valdolar', 0))
            cd = clean_float(p.get('cosdol', 0))
            m1 = clean_float(p.get('margenmin1', 0))
            p_usd = round(pn / vd, 2) if vd > 0 else round(cd * (1 + m1 / 100.0), 2)
            if p_usd > 0:
                listas['dolares']['items'].append({
                    'default_code': numpro,
                    'precio_usd': p_usd
                })

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(listas, f, indent=2, ensure_ascii=False)

    print("\nRESUMEN DE LISTAS GENERADAS EN:", OUTPUT_JSON)
    for k, v in listas.items():
        print(f"  - {v['nombre']:<38} | Reglas generadas: {len(v['items'])}")

    # Verificación contra las capturas de pantalla del usuario
    print("\nVERIFICACIÓN CONTRA LAS CAPTURAS DEL SISTEMA VIEJO:")
    for test_code in ['37324', '38081', '36673']:
        p_match = next((x for x in prods if x.get('numpro') == test_code), None)
        if p_match:
            c = clean_float(p_match.get('costoreal', 0))
            ub = clean_float(p_match.get('uni_bulto', 1), 1.0)
            m1 = clean_float(p_match.get('margenmin1', 0))
            m2 = clean_float(p_match.get('margenmin2', 0))
            m3 = clean_float(p_match.get('margenmin3', 0))
            m4 = clean_float(p_match.get('margenmay', 0))
            m5 = clean_float(p_match.get('margendis', 0))
            m7 = clean_float(p_match.get('margen7', 0))
            desg_val = round((c / ub) * (1 + m7 / 100.0), 2) if p_match.get('desglose') == '1' else 0.0
            print(f"  * [{test_code}] {p_match.get('descri')} (Costo Neto: ${c:.3f}, Bulto: {int(ub)} u.)")
            print(f"      Público ({m1}%): ${c*(1+m1/100):.2f} | Mayorista ({m2}%): ${c*(1+m2/100):.2f} | 30 Días ({m3}%): ${c*(1+m3/100):.2f}")
            print(f"      Licitación ({m4}%): ${c*(1+m4/100):.2f} | Lista 5 ({m5}%): ${c*(1+m5/100):.2f} | Desglose ({m7}%): ${desg_val:.2f}")

if __name__ == '__main__':
    main()
