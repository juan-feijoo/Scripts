# ==============================================================================
# SCRIPT 02: CONFIGURACIÓN DE USUARIOS, MULTI-COMPANY Y APROBADORES STUDIO
# Odoo 18.0+e en Odoo.sh (Atlas Group)
# ==============================================================================
# Ejecución en pestaña Shell: odoo-bin shell
# Modo por defecto: DRY_RUN = True (simula y hace rollback).
# Para persistir cambios: cambiar DRY_RUN = False y re-ejecutar.

import sys
import traceback

# ------------------------------------------------------------------------------
# PARÁMETROS DE CONFIGURACIÓN
# ------------------------------------------------------------------------------
DRY_RUN =  False  # Cambiar a False para aplicar COMMIT real tras verificar los ✔
EXPECTED_DB = 'outsource-argentina-atlas-group1-staging-40016719'
MOD = 'atlas_security_approvals'

# Mapeo de Usuarios, Roles, Apps Nativas y Restricción de Compañía
USERS_CONFIG = {
    'mandatario@atlasgroup.com.ar': {
        'name': 'Operador',
        'role': 'group_role_operador',
        'apps': [
            'sales_team.group_sale_salesman',
            'purchase.group_purchase_user',
        ],
        'disallowed_apps': [
            'sales_team.group_sale_salesman_all_leads',
            'sales_team.group_sale_manager',
            'purchase.group_purchase_manager',
            'account.group_account_invoice',
            'account.group_account_user',
            'account.group_account_manager',
            'base.group_system',
            'base.group_erp_manager',
        ],
        'allow_1066': False,  # EXCLUIDO ESTRICTAMENTE DE 1066 S.A.
    },
    'hernanpacetti@atlasgroup.com.ar': {
        'name': 'Hernan Pacetti',
        'role': 'group_role_resp_operaciones',
        'apps': [
            'sales_team.group_sale_salesman_all_leads',
            'purchase.group_purchase_user',
        ],
        'disallowed_apps': [
            'sales_team.group_sale_manager',
            'purchase.group_purchase_manager',
            'account.group_account_invoice',
            'account.group_account_user',
            'account.group_account_manager',
            'base.group_system',
            'base.group_erp_manager',
        ],
        'allow_1066': False,  # EXCLUIDO ESTRICTAMENTE DE 1066 S.A.
    },
    'administracion@atlasgroup.com.ar': {
        'name': 'Tomás Di Leo',
        'role': 'group_role_administrativo',
        'apps': [
            'sales_team.group_sale_salesman_all_leads',
            'purchase.group_purchase_user',
            'account.group_account_user',
        ],
        'disallowed_apps': [
            'sales_team.group_sale_manager',
            'purchase.group_purchase_manager',
            'account.group_account_manager',
            'base.group_system',
            'base.group_erp_manager',
            f'{MOD}.group_atlas_can_unlink',
            f'{MOD}.group_atlas_aprob_venta',
            f'{MOD}.group_atlas_aprob_compra',
        ],
        'allow_1066': True,
    },
    'eugeniazanotti@atlasgroup.com.ar': {
        'name': 'Eugenia Zanotti',
        'role': 'group_role_resp_administracion',
        'apps': [
            'sales_team.group_sale_manager',
            'purchase.group_purchase_manager',
            'account.group_account_manager',
        ],
        'disallowed_apps': [
            'base.group_system',
        ],
        'allow_1066': True,
    },
    'hernanfernandez@atlasgroup.com.ar': {
        'name': 'Hernan Fernandez',
        'role': 'group_role_resp_general',
        'apps': [
            'sales_team.group_sale_manager',
            'purchase.group_purchase_manager',
            'account.group_account_manager',
        ],
        'disallowed_apps': [],
        'allow_1066': True,
    },
}

# Aprobadores directos para asignación en reglas Studio (Odoo 18 / Actividades Chatter)
APROBADORES_POR_GRUPO = {
    'group_atlas_aprob_venta': [
        'hernanpacetti@atlasgroup.com.ar',
        'eugeniazanotti@atlasgroup.com.ar',
        'hernanfernandez@atlasgroup.com.ar',
    ],
    'group_atlas_aprob_compra': [
        'eugeniazanotti@atlasgroup.com.ar',
        'hernanfernandez@atlasgroup.com.ar',
    ],
}

ok_all = True

def check(cond, msg):
    global ok_all
    ok_all &= bool(cond)
    print(('  ✔ ' if cond else '  ✘ ') + msg)

try:
    import odoo
    print("=" * 80)
    print(f"CONFIGURACIÓN DE SEGURIDAD ATLAS - Odoo {odoo.release.version}")
    print(f"DB ACTUAL : {env.cr.dbname}")
    print(f"MODO      : {'DRY-RUN (Simulación con Rollback)' if DRY_RUN else 'REAL (Commit en Base de Datos)'}")
    print("=" * 80)

    # Verificación de Base de Datos
    if env.cr.dbname != EXPECTED_DB:
        if 'atlas' in env.cr.dbname.lower():
            print(f"  ⚠ Advertencia: Base actual ({env.cr.dbname}) difiere de EXPECTED_DB ({EXPECTED_DB}), pero contiene 'atlas'. Continuando...")
        else:
            raise Exception(f"Base de datos no autorizada: {env.cr.dbname}. Se esperaba: {EXPECTED_DB}")

    # 1. Obtener Compañías
    company_bg = env['res.company'].search([('name', 'ilike', 'BULGHERONI')], limit=1)
    company_1066 = env['res.company'].search([('name', 'ilike', '1066')], limit=1)
    check(company_bg, f"Compañía BG encontrada: '{company_bg.name}' (ID {company_bg.id})")
    check(company_1066, f"Compañía 1066 encontrada: '{company_1066.name}' (ID {company_1066.id})")

    # 2. Configurar Usuarios, Multi-Company y Grupos
    print("\n=== [1] CONFIGURACIÓN DE USUARIOS Y ACCESOS ===")
    Users = env['res.users'].with_context(active_test=False)
    user_records = {}

    for login, data in USERS_CONFIG.items():
        u = Users.search([('login', '=ilike', login.strip())], limit=1)
        allowed_cos = [company_bg.id] if not data['allow_1066'] else [company_bg.id, company_1066.id]

        if not u:
            # Alta técnica sin enviar correo de invitación / reseteo
            u = Users.with_context(no_reset_password=True).create({
                'name': data['name'],
                'login': login,
                'email': login,
                'company_id': company_bg.id,
                'company_ids': [(6, 0, allowed_cos)],
                'groups_id': [(6, 0, [env.ref('base.group_user').id])],
            })
            print(f"  Usuario CREADO: {login} (ID {u.id}) | Nombre: {data['name']}")
        else:
            if not u.active:
                u.active = True
                print(f"  Usuario REACTIVADO: {login}")
            
            # Forzar actualización de compañías asignadas
            u.write({
                'company_id': company_bg.id,
                'company_ids': [(6, 0, allowed_cos)],
            })
            print(f"  Usuario ACTUALIZADO: {login} (ID {u.id}) | Cías: {[c.name for c in u.company_ids]}")
        
        user_records[login] = u

        # Asignar grupos de aplicaciones requeridas
        groups_to_add = []
        for xmlid in data['apps']:
            grp = env.ref(xmlid, raise_if_not_found=False)
            if grp:
                groups_to_add.append(grp.id)
            else:
                print(f"    ⚠ Grupo app no encontrado en DB: {xmlid}")

        # Asignar Rol Custom Atlas
        role_xmlid = f"{MOD}.{data['role']}"
        role_group = env.ref(role_xmlid, raise_if_not_found=False)
        if role_group:
            groups_to_add.append(role_group.id)
        else:
            print(f"    ⚠ Rol Atlas no encontrado en DB: {role_xmlid} (¿está instalado el módulo {MOD}?)")

        if groups_to_add:
            u.write({'groups_id': [(4, gid) for gid in groups_to_add]})

        # Remover grupos explícitamente denegados
        groups_to_remove = []
        for xmlid in data.get('disallowed_apps', []):
            grp = env.ref(xmlid, raise_if_not_found=False)
            if grp and grp in u.groups_id:
                groups_to_remove.append(grp.id)
        if groups_to_remove:
            u.write({'groups_id': [(3, gid) for gid in groups_to_remove]})
            print(f"    Grupos denegados removidos para {login}: {[env['res.groups'].browse(gid).name for gid in groups_to_remove]}")

    # 3. Vincular Aprobadores en Reglas Studio
    print("\n=== [2] VINCULACIÓN DE APROBADORES EN REGLAS STUDIO ===")
    Rules = env['studio.approval.rule'].with_context(active_test=False)
    rules_atlas = Rules.search([('name', '=like', '[ATLAS]%')])

    if not rules_atlas:
        print(f"  ⚠ No se encontraron reglas con prefijo '[ATLAS]'.")
        print(f"     Asegúrese de instalar/actualizar el módulo '{MOD}' antes de correr este script.")
        ok_all = False
    else:
        for r in rules_atlas:
            if not r.approval_group_id:
                print(f"  ⚠ Regla ID {r.id} '{r.name}' no tiene grupo asignado.")
                continue
            
            # Obtener el XML ID del grupo de aprobación
            group_xmlid_full = r.approval_group_id.get_external_id().get(r.approval_group_id.id, '')
            group_short = group_xmlid_full.split('.')[-1]
            
            target_logins = APROBADORES_POR_GRUPO.get(group_short, [])
            appr_users = Users.search([('login', 'in', target_logins)])
            
            r.write({
                'approver_ids': [(6, 0, appr_users.ids)],
                'users_to_notify': [(5, 0, 0)],
                'active': True,
            })
            print(f"  Regla '{r.name}' (ID {r.id}) → Aprobadores vinculados: {appr_users.mapped('login')}")

    env.flush_all()

    # 4. Verificación de Reglas de Negocio (Assertions)
    print("\n=== [3] VERIFICACIÓN ESTRICTA DE SEGURIDAD (ASSERTIONS) ===")
    
    # A. Multi-Compañía
    op = user_records.get('mandatario@atlasgroup.com.ar')
    ro = user_records.get('hernanpacetti@atlasgroup.com.ar')
    adm = user_records.get('administracion@atlasgroup.com.ar')
    resp_adm = user_records.get('eugeniazanotti@atlasgroup.com.ar')
    resp_gen = user_records.get('hernanfernandez@atlasgroup.com.ar')

    if op and company_1066:
        check(company_1066 not in op.company_ids, "Operador: Excluido de 1066 S.A. (Solo BG)")
    if ro and company_1066:
        check(company_1066 not in ro.company_ids, "Resp. Operaciones: Excluido de 1066 S.A. (Solo BG)")
    if adm and company_1066:
        check(company_1066 in adm.company_ids, "Administrativo: Acceso a ambas compañías (BG y 1066)")

    # B. Permiso de Eliminación (Unlink)
    grp_unlink = env.ref(f"{MOD}.group_atlas_can_unlink", raise_if_not_found=False)
    if grp_unlink:
        if op:
            check(grp_unlink not in op.groups_id, "Operador: NO tiene permiso de eliminación")
        if ro:
            check(grp_unlink not in ro.groups_id, "Resp. Operaciones: NO tiene permiso de eliminación")
        if adm:
            check(grp_unlink not in adm.groups_id, "Administrativo: NO tiene permiso de eliminación")
        if resp_adm:
            check(grp_unlink in resp_adm.groups_id, "Resp. Administración: SÍ tiene permiso de eliminación")
        if resp_gen:
            check(grp_unlink in resp_gen.groups_id, "Resp. General: SÍ tiene permiso de eliminación")
    else:
        check(False, f"Grupo '{MOD}.group_atlas_can_unlink' no existe en DB.")

    # C. Permisos de Aprobación en Reglas Studio
    rule_so = Rules.search([('name', '=like', '%Orden de Venta%')], limit=1)
    if rule_so:
        if op:
            check(not rule_so.with_user(op).can_validate, "Operador: NO puede validar Orden de Venta")
        if ro:
            check(rule_so.with_user(ro).can_validate, "Resp. Operaciones: SÍ puede validar Orden de Venta")
        if adm:
            check(not rule_so.with_user(adm).can_validate, "Administrativo: NO puede validar Orden de Venta")
        if resp_adm:
            check(rule_so.with_user(resp_adm).can_validate, "Resp. Administración: SÍ puede validar Orden de Venta")
        if resp_gen:
            check(rule_so.with_user(resp_gen).can_validate, "Resp. General: SÍ puede validar Orden de Venta")

    rule_po = Rules.search([('name', '=like', '%Requerimiento de Compra%')], limit=1)
    if rule_po:
        if op:
            check(not rule_po.with_user(op).can_validate, "Operador: NO puede validar Requerimiento de Compra")
        if ro:
            check(not rule_po.with_user(ro).can_validate, "Resp. Operaciones: NO puede validar Requerimiento de Compra")
        if adm:
            check(not rule_po.with_user(adm).can_validate, "Administrativo: NO puede validar Requerimiento de Compra")
        if resp_adm:
            check(rule_po.with_user(resp_adm).can_validate, "Resp. Administración: SÍ puede validar Requerimiento de Compra")
        if resp_gen:
            check(rule_po.with_user(resp_gen).can_validate, "Resp. General: SÍ puede validar Requerimiento de Compra")

    # 5. Cierre y Commit / Rollback
    print("\n" + "=" * 80)
    print(f"RESULTADO FINAL: {'✔ TODO OK' if ok_all else '✘ HAY ERRORES DETECTADOS'}")
    print("=" * 80)

    if DRY_RUN or not ok_all:
        env.cr.rollback()
        print(">> ROLLBACK EJECUTADO: Ningún cambio fue persistido en la base de datos.")
        if DRY_RUN and ok_all:
            print(">> Simulación completada exitosamente. Para persistir los cambios, cambie DRY_RUN = False y vuelva a ejecutar.")
        elif not ok_all:
            print(">> Se abortó la persistencia debido a chequeos fallidos (✘). Revise los errores antes de continuar.")
    else:
        env.cr.commit()
        print(">> COMMIT EXITOSO: Todos los usuarios, accesos y aprobadores fueron guardados en la base de datos.")

except Exception:
    traceback.print_exc(file=sys.stdout)
    env.cr.rollback()
    print("\n>> ERROR CRÍTICO INESPERADO → SE EJECUTÓ ROLLBACK AUTOMÁTICO")
