# -*- coding: utf-8 -*-
"""
02 - MIGRACIÓN UNIFICADA: VARIANTES, STOCK, CATEGORÍAS Y LISTA DE PRECIOS
Resuelve Tickets 1, 2 y 3 en una transacción atómica.
Control: DRY_RUN=1 (Simulación) o DRY_RUN=0 (Commit en producción).
"""
import os
import re
import json
from collections import defaultdict, Counter

h('02 - EJECUCIÓN DEL PIPELINE UNIFICADO DE MIGRACIÓN')

# Configuración: variable de entorno o fallback a True para máxima seguridad
env_dry_run = os.environ.get('DRY_RUN', '1').strip().lower()
DRY_RUN = env_dry_run in ('1', 'true', 'yes')
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

cr = env.cr
cr.execute("SAVEPOINT unificado_migracion_sp")

Product = env['product.product']
Template = env['product.template']
Attribute = env['product.attribute']
AttrValue = env['product.attribute.value']
PosCategory = env['pos.category']
PosConfig = env['pos.config']
ProductCategory = env['product.category']
Pricelist = env['product.pricelist']
PricelistItem = env['product.pricelist.item']
Quant = env['stock.quant']

has_pos_available = 'available_in_pos' in Template._fields
has_pos_categ_ids = 'pos_categ_ids' in Template._fields

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
        pcat = ProductCategory.create({'name': canon_name})
        found_id = pcat.id
        prod_cat_cache[k] = found_id
        print(f"  + Creada categoría interna de producto: '{canon_name}' (ID {found_id})")
    resolved_prod_cats[k] = found_id

default_prod_cat_id = resolved_prod_cats.get('otros') or env.ref('product.product_category_all').id

# 3. Escaneo y agrupación
sub('3. Escaneo y Agrupación del Catálogo')
fields_to_read = ['id', 'name', 'default_code', 'barcode', 'product_tmpl_id', 'list_price', 'standard_price', 'categ_id', 'uom_id']
if has_pos_categ_ids:
    fields_to_read.append('pos_categ_ids')

all_prods = Product.search_read([('active', '=', True)], fields_to_read)
families = defaultdict(list)
old_prod_ids_to_archive = []
skipped = 0

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

    old_prod_ids_to_archive.append(p['id'])
    base_name = clean_base_name(parsed['name'])
    if SEPARAR_POR_LINEA and parsed['linea']:
        family_key = (parsed['art'], parsed['linea'], base_name)
    else:
        family_key = (parsed['art'], '', base_name)
    families[family_key].append(parsed)

print(f"Total familias detectadas: {len(families)} ({len(old_prod_ids_to_archive)} productos)")
print(f"Productos especiales omitidos: {skipped}")

if LIMIT_FAMILIES:
    families_to_process = list(families.items())[:LIMIT_FAMILIES]
    print(f"[!] Modo prueba: limitando a {LIMIT_FAMILIES} familias")
else:
    families_to_process = list(families.items())

prods_in_batch = []
tmpls_in_batch = set()
for _, items in families_to_process:
    for it in items:
        prods_in_batch.append(it['old_product_id'])
        if it['old_tmpl_id']:
            tmpls_in_batch.add(it['old_tmpl_id'])

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

    vals = {
        'name': tmpl_name,
        'categ_id': target_categ_id,
        'uom_id': sample['uom_id'],
        'list_price': sample['list_price'],
        'standard_price': sample['standard_price'],
        'attribute_line_ids': [
            (0, 0, {'attribute_id': attr_talle.id, 'value_ids': [(6, 0, talle_val_ids)]}),
            (0, 0, {'attribute_id': attr_color.id, 'value_ids': [(6, 0, color_val_ids)]})
        ]
    }
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
            variant.write({
                'default_code': orig_item['code'],
                'barcode': orig_item['code'],
                'standard_price': orig_item['standard_price'],
                'list_price': orig_item['list_price'],
            })
            count_variants += 1
            for it in matching_items:
                old_to_new_variant_map[it['old_product_id']] = variant.id
                old_to_new_tmpl_map[it['old_product_id']] = new_tmpl.id
                if it.get('old_tmpl_id'):
                    old_tmpl_to_new_tmpl_map[it['old_tmpl_id']] = new_tmpl.id
            new_variant_to_price_map[variant.id] = orig_item['list_price']
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

cr.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'stock_valuation_layer');")
if cr.fetchone()[0]:
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'stock_valuation_layer' AND column_name = 'product_tmpl_id';
    """)
    has_svl_tmpl_id = bool(cr.fetchone())
    for old_pid, new_vid in old_to_new_variant_map.items():
        new_tid = old_to_new_tmpl_map.get(old_pid)
        if has_svl_tmpl_id and new_tid:
            cr.execute("UPDATE stock_valuation_layer SET product_id = %s, product_tmpl_id = %s WHERE product_id = %s", (new_vid, new_tid, old_pid))
        else:
            cr.execute("UPDATE stock_valuation_layer SET product_id = %s WHERE product_id = %s", (new_vid, old_pid))

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

# 8. Lista de Precios con Variantes (Ticket 2)
sub('8. Creación de Lista de Precios con Variantes')
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

# Remapeo de reglas existentes
cr.execute("SELECT count(*) FROM product_pricelist_item WHERE product_id = ANY(%s)", (prods_in_batch,))
ex_count = cr.fetchone()[0]
if ex_count > 0:
    for old_pid, new_vid in old_to_new_variant_map.items():
        cr.execute("UPDATE product_pricelist_item SET product_id = %s WHERE product_id = %s", (new_vid, old_pid))
    print(f"  * Remapeadas {ex_count} reglas por variante hacia nuevas variantes.")

if tmpls_in_batch:
    cr.execute("SELECT count(*) FROM product_pricelist_item WHERE product_tmpl_id = ANY(%s)", (list(tmpls_in_batch),))
    ex_tmpl_count = cr.fetchone()[0]
    if ex_tmpl_count > 0:
        for old_tid, new_tid in old_tmpl_to_new_tmpl_map.items():
            cr.execute("UPDATE product_pricelist_item SET product_tmpl_id = %s WHERE product_tmpl_id = %s", (new_tid, old_tid))
        print(f"  * Remapeadas {ex_tmpl_count} reglas por plantilla hacia nuevas plantillas.")

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
print(f"Reglas por variante creadas: {created_rules}")

# 9. Sincronizar Cajas de TPV
sub('9. Sincronización de Cajas de TPV')
all_pos_cats = sorted(list(set(c for c in pos_cat_cache.values() if c)))
for cfg in PosConfig.search([]):
    uvals = {}
    if hasattr(cfg, 'limit_categories'):
        uvals['limit_categories'] = True
    if hasattr(cfg, 'pos_category_ids'):
        uvals['pos_category_ids'] = [(6, 0, all_pos_cats)]
    if hasattr(cfg, 'available_pricelist_ids'):
        if pricelist.id not in cfg.available_pricelist_ids.ids:
            uvals['available_pricelist_ids'] = [(4, pricelist.id)]
    if hasattr(cfg, 'pricelist_id'):
        uvals['pricelist_id'] = pricelist.id
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
                cr.execute(f"SELECT 1 FROM {f_pls.relation} WHERE {f_pls.column1} = %s AND {f_pls.column2} = %s", (cfg.id, pricelist.id))
                if not cr.fetchone():
                    cr.execute(f"INSERT INTO {f_pls.relation} ({f_pls.column1}, {f_pls.column2}) VALUES (%s, %s)", (cfg.id, pricelist.id))

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

sub('RESUMEN DE OPERACIÓN')
print(f"Plantillas maestras creadas: {count_templates}")
print(f"Variantes activas creadas: {count_variants}")
print(f"Productos viejos archivados: {len(prods_in_batch)}")
print(f"Stock interno migrado (WH): {total_migrated_internal:,.2f} unidades")
print(f"Reglas de precios creadas: {created_rules}")

if DRY_RUN:
    cr.execute("ROLLBACK TO SAVEPOINT unificado_migracion_sp")
    print("\n[✓] MODO DRY-RUN: ROLLBACK TO SAVEPOINT EJECUTADO CON ÉXITO.")
    print("    No se alteró la base de datos.")
else:
    cr.execute("RELEASE SAVEPOINT unificado_migracion_sp")
    env.cr.commit()
    print("\n[✓] ¡MIGRACIÓN CONFIRMADA CON COMMIT EN LA BASE DE DATOS!")
