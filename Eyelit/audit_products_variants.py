# -*- coding: utf-8 -*-
"""
Script de Diagnóstico y Agrupación de Productos para Variantes (Odoo 18.0+)
Entorno: Odoo.sh / Local Shell
Ejecución en Odoo Shell:
    python3 odoo-bin shell -d <DB_NAME> --no-http < audit_products_variants.py
    o ejecutar directamente pegando el código en el shell interactivo.
"""
import re
import logging
from collections import defaultdict

_logger = logging.getLogger('odoo.diagnostic.products')

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
DRY_RUN = True  # Solo lectura y diagnóstico
SAMPLE_LIMIT = 15  # Cantidad de ejemplos para mostrar en consola
EXPORT_CSV = True
CSV_FILENAME = '/tmp/diagnostico_productos_eyelit.csv'

# Patrones típicos de indumentaria / ropa interior argentina
TALLES_COMUNES = ['XXXS', 'XXS', 'XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL', '1', '2', '3', '4', '5', '6', '7', '8', '36', '38', '40', '42', '44', '46', '48', '50']
REGEX_TALLE = re.compile(r'\b(T(?:ALLE)?\.?\s*[:\s]*)?(' + '|'.join(TALLES_COMUNES) + r')\b', re.IGNORECASE)

print("=" * 80)
print(f"[*] INICIANDO AUDITORÍA DE PRODUCTOS - Odoo 18 (DRY RUN: {DRY_RUN})")
print("=" * 80)

Product = env['product.product']
Template = env['product.template']

# 1. Métricas Generales
total_templates = Template.search_count([('active', 'in', [True, False])])
active_templates = Template.search_count([('active', '=', True)])
total_products = Product.search_count([('active', 'in', [True, False])])
active_products = Product.search_count([('active', '=', True)])

products_with_barcode = Product.search_count([('barcode', '!=', False), ('active', '=', True)])
products_with_code = Product.search_count([('default_code', '!=', False), ('active', '=', True)])

print(f"\n[1] METRICAS GENERALES:")
print(f"  - Templates Totales: {total_templates} (Activos: {active_templates})")
print(f"  - Variantes/Productos Totales: {total_products} (Activos: {active_products})")
print(f"  - Productos con Código de Barras (barcode): {products_with_barcode} / {active_products}")
print(f"  - Productos con Referencia Interna (default_code): {products_with_code} / {active_products}")

# 2. Análisis de Transaccionalidad / Historial Operativo
# Esto es crítico para determinar si podemos reemplazar o si debemos remapear IDs
print(f"\n[2] AUDITORÍA DE HISTORIAL Y TRANSACCIONES:")
has_stock_moves = env['stock.move'].search_count([]) > 0 if 'stock.move' in env else False
products_in_stock = 0
products_in_moves = 0
products_in_invoices = 0
products_in_sales = 0

if 'stock.quant' in env:
    products_in_stock = len(env['stock.quant'].read_group([('quantity', '!=', 0)], ['product_id'], ['product_id']))
if 'stock.move' in env:
    products_in_moves = len(env['stock.move'].read_group([], ['product_id'], ['product_id']))
if 'account.move.line' in env:
    products_in_invoices = len(env['account.move.line'].read_group([('product_id', '!=', False)], ['product_id'], ['product_id']))
if 'sale.order.line' in env:
    products_in_sales = len(env['sale.order.line'].read_group([('product_id', '!=', False)], ['product_id'], ['product_id']))

print(f"  - Productos con Stock Actual (stock.quant): {products_in_stock}")
print(f"  - Productos con Movimientos de Stock (stock.move): {products_in_moves}")
print(f"  - Productos con Líneas de Factura (account.move.line): {products_in_invoices}")
print(f"  - Productos con Líneas de Venta (sale.order.line): {products_in_sales}")

# 3. Muestreo e Inspección de Estructura de Nombres, Códigos y Barras
print(f"\n[3] INSPECCIÓN DE PATRONES (Muestra de {SAMPLE_LIMIT} productos):")
sample_products = Product.search([('active', '=', True)], limit=SAMPLE_LIMIT)

header = f"{'ID':<6} | {'Ref. Interna (default_code)':<25} | {'Código Barras':<16} | {'Nombre'}"
print(header)
print("-" * len(header))
for p in sample_products:
    code = (p.default_code or '')[:24]
    barcode = (p.barcode or '')[:15]
    name = (p.name or '')[:60]
    print(f"{p.id:<6} | {code:<25} | {barcode:<16} | {name}")

# 4. Análisis Heurístico de Agrupación Potencial
print(f"\n[4] EVALUACIÓN HEURÍSTICA DE AGRUPACIÓN:")

# Traer todos los productos activos con sus campos clave (optimizado con search_read)
all_prods = Product.search_read(
    [('active', '=', True)],
    ['id', 'name', 'default_code', 'barcode', 'product_tmpl_id'],
    limit=15000
)

# Heurística A: Agrupación por coincidencia de prefijo en default_code (ej: 500-NEG-M -> Art 500)
group_by_code_prefix = defaultdict(list)
# Heurística B: Agrupación por nombre base removiendo talle
group_by_clean_name = defaultdict(list)

for p in all_prods:
    # Por Código Interno si tiene separadores típicos '-', '.', '/'
    code = p.get('default_code') or ''
    if '-' in code:
        parts = code.split('-')
        art_code = parts[0].strip()
        group_by_code_prefix[art_code].append(p)
    elif '.' in code:
        parts = code.split('.')
        art_code = parts[0].strip()
        group_by_code_prefix[art_code].append(p)

    # Por Nombre limpiando talle
    raw_name = p.get('name') or ''
    clean_name = REGEX_TALLE.sub('', raw_name).strip(' -.,/|')
    clean_name = re.sub(r'\s+', ' ', clean_name)
    group_by_clean_name[clean_name].append(p)

print(f"  - Agrupación por Nombre Base (sin talle):")
print(f"    * Familias / Templates resultantes estimadas: {len(group_by_clean_name)}")
candidates_multivariant = [name for name, items in group_by_clean_name.items() if len(items) > 1]
print(f"    * Templates candidatos con más de 1 variante: {len(candidates_multivariant)}")

print(f"\n[5] EJEMPLO DE CANDIDATOS A VARIANTES AGRUPADAS (Top 5 familias):")
top_families = sorted(group_by_clean_name.items(), key=lambda x: len(x[1]), reverse=True)[:5]

for fam_name, items in top_families:
    print(f"\n  Template Candidato: '{fam_name}' ({len(items)} variantes detectadas)")
    for it in items[:6]:  # mostrar hasta 6 variantes
        print(f"    -> [ID {it['id']}] Code: {it.get('default_code')} | Barcode: {it.get('barcode')} | Original: {it.get('name')}")
    if len(items) > 6:
        print(f"    ... y {len(items) - 6} más.")

# 6. Exportación a CSV opcional para análisis en Excel
if EXPORT_CSV:
    import csv
    try:
        with open(CSV_FILENAME, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['product_id', 'product_tmpl_id', 'default_code', 'barcode', 'original_name', 'suggested_template_name'])
            for clean_name, prods in group_by_clean_name.items():
                for p in prods:
                    writer.writerow([
                        p['id'],
                        p['product_tmpl_id'][0] if p.get('product_tmpl_id') else '',
                        p.get('default_code') or '',
                        p.get('barcode') or '',
                        p.get('name') or '',
                        clean_name
                    ])
        print(f"\n[+] Diagnóstico exportado exitosamente a CSV en: {CSV_FILENAME}")
    except Exception as e:
        print(f"\n[-] No se pudo escribir CSV en {CSV_FILENAME}: {e}")

print("\n" + "=" * 80)
print("[*] DIAGNÓSTICO FINALIZADO CON ÉXITO")
print("=" * 80)
