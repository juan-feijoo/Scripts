# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT LIMPIO: CREACIÓN DE PLANTILLAS Y VARIANTES DESDE CERO (Odoo 18.0+)
================================================================================
Estrategia:
    1. Libera los códigos de barra de los productos viejos agregando sufijo '_OLD'.
    2. Archiva (active = False) los productos y plantillas viejos.
    3. Crea las nuevas plantillas (product.template) de forma 100% NATIVA por ORM.
    4. Configura 'available_in_pos': True (disponibles en Punto de Venta / TPV).
    5. Odoo genera automáticamente las variantes y sus relaciones oficiales.
    6. Asigna a cada nueva variante su código de barras (barcode) y referencia interna original.
    7. Desactiva variantes de la matriz que no existían en el catálogo real.

SEGURIDAD:
    - DRY_RUN = False: Aplica cambios definitivos con COMMIT.
"""
import sys
import logging
from collections import defaultdict

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
DRY_RUN = False              # False: Aplica cambios definitivos. True: Simulación con ROLLBACK.
SEPARAR_POR_LINEA = True     # True: Diferencia artículos de canal Web (P0W) vs Tradicional (P0A).
LIMIT_FAMILIES = None        # None para procesar todas las 811 familias. Número para prueba.

print("=" * 80)
print(f"[*] CREACIÓN LIMPIA DE PLANTILLAS Y VARIANTES - ODOO 18")
print(f"[*] MODO: {'SIMULACIÓN DRY-RUN (ROLLBACK)' if DRY_RUN else '*** PRODUCCIÓN (COMMIT DEFINITIVO) ***'}")
print(f"[*] DISPONIBLE EN PUNTO DE VENTA (TPV / POS): SÍ")
print(f"[*] LÍMITE: {LIMIT_FAMILIES if LIMIT_FAMILIES else 'TODAS LAS FAMILIAS'}")
print("=" * 80)

# Mapeo de normalización de talles comprobado
TALLE_MAP = {
    'XS0': 'XS', 'S00': 'S', 'M00': 'M', 'L00': 'L', 'XL0': 'XL', 'XXL': 'XXL',
    '3XL': '3XL', '4XL': '4XL', '5XL': '5XL', '6XL': '6XL',
    '000': 'U', # Talle Único
    '7/8': '7/8', '9/1': '9/10', '11/': '11/12', '13/': '13/14'
}

def normalize_talle(suffix):
    s = suffix.strip()
    if s in TALLE_MAP:
        return TALLE_MAP[s]
    if s.isdigit():
        return str(int(s))
    if s.endswith('0') and s[:-1].isalpha():
        return s[:-1]
    return s

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

# 1. Iniciar Savepoint transaccional
cr = env.cr
cr.execute("SAVEPOINT clean_migration_sp")

Product = env['product.product']
Template = env['product.template']
Attribute = env['product.attribute']
AttrValue = env['product.attribute.value']

# Verificar campos de Punto de Venta (POS) en product.template
has_pos_available = 'available_in_pos' in Template._fields
has_pos_categ_ids = 'pos_categ_ids' in Template._fields

print(f"[*] Módulo POS detectado: available_in_pos={has_pos_available}, pos_categ_ids={has_pos_categ_ids}")

# 2. Configurar o Buscar Atributos Globales 'Talle' y 'Color'
attr_talle = Attribute.search([('name', '=ilike', 'Talle')], limit=1)
if not attr_talle:
    attr_talle = Attribute.create({
        'name': 'Talle',
        'display_type': 'pills',
        'create_variant': 'always',
    })
else:
    if attr_talle.create_variant != 'always':
        attr_talle.write({'create_variant': 'always', 'display_type': 'pills'})

attr_color = Attribute.search([('name', '=ilike', 'Color')], limit=1)
if not attr_color:
    attr_color = Attribute.create({
        'name': 'Color',
        'display_type': 'select',
        'create_variant': 'always',
    })
else:
    if attr_color.create_variant != 'always':
        attr_color.write({'create_variant': 'always', 'display_type': 'select'})

print(f"[*] Atributo Talle: ID {attr_talle.id} | Atributo Color: ID {attr_color.id}")

# Cache local de valores de atributos
talle_value_cache = {v.name: v.id for v in AttrValue.search([('attribute_id', '=', attr_talle.id)])}
color_value_cache = {v.name: v.id for v in AttrValue.search([('attribute_id', '=', attr_color.id)])}

def get_or_create_value(attr_id, val_name, cache):
    if val_name not in cache:
        rec = AttrValue.create({'name': val_name, 'attribute_id': attr_id})
        cache[val_name] = rec.id
    return cache[val_name]

# 3. Leer productos activos
fields_to_read = ['id', 'name', 'default_code', 'barcode', 'product_tmpl_id', 'list_price', 'standard_price', 'categ_id', 'uom_id']
if has_pos_categ_ids:
    fields_to_read.append('pos_categ_ids')

all_prods = Product.search_read(
    [('active', '=', True)],
    fields_to_read
)

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

    if SEPARAR_POR_LINEA and parsed['linea']:
        family_key = (parsed['art'], parsed['linea'], parsed['name'])
    else:
        family_key = (parsed['art'], '', parsed['name'])
        
    families[family_key].append(parsed)

total_families = len(families)
print(f"[*] Total Familias detectadas: {total_families} ({len(old_prod_ids_to_archive)} productos)")
print(f"[*] Productos especiales que se mantienen intactos: {skipped}")

if LIMIT_FAMILIES:
    families_to_process = list(families.items())[:LIMIT_FAMILIES]
    print(f"[!] ATENCIÓN: Modo prueba con {LIMIT_FAMILIES} familias.")
else:
    families_to_process = list(families.items())

# 4. Liberar códigos de barra y archivar productos viejos que corresponden a las familias a procesar
prods_in_batch = []
tmpls_in_batch = set()
for _, items in families_to_process:
    for it in items:
        prods_in_batch.append(it['old_product_id'])
        if it['old_tmpl_id']:
            tmpls_in_batch.add(it['old_tmpl_id'])

print(f"\n[*] Liberando códigos de barra y archivando {len(prods_in_batch)} productos viejos...")
cr.execute("""
    UPDATE product_product 
    SET barcode = barcode || '_OLD',
        active = FALSE
    WHERE id = ANY(%s) AND barcode IS NOT NULL
""", (prods_in_batch,))

cr.execute("""
    UPDATE product_product 
    SET active = FALSE
    WHERE id = ANY(%s)
""", (prods_in_batch,))

cr.execute("""
    UPDATE product_template 
    SET active = FALSE
    WHERE id = ANY(%s)
""", (list(tmpls_in_batch),))

# 5. Crear Nuevas Plantillas Nativas y Configurar Variantes
print("\n[*] CREANDO NUEVAS PLANTILLAS Y VARIANTES VÍA ORM NATIVO...")

count_created_templates = 0
count_created_variants = 0
total_to_process = len(families_to_process)

for (art, linea, name), items in families_to_process:
    count_created_templates += 1
    sample = items[0]
    
    # Nombre limpio de la plantilla
    tmpl_name = f"{name} ({linea})" if linea and SEPARAR_POR_LINEA else name

    # Talles y Colores únicos de este artículo
    unique_talles = list(dict.fromkeys(it['talle'] for it in items))
    unique_colors = list(dict.fromkeys(it['color'] for it in items))

    talle_val_ids = [get_or_create_value(attr_talle.id, t, talle_value_cache) for t in unique_talles]
    color_val_ids = [get_or_create_value(attr_color.id, c, color_value_cache) for c in unique_colors]

    # Valores para la nueva plantilla
    template_vals = {
        'name': tmpl_name,
        'type': 'consu', # En Odoo 18: 'consu' (bienes/materiales)
        'categ_id': sample['categ_id'],
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

    # Habilitar en Punto de Venta (TPV / POS)
    if has_pos_available:
        template_vals['available_in_pos'] = True
    
    # Si los productos tenían categorías de POS asignadas, heredarlas
    if has_pos_categ_ids and sample.get('pos_categ_ids'):
        template_vals['pos_categ_ids'] = [(6, 0, sample['pos_categ_ids'])]

    # Crear la plantilla usando el ORM oficial de Odoo 18
    new_template = Template.create(template_vals)

    # Mapeo de búsqueda rápida para variantes originales de este artículo: (talle, color) -> item
    catalog_map = {(it['talle'], it['color']): it for it in items}

    # Asignar barcode y default_code a las variantes creadas por Odoo
    for variant in new_template.product_variant_ids:
        ptavs = variant.product_template_attribute_value_ids
        v_talle = None
        v_color = None
        for ptav in ptavs:
            if ptav.attribute_id.id == attr_talle.id:
                v_talle = ptav.product_attribute_value_id.name
            elif ptav.attribute_id.id == attr_color.id:
                v_color = ptav.product_attribute_value_id.name
        
        orig_item = catalog_map.get((v_talle, v_color))
        if orig_item:
            variant.write({
                'default_code': orig_item['code'],
                'barcode': orig_item['code'],
                'standard_price': orig_item['standard_price'],
                'list_price': orig_item['list_price'],
            })
            count_created_variants += 1
        else:
            # Combinación de la matriz que nunca existió comercialmente -> Desactivar
            variant.write({'active': False})

    if count_created_templates % 50 == 0 or count_created_templates == total_to_process:
        print(f"  -> Progreso: {count_created_templates}/{total_to_process} plantillas creadas... ({count_created_variants} variantes activadas)")

print("\n" + "=" * 80)
print("[*] RESUMEN DE LA CREACIÓN LIMPIA:")
print(f"  - Plantillas creadas: {count_created_templates}")
print(f"  - Variantes oficiales activas asignadas: {count_created_variants}")
print(f"  - Productos viejos archivados (con barcode liberado): {len(prods_in_batch)}")
print(f"  - Disponibles en Punto de Venta (POS / TPV): SÍ ('available_in_pos' = True)")
print("=" * 80)

if DRY_RUN:
    cr.execute("ROLLBACK TO SAVEPOINT clean_migration_sp")
    print("\n[✓] MODO DRY-RUN FINALIZADO: Se ejecutó ROLLBACK exitosamente.")
    print("    Ningún dato de la base de datos fue modificado.")
else:
    cr.execute("RELEASE SAVEPOINT clean_migration_sp")
    env.cr.commit()
    print("\n[✓] ¡NUEVAS PLANTILLAS Y VARIANTES CREADAS EXITOSAMENTE (COMMIT DEFINITIVO)!")

print("=" * 80)
