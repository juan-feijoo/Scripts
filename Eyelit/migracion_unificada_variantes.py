# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT UNIFICADO DEFINITIVO: MIGRACIÓN A VARIANTES, STOCK, CATEGORÍAS Y PRECIOS
Versión compatible: Odoo 17.0+e, 18.0+e y 19.0+e (Enterprise / Odoo.sh)
Cliente: Eyelit Argentina
================================================================================

TICKETS RESUELTOS EN ESTE PIPELINE UNIFICADO:
--------------------------------------------------------------------------------
1. Crear variantes de productos & Categorías:
   - Extracción de stock a la fecha antes de archivar.
   - Liberación de códigos de barra (sufijo '_OLD' idempotente) y archivado de viejos productos.
   - Creación nativa vía ORM de plantillas y variantes con Talle y Color normalizados y orden natural.
   - Limpieza de nombres duplicados tipo '(P0A) (P0A)'.
   - Configuración de categorías de producto (product.category) y de TPV (pos.category) con sinónimos.
   - Configuración de cajas registradoras (pos.config) con las categorías activas.

2. Lista de precios para productos con variantes:
   - Creación/actualización de la lista 'Lista de Precios con Variantes'.
   - Remapeo de reglas existentes de productos viejos a las nuevas variantes (a nivel variante y plantilla).
   - Generación de reglas por variante ('0_product_variant') con precio real y min_quantity=0.
   - Asignación de la lista de precios a los puntos de venta (pos.config) como pricelist_id por defecto.

3. Stock de productos:
   - Registro y snapshot de auditoría de stock antes de archivar (/tmp/stock_snapshot_eyelit_pre_migration.json).
   - Traslado y consolidación atómica de quants (stock.quant) previniendo colisiones de unicidad en PostgreSQL.
   - Actualización sincronizada de product_tmpl_id en stock_quant para habilitar el smart button de stock.
   - Actualización de capas de valoración (stock.valuation.layer) a nivel variante y plantilla.
   - Validación y verificación automática de cantidades pre vs post migración.

SEGURIDAD Y CONTROL TRANSACCIONAL:
--------------------------------------------------------------------------------
- DRY_RUN = True  : Simulación con SAVEPOINT y ROLLBACK garantizado (base intacta).
- DRY_RUN = False : Confirmación definitiva con COMMIT.
================================================================================
"""

import sys
import os
import re
import json
import logging
from collections import defaultdict, Counter

_logger = logging.getLogger('odoo.migracion.eyelit.unificada')

# ==============================================================================
# CONFIGURACIÓN GENERAL
# ==============================================================================
env_dry_run = os.environ.get('DRY_RUN', '').strip().lower()
if env_dry_run in ('0', 'false', 'no'):
    DRY_RUN = False
else:
    DRY_RUN = True               # True por defecto: Simulación con ROLLBACK | False: Escritura con COMMIT

SEPARAR_POR_LINEA = True     # True: Diferencia canal Web (P0W) vs Tradicional (P0A)
LIMIT_FAMILIES = int(os.environ.get('LIMIT_FAMILIES', '0')) or None # None para todas (811 familias). Número entero para prueba piloto (ej: 10)

# Exportación de respaldo de stock antes de archivar
EXPORT_STOCK_JSON = True
STOCK_BACKUP_PATH = '/tmp/stock_snapshot_eyelit_pre_migration.json'

print("=" * 100)
print(" PIPELINE UNIFICADO: VARIANTES, STOCK, CATEGORÍAS Y LISTAS DE PRECIOS - EYELIT")
print(f" MODO: {'*** SIMULACIÓN DRY-RUN (ROLLBACK FINAL) ***' if DRY_RUN else '*** PRODUCCIÓN (COMMIT DEFINITIVO) ***'}")
print(f" BASE DE DATOS: {env.cr.dbname}")
print(f" COMPAÑÍA: {env.company.name} (ID: {env.company.id})")
print(f" LÍMITE: {LIMIT_FAMILIES if LIMIT_FAMILIES else 'TODAS LAS FAMILIAS'}")
print("=" * 100)

# ==============================================================================
# NORMALIZACIÓN Y PARSEO
# ==============================================================================
TALLE_MAP = {
    'XS0': 'XS', 'S00': 'S', 'M00': 'M', 'L00': 'L', 'XL0': 'XL', 'XXL': 'XXL',
    '3XL': '3XL', '4XL': '4XL', '5XL': '5XL', '6XL': '6XL',
    '000': 'U', # Talle Único
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
    """Elimina etiquetas repetidas de línea al final del nombre tipo '(P0A)'."""
    n = (name or '').strip()
    return re.sub(r'(\s*\([A-Z0-9]+\))+\s*$', '', n).strip()

# ==============================================================================
# PASO 0: CONTROL TRANSACCIONAL (SAVEPOINT)
# ==============================================================================
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

# ==============================================================================
# PASO 1: ATRIBUTOS GLOBALES 'Talle' Y 'Color'
# ==============================================================================
print("\n[PASO 1/7] Configurando Atributos Globales 'Talle' y 'Color'...")
attr_talle = Attribute.search([('name', '=ilike', 'Talle')], limit=1)
if not attr_talle:
    attr_talle = Attribute.create({
        'name': 'Talle',
        'display_type': 'pills',
        'create_variant': 'always',
    })
    print(f"  + Creado atributo: 'Talle' (ID {attr_talle.id})")
else:
    if attr_talle.create_variant != 'always':
        attr_talle.write({'create_variant': 'always', 'display_type': 'pills'})
    print(f"  * Atributo existente: 'Talle' (ID {attr_talle.id})")

attr_color = Attribute.search([('name', '=ilike', 'Color')], limit=1)
if not attr_color:
    attr_color = Attribute.create({
        'name': 'Color',
        'display_type': 'select',
        'create_variant': 'always',
    })
    print(f"  + Creado atributo: 'Color' (ID {attr_color.id})")
else:
    if attr_color.create_variant != 'always':
        attr_color.write({'create_variant': 'always', 'display_type': 'select'})
    print(f"  * Atributo existente: 'Color' (ID {attr_color.id})")

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

# ==============================================================================
# PASO 2: GESTIÓN DE CATEGORÍAS CON RESOLUCIÓN DE SINÓNIMOS
# ==============================================================================
print("\n[PASO 2/7] Verificando Categorías de TPV y de Producto...")

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

# Categorías internas (product.category)
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

# ==============================================================================
# PASO 3: ESCANEO DEL CATÁLOGO ACTUAL Y AGRUPACIÓN
# ==============================================================================
print("\n[PASO 3/7] Escaneando catálogo de productos activos...")

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

total_families = len(families)
print(f"  * Total Familias detectadas: {total_families} ({len(old_prod_ids_to_archive)} productos)")
print(f"  * Productos especiales que se mantienen intactos: {skipped}")

if LIMIT_FAMILIES:
    families_to_process = list(families.items())[:LIMIT_FAMILIES]
    print(f"  [!] Modo prueba activo: procesando {LIMIT_FAMILIES} familias.")
else:
    families_to_process = list(families.items())

prods_in_batch = []
tmpls_in_batch = set()
for _, items in families_to_process:
    for it in items:
        prods_in_batch.append(it['old_product_id'])
        if it['old_tmpl_id']:
            tmpls_in_batch.add(it['old_tmpl_id'])

# ==============================================================================
# PASO 4: EXTRACCIÓN Y RESPALDO DE STOCK A LA FECHA (TICKETS 1 & 3)
# ==============================================================================
print(f"\n[PASO 4/7] Extrayendo stock a la fecha antes de archivar ({len(prods_in_batch)} productos)...")

cr.execute("SELECT id FROM stock_location WHERE usage = 'internal'")
internal_loc_ids = {r[0] for r in cr.fetchall()}

stock_quants_raw = Quant.search_read(
    [('product_id', 'in', prods_in_batch), ('quantity', '!=', 0)],
    ['id', 'product_id', 'location_id', 'quantity', 'reserved_quantity', 'lot_id', 'package_id', 'company_id', 'owner_id']
)

stock_snapshot = {}
quants_by_old_product = defaultdict(list)
total_stock_units_initial = 0.0
total_internal_units_initial = 0.0

for q in stock_quants_raw:
    old_pid = q['product_id'][0]
    loc_id = q['location_id'][0]
    loc_name = q['location_id'][1]
    qty = q['quantity']
    res_qty = q.get('reserved_quantity', 0.0)
    is_internal = loc_id in internal_loc_ids
    
    quants_by_old_product[old_pid].append(q)
    total_stock_units_initial += qty
    if is_internal:
        total_internal_units_initial += qty
    
    if old_pid not in stock_snapshot:
        stock_snapshot[old_pid] = {
            'old_product_id': old_pid,
            'total_qty': 0.0,
            'internal_qty': 0.0,
            'total_reserved': 0.0,
            'locations': defaultdict(float),
            'quants_count': 0
        }
    stock_snapshot[old_pid]['total_qty'] += qty
    if is_internal:
        stock_snapshot[old_pid]['internal_qty'] += qty
    stock_snapshot[old_pid]['total_reserved'] += res_qty
    stock_snapshot[old_pid]['locations'][loc_name] += qty
    stock_snapshot[old_pid]['quants_count'] += 1

print(f"  * Quants con stock positivo o negativo encontrados: {len(stock_quants_raw)}")
print(f"  * Productos con stock activo: {len(stock_snapshot)}")
print(f"  * Total de unidades físicas en existencias internas (WH): {total_internal_units_initial:,.2f}")
print(f"  * Total balance neto en todas las ubicaciones (incluye partners): {total_stock_units_initial:,.2f}")

if EXPORT_STOCK_JSON and stock_snapshot:
    try:
        serializable_snapshot = {
            str(pid): {
                'old_product_id': d['old_product_id'],
                'total_qty': d['total_qty'],
                'total_reserved': d['total_reserved'],
                'locations': dict(d['locations']),
                'quants_count': d['quants_count']
            } for pid, d in stock_snapshot.items()
        }
        with open(STOCK_BACKUP_PATH, 'w', encoding='utf-8') as f:
            json.dump(serializable_snapshot, f, indent=2, ensure_ascii=False)
        print(f"  [✓] Respaldo de stock guardado en: {STOCK_BACKUP_PATH}")
    except Exception as e:
        print(f"  [AVISO] No se pudo escribir JSON de respaldo: {e}")

# ==============================================================================
# PASO 5: LIBERACIÓN DE CÓDIGOS DE BARRA Y ARCHIVADO (IDEMPOTENTE)
# ==============================================================================
print(f"\n[PASO 5/7] Liberando códigos de barra y archivando {len(prods_in_batch)} productos viejos...")

cr.execute("""
    UPDATE product_product 
    SET barcode = barcode || '_OLD'
    WHERE id = ANY(%s) 
      AND barcode IS NOT NULL 
      AND barcode NOT LIKE '%%_OLD'
""", (prods_in_batch,))

cr.execute("""
    UPDATE product_product 
    SET active = FALSE
    WHERE id = ANY(%s)
""", (prods_in_batch,))

if tmpls_in_batch:
    cr.execute("""
        UPDATE product_template 
        SET active = FALSE
        WHERE id = ANY(%s)
    """, (list(tmpls_in_batch),))

Product.invalidate_model()
Template.invalidate_model()
print("  * Códigos de barra liberados y productos viejos archivados exitosamente.")

# ==============================================================================
# PASO 6: CREACIÓN NATIVA DE PLANTILLAS Y VARIANTES (ORM ODOO 18)
# ==============================================================================
print("\n[PASO 6/7] Creando nuevas plantillas nativas y configurando variantes...")

count_created_templates = 0
count_created_variants = 0
total_to_process = len(families_to_process)

old_to_new_variant_map = {}
old_to_new_tmpl_map = {}
old_tmpl_to_new_tmpl_map = {}
new_variant_to_price_map = {}
assigned_pos_cats_counter = Counter()
assigned_prod_cats_counter = Counter()

for (art, linea, base_name), items in families_to_process:
    count_created_templates += 1
    sample = items[0]
    
    tmpl_name = f"{base_name} ({linea})" if (linea and SEPARAR_POR_LINEA) else base_name

    # Talles ordenados de forma natural (U, XS, S, M, L, XL... o numérico)
    unique_talles = sorted(list(dict.fromkeys(it['talle'] for it in items)), key=talle_sort_key)
    unique_colors = list(dict.fromkeys(it['color'] for it in items))

    talle_val_ids = [get_or_create_value(attr_talle.id, t, talle_value_cache) for t in unique_talles]
    color_val_ids = [get_or_create_value(attr_color.id, c, color_value_cache) for c in unique_colors]

    pos_cat_id = classify_pos_category(base_name)
    assigned_pos_cats_counter[pos_cat_id] += 1

    target_categ_id = None
    for canon_k, c_id in resolved_pos_cats.items():
        if c_id == pos_cat_id:
            target_categ_id = resolved_prod_cats.get(canon_k)
            break
    if not target_categ_id:
        target_categ_id = sample.get('categ_id') or default_prod_cat_id
    assigned_prod_cats_counter[target_categ_id] += 1

    template_vals = {
        'name': tmpl_name,
        'categ_id': target_categ_id,
        'uom_id': sample['uom_id'],
        'list_price': sample['list_price'],
        'standard_price': sample['standard_price'],
        'attribute_line_ids': [
            (0, 0, {
                'attribute_id': attr_talle.id,
                'value_ids': [(6, 0, talle_val_ids)]
            }),
            (0, 0, {
                'attribute_id': attr_color.id,
                'value_ids': [(6, 0, color_val_ids)]
            })
        ]
    }

    if 'is_storable' in Template._fields:
        template_vals['is_storable'] = True
        template_vals['type'] = 'consu'
    elif 'detailed_type' in Template._fields:
        template_vals['detailed_type'] = 'product'
        template_vals['type'] = 'product'
    else:
        template_vals['type'] = 'product'

    if has_pos_available:
        template_vals['available_in_pos'] = True
    
    if has_pos_categ_ids:
        assigned_pos_cat = pos_cat_id or resolved_pos_cats.get('otros') or (list(pos_cat_cache.values())[0] if pos_cat_cache else False)
        if assigned_pos_cat:
            template_vals['pos_categ_ids'] = [(6, 0, [assigned_pos_cat])]

    new_template = Template.create(template_vals)

    # Agrupar productos viejos por combinación (talle, color) para evitar pérdida en colisiones
    catalog_items_map = defaultdict(list)
    for it in items:
        catalog_items_map[(it['talle'], it['color'])].append(it)

    for variant in new_template.product_variant_ids:
        ptavs = variant.product_template_attribute_value_ids
        v_talle = None
        v_color = None
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
            count_created_variants += 1
            for it in matching_items:
                old_to_new_variant_map[it['old_product_id']] = variant.id
                old_to_new_tmpl_map[it['old_product_id']] = new_template.id
                if it.get('old_tmpl_id'):
                    old_tmpl_to_new_tmpl_map[it['old_tmpl_id']] = new_template.id
            new_variant_to_price_map[variant.id] = orig_item['list_price']
        else:
            variant.write({'active': False})

    if count_created_templates % 50 == 0 or count_created_templates == total_to_process:
        print(f"  -> Progreso: {count_created_templates}/{total_to_process} plantillas creadas... ({count_created_variants} variantes activadas)")

# ==============================================================================
# PASO 7: TRASLADO DE STOCK, LISTA DE PRECIOS Y CONFIGURACIÓN POS (TICKETS 1, 2, 3)
# ==============================================================================
print("\n[PASO 7/7] Trasladando stock, creando lista de precios y sincronizando POS...")

# 7.1 Traslado Consolidado de Stock (Ticket 3)
print("  [7.1] Re-enlazando y consolidando quants de stock a las nuevas variantes...")

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

# Actualizar stock.valuation.layer si existe
cr.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'stock_valuation_layer'
    );
""")
has_svl = cr.fetchone()[0]
if has_svl:
    print("  [7.1.1] Actualizando capas de valoración (stock.valuation.layer)...")
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

# Verificación de consistencia de stock
print("  [7.1.2] Verificando consistencia física de stock pre vs post migración...")
stock_match_ok = 0
stock_discrepancies = 0
total_stock_units_migrated = 0.0

new_variant_expected_internal = defaultdict(float)
new_variant_expected_total = defaultdict(float)
for old_pid, snap in stock_snapshot.items():
    new_vid = old_to_new_variant_map.get(old_pid)
    if new_vid:
        new_variant_expected_internal[new_vid] += snap.get('internal_qty', 0.0)
        new_variant_expected_total[new_vid] += snap['total_qty']

for new_vid, exp_int_qty in new_variant_expected_internal.items():
    new_v = Product.browse(new_vid)
    current_qty = new_v.qty_available
    total_stock_units_migrated += current_qty
    if abs(current_qty - exp_int_qty) < 0.001:
        stock_match_ok += 1
    else:
        stock_discrepancies += 1
        print(f"    [!] Discrepancia en [{new_v.default_code}]: Esperado {exp_int_qty} | Actual {current_qty}")

print(f"  * Quants trasladados/consolidados: {transferred_quants_count} (Grupos consolidados: {consolidated_groups})")
print(f"  * Variantes verificadas con stock exacto (En Mano): {stock_match_ok} / {len(new_variant_expected_internal)}")
print(f"  * Total unidades físicas en nuevas variantes (WH): {total_stock_units_migrated:,.2f}")
if stock_discrepancies == 0:
    print("  [✓] ¡STOCK INTERNO MIGRADO CON 100% DE COINCIDENCIA!")
else:
    print(f"  [!] Alerta: Se detectaron {stock_discrepancies} variantes con diferencias.")

# 7.2 Crear y Configurar Lista de Precios con Variantes (Ticket 2)
print("\n  [7.2] Configurando Lista de Precios con Variantes...")
pl_name = "Lista de Precios con Variantes"
pricelist = Pricelist.search([
    ('name', '=', pl_name),
    ('company_id', 'in', [env.company.id, False])
], limit=1)

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

# Remapear reglas en listas de precios existentes
cr.execute("""
    SELECT count(*) 
    FROM product_pricelist_item 
    WHERE product_id = ANY(%s)
""", (prods_in_batch,))
existing_var_rules_count = cr.fetchone()[0]

if existing_var_rules_count > 0:
    print(f"  * Remapeando {existing_var_rules_count} reglas por variante hacia nuevas variantes...")
    for old_pid, new_vid in old_to_new_variant_map.items():
        cr.execute("UPDATE product_pricelist_item SET product_id = %s WHERE product_id = %s", (new_vid, old_pid))

if tmpls_in_batch:
    cr.execute("""
        SELECT count(*) 
        FROM product_pricelist_item 
        WHERE product_tmpl_id = ANY(%s)
    """, (list(tmpls_in_batch),))
    existing_tmpl_rules_count = cr.fetchone()[0]

    if existing_tmpl_rules_count > 0:
        print(f"  * Remapeando {existing_tmpl_rules_count} reglas por plantilla hacia nuevas plantillas...")
        for old_tid, new_tid in old_tmpl_to_new_tmpl_map.items():
            cr.execute("UPDATE product_pricelist_item SET product_tmpl_id = %s WHERE product_tmpl_id = %s", (new_tid, old_tid))

# Generar reglas específicas por variante en 'Lista de Precios con Variantes'
item_fields = set(PricelistItem._fields.keys())
existing_pl_variant_ids = set(PricelistItem.search([
    ('pricelist_id', '=', pricelist.id),
    ('applied_on', '=', '0_product_variant')
]).mapped('product_id.id'))

items_to_create = []
for v_id, price in new_variant_to_price_map.items():
    if v_id in existing_pl_variant_ids:
        continue
    item_vals = {
        'pricelist_id': pricelist.id,
        'applied_on': '0_product_variant',
        'product_id': v_id,
        'compute_price': 'fixed',
        'fixed_price': price,
        'min_quantity': 0,
    }
    if 'company_id' in item_fields:
        item_vals['company_id'] = env.company.id
    items_to_create.append(item_vals)

BATCH_SIZE = 500
created_rules_count = 0
for i in range(0, len(items_to_create), BATCH_SIZE):
    batch = items_to_create[i:i + BATCH_SIZE]
    PricelistItem.create(batch)
    created_rules_count += len(batch)

print(f"  [✓] Reglas de variantes creadas en la lista de precios: {created_rules_count}")

# 7.3 Configurar Puntos de Venta (pos.config)
print("\n  [7.3] Actualizando configuración de cajas registradoras (pos.config)...")
all_active_pos_cat_ids = sorted(list(set(c for c in pos_cat_cache.values() if c)))
pos_configs = PosConfig.search([])

for cfg in pos_configs:
    vals_cfg = {}
    if hasattr(cfg, 'limit_categories'):
        vals_cfg['limit_categories'] = True
    if hasattr(cfg, 'pos_category_ids'):
        vals_cfg['pos_category_ids'] = [(6, 0, all_active_pos_cat_ids)]
    if hasattr(cfg, 'available_pricelist_ids'):
        current_pls = cfg.available_pricelist_ids.ids
        if pricelist.id not in current_pls:
            vals_cfg['available_pricelist_ids'] = [(4, pricelist.id)]
    if hasattr(cfg, 'pricelist_id'):
        vals_cfg['pricelist_id'] = pricelist.id
    if hasattr(cfg, 'use_pricelist'):
        vals_cfg['use_pricelist'] = True
    if not vals_cfg:
        continue

    try:
        with env.cr.savepoint():
            cfg.write(vals_cfg)
        print(f"  + TPV '{cfg.name}' actualizado vía ORM con categorías y lista de precios.")
    except Exception as err:
        print(f"  [!] Aviso: No se pudo actualizar TPV '{cfg.name}' vía ORM ({err}).")
        try:
            sql_set = []
            sql_vals = []
            if 'pricelist_id' in vals_cfg and 'pricelist_id' in cfg._fields:
                sql_set.append("pricelist_id = %s")
                sql_vals.append(vals_cfg['pricelist_id'])
            if 'use_pricelist' in vals_cfg and 'use_pricelist' in cfg._fields:
                sql_set.append("use_pricelist = %s")
                sql_vals.append(vals_cfg['use_pricelist'])
            if 'limit_categories' in vals_cfg and 'limit_categories' in cfg._fields:
                sql_set.append("limit_categories = %s")
                sql_vals.append(vals_cfg['limit_categories'])
            
            if sql_set:
                sql_vals.append(cfg.id)
                cr.execute(f"UPDATE pos_config SET {', '.join(sql_set)} WHERE id = %s", tuple(sql_vals))

            if 'pos_category_ids' in cfg._fields and all_active_pos_cat_ids:
                f_cats = cfg._fields['pos_category_ids']
                cr.execute(f"DELETE FROM {f_cats.relation} WHERE {f_cats.column1} = %s", (cfg.id,))
                for cat_id in all_active_pos_cat_ids:
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
        print(f"\n[!] AVISO: Se detectaron {len(open_sessions)} sesiones de TPV abiertas:")
        for s in open_sessions:
            print(f"    - Sesión [ID {s.id}] '{s.name}' (Usuario: {s.user_id.name})")
        print("    * Los cajeros deberán presionar Ctrl+F5 o cerrar/reabrir sesión para recargar el catálogo.")

# ==============================================================================
# AUDITORÍA FINAL Y RESOLUCIÓN DE TRANSACCIÓN
# ==============================================================================
print("\n" + "=" * 100)
print(" RESUMEN GENERAL DE LA MIGRACIÓN:")
print(f"  - Plantillas Maestras Creadas: {count_created_templates}")
print(f"  - Variantes Oficiales Creadas y Activas: {count_created_variants}")
print(f"  - Productos Viejos Archivados (barcode con sufijo _OLD): {len(prods_in_batch)}")
print(f"  - Stock Físico Trasladado a Nuevas Variantes: {total_stock_units_migrated:,.2f} unidades ({transferred_quants_count} quants procesados)")
print(f"  - Reglas en Lista de Precios con Variantes: {created_rules_count}")
print(f"  - Categorías de TPV Asignadas:")
for pcat_id, count in assigned_pos_cats_counter.items():
    pcat_rec = PosCategory.browse(pcat_id)
    print(f"      * {pcat_rec.name}: {count} plantillas")
print("=" * 100)

if DRY_RUN:
    cr.execute("ROLLBACK TO SAVEPOINT unificado_migracion_sp")
    print("\n[✓] MODO DRY-RUN FINALIZADO: Se ejecutó ROLLBACK TO SAVEPOINT exitosamente.")
    print("    Ningún dato de la base de datos fue modificado de forma permanente.")
    print("    Para aplicar cambios en producción, configure DRY_RUN = False y vuelva a ejecutar.")
else:
    cr.execute("RELEASE SAVEPOINT unificado_migracion_sp")
    env.cr.commit()
    print("\n[✓] ¡MIGRACIÓN DEFINITIVA APLICADA Y CONFIRMADA CON ÉXITO (COMMIT)!")
    print("    Recargue el TPV y los formularios en el navegador con Ctrl + F5.")
