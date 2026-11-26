# -*- coding: utf-8 -*-
# 04 - Estado actual de documentos demo, contactos existentes y chatter/notificaciones previas (solo lectura)

h('04 - DOCUMENTOS DEMO, CONTACTOS Y EVIDENCIA PREVIA EN CHATTER')

sub('Resumen de sale.order y purchase.order por compañía y estado')
for model_name in ('sale.order', 'purchase.order'):
    if model_name not in env:
        continue
    print('\n  %s (total=%s):' % (model_name, env[model_name].search_count([])))
    groups = safe(env[model_name].read_group, [], ['company_id', 'state'], ['company_id', 'state'], lazy=False) or []
    for g in groups:
        print('    comp=%-35s | state=%-12s | count=%s' % (g.get('company_id'), g.get('state'), g.get('__count')))

sub('Registros DEMO / TEST previos de Atlas (para saber qué limpiar luego)')
demo_sos = env['sale.order'].search([
    '|', '|',
    ('client_order_ref', 'ilike', 'DEMO'),
    ('client_order_ref', 'ilike', 'TEST'),
    ('partner_id.name', 'ilike', 'ATLAS'),
], order='id desc', limit=20)
print('  sale.order demo/test (%s):' % len(demo_sos))
for so in demo_sos:
    print('    id=%-5s name=%-12s state=%-8s ref=%-18s user=%-25s partner=%-35s total=%s' % (
        so.id, so.name, so.state, so.client_order_ref or '-', so.user_id.login or '-', so.partner_id.name[:35], so.amount_total
    ))

demo_pos = env['purchase.order'].search([
    '|', '|',
    ('partner_ref', 'ilike', 'DEMO'),
    ('partner_ref', 'ilike', 'TEST'),
    ('partner_id.name', 'ilike', 'ATLAS'),
], order='id desc', limit=20)
print('\n  purchase.order demo/test (%s):' % len(demo_pos))
for po in demo_pos:
    print('    id=%-5s name=%-12s state=%-10s ref=%-18s user=%-25s partner=%-35s total=%s' % (
        po.id, po.name, po.state, po.partner_ref or '-', po.user_id.login or '-', po.partner_id.name[:35], po.amount_total
    ))

sub('Chatter + actividades + mail.notification de las últimas 3 OV (demo o recientes)')
inspect_sos = demo_sos[:3] if demo_sos else env['sale.order'].search([], order='id desc', limit=3)
for so in inspect_sos:
    print('\n  >>> OV %s (id=%s, state=%s, company=%s, user=%s)' % (
        so.name, so.id, so.state, so.company_id.name, so.user_id.login
    ))
    chatter(so)
    acts = env['mail.activity'].search([('res_model', '=', 'sale.order'), ('res_id', '=', so.id)])
    print('  Actividades en %s: %s' % (so.name, [(a.id, a.activity_type_id.name, a.user_id.login, a.summary) for a in acts]))

sub('Chatter + actividades + mail.notification de las últimas 3 OC (demo o recientes)')
inspect_pos = demo_pos[:3] if demo_pos else env['purchase.order'].search([], order='id desc', limit=3)
for po in inspect_pos:
    print('\n  >>> OC %s (id=%s, state=%s, company=%s, user=%s, partner=%s)' % (
        po.name, po.id, po.state, po.company_id.name, po.user_id.login, po.partner_id.name
    ))
    chatter(po)
    acts = env['mail.activity'].search([('res_model', '=', 'purchase.order'), ('res_id', '=', po.id)])
    print('  Actividades en %s: %s' % (po.name, [(a.id, a.activity_type_id.name, a.user_id.login, a.summary) for a in acts]))

sub('Contactos relacionados con Atlas / Terceros / Proveedores recientes')
Partner = env['res.partner'].with_context(active_test=False)
p_match = Partner.search([
    '|', '|', '|',
    ('name', 'ilike', 'atlas'),
    ('name', 'ilike', 'tercero'),
    ('name', 'ilike', 'gasto'),
    ('name', '=', CONTACTO_CIRCUITO_COMPRA),
], limit=30)
print('  Coincidencias por nombre (%s):' % len(p_match))
for p in p_match:
    print('    id=%-6s active=%-5s comp=%-25s supp_rank=%s cust_rank=%s vat=%-15s name=%s' % (
        p.id, p.active, p.company_id.name or '(todas)', p.supplier_rank, p.customer_rank, p.vat or '-', p.name
    ))

print('\n  Últimos 10 proveedores usados en purchase.order:')
recent_pos = env['purchase.order'].search([], order='id desc', limit=20)
seen_p = set()
for po in recent_pos:
    p = po.partner_id
    if p and p.id not in seen_p:
        seen_p.add(p.id)
        print('    id=%-6s comp=%-25s vat=%-15s name=%s' % (p.id, p.company_id.name or '(todas)', p.vat or '-', p.name))
        if len(seen_p) >= 10:
            break
