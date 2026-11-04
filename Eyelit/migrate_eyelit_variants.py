# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT DE MIGRACIÓN DEFINITIVO: UNIFICACIÓN DE VARIANTES EYELIT (Odoo 18.0+)
================================================================================
Entorno: Odoo.sh (Python Shell)
Uso:
    python3 odoo-bin shell -d $ODOO_DATABASE --no-http < migrate_eyelit_variants.py

CORRECCIONES APLICADAS:
    1. Campo 'name' en Odoo 18 es JSONB (traducciones). Solo actualizamos 'active = FALSE' en SQL.
    2. Sincronización explícita de PTAVs vía _update_product_template_attribute_values() y env.flush_all().
    3. Extracción de PTAVs directamente desde ptal.product_template_value_ids.
    4. Asignación atómica de combination_indices para cumplir con product_product_combination_unique.
"""
import sys
import logging
from collections import defaultdict
from psycopg2.extras import execute_values

_logger = logging.getLogger('odoo.migration.eyelit')

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
DRY_RUN = True               # True: Simula y hace ROLLBACK. False: Confirma cambios con COMMIT.
SEPARAR_POR_LINEA = True     # True: Agrupa por (Art, Linea, Nombre) -> 0 colisiones (P0A vs P0W).
LIMIT_FAMILIES = None        # None para todas (811 familias), o un número entero (ej. 5) para prueba piloto.

print("=" * 80)
print(f"[*] INICIANDO PROCESO DE MIGRACIÓN A VARIANTES - ODOO 18")
print(f"[*] MODO: {'SIMULACIÓN DRY-RUN (ROLLBACK)' if DRY_RUN else '*** PRODUCCIÓN (COMMIT) ***'}")
print(f"[*] SEPARAR POR LÍNEA: {SEPARAR_POR_LINEA}")
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
cr.execute("SAVEPOINT migration_eyelit_sp")

Product = env['product.product']
Template = env['product.template']
Attribute = env['product.attribute']
AttrValue = env['product.attribute.value']
PTAL = env['product.template.attribute.line']
PTAV = env['product.template.attribute.value']

# 2. Configurar o Buscar Atributos Globales 'Talle' y 'Color'
attr_talle = Attribute.search([('name', '=ilike', 'Talle')], limit=1)
if not attr_talle:
    attr_talle = Attribute.create({
        'name': 'Talle',
        'display_type': 'pills',
        'create_variant': 'always',
    })
    print(f"[+] Creado atributo: 'Talle' (ID {attr_talle.id})")
else:
    if attr_talle.create_variant != 'always':
        attr_talle.write({'create_variant': 'always', 'display_type': 'pills'})
    print(f"[*] Utilizando atributo existente: 'Talle' (ID {attr_talle.id})")

attr_color = Attribute.search([('name', '=ilike', 'Color')], limit=1)
if not attr_color:
    attr_color = Attribute.create({
        'name': 'Color',
        'display_type': 'select',
        'create_variant': 'always',
    })
    print(f"[+] Creado atributo: 'Color' (ID {attr_color.id})")
else:
    if attr_color.create_variant != 'always':
        attr_color.write({'create_variant': 'always', 'display_type': 'select'})
    print(f"[*] Utilizando atributo existente: 'Color' (ID {attr_color.id})")

# Cache local de valores de atributos para optimizar
talle_value_cache = {v.name: v.id for v in AttrValue.search([('attribute_id', '=', attr_talle.id)])}
color_value_cache = {v.name: v.id for v in AttrValue.search([('attribute_id', '=', attr_color.id)])}

def get_or_create_value(attr_id, val_name, cache):
    if val_name not in cache:
        rec = AttrValue.create({'name': val_name, 'attribute_id': attr_id})
        cache[val_name] = rec.id
    return cache[val_name]

# 3. Lectura de Todos los Productos
print("\n[*] Leyendo catálogo de productos...")
all_prods = Product.search_read(
    [('active', 'in', [True, False])],
    ['id', 'name', 'default_code', 'barcode', 'product_tmpl_id', 'active']
)

# Identificar productos que tienen movimientos o stock (para darles prioridad como master)
products_with_history = set()
if 'stock.move' in env:
    cr.execute("SELECT DISTINCT product_id FROM stock_move WHERE product_id IS NOT NULL")
    products_with_history.update(r[0] for r in cr.fetchall())
if 'account.move.line' in env:
    cr.execute("SELECT DISTINCT product_id FROM account_move_line WHERE product_id IS NOT NULL")
    products_with_history.update(r[0] for r in cr.fetchall())

print(f"[*] Productos identificados con historial operativo: {len(products_with_history)}")

# 4. Agrupación por Familia
families = defaultdict(list)
skipped = 0

for p in all_prods:
    code = (p.get('default_code') or p.get('barcode') or '').strip()
    parsed = parse_code(code)
    if not parsed:
        skipped += 1
        continue
    
    parsed['product_id'] = p['id']
    parsed['product_tmpl_id'] = p['product_tmpl_id'][0] if p.get('product_tmpl_id') else False
    parsed['name'] = p.get('name') or ''
    parsed['has_history'] = p['id'] in products_with_history

    if SEPARAR_POR_LINEA and parsed['linea']:
        family_key = (parsed['art'], parsed['linea'], parsed['name'])
    else:
        family_key = (parsed['art'], '', parsed['name'])
        
    families[family_key].append(parsed)

total_families = len(families)
print(f"[*] Total Familias detectadas para migrar: {total_families} (Productos a migrar: {len(all_prods) - skipped})")
print(f"[*] Productos excluidos (servicios/packaging/especiales): {skipped}")

if LIMIT_FAMILIES:
    families_to_process = list(families.items())[:LIMIT_FAMILIES]
    print(f"[!] ATENCIÓN: Procesando solo {LIMIT_FAMILIES} familias en modo prueba.")
else:
    families_to_process = list(families.items())

# 5. Ejecutar Re-parenting y Creación de Variantes
count_processed_families = 0
count_migrated_variants = 0
count_archived_templates = 0

print("\n[*] PROCESANDO FAMILIAS...")

for (art, linea, name), items in families_to_process:
    count_processed_families += 1

    # A. Elegir el Master Template: aquel producto que tenga historial o el de menor ID
    master_item = next((it for it in items if it['has_history']), items[0])
    master_tmpl_id = master_item['product_tmpl_id']
    master_tmpl = Template.browse(master_tmpl_id)

    # Actualizar nombre del template si incluye línea para claridad
    if linea and SEPARAR_POR_LINEA and linea not in (master_tmpl.name or ''):
        master_tmpl.name = f"{name} ({linea})"

    # B. Extraer todos los talles y colores únicos requeridos por esta familia
    unique_talles = list(dict.fromkeys(it['talle'] for it in items))
    unique_colors = list(dict.fromkeys(it['color'] for it in items))

    # C. Obtener o crear los IDs de product.attribute.value
    talle_val_ids = [get_or_create_value(attr_talle.id, t, talle_value_cache) for t in unique_talles]
    color_val_ids = [get_or_create_value(attr_color.id, c, color_value_cache) for c in unique_colors]

    # D. Crear o actualizar PTAL (product.template.attribute.line) en el Master Template
    PTAL_ctx = PTAL.with_context(create_product_product=False)
    
    # PTAL Talle
    ptal_talle = PTAL_ctx.search([('product_tmpl_id', '=', master_tmpl_id), ('attribute_id', '=', attr_talle.id)], limit=1)
    if not ptal_talle:
        ptal_talle = PTAL_ctx.create({
            'product_tmpl_id': master_tmpl_id,
            'attribute_id': attr_talle.id,
            'value_ids': [(6, 0, talle_val_ids)]
        })
    else:
        ptal_talle.write({'value_ids': [(6, 0, list(set(ptal_talle.value_ids.ids + talle_val_ids)))]})

    # PTAL Color
    ptal_color = PTAL_ctx.search([('product_tmpl_id', '=', master_tmpl_id), ('attribute_id', '=', attr_color.id)], limit=1)
    if not ptal_color:
        ptal_color = PTAL_ctx.create({
            'product_tmpl_id': master_tmpl_id,
            'attribute_id': attr_color.id,
            'value_ids': [(6, 0, color_val_ids)]
        })
    else:
        ptal_color.write({'value_ids': [(6, 0, list(set(ptal_color.value_ids.ids + color_val_ids)))]})

    # Forzar actualización de PTAVs en el modelo
    if hasattr(ptal_talle, '_update_product_template_attribute_values'):
        ptal_talle._update_product_template_attribute_values()
    if hasattr(ptal_color, '_update_product_template_attribute_values'):
        ptal_color._update_product_template_attribute_values()

    env.flush_all()

    # E. Mapear los PTAV generados para este template directamente desde las líneas
    pav_to_ptav = {}
    for ptav in ptal_talle.product_template_value_ids:
        pav_to_ptav[ptav.product_attribute_value_id.id] = ptav.id
    for ptav in ptal_color.product_template_value_ids:
        pav_to_ptav[ptav.product_attribute_value_id.id] = ptav.id

    # F. Preparar Re-parenting y combinación de índices
    known_product_ids = [it['product_id'] for it in items]
    redundant_tmpl_ids = set()
    product_update_data = [] # (prod_id, master_tmpl_id, comb_idx)
    ptav_combinations_to_insert = []

    for it in items:
        p_id = it['product_id']
        old_tmpl_id = it['product_tmpl_id']
        if old_tmpl_id != master_tmpl_id:
            redundant_tmpl_ids.add(old_tmpl_id)

        t_val_id = talle_value_cache[it['talle']]
        c_val_id = color_value_cache[it['color']]

        t_ptav_id = pav_to_ptav.get(t_val_id)
        c_ptav_id = pav_to_ptav.get(c_val_id)

        if not t_ptav_id or not c_ptav_id:
            print(f"[-] ERROR: No se encontró PTAV para Talle {it['talle']} o Color {it['color']} en Template {master_tmpl_id}")
            continue

        comb_idx = ",".join(str(x) for x in sorted([t_ptav_id, c_ptav_id]))
        product_update_data.append((p_id, master_tmpl_id, comb_idx))
        ptav_combinations_to_insert.append((p_id, t_ptav_id))
        ptav_combinations_to_insert.append((p_id, c_ptav_id))

    # G. Actualización Atómica en SQL (evitando product_product_combination_unique)
    if product_update_data:
        # 1. Eliminar cualquier variante dummy autogenerada por Odoo que no pertenezca a nuestro set original
        cr.execute("""
            DELETE FROM product_product 
            WHERE product_tmpl_id = %s AND id != ANY(%s)
        """, (master_tmpl_id, known_product_ids))

        # 2. Asignar temporalmente un comb_idx único a los productos para evitar colisión de vacíos ('')
        cr.execute("""
            UPDATE product_product 
            SET combination_indices = 'TEMP_' || id::text 
            WHERE id = ANY(%s)
        """, (known_product_ids,))

        # 3. Actualizar product_tmpl_id Y el combination_indices real de forma simultánea
        execute_values(cr, """
            UPDATE product_product AS p
            SET product_tmpl_id = data.tmpl_id,
                combination_indices = data.comb_idx
            FROM (VALUES %s) AS data(prod_id, tmpl_id, comb_idx)
            WHERE p.id = data.prod_id
        """, product_update_data)

        # 4. Actualizar la tabla intermedia product_variant_combination
        cr.execute("DELETE FROM product_variant_combination WHERE product_product_id = ANY(%s)", (known_product_ids,))
        execute_values(cr, """
            INSERT INTO product_variant_combination (product_product_id, product_template_attribute_value_id)
            VALUES %s
            ON CONFLICT DO NOTHING
        """, ptav_combinations_to_insert)

    # H. Desactivar Templates redundantes que quedaron vacíos (campo active es booleano seguro)
    if redundant_tmpl_ids:
        cr.execute("""
            UPDATE product_template 
            SET active = FALSE 
            WHERE id = ANY(%s)
        """, (list(redundant_tmpl_ids),))
        count_archived_templates += len(redundant_tmpl_ids)

    count_migrated_variants += len(product_update_data)

    if count_processed_families % 100 == 0 or count_processed_families == len(families_to_process):
        print(f"  -> Progreso: {count_processed_families}/{len(families_to_process)} familias procesadas... ({count_migrated_variants} variantes vinculadas)")

# 6. Resumen Final y Rollback/Commit
print("\n" + "=" * 80)
print("[*] RESUMEN DE LA MIGRACIÓN:")
print(f"  - Familias / Templates Maestros procesados: {count_processed_families}")
print(f"  - Variantes vinculadas exitosamente: {count_migrated_variants}")
print(f"  - Plantillas unitarias vacías archivadas: {count_archived_templates}")
print("=" * 80)

if DRY_RUN:
    cr.execute("ROLLBACK TO SAVEPOINT migration_eyelit_sp")
    print("\n[✓] MODO DRY-RUN FINALIZADO: Se ejecutó ROLLBACK exitosamente.")
    print("    Ningún dato de la base de datos fue modificado.")
    print("    Para aplicar los cambios reales en producción, cambia DRY_RUN = False en el script.")
else:
    cr.execute("RELEASE SAVEPOINT migration_eyelit_sp")
    env.cr.commit()
    print("\n[✓] ¡MIGRACIÓN COMPLETADA Y CONFIRMADA (COMMIT) EXITOSAMENTE EN LA BASE DE DATOS!")

print("=" * 80)
