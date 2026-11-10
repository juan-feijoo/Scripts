# -*- coding: utf-8 -*-
# 07 - Auditoría de movimientos de rechazo y simulación completa del reporte
from odoo import fields

company = get_company()
h('07 - AUDITORÍA DE MOVIMIENTOS DE RECHAZO Y REPORTE (%s)' % company.name)

sub('1. Movimientos en la cuenta 1.1.1.02.006 (Cheque de terceros rechazado)')
acc_rej = env['account.account'].with_company(company).search([('code', '=', '1.1.1.02.006')], limit=1)
if not acc_rej:
    acc_rej = env['account.account'].with_company(company).search([('name', 'ilike', 'terceros rechazado')], limit=1)

if acc_rej:
    lines = env['account.move.line'].with_company(company).search([
        ('account_id', '=', acc_rej.id),
        ('parent_state', '=', 'posted')
    ], order='date desc, id desc')
    print('Total movimientos posted en %s: %d' % (acc_rej.display_name, len(lines)))
    for l in lines:
        try:
            pay = l.payment_id or (l.move_id.payment_ids[:1] if hasattr(l.move_id, 'payment_ids') and l.move_id.payment_ids else None)
            chk_names = []
            if pay:
                if hasattr(pay, 'l10n_latam_new_check_ids') and pay.l10n_latam_new_check_ids:
                    chk_names.extend(pay.l10n_latam_new_check_ids.mapped('name'))
                if hasattr(pay, 'l10n_latam_move_check_ids') and pay.l10n_latam_move_check_ids:
                    chk_names.extend(pay.l10n_latam_move_check_ids.mapped('name'))
            print('  ID=%-6s Fecha=%s Asiento=%-20s Debe=%-10.2f Haber=%-10.2f Partner=%-25s Ref=%-15s Cheques=%s' % (
                l.id, l.date, l.move_id.name, l.debit, l.credit,
                (l.partner_id.name or '')[:25], (l.name or '')[:15], ', '.join(chk_names) if chk_names else 'N/A'
            ))
        except Exception as e:
            print('  Error imprimiendo línea ID=%s: %s' % (l.id, e))

sub('2. Pagos en estado rejected o en diarios de rechazo')
try:
    rej_pays = env['account.payment'].with_company(company).search([
        '|', '|',
        ('state', '=', 'rejected'),
        ('journal_id.code', 'in', ['CSH3', 'CHTER']),
        ('journal_id.name', 'ilike', 'rechaz')
    ], order='date desc, id desc', limit=20)
    print('Pagos detectados (%d):' % len(rej_pays))
    for p in rej_pays:
        print('  ID=%-6s Ref=%-20s Fecha=%s Estado=%-10s Diario=%-20s Imp=%-10.2f Partner=%s' % (
            p.id, p.name, p.date, p.state, p.journal_id.name, p.amount,
            p.partner_id.display_name if p.partner_id else ''
        ))
except Exception as e:
    print('Error en sección 2: %s' % e)

sub('3. Simulación de account.check.to_date.report.wizard')
try:
    Wizard = env['account.check.to_date.report.wizard']
    today = fields.Date.today()

    print('\n-- Ejecutando _get_checks_on_hand SIN filtro de diario (to_date=%s) --' % today)
    checks_all = Wizard._get_checks_on_hand(False, today)
    print('Total cheques en mano devueltos: %d | Importe total: $ %.2f' % (
        len(checks_all), sum(checks_all.mapped('amount'))
    ))
    print('Primeros 15 cheques en el reporte:')
    for c in checks_all[:15]:
        jname = c.current_journal_id.name if c.current_journal_id else 'None'
        print('  ID=%-5s Núm=%-12s Vto=%s Imp=%-11.2f DiarioActual=%-20s Partner=%s' % (
            c.id, c.name, c.payment_date, c.amount, jname[:20], (c.partner_id.name or '')[:30]
        ))

    # Buscar diarios de cheques
    cheq_journals = env['account.journal'].with_company(company).search([
        '|', ('code', 'in', ['CHEQT', 'CSH2']),
        ('name', 'ilike', 'cheque')
    ])
    for j in cheq_journals:
        print('\n-- Ejecutando _get_checks_on_hand para Diario [%s] %s --' % (j.code, j.name))
        checks_j = Wizard._get_checks_on_hand(j.id, today)
        print('Total cheques devueltos para este diario: %d | Importe total: $ %.2f' % (
            len(checks_j), sum(checks_j.mapped('amount'))
        ))
        for c in checks_j[:5]:
            print('  ID=%-5s Núm=%-12s Vto=%s Imp=%-11.2f Partner=%s' % (
                c.id, c.name, c.payment_date, c.amount, (c.partner_id.name or '')[:30]
            ))
except Exception as e:
    print('Error en sección 3: %s' % e)
    traceback.print_exc()

sub('4. Verificación de la vista de búsqueda de l10n_latam.check')
try:
    search_views = env['ir.ui.view'].search([('model', '=', 'l10n_latam.check'), ('type', '=', 'search')])
    for f in search_views:
        print('  View ID=%s: %s' % (f.id, f.name))
        if f.arch and 'checks_on_hand' in f.arch:
            for line in f.arch.splitlines():
                if 'checks_on_hand' in line:
                    print('    Definición checks_on_hand: %s' % line.strip())
except Exception as e:
    print('Error en sección 4: %s' % e)
