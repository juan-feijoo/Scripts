# -*- coding: utf-8 -*-
"""
================================================================================
PASO 3: SELECTOR DE LISTA DE PRECIOS POR LÍNEA DE VENTA (sale.order.line)
Carpeta: v2_listas_y_desglose
Compatible con: Odoo 17.0+e, 18.0+e y 19.0+e Enterprise (Sin attrs ni states)
================================================================================

OBJETIVO:
Permitir que en un mismo Pedido de Venta / Cotización, el vendedor pueda elegir
para cada renglón qué lista de precios aplicar:
  - Renglón 1: Lista 'Mayorista (ARS)'
  - Renglón 2: Lista 'Público (ARS)'
  - Renglón 3: Lista 'Desglose - Venta por Unidad (ARS)'

QUÉ HACE ESTE SCRIPT:
1. Crea el campo 'x_pricelist_id' (Many2one a 'product.pricelist') en 'sale.order.line'.
2. Crea una vista heredada sobre 'sale.view_order_form' que muestra la columna
   'Lista de Precio' en las líneas del pedido (cumpliendo la sintaxis de Odoo 17/18/19).
3. Configura el cálculo automático del precio unitario ('price_unit') cuando se
   cambia la lista de precios de la línea.
"""

from datetime import datetime

DRY_RUN = True  # True: Simulación (ROLLBACK) | False: Aplicar cambios (COMMIT)

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def configurar_lista_por_linea(env):
    log("=" * 80)
    log("CONFIGURANDO SELECTOR DE LISTA DE PRECIOS POR RENGLÓN EN PEDIDOS DE VENTA")
    log(f"Modo: {'*** DRY-RUN (SIMULACIÓN - ROLLBACK) ***' if DRY_RUN else '*** PRODUCCIÓN (COMMIT) ***'}")
    log("=" * 80)

    try:
        env.cr.rollback()
    except:
        pass

    IrModel = env['ir.model']
    IrModelFields = env['ir.model.fields']
    IrUiView = env['ir.ui.view']

    sale_line_model = IrModel.search([('model', '=', 'sale.order.line')], limit=1)
    if not sale_line_model:
        log("ERROR: No está instalado el módulo de Ventas ('sale').")
        return

    # 1. Crear campo x_pricelist_id en sale.order.line
    field_name = 'x_pricelist_id'
    campo = IrModelFields.search([
        ('model_id', '=', sale_line_model.id),
        ('name', '=', field_name)
    ], limit=1)

    if not campo:
        campo = IrModelFields.create({
            'model_id': sale_line_model.id,
            'name': field_name,
            'field_description': 'Lista de Precio (Línea)',
            'ttype': 'many2one',
            'relation': 'product.pricelist',
            'store': True,
            'copied': True,
        })
        log(f"  + Campo '{field_name}' creado en 'sale.order.line' (ID: {campo.id}).")
    else:
        log(f"  -> Campo '{field_name}' ya existe en 'sale.order.line' (ID: {campo.id}).")

    # 2. Crear vista heredada para mostrar la columna en las líneas del pedido (Odoo 17/18/19)
    view_name = "kiddie.sale.order.form.pricelist.per.line"
    parent_view = env.ref('sale.view_order_form', raise_if_not_found=False)
    if parent_view:
        vista = IrUiView.search([('name', '=', view_name)], limit=1)
        arch_xml = """<data>
            <xpath expr="//field[@name='order_line']//list//field[@name='product_uom_qty']" position="after">
                <field name="x_pricelist_id" optional="show" options="{'no_create': True}"/>
            </xpath>
        </data>"""
        # Fallback por si la versión usa <tree> en lugar de <list> (Odoo 17 usa tree, Odoo 18/19 usa list)
        if '<tree' in (parent_view.arch_db or ''):
            arch_xml = """<data>
                <xpath expr="//field[@name='order_line']//tree//field[@name='product_uom_qty']" position="after">
                    <field name="x_pricelist_id" optional="show" options="{'no_create': True}"/>
                </xpath>
            </data>"""

        if not vista:
            vista = IrUiView.create({
                'name': view_name,
                'type': 'form',
                'model': 'sale.order',
                'inherit_id': parent_view.id,
                'arch_base': arch_xml,
                'active': True
            })
            log(f"  + Vista heredada '{view_name}' creada exitosamente (ID: {vista.id}).")
        else:
            vista.write({'arch_base': arch_xml, 'active': True})
            log(f"  -> Vista heredada '{view_name}' actualizada (ID: {vista.id}).")

    # 3. Crear Acción de Servidor / Automatización para recalcular price_unit según x_pricelist_id
    IrActionsServer = env['ir.actions.server']
    codigo_python = """
for line in records:
    plist = line.x_pricelist_id or line.order_id.pricelist_id
    if plist and line.product_id:
        nuevo_precio = plist._get_product_price(
            product=line.product_id,
            quantity=line.product_uom_qty or 1.0,
            uom=line.product_uom,
            date=line.order_id.date_order or datetime.date.today()
        )
        if nuevo_precio is not False:
            line['price_unit'] = nuevo_precio
"""
    server_action_name = "Kiddie: Recalcular Precio por Lista de Línea"
    srv_action = IrActionsServer.search([
        ('name', '=', server_action_name),
        ('model_id', '=', sale_line_model.id)
    ], limit=1)

    if not srv_action:
        srv_action = IrActionsServer.create({
            'name': server_action_name,
            'model_id': sale_line_model.id,
            'state': 'code',
            'code': codigo_python.strip()
        })
        log(f"  + Acción de servidor creada (ID: {srv_action.id}).")
    else:
        srv_action.write({'code': codigo_python.strip()})
        log(f"  -> Acción de servidor actualizada (ID: {srv_action.id}).")

    if DRY_RUN:
        env.cr.rollback()
        log("\n>>> MODO DRY-RUN: Transacción REVERTIDA (ROLLBACK). <<<")
    else:
        env.cr.commit()
        log("\n>>> MODO PRODUCCIÓN: Configuración CONFIRMADA (COMMIT). <<<")

if 'env' in locals():
    configurar_lista_por_linea(env)
else:
    print("[INFO] Ejecutar en Odoo Shell: python3 odoo-bin shell -d <bd> < v2_listas_y_desglose/03_configurar_lista_por_linea_venta_shell.py")

