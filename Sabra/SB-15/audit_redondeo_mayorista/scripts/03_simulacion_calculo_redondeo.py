# -*- coding: utf-8 -*-
# 03 - Simulación de Cálculo de Precios Mayoristas y Estrategias de Redondeo (DRY-RUN)
import math

company = get_company()
h('03 - SIMULACIÓN DE CÁLCULO MAYORISTA Y ESTRATEGIAS DE REDONDEO (%s)' % company.name)

# 1. Obtener Listas de Precios
pl_min = env['product.pricelist'].browse(MINORISTA_PL_ID)
if not pl_min.exists():
    pl_min = env['product.pricelist'].search([('name', 'ilike', 'ars'), ('company_id', 'in', [company.id, False])], limit=1)

pl_may = env['product.pricelist'].browse(MAYORISTA_PL_ID)
if not pl_may.exists():
    pl_may = env['product.pricelist'].search([('name', 'ilike', 'mayorista'), ('company_id', 'in', [company.id, False])], limit=1)

print("Lista Minorista en uso : [ID: %s] %s" % (pl_min.id if pl_min else 'N/A', pl_min.name if pl_min else 'N/A'))
print("Lista Mayorista en uso : [ID: %s] %s" % (pl_may.id if pl_may else 'N/A', pl_may.name if pl_may else 'N/A'))

# 2. Selección de Productos
sample_codes = ['101500700374', '21819', '1809', '6988776231993', '7795587005106']
products = env['product.product'].with_company(company).search([
    '|', ('default_code', 'in', sample_codes), ('barcode', 'in', sample_codes)
])

if len(products) < 5:
    extra = env['product.product'].with_company(company).search([('sale_ok', '=', True)], limit=10)
    products = (products | extra)[:10]

currency = company.currency_id

sub('TABLA COMPARATIVA DE CÁLCULO Y ALTERNATIVAS DE REDONDEO')
print("Explicación de columnas:")
print("  - LIST PRICE    : Precio de lista en la ficha del producto.")
print("  - MIN. C/IVA    : Precio minorista final (con impuestos).")
print("  - MAY. BASE     : Precio devuelto por la regla mayorista (neto sin IVA).")
print("  - MAY. ACTUAL   : Precio mayorista con IVA actual (con sus decimales).")
print("  - REDOND. $1    : Redondeo al entero más cercano (sin centavos).")
print("  - REDOND. $10   : Redondeo a la decena más cercana.")
print("  - CEIL $10      : Redondeo a la decena siempre hacia arriba.")
print("  - REDOND. $50   : Redondeo al múltiplo de $50.")
print("-" * 125)
header = "%-14s | %-20s | %10s | %10s | %10s | %12s | %10s | %10s | %10s | %10s" % (
    "CÓDIGO", "PRODUCTO", "LIST PRICE", "MIN C/IVA", "MAY BASE", "MAY ACTUAL", "RED $1", "RED $10", "CEIL $10", "RED $50"
)
print(header)
print("-" * 125)

for p in products:
    code = (p.default_code or p.barcode or 'S/C')[:14]
    name = (p.name or '')[:20]
    
    # 1. Minorista
    p_min_base = pl_min._get_product_price(p, 1.0, currency=currency) if pl_min else p.list_price
    t_min = p.taxes_id.compute_all(p_min_base, product=p, partner=False) if p.taxes_id else {'total_included': p_min_base}
    p_min_inc = t_min['total_included']
    
    # 2. Mayorista
    p_may_base = pl_may._get_product_price(p, 1.0, currency=currency) if pl_may else p_min_base
    t_may = p.taxes_id.compute_all(p_may_base, product=p, partner=False) if p.taxes_id else {'total_included': p_may_base}
    p_may_inc = t_may['total_included']
    
    # Estrategias de Redondeo sobre el precio mayorista con IVA
    r_1 = round(p_may_inc)
    r_10 = round(p_may_inc / 10.0) * 10
    c_10 = math.ceil(p_may_inc / 10.0) * 10
    r_50 = round(p_may_inc / 50.0) * 50
    
    line = "%-14s | %-20s | %10.2f | %10.2f | %10.2f | %12.4f | %10.2f | %10.2f | %10.2f | %10.2f" % (
        code, name, p.list_price, p_min_inc, p_may_base, p_may_inc, r_1, r_10, c_10, r_50
    )
    print(line)

print("-" * 125)
print("\nObservaciones sobre el cálculo:")
print("1. Si 'MAY BASE' no tiene centavos pero 'MAY ACTUAL' sí, los centavos provienen de la alícuota de IVA (ej. 21%% sobre una base impar).")
print("2. Si 'MAY BASE' ya tiene centavos, la regla de la lista de precios no tiene configurado 'price_round' (método de redondeo) o tiene un porcentaje fraccionario.")
print("3. Si la empresa busca precios comerciales limpios en la etiqueta, la solución más robusta depende de si se quiere redondear antes o después de impuestos.")
