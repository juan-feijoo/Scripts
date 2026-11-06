# -*- coding: utf-8 -*-
# 02 - Monedas, Precisión Decimal e Impuestos de Venta
company = get_company()
h('02 - CONFIGURACIÓN DE MONEDA, PRECISIÓN DECIMAL E IMPUESTOS (%s)' % company.name)

# 1. Monedas
sub('1. Monedas (res.currency)')
currencies = env['res.currency'].search([('name', 'in', ['ARS', 'USD'])])
for cur in currencies:
    print("  Moneda: %s (%s) [ID: %s]" % (cur.name, cur.symbol, cur.id))
    print("    - Redondeo (rounding): %s" % cur.rounding)
    print("    - Lugares decimales (decimal_places): %s" % cur.decimal_places)
    print("    - Posición del símbolo: %s" % cur.position)
    print("    - Activa: %s" % cur.active)
    print("    - Tasa actual: %s\n" % cur.rate)

# 2. Precisión Decimal
sub('2. Precisión Decimal (decimal.precision)')
precisions = env['decimal.precision'].search([])
for dp in precisions:
    print("  - %-30s : %d dígitos" % (dp.name, dp.digits))

# 3. Configuración de la Compañía para Impuestos
sub('3. Configuración de Redondeo en res.company')
print("  - Compañía: %s [ID: %s]" % (company.name, company.id))
print("  - Moneda principal: %s" % company.currency_id.name)
if has_field('res.company', 'tax_calculation_rounding_method'):
    print("  - Método de redondeo de impuestos (tax_calculation_rounding_method): %s" % company.tax_calculation_rounding_method)

# 4. Impuestos de Venta
sub('4. Impuestos de Venta (account.tax)')
sale_taxes = env['account.tax'].search([
    ('type_tax_use', '=', 'sale'),
    ('company_id', 'in', [company.id, False])
])
for tax in sale_taxes:
    print("  [ID: %s] %-35s | Alícuota: %6.2f%% | Tipo: %s | ¿Incluido en precio? (price_include): %s" % (
        tax.id, tax.name, tax.amount, tax.amount_type, tax.price_include
    ))
