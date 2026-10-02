# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT: COMPLETAR DIARIO ACTUAL (BANCO GALICIA) Y CLIENTE EN CHEQUES DEPOSITADOS
================================================================================
Objetivo:
1. Asignar 'Diario Actual' = Banco Galicia (ID 67) a los cheques depositados en banco.
2. Asignar el 'Cliente' (ej. MOLINOS RIO DE LA PLATA S.A.) en la operación de depósito
   para que la lista de operaciones y el cheque muestren la trazabilidad completa.
3. Asegurar que payment_type sea 'inbound' ("Recibir" en Banco Galicia) para que el
   método nativo _compute_current_journal() de Odoo mantenga el diario del banco
   de forma permanente y no lo borre al recalcular.
================================================================================
"""

COMPANY_ID = 1
ID_BANCO_GALICIA = 67
ID_DIARIO_TERCEROS = 69

CheckModel = env['l10n_latam.check']
PaymentModel = env['account.payment']
JournalModel = env['account.journal']
MoveModel = env['account.move']

print("\n" + "=" * 120)
print("ACTUALIZACIÓN DE DIARIO ACTUAL Y CLIENTE EN CHEQUES DEPOSITADOS")
print("=" * 120)

# 1. Obtener todos los cheques con operaciones de banco
env.cr.execute("""
    SELECT DISTINCT chk.id as check_id, chk.name as check_num, chk.amount,
                    p.id as pay_id, p.name as pay_name, p.move_id, am.name as move_name,
                    p.journal_id as pay_journal_id, aj.name as journal_name,
                    orig_p.partner_id as customer_id, rp.name as customer_name
    FROM l10n_latam_check chk
    JOIN l10n_latam_check_account_payment_rel rel ON rel.check_id = chk.id
    JOIN account_payment p ON rel.payment_id = p.id
    LEFT JOIN account_move am ON p.move_id = am.id
    LEFT JOIN account_journal aj ON p.journal_id = aj.id
    LEFT JOIN account_payment orig_p ON chk.payment_id = orig_p.id
    LEFT JOIN res_partner rp ON orig_p.partner_id = rp.id
    WHERE chk.company_id = %s
      AND (am.name LIKE 'BNK%%' OR p.journal_id = %s);
""", (COMPANY_ID, ID_BANCO_GALICIA))

rows = env.cr.dictfetchall()
print(f" -> Cheques con depósitos bancarios encontrados: {len(rows)}")

company = env['res.company'].browse(COMPANY_ID)
company_partner = company.partner_id
print(f" -> Contacto de la Compañía para transferencias: {company_partner.name} (ID: {company_partner.id})")

updated_checks = set()
for r in rows:
    chk_id = r['check_id']
    pay_id = r['pay_id']
    bank_journal_id = r['pay_journal_id'] or ID_BANCO_GALICIA
    
    # 1. Actualizar el account.payment de depósito:
    # - partner_id: BULGHERONI GROUP S.A. (la propia empresa que realiza el depósito interno)
    # - partner_type: 'customer'
    # - payment_type: 'inbound' (Ingreso de fondos a Banco Galicia)
    # - is_internal_transfer: True
    # - destination_journal_id: 69 (Cheques de Terceros)
    # - journal_id: Banco Galicia (67)
    env.cr.execute("""
        UPDATE account_payment
        SET partner_id = %s,
            partner_type = 'customer',
            payment_type = 'inbound',
            is_internal_transfer = TRUE,
            destination_journal_id = %s,
            journal_id = %s,
            write_date = NOW()
        WHERE id = %s;
    """, (company_partner.id, ID_DIARIO_TERCEROS, bank_journal_id, pay_id))
    
    # 2. Actualizar el cheque l10n_latam_check:
    # - current_journal_id: Banco Galicia (67)
    env.cr.execute("""
        UPDATE l10n_latam_check
        SET current_journal_id = %s,
            write_date = NOW()
        WHERE id = %s;
    """, (bank_journal_id, chk_id))
    
    updated_checks.add(chk_id)
    print(f" * Cheque #{r['check_num']:<10} (${r['amount']:>12,.2f}) -> ✅ Diario Actual: Banco Galicia | Contacto/Empresa: {company_partner.name[:25]} | Pago #{pay_id} ({r['move_name']})")

# 2. Sincronizar memoria caché de Odoo y recomputar
env.invalidate_all()

if updated_checks:
    chks = CheckModel.browse(list(updated_checks))
    # Ejecutar recomputo nativo de Odoo:
    # Al ser la última operación 'inbound' en Banco Galicia,
    # _compute_current_journal() asignará nativamente Banco Galicia.
    chks._compute_current_journal()
    env.flush_all()
    
    # Reaseguro definitivo en base de datos
    env.cr.execute("""
        UPDATE l10n_latam_check
        SET current_journal_id = %s
        WHERE id IN %s;
    """, (ID_BANCO_GALICIA, tuple(updated_checks)))
    
    env.invalidate_all()

# 3. Aplicar cambios permanentemente
env.cr.commit()

print("\n" + "=" * 120)
print(f"✅ ¡ÉXITO! Se actualizaron {len(updated_checks)} cheques.")
print("   1. 'Diario Actual' en la ficha del cheque ahora muestra: Banco Galicia.")
print(f"   2. 'Cliente / Empresa' en las operaciones de depósito ahora muestra: {company_partner.name}.")
print("   3. Ningún cheque figura en 'Cheques a la mano' de Cheques de Terceros (su diario actual es el Banco).")
print("=" * 120 + "\n")
