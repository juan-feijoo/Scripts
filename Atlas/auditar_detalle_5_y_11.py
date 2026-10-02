# -*- coding: utf-8 -*-
"""
================================================================================
AUDITORÍA DETALLADA: LOS 5 CHEQUES DE LA REUNIÓN VS LOS 11 CHEQUES EN CARTERA
================================================================================
Objetivo:
1. Ver exactamente por qué los 5 cheques de la reunión figuran 'EGRESADO' en Odoo:
   - ¿Qué operaciones tienen en operation_ids?
   - ¿A qué asientos/pagos están vinculados?
2. Ver el detalle de los 11 cheques que actualmente figuran 'A la mano':
   - ¿Por qué no salieron? ¿Tienen depósitos o pagos registrados?
3. Brindar la opción de regularizar:
   - Devolver a cartera los 5 cheques si salieron por error.
   - O dar salida a los 11 cheques si ya debían haber egresado.
================================================================================
"""

CheckModel = env['l10n_latam.check']
PaymentModel = env['account.payment']
MoveModel = env['account.move']
LineModel = env['account.move.line']

target_5_nums = ['30014031', '76713446', '30014086', '30014125', '76714712']
chks_5 = CheckModel.search([('name', 'in', target_5_nums), ('company_id', '=', 1)])

print("\n" + "=" * 135)
print("DETALLE DE LOS 5 CHEQUES QUE DEBERÍAN ESTAR EN CARTERA SEGÚN LA REUNIÓN:")
print("=" * 135)

for c in chks_5:
    print(f"\n📌 Cheque #{c.name} | Monto: $ {c.amount:,.2f} | Fecha: {c.payment_date} | Cliente: {c.partner_id.name if c.partner_id else 'S/P'}")
    print(f"   * Diario Actual: {c.current_journal_id.name if c.current_journal_id else 'Ninguno (EGRESADO/FUERA DE CARTERA)'}")
    print(f"   * Operación de Ingreso (payment_id): #{c.payment_id.id} ({c.payment_id.move_id.name if c.payment_id and c.payment_id.move_id else 'Sin asiento'}) - Tipo: {c.payment_id.payment_type} - Fecha: {c.payment_id.date}")
    
    # Ver operaciones de salida
    if c.operation_ids:
        print(f"   * Operaciones asociadas ({len(c.operation_ids)}):")
        for op in c.operation_ids:
            print(f"      -> Pago #{op.id} | Asiento: {op.move_id.name} | Tipo: {op.payment_type} | Fecha: {op.date} | Diario: {op.journal_id.name} | Estado: {op.state}")
    else:
        print("   * Operaciones asociadas: Ninguna (¿Por qué current_journal_id está en False?)")
        # Revisar si se le modificó directamente en base de datos
        env.cr.execute("SELECT current_journal_id FROM l10n_latam_check WHERE id = %s;", (c.id,))
        raw_j = env.cr.fetchone()[0]
        print(f"      -> En BD raw current_journal_id: {raw_j}")

print("\n" + "=" * 135)
print("DETALLE DE LOS 11 CHEQUES QUE ACTUALMENTE FIGURAN 'A LA MANO':")
print("=" * 135)

current_11 = CheckModel.search([('company_id', '=', 1), ('current_journal_id', '!=', False)], order="payment_date asc")
for c in current_11:
    print(f"\n📌 Cheque #{c.name} (ID {c.id}) | Monto: $ {c.amount:,.2f} | Fecha: {c.payment_date} | Cliente: {c.partner_id.name if c.partner_id else 'S/P'}")
    print(f"   * Diario Actual: {c.current_journal_id.name}")
    print(f"   * Ingreso (payment_id): #{c.payment_id.id} ({c.payment_id.move_id.name if c.payment_id and c.payment_id.move_id else 'Sin asiento'}) - Fecha: {c.payment_id.date}")
    if c.operation_ids:
        print(f"   * Operaciones asociadas ({len(c.operation_ids)}):")
        for op in c.operation_ids:
            print(f"      -> Pago #{op.id} | Asiento: {op.move_id.name} | Tipo: {op.payment_type} | Fecha: {op.date}")
    else:
        print("   * Operaciones de salida: Ninguna (Aún no tiene egreso registrado)")

print("\n" + "=" * 135 + "\n")
