# -*- coding: utf-8 -*-
"""
01 - DIAGNÓSTICO PREVIO: CATÁLOGO, STOCK, TPV Y LISTAS DE PRECIOS
Solo lectura. Audita la situación actual antes de ejecutar la migración.
"""
from collections import defaultdict, Counter

h('01 - DIAGNÓSTICO PREVIO DE PRODUCTOS, STOCK, TPV Y PRECIOS')

Product = env['product.product']
Template = env['product.template']
Quant = env['stock.quant']
PosCategory = env['pos.category']
PosConfig = env['pos.config']
Pricelist = env['product.pricelist']
PricelistItem = env['product.pricelist.item']

# 1. Catálogo de productos
total_active_prods = Product.search_count([('active', '=', True)])
total_archived_prods = Product.search_count([('active', '=', False)])
total_templates = Template.search_count([('active', '=', True)])

sub('1. Catálogo Actual')
print(f"Total productos activos: {total_active_prods}")
print(f"Total productos archivados: {total_archived_prods}")
print(f"Total plantillas activas: {total_templates}")

# 2. Análisis de Códigos y Patrones Eyelit
prods_data = Product.search_read(
    [('active', '=', True)],
    ['id', 'name', 'default_code', 'barcode']
)

with_pattern = 0
without_pattern = 0
for p in prods_data:
    code = (p.get('default_code') or p.get('barcode') or '').strip()
    if '.' in code:
        with_pattern += 1
    else:
        without_pattern += 1

print(f"Productos con estructura Eyelit (con punto): {with_pattern}")
print(f"Productos especiales (sin punto / servicios): {without_pattern}")

# 3. Stock Físico a la fecha
sub('2. Stock Físico Actual (stock.quant)')
quants = Quant.search([('quantity', '!=', 0)])
quants_by_location = defaultdict(float)
total_units = 0.0
prods_with_stock = set()

for q in quants:
    total_units += q.quantity
    quants_by_location[q.location_id.complete_name] += q.quantity
    prods_with_stock.add(q.product_id.id)

print(f"Total quants activos con stock != 0: {len(quants)}")
print(f"Total productos distintos con stock: {len(prods_with_stock)}")
print(f"Total unidades físicas globales: {total_units:,.2f}")
print("\nDistribución por ubicación:")
for loc, qty in sorted(quants_by_location.items()):
    print(f"  - {loc}: {qty:,.2f} unidades")

# 4. Categorías de Punto de Venta (TPV)
sub('3. Categorías de Punto de Venta (pos.category)')
pos_cats = PosCategory.search([])
print(f"Categorías de TPV existentes: {len(pos_cats)}")
for cat in pos_cats:
    tmpl_count = Template.search_count([('pos_categ_ids', 'in', cat.id), ('active', '=', True)])
    print(f"  - [ID {cat.id}] {cat.name}: {tmpl_count} productos asociados")

# 5. Configuración de Cajas de TPV (pos.config)
sub('4. Cajas Registradoras (pos.config)')
configs = PosConfig.search([])
for cfg in configs:
    limit_cats = getattr(cfg, 'limit_categories', False)
    cat_names = [c.name for c in cfg.pos_category_ids] if hasattr(cfg, 'pos_category_ids') else []
    print(f"  - Caja '{cfg.name}': limit_categories={limit_cats} | Categorías permitidas ({len(cat_names)}): {cat_names[:5]}...")

# 6. Listas de Precios (product.pricelist)
sub('5. Listas de Precios Existentes')
pricelists = Pricelist.search([])
for pl in pricelists:
    rules_count = PricelistItem.search_count([('pricelist_id', '=', pl.id)])
    print(f"  - [ID {pl.id}] '{pl.name}' ({pl.currency_id.name}): {rules_count} reglas activas")

# 7. Sesiones de TPV abiertas (pos.session)
sub('6. Estado de Sesiones de TPV (pos.session)')
if 'pos.session' in env:
    open_sessions = env['pos.session'].search([('state', '!=', 'closed')])
    print(f"Sesiones de TPV abiertas detectadas: {len(open_sessions)}")
    for s in open_sessions:
        print(f"  [!] Sesión [ID {s.id}] '{s.name}' abierta por '{s.user_id.name}' (Estado: {s.state})")
        print("      NOTA: Las sesiones abiertas cargan el catálogo en el navegador; requerirán Ctrl+F5 o reapertura tras migrar.")
    if not open_sessions:
        print("  [✓] No hay sesiones de TPV abiertas. Entorno ideal para migración.")

# 8. Verificación de Esquema SQL de stock_quant
sub('7. Esquema SQL de stock_quant')
env.cr.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'stock_quant' AND column_name = 'product_tmpl_id';
""")
has_tmpl_col = bool(env.cr.fetchone())
print(f"Columna 'product_tmpl_id' presente en tabla stock_quant: {has_tmpl_col}")

print("\n" + "=" * 100)
print("[✓] Diagnóstico finalizado exitosamente.")
print("=" * 100)
