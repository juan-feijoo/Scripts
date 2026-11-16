# -*- coding: utf-8 -*-
# 01 - Entorno, módulos instalados, parámetros y código fuente real del circuito de padrón/retenciones
import os

h('01 - ENTORNO, MÓDULOS Y CÓDIGO INSTALADO')

# 1. Compañías
sub('Compañías en la base')
companies = env['res.company'].with_context(active_test=False).search([])
for c in companies:
    print('  [%s] %s | active=%s | CUIT=%s | country=%s | chart=%s' % (
        c.id, c.name, c.active, c.vat, c.country_id.code if c.country_id else False,
        getattr(c, 'chart_template', False),
    ))
    extra = []
    for fname in ('use_payment_pro', 'l10n_ar_arba_wh_mode', 'l10n_ar_afip_ws_environment',
                  'l10n_ar_tax_base_account_id', 'l10n_ar_company_requires_vat', 'reconcile_on_company_currency'):
        if has_field('res.company', fname):
            extra.append('%s=%s' % (fname, fmt(c, fname)))
    if has_field('res.company', 'arba_cit'):
        cit = getattr(c, 'arba_cit', False)
        extra.append('arba_cit=%s' % ('SET (len=%d)' % len(cit) if cit else 'EMPTY'))
    if extra:
        print('      ' + ' | '.join(extra))

company = get_company()
print('\n[*] Compañía seleccionada: [%s] %s' % (company.id, company.name))

# 2. Parámetros del sistema relevantes
sub('ir.config_parameter (arba / padron / l10n_ar / withholding)')
params = env['ir.config_parameter'].sudo().search([
    '|', '|', '|',
    ('key', 'ilike', 'arba'),
    ('key', 'ilike', 'padron'),
    ('key', 'ilike', 'l10n_ar'),
    ('key', 'ilike', 'withholding'),
], order='key')
for p in params:
    val = p.value or ''
    if any(k in p.key.lower() for k in ('pass', 'secret', 'token', 'cit', 'key')):
        val = '<oculto len=%d>' % len(val)
    print('  %-55s = %s' % (p.key, val[:150]))

# 3. Módulos instalados de localización, pagos y terceros/custom
sub('Módulos instalados (no Odoo S.A. o l10n_ar / payment / tax)')
mods = env['ir.module.module'].search([
    ('state', '=', 'installed'),
    '|', '|', '|',
    ('author', 'not ilike', 'Odoo S.A.'),
    ('name', 'ilike', 'l10n_ar'),
    ('name', 'ilike', 'payment_pro'),
    ('name', 'ilike', 'tax_settlement'),
], order='name')
for m in mods:
    print('  %-38s | %-15s | %s' % (m.name, m.latest_version or m.installed_version or '', m.author or ''))

# 4. Crons, automatizaciones y acciones de servidor relacionadas
sub('ir.cron relacionados (activos e inactivos)')
crons = env['ir.cron'].with_context(active_test=False).search([
    '|', '|',
    ('name', 'ilike', 'padron'),
    ('name', 'ilike', 'arba'),
    ('name', 'ilike', 'l10n_ar'),
], order='name')
for cr in crons:
    print('  [%s] %s | active=%s | interval=%s %s | nextcall=%s | model=%s' % (
        cr.id, cr.name, cr.active, cr.interval_number, cr.interval_type,
        cr.nextcall, cr.model_id.model if cr.model_id else False,
    ))

sub('base.automation y ir.actions.server (code) relacionados')
if 'base.automation' in env:
    autos = env['base.automation'].with_context(active_test=False).search([])
    for a in autos:
        print('  AUTO [%s] %s | active=%s | model=%s | trigger=%s' % (
            a.id, a.name, a.active, a.model_id.model if a.model_id else False, a.trigger,
        ))
srv_actions = env['ir.actions.server'].search([
    ('state', '=', 'code'),
    '|', '|',
    ('model_id.model', 'in', ['res.partner', 'account.payment', 'account.move', 'res.company.jurisdiction.padron', 'l10n_ar.partner.tax']),
    ('name', 'ilike', 'padron'),
    ('name', 'ilike', 'arba'),
])
for sa in srv_actions:
    if any(k in (sa.code or '').lower() for k in ('padron', 'arba', 'l10n_ar', 'partner.tax', 'withholding', 'aliquot')):
        print('  ACTION [%s] %s | model=%s' % (sa.id, sa.name, sa.model_id.model))
        print('    ' + (sa.code or '').replace('\n', '\n    '))

# 5. Código fuente real en ejecución (MRO completo)
h('CÓDIGO FUENTE EN EJECUCIÓN (MRO)')
safe(method_sources, 'res.company.jurisdiction.padron', [
    'check_state_id', 'descompress_file', 'find_file', 'find_aliquot', '_get_aliquot', '_get_parp_tmp_dir',
], only_custom=False)
safe(method_sources, 'account.fiscal.position', [
    '_l10n_ar_add_taxes', '_get_fpos_ranking_functions', '_get_fiscal_position',
], only_custom=False)
safe(method_sources, 'account.fiscal.position.l10n_ar_tax', [
    '_get_missing_taxes', '_get_tax_from_ws', '_ensure_tax', '_get_arba_data', '_get_padron_data', '_search_padron_file',
], only_custom=False)
safe(method_sources, 'account.payment', [
    '_compute_fiscal_position_id', '_compute_l10n_ar_withholding_line_ids', 'action_confirm', 'action_post',
], only_custom=False)
safe(method_sources, 'account.move', [
    '_compute_fiscal_position_id', '_l10n_ar_recompute_fiscal_position_taxes',
], only_custom=False)
safe(method_sources, 'account.move.line', [
    '_get_computed_taxes',
], only_custom=False)
safe(method_sources, 'sale.order.line', [
    '_compute_tax_id',
], only_custom=False)
safe(method_sources, 'l10n_ar.partner.tax', [
    '_check_tax_group_overlap',
], only_custom=False)
