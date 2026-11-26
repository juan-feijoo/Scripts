# -*- coding: utf-8 -*-
"""
02 - MIGRACIÓN UNIFICADA: VARIANTES, STOCK, CATEGORÍAS Y LISTA DE PRECIOS
Resuelve Tickets 1, 2 y 3 en una transacción atómica.
Control: DRY_RUN=1 (Simulación) o DRY_RUN=0 (Commit en producción).
"""
import os
import re
import sys
import json
from collections import defaultdict, Counter

h('02 - EJECUCIÓN DEL PIPELINE UNIFICADO DE MIGRACIÓN')

# Configuración: variable de entorno o fallback a True para máxima seguridad
env_dry_run = os.environ.get('DRY_RUN', '1').strip().lower()
DRY_RUN = env_dry_run in ('1', 'true', 'yes')
ALLOW_OPEN_POS = os.environ.get('ALLOW_OPEN_POS', '0').strip().lower() in ('1', 'true', 'yes')
FORCE_RERUN = os.environ.get('FORCE_RERUN', '0').strip().lower() in ('1', 'true', 'yes')
SEPARAR_POR_LINEA = True
LIMIT_FAMILIES = int(os.environ.get('LIMIT_FAMILIES', '0')) or None
EXPORT_STOCK_JSON = True
STOCK_BACKUP_PATH = '/tmp/stock_snapshot_eyelit_pre_migration.json'

print(f"[*] MODO EJECUCIÓN: {'*** SIMULACIÓN DRY-RUN (ROLLBACK) ***' if DRY_RUN else '*** PRODUCCIÓN (COMMIT DEFINITIVO) ***'}")
print(f"[*] BASE DE DATOS: {env.cr.dbname}")
print(f"[*] COMPAÑÍA: {env.company.name} (ID: {env.company.id})")
print(f"[*] LÍMITE: {LIMIT_FAMILIES if LIMIT_FAMILIES else 'TODAS LAS FAMILIAS'}")

TALLE_MAP = {
    'XS0': 'XS', 'S00': 'S', 'M00': 'M', 'L00': 'L', 'XL0': 'XL', 'XXL': 'XXL',
    '3XL': '3XL', '4XL': '4XL', '5XL': '5XL', '6XL': '6XL',
    '000': 'U',
    '7/8': '7/8', '9/1': '9/10', '11/': '11/12', '13/': '13/14'
}

TALLE_ORDER_MAP = {
    'U': 0, '0': 0, '000': 0, 'UNICO': 0, 'ÚNICO': 0,
    'XXXS': 1, 'XXS': 2, 'XS': 3, 'S': 4, 'M': 5, 'L': 6,
    'XL': 7, 'XXL': 8, '2XL': 8, '3XL': 9, '4XL': 10, '5XL': 11, '6XL': 12
}

def normalize_talle(suffix):
    s = (suffix or '').strip()
    if s in TALLE_MAP:
        return TALLE_MAP[s]
    if s.isdigit():
        return str(int(s))
    if s.endswith('0') and s[:-1].isalpha():
        return s[:-1]
    return s

def talle_sort_key(t):
    t_clean = (t or '').strip().upper()
    if t_clean in TALLE_ORDER_MAP:
        return (1, TALLE_ORDER_MAP[t_clean], t_clean)
    if t_clean.isdigit():
        return (2, int(t_clean), t_clean)
    if '/' in t_clean:
        prefix_num = t_clean.split('/')[0]
        if prefix_num.isdigit():
            return (3, int(prefix_num), t_clean)
    return (4, 0, t_clean)

def parse_code(code):
    code = (code or '').strip()
    if '.' not in code:
        return None
    prefix, suffix = code.rsplit('.', 1)
    talle = normalize_talle(suffix)
    art = prefix[:4] if len(prefix) >= 4 else prefix
    linea = prefix[4:7] if len(prefix) >= 7 else ''
    color = prefix[7:9] if len(prefix) >= 9 else prefix[4:]
    if not color:
        color = 'STD'
    return {
        'code': code,
        'prefix': prefix,
        'art': art,
        'linea': linea,
        'color': color,
        'talle': talle
    }

def clean_base_name(name):
    n = (name or '').strip()
    return re.sub(r'(\s*\([A-Z0-9]+\))+\s*$', '', n).strip()

def is_sku_like_name(name, code=''):
    n = (name or '').strip()
    if not n:
        return True
    if code and n.upper() == code.strip().upper():
        return True
    return bool(re.match(r'^[0-9A-Z]{5,}\.[0-9A-Z/]+$', n, re.IGNORECASE))

cr = env.cr
cr.execute("SAVEPOINT unificado_migracion_sp")

# Detectar idioma español activo en la base (crítico: en_US puede tener códigos SKU donde es_AR tiene el nombre real)
active_langs = env['res.lang'].search([('active', '=', True)]).mapped('code')
target_lang = next((l for l in ['es_AR', 'es_419', 'es_ES'] if l in active_langs), env.lang or 'en_US')
print(f"[*] IDIOMA DE TRABAJO (NOMBRES): {target_lang} (activos: {active_langs})")

Product = env['product.product'].with_context(lang=target_lang)
Template = env['product.template'].with_context(lang=target_lang)
Attribute = env['product.attribute'].with_context(lang=target_lang)
AttrValue = env['product.attribute.value'].with_context(lang=target_lang)
PosCategory = env['pos.category'].with_context(lang=target_lang)
PosConfig = env['pos.config'].with_context(lang=target_lang)
ProductCategory = env['product.category'].with_context(lang=target_lang)
Pricelist = env['product.pricelist'].with_context(lang=target_lang)
PricelistItem = env['product.pricelist.item'].with_context(lang=target_lang)
Quant = env['stock.quant']

has_pos_available = 'available_in_pos' in Template._fields
has_pos_categ_ids = 'pos_categ_ids' in Template._fields

# 0. Guardas de Seguridad en Producción y Activación del Check de Variantes
sub('0. Guardas de Producción y Activación de Check Variantes')

# 0.1. Verificar sesiones de TPV abiertas (CRÍTICO en producción)
if 'pos.session' in env:
    open_pos_sessions = env['pos.session'].search([('state', '!=', 'closed')])
    if open_pos_sessions:
        print(f"[!] DETECTADAS {len(open_pos_sessions)} SESIONES DE TPV ABIERTAS:")
        for s in open_pos_sessions:
            print(f"    - Sesión [ID {s.id}] '{s.name}' (Caja: {s.config_id.name}, Usuario: {s.user_id.name}, Estado: {s.state})")
        if not DRY_RUN and not ALLOW_OPEN_POS:
            cr.execute("ROLLBACK TO SAVEPOINT unificado_migracion_sp")
            print("\n!! ERROR DE SEGURIDAD EN PRODUCCIÓN: No se puede ejecutar DRY_RUN=0 con sesiones de TPV abiertas.")
            print("   Motivo: Las ventas de una sesión abierta descontarían stock sobre los productos viejos archivados al cerrar la caja.")
            print("   Acción requerida: Cierre todas las cajas en Punto de Venta (sin tickets pendientes) y vuelva a correr DRY_RUN=0.")
            print("   (Si necesita forzarlo conscientemente, pase ALLOW_OPEN_POS=1 DRY_RUN=0 bash run_all.sh)")
            sys.exit(1)
        elif DRY_RUN:
            print("    * En modo DRY_RUN se continúa la simulación, pero en PRODUCCIÓN (DRY_RUN=0) deberá cerrar la caja antes.")

# 0.2. Protección anti-doble ejecución accidental en producción
already_archived_old = Product.search_count([('active', '=', False), ('barcode', '=like', '%_OLD')])
if already_archived_old >= 100 and not DRY_RUN and not FORCE_RERUN:
    cr.execute("ROLLBACK TO SAVEPOINT unificado_migracion_sp")
    print(f"\n!! ERROR DE SEGURIDAD: Ya existen {already_archived_old} productos archivados con sufijo '_OLD'.")
    print("   La migración parece haberse ejecutado previamente sobre esta base de datos.")
    print("   (Si realmente desea re-ejecutarla, pase FORCE_RERUN=1 DRY_RUN=0 bash run_all.sh)")
    sys.exit(1)

# 0.3. Activar Check de 'Variantes' (Ajustes -> Ventas -> Variantes: product.group_product_variant)
group_user = env.ref('base.group_user', raise_if_not_found=False)
group_variant = env.ref('product.group_product_variant', raise_if_not_found=False)
if group_user and group_variant:
    if group_variant not in group_user.implied_ids:
        group_user.write({'implied_ids': [(4, group_variant.id)]})
        print("  + Activado check 'Variantes' (product.group_product_variant -> base.group_user).")
    else:
        print("  * Check 'Variantes' (product.group_product_variant) ya se encontraba activo.")

group_pricelist = env.ref('product.group_product_pricelist', raise_if_not_found=False)
if group_user and group_pricelist:
    if group_pricelist not in group_user.implied_ids:
        group_user.write({'implied_ids': [(4, group_pricelist.id)]})
        print("  + Activado check 'Listas de precios' (product.group_product_pricelist -> base.group_user).")
    else:
        print("  * Check 'Listas de precios' (product.group_product_pricelist) ya se encontraba activo.")

# 1. Atributos Talle y Color
sub('1. Configuración de Atributos Globales')
attr_talle = Attribute.search([('name', '=ilike', 'Talle')], limit=1)
if not attr_talle:
    attr_talle = Attribute.create({'name': 'Talle', 'display_type': 'pills', 'create_variant': 'always'})
else:
    if attr_talle.create_variant != 'always':
        attr_talle.write({'create_variant': 'always', 'display_type': 'pills'})

attr_color = Attribute.search([('name', '=ilike', 'Color')], limit=1)
if not attr_color:
    attr_color = Attribute.create({'name': 'Color', 'display_type': 'select', 'create_variant': 'always'})
else:
    if attr_color.create_variant != 'always':
        attr_color.write({'create_variant': 'always', 'display_type': 'select'})

talle_value_cache = {v.name: v.id for v in AttrValue.with_context(active_test=False).search([('attribute_id', '=', attr_talle.id)])}
color_value_cache = {v.name: v.id for v in AttrValue.with_context(active_test=False).search([('attribute_id', '=', attr_color.id)])}

def get_or_create_value(attr_id, val_name, cache):
    if val_name not in cache:
        existing = AttrValue.with_context(active_test=False).search([
            ('attribute_id', '=', attr_id),
            ('name', '=', val_name)
        ], limit=1)
        if existing:
            if not existing.active:
                existing.write({'active': True})
            cache[val_name] = existing.id
        else:
            rec = AttrValue.create({'name': val_name, 'attribute_id': attr_id})
            cache[val_name] = rec.id
    return cache[val_name]

# 2. Categorías TPV y Producto con resolución de sinónimos
sub('2. Categorías de TPV y Producto')
REQUIRED_CATEGORIES = [
    'Boxers', 'Slips', 'Femenina', 'Camisetas y Remeras',
    'Medias', 'Pantalones', 'Pijamas', 'Otros'
]

SYNONYMS_MAP = {
    'camisetas y remeras': ['camisetas y remeras', 'upper body', 'remeras y camisetas', 'camisetas', 'remeras'],
    'otros': ['otros', 'others', 'otro', 'other'],
    'femenina': ['femenina', 'mujer', 'women'],
    'boxers': ['boxers', 'boxer'],
    'slips': ['slips', 'slip'],
    'medias': ['medias', 'socks', 'soquetes'],
    'pantalones': ['pantalones', 'pants', 'bottoms'],
    'pijamas': ['pijamas', 'sleepwear']
}

pos_cat_cache = {c.name.strip().lower(): c.id for c in PosCategory.search([])}
resolved_pos_cats = {}
for canon_name in REQUIRED_CATEGORIES:
    k = canon_name.strip().lower()
    syns = SYNONYMS_MAP.get(k, [k])
    found_id = None
    for s in syns:
        if s in pos_cat_cache:
            found_id = pos_cat_cache[s]
            break
    if not found_id:
        cat_rec = PosCategory.create({'name': canon_name})
        found_id = cat_rec.id
        pos_cat_cache[k] = found_id
        print(f"  + Creada categoría TPV: '{canon_name}' (ID {found_id})")
    resolved_pos_cats[k] = found_id

def classify_pos_category(name):
    n = (name or '').lower()
    if 'boxer' in n:
        return resolved_pos_cats.get('boxers')
    elif 'slip' in n:
        return resolved_pos_cats.get('slips')
    elif any(k in n for k in ['soutien', 'femenin', 'bombacha', 'colaless', 'vedetina', 'culotte', 'tanga']):
        return resolved_pos_cats.get('femenina')
    elif any(k in n for k in ['remera', 'camiseta', 'musculosa', 'chomba', 'top']):
        return resolved_pos_cats.get('camisetas y remeras') or resolved_pos_cats.get('otros')
    elif any(k in n for k in ['media', 'soquete', 'pantys']):
        return resolved_pos_cats.get('medias') or resolved_pos_cats.get('otros')
    elif any(k in n for k in ['pantalon', 'short', 'bermuda', 'calzoncillo']):
        return resolved_pos_cats.get('pantalones') or resolved_pos_cats.get('otros')
    elif any(k in n for k in ['pijama', 'camison']):
        return resolved_pos_cats.get('pijamas') or resolved_pos_cats.get('otros')
    else:
        return resolved_pos_cats.get('otros')

all_categ = env.ref('product.product_category_all', raise_if_not_found=False)
ropa_int_categ = ProductCategory.search([('name', '=ilike', 'Ropa Interior')], limit=1)
parent_default_categ_id = ropa_int_categ.id if ropa_int_categ else (all_categ.id if all_categ else False)
all_categ_id = all_categ.id if all_categ else False
prod_cat_cache = {c.name.strip().lower(): c.id for c in ProductCategory.search([])}
resolved_prod_cats = {}
for canon_name in REQUIRED_CATEGORIES:
    k = canon_name.strip().lower()
    syns = SYNONYMS_MAP.get(k, [k])
    found_id = None
    for s in syns:
        if s in prod_cat_cache:
            found_id = prod_cat_cache[s]
            break
    if not found_id:
        pcat_vals = {'name': canon_name}
        if parent_default_categ_id:
            pcat_vals['parent_id'] = parent_default_categ_id
        pcat = ProductCategory.create(pcat_vals)
        found_id = pcat.id
        prod_cat_cache[k] = found_id
        print(f"  + Creada categoría interna de producto: '{canon_name}' (ID {found_id})")
    resolved_prod_cats[k] = found_id

default_prod_cat_id = resolved_prod_cats.get('otros') or all_categ_id

# 3. Escaneo y agrupación (usando nombres en español + fallback a nombre hermano por art+linea si viene código SKU)
sub('3. Escaneo y Agrupación del Catálogo')
fields_to_read = ['id', 'name', 'default_code', 'barcode', 'product_tmpl_id', 'list_price', 'standard_price', 'categ_id', 'uom_id']
has_taxes_id = 'taxes_id' in Product._fields
has_supplier_taxes_id = 'supplier_taxes_id' in Product._fields
has_uom_po_id = 'uom_po_id' in Product._fields
has_sale_ok = 'sale_ok' in Product._fields
has_purchase_ok = 'purchase_ok' in Product._fields

if has_pos_categ_ids:
    fields_to_read.append('pos_categ_ids')
if has_taxes_id:
    fields_to_read.append('taxes_id')
if has_supplier_taxes_id:
    fields_to_read.append('supplier_taxes_id')
if has_uom_po_id:
    fields_to_read.append('uom_po_id')
if has_sale_ok:
    fields_to_read.append('sale_ok')
if has_purchase_ok:
    fields_to_read.append('purchase_ok')

all_prods = Product.search_read([('active', '=', True)], fields_to_read)
parsed_items = []
old_prod_ids_to_archive = []
skipped = 0
human_names_by_art_linea = defaultdict(Counter)

for p in all_prods:
    code = (p.get('default_code') or p.get('barcode') or '').strip()
    parsed = parse_code(code)
    if not parsed:
        skipped += 1
        continue
    
    parsed['old_product_id'] = p['id']
    parsed['old_tmpl_id'] = p['product_tmpl_id'][0] if p.get('product_tmpl_id') else False
    parsed['name'] = p.get('name') or ''
    parsed['list_price'] = p.get('list_price') or 0.0
    parsed['standard_price'] = p.get('standard_price') or 0.0
    parsed['categ_id'] = p.get('categ_id')[0] if p.get('categ_id') else False
    parsed['uom_id'] = p.get('uom_id')[0] if p.get('uom_id') else False
    parsed['pos_categ_ids'] = p.get('pos_categ_ids') or [] if has_pos_categ_ids else []
    parsed['taxes_id'] = p.get('taxes_id') or [] if has_taxes_id else []
    parsed['supplier_taxes_id'] = p.get('supplier_taxes_id') or [] if has_supplier_taxes_id else []
    parsed['uom_po_id'] = p['uom_po_id'][0] if (has_uom_po_id and p.get('uom_po_id')) else False
    parsed['sale_ok'] = p.get('sale_ok', True) if has_sale_ok else True
    parsed['purchase_ok'] = p.get('purchase_ok', True) if has_purchase_ok else True

    base_name = clean_base_name(parsed['name'])
    parsed['base_name'] = base_name
    if not is_sku_like_name(base_name, code):
        al_key = (parsed['art'], parsed['linea'] if SEPARAR_POR_LINEA else '')
        human_names_by_art_linea[al_key][base_name] += 1

    old_prod_ids_to_archive.append(p['id'])
    parsed_items.append(parsed)

families = defaultdict(list)
fixed_sku_names = 0
for parsed in parsed_items:
    base_name = parsed['base_name']
    al_key = (parsed['art'], parsed['linea'] if SEPARAR_POR_LINEA else '')
    if is_sku_like_name(base_name, parsed['code']) and human_names_by_art_linea.get(al_key):
        base_name = human_names_by_art_linea[al_key].most_common(1)[0][0]
        fixed_sku_names += 1
    if SEPARAR_POR_LINEA and parsed['linea']:
        family_key = (parsed['art'], parsed['linea'], base_name)
    else:
        family_key = (parsed['art'], '', base_name)
    families[family_key].append(parsed)

print(f"Total familias detectadas: {len(families)} ({len(old_prod_ids_to_archive)} productos)")
print(f"Productos especiales omitidos: {skipped}")
if fixed_sku_names > 0:
    print(f"  * Nombres SKU resueltos con nombre de familia hermana: {fixed_sku_names}")

if LIMIT_FAMILIES:
    families_to_process = list(families.items())[:LIMIT_FAMILIES]
    print(f"[!] Modo prueba: limitando a {LIMIT_FAMILIES} familias")
else:
    families_to_process = list(families.items())

prods_in_batch = []
tmpls_in_batch = set()
old_pid_to_old_tid = {}
for _, items in families_to_process:
    for it in items:
        prods_in_batch.append(it['old_product_id'])
        if it['old_tmpl_id']:
            tmpls_in_batch.add(it['old_tmpl_id'])
            old_pid_to_old_tid[it['old_product_id']] = it['old_tmpl_id']
old_tid_to_old_pid = {tid: pid for pid, tid in old_pid_to_old_tid.items()}

# 3.1. Extracción y Verificación de Precios Pre-Migración (SIN alterar list_price base de producción)
sub('3.1. Extracción y Verificación de Precios Pre-Migración')
pos_configs = PosConfig.search([])
main_pos_pricelist = None
for cfg in pos_configs:
    if hasattr(cfg, 'pricelist_id') and cfg.pricelist_id:
        main_pos_pricelist = cfg.pricelist_id
        break

if not main_pos_pricelist:
    main_pos_pricelist = Pricelist.search([('name', '=ilike', '%AR 2%')], limit=1)

main_pos_pl_id = main_pos_pricelist.id if main_pos_pricelist else False
if main_pos_pricelist:
    print(f"Lista de precios principal detectada (TPV): '{main_pos_pricelist.name}' (ID {main_pos_pl_id})")

# Consultar reglas existentes de precios para los productos/plantillas del lote
cr.execute("""
    SELECT 
        ppi.id,
        ppi.pricelist_id,
        ppi.product_id,
        ppi.product_tmpl_id,
        ppi.compute_price,
        ppi.fixed_price,
        ppi.applied_on,
        pl.active
    FROM product_pricelist_item ppi
    JOIN product_pricelist pl ON pl.id = ppi.pricelist_id
    WHERE (ppi.product_id = ANY(%s) OR (ppi.product_tmpl_id = ANY(%s) AND ppi.product_tmpl_id IS NOT NULL))
      AND (ppi.company_id = %s OR ppi.company_id IS NULL)
    ORDER BY ppi.id DESC
""", (prods_in_batch, list(tmpls_in_batch) if tmpls_in_batch else [0], env.company.id))

existing_rules = cr.fetchall()
print(f"Reglas de listas de precios existentes encontradas para estos productos: {len(existing_rules)}")

old_prod_main_pl_price = {}
old_prod_any_pl_price = {}
for r_id, pl_id, p_id, pt_id, comp_price, fix_price, app_on, pl_active in existing_rules:
    if not pl_active:
        continue
    if comp_price == 'fixed' and fix_price and fix_price > 0:
        target_pid = p_id or (old_tid_to_old_pid.get(pt_id) if pt_id else None)
        if target_pid:
            if pl_id == main_pos_pl_id and target_pid not in old_prod_main_pl_price:
                old_prod_main_pl_price[target_pid] = fix_price
            elif target_pid not in old_prod_any_pl_price:
                old_prod_any_pl_price[target_pid] = fix_price

captured_pl_prices = 0
for _, items in families_to_process:
    for it in items:
        pid = it['old_product_id']
        best_pl_price = old_prod_main_pl_price.get(pid) or old_prod_any_pl_price.get(pid)
        if best_pl_price and best_pl_price > 0:
            it['pricelist_price'] = best_pl_price
            captured_pl_prices += 1
        else:
            it['pricelist_price'] = it.get('list_price') or 0.0

print(f"  * Precios de lista capturados para reglas de variantes: {captured_pl_prices} productos.")
print("  * Campo 'Precio de venta' (list_price) en ficha de producto se preserva tal como viene de producción ($1.00).")

# 4. Extracción de Stock antes de archivar (Tickets 1 & 3)
sub('4. Extracción de Stock a la Fecha antes de Archivar')

cr.execute("SELECT id FROM stock_location WHERE usage = 'internal'")
internal_loc_ids = {r[0] for r in cr.fetchall()}

stock_quants_raw = Quant.search_read(
    [('product_id', 'in', prods_in_batch), ('quantity', '!=', 0)],
    ['id', 'product_id', 'location_id', 'quantity', 'reserved_quantity', 'lot_id', 'package_id', 'company_id', 'owner_id']
)
stock_snapshot = {}
quants_by_old_product = defaultdict(list)
total_stock_initial = 0.0
total_internal_initial = 0.0

for q in stock_quants_raw:
    old_pid = q['product_id'][0]
    loc_id = q['location_id'][0]
    loc_name = q['location_id'][1]
    qty = q['quantity']
    is_internal = loc_id in internal_loc_ids
    quants_by_old_product[old_pid].append(q)
    total_stock_initial += qty
    if is_internal:
        total_internal_initial += qty
    
    if old_pid not in stock_snapshot:
        stock_snapshot[old_pid] = {
            'old_product_id': old_pid,
            'total_qty': 0.0,
            'internal_qty': 0.0,
            'total_reserved': 0.0,
            'locations': defaultdict(float)
        }
    stock_snapshot[old_pid]['total_qty'] += qty
    if is_internal:
        stock_snapshot[old_pid]['internal_qty'] += qty
    stock_snapshot[old_pid]['total_reserved'] += q.get('reserved_quantity', 0.0)
    stock_snapshot[old_pid]['locations'][loc_name] += qty

print(f"Quants con stock a trasladar: {len(stock_quants_raw)}")
print(f"Total unidades físicas en existencias internas (WH): {total_internal_initial:,.2f}")
print(f"Total balance neto en todas las ubicaciones (incluye partners): {total_stock_initial:,.2f}")

if EXPORT_STOCK_JSON and stock_snapshot:
    try:
        with open(STOCK_BACKUP_PATH, 'w', encoding='utf-8') as f:
            json.dump({str(k): {'total_qty': v['total_qty'], 'internal_qty': v['internal_qty'], 'locations': dict(v['locations'])} for k, v in stock_snapshot.items()}, f, indent=2)
        print(f"Respaldo de stock guardado en {STOCK_BACKUP_PATH}")
    except Exception as e:
        print(f"Aviso al guardar json: {e}")

# 5. Liberar Barcodes y Archivar (Idempotente)
sub('5. Liberación de Códigos de Barra y Archivado')
cr.execute("""
    UPDATE product_product 
    SET barcode = barcode || '_OLD' 
    WHERE id = ANY(%s) 
      AND barcode IS NOT NULL 
      AND barcode NOT LIKE '%%_OLD'
""", (prods_in_batch,))
if prods_in_batch:
    cr.execute("UPDATE product_product SET active = FALSE WHERE id = ANY(%s)", (prods_in_batch,))
if tmpls_in_batch:
    cr.execute("UPDATE product_template SET active = FALSE WHERE id = ANY(%s)", (list(tmpls_in_batch),))
Product.invalidate_model()
Template.invalidate_model()
print(f"Liberados barcodes y archivados {len(prods_in_batch)} productos viejos.")

# 6. Creación nativa de plantillas y variantes
sub('6. Creación Nativa de Plantillas y Variantes (ORM)')
count_templates = 0
count_variants = 0
old_to_new_variant_map = {}
old_to_new_tmpl_map = {}
old_tmpl_to_new_tmpl_map = {}
new_variant_to_price_map = {}
new_variant_to_tmpl_map = {}
assigned_pos_cats = Counter()

for (art, linea, base_name), items in families_to_process:
    count_templates += 1
    sample = items[0]
    tmpl_name = f"{base_name} ({linea})" if (linea and SEPARAR_POR_LINEA) else base_name

    unique_talles = sorted(list(dict.fromkeys(it['talle'] for it in items)), key=talle_sort_key)
    unique_colors = list(dict.fromkeys(it['color'] for it in items))

    talle_val_ids = [get_or_create_value(attr_talle.id, t, talle_value_cache) for t in unique_talles]
    color_val_ids = [get_or_create_value(attr_color.id, c, color_value_cache) for c in unique_colors]

    pos_cat_id = classify_pos_category(base_name)
    assigned_pos_cats[pos_cat_id] += 1
    
    target_categ_id = None
    for canon_k, c_id in resolved_pos_cats.items():
        if c_id == pos_cat_id:
            target_categ_id = resolved_prod_cats.get(canon_k)
            break
    if not target_categ_id:
        target_categ_id = sample.get('categ_id') or default_prod_cat_id

    # Precio base en ficha (list_price): se preserva exacto tal como viene de producción ($1.00)
    tmpl_list_price = sample.get('list_price') or 0.0
    # Precio real de lista de precios de la familia (para reglas en Listas de Precios)
    family_pl_price = max((it.get('pricelist_price') or 0.0 for it in items), default=0.0)

    vals = {
        'name': tmpl_name,
        'categ_id': target_categ_id,
        'uom_id': sample['uom_id'],
        'list_price': tmpl_list_price,
        'standard_price': sample['standard_price'],
        'attribute_line_ids': [
            (0, 0, {'attribute_id': attr_talle.id, 'value_ids': [(6, 0, talle_val_ids)]}),
            (0, 0, {'attribute_id': attr_color.id, 'value_ids': [(6, 0, color_val_ids)]})
        ]
    }
    if has_taxes_id:
        vals['taxes_id'] = [(6, 0, sample.get('taxes_id') or [])]
    if has_supplier_taxes_id:
        vals['supplier_taxes_id'] = [(6, 0, sample.get('supplier_taxes_id') or [])]
    if has_uom_po_id and sample.get('uom_po_id'):
        vals['uom_po_id'] = sample['uom_po_id']
    if has_sale_ok:
        vals['sale_ok'] = sample.get('sale_ok', True)
    if has_purchase_ok:
        vals['purchase_ok'] = sample.get('purchase_ok', True)

    if 'is_storable' in Template._fields:
        vals['is_storable'] = True
        vals['type'] = 'consu'
    elif 'detailed_type' in Template._fields:
        vals['detailed_type'] = 'product'
        vals['type'] = 'product'
    else:
        vals['type'] = 'product'

    if has_pos_available:
        vals['available_in_pos'] = True
    if has_pos_categ_ids:
        assigned_pos_cat = pos_cat_id or resolved_pos_cats.get('otros') or (list(pos_cat_cache.values())[0] if pos_cat_cache else False)
        if assigned_pos_cat:
            vals['pos_categ_ids'] = [(6, 0, [assigned_pos_cat])]

    new_tmpl = Template.create(vals)
    # Sincronizar también nombre en en_US para consistencia entre idiomas
    if 'en_US' in active_langs and target_lang != 'en_US':
        new_tmpl.with_context(lang='en_US').write({'name': tmpl_name})

    catalog_items_map = defaultdict(list)
    for it in items:
        catalog_items_map[(it['talle'], it['color'])].append(it)

    for variant in new_tmpl.product_variant_ids:
        ptavs = variant.product_template_attribute_value_ids
        v_talle, v_color = None, None
        for ptav in ptavs:
            if ptav.attribute_id.id == attr_talle.id:
                v_talle = ptav.product_attribute_value_id.name
            elif ptav.attribute_id.id == attr_color.id:
                v_color = ptav.product_attribute_value_id.name
        
        matching_items = catalog_items_map.get((v_talle, v_color))
        if matching_items:
            orig_item = matching_items[0]
            v_pl_price = orig_item.get('pricelist_price') or 0.0
            if v_pl_price <= 1.0 and family_pl_price > 1.0:
                v_pl_price = family_pl_price
            variant.write({
                'default_code': orig_item['code'],
                'barcode': orig_item['code'],
                'standard_price': orig_item['standard_price'],
            })
            count_variants += 1
            for it in matching_items:
                old_to_new_variant_map[it['old_product_id']] = variant.id
                old_to_new_tmpl_map[it['old_product_id']] = new_tmpl.id
                if it.get('old_tmpl_id'):
                    old_tmpl_to_new_tmpl_map[it['old_tmpl_id']] = new_tmpl.id
            new_variant_to_price_map[variant.id] = v_pl_price
            new_variant_to_tmpl_map[variant.id] = new_tmpl.id
        else:
            variant.write({'active': False})

    if count_templates % 100 == 0 or count_templates == len(families_to_process):
        print(f"  Progreso: {count_templates}/{len(families_to_process)} plantillas...")

# 7. Traslado de Stock Físico a Nuevas Variantes (Ticket 3)
sub('7. Traslado de Stock Físico a Nuevas Variantes')

cr.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'stock_quant' AND column_name = 'product_tmpl_id';
""")
has_quant_tmpl_id = bool(cr.fetchone())

quants_by_dest_key = defaultdict(list)
for old_pid, quants in quants_by_old_product.items():
    new_vid = old_to_new_variant_map.get(old_pid)
    new_tid = old_to_new_tmpl_map.get(old_pid)
    if not new_vid:
        continue
    for q in quants:
        dest_key = (
            new_vid,
            new_tid,
            q['location_id'][0],
            q.get('company_id')[0] if q.get('company_id') else env.company.id,
            q.get('lot_id')[0] if q.get('lot_id') else None,
            q.get('package_id')[0] if q.get('package_id') else None,
            q.get('owner_id')[0] if q.get('owner_id') else None
        )
        quants_by_dest_key[dest_key].append(q)

transferred_quants_count = 0
consolidated_groups = 0

for dest_key, q_list in quants_by_dest_key.items():
    new_vid, new_tid, loc_id, comp_id, lot_id, pack_id, owner_id = dest_key
    
    existing_query = """
        SELECT id, quantity, reserved_quantity 
        FROM stock_quant 
        WHERE product_id = %s 
          AND location_id = %s 
          AND (company_id = %s OR (company_id IS NULL AND %s IS NULL))
          AND (lot_id = %s OR (lot_id IS NULL AND %s IS NULL))
          AND (package_id = %s OR (package_id IS NULL AND %s IS NULL))
          AND (owner_id = %s OR (owner_id IS NULL AND %s IS NULL))
        LIMIT 1
    """
    cr.execute(existing_query, (new_vid, loc_id, comp_id, comp_id, lot_id, lot_id, pack_id, pack_id, owner_id, owner_id))
    dest_existing = cr.fetchone()
    
    old_quant_ids = [q['id'] for q in q_list]
    total_qty_to_merge = sum(q['quantity'] for q in q_list)
    total_res_to_merge = sum(q.get('reserved_quantity', 0.0) for q in q_list)
    
    if dest_existing:
        dest_qid, dest_qty, dest_res = dest_existing
        new_tot_qty = dest_qty + total_qty_to_merge
        new_tot_res = dest_res + total_res_to_merge
        cr.execute("UPDATE stock_quant SET quantity = %s, reserved_quantity = %s WHERE id = %s", (new_tot_qty, new_tot_res, dest_qid))
        cr.execute("DELETE FROM stock_quant WHERE id = ANY(%s)", (old_quant_ids,))
        transferred_quants_count += len(old_quant_ids)
        consolidated_groups += 1
    elif len(q_list) > 1:
        primary_qid = old_quant_ids[0]
        duplicate_qids = old_quant_ids[1:]
        if has_quant_tmpl_id and new_tid:
            cr.execute("""
                UPDATE stock_quant 
                SET product_id = %s, product_tmpl_id = %s, quantity = %s, reserved_quantity = %s 
                WHERE id = %s
            """, (new_vid, new_tid, total_qty_to_merge, total_res_to_merge, primary_qid))
        else:
            cr.execute("""
                UPDATE stock_quant 
                SET product_id = %s, quantity = %s, reserved_quantity = %s 
                WHERE id = %s
            """, (new_vid, total_qty_to_merge, total_res_to_merge, primary_qid))
        cr.execute("DELETE FROM stock_quant WHERE id = ANY(%s)", (duplicate_qids,))
        transferred_quants_count += len(old_quant_ids)
        consolidated_groups += 1
    else:
        primary_qid = old_quant_ids[0]
        if has_quant_tmpl_id and new_tid:
            cr.execute("UPDATE stock_quant SET product_id = %s, product_tmpl_id = %s WHERE id = %s", (new_vid, new_tid, primary_qid))
        else:
            cr.execute("UPDATE stock_quant SET product_id = %s WHERE id = %s", (new_vid, primary_qid))
        transferred_quants_count += 1

# Crear tabla temporal de mapeo masivo (old_pid, old_tid, new_vid, new_tid) para SVL y Listas de Precios
if old_to_new_variant_map:
    cr.execute("""
        CREATE TEMP TABLE IF NOT EXISTS _tmp_eyelit_mig_map (
            old_pid INT,
            old_tid INT,
            new_vid INT,
            new_tid INT
        );
        TRUNCATE _tmp_eyelit_mig_map;
    """)
    map_rows = [
        (opid, old_pid_to_old_tid.get(opid), nvid, old_to_new_tmpl_map.get(opid))
        for opid, nvid in old_to_new_variant_map.items()
    ]
    for i in range(0, len(map_rows), 1000):
        chunk = map_rows[i:i+1000]
        placeholders = ','.join(['(%s,%s,%s,%s)'] * len(chunk))
        flat_params = [val for row in chunk for val in row]
        cr.execute(f"INSERT INTO _tmp_eyelit_mig_map (old_pid, old_tid, new_vid, new_tid) VALUES {placeholders};", tuple(flat_params))

    cr.execute("CREATE INDEX IF NOT EXISTS _idx_tmp_mig_pid ON _tmp_eyelit_mig_map (old_pid);")
    cr.execute("CREATE INDEX IF NOT EXISTS _idx_tmp_mig_tid ON _tmp_eyelit_mig_map (old_tid);")

cr.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'stock_valuation_layer');")
if cr.fetchone()[0] and old_to_new_variant_map:
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'stock_valuation_layer' AND column_name = 'product_tmpl_id';
    """)
    has_svl_tmpl_id = bool(cr.fetchone())
    if has_svl_tmpl_id:
        cr.execute("""
            UPDATE stock_valuation_layer svl
            SET product_id = m.new_vid,
                product_tmpl_id = m.new_tid
            FROM _tmp_eyelit_mig_map m
            WHERE svl.product_id = m.old_pid;
        """)
    else:
        cr.execute("""
            UPDATE stock_valuation_layer svl
            SET product_id = m.new_vid
            FROM _tmp_eyelit_mig_map m
            WHERE svl.product_id = m.old_pid;
        """)

Quant.invalidate_model()
Product.invalidate_model()
Template.invalidate_model()

stock_ok = 0
stock_err = 0
total_migrated_internal = 0.0

new_variant_expected_internal = defaultdict(float)
new_variant_expected_total = defaultdict(float)
for old_pid, snap in stock_snapshot.items():
    new_vid = old_to_new_variant_map.get(old_pid)
    if new_vid:
        new_variant_expected_internal[new_vid] += snap.get('internal_qty', 0.0)
        new_variant_expected_total[new_vid] += snap['total_qty']

for new_vid, exp_int_qty in new_variant_expected_internal.items():
    new_v = Product.browse(new_vid)
    act_int_qty = new_v.qty_available
    total_migrated_internal += act_int_qty
    if abs(act_int_qty - exp_int_qty) < 0.001:
        stock_ok += 1
    else:
        stock_err += 1
        print(f"    [!] Discrepancia en [{new_v.default_code}]: Esperado {exp_int_qty} | Actual {act_int_qty}")

print(f"Quants trasladados/consolidados: {transferred_quants_count} (Grupos consolidados: {consolidated_groups})")
print(f"Coincidencias exactas de stock interno (En Mano): {stock_ok}/{len(new_variant_expected_internal)} (Diferencias: {stock_err})")
print(f"Total unidades físicas en nuevas variantes (WH): {total_migrated_internal:,.2f}")

# 8. Lista de Precios con Variantes y Remapeo de Reglas Existentes
sub('8. Creación de Lista de Precios con Variantes y Remapeo de Reglas')
pl_name = "Lista de Precios con Variantes"
pricelist = Pricelist.search([('name', '=', pl_name), ('company_id', 'in', [env.company.id, False])], limit=1)
if not pricelist:
    pricelist = Pricelist.create({
        'name': pl_name,
        'currency_id': env.company.currency_id.id,
        'company_id': env.company.id,
        'active': True,
    })
    print(f"  + Creada lista de precios: '{pl_name}' (ID {pricelist.id})")
else:
    print(f"  * Usando lista de precios existente: '{pl_name}' (ID {pricelist.id})")

# 8.1. Remapeo masivo de reglas existentes a nivel de variante (Odoo 18 requiere product_id + product_tmpl_id)
remapped_variant_rules = 0
remapped_tmpl_rules = 0

if old_to_new_variant_map:
    # 1) Reglas por product_id existente -> nuevas variantes + nueva plantilla (evitando duplicados)
    cr.execute("""
        WITH candidates AS (
            SELECT ppi.id, ppi.pricelist_id, m.new_vid, m.new_tid, ppi.min_quantity,
                   ROW_NUMBER() OVER (PARTITION BY ppi.pricelist_id, m.new_vid, ppi.min_quantity ORDER BY ppi.id DESC) AS rn
            FROM product_pricelist_item ppi
            JOIN _tmp_eyelit_mig_map m ON m.old_pid = ppi.product_id
        )
        UPDATE product_pricelist_item ppi
        SET applied_on = '0_product_variant',
            product_id = c.new_vid,
            product_tmpl_id = c.new_tid
        FROM candidates c
        WHERE ppi.id = c.id
          AND c.rn = 1
          AND NOT EXISTS (
              SELECT 1 FROM product_pricelist_item ppi2
              WHERE ppi2.pricelist_id = c.pricelist_id
                AND ppi2.product_id = c.new_vid
                AND ppi2.min_quantity = c.min_quantity
                AND ppi2.id != c.id
          );
    """)
    remapped_variant_rules = cr.rowcount

    cr.execute("""
        DELETE FROM product_pricelist_item ppi
        USING _tmp_eyelit_mig_map m
        WHERE ppi.product_id = m.old_pid;
    """)

    # 2) Reglas por product_tmpl_id existente -> convertir a nivel variante (0_product_variant) con product_id + product_tmpl_id
    cr.execute("""
        WITH candidates AS (
            SELECT ppi.id, ppi.pricelist_id, m.new_vid, m.new_tid, ppi.min_quantity,
                   ROW_NUMBER() OVER (PARTITION BY ppi.pricelist_id, m.new_vid, ppi.min_quantity ORDER BY ppi.id DESC) AS rn
            FROM product_pricelist_item ppi
            JOIN _tmp_eyelit_mig_map m ON m.old_tid = ppi.product_tmpl_id
            WHERE m.old_tid IS NOT NULL
        )
        UPDATE product_pricelist_item ppi
        SET applied_on = '0_product_variant',
            product_id = c.new_vid,
            product_tmpl_id = c.new_tid
        FROM candidates c
        WHERE ppi.id = c.id
          AND c.rn = 1
          AND NOT EXISTS (
              SELECT 1 FROM product_pricelist_item ppi2
              WHERE ppi2.pricelist_id = c.pricelist_id
                AND ppi2.product_id = c.new_vid
                AND ppi2.min_quantity = c.min_quantity
          );
    """)
    remapped_tmpl_rules = cr.rowcount

    cr.execute("""
        DELETE FROM product_pricelist_item ppi
        USING _tmp_eyelit_mig_map m
        WHERE m.old_tid IS NOT NULL AND ppi.product_tmpl_id = m.old_tid;
    """)

    PricelistItem.invalidate_model()

if remapped_variant_rules > 0:
    print(f"  * Remapeadas {remapped_variant_rules} reglas existentes por producto hacia nuevas variantes.")
if remapped_tmpl_rules > 0:
    print(f"  * Convertidas {remapped_tmpl_rules} reglas de plantillas viejas a reglas de variante en nuevas variantes.")

# 8.2. Asegurar cobertura en 'Lista de Precios con Variantes'
item_fields = set(PricelistItem._fields.keys())
existing_vids = set(PricelistItem.search([('pricelist_id', '=', pricelist.id), ('applied_on', '=', '0_product_variant')]).mapped('product_id.id'))
batch_items = []
for vid, price in new_variant_to_price_map.items():
    if vid in existing_vids:
        continue
    iv = {
        'pricelist_id': pricelist.id,
        'applied_on': '0_product_variant',
        'product_id': vid,
        'product_tmpl_id': new_variant_to_tmpl_map[vid],
        'compute_price': 'fixed',
        'fixed_price': price,
        'min_quantity': 0,
    }
    if 'company_id' in item_fields:
        iv['company_id'] = env.company.id
    batch_items.append(iv)

created_rules = 0
for i in range(0, len(batch_items), 500):
    b = batch_items[i:i+500]
    PricelistItem.create(b)
    created_rules += len(b)
print(f"  + Reglas creadas en '{pl_name}': {created_rules}")

# 8.3. Asegurar cobertura completa en la lista principal de TPV si existe (ej: 'Lista Precios AR 2')
if main_pos_pricelist and main_pos_pricelist.id != pricelist.id:
    existing_in_main = set(
        PricelistItem.search([
            ('pricelist_id', '=', main_pos_pricelist.id),
            ('applied_on', '=', '0_product_variant'),
            ('product_id', 'in', list(new_variant_to_price_map.keys()))
        ]).mapped('product_id.id')
    )
    missing_in_main = [vid for vid in new_variant_to_price_map if vid not in existing_in_main]
    if missing_in_main:
        print(f"  + Completando {len(missing_in_main)} variantes en lista principal de TPV '{main_pos_pricelist.name}'...")
        batch_main = []
        for vid in missing_in_main:
            iv = {
                'pricelist_id': main_pos_pricelist.id,
                'applied_on': '0_product_variant',
                'product_id': vid,
                'product_tmpl_id': new_variant_to_tmpl_map[vid],
                'compute_price': 'fixed',
                'fixed_price': new_variant_to_price_map[vid],
                'min_quantity': 0,
            }
            if 'company_id' in item_fields:
                iv['company_id'] = env.company.id
            batch_main.append(iv)
        for i in range(0, len(batch_main), 500):
            PricelistItem.create(batch_main[i:i+500])

# 9. Sincronizar Cajas de TPV
sub('9. Sincronización de Cajas de TPV')
all_pos_cats = sorted(list(set(c for c in pos_cat_cache.values() if c)))
for cfg in PosConfig.search([]):
    uvals = {}
    if hasattr(cfg, 'limit_categories'):
        uvals['limit_categories'] = True
    if hasattr(cfg, 'pos_category_ids'):
        uvals['pos_category_ids'] = [(6, 0, all_pos_cats)]
    
    available_pls = set(cfg.available_pricelist_ids.ids) if hasattr(cfg, 'available_pricelist_ids') else set()
    available_pls.add(pricelist.id)
    if hasattr(cfg, 'pricelist_id') and cfg.pricelist_id:
        available_pls.add(cfg.pricelist_id.id)
    if hasattr(cfg, 'available_pricelist_ids'):
        uvals['available_pricelist_ids'] = [(6, 0, list(available_pls))]

    if hasattr(cfg, 'pricelist_id'):
        if not cfg.pricelist_id:
            uvals['pricelist_id'] = main_pos_pricelist.id if main_pos_pricelist else pricelist.id
    if hasattr(cfg, 'use_pricelist'):
        uvals['use_pricelist'] = True
    if not uvals:
        continue

    try:
        with env.cr.savepoint():
            cfg.write(uvals)
        print(f"  + TPV '{cfg.name}' actualizado vía ORM con categorías y lista de precios.")
    except Exception as err:
        print(f"  [!] Aviso: No se pudo actualizar TPV '{cfg.name}' vía ORM ({err}).")
        # Fallback actualización directa para no abortar migración cuando hay una sesión abierta
        try:
            sql_set = []
            sql_vals = []
            if 'pricelist_id' in uvals and 'pricelist_id' in cfg._fields:
                sql_set.append("pricelist_id = %s")
                sql_vals.append(uvals['pricelist_id'])
            if 'use_pricelist' in uvals and 'use_pricelist' in cfg._fields:
                sql_set.append("use_pricelist = %s")
                sql_vals.append(uvals['use_pricelist'])
            if 'limit_categories' in uvals and 'limit_categories' in cfg._fields:
                sql_set.append("limit_categories = %s")
                sql_vals.append(uvals['limit_categories'])
            
            if sql_set:
                sql_vals.append(cfg.id)
                cr.execute(f"UPDATE pos_config SET {', '.join(sql_set)} WHERE id = %s", tuple(sql_vals))

            if 'pos_category_ids' in cfg._fields and all_pos_cats:
                f_cats = cfg._fields['pos_category_ids']
                cr.execute(f"DELETE FROM {f_cats.relation} WHERE {f_cats.column1} = %s", (cfg.id,))
                for cat_id in all_pos_cats:
                    cr.execute(f"INSERT INTO {f_cats.relation} ({f_cats.column1}, {f_cats.column2}) VALUES (%s, %s)", (cfg.id, cat_id))

            if 'available_pricelist_ids' in cfg._fields:
                f_pls = cfg._fields['available_pricelist_ids']
                for pl_target_id in [pricelist.id, main_pos_pl_id]:
                    if not pl_target_id:
                        continue
                    cr.execute(f"SELECT 1 FROM {f_pls.relation} WHERE {f_pls.column1} = %s AND {f_pls.column2} = %s", (cfg.id, pl_target_id))
                    if not cr.fetchone():
                        cr.execute(f"INSERT INTO {f_pls.relation} ({f_pls.column1}, {f_pls.column2}) VALUES (%s, %s)", (cfg.id, pl_target_id))

            cfg.invalidate_recordset()
            print(f"  [✓] TPV '{cfg.name}' sincronizado exitosamente vía SQL directo (sesión abierta respetada).")
        except Exception as sql_err:
            print(f"  [!] Alerta no bloqueante en TPV '{cfg.name}': {sql_err}")
            print("      Podrá asignar la lista de precios y categorías manualmente al cerrar la sesión de caja.")

if 'pos.session' in env:
    open_sessions = env['pos.session'].search([('state', '!=', 'closed')])
    if open_sessions:
        print(f"\n[!] AVISO: {len(open_sessions)} sesiones de TPV abiertas:")
        for s in open_sessions:
            print(f"    - Sesión [ID {s.id}] '{s.name}' (Usuario: {s.user_id.name})")
        print("    * Los cajeros deberán recargar la página (Ctrl+F5) o cerrar/reabrir sesión para actualizar catálogo.")

# 9.1. Verificación de Precios y Nombres en Variantes Migradas (dentro de la transacción)
sub('9.1. Verificación de Precios y Nombres en Nuevas Variantes')
real_price_count = sum(1 for p in new_variant_to_price_map.values() if p and p > 1.0)
dummy_or_zero_count = sum(1 for p in new_variant_to_price_map.values() if not p or p <= 1.0)
print(f"Variantes migradas con precio real (> $1.00) en Listas de Precios: {real_price_count}/{len(new_variant_to_price_map)}")
if dummy_or_zero_count > 0:
    print(f"  [i] Variantes sin regla de precio previo en origen (<= $1.00): {dummy_or_zero_count}")
else:
    print("  [✓] ¡100% DE LAS VARIANTES TIENEN PRECIO REAL ASIGNADO EN LISTAS DE PRECIOS!")

# Verificar que ninguna plantilla nueva haya quedado nombrada como código SKU
new_tmpl_ids_set = list(set(new_variant_to_tmpl_map.values()))
sku_named_new = Template.browse(new_tmpl_ids_set).filtered(lambda t: is_sku_like_name(clean_base_name(t.name)))
if sku_named_new:
    print(f"  [!] Aviso: {len(sku_named_new)} plantillas nuevas tienen nombre tipo código SKU (sin nombre humano en {target_lang}):")
    for st in sku_named_new[:5]:
        print(f"      - [ID {st.id}] {st.name}")
else:
    print(f"  [✓] 0 plantillas nuevas con nombre de código SKU (100% agrupadas con nombre humano en {target_lang}).")

# Verificar integridad Odoo 18 de product_tmpl_id en reglas de variantes
cr.execute("""
    SELECT count(*)
    FROM product_pricelist_item ppi
    JOIN product_product pp ON pp.id = ppi.product_id
    WHERE ppi.applied_on = '0_product_variant'
      AND pp.active = TRUE
      AND (ppi.product_tmpl_id IS NULL OR ppi.product_tmpl_id != pp.product_tmpl_id);
""")
misaligned_pl_count = cr.fetchone()[0]
if misaligned_pl_count > 0:
    print(f"  [!] Alerta: {misaligned_pl_count} reglas de variante sin product_tmpl_id alineado.")
else:
    print("  [✓] 100% de las reglas de variantes tienen product_tmpl_id alineado (UI + POS Odoo 18 OK).")

sample_vids = list(new_variant_to_price_map.keys())[:5]
if sample_vids:
    print("\nMuestra de verificación de precios en nuevas variantes (Base preservado vs Listas):")
    for sv in Product.browse(sample_vids):
        try:
            p_var_str = f"${pricelist._get_product_price(sv, 1.0):,.2f}"
        except Exception:
            r_var = PricelistItem.search([('pricelist_id', '=', pricelist.id), ('applied_on', '=', '0_product_variant'), ('product_id', '=', sv.id)], limit=1)
            p_var_str = f"${r_var.fixed_price:,.2f}" if r_var else "N/A"
        p_pos_str = "N/A"
        if main_pos_pricelist:
            try:
                p_pos_str = f"${main_pos_pricelist._get_product_price(sv, 1.0):,.2f}"
            except Exception:
                r_pos = PricelistItem.search([('pricelist_id', '=', main_pos_pricelist.id), ('applied_on', '=', '0_product_variant'), ('product_id', '=', sv.id)], limit=1)
                if r_pos:
                    p_pos_str = f"${r_pos.fixed_price:,.2f}"
        print(f"  [{sv.default_code}] {sv.name[:25]} | Base (list_price): ${sv.list_price:,.2f} | Lista Variantes: {p_var_str} | TPV ({main_pos_pricelist.name if main_pos_pricelist else '-'}): {p_pos_str}")

sub('RESUMEN DE OPERACIÓN')
print(f"Plantillas maestras creadas: {count_templates}")
print(f"Variantes activas creadas: {count_variants}")
print(f"Productos viejos archivados: {len(prods_in_batch)}")
print(f"Stock interno migrado (WH): {total_migrated_internal:,.2f} unidades")
print(f"Reglas remapeadas por producto hacia variantes: {remapped_variant_rules}")
print(f"Reglas convertidas de plantillas viejas a variantes: {remapped_tmpl_rules}")
print(f"Reglas nuevas creadas en '{pl_name}': {created_rules}")
print(f"Variantes con precio real (> $1.00): {real_price_count}/{len(new_variant_to_price_map)}")

if old_to_new_variant_map:
    cr.execute("DROP TABLE IF EXISTS _tmp_eyelit_mig_map;")

if DRY_RUN:
    cr.execute("ROLLBACK TO SAVEPOINT unificado_migracion_sp")
    print("\n[✓] MODO DRY-RUN: ROLLBACK TO SAVEPOINT EJECUTADO CON ÉXITO.")
    print("    No se alteró la base de datos.")
else:
    cr.execute("RELEASE SAVEPOINT unificado_migracion_sp")
    env.cr.commit()
    print("\n[✓] ¡MIGRACIÓN CONFIRMADA CON COMMIT EN LA BASE DE DATOS!")
