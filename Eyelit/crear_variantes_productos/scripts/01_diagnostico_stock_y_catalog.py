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

active_langs = env['res.lang'].search([('active', '=', True)]).mapped('code')
target_lang = next((l for l in ['es_AR', 'es_419', 'es_ES'] if l in active_langs), env.lang or 'en_US')
print(f"[*] Idioma español detectado para lectura de nombres: {target_lang} (activos: {active_langs})")

# 1. Catálogo de productos
total_active_prods = Product.search_count([('active', '=', True)])
total_archived_prods = Product.search_count([('active', '=', False)])
total_templates = Template.search_count([('active', '=', True)])

sub('1. Catálogo Actual')
print(f"Total productos activos: {total_active_prods}")
print(f"Total productos archivados: {total_archived_prods}")
print(f"Total plantillas activas: {total_templates}")

# 2. Análisis de Códigos y Patrones Eyelit (comparando nombre en_US vs target_lang)
prods_data_es = Product.with_context(lang=target_lang).search_read(
    [('active', '=', True)],
    ['id', 'name', 'default_code', 'barcode']
)
prods_data_en = Product.with_context(lang='en_US').search_read(
    [('active', '=', True)],
    ['id', 'name']
) if 'en_US' in active_langs and target_lang != 'en_US' else []
en_name_by_id = {p['id']: (p.get('name') or '').strip() for p in prods_data_en}

with_pattern = 0
without_pattern = 0
en_sku_but_es_human = 0
for p in prods_data_es:
    code = (p.get('default_code') or p.get('barcode') or '').strip()
    es_name = (p.get('name') or '').strip()
    en_name = en_name_by_id.get(p['id'], '')
    if '.' in code:
        with_pattern += 1
        if en_name and en_name == code and es_name and es_name != code:
            en_sku_but_es_human += 1
    else:
        without_pattern += 1

print(f"Productos con estructura Eyelit (con punto): {with_pattern}")
print(f"Productos especiales (sin punto / servicios): {without_pattern}")
if en_sku_but_es_human > 0:
    print(f"  [i] Detectados {en_sku_but_es_human} productos con código SKU en en_US pero nombre real en {target_lang} (se agruparán correctamente usando {target_lang}).")

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
sub('4. Cajas Registradoras y Configuración POS (pos.config)')
configs = PosConfig.search([])
for cfg in configs:
    limit_cats = getattr(cfg, 'limit_categories', False)
    cat_names = [c.name for c in cfg.pos_category_ids] if hasattr(cfg, 'pos_category_ids') else []
    use_pl = getattr(cfg, 'use_pricelist', False)
    def_pl = cfg.pricelist_id if hasattr(cfg, 'pricelist_id') else False
    def_pl_es = def_pl.with_context(lang=target_lang).name if def_pl else 'Ninguna'
    avail_pls = cfg.available_pricelist_ids if hasattr(cfg, 'available_pricelist_ids') else []
    avail_str = [f"[ID {p.id}] {p.with_context(lang=target_lang).name}" for p in avail_pls]
    tax_inc = getattr(cfg, 'iface_tax_included', 'N/A')
    man_disc = getattr(cfg, 'manual_discount', False)
    glob_disc = getattr(cfg, 'module_pos_discount', False)
    disc_prod = getattr(cfg, 'discount_product_id', False)
    price_ctrl = getattr(cfg, 'restrict_price_control', False)
    print(f"  - Caja '{cfg.name}' (ID {cfg.id}):")
    print(f"      * Listas flexibles (use_pricelist): {use_pl} | Predeterminada: [{def_pl.id if def_pl else '-'}] '{def_pl_es}'")
    print(f"      * Listas disponibles ({len(avail_str)}): {avail_str}")
    print(f"      * Impuestos en recibo (iface_tax_included): '{tax_inc}' | Control precios: {price_ctrl}")
    print(f"      * Línea descuentos: {man_disc} | Descuentos globales: {glob_disc} | Prod descuento: {disc_prod.display_name if disc_prod else 'N/A'}")
    print(f"      * Limitar categorías: {limit_cats} | Categorías permitidas ({len(cat_names)}): {cat_names[:10]}")

# 6. Listas de Precios y Análisis de Precios de Productos
sub('5. Listas de Precios Existentes y Precios de Productos')
pos_pl_ids = {cfg.pricelist_id.id for cfg in configs if hasattr(cfg, 'pricelist_id') and cfg.pricelist_id}
pricelists = Pricelist.search([])
for pl in pricelists:
    rules = PricelistItem.search([('pricelist_id', '=', pl.id)])
    rules_tmpl = sum(1 for r in rules if r.applied_on == '1_product')
    rules_var = sum(1 for r in rules if r.applied_on == '0_product_variant')
    rules_cat = sum(1 for r in rules if r.applied_on == '2_product_category')
    rules_glob = sum(1 for r in rules if r.applied_on == '3_global')
    rules_fixed = sum(1 for r in rules if r.compute_price == 'fixed')
    pos_tag = " [DEFAULT TPV]" if pl.id in pos_pl_ids else ""
    comp_name = pl.company_id.name if pl.company_id else "Todas"
    pl_name_es = pl.with_context(lang=target_lang).name
    name_disp = f"'{pl_name_es}' (en_US: '{pl.name}')" if pl_name_es != pl.name else f"'{pl.name}'"
    print(f"  - [ID {pl.id}] {name_disp} ({pl.currency_id.name} | Cía: {comp_name}){pos_tag}: {len(rules)} reglas activas")
    print(f"      * Por plantilla (1_product): {rules_tmpl} | Por variante (0_product_variant): {rules_var}")
    print(f"      * Por categoría: {rules_cat} | Globales: {rules_glob} | Precios fijos: {rules_fixed}")

# Auditoría de precios en ficha de productos
prods_real_price = Product.search_count([('active', '=', True), ('list_price', '>', 1.0)])
prods_dummy_one = Product.search_count([('active', '=', True), ('list_price', '>', 0), ('list_price', '<=', 1.0)])
prods_without_price = Product.search_count([('active', '=', True), ('list_price', '<=', 0)])
print(f"\nEstado de precios base en catálogo (list_price):")
print(f"  - Productos con list_price > $1.00: {prods_real_price}")
print(f"  - Productos con list_price dummy (<= $1.00): {prods_dummy_one}")
print(f"  - Productos con list_price == $0.00: {prods_without_price}")

# Muestra de 5 productos con sus precios e impuestos (IVA) en catálogo y en listas de precios
sample_prods = Product.search([('active', '=', True), ('default_code', '=like', '%.%')], limit=5)
if not sample_prods:
    sample_prods = Product.search([('active', '=', True), ('default_code', '!=', False)], limit=5)
print("\nMuestra de 5 productos, impuestos (IVA) y precios:")
for sp in sample_prods:
    prices_info = []
    for pl in pricelists:
        rule = PricelistItem.search([
            ('pricelist_id', '=', pl.id),
            '|',
            '&', ('applied_on', '=', '0_product_variant'), ('product_id', '=', sp.id),
            '&', ('applied_on', '=', '1_product'), ('product_tmpl_id', '=', sp.product_tmpl_id.id)
        ], limit=1)
        if rule and rule.compute_price == 'fixed':
            prices_info.append(f"{pl.with_context(lang=target_lang).name} (ID {pl.id}): ${rule.fixed_price:,.2f}")
    taxes_str = ", ".join(t.name for t in sp.taxes_id) if hasattr(sp, 'taxes_id') and sp.taxes_id else "Sin impuestos"
    pl_str = " | ".join(prices_info) if prices_info else "Sin reglas específicas"
    print(f"  [{sp.default_code}] {sp.name[:25]} | IVA: [{taxes_str}] | list_price=${sp.list_price:,.2f} -> {pl_str}")

# Auditoría de Programas de Fidelidad / Promociones en POS (loyalty.program)
if 'loyalty.program' in env:
    progs = env['loyalty.program'].search([('active', '=', True)])
    if progs:
        print(f"\nProgramas de Lealtad / Promociones activos ({len(progs)}):")
        for pr in progs:
            rule_prods = sum(len(r.product_ids) for r in pr.rule_ids) if hasattr(pr, 'rule_ids') else 0
            rule_cats = [r.product_category_id.name for r in pr.rule_ids if getattr(r, 'product_category_id', False)] if hasattr(pr, 'rule_ids') else []
            print(f"  - [ID {pr.id}] '{pr.name}' (tipo: {pr.program_type}, POS: {getattr(pr, 'pos_ok', 'N/A')}): reglas con prod específicos={rule_prods}, categorías={rule_cats}")

# 7. Sesiones de TPV abiertas (pos.session) y órdenes borrador
sub('6. Estado de Sesiones de TPV (pos.session) y Órdenes Pendientes')
if 'pos.session' in env:
    open_sessions = env['pos.session'].search([('state', '!=', 'closed')])
    print(f"Sesiones de TPV abiertas detectadas: {len(open_sessions)}")
    for s in open_sessions:
        print(f"  [!] Sesión [ID {s.id}] '{s.name}' abierta por '{s.user_id.name}' (Estado: {s.state})")
        print("      IMPORTANTE PRODUCCIÓN: Cerrar todas las cajas antes de correr DRY_RUN=0 para que el stock y la contabilidad cierren limpios.")
    if not open_sessions:
        print("  [✓] No hay sesiones de TPV abiertas. Entorno ideal para migración.")
if 'pos.order' in env:
    draft_pos_orders = env['pos.order'].search_count([('state', '=', 'draft')])
    print(f"Órdenes de TPV en borrador (sin pagar/cerrar): {draft_pos_orders}")

# 8. Configuración de Ajustes (Check Variantes y Listas de Precios)
sub('7. Ajustes de Catálogo (Check Variantes y Listas de Precios)')
group_user = env.ref('base.group_user', raise_if_not_found=False)
group_variant = env.ref('product.group_product_variant', raise_if_not_found=False)
group_pricelist = env.ref('product.group_product_pricelist', raise_if_not_found=False)
if group_user and group_variant:
    var_enabled = group_variant in group_user.implied_ids
    print(f"  - Check 'Variantes' (product.group_product_variant): {'ACTIVO [✓]' if var_enabled else 'INACTIVO [!] (el script 02 lo activará automáticamente)'}")
if group_user and group_pricelist:
    pl_enabled = group_pricelist in group_user.implied_ids
    print(f"  - Check 'Listas de precios' (product.group_product_pricelist): {'ACTIVO [✓]' if pl_enabled else 'INACTIVO [!] (el script 02 lo activará automáticamente)'}")

# 9. Reservas de Stock y Transferencias Abiertas
sub('8. Stock Reservado y Transferencias Pendientes')
reserved_quants = Quant.search([('reserved_quantity', '!=', 0)])
total_reserved = sum(reserved_quants.mapped('reserved_quantity')) if reserved_quants else 0.0
print(f"Quants con cantidad reservada != 0: {len(reserved_quants)} (Total reservado: {total_reserved:,.2f})")
if 'stock.picking' in env:
    open_pickings = env['stock.picking'].search_count([('state', 'in', ['confirmed', 'waiting', 'assigned'])])
    print(f"Transferencias de inventario pendientes (confirmadas/en espera/listas): {open_pickings}")
    if open_pickings > 0:
        print("  [!] Nota: Revise si hay remitos/recepciones abiertas antes de archivar los productos viejos.")

# 10. Verificación de Esquema SQL de stock_quant
sub('9. Esquema SQL de stock_quant')
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
