# -*- coding: utf-8 -*-
"""
03 - AUDITORÍA Y VERIFICACIÓN POST-MIGRACIÓN
Verifica el estado del catálogo, TPV, stock y listas de precios.
"""
import json
import os

h('03 - AUDITORÍA Y VERIFICACIÓN POST-MIGRACIÓN')

Product = env['product.product']
Template = env['product.template']
Quant = env['stock.quant']
PosCategory = env['pos.category']
PosConfig = env['pos.config']
Pricelist = env['product.pricelist']
PricelistItem = env['product.pricelist.item']

# 1. Verificación de Plantillas y Variantes Activas
sub('1. Estado de Plantillas y Variantes')
active_tmpls = Template.search([('active', '=', True)])
active_variants = Product.search([('active', '=', True)])
archived_prods = Product.search([('active', '=', False), ('barcode', '=like', '%_OLD')])

print(f"Plantillas activas: {len(active_tmpls)}")
print(f"Variantes activas: {len(active_variants)}")
print(f"Productos viejos archivados con sufijo _OLD: {len(archived_prods)}")
if not archived_prods:
    print("\n  [i] INFORMACIÓN: No se detectaron productos archivados con sufijo '_OLD'.")
    print("      La base de datos se encuentra en estado PRE-MIGRACIÓN (o la última ejecución fue en modo DRY_RUN con rollback).")
    print("      Para aplicar la migración y persistir los cambios, ejecute el runner con DRY_RUN=0.")

# 2. Visibilidad en Punto de Venta
sub('2. Disponibilidad en TPV / POS')
pos_tmpls = Template.search([('available_in_pos', '=', True), ('active', '=', True)])
without_pos_cats = pos_tmpls.filtered(lambda t: not t.pos_categ_ids)
print(f"Plantillas disponibles en TPV: {len(pos_tmpls)} / {len(active_tmpls)}")
print(f"Plantillas en TPV sin categorías asignadas: {len(without_pos_cats)}")
if without_pos_cats:
    print(f"  [!] Alerta: Hay {len(without_pos_cats)} plantillas sin categoría de TPV!")
else:
    print("  [✓] 100% de las plantillas en TPV tienen categoría asignada.")

# Configuración de cajas registradoras
configs = PosConfig.search([])
for cfg in configs:
    pl_name = cfg.pricelist_id.name if hasattr(cfg, 'pricelist_id') and cfg.pricelist_id else 'Sin lista por defecto'
    cats_count = len(cfg.pos_category_ids) if hasattr(cfg, 'pos_category_ids') else 0
    print(f"  * TPV '{cfg.name}': Lista por defecto='{pl_name}' | Categorías habilitadas={cats_count}")

# 3. Verificación de Stock Actual
sub('3. Stock Físico en Variantes Activas y Plantillas')
quants_active = Quant.search([('product_id.active', '=', True), ('quantity', '!=', 0)])
quants_archived = Quant.search([('product_id.active', '=', False), ('quantity', '!=', 0)])

internal_active_quants = quants_active.filtered(lambda q: q.location_id.usage == 'internal')
total_internal_active = sum(internal_active_quants.mapped('quantity'))
total_qty_active = sum(quants_active.mapped('quantity'))
total_qty_archived = sum(quants_archived.mapped('quantity'))

print(f"Stock físico en ubicaciones internas (En Mano / WH): {total_internal_active:,.2f} unidades ({len(internal_active_quants)} quants)")
print(f"Balance neto en todas las ubicaciones (incluye partners): {total_qty_active:,.2f} unidades ({len(quants_active)} quants)")
print(f"Total unidades residuales en productos archivados: {total_qty_archived:,.2f} ({len(quants_archived)} quants)")
if total_qty_archived > 0:
    print(f"  [!] Alerta: Quedaron {total_qty_archived:,.2f} unidades en productos archivados.")
else:
    print("  [✓] Cero stock residual en productos archivados.")

# Verificación de alineación product_tmpl_id en stock.quant (si existe como columna en el schema)
env.cr.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'stock_quant' AND column_name = 'product_tmpl_id';
""")
if env.cr.fetchone():
    env.cr.execute("""
        SELECT count(*) 
        FROM stock_quant sq 
        JOIN product_product pp ON pp.id = sq.product_id 
        WHERE sq.product_tmpl_id IS NOT NULL 
          AND sq.product_tmpl_id != pp.product_tmpl_id;
    """)
    mismatched_tmpl_quants = env.cr.fetchone()[0]
    if mismatched_tmpl_quants > 0:
        print(f"  [!] Alerta: Hay {mismatched_tmpl_quants} quants con product_tmpl_id desalineado!")
    else:
        print("  [✓] Quants perfectamente alineados con sus plantillas maestras en tabla SQL.")
else:
    print("  [✓] En Odoo 18 'product_tmpl_id' es un campo relacionado en stock.quant (resuelto dinámicamente vía product_id.product_tmpl_id).")

# Comparación con respaldo de stock previo si existe
STOCK_BACKUP_PATH = '/tmp/stock_snapshot_eyelit_pre_migration.json'
if os.path.exists(STOCK_BACKUP_PATH):
    try:
        with open(STOCK_BACKUP_PATH, 'r', encoding='utf-8') as f:
            snap_data = json.load(f)
        total_snapshot_qty = sum(v.get('total_qty', 0.0) for v in snap_data.values())
        total_snapshot_internal = sum(v.get('internal_qty', 0.0) for v in snap_data.values()) if any('internal_qty' in v for v in snap_data.values()) else None
        
        print(f"\nComparación con snapshot previo ({len(snap_data)} productos con stock inicial):")
        if total_snapshot_internal is not None:
            print(f"  - Stock interno inicial en snapshot: {total_snapshot_internal:,.2f}")
            print(f"  - Stock interno actual en variantes: {total_internal_active:,.2f}")
            diff_int = abs(total_snapshot_internal - total_internal_active)
            if diff_int < 0.01:
                print("  [✓] ¡STOCK INTERNO (WH/EXISTENCIAS) EXACTO AL 100%!")
            else:
                print(f"  [!] Diferencia en stock interno: {diff_int:,.2f} unidades.")

        print(f"  - Balance neto global inicial en snapshot: {total_snapshot_qty:,.2f}")
        print(f"  - Balance neto global actual en variantes: {total_qty_active:,.2f}")
        diff = abs(total_snapshot_qty - total_qty_active)
        if diff < 0.01:
            print("  [✓] ¡BALANCE GLOBAL DE QUANTS EXACTO AL 100%!")
        else:
            print(f"  [!] Diferencia detectada en balance global: {diff:,.2f} unidades.")
    except Exception as e:
        print(f"  [AVISO] No se pudo leer el archivo snapshot: {e}")

# 4. Verificación de Lista de Precios
sub('4. Lista de Precios con Variantes')
pl = Pricelist.search([('name', '=', 'Lista de Precios con Variantes')], limit=1)
if pl:
    items_count = PricelistItem.search_count([('pricelist_id', '=', pl.id), ('applied_on', '=', '0_product_variant')])
    print(f"  [✓] Lista '{pl.name}' encontrada con {items_count} reglas específicas de variante.")
else:
    print("  [!] No se encontró la 'Lista de Precios con Variantes'.")

# 5. Sesiones de TPV abiertas
sub('5. Sesiones de TPV')
if 'pos.session' in env:
    open_sessions = env['pos.session'].search([('state', '!=', 'closed')])
    if open_sessions:
        print(f"  [!] Hay {len(open_sessions)} sesiones abiertas que requieren recarga (Ctrl+F5).")
    else:
        print("  [✓] Todas las sesiones de TPV están cerradas.")

print("\n" + "=" * 100)
print("[✓] Verificación post-migración finalizada.")
print("=" * 100)
