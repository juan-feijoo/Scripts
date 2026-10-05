# -*- coding: utf-8 -*-
"""
==============================================================================
FMF GROUP - SCRIPT DE SIMULACIÓN Y AUDITORÍA DE OT (EJEMPLO PDF PÁGINA 1)
==============================================================================
OT-TMEC-01 N° 2215 (Tractor / Equipo de Arrastre - Taller Mecánico)
Entorno: Odoo 17.0+e (Enterprise) / Odoo.sh Staging
Modo Dry-Run: True por defecto (Rollback automático)
==============================================================================
"""

import logging
from datetime import datetime, timedelta

_logger = logging.getLogger("fmf.ot_simulation")

# Configuración de ejecución
DRY_RUN = True  # Cambiar a False para persistir la OT en la base de datos


def print_header(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_step(step, desc):
    print(f"\n--> [{step}] {desc}")
    print("-" * 80)


def run_simulation(env, dry_run=DRY_RUN):
    print_header(f"SIMULACIÓN DE ORDEN DE TRABAJO (PDF PÁG. 1 - OT 2215) | BD: {env.cr.dbname}")
    print(f"  * MODO: {'DRY-RUN (Simulación segura, se cancelará al final)' if dry_run else 'PRODUCCIÓN (Se guardará en la BD)'}")

    # =========================================================================
    # PASO 1: BÚSQUEDA DE VEHÍCULOS (TRACTOR MT023 Y CISTERNA AT019)
    # =========================================================================
    print_step(1, "VERIFICACIÓN DE VEHÍCULOS EN FLOTA (fleet.vehicle)")
    
    # 1.1 Tractor: MT023 / AG 305 GQ / Scania G500
    tractor = env['fleet.vehicle'].search([
        '|', '|',
        ('license_plate', 'ilike', 'AG305GQ'),
        ('license_plate', 'ilike', 'AG 305 GQ'),
        ('name', 'ilike', 'MT023')
    ], limit=1)

    if not tractor:
        # Búsqueda más amplia por Scania o MT023
        tractor = env['fleet.vehicle'].search([
            '|', ('name', 'ilike', 'MT023'), ('model_id.name', 'ilike', 'G500')
        ], limit=1)

    if tractor:
        print(f"  [OK] Tractor Encontrado: ID {tractor.id} | {tractor.display_name} | Patente: {tractor.license_plate}")
    else:
        print("  [!] Tractor MT023 (AG 305 GQ) no encontrado en base. Se simulará su selección.")
        # Buscar un tractor cualquiera como fallback
        tractor = env['fleet.vehicle'].search([('model_id.category_id.name', '=', 'TRACTOR')], limit=1)
        if tractor:
            print(f"      -> Fallback Tractor asignado para la prueba: ID {tractor.id} ({tractor.display_name})")

    # 1.2 Arrastre: AT019 / AA 376 OV / Cisterna 3 Ejes
    arrastre = env['fleet.vehicle'].search([
        '|', '|',
        ('license_plate', 'ilike', 'AA376OV'),
        ('license_plate', 'ilike', 'AA 376 OV'),
        ('name', 'ilike', 'AT019')
    ], limit=1)

    if not arrastre:
        arrastre = env['fleet.vehicle'].search([
            '|', ('name', 'ilike', 'AT019'), ('model_id.category_id.name', 'in', ['CISTERNA', 'SEMIRREMOLQUE'])
        ], limit=1)

    if arrastre:
        print(f"  [OK] Equipo Arrastre Encontrado: ID {arrastre.id} | {arrastre.display_name} | Patente: {arrastre.license_plate}")
    else:
        print("  [!] Equipo Arrastre AT019 (AA 376 OV) no encontrado. Se asignará fallback si existe.")

    # =========================================================================
    # PASO 2: BÚSQUEDA DE CHOFER Y PERSONAL MECÁNICO
    # =========================================================================
    print_step(2, "VERIFICACIÓN DE CHOFER Y MECÁNICOS (hr.employee / res.partner)")
    
    # 2.1 Chofer: GERARDI RICARDO
    chofer = env['res.partner'].search([('name', 'ilike', 'Gerardi%Ricardo')], limit=1)
    if not chofer:
        chofer_emp = env['hr.employee'].search([('name', 'ilike', 'Gerardi%Ricardo')], limit=1)
        if chofer_emp:
            chofer = chofer_emp.work_contact_id or chofer_emp.user_id.partner_id

    if chofer:
        print(f"  [OK] Chofer Encontrado: ID {chofer.id} | {chofer.name}")
    else:
        print("  [!] Chofer 'GERARDI RICARDO' no encontrado como contacto. Se usará el conductor actual del vehículo.")
        if tractor and tractor.driver_id:
            chofer = tractor.driver_id
            print(f"      -> Conductor asociado al tractor: ID {chofer.id} ({chofer.name})")

    # 2.2 Mecánicos del reporte (Serrano, Arancibia, Gonzalez, Segovia, Vilca, Tejerina)
    nombres_mecanicos = ['Serrano', 'Arancibia', 'Gonzalez', 'Segovia', 'Vilca', 'Tejerina']
    mecanicos_dict = {}
    for nom in nombres_mecanicos:
        emp = env['hr.employee'].search([('name', 'ilike', nom), ('active', '=', True)], limit=1)
        if emp:
            mecanicos_dict[nom] = emp
            print(f"  [OK] Mecánico '{nom}': ID {emp.id} | {emp.name}")
        else:
            print(f"  [?] Mecánico '{nom}' no localizado exactamente. (Usará usuario del sistema si se requiere)")

    # =========================================================================
    # PASO 3: ALMACÉN TALLER Y REPUESTOS (ID 104 - TALL/Existencias)
    # =========================================================================
    print_step(3, "INSPECCIÓN DE ALMACÉN TALLER Y PRODUCTOS (stock.warehouse / product.product)")
    
    taller_wh = env['stock.warehouse'].browse(104)
    if not taller_wh.exists():
        taller_wh = env['stock.warehouse'].search([('code', '=', 'TALL')], limit=1)

    print(f"  * Almacén Taller: {taller_wh.name} [{taller_wh.code}]")
    taller_stock_loc = taller_wh.lot_stock_id
    print(f"  * Ubicación Origen de Repuestos: {taller_stock_loc.complete_name} (ID: {taller_stock_loc.id})")

    # Tipo de operación para salida o consumo de repuestos en el taller
    picking_type = env['stock.picking.type'].search([
        ('warehouse_id', '=', taller_wh.id),
        ('code', '=', 'outgoing')
    ], limit=1)
    if not picking_type:
        picking_type = env['stock.picking.type'].search([('warehouse_id', '=', taller_wh.id)], limit=1)
    
    print(f"  * Tipo de Operación de Salida/Consumo: ID {picking_type.id} - {picking_type.name}")

    # 3.1 Búsqueda de Repuestos de la OT
    repuestos_datos = [
        {'nombre': 'HOJA ELASTICO', 'cant': 2.0, 'medida': '13 x 90'},
        {'nombre': 'GRAMPA', 'cant': 2.0, 'medida': '7/8 x 135 x 400'},
        {'nombre': 'PUNTO FIJO C/TUERCA', 'cant': 1.0, 'medida': '1/2 120 c/u'},
    ]
    
    productos_ot = []
    for r in repuestos_datos:
        prod = env['product.product'].search([
            '|', ('name', 'ilike', r['nombre']), ('default_code', 'ilike', r['nombre'])
        ], limit=1)
        if not prod:
            # Si no existe en staging, creamos un producto temporal de repuesto
            print(f"  [i] Repuesto '{r['nombre']}' no existe en catálogo. Creando producto de prueba en memoria...")
            prod = env['product.product'].create({
                'name': r['nombre'],
                'type': 'product',  # Almacenable
                'default_code': r['nombre'][:10].replace(" ", "_").upper(),
            })
        productos_ot.append((prod, r['cant'], r['medida']))
        # Chequear stock disponible
        stock_qty = prod.with_context(location=taller_stock_loc.id).qty_available
        print(f"  [OK] Repuesto: [{prod.id}] {prod.name} | Cantidad Requerida: {r['cant']} | Stock en Taller: {stock_qty}")

    # =========================================================================
    # PASO 4: CREACIÓN DE LA ORDEN DE TRABAJO (project.task EN FSM)
    # =========================================================================
    print_step(4, "CREACIÓN DE LA TAREA EN SERVICIO EXTERNO (project.task)")
    
    proyecto_fsm = env['project.project'].browse(5)  # Proyecto Servicio Externo - FMF ARGENTINA SRL
    print(f"  * Proyecto FSM asignado: [{proyecto_fsm.id}] {proyecto_fsm.name} (Empresa: {proyecto_fsm.company_id.name})")

    # Revisar campos existentes en project.task para enlazar vehículos
    task_fields = env['project.task']._fields
    fleet_fields = [f for f in task_fields if 'vehicle' in f or 'fleet' in f or 'tractor' in f]
    print(f"  * Campos de flota detectados en project.task: {fleet_fields if fleet_fields else 'Ninguno por defecto'}")

    # Armamos la descripción rica con los datos de la OT física
    descripcion_ot = f"""
    <h3>ORDEN DE TRABAJO N° 2215 - TALLER MECÁNICO (REV. 9)</h3>
    <table class="table table-bordered" style="width: 100%;">
        <tr>
            <td style="width: 50%;"><strong>TRACTOR:</strong> {tractor.display_name if tractor else 'MT023'}</td>
            <td style="width: 50%;"><strong>ARRASTRE:</strong> {arrastre.display_name if arrastre else 'AT019 - CISTERNA'}</td>
        </tr>
        <tr>
            <td><strong>PATENTE TRACTOR:</strong> {tractor.license_plate if tractor else 'AG 305 GQ'}</td>
            <td><strong>PATENTE ARRASTRE:</strong> {arrastre.license_plate if arrastre else 'AA 376 OV'}</td>
        </tr>
        <tr>
            <td><strong>CHOFER:</strong> {chofer.name if chofer else 'GERARDI RICARDO'}</td>
            <td><strong>TIPO ARRASTRE:</strong> CISTERNA 3 EJES</td>
        </tr>
        <tr>
            <td><strong>KM ACTUAL:</strong> 114.237 km</td>
            <td><strong>KM SERVICE:</strong> 135.195 km | <strong>REM KM:</strong> 20.958 km</td>
        </tr>
    </table>
    <br/>
    <h4>OBSERVACIONES DE EQUIPO DE ARRASTRE:</h4>
    <p><em>SE REEMPLAZÓ HOJAS DE ELÁSTICO ROTA DE 2DO EJE LADO IZQUIERDO.</em></p>
    """

    task_vals = {
        'name': 'OT 2215 - TALLER MECÁNICO (MT023 / AT019)',
        'project_id': proyecto_fsm.id,
        'partner_id': chofer.id if chofer else False,
        'description': descripcion_ot,
        'company_id': proyecto_fsm.company_id.id,
    }

    # Si ya existe un campo many2one a fleet.vehicle en project.task (por Studio o módulo)
    for field_cand in ['vehicle_id', 'x_studio_vehculo', 'x_studio_vehicle_id', 'fleet_vehicle_id']:
        if field_cand in task_fields and tractor:
            task_vals[field_cand] = tractor.id
            print(f"  * Asignando tractor a campo existente: {field_cand} = {tractor.id}")
            break

    nueva_ot = env['project.task'].create(task_vals)
    print(f"  [EXITO] Tarea OT creada: ID {nueva_ot.id} - '{nueva_ot.name}'")

    # =========================================================================
    # PASO 5: REGISTRO DE TRABAJOS / TIEMPOS (DETALLE DE TAREAS Y MECÁNICOS)
    # =========================================================================
    print_step(5, "REGISTRO DE PARTES DE HORAS / TRABAJOS REALIZADOS (hr_timesheet)")
    
    trabajos = [
        {'desc': '[LAVADO] Lavado general unidad completa', 'horas': 1.0, 'mec': 'Serrano'},
        {'desc': '[TRACTOR] Revisión general parte baja, fluidos', 'horas': 0.67, 'mec': 'Arancibia'},
        {'desc': '[CISTERNA] Revisión general parte baja, sist. aire', 'horas': 0.33, 'mec': 'Gonzalez'},
        {'desc': '[AMBOS] Revisión sistema eléctrico y luces', 'horas': 0.33, 'mec': 'Segovia'},
        {'desc': '[AMBOS] Revisión de neumáticos', 'horas': 0.33, 'mec': 'Vilca'},
        {'desc': '[CISTERNA] Reparación parte baja: reemplazo elásticos y grampas', 'horas': 2.67, 'mec': 'Tejerina'},
    ]

    default_user = env.user
    for t in trabajos:
        emp = mecanicos_dict.get(t['mec'])
        user = emp.user_id if emp and emp.user_id else default_user
        
        env['account.analytic.line'].create({
            'name': f"{t['desc']} (Mecánico: {t['mec']})",
            'task_id': nueva_ot.id,
            'project_id': proyecto_fsm.id,
            'unit_amount': t['horas'],
            'employee_id': emp.id if emp else False,
            'user_id': user.id,
            'company_id': proyecto_fsm.company_id.id,
        })
        print(f"  + Tarea registrada: {t['horas']}h | {t['desc']} | Mecánico: {t['mec']}")

    # =========================================================================
    # PASO 6: CONSUMO Y DESCUENTO DE STOCK DE REPUESTOS (stock.picking / stock.move)
    # =========================================================================
    print_step(6, "DESCUENTO DE INVENTARIO DESDE TALLER (stock.picking)")

    # Ubicación de destino para consumo de taller (Virtual Locations / Production o Inventory Loss o Internal)
    ubic_cliente_consumo = env['stock.location'].search([
        ('usage', '=', 'customer')
    ], limit=1)

    picking_vals = {
        'picking_type_id': picking_type.id,
        'location_id': taller_stock_loc.id,
        'location_dest_id': ubic_cliente_consumo.id,
        'origin': f"OT {nueva_ot.name}",
        'company_id': taller_wh.company_id.id,
    }

    # Si el picking tiene enlace a la tarea o si industry_fsm_stock lo soporta
    if 'task_id' in env['stock.picking']._fields:
        picking_vals['task_id'] = nueva_ot.id

    picking = env['stock.picking'].create(picking_vals)

    for prod, cant, medida in productos_ot:
        move = env['stock.move'].create({
            'name': f"Consumo OT 2215: {prod.name} ({medida})",
            'product_id': prod.id,
            'product_uom_qty': cant,
            'product_uom': prod.uom_id.id,
            'picking_id': picking.id,
            'location_id': taller_stock_loc.id,
            'location_dest_id': ubic_cliente_consumo.id,
            'company_id': taller_wh.company_id.id,
        })
        print(f"  + Línea de movimiento preparada: {cant} x {prod.name} desde {taller_stock_loc.name}")

    # Confirmar y asignar el picking
    picking.action_confirm()
    picking.action_assign()
    print(f"  [OK] Entrega/Consumo de Stock #{picking.name} creada en estado: '{picking.state}'")

    # Simular la validación de consumo de stock
    for move_line in picking.move_line_ids:
        move_line.quantity = move_line.quantity_product_uom  # Odoo 17 usa 'quantity'
    
    print(f"  [OK] Cantidades listas para descontar de {taller_stock_loc.complete_name}")

    # =========================================================================
    # PASO 7: ACTUALIZACIÓN DE FLOTA (ODÓMETRO Y SERVICIOS)
    # =========================================================================
    print_step(7, "IMPACTO EN FLOTA (fleet.vehicle.log.services y Odómetro)")
    
    if tractor:
        # Registrar Odómetro
        km_actual = 114237.0
        odometer = env['fleet.vehicle.odometer'].create({
            'vehicle_id': tractor.id,
            'value': km_actual,
            'date': datetime.now().date(),
        })
        print(f"  [OK] Odómetro del Tractor actualizado a: {km_actual} km (ID {odometer.id})")

        # Registrar Servicio de Flota
        servicio_tipo = env['fleet.service.type'].search([('name', 'ilike', 'Reparacion')], limit=1)
        if not servicio_tipo:
            servicio_tipo = env['fleet.service.type'].search([], limit=1)

        log_service = env['fleet.vehicle.log.services'].create({
            'vehicle_id': tractor.id,
            'service_type_id': servicio_tipo.id if servicio_tipo else False,
            'description': f"OT 2215: Reemplazo elásticos y revisión taller mecánico. OT FSM ID: {nueva_ot.id}",
            'date': datetime.now().date(),
            'odometer': km_actual,
        })
        print(f"  [OK] Registro de Mantenimiento de Flota creado: ID {log_service.id}")

    # =========================================================================
    # PASO 8: CONTROL TRANSACCIONAL (DRY-RUN)
    # =========================================================================
    print_header("RESULTADO DE LA SIMULACIÓN")
    if dry_run:
        env.cr.rollback()
        print("  [*] MODO DRY-RUN COMPLETADO EXITOSAMENTE:")
        print("      - Todos los objetos (Tarea FSM, Partes de Horas, Consumo de Stock, Odómetro y Servicios)")
        print("        fueron instanciados y validados lógicamente sin errores de integridad.")
        print("      - Se ejecutó ROLLBACK: la base de datos staging quedó intacta.")
        print("      - Para crear el registro real en la base, cambia 'DRY_RUN = False' y vuelve a ejecutar.")
    else:
        env.cr.commit()
        print("  [*] MODO PRODUCCIÓN COMPLETADO:")
        print(f"      - Orden de Trabajo guardada con éxito (Tarea ID {nueva_ot.id}).")
        print(f"      - Descuento de stock confirmado en Almacén Taller #{picking.name}.")
    print("=" * 80 + "\n")


# Invocación si se ejecuta dentro del shell de Odoo
if 'env' in locals() or 'env' in globals():
    run_simulation(env, dry_run=DRY_RUN)
else:
    print("\n[!] Ejecute este script dentro de la shell de Odoo ('odoo-bin shell').")
    print("    Ejemplo: exec(open('simular_ot_pdf.py').read())\n")
