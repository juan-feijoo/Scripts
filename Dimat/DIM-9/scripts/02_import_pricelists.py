# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT 02: CREACIÓN/ACTUALIZACIÓN DE TARIFAS (ARS Y USD) CON PRODUCTOS
================================================================================
Entorno: Odoo 17.0+e / 18.0+e / 19.0+e (Odoo.sh / On-Premise)
Soporte de DRY-RUN:
    - DRY_RUN = True  -> Realiza todas las operaciones y finaliza con rollback.
    - DRY_RUN = False -> Confirma los cambios permanentemente con commit.

Uso en Odoo Shell:
    python3 odoo-bin shell -d <nombre_bd> < scripts/02_import_pricelists.py
    o pegar el contenido en la shell interactiva.
================================================================================
"""
import os
import json

# ==============================================================================
# PARÁMETROS DE CONFIGURACIÓN
# ==============================================================================
DRY_RUN = False  # <<-- Cambiar a False para persistir los cambios en la base de datos

# Nombres de las listas de precios que vamos a crear o actualizar
PRICELIST_NAME_ARS = "DIMAT - Lista General (ARS)"
PRICELIST_NAME_USD = "DIMAT - Lista General (USD)"

# Nombre o ID de la compañía (DROGUERIA DIMAT SA)
COMPANY_NAME = "DROGUERIA DIMAT SA"

# Filtros de importación
OMITIR_PRECIO_CERO = True           # Si es True, no crea items con importe 0
CAMPO_PRECIO = "price_reposicion"   # Opciones: "price_reposicion" o "price_ultima_compra"

# Rutas posibles del archivo JSON
POSSIBLE_PATHS = [
    "scripts/precios_procesados.json",
    "precios_procesados.json",
    os.path.join(os.path.dirname(__file__) if "__file__" in locals() else ".", "precios_procesados.json"),
    os.path.join(os.path.dirname(__file__) if "__file__" in locals() else ".", "scripts", "precios_procesados.json"),
]

# ==============================================================================
# 1. LOCALIZACIÓN Y CARGA DEL ARCHIVO JSON
# ==============================================================================
json_file = None
for p in POSSIBLE_PATHS:
    if os.path.exists(p):
        json_file = p
        break

if not json_file:
    raise FileNotFoundError(
        f"No se encontró 'precios_procesados.json'. Rutas buscadas: {POSSIBLE_PATHS}\n"
        "Asegúrate de copiar el archivo al directorio de trabajo en el servidor."
    )

with open(json_file, "r", encoding="utf-8") as f:
    items_data = json.load(f)

print("\n" + "="*80)
print(f" IMPORTACIÓN DE TARIFAS (DRY_RUN = {DRY_RUN}) ".center(80, "="))
print("="*80)
print(f"[*] Archivo cargado: {json_file} ({len(items_data)} registros)")

# ==============================================================================
# 2. AUDITORÍA DE COMPAÑÍA Y MONEDAS
# ==============================================================================
company = env['res.company'].search([('name', 'ilike', COMPANY_NAME)], limit=1) or env.company
print(f"[*] Compañía asignada: [{company.id}] {company.name}")

curr_ars = env['res.currency'].search([('name', '=', 'ARS')], limit=1)
curr_usd = env['res.currency'].search([('name', '=', 'USD')], limit=1)

if not curr_ars:
    raise ValueError("Moneda ARS no encontrada en el sistema.")
if not curr_usd:
    raise ValueError("Moneda USD no encontrada en el sistema.")

print(f"[*] Monedas vinculadas -> ARS: ID {curr_ars.id} | USD: ID {curr_usd.id}")

# ==============================================================================
# 3. OBTENCIÓN O CREACIÓN DE LAS LISTAS DE PRECIOS
# ==============================================================================
def get_or_create_pricelist(name, currency, comp):
    pl = env['product.pricelist'].search([
        ('name', '=', name),
        '|', ('company_id', '=', comp.id), ('company_id', '=', False)
    ], limit=1)
    if not pl:
        pl = env['product.pricelist'].create({
            'name': name,
            'currency_id': currency.id,
            'company_id': comp.id,
            'active': True,
        })
        print(f"  [+] Tarifa CREADA: '{name}' (ID: {pl.id}) en {currency.name}")
    else:
        print(f"  [=] Tarifa EXISTENTE: '{name}' (ID: {pl.id}) en {currency.name}")
    return pl

pl_ars = get_or_create_pricelist(PRICELIST_NAME_ARS, curr_ars, company)
pl_usd = get_or_create_pricelist(PRICELIST_NAME_USD, curr_usd, company)

# ==============================================================================
# 4. INDEXACIÓN EN MEMORIA DE PRODUCTOS Y REGLAS EXISTENTES (BATCH + FALLBACKS)
# ==============================================================================
print("\n[*] Indexando productos y reglas existentes...")

# Indexar items existentes por variante de producto para actualizar en vez de duplicar
items_ars_map = {item.product_id.id: item for item in pl_ars.item_ids if item.product_id}
items_usd_map = {item.product_id.id: item for item in pl_usd.item_ids if item.product_id}

# 4.1 Búsqueda directa por default_code
all_codes = list({item['code'].strip() for item in items_data if item.get('code')})
products = env['product.product'].search([('default_code', 'in', all_codes)])
prod_by_code = {p.default_code.strip(): p for p in products}

# 4.2 Fallback en product.template
missing_codes = [c for c in all_codes if c not in prod_by_code]
if missing_codes:
    templates = env['product.template'].search([('default_code', 'in', missing_codes)])
    for t in templates:
        if t.product_variant_id:
            prod_by_code[t.default_code.strip()] = t.product_variant_id

# 4.3 Fallback: Limpieza de puntos finales (ej. '88800000000059.' -> '88800000000059')
missing_codes = [c for c in all_codes if c not in prod_by_code]
dot_mapping = {c: c.rstrip('.').strip() for c in missing_codes if c.endswith('.')}
if dot_mapping:
    clean_prods = env['product.product'].search([('default_code', 'in', list(dot_mapping.values()))])
    clean_map = {p.default_code.strip(): p for p in clean_prods}
    for orig_code, clean_code in dot_mapping.items():
        if clean_code in clean_map:
            prod_by_code[orig_code] = clean_map[clean_code]

# 4.4 Fallback: Búsqueda por Código de Barras (barcode)
missing_codes = [c for c in all_codes if c not in prod_by_code]
if missing_codes:
    barcode_prods = env['product.product'].search([('barcode', 'in', missing_codes)])
    for p in barcode_prods:
        if p.barcode and p.barcode in missing_codes:
            prod_by_code[p.barcode] = p

# 4.5 Fallback: Búsqueda por Nombre exacto
missing_items = [item for item in items_data if item['code'].strip() not in prod_by_code]
for m in missing_items:
    name_clean = m['name'].strip()
    if name_clean:
        p_by_name = env['product.product'].search([('name', '=ilike', name_clean)], limit=1)
        if p_by_name:
            prod_by_code[m['code'].strip()] = p_by_name

print(f"[*] Coincidencias finales de productos en Odoo: {len(prod_by_code)} de {len(all_codes)}")

# ==============================================================================
# 5. PROCESAMIENTO Y CREACIÓN DE ITEMS
# ==============================================================================
stats = {
    'ARS': {'created': 0, 'updated': 0, 'zero_skipped': 0},
    'USD': {'created': 0, 'updated': 0, 'zero_skipped': 0},
    'not_found': 0,
    'total_processed': 0
}

items_to_create = []
not_found_list = []

for row in items_data:
    stats['total_processed'] += 1
    code = row['code'].strip()
    currency_code = row.get('currency', 'ARS')
    price = float(row.get(CAMPO_PRECIO, 0) or 0)
    
    # 1. Validar producto
    product = prod_by_code.get(code)
    if not product:
        stats['not_found'] += 1
        not_found_list.append(row)
        continue
        
    # 2. Validar precio cero
    if OMITIR_PRECIO_CERO and price <= 0.0:
        stats[currency_code]['zero_skipped'] += 1
        continue

    # 3. Determinar lista objetivo y mapa existente
    if currency_code == 'USD':
        target_pl = pl_usd
        target_map = items_usd_map
    else:
        target_pl = pl_ars
        target_map = items_ars_map

    # 4. Actualizar si ya existe en la lista, o preparar para crear
    existing_item = target_map.get(product.id)
    if existing_item:
        if abs(existing_item.fixed_price - price) > 0.001:
            existing_item.write({'fixed_price': price})
            stats[currency_code]['updated'] += 1
    else:
        items_to_create.append({
            'pricelist_id': target_pl.id,
            'applied_on': '0_product_variant',
            'product_id': product.id,
            'compute_price': 'fixed',
            'fixed_price': price,
            'min_quantity': 0,
            'company_id': target_pl.company_id.id,
        })
        stats[currency_code]['created'] += 1

# Creación masiva para optimizar velocidad
if items_to_create:
    env['product.pricelist.item'].create(items_to_create)

# ==============================================================================
# 6. RESUMEN Y GESTIÓN TRANSACCIONAL
# ==============================================================================
print("\n" + "="*80)
print(" RESUMEN FINAL DE EJECUCIÓN ".center(80, "="))
print("="*80)
print(f"Total registros analizados:           {stats['total_processed']}")
print(f"Productos NO encontrados en Odoo:     {stats['not_found']}")
print("-" * 80)
print(f"Tarifa ARS [{PRICELIST_NAME_ARS}]:")
print(f"  - Nuevos precios creados:          {stats['ARS']['created']}")
print(f"  - Precios existentes actualizados: {stats['ARS']['updated']}")
print(f"  - Omitidos por precio <= 0:        {stats['ARS']['zero_skipped']}")
print("-" * 80)
print(f"Tarifa USD [{PRICELIST_NAME_USD}]:")
print(f"  - Nuevos precios creados:          {stats['USD']['created']}")
print(f"  - Precios existentes actualizados: {stats['USD']['updated']}")
print(f"  - Omitidos por precio <= 0:        {stats['USD']['zero_skipped']}")
print("="*80)

if not_found_list:
    print(f"\n[*] Muestra de los primeros 10 productos que no existen en Odoo:")
    for nf in not_found_list[:10]:
        print(f"    - Código: {nf['code']:<15} | {nf['name']}")

if DRY_RUN:
    env.cr.rollback()
    print("\n[!] MODO DRY-RUN ACTIVO: Rollback ejecutado. La base de datos no fue modificada.")
    print("    Para guardar los cambios definitivamente, cambie DRY_RUN = False y vuelva a ejecutar.")
else:
    env.cr.commit()
    print("\n[OK] MODO PRODUCCIÓN: Transacción confirmada exitosamente (commit ejecutado).")
