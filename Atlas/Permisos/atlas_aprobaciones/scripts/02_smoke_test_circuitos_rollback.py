# -*- coding: utf-8 -*-
# 02 - Smoke Test end-to-end de notificaciones (🕒 + 💬), aprobación Ventas, Compras Tercero y vínculo relacion_oc_ov
# SIEMPRE ejecuta ROLLBACK al final (nunca deja basura en la base, incluso con APPLY=1).
import odoo

h('02 - SMOKE TEST END-TO-END: NOTIFICACIONES (🕒 + 💬), VENTAS, COMPRAS TERCERO Y RELACIÓN OC<->OV')
print('DB:   %s | Odoo %s' % (env.cr.dbname, odoo.release.version))
print('MODO: %s (este script SIEMPRE hace ROLLBACK de sus registros de prueba)' % ('DRY-RUN' if DRY_RUN else 'POST-APPLY'))

total = 0
passed = 0


def test(cond, desc):
    global total, passed
    total += 1
    if cond:
        passed += 1
        print('  ✔ [PASÓ]  %s' % desc)
    else:
        print('  ✘ [FALLÓ] %s' % desc)


try:
    check_db_safety()

    # Si estamos en DRY-RUN, 01 hizo rollback; aplicamos la config en memoria dentro de esta transacción
    # que igualmente terminará en ROLLBACK. Si estamos en APPLY=1, leemos lo ya commiteado por 01.
    if DRY_RUN:
        print('  ℹ DRY-RUN: aplicando configuración temporal en memoria para testear el circuito completo...')
        ctx = apply_atlas_configuration(verbose=False)
        company_bg = ctx['company_bg']
        company_1066 = ctx['company_1066']
        partner_tercero = ctx['partner_tercero']
        rule_so = ctx['rule_so']
        rule_po = ctx['rule_po']
        u_op = ctx['users']['mandatario@atlasgroup.com.ar']
        u_pac = ctx['users']['hernanpacetti@atlasgroup.com.ar']
        u_adm = ctx['users']['administracion@atlasgroup.com.ar']
        u_euge = ctx['users']['eugeniazanotti@atlasgroup.com.ar']
        u_hf = ctx['users']['hernanfernandez@atlasgroup.com.ar']
    else:
        company_bg = get_company(COMPANY_NAME)
        company_1066 = get_company(COMPANY_1066_NAME)
        partner_tercero = env['res.partner'].sudo().search([('name', '=', CONTACTO_CIRCUITO_COMPRA)], limit=1)
        rule_so = env['studio.approval.rule'].sudo().search([('name', '=', RULE_VENTA_NAME), ('active', '=', True)], limit=1)
        rule_po = env['studio.approval.rule'].sudo().search([('name', '=', RULE_COMPRA_NAME), ('active', '=', True)], limit=1)
        u_op = find_user('mandatario@atlasgroup.com.ar')
        u_pac = find_user('hernanpacetti@atlasgroup.com.ar')
        u_adm = find_user('administracion@atlasgroup.com.ar')
        u_euge = find_user('eugeniazanotti@atlasgroup.com.ar')
        u_hf = find_user('hernanfernandez@atlasgroup.com.ar')

    test(all([company_bg, company_1066, partner_tercero, rule_so, rule_po, u_op, u_pac, u_adm, u_euge, u_hf]),
         'Precondiciones cargadas (compañías, contacto tercero, reglas Studio y 5 usuarios)')

    # Datos auxiliares temporales (se descartan con rollback)
    partner_cliente = env['res.partner'].sudo().create({
        'name': '[SMOKE] Cliente Test',
        'company_id': company_bg.id,
        'customer_rank': 1,
    })
    partner_otro_prov = env['res.partner'].sudo().create({
        'name': '[SMOKE] Otro Proveedor Sin Regla',
        'company_id': company_bg.id,
        'supplier_rank': 1,
    })
    product = env['product.product'].sudo().search([('sale_ok', '=', True), ('purchase_ok', '=', True)], limit=1) \
        or env['product.product'].sudo().search([], limit=1)
    project = env['project.project'].sudo().create({
        'name': '[SMOKE] Proyecto Circuito OC-OV',
        'company_id': company_bg.id,
        'privacy_visibility': 'employees',
    })
    Rule = env['studio.approval.rule']
    expected_notif_partners = {u_hf.partner_id.id, u_euge.partner_id.id}
    expected_notif_logins = {'hernanfernandez@atlasgroup.com.ar', 'eugeniazanotti@atlasgroup.com.ar'}

    # ------------------------------------------------------------------
    # TEST 1: VENTAS -> ACTIVIDAD (🕒) + NOTIFICACIÓN BANDEJA INBOX (💬)
    # ------------------------------------------------------------------
    sub('TEST 1: Aprobación de Orden de Venta (notifica solo Hernán F. y Euge; aprueba también Pacetti)')
    so_vals = {
        'partner_id': partner_cliente.id,
        'user_id': u_op.id,
        'company_id': company_bg.id,
        'order_line': [(0, 0, {
            'product_id': product.id,
            'name': 'Servicio Smoke Test Venta',
            'product_uom_qty': 1,
            'price_unit': 250000.0,
        })],
    }
    if has_field('sale.order', 'project_id'):
        so_vals['project_id'] = project.id
    so = env['sale.order'].sudo().create(so_vals)
    env.flush_all()

    last_msg_id = env['mail.message'].search([], order='id desc', limit=1).id or 0
    res_so = Rule.with_user(u_op).check_approval('sale.order', so.id, 'action_confirm', False)
    env.flush_all()

    test(not res_so.get('approved'), 'OV: check_approval como Operador bloquea confirmación (approved=False)')

    acts_so = env['mail.activity'].sudo().search([('res_model', '=', 'sale.order'), ('res_id', '=', so.id)])
    act_logins_so = set(acts_so.mapped('user_id.login'))
    test(act_logins_so == expected_notif_logins,
         'OV Actividades (🕒): creadas SOLO para Hernán F. y Euge (actual: %s)' % sorted(act_logins_so))
    test('hernanpacetti@atlasgroup.com.ar' not in act_logins_so,
         'OV Actividades (🕒): Hernán Pacetti NO recibe actividad')

    msgs_so = env['mail.message'].sudo().search([
        ('model', '=', 'sale.order'),
        ('res_id', '=', so.id),
        ('id', '>', last_msg_id),
    ], order='id')
    atlas_msgs_so = msgs_so.filtered(lambda m: '[Aprobación requerida]' in strip_html(m.body))
    notifs_so = env['mail.notification'].sudo().search([('mail_message_id', 'in', atlas_msgs_so.ids)])
    inbox_so = notifs_so.filtered(lambda n: n.notification_type == 'inbox' and not n.is_read)
    inbox_partners_so = set(inbox_so.mapped('res_partner_id.id'))
    test(len(atlas_msgs_so) == 1,
         'OV Chatter: exactamente 1 nota [Aprobación requerida] sin duplicar (actual: %s)' % len(atlas_msgs_so))
    test(inbox_partners_so == expected_notif_partners and len(inbox_so) == 2,
         'OV Bandeja 💬 (mail.notification inbox sin leer): 2 exactas para Hernán F. y Euge (actual: %s)' % inbox_so.mapped('res_partner_id.name'))
    test(bool(atlas_msgs_so) and '@' in strip_html(atlas_msgs_so[0].body),
         'OV Chatter: mensaje incluye @mención visible (%s)' % (strip_html(atlas_msgs_so[0].body)[:120] if atlas_msgs_so else '-'))

    # Verificar que Hernán Pacetti SÍ puede aprobar por grupo y eso dispara users_to_notify (inbox)
    last_msg_id2 = env['mail.message'].search([], order='id desc', limit=1).id or 0
    approved_by_pac = rule_so.with_user(u_pac).set_approval(so.id, True)
    env.flush_all()
    test(bool(approved_by_pac), 'OV: Hernán Pacetti aprueba correctamente por grupo (sin haber recibido notificación previa)')

    msgs_so_appr = env['mail.message'].sudo().search([
        ('model', '=', 'sale.order'),
        ('res_id', '=', so.id),
        ('id', '>', last_msg_id2),
    ])
    inbox_so_appr = env['mail.notification'].sudo().search([
        ('mail_message_id', 'in', msgs_so_appr.ids),
        ('notification_type', '=', 'inbox'),
    ])
    test(set(inbox_so_appr.mapped('res_partner_id.id')) == expected_notif_partners,
         'OV al aprobar Pacetti: Studio notifica en bandeja 💬 a Hernán F. y Euge (%s)' % inbox_so_appr.mapped('res_partner_id.name'))

    res_so_after = Rule.with_user(u_op).check_approval('sale.order', so.id, 'action_confirm', False)
    test(bool(res_so_after.get('approved')), 'OV: tras aprobación, check_approval devuelve approved=True')

    # ------------------------------------------------------------------
    # TEST 2: COMPRAS A OTRO PROVEEDOR -> NO EXIGE APROBACIÓN
    # ------------------------------------------------------------------
    sub('TEST 2: Compra a proveedor regular (NO es el contacto tercero) -> confirma sin aprobación')
    po_normal = env['purchase.order'].sudo().create({
        'partner_id': partner_otro_prov.id,
        'user_id': u_op.id,
        'company_id': company_bg.id,
        'order_line': [(0, 0, {
            'product_id': product.id,
            'name': 'Compra regular sin aprobación',
            'product_qty': 1,
            'price_unit': 50000.0,
        })],
    })
    env.flush_all()
    res_po_normal = Rule.with_user(u_op).check_approval('purchase.order', po_normal.id, 'button_confirm', False)
    test(bool(res_po_normal.get('approved')) and not res_po_normal.get('rules'),
         'OC otro proveedor: NO aplica regla de aprobación (approved=True, 0 reglas)')

    # ------------------------------------------------------------------
    # TEST 3: COMPRAS AL CONTACTO TERCERO -> EXIGE APROBACIÓN + NOTIFICA + VÍNCULO relacion_oc_ov
    # ------------------------------------------------------------------
    sub('TEST 3: Compra al contacto tercero + aprobación + vínculo OC <-> OV (relacion_oc_ov)')
    po_vals = {
        'partner_id': partner_tercero.id,
        'user_id': u_op.id,
        'company_id': company_bg.id,
        'order_line': [(0, 0, {
            'product_id': product.id,
            'name': 'Gasto de tercero - circuito aprobación',
            'product_qty': 1,
            'price_unit': 120000.0,
        })],
    }
    if has_field('purchase.order', 'project_id'):
        po_vals['project_id'] = project.id
    po_terc = env['purchase.order'].sudo().create(po_vals)
    env.flush_all()

    last_msg_po = env['mail.message'].search([], order='id desc', limit=1).id or 0
    res_po_terc = Rule.with_user(u_op).check_approval('purchase.order', po_terc.id, 'button_confirm', False)
    env.flush_all()

    test(not res_po_terc.get('approved'),
         'OC contacto tercero (%s): bloqueada al intentar confirmar como Operador' % partner_tercero.name)

    acts_po = env['mail.activity'].sudo().search([('res_model', '=', 'purchase.order'), ('res_id', '=', po_terc.id)])
    test(set(acts_po.mapped('user_id.login')) == expected_notif_logins,
         'OC Actividades (🕒): creadas para Hernán F. y Euge (%s)' % sorted(acts_po.mapped('user_id.login')))

    msgs_po = env['mail.message'].sudo().search([
        ('model', '=', 'purchase.order'),
        ('res_id', '=', po_terc.id),
        ('id', '>', last_msg_po),
    ])
    atlas_msgs_po = msgs_po.filtered(lambda m: '[Aprobación requerida]' in strip_html(m.body))
    inbox_po = env['mail.notification'].sudo().search([
        ('mail_message_id', 'in', atlas_msgs_po.ids),
        ('notification_type', '=', 'inbox'),
        ('is_read', '=', False),
    ])
    test(len(atlas_msgs_po) == 1,
         'OC Chatter: exactamente 1 nota [Aprobación requerida] sin duplicar (actual: %s)' % len(atlas_msgs_po))
    test(set(inbox_po.mapped('res_partner_id.id')) == expected_notif_partners and len(inbox_po) == 2,
         'OC Bandeja 💬 (mail.notification inbox sin leer): 2 exactas para Hernán F. y Euge (%s)' % inbox_po.mapped('res_partner_id.name'))

    # Eugenia aprueba y se confirma la OC
    approved_po = rule_po.with_user(u_euge).set_approval(po_terc.id, True)
    test(bool(approved_po), 'OC contacto tercero: Eugenia aprueba correctamente')
    res_po_after = Rule.with_user(u_op).check_approval('purchase.order', po_terc.id, 'button_confirm', False)
    test(bool(res_po_after.get('approved')), 'OC contacto tercero: tras aprobación, check_approval devuelve approved=True')

    po_terc.sudo().button_confirm()
    test(po_terc.state in ('purchase', 'done'), 'OC contacto tercero: confirmada (state=%s)' % po_terc.state)

    # Verificar circuito relacion_oc_ov (conectar OC confirmada a OV con el mismo proyecto)
    has_rel = has_field('purchase.order', 'related_sale_order_id') and has_field('sale.order', 'related_purchase_order_ids')
    test(has_rel, 'Módulo relacion_oc_ov: campos related_sale_order_id y related_purchase_order_ids presentes')

    if has_rel:
        # Verificar el dominio exacto de la vista de relacion_oc_ov
        view_domain = [
            ('state', 'in', ('purchase', 'done')),
            ('project_id', '=', project.id),
            '|', ('related_sale_order_id', '=', False),
                 ('related_sale_order_id', '=', so.id),
        ]
        selectable_pos = env['purchase.order'].with_user(u_op).with_company(company_bg).search(view_domain)
        test(po_terc in selectable_pos,
             'relacion_oc_ov: OC confirmada es seleccionable por Operador en la OV (mismo proyecto)')

        # Conectar desde la OV como Operador (usando el inverse de related_purchase_order_ids)
        so.with_user(u_op).with_company(company_bg).write({'related_purchase_order_ids': [(4, po_terc.id)]})
        env.flush_all()
        so.invalidate_recordset()
        po_terc.invalidate_recordset()

        test(po_terc.related_sale_order_id.id == so.id,
             'relacion_oc_ov: PO.related_sale_order_id apunta a la OV (%s)' % po_terc.related_sale_order_id.name)
        test(so.related_purchase_order_count == 1 and po_terc in so.related_purchase_order_ids,
             'relacion_oc_ov: OV muestra related_purchase_order_count=1 y contiene la OC (%s)' % po_terc.name)

    print('\n' + '=' * 100)
    print('RESUMEN SMOKE TEST: %s/%s PRUEBAS EXITOSAS' % (passed, total))
    print('=' * 100)
    if passed != total:
        print('!! ERROR: Fallaron %s pruebas en Smoke Test.' % (total - passed))

except Exception:
    traceback.print_exc(file=sys.stdout)
    print('!! ERROR INESPERADO EN SMOKE TEST')
finally:
    env.cr.rollback()
    print('>> ROLLBACK FINAL EJECUTADO: Ningún dato temporal de prueba fue persistido.')
