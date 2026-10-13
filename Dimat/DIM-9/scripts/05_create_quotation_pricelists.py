# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT 05: CREACIÓN DE LISTAS DE PRECIOS PARA COTIZACIONES (FÓRMULAS DINÁMICAS)
================================================================================
Entorno: Odoo 17.0+e / 18.0+e / 19.0+e (Odoo Shell)
Lógica del Ticket:
    1. Lista Nivel 1: +40% de recargo sobre la lista base de costos.
    2. Lista Nivel 2: -3% de descuento sobre la lista Nivel 1 (+40%).
    
Implementación recomendada: Fórmulas nativas encadenadas (compute_price = 'formula').
Ventaja: Solo requiere 1 regla por lista (applied_on = '3_global'). Cuando se
actualiza un costo en la lista base, las cotizaciones se actualizan automáticamente
en tiempo real sin necesidad de volver a correr scripts.

Uso en Odoo Shell:
    python3 odoo-bin shell -d <nombre_bd> < scripts/05_create_quotation_pricelists.py
================================================================================
"""

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
DRY_RUN = False  # <<-- Cambiar a False para impactar en producción

# Nombres de las listas base que ya creamos
BASE_NAME_ARS = "DIMAT - Lista General (ARS)"
BASE_NAME_USD = "DIMAT - Lista General (USD)"

# Nombres de las nuevas listas de cotización
NAME_COTIZACION_40_ARS = "DIMAT - Cotizaciones (+40%) (ARS)"
NAME_COTIZACION_40_USD = "DIMAT - Cotizaciones (+40%) (USD)"

NAME_COTIZACION_DESC_ARS = "DIMAT - Cotizaciones Descuento (-3%) (ARS)"
NAME_COTIZACION_DESC_USD = "DIMAT - Cotizaciones Descuento (-3%) (USD)"

COMPANY_NAME = "DROGUERIA DIMAT SA"

print("\n" + "="*80)
print(f" CREACIÓN DE TARIFAS DE COTIZACIÓN (DRY_RUN = {DRY_RUN}) ".center(80, "="))
print("="*80)

# 1. Obtener compañía
company = env['res.company'].search([('name', 'ilike', COMPANY_NAME)], limit=1) or env.company
print(f"[*] Compañía: [{company.id}] {company.name}")

# 2. Localizar listas base
pl_base_ars = env['product.pricelist'].search([
    ('name', '=', BASE_NAME_ARS),
    '|', ('company_id', '=', company.id), ('company_id', '=', False)
], limit=1)

pl_base_usd = env['product.pricelist'].search([
    ('name', '=', BASE_NAME_USD),
    '|', ('company_id', '=', company.id), ('company_id', '=', False)
], limit=1)

if not pl_base_ars:
    raise ValueError(f"No se encontró la lista base ARS: '{BASE_NAME_ARS}'")
if not pl_base_usd:
    raise ValueError(f"No se encontró la lista base USD: '{BASE_NAME_USD}'")

print(f"[*] Lista Base ARS localizada: [{pl_base_ars.id}] {pl_base_ars.name} ({len(pl_base_ars.item_ids)} items)")
print(f"[*] Lista Base USD localizada: [{pl_base_usd.id}] {pl_base_usd.name} ({len(pl_base_usd.item_ids)} items)")

# ==============================================================================
# FUNCIÓN AUXILIAR: CREAR O ACTUALIZAR TARIFA CON FÓRMULA GLOBAL
# ==============================================================================
def setup_formula_pricelist(name, currency, base_pl, discount_percent, desc_info):
    """
    Crea o actualiza una lista de precios con fórmula global encadenada.
    discount_percent:
        - Si es -40.0: aplica recargo del 40% (Odoo: precio = base - (base * (-40/100)) = base * 1.40)
        - Si es 3.0: aplica descuento del 3% (Odoo: precio = base - (base * (3/100)) = base * 0.97)
    """
    pl = env['product.pricelist'].search([
        ('name', '=', name),
        '|', ('company_id', '=', company.id), ('company_id', '=', False)
    ], limit=1)
    
    if not pl:
        pl = env['product.pricelist'].create({
            'name': name,
            'currency_id': currency.id,
            'company_id': company.id,
            'active': True,
        })
        print(f"\n  [+] Tarifa CREADA: '{name}' (ID: {pl.id})")
    else:
        print(f"\n  [=] Tarifa EXISTENTE: '{name}' (ID: {pl.id})")

    # Buscar si ya tiene una regla global aplicada a toda la lista
    rule = pl.item_ids.filtered(lambda r: r.applied_on == '3_global')
    rule_vals = {
        'pricelist_id': pl.id,
        'applied_on': '3_global',
        'compute_price': 'formula',
        'base': 'pricelist',
        'base_pricelist_id': base_pl.id,
        'price_discount': discount_percent,
        'price_round': 0.01,
        'min_quantity': 0,
        'company_id': company.id,
    }
    
    if rule:
        rule.write(rule_vals)
        print(f"      Regla global ACTUALIZADA: {desc_info} sobre [{base_pl.id}] {base_pl.name}")
    else:
        env['product.pricelist.item'].create(rule_vals)
        print(f"      Regla global CREADA: {desc_info} sobre [{base_pl.id}] {base_pl.name}")
        
    return pl

# ==============================================================================
# 3. CREAR LISTAS NIVEL 1: +40% SOBRE BASE (price_discount = -40.0)
# ==============================================================================
print("\n" + "-"*80)
print(" CONFIGURANDO LISTAS DE COTIZACIÓN (+40% SOBRE COSTO) ".center(80, "-"))
print("-"*80)

# ARS (+40%)
pl_cotiz_40_ars = setup_formula_pricelist(
    name=NAME_COTIZACION_40_ARS,
    currency=pl_base_ars.currency_id,
    base_pl=pl_base_ars,
    discount_percent=-40.0,
    desc_info="Recargo de +40%"
)

# USD (+40%)
pl_cotiz_40_usd = setup_formula_pricelist(
    name=NAME_COTIZACION_40_USD,
    currency=pl_base_usd.currency_id,
    base_pl=pl_base_usd,
    discount_percent=-40.0,
    desc_info="Recargo de +40%"
)

# ==============================================================================
# 4. CREAR LISTAS NIVEL 2: -3% SOBRE NIVEL 1 (price_discount = 3.0)
# ==============================================================================
print("\n" + "-"*80)
print(" CONFIGURANDO LISTAS DE DESCUENTO (-3% SOBRE COTIZACIÓN) ".center(80, "-"))
print("-"*80)

# ARS (-3%)
pl_cotiz_desc_ars = setup_formula_pricelist(
    name=NAME_COTIZACION_DESC_ARS,
    currency=pl_base_ars.currency_id,
    base_pl=pl_cotiz_40_ars,
    discount_percent=3.0,
    desc_info="Descuento de -3%"
)

# USD (-3%)
pl_cotiz_desc_usd = setup_formula_pricelist(
    name=NAME_COTIZACION_DESC_USD,
    currency=pl_base_usd.currency_id,
    base_pl=pl_cotiz_40_usd,
    discount_percent=3.0,
    desc_info="Descuento de -3%"
)

# ==============================================================================
# 5. SIMULACIÓN DE PRUEBA (CÁLCULO DE UN PRODUCTO MUESTRA)
# ==============================================================================
print("\n" + "="*80)
print(" SIMULACIÓN DE CÁLCULO DE PRECIOS ".center(80, "="))
print("="*80)

sample_item_ars = pl_base_ars.item_ids[:1]
if sample_item_ars and sample_item_ars.product_id:
    p = sample_item_ars.product_id
    costo_ars = sample_item_ars.fixed_price
    # En Odoo _get_product_price() calcula el precio según la tarifa
    p40_ars = pl_cotiz_40_ars._get_product_price(p, 1.0)
    pdesc_ars = pl_cotiz_desc_ars._get_product_price(p, 1.0)
    
    print(f"Producto Muestra ARS: [{p.default_code}] {p.name}")
    print(f"  1. Costo Base (Lista Base ID {pl_base_ars.id}):        $ {costo_ars:,.2f}")
    print(f"  2. Cotización +40% (Lista ID {pl_cotiz_40_ars.id}):       $ {p40_ars:,.2f}  (Costo x 1.40 = ${costo_ars * 1.4:,.2f})")
    print(f"  3. Cotización -3% Desc (Lista ID {pl_cotiz_desc_ars.id}):  $ {pdesc_ars:,.2f}  (Precio +40% x 0.97 = ${p40_ars * 0.97:,.2f})")

sample_item_usd = pl_base_usd.item_ids[:1]
if sample_item_usd and sample_item_usd.product_id:
    p_u = sample_item_usd.product_id
    costo_usd = sample_item_usd.fixed_price
    p40_usd = pl_cotiz_40_usd._get_product_price(p_u, 1.0)
    pdesc_usd = pl_cotiz_desc_usd._get_product_price(p_u, 1.0)
    
    print(f"\nProducto Muestra USD: [{p_u.default_code}] {p_u.name}")
    print(f"  1. Costo Base (Lista Base ID {pl_base_usd.id}):        USD {costo_usd:,.2f}")
    print(f"  2. Cotización +40% (Lista ID {pl_cotiz_40_usd.id}):       USD {p40_usd:,.2f}  (Costo x 1.40 = USD {costo_usd * 1.4:,.2f})")
    print(f"  3. Cotización -3% Desc (Lista ID {pl_cotiz_desc_usd.id}):  USD {pdesc_usd:,.2f}  (Precio +40% x 0.97 = USD {p40_usd * 0.97:,.2f})")

print("="*80)

# ==============================================================================
# GESTIÓN TRANSACCIONAL
# ==============================================================================
if DRY_RUN:
    env.cr.rollback()
    print("\n[!] MODO DRY-RUN ACTIVO: Rollback ejecutado. Las tarifas de cotización no persistieron.")
    print("    Para crearlas definitivamente, cambie DRY_RUN = False y vuelva a ejecutar.")
else:
    env.cr.commit()
    print("\n[OK] MODO PRODUCCIÓN: Tarifas de cotización creadas y confirmadas exitosamente.")
