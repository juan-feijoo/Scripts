# -*- coding: utf-8 -*-
# 04 - Auditoría final de estado persistido en BD (100% solo lectura)
import odoo

h('04 - AUDITORÍA FINAL DEL ESTADO EN BASE DE DATOS (SOLO LECTURA)')
print('DB:   %s | Odoo %s' % (env.cr.dbname, odoo.release.version))
print('MODO: %s' % ('POST-DRY-RUN (BD sin cambios)' if DRY_RUN else 'POST-APPLY (estado guardado)'))

sub('1. Usuarios Atlas y notification_type')
for login in USERS_CONFIG:
    u = find_user(login)
    if not u:
        print('  [NO EXISTE] %s' % login)
        continue
    roles = [g.name for g in u.groups_id if 'Rol:' in g.name or 'Atlas:' in g.name]
    print('  %-35s | id=%-4s | notif=%-6s | cias=%-38s | roles=%s' % (
        u.login, u.id, u.notification_type, u.company_ids.mapped('name'), roles
    ))

sub('2. Contacto del circuito de Compras')
p_terc = env['res.partner'].with_context(active_test=False).search([('name', '=', CONTACTO_CIRCUITO_COMPRA)], limit=1)
if p_terc:
    dump(p_terc, names=['id', 'name', 'active', 'is_company', 'company_id', 'supplier_rank', 'vat', 'street', 'city', 'country_id'])
else:
    print('  (Contacto %r aún no persistido en BD)' % CONTACTO_CIRCUITO_COMPRA)

sub('3. Reglas studio.approval.rule [ATLAS]')
rules = env['studio.approval.rule'].with_context(active_test=False).search([('name', '=like', '[ATLAS]%')], order='id')
if not rules:
    print('  (Sin reglas [ATLAS] persistidas en BD)')
for r in rules:
    print('\n  REGLA id=%s | active=%s | %s' % (r.id, r.active, r.name))
    dump(r, names=['model_name', 'method', 'domain', 'approval_group_id', 'approver_ids', 'users_to_notify', 'message'], full=['domain', 'message'])

sub('4. Automatización base.automation [ATLAS]')
autos = env['base.automation'].with_context(active_test=False).search([('name', '=like', '[ATLAS]%')])
if not autos:
    print('  (Sin automatizaciones [ATLAS] persistidas en BD)')
for a in autos:
    print('  AUTO id=%s | active=%s | model=%s | trigger=%s | name=%s | actions=%s' % (
        a.id, a.active, a.model_id.model, a.trigger, a.name, a.action_server_ids.mapped('name')
    ))

sub('5. Casos UI DEMO-ATLAS-* y sus notificaciones en Bandeja 💬 + Actividades 🕒')
demo_sos = env['sale.order'].sudo().search([('client_order_ref', '=like', 'DEMO-ATLAS-%')], order='id desc')
demo_pos = env['purchase.order'].sudo().search([('partner_ref', '=like', 'DEMO-ATLAS-%')], order='id desc')
print('  OV DEMO-ATLAS-*: %s | OC DEMO-ATLAS-*: %s' % (demo_sos.mapped('name'), demo_pos.mapped('name')))

for rec in list(demo_sos) + list(demo_pos):
    print('\n  >>> %s %s (id=%s, state=%s, partner=%s)' % (
        rec._name, rec.name, rec.id, rec.state, rec.partner_id.name
    ))
    acts = env['mail.activity'].sudo().search([('res_model', '=', rec._name), ('res_id', '=', rec.id)])
    print('    Actividades 🕒 (%s): %s' % (len(acts), [(a.activity_type_id.name, a.user_id.login) for a in acts]))
    notifs = env['mail.notification'].sudo().search([
        ('mail_message_id.model', '=', rec._name),
        ('mail_message_id.res_id', '=', rec.id),
    ], order='id')
    print('    Notificaciones (%s): %s' % (
        len(notifs),
        [(n.res_partner_id.name, n.notification_type, n.notification_status, 'read=%s' % n.is_read) for n in notifs]
    ))
