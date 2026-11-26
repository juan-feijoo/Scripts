# -*- coding: utf-8 -*-
# 01 - Configuración integral de grupos, usuarios (inbox), contacto tercero, reglas Studio y automatización
# Por defecto DRY_RUN=True (hace ROLLBACK). Para aplicar cambios reales: APPLY=1 bash run_all.sh
import odoo

h('01 - CONFIGURACIÓN ATLAS: USUARIOS, CONTACTO TERCERO, REGLAS STUDIO Y NOTIFICACIONES')
print('DB:   %s | Odoo %s' % (env.cr.dbname, odoo.release.version))
print('MODO: %s' % ('DRY-RUN (Simulación con ROLLBACK)' if DRY_RUN else 'REAL (APPLY=1 -> COMMIT si todo OK)'))

ok_all = True


def check(cond, msg):
    global ok_all
    ok_all &= bool(cond)
    print(('  ✔ ' if cond else '  ✘ ') + msg)


try:
    check_db_safety()
    res = apply_atlas_configuration(verbose=True)

    company_bg = res['company_bg']
    company_1066 = res['company_1066']
    groups = res['groups']
    users = res['users']
    partner_tercero = res['partner_tercero']
    rule_so = res['rule_so']
    rule_po = res['rule_po']
    auto = res['auto']

    u_op = users['mandatario@atlasgroup.com.ar']
    u_pac = users['hernanpacetti@atlasgroup.com.ar']
    u_adm = users['administracion@atlasgroup.com.ar']
    u_euge = users['eugeniazanotti@atlasgroup.com.ar']
    u_hf = users['hernanfernandez@atlasgroup.com.ar']

    sub('6. Verificación estricta (Assertions)')

    # A. Multi-compañía
    check(company_1066 not in u_op.company_ids and company_bg in u_op.company_ids,
          'Operador: solo BG (excluido de 1066 S.A.)')
    check(company_1066 not in u_pac.company_ids and company_bg in u_pac.company_ids,
          'Hernán Pacetti: solo BG (excluido de 1066 S.A.)')
    check(company_1066 in u_adm.company_ids and company_bg in u_adm.company_ids,
          'Administrativo: acceso a BG y 1066 S.A.')
    check(company_1066 in u_euge.company_ids and company_bg in u_euge.company_ids,
          'Eugenia Zanotti: acceso a BG y 1066 S.A.')
    check(company_1066 in u_hf.company_ids and company_bg in u_hf.company_ids,
          'Hernán Fernández: acceso a BG y 1066 S.A.')

    # B. Notificaciones en bandeja de Odoo (inbox)
    for login, u in users.items():
        check(u.notification_type == 'inbox', '%s: notification_type = inbox (Gestionar en Odoo)' % login)

    # C. Permisos base denegados en Administrativo
    check(not u_adm.has_group('base.group_system') and not u_adm.has_group('base.group_erp_manager'),
          'Administrativo: sin permisos de Configuración/Sistema')
    check(not u_euge.has_group('base.group_system'),
          'Eugenia Zanotti: sin base.group_system')

    # D. Contacto tercero creado correctamente
    check(bool(partner_tercero.id) and partner_tercero.active and partner_tercero.supplier_rank >= 1,
          'Contacto tercero activo y proveedor: %s (id=%s, comp=%s)' % (
              partner_tercero.name, partner_tercero.id, partner_tercero.company_id.name
          ))

    # E. Regla Ventas: aprueban Pacetti + Euge + Hernán F.; notifican SOLO Hernán F. + Euge
    expected_notif_so = {u_hf.id, u_euge.id}
    check(set(rule_so.approver_ids.ids) == expected_notif_so,
          'Regla Ventas approver_ids (actividad 🕒) = %s' % rule_so.approver_ids.mapped('login'))
    check(set(rule_so.users_to_notify.ids) == expected_notif_so,
          'Regla Ventas users_to_notify (nota aprobación) = %s' % rule_so.users_to_notify.mapped('login'))
    check(not rule_so.with_user(u_op).can_validate, 'Regla Ventas: Operador NO puede aprobar')
    check(rule_so.with_user(u_pac).can_validate, 'Regla Ventas: Hernán Pacetti SÍ puede aprobar (por grupo, sin notif)')
    check(not rule_so.with_user(u_adm).can_validate, 'Regla Ventas: Administrativo NO puede aprobar')
    check(rule_so.with_user(u_euge).can_validate, 'Regla Ventas: Eugenia Zanotti SÍ puede aprobar')
    check(rule_so.with_user(u_hf).can_validate, 'Regla Ventas: Hernán Fernández SÍ puede aprobar')

    # F. Regla Compras: dominio solo contacto tercero; aprueban y notifican Euge + Hernán F.
    expected_domain = str([('partner_id', '=', partner_tercero.id)])
    check(rule_po.domain == expected_domain,
          'Regla Compras dominio = %s' % rule_po.domain)
    check(set(rule_po.approver_ids.ids) == expected_notif_so,
          'Regla Compras approver_ids (actividad 🕒) = %s' % rule_po.approver_ids.mapped('login'))
    check(set(rule_po.users_to_notify.ids) == expected_notif_so,
          'Regla Compras users_to_notify = %s' % rule_po.users_to_notify.mapped('login'))
    check(not rule_po.with_user(u_op).can_validate, 'Regla Compras: Operador NO puede aprobar')
    check(not rule_po.with_user(u_pac).can_validate, 'Regla Compras: Hernán Pacetti NO puede aprobar')
    check(not rule_po.with_user(u_adm).can_validate, 'Regla Compras: Administrativo NO puede aprobar')
    check(rule_po.with_user(u_euge).can_validate, 'Regla Compras: Eugenia Zanotti SÍ puede aprobar')
    check(rule_po.with_user(u_hf).can_validate, 'Regla Compras: Hernán Fernández SÍ puede aprobar')

    # G. Automatización de notificación en bandeja 💬
    check(auto.active and auto.trigger == 'on_create' and bool(auto.action_server_ids),
          'Automatización base.automation activa sobre studio.approval.request (id=%s)' % auto.id)

    print('\n' + '=' * 100)
    print('RESULTADO SCRIPT 01: %s' % ('✔ TODO OK' if ok_all else '✘ HAY ERRORES'))
    print('=' * 100)

    if DRY_RUN or not ok_all:
        env.cr.rollback()
        print('>> ROLLBACK EJECUTADO (nada persistido en BD).')
        if DRY_RUN and ok_all:
            print('>> DRY-RUN exitoso. Para guardar en BD, correr: APPLY=1 bash run_all.sh')
    else:
        if hasattr(env.registry, 'signal_change'):
            env.registry.signal_change()
        env.cr.commit()
        print('>> COMMIT EXITOSO: usuarios, contacto tercero, reglas Studio y automatización guardados.')

except Exception:
    traceback.print_exc(file=sys.stdout)
    env.cr.rollback()
    print('!! ERROR CRÍTICO -> ROLLBACK EJECUTADO')
