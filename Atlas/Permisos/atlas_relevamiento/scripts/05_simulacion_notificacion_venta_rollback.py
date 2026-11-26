# -*- coding: utf-8 -*-
# 05 - Simulación 100% segura (savepoint + rollback) de notificaciones de aprobación en Ventas
# Comprueba qué genera Studio HOY vs con notification_type='inbox' + Hernán F. y Euge.

h('05 - SIMULACIÓN DE NOTIFICACIONES EN VENTAS (100% ROLLBACK)')


class _Undo(Exception):
    pass


def _inspect_so_events(so, before_msg_id, before_act_id, before_notif_id):
    acts = env['mail.activity'].search([
        ('res_model', '=', 'sale.order'),
        ('res_id', '=', so.id),
        ('id', '>', before_act_id),
    ])
    msgs = env['mail.message'].search([
        ('model', '=', 'sale.order'),
        ('res_id', '=', so.id),
        ('id', '>', before_msg_id),
    ], order='id')
    notifs = env['mail.notification'].search([
        ('mail_message_id', 'in', msgs.ids),
        ('id', '>', before_notif_id),
    ], order='id')
    reqs = (
        env['studio.approval.request'].search([('res_id', '=', so.id)])
        if 'studio.approval.request' in env
        else env['res.users']
    )
    entries = (
        env['studio.approval.entry'].search([('model', '=', 'sale.order'), ('res_id', '=', so.id)])
        if 'studio.approval.entry' in env
        else env['res.users']
    )

    print('  studio.approval.request (%s):' % len(reqs))
    for q in reqs:
        act = q.mail_activity_id if has_field('studio.approval.request', 'mail_activity_id') else None
        print('    req=%s rule=%s act=%s user=%s' % (q.id, q.rule_id.name, act.id if act else 0, act.user_id.login if act else '-'))

    print('  studio.approval.entry (%s):' % len(entries))
    for e in entries:
        print('    entry=%s rule=%s user=%s approved=%s' % (e.id, e.rule_id.name, e.user_id.login, e.approved))

    print('  mail.activity nuevas (%s):' % len(acts))
    for a in acts:
        print('    act=%s tipo=%s para=%s summary=%s' % (a.id, a.activity_type_id.name, a.user_id.login, a.summary))

    print('  mail.message nuevos (%s):' % len(msgs))
    for m in msgs:
        print('    msg=%s tipo=%s subtype=%s autor=%s partner_ids=%s | body=%s' % (
            m.id, m.message_type, m.subtype_id.name, m.author_id.name,
            m.partner_ids.mapped('name'), strip_html(m.body)[:180]
        ))

    print('  mail.notification nuevas (%s):' % len(notifs))
    for nf in notifs:
        print('    nf=%s para=%s tipo=%s estado=%s is_read=%s msg_id=%s' % (
            nf.id,
            nf.res_partner_id.name,
            nf.notification_type if has_field('mail.notification', 'notification_type') else '?',
            nf.notification_status if has_field('mail.notification', 'notification_status') else '?',
            nf.is_read if has_field('mail.notification', 'is_read') else '?',
            nf.mail_message_id.id,
        ))


try:
    company_bg = get_company(COMPANY_NAME)
    u_op = find_user('mandatario@atlasgroup.com.ar')
    u_pac = find_user('hernanpacetti@atlasgroup.com.ar')
    u_adm = find_user('administracion@atlasgroup.com.ar')
    u_euge = find_user('eugeniazanotti@atlasgroup.com.ar')
    u_hf = find_user('hernanfernandez@atlasgroup.com.ar')

    Rule = env['studio.approval.rule']
    rule_so = Rule.search([
        ('model_id.model', '=', 'sale.order'),
        ('method', '=', 'action_confirm'),
        ('active', '=', True),
    ], limit=1)

    print('Compañía BG: %s' % (company_bg.name if company_bg else 'NO ENCONTRADA'))
    print('Regla OV activa: %s (id=%s)' % (rule_so.name if rule_so else 'NO ENCONTRADA', rule_so.id if rule_so else 0))
    print('Usuarios encontrados: op=%s pac=%s adm=%s euge=%s hf=%s' % (
        bool(u_op), bool(u_pac), bool(u_adm), bool(u_euge), bool(u_hf)
    ))

    if not (company_bg and rule_so and u_op and u_euge and u_hf):
        print('!! Faltan datos mínimos (compañía, regla OV activa o usuarios) para correr la simulación.')
    else:
        partner = env['res.partner'].sudo().search([('company_id', 'in', (False, company_bg.id))], limit=1)
        product = env['product.product'].sudo().search([('sale_ok', '=', True)], limit=1) or env['product.product'].sudo().search([], limit=1)
        if not (partner and product):
            print('!! Falta al menos 1 partner y 1 producto en la base para simular la OV.')
        else:
            # ------------------------------------------------------------------
            # ESCENARIO A: Estado ACTUAL de la base (sin cambios)
            # ------------------------------------------------------------------
            sub('ESCENARIO A: Estado ACTUAL (operador solicita aprobación en OV)')
            try:
                with env.cr.savepoint():
                    so = env['sale.order'].sudo().create({
                        'partner_id': partner.id,
                        'user_id': u_op.id,
                        'company_id': company_bg.id,
                        'order_line': [(0, 0, {
                            'product_id': product.id,
                            'name': 'Simulación Escenario A',
                            'product_uom_qty': 1,
                            'price_unit': 100000.0,
                        })],
                    })
                    env.flush_all()
                    last_msg = (env['mail.message'].search([], order='id desc', limit=1).id or 0)
                    last_act = (env['mail.activity'].search([], order='id desc', limit=1).id or 0)
                    last_nf = (env['mail.notification'].search([], order='id desc', limit=1).id or 0)

                    print('  notification_type ACTUAL -> Hernán F.: %s | Euge: %s | Pacetti: %s' % (
                        u_hf.notification_type, u_euge.notification_type, u_pac.notification_type if u_pac else '-'
                    ))
                    print('  Regla ACTUAL -> approver_ids=%s | users_to_notify=%s' % (
                        rule_so.approver_ids.mapped('login'), rule_so.users_to_notify.mapped('login')
                    ))

                    res = safe(Rule.with_user(u_op).check_approval, 'sale.order', so.id, 'action_confirm', False)
                    env.flush_all()
                    print('  check_approval (como Operador) -> approved=%s' % (res.get('approved') if isinstance(res, dict) else res))
                    _inspect_so_events(so, last_msg, last_act, last_nf)
                    raise _Undo()
            except _Undo:
                pass
            env.invalidate_all()

            # ------------------------------------------------------------------
            # ESCENARIO B: Propuesta (inbox + approver_ids=[HF, Euge] + users_to_notify=[HF, Euge])
            # ------------------------------------------------------------------
            sub('ESCENARIO B: Simulación PROPUESTA (inbox + solo Hernán F. y Euge notificados)')
            try:
                with env.cr.savepoint():
                    notif_users = u_hf | u_euge
                    notif_users.sudo().write({'notification_type': 'inbox'})
                    rule_so.sudo().write({
                        'approver_ids': [(6, 0, notif_users.ids)],
                        'users_to_notify': [(6, 0, notif_users.ids)],
                    })
                    env.flush_all()
                    rule_so.invalidate_recordset()

                    print('  Verificación can_validate con nueva config:')
                    for label, usr in [
                        ('Operador', u_op),
                        ('Hernán Pacetti (por grupo)', u_pac),
                        ('Administrativo', u_adm),
                        ('Eugenia Zanotti', u_euge),
                        ('Hernán Fernández', u_hf),
                    ]:
                        if usr:
                            print('    %-28s -> can_validate=%s | notif_type=%s' % (
                                label, rule_so.with_user(usr).can_validate, usr.notification_type
                            ))

                    so = env['sale.order'].sudo().create({
                        'partner_id': partner.id,
                        'user_id': u_op.id,
                        'company_id': company_bg.id,
                        'order_line': [(0, 0, {
                            'product_id': product.id,
                            'name': 'Simulación Escenario B',
                            'product_uom_qty': 1,
                            'price_unit': 100000.0,
                        })],
                    })
                    env.flush_all()
                    last_msg = (env['mail.message'].search([], order='id desc', limit=1).id or 0)
                    last_act = (env['mail.activity'].search([], order='id desc', limit=1).id or 0)
                    last_nf = (env['mail.notification'].search([], order='id desc', limit=1).id or 0)

                    print('\n  [Paso B1] Operador dispara check_approval:')
                    res = safe(Rule.with_user(u_op).check_approval, 'sale.order', so.id, 'action_confirm', False)
                    env.flush_all()
                    print('  check_approval -> approved=%s' % (res.get('approved') if isinstance(res, dict) else res))
                    _inspect_so_events(so, last_msg, last_act, last_nf)

                    print('\n  [Paso B2] Prueba directa de @mención en chatter hacia Hernán F. y Euge con inbox:')
                    last_msg2 = (env['mail.message'].search([], order='id desc', limit=1).id or 0)
                    last_act2 = (env['mail.activity'].search([], order='id desc', limit=1).id or 0)
                    last_nf2 = (env['mail.notification'].search([], order='id desc', limit=1).id or 0)
                    from markupsafe import Markup
                    mentions = ' '.join(
                        '<a href="#" data-oe-model="res.partner" data-oe-id="%s">@%s</a>' % (u.partner_id.id, u.name)
                        for u in notif_users
                    )
                    so.with_user(u_op).message_post(
                        body=Markup('Solicitud de aprobación pendiente para %s') % Markup(mentions),
                        partner_ids=notif_users.mapped('partner_id').ids,
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )
                    env.flush_all()
                    _inspect_so_events(so, last_msg2, last_act2, last_nf2)

                    print('\n  [Paso B3] Eugenia aprueba (set_approval) para ver qué dispara users_to_notify:')
                    last_msg3 = (env['mail.message'].search([], order='id desc', limit=1).id or 0)
                    last_act3 = (env['mail.activity'].search([], order='id desc', limit=1).id or 0)
                    last_nf3 = (env['mail.notification'].search([], order='id desc', limit=1).id or 0)
                    safe(rule_so.with_user(u_euge).set_approval, so.id, True)
                    env.flush_all()
                    _inspect_so_events(so, last_msg3, last_act3, last_nf3)

                    raise _Undo()
            except _Undo:
                pass
            env.invalidate_all()

finally:
    env.cr.rollback()
    print('\n>> ROLLBACK FINAL EJECUTADO: Base de datos intacta (0 cambios persistidos).')
