# -*- coding: utf-8 -*-
# 01 - Auditoría detallada de Listas de Precios y Reglas de Redondeo
company = get_company()
h('01 - LISTAS DE PRECIOS Y REGLAS DE CÁLCULO / REDONDEO (%s)' % company.name)

pricelists = env['product.pricelist'].with_company(company).search([])
print("Total de listas de precios encontradas: %d\n" % len(pricelists))

for pl in pricelists:
    sub("Lista [ID: %s] '%s' (Moneda: %s, Compañía: %s, Activa: %s)" % (
        pl.id, pl.name, pl.currency_id.name, pl.company_id.name or 'Global', pl.active
    ))
    
    # Política de descuentos y campos clave
    dump(pl, names=['discount_policy', 'currency_id', 'company_id', 'active'])
    
    items = pl.item_ids
    print("\n  Cantidad de reglas (item_ids): %d" % len(items))
    for idx, item in enumerate(items, 1):
        target = "Global (Todo el catálogo)"
        if item.applied_on == '2_product_category':
            target = "Categoría: %s" % (item.categ_id.display_name if item.categ_id else 'N/A')
        elif item.applied_on == '1_product':
            target = "Plantilla: %s" % (item.product_tmpl_id.display_name if item.product_tmpl_id else 'N/A')
        elif item.applied_on == '0_product_variant':
            target = "Variante: %s" % (item.product_id.display_name if item.product_id else 'N/A')
            
        print("\n    Regla #%d [ID: %s] | Aplica a: %s (%s)" % (idx, item.id, item.applied_on, target))
        print("      - Método de cálculo (compute_price): %s" % item.compute_price)
        
        if item.compute_price == 'fixed':
            print("      - Precio Fijo: %s" % item.fixed_price)
        elif item.compute_price == 'percentage':
            print("      - Porcentaje de Descuento: %s %%" % item.percent_price)
        elif item.compute_price == 'formula':
            base_desc = item.base
            if item.base == 'pricelist' and item.base_pricelist_id:
                base_desc += " -> Lista '%s' [ID: %s]" % (item.base_pricelist_id.name, item.base_pricelist_id.id)
            print("      - Base de cálculo: %s" % base_desc)
            print("      - Descuento (price_discount): %s %%" % item.price_discount)
            print("      - Margen extra / Recargo (price_surcharge): %s" % item.price_surcharge)
            print("      - MÉTODO DE REDONDEO (price_round): %s" % item.price_round)
            print("      - Margen Mínimo: %s | Margen Máximo: %s" % (item.price_min_margin, item.price_max_margin))
            
        print("      - Cantidad Mínima: %s" % item.min_quantity)
        if item.date_start or item.date_end:
            print("      - Vigencia: desde %s hasta %s" % (item.date_start, item.date_end))
