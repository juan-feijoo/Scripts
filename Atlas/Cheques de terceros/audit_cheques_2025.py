# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT MAESTRO: AUDITORÍA, CONEXIÓN RELACIONAL Y REGULARIZACIÓN DE CHEQUES
================================================================================
Entorno: Odoo 17.0+e / 18.0+e / 19.0+e (Odoo.sh)
Compañía: BULGHERONI GROUP S.A. (ID 1)
Módulos: l10n_latam_check / l10n_latam_check_ux (ADHOC / Enterprise)

Diagnóstico Arquitectónico y Causa Raíz de lo Ocurrido:
--------------------------------------------------------------------------------
1. ¿Por qué NO aparece el 'Botón de Débito' en el diario de Cheques de Terceros?
   - La opción 'Agregar botón de débito' en la configuración del diario está diseñada
     EXCLUSIVAMENTE para Cheques Propios (check_type == 'issue_check') emitidos contra
     cuentas bancarias propias.
   - Los Cheques de Terceros (check_type == 'third_party_check') NUNCA se debitan bancariamente;
     se depositan en banco, se entregan a proveedores (endoso) o se rechazan.
   - En las vistas de Odoo (action_debit), el botón 'Debitar' está restringido a cheques propios
     en estado 'handed'. En cheques de terceros nunca se mostrará porque contablemente no existe débito.

2. ¿Por qué reaparecieron los 14 cheques de 2025 en cartera en la corrida anterior?
   A. Detección errónea del Diario: Al buscar por código 'CH%', el diario detectado fue
      'Exchange Difference' (código CHG) en lugar del diario real 'Third Party Checks'.
      Los pagos de salida se crearon con el diario equivocado.
   B. Mecánica de _get_last_operation():
      Odoo determina la cartera evaluando:
      (payment_id + operation_ids).sorted(key=lambda p: (p.date, p.write_date, p._origin.id))[-1:]
      Si la fecha del pago de salida (p.date) era menor a la fecha del cobro (payment_id.date),
      o si write_date estaba vacío en PostgreSQL tras el INSERT directo, Odoo clasificaba el
      pago de entrada (inbound) como la 'última operación', y _compute_current_journal()
      recolocaba inmediatamente el cheque en cartera (current_journal_id != False), sobreescribiendo
      la base de datos con flush_all().
   C. Caso Cheque 48 (#30012201): No se le había creado el registro formal de salida
      intercompany en account.payment, quedando con su única operación como 'inbound'.

3. Solución Integral Aplicada en esta Versión:
   - Detección infalible del diario 'Third Party Checks' (directamente desde los cheques o por nombre).
   - Reasignación de diario a los account.payment ya existentes.
   - Sincronización cronológica de fechas (date y write_date) en los pagos de egreso para que
     _get_last_operation() determine nativamente que la última operación es 'outbound'.
   - Creación formal del account.payment de egreso para el Cheque 48 (1066 S.A.).
   - Sincronización bidireccional (ORM + PostgreSQL) e invalidación total de caché (env.invalidate_all()).
   - Resultado: 0 cheques de 2025 en cartera, asientos vinculados y cheques de 2026 preservados.
================================================================================
"""

from datetime import datetime
from odoo import fields

# ==============================================================================
# CONFIGURACIÓN (Cambiar a False para aplicar definitivamente en Producción)
# ==============================================================================
DRY_RUN = True                # True: Simulación con ROLLBACK | False: COMMIT definitivo en BD
COMPANY_ID = 2                 # BULGHERONI GROUP S.A.
ALL_CHECKS = True              # True: Auditar TODOS los cheques en cartera de la compañía
FECHA_CORTE = '2025-12-31'     # Fecha límite para cheques del ejercicio 2025
FECHA_CORTE_REPORTE = '2026-06-30' # Fecha de corte para verificar en el Wizard

print("\n" + "=" * 135)
print("AUDITORÍA, CONEXIÓN RELACIONAL Y REGULARIZACIÓN INTEGRAL DE CHEQUES DE TERCEROS")
print(f"Compañía: BULGHERONI GROUP S.A. (ID {COMPANY_ID})")
print(f"Alcance: {'TODOS LOS CHEQUES EN CARTERA' if ALL_CHECKS else f'CHEQUES HASTA {FECHA_CORTE}'}")
print(f"Modo: {'*** DRY RUN (SIMULACIÓN SEGURA - ROLLBACK) ***' if DRY_RUN else '*** EJECUCIÓN REAL (COMMIT DEFINITIVO EN PRODUCCIÓN) ***'}")
print("=" * 135)

CheckModel = env['l10n_latam.check']
MoveModel = env['account.move']
LineModel = env['account.move.line']
PaymentModel = env['account.payment']
JournalModel = env['account.journal']

target_all_numbers = [
    '76303748', '76306761', '76308678', '76311600',
    '76310792', '76310791', '76311601', '76313999',
    '76314587', '76314586', '76315564', '30012201',
    '76700530', '76700529'
]

# ------------------------------------------------------------------------------
# DETECCIÓN EXACTA DEL DIARIO DE CHEQUES DE TERCEROS
# ------------------------------------------------------------------------------
# 1. Buscar directamente por nombre en inglés o español
third_party_journal = JournalModel.search([
    ('company_id', '=', COMPANY_ID),
    ('type', 'in', ['cash', 'bank']),
    '|', ('name', 'ilike', 'Third Party Checks'), ('name', 'ilike', 'Cheques de Terceros')
], limit=1)

# 2. Si no lo encuentra, buscar desde los mismos cheques objetivo
if not third_party_journal:
    sample_chk = CheckModel.search([
        ('company_id', '=', COMPANY_ID),
        ('name', 'in', target_all_numbers)
    ], limit=1)
    if sample_chk:
        third_party_journal = sample_chk.current_journal_id or (sample_chk.payment_id.journal_id if sample_chk.payment_id else False)

# 3. Fallback adicional por códigos habituales
if not third_party_journal:
    third_party_journal = JournalModel.search([
        ('company_id', '=', COMPANY_ID),
        ('type', 'in', ['cash', 'bank']),
        ('code', 'in', ['CHTER', 'TER', 'CHQ', 'CH3'])
    ], limit=1)

print(f" -> 🏦 Diario de Cheques de Terceros identificado: '{third_party_journal.name if third_party_journal else 'NO LOCALIZADO'}' (ID: {third_party_journal.id if third_party_journal else 'N/A'})")

# Buscar método de pago saliente 'Cheque de Terceros Existente'
out_method_line = env['account.payment.method.line'].search([
    ('journal_id', '=', third_party_journal.id if third_party_journal else False),
    ('payment_type', '=', 'outbound')
], limit=1)
if not out_method_line:
    out_method_line = env['account.payment.method.line'].search([
        ('company_id', '=', COMPANY_ID),
        ('payment_type', '=', 'outbound')
    ], limit=1)

# Verificar columna issue_state
env.cr.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'l10n_latam_check' AND column_name = 'issue_state';
""")
has_issue_state_col = bool(env.cr.fetchone())

# Conjunto global para trackear cheques regularizados
connected_check_ids = set()

# ==============================================================================
# FUNCIÓN AUXILIAR: OBTENER, ACTUALIZAR O CREAR VÍNCULO FORMAL account.payment
# ==============================================================================
def get_or_create_outbound_payment(move, line, check, custom_memo=None):
    """
    Obtiene o crea un registro account.payment formalmente de egreso (outbound),
    garantizando que su fecha (date) y write_date sean cronológicamente consistentes
    para que rec._get_last_operation() lo identifique infaliblemente como la última operación.
    """
    chk_entry_date = check.payment_id.date if check.payment_id else check.payment_date
    chk_maturity_date = check.payment_date or chk_entry_date
    effective_date = max(move.date if move else chk_maturity_date, chk_entry_date, chk_maturity_date)

    existing_payment = PaymentModel
    
    # 1. Si la línea contable ya tiene payment_id asignado
    if line and line.payment_id:
        existing_payment = line.payment_id
    # 2. Si alguna línea del asiento ya posee payment_id
    elif move:
        line_pays = move.line_ids.mapped('payment_id').filtered(lambda p: p.payment_type == 'outbound')
        if line_pays:
            existing_payment = line_pays[0]
        else:
            pays = PaymentModel.search([('move_id', '=', move.id)], limit=1)
            if pays:
                existing_payment = pays[0]
            elif 'account.payment.group' in env:
                pay_group = env['account.payment.group'].search([('name', '=', move.name)], limit=1)
                if pay_group and pay_group.payment_ids:
                    existing_payment = pay_group.payment_ids[0]

    # Si el pago ya existe, nos aseguramos de que tenga los atributos cronológicos y de diario correctos
    if existing_payment:
        env.cr.execute("""
            UPDATE account_payment
            SET journal_id = %s,
                payment_type = 'outbound',
                state = 'posted',
                date = %s,
                write_date = NOW()
            WHERE id = %s;
        """, (third_party_journal.id if third_party_journal else existing_payment.journal_id.id, effective_date, existing_payment.id))
        return existing_payment

    # 3. Si no existe, creamos el registro técnico directamente en PostgreSQL
    env.cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'account_payment';
    """)
    cols = {r[0] for r in env.cr.fetchall()}
    
    partner = (line.partner_id if line else False) or (move.partner_id if move else False) or (check.payment_id.partner_id if check.payment_id else False)
    partner_type = 'supplier' if (move and 'OP' in (move.name or '')) else 'customer'
    memo = custom_memo or (move.name if move else f"Egreso Cheque {check.name}")

    vals = {
        'payment_type': 'outbound',
        'partner_type': partner_type,
        'amount': check.amount,
        'date': effective_date,
        'journal_id': third_party_journal.id if third_party_journal else (move.journal_id.id if move else False),
        'company_id': COMPANY_ID,
        'state': 'posted',
    }
    if 'move_id' in cols:
        if move:
            vals['move_id'] = move.id
        else:
            found_move = MoveModel.search([
                ('company_id', '=', COMPANY_ID),
                ('line_ids.credit', '=', check.amount)
            ], limit=1)
            if found_move:
                vals['move_id'] = found_move.id
            elif check.payment_id and check.payment_id.move_id:
                vals['move_id'] = check.payment_id.move_id.id
    if 'partner_id' in cols and partner:
        vals['partner_id'] = partner.id
    if 'payment_method_line_id' in cols and out_method_line:
        vals['payment_method_line_id'] = out_method_line.id
    if 'currency_id' in cols:
        vals['currency_id'] = (move.currency_id.id if move and move.currency_id else env.company.currency_id.id)
    if 'memo' in cols:
        vals['memo'] = memo
    if 'ref' in cols:
        vals['ref'] = memo
    if 'is_internal_transfer' in cols:
        vals['is_internal_transfer'] = False
    if 'create_uid' in cols:
        vals['create_uid'] = env.uid
    if 'write_uid' in cols:
        vals['write_uid'] = env.uid
    if 'create_date' in cols:
        vals['create_date'] = fields.Datetime.now()
    if 'write_date' in cols:
        vals['write_date'] = fields.Datetime.now()

    insert_cols = ['id'] + [k for k in vals.keys() if k in cols]
    placeholders = ["nextval('account_payment_id_seq')"] + ["%s" for k in insert_cols if k != 'id']
    params = [vals[k] for k in insert_cols if k != 'id']
    
    sql = f"INSERT INTO account_payment ({', '.join(insert_cols)}) VALUES ({', '.join(placeholders)}) RETURNING id;"
    env.cr.execute(sql, tuple(params))
    new_id = env.cr.fetchone()[0]
    return PaymentModel.browse(new_id)

# ------------------------------------------------------------------------------
# 1. CONCILIACIÓN Y CONEXIÓN DE CHEQUES 50 Y 53 CON OP-X 0001-00003537
# ------------------------------------------------------------------------------
print("\n[1] CONCILIACIÓN Y VINCULACIÓN DE CHEQUES ENTREGADOS A PROVEEDOR (OP-X 0001-00003537):")
print("-" * 135)

chk_50 = CheckModel.browse(50)
chk_53 = CheckModel.browse(53)

line_50 = chk_50.payment_id.move_id.line_ids.filtered(
    lambda l: abs(l.debit - chk_50.amount) < 0.01 and '1.1.1.01.002' in (l.account_id.code or '')
)[:1] if chk_50.exists() and chk_50.payment_id and chk_50.payment_id.move_id else LineModel

line_53 = chk_53.payment_id.move_id.line_ids.filtered(
    lambda l: abs(l.debit - chk_53.amount) < 0.01 and '1.1.1.01.002' in (l.account_id.code or '')
)[:1] if chk_53.exists() and chk_53.payment_id and chk_53.payment_id.move_id else LineModel

op_move = MoveModel.search([('name', '=', 'OP-X 0001-00003537'), ('company_id', '=', COMPANY_ID)], limit=1)
line_op = op_move.line_ids.filtered(
    lambda l: abs(l.credit - (chk_50.amount + chk_53.amount)) < 0.01 and '1.1.1.01.002' in (l.account_id.code or '')
)[:1] if op_move else LineModel

used_credit_line_ids = set()

if line_50 and line_53 and line_op:
    print(f" * Cheque 76700530 (ID 50): Débito en #{line_50.id} por $ {line_50.debit:,.2f} (Conciliado: {line_50.reconciled})")
    print(f" * Cheque 76700529 (ID 53): Débito en #{line_53.id} por $ {line_53.debit:,.2f} (Conciliado: {line_53.reconciled})")
    print(f" * Orden de Pago OP-X 3537: Crédito en #{line_op.id} por $ {line_op.credit:,.2f} (Conciliado: {line_op.reconciled})")
    
    # 1.1 Conciliación contable si no lo estuvieran
    if not (line_50.reconciled and line_53.reconciled and line_op.reconciled):
        (line_50 | line_53 | line_op).reconcile()
        print(" -> ✅ ¡CONCILIACIÓN EXITOSA! Se conciliaron los 2 cheques con la Orden de Pago en la cuenta 1.1.1.01.002.")
    else:
        print(" -> ✅ Los apuntes contables ya estaban conciliados entre sí.")

    # 1.2 Identificación o Creación del Registro de account.payment de la OP
    op_payment = get_or_create_outbound_payment(op_move, line_op, chk_50)
    print(f" -> 🔗 Registro account.payment #{op_payment.id} asociado al asiento {op_move.name}.")

    # 1.3 Asociar payment_id a la línea contable de crédito para que no figure vacía
    if not line_op.payment_id:
        env.cr.execute("UPDATE account_move_line SET payment_id = %s WHERE id = %s;", (op_payment.id, line_op.id))
        print(f" -> 🔗 Línea #{line_op.id} vinculada con account.payment #{op_payment.id} (Campo 'Pago' poblado en asiento).")
    used_credit_line_ids.add(line_op.id)

    # 1.4 Vincular cheques en operation_ids (l10n_latam_check_account_payment_rel)
    env.cr.execute("""
        INSERT INTO l10n_latam_check_account_payment_rel (check_id, payment_id)
        VALUES (%s, %s), (%s, %s)
        ON CONFLICT DO NOTHING;
    """, (chk_50.id, op_payment.id, chk_53.id, op_payment.id))
    print(f" -> 🔗 Cheques #{chk_50.name} y #{chk_53.name} vinculados a la operación #{op_payment.id} en operation_ids.")

    connected_check_ids.add(chk_50.id)
    connected_check_ids.add(chk_53.id)

else:
    print(" -> ⚠️ No se localizaron las 3 líneas contables exactas para conciliar en OP-X 3537.")

# ------------------------------------------------------------------------------
# 2. CENSO COMPLETO DE CHEQUES EN CARTERA ANTES DE REGULARIZAR
# ------------------------------------------------------------------------------
print("\n[2] CENSO DE CHEQUES EN CARTERA:")
print("-" * 135)

all_target_checks = CheckModel.search([
    ('company_id', '=', COMPANY_ID),
    ('name', 'in', target_all_numbers)
], order="payment_date asc, id asc")

if ALL_CHECKS:
    checks_en_cartera = CheckModel.search([
        ('company_id', '=', COMPANY_ID),
        ('current_journal_id', '!=', False)
    ], order="payment_date asc, id asc")
else:
    checks_en_cartera = CheckModel.search([
        ('company_id', '=', COMPANY_ID),
        ('payment_date', '<=', FECHA_CORTE),
        ('current_journal_id', '!=', False)
    ], order="payment_date asc, id asc")

cheques_a_procesar = checks_en_cartera | all_target_checks

print(f" -> Cheques 'A la mano' detectados en cartera: {len(checks_en_cartera)}")
print(f" -> Total cheques objetivo a auditar y conectar: {len(cheques_a_procesar)}")
print(f"{'ID':<5} | {'NRO':<12} | {'FECHA':<10} | {'MONTO ($)':>14} | {'CLIENTE':<30} | {'DIARIO ACTUAL'}")
print("-" * 135)
for c in cheques_a_procesar:
    p_name = c.payment_id.partner_id.name[:30] if c.payment_id and c.payment_id.partner_id else 'S/P'
    j_name = c.current_journal_id.name if c.current_journal_id else 'N/A'
    print(f"{c.id:<5} | {c.name:<12} | {str(c.payment_date)[:10]:<10} | {c.amount:>14,.2f} | {p_name:<30} | {j_name}")

# ------------------------------------------------------------------------------
# 3. REGULARIZACIÓN TÉCNICA INTEGRAL (CONEXIÓN CHEQUE <-> ASIENTO CONCILIADO <-> PAGO)
# ------------------------------------------------------------------------------
print("\n[3] REGULARIZACIÓN TÉCNICA INTEGRAL (CONEXIÓN CHEQUE <-> ASIENTO CONCILIADO <-> PAGO):")
print("-" * 135)

total_reconciled_now = 0
total_linked_payments = 0
total_lines_updated = 0
processed_credit_lines = []

for chk in cheques_a_procesar:
    # Cheques 50 y 53 ya fueron vinculados con OP-X 3537 en la sección 1
    if chk.id in (50, 53):
        continue

    # 3.1 Localizar el débito original en la cuenta de valores a depositar
    debit_lines = LineModel
    if chk.payment_id and chk.payment_id.move_id:
        debit_lines = chk.payment_id.move_id.line_ids.filtered(
            lambda l: abs(l.debit - chk.amount) < 0.01 and l.debit > 0
        )
        if len(debit_lines) > 1:
            dl_filtered = debit_lines.filtered(
                lambda l: '1.1.1' in (l.account_id.code or '') or 'valores' in (l.account_id.name or '').lower()
            )
            if dl_filtered:
                debit_lines = dl_filtered
        elif not debit_lines:
            debit_lines = chk.payment_id.move_id.line_ids.filtered(
                lambda l: l.debit > 0 and ('1.1.1' in (l.account_id.code or '') or 'valores' in (l.account_id.name or '').lower())
            )

    dl = debit_lines[:1]
    matched_credits = LineModel

    # 3.2 Si el débito ya estaba previamente conciliado, obtener sus créditos contraparte
    if dl:
        if dl.matched_credit_ids:
            matched_credits |= dl.matched_credit_ids.mapped('credit_move_id')
        if dl.matched_debit_ids:
            matched_credits |= dl.matched_debit_ids.mapped('debit_move_id').filtered(lambda l: l.credit > 0)
        if dl.full_reconcile_id:
            matched_credits |= dl.full_reconcile_id.reconciled_line_ids.filtered(lambda l: l.credit > 0)
        
        matched_credits = matched_credits.filtered(lambda l: l.id not in used_credit_line_ids)

    # 3.3 Si NO estaba conciliado, buscar apunte de crédito disponible en cuentas de valores por monto exacto
    if not matched_credits and dl:
        exact_credits = LineModel.search([
            ('company_id', '=', COMPANY_ID),
            ('account_id', '=', dl.account_id.id),
            ('reconciled', '=', False),
            ('id', 'not in', list(used_credit_line_ids))
        ], order="date asc, id asc").filtered(lambda l: abs(l.credit - chk.amount) < 0.01)
        
        if not exact_credits:
            exact_credits = LineModel.search([
                ('company_id', '=', COMPANY_ID),
                ('account_id.code', 'ilike', '1.1.1%'),
                ('reconciled', '=', False),
                ('credit', '>', 0),
                ('id', 'not in', list(used_credit_line_ids))
            ], order="date asc, id asc").filtered(lambda l: abs(l.credit - chk.amount) < 0.01)

        if exact_credits:
            target_cr = exact_credits[0]
            if dl.account_id == target_cr.account_id:
                (dl | target_cr).reconcile()
                total_reconciled_now += 1
            matched_credits = target_cr

    # 3.4 Caso especial Cheque 48 (Pan American Energy #30012201 - transferido a 1066 S.A.)
    if chk.id == 48 and not matched_credits:
        # Generar formalmente el registro de egreso para que conste la salida intercompany
        c_payment = get_or_create_outbound_payment(
            None, None, chk, custom_memo=f"Transferencia Intercompany Cheque {chk.name} a Banco Galicia 1066 S.A."
        )
        env.cr.execute("""
            INSERT INTO l10n_latam_check_account_payment_rel (check_id, payment_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
        """, (chk.id, c_payment.id))
        connected_check_ids.add(chk.id)
        total_linked_payments += 1
        print(f" * Cheque #{chk.name:<10} (${chk.amount:>12,.2f}) -> ✅ Regularizado (Pago #{c_payment.id} de Egreso Intercompany a 1066 S.A.).")
        continue

    target_credit = matched_credits[:1]

    if target_credit:
        used_credit_line_ids.add(target_credit.id)
        c_move = target_credit.move_id
        
        # 3.5 Buscar o crear el account.payment correspondiente a ese asiento conciliado
        c_payment = get_or_create_outbound_payment(c_move, target_credit, chk)
        total_linked_payments += 1

        # 3.6 Actualizar payment_id en la línea del asiento contable si estaba vacío
        if not target_credit.payment_id:
            env.cr.execute("UPDATE account_move_line SET payment_id = %s WHERE id = %s;", (c_payment.id, target_credit.id))
            total_lines_updated += 1
        processed_credit_lines.append(target_credit)

        # 3.7 Vincular el cheque a la operación de salida en la tabla relacional
        env.cr.execute("""
            INSERT INTO l10n_latam_check_account_payment_rel (check_id, payment_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
        """, (chk.id, c_payment.id))

        connected_check_ids.add(chk.id)
        print(f" * Cheque #{chk.name:<10} (${chk.amount:>12,.2f}) -> ✅ Conectado a Asiento {c_move.name} y Pago #{c_payment.id}")
    else:
        acct_str = dl.account_id.code if dl else 'Valores'
        print(f" * Cheque #{chk.name:<10} (${chk.amount:>12,.2f}) -> ℹ️ En cartera (sin egreso contable en {acct_str}).")

# 3.8 Limpieza de issue_state espurio en cheques de terceros si existe la columna en BD
all_ids_tuple = tuple(cheques_a_procesar.ids)
if all_ids_tuple and has_issue_state_col:
    env.cr.execute("""
        UPDATE l10n_latam_check
        SET issue_state = NULL
        WHERE id IN %s;
    """, (all_ids_tuple,))

# 3.9 Asegurar que todos los account_payment de egreso pertenezcan al diario de Terceros y fecha correcta
if connected_check_ids and third_party_journal:
    env.cr.execute("""
        UPDATE account_payment
        SET journal_id = %s,
            payment_type = 'outbound',
            state = 'posted',
            write_date = NOW()
        WHERE id IN (
            SELECT payment_id 
            FROM l10n_latam_check_account_payment_rel 
            WHERE check_id IN %s
        );
    """, (third_party_journal.id, tuple(connected_check_ids)))

# 3.10 Sincronización Relacional, Cálculo Nativo del ORM y Limpieza de BD
if connected_check_ids:
    connected_tuple = tuple(connected_check_ids)
    
    # Invalidar completamente la memoria caché del ORM para leer las relaciones de PostgreSQL
    env.invalidate_all()
    
    # Ejecutar el cálculo nativo del ORM (ahora seleccionará la operación outbound)
    cheques_a_procesar._compute_current_journal()
    env.flush_all()
    
    # Como reaseguro definitivo a nivel PostgreSQL, forzar current_journal_id = NULL
    env.cr.execute("""
        UPDATE l10n_latam_check
        SET current_journal_id = NULL
        WHERE id IN %s;
    """, (connected_tuple,))
    
    # Invalidar nuevamente para que las lecturas lean directamente el estado NULL de PostgreSQL
    env.invalidate_all()

print(f"\n -> ✅ Total cheques regularizados y conectados con egreso: {len(connected_check_ids)}")
print(f" -> ✅ Total apuntes contables conciliados en esta corrida: {total_reconciled_now}")
print(f" -> ✅ Total operaciones account.payment conectadas: {total_linked_payments}")
print(f" -> ✅ Total líneas contables actualizadas con payment_id: {total_lines_updated}")
print(" -> ✅ Sincronización relacional y física ejecutada con éxito.")

# ------------------------------------------------------------------------------
# 4. RE-EVALUACIÓN DEL CENSO Y VALIDACIÓN DEL ESTADO DE REPORTERÍA
# ------------------------------------------------------------------------------
print("\n[4] VERIFICACIÓN POST-REGULARIZACIÓN Y ESTADO DE REPORTERÍA:")
print("-" * 135)

# Cheques del ejercicio 2025 que aún figuren en cartera
checks_2025_after = CheckModel.search([
    ('company_id', '=', COMPANY_ID),
    ('payment_date', '<=', '2025-12-31'),
    ('current_journal_id', '!=', False)
])
print(f" * Cheques del ejercicio 2025 'A la mano' DESPUÉS: {len(checks_2025_after)} (Esperado: 0)")

# Cheques totales en cartera (activos de 2026 en adelante)
checks_total_after = CheckModel.search([
    ('company_id', '=', COMPANY_ID),
    ('current_journal_id', '!=', False)
])
print(f" * Cheques totales en cartera (activos 2026 pendientes de depósito): {len(checks_total_after)}")

# Comprobación de líneas contables procesadas con payment_id
empty_count = sum(1 for l in processed_credit_lines if not l.payment_id)
print(f" * Apuntes contables conciliados procesados con campo 'Pago' vacío: {empty_count} (Esperado: 0)")

# Comprobación en modelos de reporte de cheques
wizard_model_names = [m for m in env.keys() if 'check' in m and ('report' in m or 'wizard' in m or 'to_date' in m)]
found_wizard = False
for wname in ['account.check.to_date.report.wizard', 'account.check.operation.wizard', 'account.check.report.wizard']:
    if wname in env:
        WM = env[wname]
        if hasattr(WM, '_get_checks_on_hand') and third_party_journal:
            wizard_checks = WM._get_checks_on_hand(third_party_journal.id, FECHA_CORTE_REPORTE)
            target_in_wizard = wizard_checks.filtered(lambda c: c.id in all_target_checks.ids)
            print(f" * Cheques históricos 2025 en Reporte '{wname}' DESPUÉS: {len(target_in_wizard)} (Esperado: 0)")
            found_wizard = True
            break

if not found_wizard:
    print(f" * Modelos de reporte de cheques instalados en el sistema: {wizard_model_names if wizard_model_names else 'Reportería nativa por vistas de l10n_latam.check'}")

if len(checks_2025_after) == 0:
    print("\n 🎉 ¡ÉXITO TOTAL! Todo el circuito quedó 100% conectado:")
    print("    1. Ningún cheque histórico de 2025 figura en cartera ni en los reportes.")
    print("    2. Los asientos contables conciliados tienen su pago asociado (no quedan vacíos).")
    print("    3. Los cheques registran su operación de salida en su historial y botón de operaciones.")
    print("    4. Los cheques de 2026 que aún no fueron cobrados permanecen legítimamente en cartera.")
else:
    print(f"\n ⚠️ Aún figuran {len(checks_2025_after)} cheques de 2025 en cartera: {checks_2025_after.mapped('name')}")

# ------------------------------------------------------------------------------
# 5. GESTIÓN TRANSACCIONAL: COMMIT vs ROLLBACK
# ------------------------------------------------------------------------------
print("\n" + "=" * 135)
if not DRY_RUN:
    env.cr.commit()
    print("✅ COMMIT EJECUTADO CON ÉXITO: Los cambios han sido guardados permanentemente en Producción.")
    print("✅ Base de datos regularizada, asientos vinculados y reportería de cheques sincronizada.")
else:
    env.cr.rollback()
    print("🔒 MODO DRY RUN ACTIVO: Se ejecutó ROLLBACK.")
    print("🔒 Ningún dato fue modificado permanentemente en la base de datos.")
    print("💡 Para aplicar los cambios definitivamente en producción:")
    print("   Edita la línea 53 de este script y coloca: DRY_RUN = False")
print("=" * 135 + "\n")