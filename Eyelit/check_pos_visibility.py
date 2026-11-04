# -*- coding: utf-8 -*-
"""
Diagnóstico de Visibilidad en Punto de Venta (POS / TPV) - Odoo 18
"""
print("=" * 80)
print("[*] DIAGNÓSTICO DE PRODUCTOS EN PUNTO DE VENTA (POS)")
print("=" * 80)

Template = env['product.template']
Product = env['product.product']

# 1. Categorías de POS existentes
PosCategory = env['pos.category']
pos_cats = PosCategory.search([])
print(f"Categorías de TPV (pos.category) configuradas: {len(pos_cats)}")
for cat in pos_cats:
    print(f"  - [ID {cat.id}] {cat.name}")

# 2. Configuración de los Puntos de Venta (pos.config)
PosConfig = env['pos.config']
pos_configs = PosConfig.search([])
print(f"\nPuntos de Venta configurados (pos.config): {len(pos_configs)}")
for cfg in pos_configs:
    limit_cats = getattr(cfg, 'limit_categories', False)
    if_empty = getattr(cfg, 'if_empty_product_page', False)
    print(f"  - POS '{cfg.name}': limit_categories={limit_cats}")
    if limit_cats and hasattr(cfg, 'pos_category_ids'):
        print(f"    Categorías permitidas: {[c.name for c in cfg.pos_category_ids]}")

# 3. Productos marcados como disponibles en POS
templates_in_pos = Template.search([('available_in_pos', '=', True), ('active', '=', True)])
print(f"\nPlantillas activas con available_in_pos = True: {len(templates_in_pos)}")

# Muestra de las primeras 10 plantillas
for tmpl in templates_in_pos[:10]:
    cats = [c.name for c in tmpl.pos_categ_ids] if hasattr(tmpl, 'pos_categ_ids') else []
    variants_active = Product.search_count([('product_tmpl_id', '=', tmpl.id), ('active', '=', True)])
    print(f"  - [ID {tmpl.id}] '{tmpl.name}' | sale_ok={tmpl.sale_ok} | Variantes activas: {variants_active} | Cat TPV: {cats}")

# 4. Verificar productos en sesión de POS abierta
PosSession = env['pos.session']
open_sessions = PosSession.search([('state', '!=', 'closed')])
print(f"\nSesiones de TPV actualmente abiertas: {len(open_sessions)}")
for s in open_sessions:
    print(f"  - Sesión [ID {s.id}] {s.name} (Usuario: {s.user_id.name}, Estado: {s.state})")
    print(f"    * AVISO: Las sesiones abiertas cargan los productos en memoria del navegador al inicio. Requieren recarga (F5) o cerrar/reabrir.")

print("=" * 80)
