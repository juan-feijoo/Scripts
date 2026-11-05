# -*- coding: utf-8 -*-
"""
Test de compatibilidad para report_product_labels.xml
Comprueba que la lógica funcione tanto con product.template como con product.product
Ejecución: python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < test_compatibilidad_modelos.py
"""

print("\n" + "=" * 80)
print("TEST DE COMPATIBILIDAD TEMPLATE Y PRODUCT")
print("=" * 80)

# 1. Probar con product.template
tmpls = env['product.template'].search([('sale_ok', '=', True)], limit=3)
pl_min = env['product.pricelist'].browse(5)
pl_may = env['product.pricelist'].browse(7)

for t in tmpls:
    print(f"\nProbando product.template: [{t.default_code}] {t.name}")
    is_tmpl = t._name == 'product.template'
    prod_variant = t.product_variant_id if is_tmpl and t.product_variant_id else t
    seller = t.seller_ids and t.seller_ids[0]
    
    price_min = pl_min._get_product_price(prod_variant, 1.0)
    tax_min = t.taxes_id.compute_all(price_min, product=prod_variant)['total_included']
    
    price_may = pl_may._get_product_price(prod_variant, 1.0)
    tax_may = t.taxes_id.compute_all(price_may, product=prod_variant)['total_included']
    
    seller_name = seller.partner_id.name if seller else 'Sin proveedor'
    print(f"  OK -> Prov: {seller_name} | Min c/IVA: {tax_min} | May c/IVA: {tax_may}")

# 2. Probar con product.product
prods = env['product.product'].search([('sale_ok', '=', True)], limit=3)
for p in prods:
    print(f"\nProbando product.product: [{p.default_code}] {p.name}")
    is_tmpl = p._name == 'product.template'
    prod_variant = p.product_variant_id if is_tmpl and p.product_variant_id else p
    seller = p.seller_ids and p.seller_ids[0]
    
    price_min = pl_min._get_product_price(prod_variant, 1.0)
    tax_min = p.taxes_id.compute_all(price_min, product=prod_variant)['total_included']
    
    price_may = pl_may._get_product_price(prod_variant, 1.0)
    tax_may = p.taxes_id.compute_all(price_may, product=prod_variant)['total_included']
    
    seller_name = seller.partner_id.name if seller else 'Sin proveedor'
    print(f"  OK -> Prov: {seller_name} | Min c/IVA: {tax_min} | May c/IVA: {tax_may}")

print("\n" + "=" * 80)
print("TEST COMPLETADO EXITOSAMENTE SIN ERRORES")
print("=" * 80 + "\n")
