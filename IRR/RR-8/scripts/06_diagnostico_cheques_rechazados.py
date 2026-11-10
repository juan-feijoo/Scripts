# -*- coding: utf-8 -*-
# 06 - Diagnóstico específico de los 3 cheques rechazados y reporte Cheques a Fecha
import inspect
from odoo import fields

company = get_company()
h('06 - DIAGNÓSTICO ESPECÍFICO DE LOS 3 CHEQUES RECHAZADOS (%s)' % company.name)

target_numbers = ['64943755', '90000059', '90000058']
sub('1. Búsqueda de los 3 cheques en l10n_latam.check por número: %s' % target_numbers)

checks = env['l10n_latam.check'].with_company(company).search([
    ('name', 'in', target_numbers)
])

if not checks:
    print('!! No se encontraron por name in %s. Buscando de forma flexible...' % target_numbers)
    checks = env['l10n_latam.check'].with_company(company).search([
        '|', '|',
        ('name', 'ilike', '64943755'),
        ('name', 'ilike', '90000059'),
        ('name', 'ilike', '90000058')
    ])

print('Total cheques encontrados: %d' % len(checks))

for chk in checks:
    print('\n' + '=' * 80)
    print('CHEQUE ID: %s | Número: %s | Importe: $ %.2f | Fecha Pago/Vto: %s' % (
        chk.id, chk.name, chk.amount, chk.payment_date
    ))
    print('  Partner: %s (CUIT: %s)' % (
        chk.partner_id.display_name if chk.partner_id else 'N/A',
        chk.partner_id.vat if chk.partner_id else 'N/A'
    ))
    print('  Diario actual (current_journal_id): %s (ID=%s, Código=%s)' % (
        chk.current_journal_id.name if chk.current_journal_id else 'None',
        chk.current_journal_id.id if chk.current_journal_id else 'None',
        chk.current_journal_id.code if chk.current_journal_id else 'None'
    ))
    if chk.current_journal_id and chk.current_journal_id.default_account_id:
        acc = chk.current_journal_id.default_account_id
        print('    Cuenta del diario actual: [%s] %s' % (acc.code, acc.name))
        
    print('  Pago origen (payment_id): %s (ID=%s, State=%s, Fecha=%s, Diario=%s)' % (
        chk.payment_id.name if chk.payment_id else 'N/A',
        chk.payment_id.id if chk.payment_id else 'N/A',
        chk.payment_id.state if chk.payment_id else 'N/A',
        chk.payment_id.date if chk.payment_id else 'N/A',
        chk.payment_id.journal_id.name if chk.payment_id and chk.payment_id.journal_id else 'N/A'
    ))
    
    # Inspeccionar todos los campos relevantes del cheque
    dump(chk, prefixes=['state', 'status', 'check', 'l10n_latam', 'operation'])
    
    # Operaciones asociadas al cheque
    if hasattr(chk, 'operation_ids') and chk.operation_ids:
        print('  Operaciones asociadas (%d):' % len(chk.operation_ids))
        for op in chk.operation_ids:
            meth = op.payment_method_id.name if op.payment_method_id else ''
            print('    - Op ID=%-6s Ref=%-20s Fecha=%s Estado=%-10s Tipo=%-10s Método=%-15s Diario=%s' % (
                op.id, op.name or '', op.date, op.state,
                getattr(op, 'payment_type', ''), meth,
                op.journal_id.name if op.journal_id else ''
            ))
            if op.move_id:
                print('        Asiento: %s (id=%s, state=%s, date=%s)' % (
                    op.move_id.name, op.move_id.id, op.move_id.state, op.move_id.date
                ))
                for line in op.move_id.line_ids:
                    print('          Línea [%s] %-25s Debe=%-11.2f Haber=%-11.2f Match=%s' % (
                        line.account_id.code, line.account_id.name[:25],
                        line.debit, line.credit,
                        line.matching_number or (line.reconciled and 'Reconciled') or 'No'
                    ))

sub('2. Inspección del código fuente del Wizard account.check.to_date.report.wizard')
Wizard = env['account.check.to_date.report.wizard']
print('Campos del Wizard:')
for fname, f in sorted(Wizard._fields.items()):
    print('  %-30s %s' % (fname, f.type))

for meth_name in ['_get_checks_on_hand', 'print_report', '_get_report_data']:
    if hasattr(Wizard, meth_name):
        print('\n--- Fuente del método %s ---' % meth_name)
        try:
            fn = getattr(Wizard, meth_name)
            src = inspect.getsource(fn)
            print(src)
        except Exception as e:
            print('  <No se pudo obtener fuente: %s>' % e)

sub('3. Simulación de ejecución del Wizard al 06/11/2026 con Diario CHEQT')
cheqt = env['account.journal'].with_company(company).search([('code', '=', 'CHEQT')], limit=1)
if not cheqt:
    cheqt = env['account.journal'].with_company(company).search([('name', 'ilike', 'Cheques de Terceros')], limit=1)

target_date = fields.Date.from_string('2026-11-06')
print('Diario seleccionado: [%s] %s (ID=%s)' % (cheqt.code if cheqt else 'N/A', cheqt.name if cheqt else 'N/A', cheqt.id if cheqt else 'N/A'))
print('Fecha corte: %s' % target_date)

try:
    checks_cheqt = Wizard._get_checks_on_hand(cheqt.id if cheqt else False, target_date)
    print('\nTotal cheques devueltos por el Wizard para CHEQT: %d | Total $: %.2f' % (
        len(checks_cheqt), sum(checks_cheqt.mapped('amount'))
    ))
    
    # Ver si están los 3 cheques
    found_in_report = checks_cheqt.filtered(lambda c: c.name in target_numbers)
    print('¿Aparecen los 3 cheques rechazados en el resultado?: %d encontrados' % len(found_in_report))
    for fc in found_in_report:
        print('  -> ID=%s Núm=%s Imp=$ %.2f DiarioActual=[%s] %s' % (
            fc.id, fc.name, fc.amount,
            fc.current_journal_id.code if fc.current_journal_id else 'None',
            fc.current_journal_id.name if fc.current_journal_id else 'None'
        ))
except Exception as e:
    print('Error ejecutando _get_checks_on_hand:')
    traceback.print_exc()
