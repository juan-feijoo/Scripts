# -*- coding: utf-8 -*-
"""
==============================================================================
FMF GROUP - SCRIPT DE AUDITORÍA: FLOTA, SERVICIO EXTERNO (FSM) E INVENTARIO
==============================================================================
Entorno: Odoo 17.0+e (Enterprise) / Odoo.sh
Uso en Odoo Shell:
    $ odoo-bin shell -c /home/odoo/run/odoo.conf -d <nombre_bd>
    >>> exec(open('audit_fsm_flota.py').read())
    O invocar directamente:
    >>> run_audit(env, dry_run=True)
==============================================================================
"""

import logging
import sys

_logger = logging.getLogger("fmf.audit")

# Configuración por defecto: Modo seguro (dry-run)
DRY_RUN_DEFAULT = True


def print_title(text):
    print("\n" + "=" * 75)
    print(f"  {text}")
    print("=" * 75)


def print_section(num, title):
    print(f"\n[{num}] {title}")
    print("-" * 75)


def run_audit(env, dry_run=DRY_RUN_DEFAULT):
    """
    Ejecuta el relevamiento completo de configuración para la Orden de Trabajo
    de Taller Mecánico FMF sobre Odoo 17 Enterprise.
    """
    print_title(f"AUDITORÍA FMF - BASE DE DATOS: {env.cr.dbname} | MODO DRY-RUN: {dry_run}")

    # -------------------------------------------------------------------------
    # 1. ESTADO DE MÓDULOS DEL CIRCUITO
    # -------------------------------------------------------------------------
    print_section(1, "ESTADO DE MÓDULOS REQUERIDOS")
    required_modules = [
        ('fleet', 'Flota (Gestión de Vehículos)'),
        ('industry_fsm', 'Servicio Externo / Field Service'),
        ('industry_fsm_stock', 'Consumo de Materiales/Stock en FSM'),
        ('industry_fsm_report', 'Reportes y Hojas de Trabajo FSM'),
        ('stock', 'Inventario'),
        ('hr_timesheet', 'Partes de Horas / Tiempos'),
        ('repair', 'Reparaciones (Módulo Odoo 17)'),
    ]

    installed_records = env['ir.module.module'].search([
        ('name', 'in', [m[0] for m in required_modules])
    ])
    status_map = {m.name: m.state for m in installed_records}

    for mod_name, mod_desc in required_modules:
        state = status_map.get(mod_name, 'uninstalled')
        if state == 'installed':
            flag = "[ INSTALADO ]"
        elif state == 'to install':
            flag = "[ POR INSTALAR ]"
        else:
            flag = "[ PENDIENTE ]"
        print(f"  {flag:<16} {mod_name:<22} ({mod_desc}) -> Estado: {state}")

    # -------------------------------------------------------------------------
    # 2. RELEVAMIENTO DE FLOTA (TRACTORES Y ARRASTRES)
    # -------------------------------------------------------------------------
    print_section(2, "RELEVAMIENTO DE FLOTA (fleet.vehicle)")
    total_vehicles = env['fleet.vehicle'].search_count([])
    active_vehicles = env['fleet.vehicle'].search_count([('active', '=', True)])
    print(f"  * Total de vehículos registrados: {total_vehicles} (Activos: {active_vehicles})")

    # Muestra de modelos y categorías
    models = env['fleet.vehicle.model'].search([], limit=10)
    print(f"  * Modelos configurados en flota ({len(models)} detectados):")
    for m in models:
        brand = m.brand_id.name if m.brand_id else "Sin Marca"
        category = m.category_id.name if hasattr(m, 'category_id') and m.category_id else "Sin Categoría"
        print(f"    - [{m.id}] {m.name} | Marca: {brand} | Categoría: {category}")

    # Verificar si existen categorías para discriminar Tractor de Arrastre
    if hasattr(env['fleet.vehicle.model'], 'category_id'):
        categories = env['fleet.vehicle.model.category'].search([])
        print(f"  * Categorías de vehículos disponibles:")
        if categories:
            for cat in categories:
                count = env['fleet.vehicle'].search_count([('model_id.category_id', '=', cat.id)])
                print(f"    - Cat: '{cat.name}' (Vehículos asociados: {count})")
        else:
            print("    [!] No hay categorías de vehículos definidas.")

    # -------------------------------------------------------------------------
    # 3. ALMACENES, UBICACIONES Y STOCK DE TALLER
    # -------------------------------------------------------------------------
    print_section(3, "INVENTARIO: ALMACENES Y UBICACIONES DE TALLER")
    warehouses = env['stock.warehouse'].search([])
    print(f"  * Almacenes activos ({len(warehouses)}):")
    for wh in warehouses:
        print(f"    - {wh.name} [{wh.code}] -> Ubic. Stock: {wh.lot_stock_id.complete_name} (ID: {wh.lot_stock_id.id})")

    # Buscar ubicaciones candidatas para taller o repuestos
    taller_locs = env['stock.location'].search([
        ('usage', '=', 'internal'),
        '|', '|',
        ('name', 'ilike', 'taller'),
        ('name', 'ilike', 'repuesto'),
        ('complete_name', 'ilike', 'mecanic')
    ])
    if taller_locs:
        print(f"  * Ubicaciones internas identificadas para Taller / Repuestos:")
        for loc in taller_locs:
            print(f"    - {loc.complete_name} (ID: {loc.id})")
    else:
        print("    [!] AVISO: No se detectó una ubicación interna nombrada 'Taller' o 'Repuestos'.")
        print("        Se recomienda crear una ubicación dedicada (ej: TM/Stock) para aislar el consumo.")

    # Tipos de Operación (Pickings)
    picking_types = env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=5)
    print(f"  * Tipos de operación de salida / consumo disponibles:")
    for pt in picking_types:
        print(f"    - [{pt.id}] {pt.name} (Almacén: {pt.warehouse_id.name if pt.warehouse_id else 'General'})")

    # -------------------------------------------------------------------------
    # 4. CONFIGURACIÓN DE SERVICIO EXTERNO (industry_fsm)
    # -------------------------------------------------------------------------
    print_section(4, "SERVICIO EXTERNO (FSM) - PROYECTOS Y AJUSTES")
    fsm_projects = env['project.project'].search([('is_fsm', '=', True)])
    if fsm_projects:
        print(f"  * Proyectos FSM activos ({len(fsm_projects)}):")
        for p in fsm_projects:
            print(f"    - [{p.id}] {p.name} (Empresa: {p.company_id.name})")
            if hasattr(p, 'allow_worksheets'):
                print(f"      Hojas de trabajo habilitadas: {p.allow_worksheets}")
            if hasattr(p, 'allow_material'):
                print(f"      Consumo de materiales habilitado: {p.allow_material}")
    else:
        print("  [!] No se encontraron proyectos con flag is_fsm=True.")
        print("      Al instalar industry_fsm se genera el proyecto base 'Field Service'.")

    # -------------------------------------------------------------------------
    # 5. PERSONAL / MECÁNICOS Y TIEMPOS (hr.employee / res.users)
    # -------------------------------------------------------------------------
    print_section(5, "PERSONAL DE TALLER / MECÁNICOS")
    mechanics = env['hr.employee'].search([('active', '=', True)], limit=10)
    print(f"  * Empleados activos en sistema ({env['hr.employee'].search_count([('active', '=', True)])}):")
    for emp in mechanics:
        job = emp.job_id.name if emp.job_id else "Sin Puesto"
        dept = emp.department_id.name if emp.department_id else "Sin Depto"
        print(f"    - [{emp.id}] {emp.name} | Puesto: {job} | Depto: {dept}")

    # -------------------------------------------------------------------------
    # 6. CIERRE TRANSACCIONAL (DRY-RUN / COMMIT)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 75)
    if dry_run:
        env.cr.rollback()
        print("  [*] MODO DRY-RUN: Se ejecutó ROLLBACK de la transacción. Sin alteraciones.")
    else:
        env.cr.commit()
        print("  [*] MODO PRODUCCIÓN: Se ejecutó COMMIT de los cambios.")
    print("=" * 75 + "\n")


# Bloque de ejecución si se corre directamente en shell interactivo
if 'env' in locals() or 'env' in globals():
    run_audit(env, dry_run=DRY_RUN_DEFAULT)
else:
    print("\n[!] Este script debe ejecutarse dentro de la shell de Odoo ('odoo-bin shell').")
    print("    Ejemplo: exec(open('audit_fsm_flota.py').read())\n")
