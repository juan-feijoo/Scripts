# -*- coding: utf-8 -*-
# 01 - Entorno, compañías, usuarios Atlas, notification_type y estado de correo/notificaciones (solo lectura)
import odoo

h('01 - ENTORNO, USUARIOS Y CONFIGURACIÓN DE NOTIFICACIONES')
print('DB:      %s' % env.cr.dbname)
print('Odoo:    %s' % odoo.release.version)

sub('Parámetros de sistema clave (neutralización / correo / base)')
ICP = env['ir.config_parameter'].sudo()
for key in [
    'database.is_neutralized',
    'web.base.url',
    'mail.catchall.domain',
    'mail.default.from',
    'mail.bounce.alias',
]:
    print('  %-35s %r' % (key, ICP.get_param(key)))

sub('Servidores de correo saliente (ir.mail_server)')
for srv in env['ir.mail_server'].with_context(active_test=False).search([]):
    dump(srv, names=['name', 'active', 'smtp_host', 'smtp_port', 'smtp_encryption', 'smtp_user', 'sequence'])

sub('Compañías registradas')
for c in env['res.company'].search([]):
    print(
        '  id=%-3s | %-35s | moneda=%-5s | vat=%-18s | po_double_val=%s (%s)'
        % (
            c.id,
            c.name,
            c.currency_id.name if c.currency_id else '-',
            c.vat if has_field('res.company', 'vat') else '-',
            c.po_double_validation if has_field('res.company', 'po_double_validation') else '-',
            c.po_double_validation_amount if has_field('res.company', 'po_double_validation_amount') else '-',
        )
    )

sub('Usuarios del proyecto Atlas (detalle completo incluyendo notification_type)')
for login in TARGET_LOGINS:
    u = find_user(login)
    if not u:
        print('  [FALTA] %s (no existe en la BD)' % login)
        continue
    print('\n  >> %s (id=%s | partner_id=%s | activo=%s)' % (u.login, u.id, u.partner_id.id, u.active))
    dump(
        u,
        names=[
            'name',
            'login',
            'email',
            'active',
            'share',
            'state',
            'notification_type',
            'odoobot_state',
            'company_id',
            'company_ids',
            'lang',
            'tz',
        ],
    )
    atlas_groups = [
        '%s (%s)' % (g.name, g.get_external_id().get(g.id, '-'))
        for g in u.groups_id
        if 'atlas' in (g.category_id.name or '').lower() or 'atlas' in (g.name or '').lower() or 'rol:' in (g.name or '').lower()
    ]
    key_app_xmlids = [
        'sales_team.group_sale_salesman',
        'sales_team.group_sale_salesman_all_leads',
        'sales_team.group_sale_manager',
        'purchase.group_purchase_user',
        'purchase.group_purchase_manager',
        'account.group_account_invoice',
        'account.group_account_user',
        'account.group_account_manager',
        'base.group_erp_manager',
        'base.group_system',
    ]
    has_apps = [x for x in key_app_xmlids if env.ref(x, raise_if_not_found=False) and u.has_group(x)]
    print('  %-45s %s' % ('grupos_atlas', atlas_groups or '[]'))
    print('  %-45s %s' % ('grupos_app_clave', has_apps))

sub('Otros usuarios internos (share=False)')
other_users = env['res.users'].with_context(active_test=False).search([
    ('share', '=', False),
    ('login', 'not in', TARGET_LOGINS),
])
for u in other_users:
    nt = u.notification_type if has_field('res.users', 'notification_type') else '?'
    print('  id=%-4s activo=%-5s notif=%-6s login=%-38s nombre=%s' % (u.id, u.active, nt, u.login, u.name))

sub('Grupos de categoría Atlas y membresías')
groups = env['res.groups'].search([
    '|',
    ('category_id.name', 'ilike', 'atlas'),
    ('name', 'ilike', 'atlas'),
])
if not groups:
    print('  (Sin grupos Atlas encontrados)')
for g in groups:
    xmlid = g.get_external_id().get(g.id, '-')
    print(
        '  id=%-4s | %-42s | xmlid=%-50s | implica=%s | usuarios=%s'
        % (
            g.id,
            g.name,
            xmlid,
            g.implied_ids.mapped('name'),
            g.users.mapped('login'),
        )
    )

sub('Últimas 15 mail.notification para Hernán F., Euge y Hernán Pacetti')
check_users = [find_user(l) for l in (NOTIF_VENTA_LOGINS + ['hernanpacetti@atlasgroup.com.ar'])]
check_partners = [u.partner_id.id for u in check_users if u and u.partner_id]
if check_partners and 'mail.notification' in env:
    notifs = env['mail.notification'].search(
        [('res_partner_id', 'in', check_partners)],
        order='id desc',
        limit=15,
    )
    if not notifs:
        print('  (Sin registros en mail.notification para estos usuarios)')
    for nf in notifs:
        msg = nf.mail_message_id
        print(
            '  nf=%-6s | para=%-20s | tipo=%-6s | estado=%-10s | read=%-5s | model=%-15s res_id=%-5s | msg=%s'
            % (
                nf.id,
                nf.res_partner_id.name[:20],
                nf.notification_type if has_field('mail.notification', 'notification_type') else '?',
                nf.notification_status if has_field('mail.notification', 'notification_status') else '?',
                nf.is_read if has_field('mail.notification', 'is_read') else '?',
                msg.model or '-',
                msg.res_id or 0,
                strip_html(msg.body)[:90],
            )
        )

sub('Actividades pendientes (mail.activity) para usuarios Atlas')
atlas_uids = [u.id for u in [find_user(l) for l in TARGET_LOGINS] if u]
if atlas_uids and 'mail.activity' in env:
    acts = env['mail.activity'].search([('user_id', 'in', atlas_uids)], order='id desc', limit=30)
    if not acts:
        print('  (Sin actividades pendientes para usuarios Atlas)')
    for a in acts:
        print(
            '  act=%-5s | user=%-32s | tipo=%-22s | model=%-15s res_id=%-5s | deadline=%s | summary=%s'
            % (
                a.id,
                a.user_id.login,
                a.activity_type_id.name,
                a.res_model,
                a.res_id,
                a.date_deadline,
                (a.summary or '')[:60],
            )
        )
