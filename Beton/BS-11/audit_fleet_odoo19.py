# -*- coding: utf-8 -*-
# ==============================================================================
# SCRIPT DE AUDITORÍA Y DIAGNÓSTICO: FLOTA Y MANTENIMIENTO - ODOO 19.0+e / 18.0+e
# Entorno: Odoo.sh / Standalone Shell (odoo-bin shell)
# Modo: Solo Lectura (Read-Only) / Transacción protegida
# ==============================================================================
"""
Instrucciones de ejecución en Odoo.sh:
1. Subir al servidor o ejecutar vía CLI interactiva:
   python3 odoo-bin shell -d $ODOO_STAGE --no-http < audit_fleet_odoo19.py

2. O desde la consola interactiva de Odoo Shell:
   exec(open('audit_fleet_odoo19.py').read())
"""

import sys
import logging
import odoo
from odoo import release

_logger = logging.getLogger("fleet_audit")

# Configuración de seguridad: Solo lectura estricto
DRY_RUN = True


def print_title(text):
    print("\n" + "=" * 80)
    print(f" {text}")
    print("=" * 80)


def print_subtitle(text):
    print(f"\n--- {text} ---")


def run_fleet_audit(odoo_env):
    print_title("INICIANDO AUDITORÍA TÉCNICA DE MODELOS (ODOO 19+e / ENTERPRISE)")
    print(f"[*] Base de Datos: {odoo_env.cr.dbname}")
    print(f"[*] Versión Odoo: {release.version} ({release.version_info})")
    print(f"[*] Usuario: {odoo_env.user.name} (ID: {odoo_env.user.id})")
    print(f"[*] Modo: {'SOLO LECTURA (AUDITORÍA PURA)' if DRY_RUN else 'MODO ESCRITURA'}")

    # --------------------------------------------------------------------------
    # 1. ESTADO DE MÓDULOS INSTALADOS
    # --------------------------------------------------------------------------
    print_title("1. VERIFICACIÓN DE MÓDULOS RELEVANTES")
    IrModule = odoo_env["ir.module.module"]
    target_modules = [
        "fleet",
        "maintenance",
        "hr_fleet",
        "stock",
        "l10n_ar",
    ]
    for mod_name in target_modules:
        mod = IrModule.search([("name", "=", mod_name)], limit=1)
        status = mod.state if mod else "no instalado"
        print(f" • Módulo '{mod_name:<15}': {status.upper()}")

    # Módulos personalizados o de Studio instalados
    custom_mods = IrModule.search([
        ("state", "=", "installed"),
        ("name", "like", "studio_customization%"),
    ])
    if custom_mods:
        print("\n [!] Se detectaron módulos de Studio:")
        for c in custom_mods:
            print(f"   - {c.name} ({c.shortdesc})")

    # Módulos de terceros o in-house
    inhouse_mods = IrModule.search([
        ("state", "=", "installed"),
        ("author", "not in", ["Odoo S.A.", "Odoo", "Odoo Community Association (OCA)"]),
        ("name", "not like", "studio_customization%"),
    ])
    if inhouse_mods:
        print("\n [!] Módulos personalizados detectados:")
        for m in inhouse_mods[:10]:
            print(f"   - {m.name} (Autor: {m.author})")

    # --------------------------------------------------------------------------
    # 2. AUDITORÍA DEL MODELO fleet.vehicle
    # --------------------------------------------------------------------------
    print_title("2. INSPECCIÓN TÉCNICA: fleet.vehicle")
    if "fleet.vehicle" not in odoo_env:
        print("[X] ERROR: El modelo 'fleet.vehicle' no está disponible en el entorno.")
        return

    VehicleModel = odoo_env["fleet.vehicle"]
    fields_vehicle = VehicleModel._fields

    # Verificación de campos estándar esperados
    print_subtitle("Campos de Identificación y Especificaciones")
    key_fields = [
        "license_plate",
        "vin_sn",
        "model_year",
        "category_id",
        "model_id",
        "brand_id",
        "odometer_unit",
        "driver_id",
        "future_driver_id",
        "manager_id",
        "state_id",
        "company_id",
        "acquisition_date",
        "description",
    ]
    for f_name in key_fields:
        if f_name in fields_vehicle:
            f = fields_vehicle[f_name]
            rel = f" -> {f.comodel_name}" if hasattr(f, "comodel_name") and f.comodel_name else ""
            req = " [OBLIGATORIO]" if f.required else ""
            ro = " [READONLY]" if f.readonly else ""
            print(f" [✓] {f_name:<20} | Tipo: {f.type:<12}{rel}{req}{ro} | '{f.string}'")
        else:
            print(f" [X] {f_name:<20} | NO EXISTE EN ESTA VERSIÓN")

    # Análisis del campo odometer_unit
    if "odometer_unit" in fields_vehicle:
        odo_field = fields_vehicle["odometer_unit"]
        print_subtitle("Valores permitidos en 'odometer_unit'")
        selection = odo_field.selection
        if callable(selection):
            selection = selection(VehicleModel)
        print(f" Opciones actuales: {selection}")
        has_hours = any(k == "hours" or "hora" in str(v).lower() for k, v in (selection or []))
        if has_hours:
            print(" -> [!] Soporta medición en Horas de fábrica o por personalización.")
        else:
            print(" -> [i] Solo soporta Km/Millas nativamente (Horas requerirá customización o uso de kilometraje).")

    # Detección de campos para Número de Motor
    print_subtitle("Búsqueda de Campos para 'Número de Motor'")
    motor_matches = []
    for f_name, f in fields_vehicle.items():
        name_lower = f_name.lower()
        string_lower = (f.string or "").lower()
        if any(term in name_lower or term in string_lower for term in ["motor", "engine", "chasis_motor", "nro_motor"]):
            motor_matches.append((f_name, f.type, f.string))

    if motor_matches:
        print(" [!] Se encontraron los siguientes campos candidatos para Motor:")
        for m_name, m_type, m_str in motor_matches:
            print(f"   • {m_name:<25} ({m_type}) -> '{m_str}'")
    else:
        print(" [i] No existe ningún campo nativo ni personalizado para 'Número de Motor'.")
        print("     Se recomienda crearlo mediante módulo (engine_number) o Studio (x_engine_number).")

    # Detección de campos creados por Studio o Custom (prefijo x_ o x_studio)
    print_subtitle("Campos Personalizados (x_ / Studio) en fleet.vehicle")
    custom_vehicle_fields = [(k, v.type, v.string) for k, v in fields_vehicle.items() if k.startswith("x_")]
    if custom_vehicle_fields:
        for cf, ctype, cstr in custom_vehicle_fields:
            print(f" • {cf:<30} ({ctype}) -> '{cstr}'")
    else:
        print(" (Sin campos personalizados con prefijo x_)")

    # --------------------------------------------------------------------------
    # 3. AUDITORÍA DE MODELOS fleet.vehicle.model, brand y category
    # --------------------------------------------------------------------------
    print_title("3. INSPECCIÓN DE MODELOS AUXILIARES DE FLOTA")

    # fleet.vehicle.model
    if "fleet.vehicle.model" in odoo_env:
        ModelObj = odoo_env["fleet.vehicle.model"]
        fields_model = ModelObj._fields
        print_subtitle("fleet.vehicle.model")
        for f_name in ["name", "brand_id", "category_id", "vehicle_type"]:
            if f_name in fields_model:
                f = fields_model[f_name]
                print(f" [✓] {f_name:<18} | Tipo: {f.type:<12} | '{f.string}'")
                if f_name == "vehicle_type":
                    v_sel = f.selection(ModelObj) if callable(f.selection) else f.selection
                    print(f"     -> Opciones de vehicle_type: {v_sel}")
            else:
                print(f" [X] {f_name:<18} | NO EXISTE")

    # fleet.vehicle.model.category
    if "fleet.vehicle.model.category" in odoo_env:
        CatObj = odoo_env["fleet.vehicle.model.category"]
        print_subtitle("fleet.vehicle.model.category")
        print(f" [✓] Modelo presente. Total categorías existentes: {CatObj.search_count([])}")
        cats = CatObj.search([], limit=10)
        print("     Categorías cargadas: " + ", ".join([c.name for c in cats]) if cats else "     (Vacío)")

    # fleet.vehicle.model.brand
    if "fleet.vehicle.model.brand" in odoo_env:
        BrandObj = odoo_env["fleet.vehicle.model.brand"]
        print_subtitle("fleet.vehicle.model.brand")
        print(f" [✓] Modelo presente. Total marcas existentes: {BrandObj.search_count([])}")
        brands = BrandObj.search([], limit=10)
        print("     Marcas cargadas: " + ", ".join([b.name for b in brands]) if brands else "     (Vacío)")

    # --------------------------------------------------------------------------
    # 4. AUDITORÍA DEL MÓDULO maintenance (EQUIPOS)
    # --------------------------------------------------------------------------
    print_title("4. INSPECCIÓN TÉCNICA: maintenance.equipment (MANTENIMIENTO)")
    if "maintenance.equipment" in odoo_env:
        EquipmentModel = odoo_env["maintenance.equipment"]
        fields_eq = EquipmentModel._fields
        print(" [✓] Modelo 'maintenance.equipment' disponible.")
        print(f" [*] Total equipos registrados: {EquipmentModel.search_count([])}")

        print_subtitle("Campos de Equipos de Mantenimiento")
        eq_key_fields = [
            "name",
            "category_id",
            "serial_no",
            "model",
            "partner_id",
            "technician_user_id",
            "maintenance_team_id",
            "assign_date",
            "effective_date",
        ]
        for f_name in eq_key_fields:
            if f_name in fields_eq:
                f = fields_eq[f_name]
                print(f" [✓] {f_name:<22} | Tipo: {f.type:<12} | '{f.string}'")

        # Verificar si existe vínculo nativo o custom entre maintenance y fleet
        print_subtitle("Vínculos entre maintenance.equipment y fleet.vehicle")
        fleet_links = []
        for f_name, f in fields_eq.items():
            if hasattr(f, "comodel_name") and f.comodel_name == "fleet.vehicle":
                fleet_links.append((f_name, f.string))

        if fleet_links:
            print(" [!] Se detectó relación con Flota:")
            for l_name, l_str in fleet_links:
                print(f"   • {l_name} -> '{l_str}'")
        else:
            print(" [i] No existe relación Many2one con 'fleet.vehicle' nativamente.")
            print("     Si se requiere vincularlos, se puede crear: vehicle_id = fields.Many2one('fleet.vehicle')")

    else:
        print(" [X] El modelo 'maintenance.equipment' NO está instalado en esta base de datos.")

    # --------------------------------------------------------------------------
    # 5. MUESTRA DE REGISTROS EXISTENTES EN FLOTA
    # --------------------------------------------------------------------------
    print_title("5. ESTADO ACTUAL DE REGISTROS DE FLOTA EN BD")
    total_vehicles = VehicleModel.search_count([])
    print(f"[*] Total vehículos en 'fleet.vehicle': {total_vehicles}")

    if total_vehicles > 0:
        print_subtitle("Últimos vehículos creados (Muestra de hasta 5):")
        sample_vehicles = VehicleModel.search([], order="id desc", limit=5)
        for sv in sample_vehicles:
            brand = sv.model_id.brand_id.name if sv.model_id.brand_id else "S/M"
            model = sv.model_id.name if sv.model_id else "S/M"
            cat = sv.category_id.name if sv.category_id else "S/C"
            chassis = sv.vin_sn or "S/Chasis"
            print(f" • [ID {sv.id:3d}] Patente: {sv.license_plate:<12} | {brand} {model} | Cat: {cat} | VIN: {chassis}")

    print_title("FIN DE AUDITORÍA - SISTEMA LISTO PARA DEFINICIÓN DE IMPORTACIÓN")


# ------------------------------------------------------------------------------
# PUNTO DE ENTRADA SHELL
# ------------------------------------------------------------------------------
if "env" in globals():
    try:
        run_fleet_audit(env)
    except Exception as e:
        print(f"\n[X] Error durante la auditoría: {e}")
        import traceback
        traceback.print_exc()
else:
    print("Este script debe ejecutarse dentro de la shell de Odoo (odoo-bin shell).")
    print("Comando recomendado en Odoo.sh:")
    print("  python3 odoo-bin shell -d $ODOO_STAGE --no-http < audit_fleet_odoo19.py")

