# -*- coding: utf-8 -*-
"""
Prueba unitaria de creación de un cheque propio en Odoo 19 Enterprise (l10n_latam_check).
Ejecución: python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < test_crear_un_cheque_19.py
"""

print("\n" + "=" * 80)
print("TEST UNITARIO: CREACIÓN DE PAGO CON CHEQUE PROPIO (ODOO 19)")
print("=" * 80)

try:
    partner = env['res.partner'].search([('vat', '=', '30710094337')], limit=1)
    if not partner:
        partner = env['res.partner'].browse(5776)

    journal = env['account.journal'].browse(36) # BNK1
    pml = env['account.payment.method.line'].browse(35) # Own Checks

    print(f"Partner: {partner.name} (ID: {partner.id})")
    print(f"Journal: {journal.name} (ID: {journal.id})")
    print(f"Payment Method Line: {pml.name} (Code: {pml.payment_method_id.code})")

    # Valores para crear el account.payment vinculando el cheque propio en l10n_latam_new_check_ids
    payment_vals = {
        'payment_type': 'outbound',
        'partner_type': 'supplier',
        'partner_id': partner.id,
        'amount': 1135295.00,
        'date': '2026-10-28',
        'journal_id': journal.id,
        'payment_method_line_id': pml.id,
        'l10n_latam_new_check_ids': [(0, 0, {
            'name': '70747825',
            'payment_date': '2026-11-28',
            'amount': 1135295.00,
            'partner_id': partner.id,
            'memo': 'ECHEQ 70747825',
        })],
    }
    if 'memo' in env['account.payment']._fields:
        payment_vals['memo'] = 'ECHEQ 70747825 - INDUSTRIAS TECNOMATRIC SRL'

    print("\nCreando account.payment de prueba...")
    payment = env['account.payment'].create(payment_vals)
    if payment.move_id:
        payment.move_id.ref = 'ECHEQ 70747825 - INDUSTRIAS TECNOMATRIC SRL'
    print(f"[OK] Pago creado: ID {payment.id} | Estado: {payment.state}")
    print(f"Cheques en l10n_latam_new_check_ids: {len(payment.l10n_latam_new_check_ids)}")
    for ch in payment.l10n_latam_new_check_ids:
        print(f"  -> Check ID {ch.id} | Nro: {ch.name} | Cobro: {ch.payment_date} | Monto: {ch.amount}")

    print("\nEjecutando action_post()...")
    payment.action_post()
    print(f"[OK] Pago posteado | Estado: {payment.state}")
    print(f"Asiento generado (move_id): {payment.move_id.name}")
    print("Apuntes contables generados (move lines):")
    for line in payment.move_id.line_ids:
        print(f"  - Cuenta: {line.account_id.code} ({line.account_id.name}) | Debe: ${line.debit:,.2f} | Haber: ${line.credit:,.2f}")

    print("\nEstado de los cheques tras action_post():")
    for ch in payment.l10n_latam_new_check_ids:
        print(f"  -> Check ID {ch.id} | Nro: {ch.name} | issue_state: {getattr(ch, 'issue_state', 'N/A')} | payment_state: {getattr(ch, 'payment_state', 'N/A')}")

except Exception as e:
    import traceback
    print("\n[ERROR EN TEST]:")
    traceback.print_exc()
finally:
    env.cr.rollback()
    print("\n" + "=" * 80)
    print("FIN DEL TEST (ROLLBACK APLICADO - BASE INTACTA)")
    print("=" * 80 + "\n")
