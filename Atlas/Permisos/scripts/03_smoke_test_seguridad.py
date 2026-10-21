# ==============================================================================
# SCRIPT 03: SMOKE TEST DE SEGURIDAD Y APROBACIONES (Simulación 100% Segura)
# Odoo 18.0+e en Odoo.sh (Atlas Group)
# ==============================================================================
# Ejecución en pestaña Shell: odoo-bin shell
# Utiliza Savepoints transaccionales. NO crea ni modifica datos permanentes.

import sys
import traceback
from odoo.exceptions import UserError, AccessError

print("=" * 80)
print(f"SMOKE TEST DE SEGURIDAD ATLAS - DB: {env.cr.dbname}")
print("=" * 80)

Users = env['res.users'].with_context(active_test=False)
Rules = env['studio.approval.rule']

u_operador = Users.search([('login', '=', 'mandatario@atlasgroup.com.ar')], limit=1)
u_resp_op = Users.search([('login', '=', 'hernanpacetti@atlasgroup.com.ar')], limit=1)
u_adm = Users.search([('login', '=', 'administracion@atlasgroup.com.ar')], limit=1)
u_resp_adm = Users.search([('login', '=', 'eugeniazanotti@atlasgroup.com.ar')], limit=1)
u_resp_gen = Users.search([('login', '=', 'hernanfernandez@atlasgroup.com.ar')], limit=1)

company_bg = env['res.company'].search([('name', 'ilike', 'BULGHERONI')], limit=1)
company_1066 = env['res.company'].search([('name', 'ilike', '1066')], limit=1)

partner_demo = env['res.partner'].search([('company_id', 'in', (False, company_bg.id))], limit=1)
product_demo = env['product.product'].search([('sale_ok', '=', True)], limit=1)

total_tests = 0
passed_tests = 0

def test(cond, desc):
    global total_tests, passed_tests
    total_tests += 1
    if cond:
        passed_tests += 1
        print(f"  ✔ [PASÓ] {desc}")
    else:
        print(f"  ✘ [FALLÓ] {desc}")

class RollbackTest(Exception):
    pass

try:
    # --------------------------------------------------------------------------
    # TEST 1: RESTRICCIÓN MULTI-COMPAÑÍA (1066 S.A.)
    # --------------------------------------------------------------------------
    print("\n[TEST 1] AISLAMIENTO MULTI-COMPAÑÍA (BG vs 1066):")
    if u_operador and company_1066:
        test(company_1066.id not in u_operador.company_ids.ids, "Operador tiene prohibido el acceso a 1066 S.A.")
    if u_resp_op and company_1066:
        test(company_1066.id not in u_resp_op.company_ids.ids, "Resp. Operaciones tiene prohibido el acceso a 1066 S.A.")
    if u_adm and company_1066:
        test(company_1066.id in u_adm.company_ids.ids, "Administrativo tiene acceso concedido a 1066 S.A.")

    # --------------------------------------------------------------------------
    # TEST 2: RESTRICCIÓN DE ELIMINACIÓN (UNLINK)
    # --------------------------------------------------------------------------
    print("\n[TEST 2] CONTROL DE ELIMINACIÓN (UNLINK EN VENTAS, COMPRAS, FACTURAS):")
    
    # 2.A: Operador intenta eliminar presupuesto de venta
    try:
        with env.cr.savepoint():
            so = env['sale.order'].sudo().create({
                'partner_id': partner_demo.id,
                'company_id': company_bg.id,
            })
            # Ejecutar unlink como operador
            so.with_user(u_operador).unlink()
            test(False, "Operador eliminó presupuesto de venta (FALLO: debió ser bloqueado)")
            raise RollbackTest()
    except UserError as e:
        test("no tiene permisos para eliminar" in str(e).lower() or "restringida" in str(e).lower(),
             f"Operador bloqueado al eliminar OV con UserError explicativo")
    except RollbackTest:
        pass

    # 2.B: Administrativo intenta eliminar requerimiento de compra
    try:
        with env.cr.savepoint():
            po = env['purchase.order'].sudo().create({
                'partner_id': partner_demo.id,
                'company_id': company_bg.id,
            })
            po.with_user(u_adm).unlink()
            test(False, "Administrativo eliminó requerimiento de compra (FALLO: debió ser bloqueado)")
            raise RollbackTest()
    except UserError as e:
        test("no tiene permisos para eliminar" in str(e).lower() or "restringida" in str(e).lower(),
             f"Administrativo bloqueado al eliminar OC con UserError explicativo")
    except RollbackTest:
        pass

    # 2.C: Resp. Administración SÍ puede eliminar (tiene group_atlas_can_unlink)
    try:
        with env.cr.savepoint():
            so_adm = env['sale.order'].sudo().create({
                'partner_id': partner_demo.id,
                'company_id': company_bg.id,
            })
            so_id = so_adm.id
            so_adm.with_user(u_resp_adm).unlink()
            remaining = env['sale.order'].sudo().search([('id', '=', so_id)])
            test(not remaining, "Resp. Administración eliminó presupuesto correctamente (Permitido)")
            raise RollbackTest()
    except RollbackTest:
        pass
    except Exception as e:
        test(False, f"Resp. Administración no pudo eliminar presupuesto: {e}")

    # --------------------------------------------------------------------------
    # TEST 3: REGLAS STUDIO DE APROBACIÓN
    # --------------------------------------------------------------------------
    print("\n[TEST 3] REGLAS DE APROBACIÓN STUDIO (VENTAS Y COMPRAS):")
    rule_so = Rules.search([('name', '=like', '%Orden de Venta%')], limit=1)
    rule_po = Rules.search([('name', '=like', '%Requerimiento de Compra%')], limit=1)

    if rule_so and u_operador and u_resp_op:
        with env.cr.savepoint():
            so = env['sale.order'].sudo().create({
                'partner_id': partner_demo.id,
                'company_id': company_bg.id,
            })
            appr_op = Rules.check_approval('sale.order', so.id, 'action_confirm', False)
            test(not appr_op.get('approved', False), "Orden de Venta: Exige aprobación ante intento de confirmación del Operador")
            test(rule_so.with_user(u_resp_op).can_validate, "Orden de Venta: Resp. Operaciones tiene permiso para aprobar")
            test(not rule_so.with_user(u_adm).can_validate, "Orden de Venta: Administrativo NO puede aprobar")

    if rule_po and u_resp_op and u_resp_adm:
        with env.cr.savepoint():
            po = env['purchase.order'].sudo().create({
                'partner_id': partner_demo.id,
                'company_id': company_bg.id,
            })
            test(not rule_po.with_user(u_resp_op).can_validate, "Requerimiento de Compra: Resp. Operaciones NO puede aprobar")
            test(rule_po.with_user(u_resp_adm).can_validate, "Requerimiento de Compra: Resp. Administración SÍ puede aprobar")

    # --------------------------------------------------------------------------
    # TEST 4: CARGA DE CONTACTOS Y PRODUCTOS
    # --------------------------------------------------------------------------
    print("\n[TEST 4] RESTRICCIÓN DE ALTA DE CONTACTOS Y PRODUCTOS:")
    
    # 4.A: Operador intenta dar de alta un contacto
    try:
        with env.cr.savepoint():
            env['res.partner'].with_user(u_operador).create({
                'name': 'Cliente Demo Prueba',
            })
            test(False, "Operador creó un contacto nuevo (FALLO: debió ser bloqueado)")
            raise RollbackTest()
    except UserError as e:
        test("no tiene permisos para dar de alta nuevos contactos" in str(e).lower(),
             "Operador bloqueado al crear nuevo contacto (UserError explicativo)")
    except RollbackTest:
        pass

    # 4.B: Operador intenta dar de alta un producto
    try:
        with env.cr.savepoint():
            env['product.template'].with_user(u_operador).create({
                'name': 'Producto Demo Prueba',
            })
            test(False, "Operador creó un producto nuevo (FALLO: debió ser bloqueado)")
            raise RollbackTest()
    except UserError as e:
        test("no tiene permisos para dar de alta nuevos productos" in str(e).lower(),
             "Operador bloqueado al crear nuevo producto (UserError explicativo)")
    except RollbackTest:
        pass

    # 4.C: Administrativo SÍ puede crear contacto y producto
    try:
        with env.cr.savepoint():
            p_test = env['res.partner'].with_user(u_adm).create({
                'name': 'Cliente Creado Por Adm',
            })
            test(bool(p_test.id), "Administrativo creó nuevo contacto exitosamente (Permitido)")
            raise RollbackTest()
    except RollbackTest:
        pass
    except Exception as e:
        test(False, f"Administrativo falló al crear contacto: {e}")

    print("\n" + "=" * 80)
    print(f"RESUMEN SMOKE TEST: {passed_tests}/{total_tests} PRUEBAS EXITOSAS")
    print("=" * 80)

finally:
    env.cr.rollback()
    print(">> ROLLBACK FINAL EJECUTADO: Base de datos intacta.")
