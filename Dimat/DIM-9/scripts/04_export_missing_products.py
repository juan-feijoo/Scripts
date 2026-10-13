# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT 04: IDENTIFICAR Y EXPORTAR PRODUCTOS DEL EXCEL QUE NO ESTÁN EN ODOO
================================================================================
Entorno: Odoo 17.0+e / 18.0+e / 19.0+e (Odoo Shell - Read Only)
Genera:
    1. Reporte detallado en consola.
    2. Archivo CSV ('productos_no_encontrados_en_odoo.csv') con codificación UTF-8 BOM
       y delimitador ';' listo para abrir directamente en Microsoft Excel.
    3. Archivo JSON ('productos_no_encontrados_en_odoo.json').

Uso en Odoo Shell:
    python3 odoo-bin shell -d <nombre_bd> < scripts/04_export_missing_products.py
    o pegar directamente en la shell interactiva.
================================================================================
"""
import os
import csv
import json
from collections import Counter

# Rutas posibles del archivo JSON de origen
POSSIBLE_PATHS = [
    "scripts/precios_procesados.json",
    "precios_procesados.json",
    os.path.join(os.path.dirname(__file__) if "__file__" in locals() else ".", "precios_procesados.json"),
    os.path.join(os.path.dirname(__file__) if "__file__" in locals() else ".", "scripts", "precios_procesados.json"),
]

json_file = None
for p in POSSIBLE_PATHS:
    if os.path.exists(p):
        json_file = p
        break

if not json_file:
    raise FileNotFoundError(
        f"No se encontró 'precios_procesados.json'. Rutas buscadas: {POSSIBLE_PATHS}"
    )

with open(json_file, "r", encoding="utf-8") as f:
    items_data = json.load(f)

print("\n" + "="*80)
print(" AUDITORÍA DE PRODUCTOS FALTANTES: EXCEL VS ODOO ".center(80, "="))
print("="*80)
print(f"[*] Registros analizados en el archivo: {len(items_data)}")

# ==============================================================================
# 1. BÚSQUEDA Y MATCHING EN ODOO (BATCH)
# ==============================================================================
print("[*] Verificando existencia en la base de datos de Odoo...")

all_codes = list({item['code'].strip() for item in items_data if item.get('code')})

# 1.1 Match directo por default_code en product.product
products = env['product.product'].search([('default_code', 'in', all_codes)])
found_codes = {p.default_code.strip() for p in products if p.default_code}

# 1.2 Fallback en product.template
missing_codes = [c for c in all_codes if c not in found_codes]
if missing_codes:
    templates = env['product.template'].search([('default_code', 'in', missing_codes)])
    for t in templates:
        if t.default_code:
            found_codes.add(t.default_code.strip())

# 1.3 Fallback limpieza de puntos finales (ej. '88800000000059.')
missing_codes = [c for c in all_codes if c not in found_codes]
dot_mapping = {c: c.rstrip('.').strip() for c in missing_codes if c.endswith('.')}
if dot_mapping:
    clean_prods = env['product.product'].search([('default_code', 'in', list(dot_mapping.values()))])
    clean_set = {p.default_code.strip() for p in clean_prods if p.default_code}
    for orig_code, clean_code in dot_mapping.items():
        if clean_code in clean_set:
            found_codes.add(orig_code)

# 1.4 Fallback por código de barras (barcode)
missing_codes = [c for c in all_codes if c not in found_codes]
if missing_codes:
    barcode_prods = env['product.product'].search([('barcode', 'in', missing_codes)])
    for p in barcode_prods:
        if p.barcode and p.barcode in missing_codes:
            found_codes.add(p.barcode)

# 1.5 Fallback por coincidencia de nombre exacto
missing_items_temp = [item for item in items_data if item['code'].strip() not in found_codes]
for m in missing_items_temp:
    name_clean = m['name'].strip()
    if name_clean:
        p_by_name = env['product.product'].search([('name', '=ilike', name_clean)], limit=1)
        if p_by_name:
            found_codes.add(m['code'].strip())

# ==============================================================================
# 2. IDENTIFICAR LOS PRODUCTOS NO ENCONTRADOS
# ==============================================================================
missing_products = []
for item in items_data:
    code = item['code'].strip()
    if code not in found_codes:
        missing_products.append(item)

print(f"\n[+] Total productos presentes en Odoo:     {len(found_codes)}")
print(f"[-] Total productos NO encontrados en Odoo: {len(missing_products)}")

# ==============================================================================
# 3. EXPORTAR A CSV (UTF-8 con BOM y ';' para Excel)
# ==============================================================================
output_dir = os.path.dirname(json_file) or "."
csv_filename = os.path.join(output_dir, "productos_no_encontrados_en_odoo.csv")
json_filename = os.path.join(output_dir, "productos_no_encontrados_en_odoo.json")

fieldnames = [
    'Codigo_Excel',
    'Descripcion',
    'Marca',
    'Moneda',
    'Importe_Reposicion',
    'Importe_Ultima_Compra',
    'Etiqueta'
]

with open(csv_filename, mode='w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f, delimiter=';')
    writer.writerow(fieldnames)
    for row in missing_products:
        writer.writerow([
            row.get('code', ''),
            row.get('name', ''),
            row.get('brand', ''),
            row.get('currency', ''),
            f"{row.get('price_reposicion', 0):.2f}".replace('.', ','),
            f"{row.get('price_ultima_compra', 0):.2f}".replace('.', ','),
            row.get('tag', '')
        ])

with open(json_filename, mode='w', encoding='utf-8') as f:
    json.dump(missing_products, f, ensure_ascii=False, indent=2)

print(f"\n[*] Archivos generados con éxito:")
print(f"    - CSV:  {csv_filename}")
print(f"    - JSON: {json_filename}")

# ==============================================================================
# 4. RESUMEN ESTADÍSTICO DE FALTANTES
# ==============================================================================
print("\n" + "="*80)
print(" RESUMEN DE ARTÍCULOS NO ENCONTRADOS ".center(80, "="))
print("="*80)

tags_counter = Counter([p.get('tag', 'Sin etiqueta') for p in missing_products])
print("\n[*] Distribución por Etiqueta / Rubro:")
for tag, count in tags_counter.most_common():
    print(f"    - {tag:<30}: {count} artículos")

currencies_counter = Counter([p.get('currency', 'ARS') for p in missing_products])
print(f"\n[*] Distribución por Moneda: {dict(currencies_counter)}")

print("\n[*] Primeros 15 artículos no encontrados:")
print(f"    {'Código':<18} | {'Moneda':<6} | {'Reposición':<12} | {'Descripción':<35}")
print("    " + "-"*75)
for p in missing_products[:15]:
    price_str = f"{p.get('price_reposicion', 0):,.2f}"
    print(f"    {p.get('code', ''):<18} | {p.get('currency', ''):<6} | {price_str:<12} | {p.get('name', '')[:35]}")

if len(missing_products) > 15:
    print(f"    ... y {len(missing_products) - 15} artículos más (ver archivo CSV).")

print("\n" + "="*80)
