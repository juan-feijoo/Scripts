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

active_langs = env['res.lang'].search([('active', '=', True)]).mapped('code')
target_lang = next((l for l in ['es_AR', 'es_419', 'es_ES'] if l in active_langs), env.lang or 'en_US')

# 1. Verificación de Plantillas, Variantes y Ajustes Globales
sub('1. Estado de Plantillas, Variantes y Ajustes')
group_user = env.ref('base.group_user', raise_if_not_found=False)
group_variant = env.ref('product.group_product_variant', raise_if_not_found=False)
if group_user and group_variant:
    var_on = group_variant in group_user.implied_ids
    print(f"Check 'Variantes' (product.group_product_variant): {'[✓] ACTIVO' if var_on else '[!] INACTIVO'}")

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

# Configuración completa de cajas registradoras (preservación de ajustes POS de producción)
configs = PosConfig.search([])
for cfg in configs:
    pl_def = cfg.pricelist_id if hasattr(cfg, 'pricelist_id') else False
    pl_name = f"[{pl_def.id}] {pl_def.with_context(lang=target_lang).name}" if pl_def else 'Sin lista por defecto'
    avail_pls = [f"[{p.id}] {p.with_context(lang=target_lang).name}" for p in cfg.available_pricelist_ids] if hasattr(cfg, 'available_pricelist_ids') else []
    cats_count = len(cfg.pos_category_ids) if hasattr(cfg, 'pos_category_ids') else 0
    tax_inc = getattr(cfg, 'iface_tax_included', 'N/A')
    man_disc = getattr(cfg, 'manual_discount', False)
    glob_disc = getattr(cfg, 'module_pos_discount', False)
    disc_prod = getattr(cfg, 'discount_product_id', False)
    disc_ok = bool(disc_prod and disc_prod.active) if glob_disc else True
    print(f"  * TPV '{cfg.name}':")
    print(f"      - Lista predeterminada: {pl_name} | Listas disponibles ({len(avail_pls)}): {avail_pls}")
    print(f"      - Categorías habilitadas: {cats_count} | Precios c/impuestos (iface_tax_included): '{tax_inc}'")
    print(f"      - Línea descuentos: {man_disc} | Descuentos globales: {glob_disc} | Producto descuento activo: {disc_ok}")

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

# 4. Verificación Exhaustiva de Precios y Listas de Precios
sub('4. Verificación de Precios y Listas de Precios')

# Detectar listas principales
pl_var = Pricelist.search([('name', '=', 'Lista de Precios con Variantes')], limit=1)
if pl_var:
    items_var_count = PricelistItem.search_count([('pricelist_id', '=', pl_var.id), ('applied_on', '=', '0_product_variant')])
    print(f"  [✓] 'Lista de Precios con Variantes' encontrada (ID {pl_var.id}) con {items_var_count} reglas de variantes.")
else:
    print("  [!] 'Lista de Precios con Variantes' no encontrada (modo DRY_RUN previo o pendiente de creación).")

# Lista de precios configurada en TPV
configs = PosConfig.search([])
main_pos_pl = None
for cfg in configs:
    if hasattr(cfg, 'pricelist_id') and cfg.pricelist_id:
        main_pos_pl = cfg.pricelist_id
        break

if not main_pos_pl:
    main_pos_pl = Pricelist.search([('name', '=ilike', '%AR 2%')], limit=1)

if main_pos_pl:
    items_pos_count = PricelistItem.search_count([('pricelist_id', '=', main_pos_pl.id), ('applied_on', '=', '0_product_variant')])
    print(f"  [✓] Lista principal de TPV '{main_pos_pl.name}' (ID {main_pos_pl.id}) con {items_pos_count} reglas de variantes.")

# Verificación de integridad de product_tmpl_id en product_pricelist_item (Odoo 18 requiere ambos en 0_product_variant)
env.cr.execute("""
    SELECT count(*)
    FROM product_pricelist_item ppi
    JOIN product_product pp ON pp.id = ppi.product_id
    WHERE ppi.applied_on = '0_product_variant'
      AND pp.active = TRUE
      AND (ppi.product_tmpl_id IS NULL OR ppi.product_tmpl_id != pp.product_tmpl_id);
""")
misaligned_pl_items = env.cr.fetchone()[0]
if misaligned_pl_items > 0:
    print(f"  [!] Alerta: Hay {misaligned_pl_items} reglas de variante con product_tmpl_id nulo o desalineado.")
else:
    print("  [✓] 100% de las reglas de variantes tienen product_tmpl_id perfectamente alineado (compatible Odoo 18 UI y POS).")

# Comprobar cobertura de precios en variantes Eyelit (list_price preservado + precios reales en Listas de Precios)
eyelit_vars = Product.search([('active', '=', True), ('default_code', '=like', '%.%')])
vars_lp_one = eyelit_vars.filtered(lambda v: abs(v.list_price - 1.0) < 0.01)
print(f"\nEstado de precio base (list_price) en variantes Eyelit ({len(eyelit_vars)} variantes):")
print(f"  - Variantes manteniendo list_price = $1.00 (como producción): {len(vars_lp_one)}")

# Verificar cuántas plantillas activas quedaron con nombre de código SKU (debe ser 0)
import re as _re
sku_named_tmpls = Template.with_context(lang=target_lang).search([('active', '=', True)]).filtered(
    lambda t: bool(_re.match(r'^[0-9A-Z]{5,}\.[0-9A-Z/]+(\s*\([A-Z0-9]+\))?$', (t.name or '').strip()))
)
if sku_named_tmpls:
    print(f"  [!] Alerta: Hay {len(sku_named_tmpls)} plantillas con nombre tipo código SKU:")
    for st in sku_named_tmpls[:5]:
        print(f"      - [ID {st.id}] {st.name}")
else:
    print("  [✓] 0 plantillas con nombre de código SKU (100% agrupadas con nombre humano en español).")

# Cobertura real de precios en las listas de precios (> $1.00)
if pl_var:
    pl_var_real = PricelistItem.search_count([
        ('pricelist_id', '=', pl_var.id),
        ('applied_on', '=', '0_product_variant'),
        ('fixed_price', '>', 1.0),
    ])
    print(f"  - Reglas con precio real (> $1.00) en '{pl_var.name}': {pl_var_real}/{len(eyelit_vars)}")
if main_pos_pl:
    pl_pos_real = PricelistItem.search_count([
        ('pricelist_id', '=', main_pos_pl.id),
        ('applied_on', '=', '0_product_variant'),
        ('fixed_price', '>', 1.0),
    ])
    print(f"  - Reglas con precio real (> $1.00) en '{main_pos_pl.with_context(lang=target_lang).name}': {pl_pos_real}/{len(eyelit_vars)}")

# Muestra de precios e IVA en 5 variantes Eyelit (probando TODAS las listas disponibles en POS con _get_product_price)
pos_eval_pls = []
seen_pl_ids = set()
for cfg in configs:
    if hasattr(cfg, 'available_pricelist_ids'):
        for p in cfg.available_pricelist_ids:
            if p.id not in seen_pl_ids:
                pos_eval_pls.append(p)
                seen_pl_ids.add(p.id)
for fallback_pl in [main_pos_pl, pl_var]:
    if fallback_pl and fallback_pl.id not in seen_pl_ids:
        pos_eval_pls.append(fallback_pl)
        seen_pl_ids.add(fallback_pl.id)

sample_vars = eyelit_vars[:5]
print("\nMuestra de precios e IVA verificados en 5 variantes Eyelit (todas las listas del POS):")
for sv in sample_vars:
    taxes_str = ", ".join(t.name for t in sv.taxes_id) if hasattr(sv, 'taxes_id') and sv.taxes_id else "Sin impuestos"
    p_info = [f"IVA: [{taxes_str}]", f"Base: ${sv.list_price:,.2f}"]
    for eval_pl in pos_eval_pls:
        pl_lbl = f"{eval_pl.with_context(lang=target_lang).name} (ID {eval_pl.id})"
        try:
            computed_val = eval_pl._get_product_price(sv, 1.0)
            p_info.append(f"{pl_lbl}: ${computed_val:,.2f}")
        except Exception:
            r_x = PricelistItem.search([('pricelist_id', '=', eval_pl.id), ('applied_on', '=', '0_product_variant'), ('product_id', '=', sv.id)], limit=1)
            if r_x:
                p_info.append(f"{pl_lbl}: ${r_x.fixed_price:,.2f}")
    print(f"  [{sv.default_code}] {sv.name[:22]} | {' | '.join(p_info)}")

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
