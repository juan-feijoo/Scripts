# -*- coding: utf-8 -*-
# 01 - Entorno, módulos instalados/custom, automatizaciones, acciones de servidor y overrides (solo lectura)
import odoo

h('01 - ENTORNO, MÓDULOS, AUTOMATIZACIONES Y OVERRIDES')

print('Base de datos : %s' % env.cr.dbname)
print('Versión Odoo  : %s' % odoo.release.version)

sub('Compañías (res.company)')
for c in env['res.company'].with_context(active_test=False).search([]):
    print('  id=%s | active=%s | name=%r | vat=%r | country=%s | currency=%s | parent=%s' % (
        c.id, c.active, c.name, c.vat, c.country_id.code if c.country_id else False,
        c.currency_id.name if c.currency_id else False, c.parent_id.name if c.parent_id else False,
    ))

sub('Estado de módulos clave estándar/localización')
key_mods = [
    'sale', 'sale_management', 'purchase', 'stock', 'sale_stock', 'purchase_stock',
    'account', 'account_accountant', 'l10n_ar', 'l10n_ar_afipws_fe', 'l10n_ar_edi',
    'web_studio', 'documents', 'website_sale', 'portal', 'product_expiry',
    'quality_control', 'mrp', 'base_automation', 'stock_barcode',
]
mods_map = {m.name: m for m in env['ir.module.module'].search([('name', 'in', key_mods)])}
for mname in key_mods:
    m = mods_map.get(mname)
    print('  %-25s %s' % (mname, '%s (ver=%s)' % (m.state, m.installed_version) if m else '<no encontrado>'))

sub('Módulos instalados NO Odoo S.A. (custom / terceros / OCA)')
custom_mods = env['ir.module.module'].search([
    ('state', '=', 'installed'),
    ('author', 'not ilike', 'Odoo S.A.'),
], order='name')
print('Total módulos no Odoo S.A. instalados: %s' % len(custom_mods))
for m in custom_mods:
    print('  %-40s | ver=%-14s | author=%r | %s' % (
        m.name, m.installed_version or '', m.author or '', m.shortdesc or '',
    ))

TARGET_MODELS = {
    'product.template', 'product.product', 'res.partner',
    'sale.order', 'sale.order.line',
    'purchase.order', 'purchase.order.line',
    'stock.picking', 'stock.move', 'stock.move.line',
    'account.move', 'account.move.line',
}
KEYWORDS = ('traz', 'hab', 'sedro', 'renpre', 'precur', 'studio', 'warn', 'block', 'barra', 'cert', 'anmat')

if 'base.automation' in env:
    sub('Automatizaciones (base.automation) - todas (activas e inactivas)')
    autos = env['base.automation'].with_context(active_test=False).search([], order='model_id, id')
    print('Total base.automation: %s' % len(autos))
    for a in autos:
        mname = a.model_id.model if a.model_id else ''
        relevant = (mname in TARGET_MODELS) or any(k in (a.name or '').lower() for k in KEYWORDS)
        print('  id=%s | active=%s | model=%s | trigger=%s | name=%r%s' % (
            a.id, a.active, mname, a.trigger, a.name, ' [RELEVANTE]' if relevant else '',
        ))
        if relevant:
            dump(a, names=[
                'filter_domain', 'filter_pre_domain', 'on_change_field_ids',
                'trigger_field_ids', 'action_server_ids',
            ])
            if has_field('base.automation', 'action_server_ids'):
                for srv in a.action_server_ids:
                    print('    -> Server Action id=%s state=%s name=%r' % (srv.id, srv.state, srv.name))
                    if srv.state == 'code' and srv.code:
                        print('       CODE:\n' + '\n'.join('       ' + ln for ln in srv.code.splitlines()))
else:
    sub('Automatizaciones (base.automation)')
    print('  Modelo base.automation no instalado.')

sub('Acciones de servidor Python (ir.actions.server state=code) en modelos relevantes o por keyword')
srv_actions = env['ir.actions.server'].with_context(active_test=False).search([('state', '=', 'code')], order='model_id, id')
print('Total ir.actions.server state=code: %s' % len(srv_actions))
for srv in srv_actions:
    mname = srv.model_id.model if srv.model_id else ''
    blob = ('%s %s %s' % (mname, srv.name or '', srv.code or '')).lower()
    if mname in TARGET_MODELS or any(k in blob for k in KEYWORDS):
        print('  id=%s | model=%s | name=%r | usage=%s' % (
            srv.id, mname, srv.name, fmt(srv, 'usage') if has_field('ir.actions.server', 'usage') else '-',
        ))
        if srv.code:
            print('    CODE:\n' + '\n'.join('    ' + ln for ln in srv.code.splitlines()))

sub('Crons (ir.cron) en modelos relevantes o por keyword')
crons = env['ir.cron'].with_context(active_test=False).search([], order='id')
for cr in crons:
    mname = cr.model_id.model if cr.model_id else ''
    blob = ('%s %s %s' % (mname, cr.name or '', cr.code or '')).lower()
    if mname in TARGET_MODELS or any(k in blob for k in KEYWORDS):
        print('  id=%s | active=%s | model=%s | name=%r' % (cr.id, cr.active, mname, cr.name))

sub('Overrides de código en /src/user/ (MRO)')
method_sources('sale.order', ['action_confirm', '_action_confirm', '_prepare_confirmation_values'], only_custom=True)
method_sources('sale.order.line', ['_onchange_product_id_warning', '_compute_name'], only_custom=True)
method_sources('purchase.order', ['button_confirm'], only_custom=True)
method_sources('purchase.order.line', ['_onchange_product_id_warning'], only_custom=True)
method_sources('stock.picking', ['button_validate'], only_custom=True)
method_sources('account.move', ['action_post', '_post'], only_custom=True)
method_sources('product.template', ['create', 'write'], only_custom=True)
method_sources('res.partner', ['create', 'write'], only_custom=True)
