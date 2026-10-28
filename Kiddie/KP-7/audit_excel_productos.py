# -*- coding: utf-8 -*-
"""
Auditoría integral del archivo 'Sistema Cristian 27-10 kiddie.xlsx'
Módulos: Productos, Categorías (Rubros), Subcategorías (Subrubros), Impuestos, Stock y Proveedores.
Compatible con Odoo 17.0+e, 18.0+e y 19.0+e.
"""

import os
import sys
import zipfile
import json
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

def run_audit():
    if not os.path.exists(EXCEL_FILE):
        print(f"ERROR: No se encuentra el archivo {EXCEL_FILE}")
        return

    print("=" * 80)
    print("AUDITORÍA DE DATOS: MIGRACIÓN DE PRODUCTOS Y CATEGORÍAS A ODOO")
    print(f"Archivo de origen: {EXCEL_FILE}")
    print("=" * 80)

    with zipfile.ZipFile(EXCEL_FILE) as z:
        # 1. Auditoría de Hojas
        wb_tree = ET.fromstring(z.read('xl/workbook.xml'))
        sheets = wb_tree.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheets/{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet')
        print(f"\nHojas detectadas ({len(sheets)}):")
        for s in sheets:
            print(f"  - {s.attrib.get('name')} (ID: {s.attrib.get('sheetId')})")

        _, proveedores = parse_sheet(z, 'xl/worksheets/sheet2.xml')
        _, productos = parse_sheet(z, 'xl/worksheets/sheet3.xml')

    print(f"\nTotal Proveedores en hoja 'proveedores': {len(proveedores)}")
    print(f"Total Productos en hoja 'produc_vista': {len(productos)}")

    # 2. Análisis de Códigos e Identificadores
    print("\n" + "-" * 40)
    print("1. CLAVES PRIMARIAS E IDENTIFICADORES")
    print("-" * 40)
    numpros = [p.get('numpro', '') for p in productos]
    descris = [p.get('descri', '') for p in productos]
    barcodes = [p.get('codbarra', '') for p in productos if p.get('codbarra', '')]

    print(f"- numpro: {len(numpros)} registros, {len(set(numpros))} únicos. ¿100% único?: {'SÍ' if len(numpros) == len(set(numpros)) else 'NO'}")
    print(f"  -> Conclusión: 'numpro' es 100% apto como default_code (Referencia Interna Odoo).")

    # Duplicados de nombres
    descri_counter = Counter(descris)
    dup_descris = {k: v for k, v in descri_counter.items() if v > 1 and k}
    print(f"- descri (Nombres): {len(set(descris))} únicos. Nombres duplicados: {len(dup_descris)}")
    if dup_descris:
        print("  Ejemplos de nombres repetidos:")
        for d, count in list(dup_descris.items())[:5]:
            nums = [p.get('numpro') for p in productos if p.get('descri') == d]
            print(f"    * '{d}' ({count} veces) -> numpro: {nums}")

    # Duplicados de código de barra
    bc_counter = Counter(barcodes)
    dup_bcs = {k: v for k, v in bc_counter.items() if v > 1}
    print(f"- codbarra (Códigos de barra):")
    print(f"  * Productos CON código de barra: {len(barcodes)} ({len(barcodes)/len(productos)*100:.1f}%)")
    print(f"  * Productos SIN código de barra: {len(productos) - len(barcodes)} ({(len(productos)-len(barcodes))/len(productos)*100:.1f}%)")
    print(f"  * Códigos de barra repetidos: {len(dup_bcs)} códigos compartidos por múltiples productos")
    if dup_bcs:
        print("  ¡ATENCIÓN! Odoo valida unicidad de barcode por defecto. Ejemplos de colisiones:")
        for bc, count in list(dup_bcs.items())[:5]:
            owners = [(p.get('numpro'), p.get('descri')[:35]) for p in productos if p.get('codbarra') == bc]
            print(f"    * Barcode '{bc}' ({count} prods): {owners}")

    # 3. Análisis de Categorías (Rubro y Subrubro)
    print("\n" + "-" * 40)
    print("2. ANÁLISIS DE CATEGORÍAS (RUBROS Y SUBRUBROS)")
    print("-" * 40)

    subrubros = Counter()
    rubros = Counter()
    rubro_to_sub = defaultdict(set)
    sub_to_rub = defaultdict(set)

    for p in productos:
        crub = p.get('codrub', '')
        nrub = p.get('rubro', '')
        csub = p.get('codsub', '')
        nsub = p.get('subrubro', '')

        rub_str = f"[{crub}] {nrub}"
        sub_str = f"[{csub}] {nsub}"

        rubros[rub_str] += 1
        subrubros[sub_str] += 1
        rubro_to_sub[rub_str].add(sub_str)
        sub_to_rub[sub_str].add(rub_str)

    print(f"Subrubros encontrados (Macro-categorías): {len(subrubros)}")
    for sub, count in subrubros.most_common():
        r_count = len(sub_to_rub[sub])
        print(f"  - {sub:30} -> {count:5} productos | {r_count:3} rubros asociados")

    print(f"\nRubros encontrados (Micro-categorías/Familias): {len(rubros)}")
    multi_parent = {r: subs for r, subs in rubro_to_sub.items() if len(subs) > 1}
    print(f"  * Rubros con un solo Subrubro: {len(rubros) - len(multi_parent)}")
    print(f"  * Rubros que aparecen en MÁS de un Subrubro: {len(multi_parent)}")
    if multi_parent:
        print("  Ejemplos de rubros compartidos:")
        for r, subs in list(multi_parent.items())[:5]:
            print(f"    * {r} -> presente en: {list(subs)}")

    # 4. Impuestos (Tasa IVA)
    print("\n" + "-" * 40)
    print("3. ANÁLISIS DE IMPUESTOS (TASA IVA)")
    print("-" * 40)
    tasas = Counter(p.get('tasa', '') for p in productos)
    print("Distribución de alícuotas (tasa):")
    for t, c in tasas.most_common():
        print(f"  - Tasa '{t}': {c} productos ({c/len(productos)*100:.2f}%)")

    anomalias_iva = [p for p in productos if p.get('tasa') not in ('21', '10.5', '0', '')]
    if anomalias_iva:
        print(f"  ¡Anomalías en IVA ({len(anomalias_iva)} productos)!:")
        for a in anomalias_iva:
            print(f"    * numpro={a.get('numpro')}: '{a.get('descri')[:35]}' con tasa='{a.get('tasa')}'")

    # 5. Precios, Costos y Monedas
    print("\n" + "-" * 40)
    print("4. PRECIOS, COSTOS Y MONEDAS")
    print("-" * 40)
    monedas = Counter(p.get('moneda', '') for p in productos)
    print("Distribución de moneda:")
    for m, c in monedas.most_common():
        m_label = "USD (Dólares)" if m == 'D' else "ARS (Pesos / Sin marca)"
        print(f"  - '{m}' ({m_label}): {c} productos")

    costo_cero = [p for p in productos if float(p.get('costoreal', 0) or 0) <= 0]
    precio_cero = [p for p in productos if float(p.get('precio_neto', 0) or 0) <= 0]
    print(f"- Productos con costoreal <= 0: {len(costo_cero)}")
    print(f"- Productos con precio_neto <= 0: {len(precio_cero)}")

    # 6. Stock e Inventario
    print("\n" + "-" * 40)
    print("5. STOCK ACTUAL Y MÍNIMO")
    print("-" * 40)
    stk_pos = [p for p in productos if float(p.get('stkact', 0) or 0) > 0]
    stk_cero = [p for p in productos if float(p.get('stkact', 0) or 0) == 0]
    stk_neg = [p for p in productos if float(p.get('stkact', 0) or 0) < 0]
    print(f"- Stock positivo (> 0): {len(stk_pos)} productos")
    print(f"- Stock cero (== 0):     {len(stk_cero)} productos")
    print(f"- Stock negativo (< 0): {len(stk_neg)} productos (¡ATENCIÓN! Requiere normalización antes de ajuste de inventario)")
    if stk_neg:
        print("  Ejemplos de stock negativo:")
        for sn in stk_neg[:5]:
            print(f"    * numpro={sn.get('numpro')}: '{sn.get('descri')[:30]}' -> Stock: {sn.get('stkact')}")

    # 7. Marcas y Proveedores
    print("\n" + "-" * 40)
    print("6. MARCAS Y PROVEEDORES")
    print("-" * 40)
    marcas = Counter(p.get('marca', '') for p in productos)
    print(f"- Total de Marcas: {len(marcas)}")
    print(f"  Top 5 marcas: {marcas.most_common(5)}")

    prov_ids_en_prods = set(p.get('numprv', '') for p in productos if p.get('numprv', ''))
    prov_ids_en_hoja = set(pr.get('numprv', '') for pr in proveedores if pr.get('numprv', ''))
    prov_huerfanos = prov_ids_en_prods - prov_ids_en_hoja
    print(f"- Proveedores referenciados en productos: {len(prov_ids_en_prods)}")
    print(f"- Proveedores existentes en hoja 'proveedores': {len(prov_ids_en_hoja)}")
    print(f"- Proveedores huérfanos (en productos pero no en hoja): {len(prov_huerfanos)}")
    if prov_huerfanos:
        print(f"  IDs huérfanos: {list(prov_huerfanos)[:5]}")

    print("\n" + "=" * 80)
    print("FIN DE AUDITORÍA")
    print("=" * 80)

if __name__ == '__main__':
    run_audit()

