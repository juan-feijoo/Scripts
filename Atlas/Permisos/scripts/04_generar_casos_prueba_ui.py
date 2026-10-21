# ==============================================================================
# SCRIPT 04: GENERACIÓN DE CASOS DE PRUEBA VISUALES PARA UI (Persistidos en BD)
# Odoo 18.0+e en Odoo.sh (Atlas Group - Staging)
# ==============================================================================
# Este script crea registros reales y actividades en el chatter para que puedas
# iniciar sesión desde la interfaz web (UI) y validar visualmente los flujos.
#
# Ejecutar en odoo-bin shell:
# python / scripts / pegar bloque completo.

import sys
import traceback

try:
    from markupsafe import Markup
except ImportError:
    Markup = lambda s: s

EXPECTED_DB = 'outsource-argentina-atlas-group1-staging-40016719'

# ¿Setear contraseña temporal para poder ingresar por UI en modo incógnito?
SET_PASSWORDS = True
TEST_PASSWORD = '12345'  # Contraseña uniforme para pruebas en staging

try:
    import odoo
    print("=" * 80)
    print(f"GENERADOR DE CASOS DE PRUEBA VISUALES - DB: {env.cr.dbname}")
    print("=" * 80)

    if env.cr.dbname != EXPECTED_DB and 'atlas' not in env.cr.dbname.lower():
        raise Exception(f"Base de datos no autorizada: {env.cr.dbname}")

    Users = env['res.users'].with_context(active_test=False)
    Rules = env['studio.approval.rule']

    u_operador = Users.search([('login', '=', 'mandatario@atlasgroup.com.ar')], limit=1)
    u_resp_op = Users.search([('login', '=', 'hernanpacetti@atlasgroup.com.ar')], limit=1)
    u_adm = Users.search([('login', '=', 'administracion@atlasgroup.com.ar')], limit=1)
    u_resp_adm = Users.search([('login', '=', 'eugeniazanotti@atlasgroup.com.ar')], limit=1)
    u_resp_gen = Users.search([('login', '=', 'hernanfernandez@atlasgroup.com.ar')], limit=1)

    for name, u in [('Operador', u_operador), ('Resp. Op', u_resp_op), ('Admin', u_adm), ('Resp. Adm', u_resp_adm), ('Resp. Gen', u_resp_gen)]:
        if not u:
            raise Exception(f"Usuario {name} no encontrado. Ejecutar primero el Script 02 con commit.")

    company_bg = env['res.company'].search([('name', 'ilike', 'BULGHERONI')], limit=1)
    company_1066 = env['res.company'].search([('name', 'ilike', '1066')], limit=1)

    # --------------------------------------------------------------------------
    # 1. CONTRASEÑAS DE ACCESO PARA PRUEBAS EN UI (MODO INCÓGNITO)
    # --------------------------------------------------------------------------
    if SET_PASSWORDS:
        print("\n[1] CONFIGURANDO CONTRASEÑAS DE PRUEBA EN STAGING:")
        users_to_pwd = [u_operador, u_resp_op, u_adm, u_resp_adm, u_resp_gen]
        for u in users_to_pwd:
            u.sudo().write({'password': TEST_PASSWORD})
            print(f"  ✔ {u.login:<35} → Clave: {TEST_PASSWORD}")

    # --------------------------------------------------------------------------
    # 2. CONTACTO Y PRODUCTO DEMO
    # --------------------------------------------------------------------------
    print("\n[2] VERIFICANDO PARTNERS Y PRODUCTOS DEMO:")
    Partner = env['res.partner'].sudo()
    Product = env['product.product'].sudo()

    partner_cliente = Partner.search([('name', '=', '[ATLAS DEMO] Cliente Corporativo S.A.')], limit=1)
    if not partner_cliente:
        partner_cliente = Partner.create({
            'name': '[ATLAS DEMO] Cliente Corporativo S.A.',
            'company_id': company_bg.id,
            'customer_rank': 1,
            'street': 'Av. Libertador 1000',
            'city': 'Buenos Aires',
        })
        print(f"  ✔ Cliente Demo Creado: {partner_cliente.name} (ID {partner_cliente.id})")
    else:
        print(f"  ✔ Cliente Demo Existente: {partner_cliente.name}")

    partner_proveedor = Partner.search([('name', '=', '[ATLAS DEMO] Proveedor de Servicios SRL')], limit=1)
    if not partner_proveedor:
        partner_proveedor = Partner.create({
            'name': '[ATLAS DEMO] Proveedor de Servicios SRL',
            'company_id': company_bg.id,
            'supplier_rank': 1,
            'street': 'Av. Corrientes 2500',
            'city': 'Buenos Aires',
        })
        print(f"  ✔ Proveedor Demo Creado: {partner_proveedor.name} (ID {partner_proveedor.id})")
    else:
        print(f"  ✔ Proveedor Demo Existente: {partner_proveedor.name}")

    prod = Product.search([('sale_ok', '=', True), ('purchase_ok', '=', True)], limit=1)
    if not prod:
        prod = Product.search([], limit=1)
    print(f"  ✔ Producto Utilizado: {prod.display_name} (ID {prod.id})")

    # --------------------------------------------------------------------------
    # 3. CASO VISUAL A: ORDEN DE VENTA CON APROBACIÓN SOLICITADA
    # --------------------------------------------------------------------------
    print("\n[3] CASO VISUAL A: ORDEN DE VENTA CON APROBACIÓN REQUERIDA (CHATTER)")
    so_exist = env['sale.order'].sudo().search([('client_order_ref', '=', 'DEMO-APROB-OV')], limit=1)
    if so_exist:
        so_exist.unlink()

    so_demo = env['sale.order'].sudo().create({
        'partner_id': partner_cliente.id,
        'user_id': u_operador.id,
        'company_id': company_bg.id,
        'client_order_ref': 'DEMO-APROB-OV',
        'note': 'CASO DEMO VISUAL: Creada por Operador. Requiere aprobación de Resp. Operaciones, Resp. Administración o Resp. General.',
        'order_line': [(0, 0, {
            'product_id': prod.id,
            'name': 'Servicio Operativo Integral - Prueba Visual Aprobaciones',
            'product_uom_qty': 1,
            'price_unit': 250000.0,
        })],
    })
    # Disparar chequeo de aprobación para que Studio genere las actividades en el chatter
    Rules.check_approval('sale.order', so_demo.id, 'action_confirm', False)
    so_demo.message_post(
        body=Markup("<b>[ATLAS - DEMO]</b> Presupuesto creado por Operador (mandatario@). Se solicitó aprobación formal para confirmar la venta."),
        message_type='comment',
        subtype_xmlid='mail.mt_comment'
    )
    activities_so = env['mail.activity'].search([('res_model', '=', 'sale.order'), ('res_id', '=', so_demo.id)])
    print(f"  ✔ Presupuesto {so_demo.name} creado | Estado: '{so_demo.state}' (en UI: 'Presupuesto') | Total: ${so_demo.amount_total:,.2f}")
    print(f"  ✔ Actividades agendadas en chatter para: {activities_so.mapped('user_id.name')}")

    # --------------------------------------------------------------------------
    # 4. CASO VISUAL B: REQUERIMIENTO DE COMPRA CON APROBACIÓN SOLICITADA
    # --------------------------------------------------------------------------
    print("\n[4] CASO VISUAL B: REQUERIMIENTO DE COMPRA CON APROBACIÓN REQUERIDA")
    po_exist = env['purchase.order'].sudo().search([('partner_ref', '=', 'DEMO-APROB-OC')], limit=1)
    if po_exist:
        po_exist.unlink()

    po_demo = env['purchase.order'].sudo().create({
        'partner_id': partner_proveedor.id,
        'user_id': u_operador.id,
        'company_id': company_bg.id,
        'partner_ref': 'DEMO-APROB-OC',
        'notes': 'CASO DEMO VISUAL: Solicitud de Presupuesto para Gastos de Terceros. Requiere aprobación de Resp. Administración o Resp. General.',
        'order_line': [(0, 0, {
            'product_id': prod.id,
            'name': 'Gasto Operativo Terceros - Prueba Visual Aprobación Compras',
            'product_qty': 1,
            'price_unit': 120000.0,
        })],
    })
    # Disparar chequeo de aprobación de compra
    Rules.check_approval('purchase.order', po_demo.id, 'button_confirm', False)
    po_demo.message_post(
        body=Markup("<b>[ATLAS - DEMO]</b> Requerimiento de compra creado. Aprobación pendiente asignada a Eugenia Zanotti y Hernán Fernández."),
        message_type='comment',
        subtype_xmlid='mail.mt_comment'
    )
    activities_po = env['mail.activity'].search([('res_model', '=', 'purchase.order'), ('res_id', '=', po_demo.id)])
    print(f"  ✔ Solicitud de Compra {po_demo.name} creada | Estado: '{po_demo.state}' (en UI: 'Solicitud de Presupuesto') | Total: ${po_demo.amount_total:,.2f}")
    print(f"  ✔ Actividades agendadas en chatter para: {activities_po.mapped('user_id.name')}")

    # --------------------------------------------------------------------------
    # 5. CASO VISUAL C: DOCUMENTOS PARA PRUEBA DE BLOQUEO DE SUPRIMIR (UNLINK)
    # --------------------------------------------------------------------------
    print("\n[5] CASO VISUAL C: DOCUMENTOS BORRADOR PARA TESTEAR BOTÓN 'SUPRIMIR'")
    so_del_exist = env['sale.order'].sudo().search([('client_order_ref', '=', 'TEST-BORRADO-OV')], limit=1)
    if so_del_exist:
        so_del_exist.unlink()

    so_test_borrado = env['sale.order'].sudo().create({
        'partner_id': partner_cliente.id,
        'user_id': u_operador.id,
        'company_id': company_bg.id,
        'client_order_ref': 'TEST-BORRADO-OV',
        'note': 'PRUEBA DE ELIMINACIÓN: Intentar eliminar (Acción -> Suprimir) con Operador o Administrativo. Debe salir UserError de bloqueo.',
        'order_line': [(0, 0, {
            'product_id': prod.id,
            'name': 'Item Test Eliminación',
            'product_uom_qty': 1,
            'price_unit': 50000.0,
        })],
    })
    print(f"  ✔ Presupuesto de prueba de borrado: {so_test_borrado.name}")

    po_del_exist = env['purchase.order'].sudo().search([('partner_ref', '=', 'TEST-BORRADO-OC')], limit=1)
    if po_del_exist:
        po_del_exist.unlink()

    po_test_borrado = env['purchase.order'].sudo().create({
        'partner_id': partner_proveedor.id,
        'user_id': u_adm.id,
        'company_id': company_bg.id,
        'partner_ref': 'TEST-BORRADO-OC',
        'notes': 'PRUEBA DE ELIMINACIÓN: Intentar eliminar (Acción -> Suprimir) con Administrativo o Resp. Operaciones. Debe salir UserError de bloqueo.',
        'order_line': [(0, 0, {
            'product_id': prod.id,
            'name': 'Item Test Eliminación Compras',
            'product_qty': 1,
            'price_unit': 40000.0,
        })],
    })
    print(f"  ✔ Solicitud de Compra prueba de borrado: {po_test_borrado.name}")

    env.flush_all()
    env.cr.commit()

    print("\n" + "=" * 80)
    print(">> COMMIT EXITOSO: CASOS DE PRUEBA GUARDADOS EN LA BASE DE DATOS")
    print("=" * 80)
    print("\nCREDENCIALES PARA PRUEBAS EN MODO INCÓGNITO:")
    print(f"  Contraseña común para todos: {TEST_PASSWORD}")
    print("  1. Operador:             mandatario@atlasgroup.com.ar")
    print("  2. Resp. Operaciones:    hernanpacetti@atlasgroup.com.ar")
    print("  3. Administrativo:       administracion@atlasgroup.com.ar")
    print("  4. Resp. Administración: eugeniazanotti@atlasgroup.com.ar")
    print("  5. Resp. General:        hernanfernandez@atlasgroup.com.ar")
    print("\nDOCUMENTOS PARA PROBAR EN UI:")
    print(f"  - OV Pendiente Aprobación:   {so_demo.name} (Ver actividades de Hernan Pacetti)")
    print(f"  - OC Pendiente Aprobación:   {po_demo.name} (Ver actividades de Eugenia Zanotti)")
    print(f"  - OV para probar Suprimir:   {so_test_borrado.name} (Probar con mandatario@ o administracion@)")
    print(f"  - OC para probar Suprimir:   {po_test_borrado.name} (Probar con administracion@)")
    print("\n💡 TIPS PARA ENCONTRARLOS EN LA INTERFAZ:")
    print("  1. En Ventas el estado borrador se llama 'Presupuesto' (en Compras: 'Solicitud de Presupuesto').")
    print("  2. Si entrás con otro usuario (ej. Admin o Hernán), quitá la cruz ✖ del filtro 'Mis presupuestos'")
    print("     en la barra de búsqueda superior para ver las cotizaciones creadas por el Operador.")
    print("  3. Asegurate de tener seleccionada 'BULGHERONI GROUP S.A.' en el selector de empresas arriba a la derecha.")
    print("=" * 80)

except Exception:
    traceback.print_exc(file=sys.stdout)
    env.cr.rollback()
    print("\n>> ERROR → ROLLBACK")
