# -*- coding: utf-8 -*-
# 02 - Reportes, menús, acciones de ventana y vistas de cheques
company = get_company()
h('02 - REPORTES, MENÚS Y ACCIONES DE CHEQUES (%s)' % company.name)

sub('Menús relacionados a cheques')
menus = env['ir.ui.menu'].search([
    '|', '|',
    ('name', 'ilike', 'cheque'),
    ('name', 'ilike', 'check'),
    ('complete_name', 'ilike', 'cheque')
])
for m in menus:
    print('  ID=%-6s Menú: %-45s Acción: %s' % (m.id, m.complete_name, m.action.display_name if m.action else 'Sin acción'))

sub('Acciones de ventana (ir.actions.act_window) sobre cheques')
actions = env['ir.actions.act_window'].search([
    '|', '|', '|',
    ('name', 'ilike', 'cheque'),
    ('name', 'ilike', 'check'),
    ('res_model', '=', 'account.check'),
    ('domain', 'ilike', 'check')
])
for a in actions:
    print('\n  Acción ID=%s: %s (Modelo: %s)' % (a.id, a.name, a.res_model))
    print('    Dominio: %s' % a.domain)
    print('    Contexto: %s' % a.context)
    print('    Modos de vista: %s' % a.view_mode)

if 'account.report' in env:
    sub('Reportes contables dinámicos (account.report)')
    acc_reports = env['account.report'].search([
        '|', '|',
        ('name', 'ilike', 'cheque'),
        ('name', 'ilike', 'check'),
        ('name', 'ilike', 'tercero')
    ])
    for rep in acc_reports:
        print('\n  Reporte ID=%s: %s (Código: %s)' % (rep.id, rep.name, getattr(rep, 'code', '')))
        if has_field('account.report', 'custom_handler_model_id') and rep.custom_handler_model_id:
            print('    Custom handler model: %s' % rep.custom_handler_model_id.model)
        if has_field('account.report', 'filter_unreconciled'):
            print('    Filtro no conciliados: %s' % rep.filter_unreconciled)
        
        lines = env['account.report.line'].search([('report_id', '=', rep.id)])
        print('    Líneas del reporte (%d):' % len(lines))
        for line in lines:
            print('      - Línea ID=%s: %-35s (code=%s)' % (line.id, line.name, line.code or ''))
            exprs = env['account.report.expression'].search([('report_line_id', '=', line.id)])
            for exp in exprs:
                print('          Expr: %-15s engine=%-12s formula=%s' % (exp.label, exp.engine, exp.formula))

sub('Reportes impresos / QWeb (ir.actions.report)')
qweb_reports = env['ir.actions.report'].search([
    '|', '|',
    ('name', 'ilike', 'cheque'),
    ('name', 'ilike', 'check'),
    ('model', 'in', ['account.check', 'account.payment'])
])
for r in qweb_reports:
    print('  ID=%-6s Nombre: %-35s Modelo: %-20s Tipo: %s (report_name: %s)' % (
        r.id, r.name, r.model, r.report_type, r.report_name
    ))
