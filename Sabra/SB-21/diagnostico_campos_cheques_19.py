# -*- coding: utf-8 -*-
"""
Diagnóstico de campos y flujo de Cheques Propios en Odoo 19 Enterprise.
Ejecución: python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < diagnostico_campos_cheques_19.py
"""

print("\n" + "=" * 80)
print("DIAGNÓSTICO TÉCNICO: CAMPOS Y ARQUITECTURA DE CHEQUES EN ODOO 19")
print("=" * 80)

# 1. Campos del modelo l10n_latam.check
if 'l10n_latam.check' in env:
    check_model = env['l10n_latam.check']
    fields = check_model.fields_get()
    print("\n--- CAMPOS DE 'l10n_latam.check' ---")
    for fname, finfo in sorted(fields.items()):
        print(f"  - {fname.ljust(25)} : {finfo['type'].ljust(12)} | {finfo.get('string', '')}")
else:
    print("\n'l10n_latam.check' NO existe.")

# 2. Todos los campos de account.payment que contengan 'check', 'latam', 'date' o 'own'
p_fields = env['account.payment'].fields_get()
print("\n--- CAMPOS RELEVANTES EN 'account.payment' ---")
for fname, finfo in sorted(p_fields.items()):
    if any(k in fname.lower() for k in ['check', 'latam', 'date', 'own', 'method', 'number']):
        print(f"  - {fname.ljust(30)} : {finfo['type'].ljust(12)} | {finfo.get('string', '')}")

# 3. Inspeccionar el método de pago 'own_checks' (ID 35 en BNK1)
pml = env['account.payment.method.line'].browse(35)
print(f"\n--- MÉTODO DE PAGO ID 35: {pml.name} ---")
print(f"Diario: {pml.journal_id.name} (Code: {pml.journal_id.code})")
print(f"Payment Method Code: {pml.payment_method_id.code}")
print(f"Payment Method Type: {pml.payment_method_id.payment_type}")

# 4. Probar simulación de default_get para un pago con 'own_checks'
print("\n--- SIMULACIÓN DEFAULT_GET PARA 'own_checks' ---")
try:
    test_context = {
        'default_payment_type': 'outbound',
        'default_partner_type': 'supplier',
        'default_journal_id': 36,
        'default_payment_method_line_id': 35,
    }
    defaults = env['account.payment'].with_context(test_context).default_get([
        'payment_type', 'partner_type', 'journal_id', 'payment_method_line_id',
        'amount', 'date'
    ])
    print(f"Defaults obtenidos: {defaults}")
except Exception as e:
    print(f"Error en default_get: {e}")

# 5. Buscar si existe el módulo account_check_printing en la lista de módulos disponibles
mod_printing = env['ir.module.module'].search([('name', '=', 'account_check_printing')])
if mod_printing:
    print(f"\nMódulo 'account_check_printing': Estado actual = '{mod_printing.state}'")
else:
    print("\nMódulo 'account_check_printing' no encontrado en ir.module.module.")

print("\n" + "=" * 80)
print("FIN DIAGNÓSTICO")
print("=" * 80 + "\n")
