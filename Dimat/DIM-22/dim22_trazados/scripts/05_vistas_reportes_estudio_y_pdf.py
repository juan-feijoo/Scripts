# -*- coding: utf-8 -*-
# 05 - Vistas Studio/custom, reportes QWeb PDF existentes y verificación de Website/eCommerce (solo lectura)

h('05 - VISTAS CUSTOM/STUDIO, REPORTES QWEB Y WEBSITE')

TARGET_MODELS = [
    'product.template', 'product.product', 'res.partner',
    'sale.order', 'sale.order.line',
    'purchase.order', 'purchase.order.line',
    'stock.picking', 'stock.move',
    'account.move', 'account.move.line',
]

# Mapa view_id -> xml_id (module.name)
imd_recs = env['ir.model.data'].search([('model', '=', 'ir.ui.view')])
view_xmlids = {r.res_id: '%s.%s' % (r.module, r.name) for r in imd_recs}
installed_core_mods = set(env['ir.module.module'].search([
    ('state', '=', 'installed'),
    ('author', 'ilike', 'Odoo S.A.'),
]).mapped('name'))

sub('Vistas heredadas/custom/Studio en modelos objetivo (ir.ui.view)')
views = env['ir.ui.view'].with_context(active_test=False).search([
    '|', ('model', 'in', TARGET_MODELS), ('type', '=', 'qweb'),
], order='model, priority, id')

for v in views:
    xmlid = view_xmlids.get(v.id, '')
    mod = xmlid.split('.')[0] if '.' in xmlid else ''
    is_studio = 'studio' in (v.name or '').lower() or 'studio' in xmlid.lower()
    is_custom = (not mod) or (mod not in installed_core_mods)
    if v.type == 'qweb':
        # Para qweb filtramos las relevantes a ventas/compras/remitos/facturas o custom/studio
        qblob = ('%s %s' % (v.name or '', xmlid)).lower()
        qrelevant = any(k in qblob for k in ('saleorder', 'purchaseorder', 'deliveryslip', 'invoice', 'l10n_ar', 'picking', 'studio'))
        if not (qrelevant and (is_studio or is_custom)):
            continue
    elif not (is_studio or is_custom):
        continue

    print('  id=%-5s | act=%-5s | type=%-5s | model=%-20s | prio=%-3s | xmlid=%-40s | inherit=%s | name=%r' % (
        v.id, v.active, v.type, v.model or '-', v.priority, xmlid or '<sin xml_id>',
        v.inherit_id.name if v.inherit_id else '-', v.name,
    ))
    if v.arch_db:
        print('    ARCH:\n' + '\n'.join('    ' + ln for ln in v.arch_db.splitlines()[:80]))

sub('Reportes QWeb registrados (ir.actions.report) para Venta, Compra, Remito y Factura')
reports = env['ir.actions.report'].search([
    ('model', 'in', ['sale.order', 'purchase.order', 'stock.picking', 'account.move']),
], order='model, id')
rep_imd = {r.res_id: '%s.%s' % (r.module, r.name) for r in env['ir.model.data'].search([('model', '=', 'ir.actions.report')])}
for r in reports:
    print('  id=%-4s | model=%-15s | type=%-10s | xmlid=%-42s | report_name=%-40s | name=%r' % (
        r.id, r.model, r.report_type, rep_imd.get(r.id, '<sin xml_id>'), r.report_name, r.name,
    ))

sub('Estado de Website / eCommerce respecto a productos "/"')
pub_field = (
    'website_published' if has_field('product.template', 'website_published')
    else ('is_published' if has_field('product.template', 'is_published') else None)
)
if 'website' in env and pub_field:
    PT = env['product.template'].with_context(active_test=False)
    traced = PT.search([('name', '=like', TRACED_PREFIX + '%')])
    pub_traced = traced.filtered(lambda p: p[pub_field])
    print('website_sale instalado. Productos "/" totales: %s | publicados en web (%s): %s' % (
        len(traced), pub_field, len(pub_traced),
    ))
    for p in pub_traced[:30]:
        print('  [WEB PUB] id=%s | name=%r | website_id=%s' % (
            p.id, p.name, fmt(p, 'website_id') if has_field('product.template', 'website_id') else '-',
        ))
else:
    print('website_sale no está instalado (o product.template sin website_published/is_published).')
