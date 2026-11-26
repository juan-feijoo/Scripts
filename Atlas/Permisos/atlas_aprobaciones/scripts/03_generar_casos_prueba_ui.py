# -*- coding: utf-8 -*-
# 03 - Genera casos de prueba visuales para validar en UI (solo staging; respeta DRY_RUN / APPLY=1)
import odoo

h('03 - GENERACIÓN DE CASOS DE PRUEBA VISUALES PARA UI (STAGING)')
print('DB:   %s | Odoo %s' % (env.cr.dbname, odoo.release.version))
print('MODO: %s' % ('DRY-RUN (Simulación con ROLLBACK)' if DRY_RUN else 'REAL (APPLY=1 -> COMMIT)'))

try:
    check_db_safety()
    if is_production_db():
        print('  ℹ Base de producción detectada: se omite la creación de documentos demo de UI.')
    else:
        if DRY_RUN:
            print('  ℹ DRY-RUN: aplicando configuración temporal en memoria para simular los casos UI...')
            ctx = apply_atlas_configuration(verbose=False)
            company_bg = ctx['company_bg']
            partner_tercero = ctx['partner_tercero']
            u_op = ctx['users']['mandatario@atlasgroup.com.ar']
            u_euge = ctx['users']['eugeniazanotti@atlasgroup.com.ar']
            u_hf = ctx['users']['hernanfernandez@atlasgroup.com.ar']
        else:
            company_bg = get_company(COMPANY_NAME)
            partner_tercero = env['res.partner'].sudo().search([('name', '=', CONTACTO_CIRCUITO_COMPRA)], limit=1)
            u_op = find_user('mandatario@atlasgroup.com.ar')
            u_euge = find_user('eugeniazanotti@atlasgroup.com.ar')
            u_hf = find_user('hernanfernandez@atlasgroup.com.ar')

        if not (company_bg and partner_tercero and u_op and u_euge and u_hf):
            raise Exception('Faltan usuarios, compañía BG o contacto tercero. Correr Script 01 primero.')

        # 1. Asegurar proyecto, cliente demo y proveedor normal demo
        sub('1. Datos base para pruebas visuales (Proyecto, Cliente Demo y Proveedor Regular)')
        Project = env['project.project'].sudo()
        project = Project.search([('name', '=', PROYECTO_CIRCUITO_NAME), ('company_id', '=', company_bg.id)], limit=1)
        if not project:
            project = Project.create({
                'name': PROYECTO_CIRCUITO_NAME,
                'company_id': company_bg.id,
                'privacy_visibility': 'employees',
            })
            print('  [creado]    Proyecto: %s (id=%s)' % (project.name, project.id))
        else:
            project.write({'privacy_visibility': 'employees'})
            print('  [existente] Proyecto: %s (id=%s)' % (project.name, project.id))

        Partner = env['res.partner'].sudo()
        partner_cliente = Partner.search([('name', '=', CLIENTE_DEMO_NAME)], limit=1)
        if not partner_cliente:
            partner_cliente = Partner.create({
                'name': CLIENTE_DEMO_NAME,
                'is_company': True,
                'company_id': company_bg.id,
                'customer_rank': 1,
                'street': 'Av. Libertador 1000',
                'city': 'Buenos Aires',
            })
            print('  [creado]    Cliente demo: %s (id=%s)' % (partner_cliente.name, partner_cliente.id))
        else:
            print('  [existente] Cliente demo: %s (id=%s)' % (partner_cliente.name, partner_cliente.id))

        partner_normal = Partner.search([('name', '=', PROV_NORMAL_DEMO_NAME)], limit=1)
        if not partner_normal:
            partner_normal = Partner.create({
                'name': PROV_NORMAL_DEMO_NAME,
                'is_company': True,
                'company_id': company_bg.id,
                'supplier_rank': 1,
                'street': 'Av. Santa Fe 1500',
                'city': 'Buenos Aires',
            })
            print('  [creado]    Proveedor regular demo: %s (id=%s)' % (partner_normal.name, partner_normal.id))
        else:
            print('  [existente] Proveedor regular demo: %s (id=%s)' % (partner_normal.name, partner_normal.id))

        Product = env['product.product'].sudo()
        prod = Product.search([('sale_ok', '=', True), ('purchase_ok', '=', True)], limit=1) \
            or Product.search([], limit=1)
        print('  [producto]  %s (id=%s)' % (prod.display_name, prod.id))

        # 2. Limpiar casos demo previos (DEMO-ATLAS-*)
        sub('2. Limpieza de casos demo previos (DEMO-ATLAS-*)')
        old_sos = env['sale.order'].sudo().search([('client_order_ref', '=like', 'DEMO-ATLAS-%')])
        if old_sos:
            old_sos.filtered(lambda s: s.state != 'draft').action_cancel()
            old_sos.unlink()
            print('  Eliminadas %s OV demo anteriores' % len(old_sos))
        old_pos = env['purchase.order'].sudo().search([('partner_ref', '=like', 'DEMO-ATLAS-%')])
        if old_pos:
            if has_field('purchase.order', 'related_sale_order_id'):
                old_pos.write({'related_sale_order_id': False})
            old_pos.filtered(lambda p: p.state != 'draft').button_cancel()
            old_pos.unlink()
            print('  Eliminadas %s OC demo anteriores' % len(old_pos))

        Rule = env['studio.approval.rule']

        # 3. Caso UI A: Orden de Venta pendiente de aprobación (con proyecto compartido)
        sub('3. Caso UI A: Orden de Venta pendiente de aprobación (notifica a Hernán F. y Euge)')
        so_vals = {
            'partner_id': partner_cliente.id,
            'user_id': u_op.id,
            'company_id': company_bg.id,
            'client_order_ref': 'DEMO-ATLAS-OV',
            'note': (
                'CASO UI VENTAS: Creada por Operador. Solicitud de aprobación enviada a Hernán F. y Eugenia '
                '(reloj 🕒 + Bandeja 💬). Una vez confirmada la OC de tercero del mismo proyecto, '
                'vincularla en el campo "Órdenes de Compra relacionadas".'
            ),
            'order_line': [(0, 0, {
                'product_id': prod.id,
                'name': 'Servicio Operativo Integral - Prueba Aprobación Ventas',
                'product_uom_qty': 1,
                'price_unit': 250000.0,
            })],
        }
        if has_field('sale.order', 'project_id'):
            so_vals['project_id'] = project.id
        so_demo = env['sale.order'].sudo().create(so_vals)
        env.flush_all()

        # Disparar solicitud COMO OPERADOR para generar actividad 🕒 + notificación bandeja 💬
        last_msg_so = env['mail.message'].search([], order='id desc', limit=1).id or 0
        res_so = Rule.with_user(u_op).check_approval('sale.order', so_demo.id, 'action_confirm', False)
        env.flush_all()
        acts_so = env['mail.activity'].sudo().search([('res_model', '=', 'sale.order'), ('res_id', '=', so_demo.id)])
        notifs_so = env['mail.notification'].sudo().search([
            ('mail_message_id.model', '=', 'sale.order'),
            ('mail_message_id.res_id', '=', so_demo.id),
            ('mail_message_id', '>', last_msg_so),
            ('notification_type', '=', 'inbox'),
        ])
        print('  ✔ OV %s (id=%s) | approved=%s | proyecto=%s' % (so_demo.name, so_demo.id, res_so.get('approved'), project.name))
        print('    Actividades 🕒: %s' % acts_so.mapped('user_id.login'))
        print('    Bandeja 💬:     %s' % notifs_so.mapped('res_partner_id.name'))

        # 4. Caso UI B: Compra al contacto tercero pendiente de aprobación (mismo proyecto)
        sub('4. Caso UI B: OC a Tercero pendiente de aprobación (circuito contacto particular + relacion_oc_ov)')
        po_terc_vals = {
            'partner_id': partner_tercero.id,
            'user_id': u_op.id,
            'company_id': company_bg.id,
            'partner_ref': 'DEMO-ATLAS-OC-TERCERO',
            'notes': (
                'CASO UI COMPRAS TERCERO: Proveedor = %s. Exige aprobación de Eugenia o Hernán F. '
                'Luego de aprobar y confirmar, abrir la OV %s y seleccionarla en "Órdenes de Compra relacionadas".'
                % (partner_tercero.name, so_demo.name)
            ),
            'order_line': [(0, 0, {
                'product_id': prod.id,
                'name': 'Gasto de Terceros - Requiere Aprobación',
                'product_qty': 1,
                'price_unit': 120000.0,
            })],
        }
        if has_field('purchase.order', 'project_id'):
            po_terc_vals['project_id'] = project.id
        po_terc_demo = env['purchase.order'].sudo().create(po_terc_vals)
        env.flush_all()

        last_msg_po = env['mail.message'].search([], order='id desc', limit=1).id or 0
        res_po = Rule.with_user(u_op).check_approval('purchase.order', po_terc_demo.id, 'button_confirm', False)
        env.flush_all()
        acts_po = env['mail.activity'].sudo().search([('res_model', '=', 'purchase.order'), ('res_id', '=', po_terc_demo.id)])
        notifs_po = env['mail.notification'].sudo().search([
            ('mail_message_id.model', '=', 'purchase.order'),
            ('mail_message_id.res_id', '=', po_terc_demo.id),
            ('mail_message_id', '>', last_msg_po),
            ('notification_type', '=', 'inbox'),
        ])
        print('  ✔ OC Tercero %s (id=%s) | partner=%s | approved=%s | proyecto=%s' % (
            po_terc_demo.name, po_terc_demo.id, partner_tercero.name, res_po.get('approved'), project.name
        ))
        print('    Actividades 🕒: %s' % acts_po.mapped('user_id.login'))
        print('    Bandeja 💬:     %s' % notifs_po.mapped('res_partner_id.name'))

        # 5. Caso UI C: Compra a proveedor regular (NO debe exigir aprobación)
        sub('5. Caso UI C: OC a proveedor regular (debe confirmar directo sin pedir aprobación)')
        po_norm_demo = env['purchase.order'].sudo().create({
            'partner_id': partner_normal.id,
            'user_id': u_op.id,
            'company_id': company_bg.id,
            'partner_ref': 'DEMO-ATLAS-OC-NORMAL',
            'notes': 'CASO UI COMPRAS SIN APROBACIÓN: Proveedor distinto al tercero. Confirmar Pedido debe avanzar directo.',
            'order_line': [(0, 0, {
                'product_id': prod.id,
                'name': 'Insumo Regular - Sin Aprobación',
                'product_qty': 1,
                'price_unit': 35000.0,
            })],
        })
        print('  ✔ OC Regular %s (id=%s) | partner=%s (sin aprobación)' % (
            po_norm_demo.name, po_norm_demo.id, partner_normal.name
        ))

        env.flush_all()
        if DRY_RUN:
            env.cr.rollback()
            print('\n>> DRY-RUN COMPLETADO -> ROLLBACK (casos UI no persistidos aún).')
        else:
            env.cr.commit()
            print('\n>> COMMIT EXITOSO: Casos UI guardados en Staging.')
            print('   - OV pendiente:         %s (ref: DEMO-ATLAS-OV)' % so_demo.name)
            print('   - OC tercero pendiente: %s (ref: DEMO-ATLAS-OC-TERCERO)' % po_terc_demo.name)
            print('   - OC regular libre:     %s (ref: DEMO-ATLAS-OC-NORMAL)' % po_norm_demo.name)
            print('   - Proyecto compartido:  %s' % project.name)
            if SET_STAGING_PASSWORDS:
                print('   - Clave staging:        %s' % TEST_PASSWORD)

except Exception:
    traceback.print_exc(file=sys.stdout)
    env.cr.rollback()
    print('!! ERROR -> ROLLBACK EJECUTADO')
