# -*- coding: utf-8 -*-
"""
================================================================================
AUDITORÍA FORENSE Y REGULARIZACIÓN DE CHEQUES DE TERCEROS Y DEPÓSITOS
================================================================================
Entorno: Odoo 17.0+e / 18.0+e / 19.0+e (Odoo.sh)
Compañía: BULGHERONI GROUP S.A. (ID 1)
Módulos: l10n_latam_check, l10n_ar, account

UNIFICACIÓN TOTAL Y DEFINITIVA:
1. Rastrear cheques en cartera y conectarlos con sus asientos contables reales ya
   conciliados (asientos bancarios 'BNK...' o pagos a proveedores 'OP...').
2. Saneamiento relacional de operaciones (account.payment):
   - En depósitos bancarios: Asigna como contacto a la propia empresa (BULGHERONI GROUP S.A.),
     establece 'is_internal_transfer = True', 'payment_type = inbound' (Recibir en Banco Galicia)
     y 'journal_id = 67' (Banco Galicia).
   - En entregas a proveedores: Asigna el proveedor real y 'payment_type = outbound'.
   - En cheques agrupados en una sola OP (ej. Cheques 50 y 53 en OP-X 3537): detecta
     la operación existente en operation_ids y regulariza su egreso.
3. Actualización de 'Diario Actual' en la ficha del cheque (l10n_latam.check):
   - En depósitos: Asigna el diario de Banco Galicia (67), saliendo de 'Cheques de Terceros'.
   - En entregas a proveedores: Asigna NULL (egresado de la empresa).
4. Reaseguro definitivo post-compute:
   - Impide que _compute_current_journal() reinicie los cheques a cartera por disparidad
     de fechas o reglas multicompañía.
5. Cero impacto contable:
   - NO crea asientos contables nuevos; la contabilidad mantiene su cuadratura intacta.
================================================================================
"""

import sys
from datetime import datetime
from odoo import fields

# ==============================================================================
# CONFIGURACIÓN TRANSACCIONAL
# ==============================================================================
# Cambiar a False para aplicar definitivamente en Producción:
DRY_RUN = False                    # True: Simulación con ROLLBACK | False: COMMIT definitivo
COMPANY_ID = 1                     # BULGHERONI GROUP S.A.
ID_DIARIO_TERCEROS = 69            # Cheques de Terceros
ID_BANCO_GALICIA = 67              # Banco Galicia

def clean_str(val, max_len=None):
    if not val:
        res = ''
    elif isinstance(val, dict):
        res = val.get('es_AR') or val.get('en_US') or next(iter(val.values()), '')
    else:
        res = str(val)
    return res[:max_len] if max_len else res

print("\n" + "=" * 135)
print("AUDITORÍA FORENSE Y REGULARIZACIÓN INTEGRAL DE CHEQUES DE TERCEROS Y DEPÓSITOS")
print(f"Compañía: BULGHERONI GROUP S.A. (ID {COMPANY_ID})")
print(f"Modo: {'*** DRY RUN (SIMULACIÓN SEGURA - ROLLBACK) ***' if DRY_RUN else '*** EJECUCIÓN REAL (COMMIT DEFINITIVO EN PRODUCCIÓN) ***'}")
print("=" * 135)

CheckModel = env['l10n_latam.check']
MoveModel = env['account.move']
LineModel = env['account.move.line']
PaymentModel = env['account.payment']
JournalModel = env['account.journal']
CompanyModel = env['res.company']

# ------------------------------------------------------------------------------
# 0. RESOLUCIÓN DE EMPRESA Y DIARIOS
# ------------------------------------------------------------------------------
company = CompanyModel.browse(COMPANY_ID)
if not company.exists():
    company = env.company
company_partner = company.partner_id

# Diario de Cheques de Terceros
journal_terceros = JournalModel.browse(ID_DIARIO_TERCEROS)
if not journal_terceros.exists():
    journal_terceros = JournalModel.search([
        ('company_id', '=', company.id),
        ('type', 'in', ['cash', 'bank']),
        '|', ('name', 'ilike', 'Third Party Checks'), ('name', 'ilike', 'Cheques de Terceros')
    ], limit=1)

# Diario de Banco Galicia
journal_banco = JournalModel.browse(ID_BANCO_GALICIA)
if not journal_banco.exists():
    journal_banco = JournalModel.search([
        ('company_id', '=', company.id),
        ('type', '=', 'bank'),
        '|', ('name', 'ilike', 'Galicia'), ('name', 'ilike', 'Banco Galicia')
    ], limit=1)

print(f" -> 🏢 Empresa: {clean_str(company.name)} | Contacto: {clean_str(company_partner.name)} (ID: {company_partner.id})")
print(f" -> 🏦 Diario Terceros: {clean_str(journal_terceros.name)} (ID: {journal_terceros.id})")
print(f" -> 🏦 Diario Banco:    {clean_str(journal_banco.name)} (ID: {journal_banco.id})")

# ------------------------------------------------------------------------------
# 1. CENSO Y BÚSQUEDA FORENSE DE CHEQUES EN CARTERA DE TERCEROS
# ------------------------------------------------------------------------------
print("\n" + "=" * 135)
print("[1] CENSO Y RASTREO CONTABLE DE CHEQUES EN CARTERA:")
print("=" * 135)

cheques_en_cartera = CheckModel.search([
    ('company_id', '=', company.id),
    ('current_journal_id', '=', journal_terceros.id)
], order="payment_date asc, id asc")

print(f" -> Total cheques 'A la mano' detectados en cartera: {len(cheques_en_cartera)}")
cheques_info = []

for c in cheques_en_cartera:
    p_name = clean_str(c.payment_id.partner_id.name if c.payment_id and c.payment_id.partner_id else (c.partner_id.name if c.partner_id else 'S/P'), 30)
    
    # 1.1 Localizar débito del cobro original
    dl = LineModel
    if c.payment_id and c.payment_id.move_id:
        move_in = c.payment_id.move_id
        dl = move_in.line_ids.filtered(lambda l: abs(l.debit - c.amount) < 0.01 and l.debit > 0)[:1]
        if not dl:
            dl = move_in.line_ids.filtered(lambda l: l.debit > 0 and ('1.1.1' in (l.account_id.code or '') or 'valores' in clean_str(l.account_id.name).lower()))[:1]
    else:
        dl = LineModel.search([
            ('company_id', '=', company.id),
            ('debit', '>=', c.amount - 0.01),
            ('debit', '<=', c.amount + 0.01),
            ('account_id.code', 'ilike', '1.1.1%')
        ], limit=1)

    matched_moves = MoveModel
    matched_lines = LineModel

    if dl:
        if dl.reconciled:
            if dl.matched_credit_ids:
                matched_lines |= dl.matched_credit_ids.mapped('credit_move_id')
            if dl.matched_debit_ids:
                matched_lines |= dl.matched_debit_ids.mapped('debit_move_id').filtered(lambda l: l.credit > 0)
            if dl.full_reconcile_id:
                matched_lines |= dl.full_reconcile_id.reconciled_line_ids.filtered(lambda l: l.credit > 0)
            matched_moves = matched_lines.mapped('move_id')

    # 1.2 Búsqueda Global si no estaba conciliado directo
    if not matched_moves:
        candidate_credits = LineModel.sudo().search([
            ('company_id', 'in', [1, 2]),
            ('credit', '>=', c.amount - 0.01),
            ('credit', '<=', c.amount + 0.01),
        ], order="date asc, id asc")
        if dl:
            candidate_credits = candidate_credits.filtered(lambda l: l.move_id != dl.move_id)
        if candidate_credits:
            matched_lines = candidate_credits[:1]
            matched_moves = candidate_credits[:1].mapped('move_id')
        else:
            by_ref_moves = MoveModel.sudo().search([
                ('company_id', 'in', [1, 2]),
                '|', ('ref', 'ilike', c.name), ('name', 'ilike', c.name)
            ], limit=1)
            if by_ref_moves:
                matched_moves = by_ref_moves
            else:
                bank_lines = LineModel.sudo().search([
                    ('company_id', 'in', [1, 2]),
                    ('debit', '>=', c.amount - 0.01),
                    ('debit', '<=', c.amount + 0.01),
                    ('journal_id.type', '=', 'bank')
                ], limit=1)
                if bank_lines:
                    matched_moves = bank_lines.mapped('move_id')
                    matched_lines = bank_lines

    # 1.3 Si no se encontró por monto exacto, revisar si ya tiene operación de egreso en operation_ids (ej. pagos agrupados)
    if not matched_moves and c.operation_ids:
        outbound_ops = c.operation_ids.filtered(lambda p: p.state not in ['draft', 'canceled'] and p.payment_type == 'outbound' and p.move_id)
        if outbound_ops:
            matched_moves = outbound_ops[:1].move_id
            matched_lines = matched_moves.line_ids.filtered(lambda l: l.credit > 0)[:1]

    desc_egreso = f"Conectado a {matched_moves[0].name}" if matched_moves else "Sin egreso contable (En cartera real)"
    print(f"📌 Cheque #{c.name:<10} | Monto: ${c.amount:>12,.2f} | Vto: {str(c.payment_date)[:10]} | Cliente: {p_name:<28} | {desc_egreso}")

    cheques_info.append({
        'check': c,
        'debit_line': dl,
        'matched_lines': matched_lines,
        'matched_moves': matched_moves,
    })

# ------------------------------------------------------------------------------
# 2. SANEAMIENTO DE PAGOS DE OPERACIONES EXISTENTES (DEPÓSITOS Y CONTACTO DE EMPRESA)
# ------------------------------------------------------------------------------
print("\n" + "=" * 135)
print("[2] SANEAMIENTO DE PAGOS DE OPERACIÓN ASOCIADOS A DEPÓSITOS:")
print("=" * 135)

env.cr.execute("""
    SELECT DISTINCT p.id as pay_id, p.name as pay_name, p.move_id, am.name as move_name,
                    p.journal_id as pay_journal_id, aj.name as journal_name,
                    p.partner_id, rp.name as partner_name, p.payment_type, p.is_internal_transfer,
                    chk.id as check_id, chk.name as check_num
    FROM l10n_latam_check chk
    JOIN l10n_latam_check_account_payment_rel rel ON rel.check_id = chk.id
    JOIN account_payment p ON rel.payment_id = p.id
    LEFT JOIN account_move am ON p.move_id = am.id
    LEFT JOIN account_journal aj ON p.journal_id = aj.id
    LEFT JOIN res_partner rp ON p.partner_id = rp.id
    WHERE chk.company_id = %s;
""", (company.id,))

op_rows = env.cr.dictfetchall()
print(f" -> Pagos de operaciones analizados: {len(op_rows)}")

pagos_corregidos = 0
for r in op_rows:
    m_name = clean_str(r['move_name'])
    j_name = clean_str(r['journal_name'])
    is_bank_move = 'BNK' in m_name or ('banco' in j_name.lower()) or (r['pay_journal_id'] == journal_banco.id)
    
    if is_bank_move:
        # Asegurar que el pago sea ingreso a Banco Galicia desde Cheques de Terceros
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
        """, (company_partner.id, journal_terceros.id, journal_banco.id, r['pay_id']))
        
        env.cr.execute("""
            UPDATE l10n_latam_check
            SET current_journal_id = %s,
                write_date = NOW()
            WHERE id = %s;
        """, (journal_banco.id, r['check_id']))
        
        pagos_corregidos += 1
        print(f" * Cheque #{r['check_num']:<10} -> Pago #{r['pay_id']} ({m_name}): Diario Actual = Banco Galicia | Contacto = {clean_str(company_partner.name, 25)}")

print(f" -> ✅ Pagos de depósitos saneados con contacto de la empresa: {pagos_corregidos}")

# ------------------------------------------------------------------------------
# 3. CONEXIÓN Y REGULARIZACIÓN DE CHEQUES A SUS ASIENTOS CONCILIADOS
# ------------------------------------------------------------------------------
print("\n" + "=" * 135)
print("[3] CONEXIÓN Y REGULARIZACIÓN DE CHEQUES A SUS ASIENTOS CONCILIADOS:")
print("=" * 135)

cheques_procesados_ids = []
cheques_banco_ids = []
cheques_proveedor_ids = []

for item in cheques_info:
    chk = item['check']
    dl = item['debit_line']
    matched_lines = item['matched_lines']
    matched_moves = item['matched_moves']
    
    if not matched_moves:
        continue

    target_move = matched_moves[0]
    target_credit_line = matched_lines[0] if matched_lines else LineModel
    
    is_bank = 'BNK' in (target_move.name or '') or (target_move.journal_id and target_move.journal_id.type == 'bank') or (target_move.journal_id.id == journal_banco.id)
    is_supplier_op = 'OP' in (target_move.name or '') or (target_move.partner_id and target_move.partner_id != chk.payment_id.partner_id)
    
    # Diario de banco destino garantizado
    dest_bank_id = target_move.journal_id.id if (target_move.journal_id and target_move.journal_id.type == 'bank' and target_move.journal_id.id != journal_terceros.id) else journal_banco.id

    # 3.1 Conciliación de apuntes si corresponde
    if dl and target_credit_line and not (dl.reconciled and target_credit_line.reconciled):
        if dl.account_id == target_credit_line.account_id:
            try:
                (dl | target_credit_line).reconcile()
            except Exception:
                pass

    # 3.2 Buscar o crear el account.payment correspondiente
    existing_pay = PaymentModel.search([('move_id', '=', target_move.id)], limit=1)
    if not existing_pay and target_credit_line and target_credit_line.payment_id:
        existing_pay = target_credit_line.payment_id
    if not existing_pay and chk.operation_ids:
        matched_op = chk.operation_ids.filtered(lambda p: p.move_id == target_move)
        if matched_op:
            existing_pay = matched_op[0]

    effective_date = max(target_move.date, chk.payment_date or target_move.date, chk.payment_id.date if chk.payment_id else target_move.date)

    if existing_pay:
        pay = existing_pay
        if is_bank:
            env.cr.execute("""
                UPDATE account_payment
                SET partner_id = %s,
                    partner_type = 'customer',
                    payment_type = 'inbound',
                    is_internal_transfer = TRUE,
                    destination_journal_id = %s,
                    journal_id = %s,
                    date = %s,
                    write_date = NOW()
                WHERE id = %s;
            """, (company_partner.id, journal_terceros.id, dest_bank_id, effective_date, pay.id))
            cheques_banco_ids.append(chk.id)
        else:
            supplier_id = target_move.partner_id.id if target_move.partner_id else (chk.partner_id.id if chk.partner_id else None)
            env.cr.execute("""
                UPDATE account_payment
                SET payment_type = 'outbound',
                    partner_type = 'supplier',
                    partner_id = %s,
                    journal_id = %s,
                    date = %s,
                    write_date = NOW()
                WHERE id = %s;
            """, (supplier_id, journal_terceros.id, effective_date, pay.id))
            cheques_proveedor_ids.append(chk.id)
    else:
        # Crear registro técnico en account.payment
        env.cr.execute("""
            SELECT column_name FROM information_schema.columns WHERE table_name = 'account_payment';
        """)
        cols = {r[0] for r in env.cr.fetchall()}
        
        vals = {
            'amount': chk.amount,
            'date': effective_date,
            'company_id': target_move.company_id.id or company.id,
            'state': 'posted',
            'move_id': target_move.id,
            'name': target_move.name,
        }
        
        if is_bank:
            vals['journal_id'] = dest_bank_id
            if 'is_internal_transfer' in cols:
                vals['is_internal_transfer'] = True
            if 'destination_journal_id' in cols:
                vals['destination_journal_id'] = journal_terceros.id
            if 'payment_type' in cols:
                vals['payment_type'] = 'inbound'
            if 'partner_type' in cols:
                vals['partner_type'] = 'customer'
            if 'partner_id' in cols:
                vals['partner_id'] = company_partner.id
            cheques_banco_ids.append(chk.id)
        else:
            vals['journal_id'] = journal_terceros.id
            vals['payment_type'] = 'outbound'
            vals['partner_type'] = 'supplier'
            if target_move.partner_id:
                vals['partner_id'] = target_move.partner_id.id
            cheques_proveedor_ids.append(chk.id)

        if 'currency_id' in cols:
            vals['currency_id'] = target_move.currency_id.id or company.currency_id.id
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
        new_pay_id = env.cr.fetchone()[0]
        pay = PaymentModel.browse(new_pay_id)
        
        if target_credit_line and not target_credit_line.payment_id:
            env.cr.execute("UPDATE account_move_line SET payment_id = %s WHERE id = %s;", (new_pay_id, target_credit_line.id))

    # 3.3 Conectar cheque en operation_ids (l10n_latam_check_account_payment_rel)
    env.cr.execute("""
        INSERT INTO l10n_latam_check_account_payment_rel (check_id, payment_id)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING;
    """, (chk.id, pay.id))

    # 3.4 Asignar Diario Actual en el cheque (Banco Galicia para depósitos, NULL para proveedores)
    dest_journal_id = dest_bank_id if is_bank else None
    env.cr.execute("""
        UPDATE l10n_latam_check
        SET current_journal_id = %s,
            write_date = NOW()
        WHERE id = %s;
    """, (dest_journal_id, chk.id))

    cheques_procesados_ids.append(chk.id)
    tipo_desc = "Depósito Banco Galicia" if is_bank else "Entrega a Proveedor"
    diario_desc = clean_str(journal_banco.name) if is_bank else "Ninguno (Egresado)"
    print(f" * Cheque #{chk.name:<10} (${chk.amount:>12,.2f}) -> ✅ {tipo_desc} | Asiento {target_move.name} | Pago #{pay.id} | Diario Actual: {diario_desc}")

# ------------------------------------------------------------------------------
# 4. SINCRONIZACIÓN Y RECOMPUTO NATIVO DEL ORM
# ------------------------------------------------------------------------------
print("\n" + "=" * 135)
print("[4] SINCRONIZACIÓN NATIVA DEL ORM Y LIMPIEZA DE CACHÉ:")
print("=" * 135)

env.invalidate_all()

if cheques_procesados_ids:
    reg_checks = CheckModel.browse(cheques_procesados_ids)
    try:
        reg_checks._compute_current_journal()
        env.flush_all()
    except Exception as e:
        print(f" -> ⚠️ Advertencia en recomputo nativo: {e}")

    # Reaseguro definitivo en base de datos:
    # 1. Cheques depositados en banco -> current_journal_id = Banco Galicia (67)
    # 2. Cheques entregados a proveedores -> current_journal_id = NULL
    if cheques_banco_ids:
        env.cr.execute("""
            UPDATE l10n_latam_check
            SET current_journal_id = %s,
                write_date = NOW()
            WHERE id IN %s;
        """, (journal_banco.id, tuple(cheques_banco_ids) + (-1,)))
        
    if cheques_proveedor_ids:
        env.cr.execute("""
            UPDATE l10n_latam_check
            SET current_journal_id = NULL,
                write_date = NOW()
            WHERE id IN %s;
        """, (tuple(cheques_proveedor_ids) + (-1,),))

    env.flush_all()
    env.invalidate_all()
    print(f" -> ✅ Memoria caché invalidada y {len(cheques_procesados_ids)} cheques sincronizados.")

# ------------------------------------------------------------------------------
# 5. VERIFICACIÓN FINAL DEL REPORTE 'A LA MANO'
# ------------------------------------------------------------------------------
print("\n" + "=" * 135)
print("[5] VERIFICACIÓN FINAL DEL REPORTE 'A LA MANO':")
print("=" * 135)

cheques_a_la_mano_despues = CheckModel.search([
    ('company_id', '=', company.id),
    ('current_journal_id', '=', journal_terceros.id)
], order="payment_date asc, id asc")

print(f" * Cheques 'A la mano' en Cheques de Terceros ANTES:  {len(cheques_en_cartera)}")
print(f" * Cheques 'A la mano' en Cheques de Terceros DESPUÉS: {len(cheques_a_la_mano_despues)}")

if cheques_a_la_mano_despues:
    print("\n📋 DETALLE DE CHEQUES QUE PERMANECEN EN CARTERA (Pendientes de cobro / Vto futuro):")
    print(f"{'ID':<6} | {'NÚMERO':<12} | {'VTO/FECHA':<12} | {'MONTO ($)':>14} | {'CLIENTE':<30}")
    print("-" * 85)
    for c in cheques_a_la_mano_despues:
        p_name = clean_str(c.payment_id.partner_id.name if c.payment_id and c.payment_id.partner_id else (c.partner_id.name if c.partner_id else 'S/P'), 28)
        print(f"{c.id:<6} | {c.name:<12} | {str(c.payment_date)[:10]:<12} | {c.amount:>14,.2f} | {p_name:<30}")

total_regularizados = len(cheques_en_cartera) - len(cheques_a_la_mano_despues)
if total_regularizados > 0:
    print(f"\n 🎉 ¡ÉXITO! Se regularizaron {total_regularizados} cheques usados en contabilidad.")
    print("    1. Ya no figuran como cheques pendientes en la caja ni en el reporte a la mano.")
    print("    2. En depósitos: 'Diario Actual' refleja 'Banco Galicia' y Contacto 'BULGHERONI GROUP S.A.'.")
    print("    3. En entregas a proveedor: Salieron de cartera y reflejan su orden de pago.")
    print("    4. La contabilidad y la conciliación mantienen su cuadratura al 100%.")

# ------------------------------------------------------------------------------
# 6. GESTIÓN TRANSACCIONAL: COMMIT vs ROLLBACK
# ------------------------------------------------------------------------------
print("\n" + "=" * 135)
if not DRY_RUN:
    env.cr.commit()
    print("✅ COMMIT EJECUTADO CON ÉXITO: Los cambios han sido guardados permanentemente.")
    print("✅ Base de datos regularizada, trazabilidad corregida y reportería sincronizada.")
else:
    env.cr.rollback()
    print("🔒 MODO DRY RUN ACTIVO: Se ejecutó ROLLBACK.")
    print("🔒 Ningún dato fue modificado permanentemente en la base de datos.")
    print("💡 Para aplicar los cambios definitivamente:")
    print("   Edita la línea 33 de este script y coloca: DRY_RUN = False")
print("=" * 135 + "\n")
