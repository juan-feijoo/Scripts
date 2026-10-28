# -*- coding: utf-8 -*-
"""
Normalización y preparación de datos para Odoo 17e/18e/19e.
Genera 'productos_preparados.json' y 'categorias_preparadas.json' listos para Odoo Shell.
"""

import os
import re
import json
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

EXCEL_FILE = "Sistema Cristian 27-10 kiddie.xlsx"
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def col_to_idx(cell_ref):
    letters = ''.join([c for c in cell_ref if c.isalpha()])
    idx = 0
    for c in letters:
        idx = idx * 26 + (ord(c.upper()) - ord('A') + 1)
    return idx - 1

def sanitize_text(text):
    if not text:
        return ""
    # Remover caracteres de control invisibles comunes en exports antiguos
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    # Espacios duplicados y trim
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def parse_sheet(z, sheet_path):
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
    if not rows:
        return [], []
    
    headers = []
    first_row = rows[0]
    for c in first_row.findall('s:c', NS):
        v = c.find('s:v', NS)
        t_type = c.attrib.get('t')
        val = v.text if v is not None else ''
        if t_type == 's' and val.isdigit():
            val = shared_strings[int(val)]
        headers.append(val.strip())

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
    return headers, parsed

def clean_float(val, default=0.0):
    if not val:
        return default
    try:
        return float(str(val).replace(',', '.'))
    except (ValueError, TypeError):
        return default

def normalizar_tasa_iva(tasa_str):
    tasa_str = tasa_str.strip()
    if tasa_str == '10.4':
        return 10.5
    elif tasa_str == '2':
        return 21.0
    elif tasa_str in ('21', '21.0'):
        return 21.0
    elif tasa_str in ('10.5', '10'):
        return 10.5
    elif tasa_str in ('0', '0.0', ''):
        return 0.0
    try:
        f = float(tasa_str)
        if abs(f - 10.5) < 0.2:
            return 10.5
        if abs(f - 21.0) < 0.2:
            return 21.0
        return f
    except:
        return 21.0

def main():
    print("Leyendo archivo Excel...")
    with zipfile.ZipFile(EXCEL_FILE) as z:
        _, raw_proveedores = parse_sheet(z, 'xl/worksheets/sheet2.xml')
        _, raw_productos = parse_sheet(z, 'xl/worksheets/sheet3.xml')

    print(f"Total productos leídos: {len(raw_productos)}")
    print(f"Total proveedores leídos: {len(raw_proveedores)}")

    # 1. Normalizar Proveedores
    proveedores_dict = {}
    for prv in raw_proveedores:
        numprv = sanitize_text(prv.get('numprv', ''))
        if not numprv:
            continue
        proveedores_dict[numprv] = {
            'numprv': numprv,
            'nombre': sanitize_text(prv.get('nombre', '')),
            'domicilio': sanitize_text(prv.get('domicilio', '')),
            'localidad': sanitize_text(prv.get('localidad', '')),
            'provincia': sanitize_text(prv.get('provincia', '')),
            'codpos': sanitize_text(prv.get('codpos', '')),
            'telefono': sanitize_text(prv.get('telefono', '')),
            'tipiva': sanitize_text(prv.get('tipiva', '')),
            'cuit': sanitize_text(prv.get('numiva', '')),
            'email': sanitize_text(prv.get('e_mail', ''))
        }

    # 2. Análisis y control de Códigos de Barra duplicados
    barcode_counts = Counter()
    for p in raw_productos:
        bc = sanitize_text(p.get('codbarra', ''))
        if bc:
            barcode_counts[bc] += 1

    barcodes_duplicados = {bc for bc, count in barcode_counts.items() if count > 1}
    print(f"Códigos de barra duplicados detectados: {len(barcodes_duplicados)}")

    barcodes_usados = set()
    incidencias = []

    # 3. Normalizar Categorías y Productos
    categorias_padre = {}  # codsub -> nombre
    categorias_hijas = {}  # (codsub, codrub) -> dict
    productos_normalizados = []

    for p in raw_productos:
        numpro = sanitize_text(p.get('numpro', ''))
        descri = sanitize_text(p.get('descri', ''))
        csub = sanitize_text(p.get('codsub', '0'))
        nsub = sanitize_text(p.get('subrubro', '')) or 'S/SUBRUBROS'
        crub = sanitize_text(p.get('codrub', '0'))
        nrub = sanitize_text(p.get('rubro', '')) or 'VARIOS'

        # Ajuste de macro categoría
        parent_name = nsub if csub != '0' else 'GENERAL'
        if csub not in categorias_padre:
            categorias_padre[csub] = parent_name

        cat_key = (parent_name, nrub)
        if cat_key not in categorias_hijas:
            categorias_hijas[cat_key] = {
                'parent_name': parent_name,
                'name': nrub,
                'codrub': crub,
                'codsub': csub,
                'full_path': f"{parent_name} / {nrub}"
            }

        # Control de código de barra
        raw_bc = sanitize_text(p.get('codbarra', ''))
        assigned_bc = ""
        is_dup_bc = False
        if raw_bc:
            if raw_bc in barcodes_usados:
                is_dup_bc = True
                incidencias.append({
                    'tipo': 'BARCODE_DUPLICADO_IGNORADO',
                    'numpro': numpro,
                    'descri': descri,
                    'barcode': raw_bc,
                    'detalle': 'Se omitió el barcode porque ya fue asignado a otro producto previamente.'
                })
            else:
                assigned_bc = raw_bc
                barcodes_usados.add(raw_bc)

        tasa_original = p.get('tasa', '')
        tasa_normalizada = normalizar_tasa_iva(tasa_original)
        if str(tasa_original).strip() in ('10.4', '2'):
            incidencias.append({
                'tipo': 'IVA_CORREGIDO',
                'numpro': numpro,
                'descri': descri,
                'tasa_original': tasa_original,
                'tasa_normalizada': tasa_normalizada
            })

        stkact = clean_float(p.get('stkact', 0))
        if stkact < 0:
            incidencias.append({
                'tipo': 'STOCK_NEGATIVO_ORIGEN',
                'numpro': numpro,
                'descri': descri,
                'stock_actual': stkact
            })

        prod_dict = {
            'default_code': numpro,
            'name': descri,
            'category_parent': parent_name,
            'category_name': nrub,
            'category_full_path': f"{parent_name} / {nrub}",
            'barcode': assigned_bc,
            'barcode_original': raw_bc,
            'barcode_duplicado': is_dup_bc,
            'list_price': clean_float(p.get('precio_neto', 0)),
            'list_price_con_iva': clean_float(p.get('precio', 0)),
            'standard_price': clean_float(p.get('costoreal', 0)),
            'cosdol': clean_float(p.get('cosdol', 0)),
            'moneda_origen': 'USD' if p.get('moneda', '').strip() == 'D' else 'ARS',
            'tasa_iva': tasa_normalizada,
            'stkact': stkact,
            'stkmin': clean_float(p.get('stkmin', 0)),
            'marca': sanitize_text(p.get('marca', '')),
            'numprv': sanitize_text(p.get('numprv', '')),
            'nomprv': sanitize_text(p.get('nomprv', '')),
            'codartpro': sanitize_text(p.get('codartpro', '')),
            'uni_compra': clean_float(p.get('uni_compra', 1), default=1.0),
            'uni_venta': clean_float(p.get('uni_venta', 1), default=1.0),
            'uni_bulto': clean_float(p.get('uni_bulto', 1), default=1.0),
            'inactivo': sanitize_text(p.get('inactivo', '0')) == '1'
        }
        productos_normalizados.append(prod_dict)

    # 4. Guardar archivos normalizados
    with open('categorias_preparadas.json', 'w', encoding='utf-8') as f:
        json.dump({
            'padres': list(set(categorias_padre.values())),
            'hijas': list(categorias_hijas.values())
        }, f, indent=2, ensure_ascii=False)

    with open('proveedores_preparados.json', 'w', encoding='utf-8') as f:
        json.dump(list(proveedores_dict.values()), f, indent=2, ensure_ascii=False)

    with open('productos_preparados.json', 'w', encoding='utf-8') as f:
        json.dump(productos_normalizados, f, indent=2, ensure_ascii=False)

    with open('reporte_incidencias.json', 'w', encoding='utf-8') as f:
        json.dump(incidencias, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("PROCESO DE PREPARACIÓN COMPLETADO CON ÉXITO")
    print(f"- Categorías padre generadas: {len(set(categorias_padre.values()))}")
    print(f"- Categorías hijas generadas: {len(categorias_hijas)}")
    print(f"- Proveedores normalizados:   {len(proveedores_dict)}")
    print(f"- Productos normalizados:     {len(productos_normalizados)}")
    print(f"- Total Incidencias auditadas: {len(incidencias)}")
    print("  * Barcodes duplicados omitidos: ", sum(1 for i in incidencias if i['tipo'] == 'BARCODE_DUPLICADO_IGNORADO'))
    print("  * Tasas de IVA corregidas:     ", sum(1 for i in incidencias if i['tipo'] == 'IVA_CORREGIDO'))
    print("  * Productos con stock negativo: ", sum(1 for i in incidencias if i['tipo'] == 'STOCK_NEGATIVO_ORIGEN'))
    print("=" * 60)

if __name__ == '__main__':
    main()

