# -*- coding: utf-8 -*-
# ==============================================================================
# SCRIPT DE MIGRACIÓN Y CARGA DE FLOTA - ODOO 17.0+e / 18.0+e / 19.0+e
# Entorno: Odoo.sh / Standalone Shell (odoo-bin shell)
# ==============================================================================
"""
Instrucciones de uso en Odoo.sh:
1. Subir este archivo al servidor (ej. /tmp/import_fleet.py)
2. Ejecutar mediante tubería a la shell de Odoo:
   python3 odoo-bin shell -d $ODOO_STAGE --no-http < /tmp/import_fleet.py

O bien dentro de una sesión interactiva de odoo-bin shell:
   exec(open('import_fleet.py').read())
"""

import sys
import logging

_logger = logging.getLogger("fleet_import")

# ------------------------------------------------------------------------------
# PARÁMETROS DE EJECUCIÓN
# ------------------------------------------------------------------------------
# DRY_RUN = True  -> Simulación: recorre, valida y hace ROLLBACK (no impacta la BD)
# DRY_RUN = False -> Producción: crea los registros y ejecuta env.cr.commit()
DRY_RUN = False

# ------------------------------------------------------------------------------
# DATASET NORMALIZADO Y SANEADO
# Estructura: (Patente/Código, Marca, Modelo, Categoría, Tipo de Vehículo)
# ------------------------------------------------------------------------------
RAW_DATA = [
    # Patentes y vehículos estándar
    ("DJQ598", "Iveco", "Camión Iveco", "Camión", "car"),
    ("GOY890", "Fiat", "Uno", "Automóvil", "car"),
    ("HMJ617", "Indumix", "Semi Indumix", "Semirremolque", "car"),
    ("HNA991", "Ford", "Ranger CS 2008", "Pick-up", "car"),
    ("HNI828", "Ford", "Ranger CS 2008", "Pick-up", "car"),
    ("IBH238", "Ford", "Ranger DC 2009", "Pick-up", "car"),
    ("IYQ813", "Volkswagen", "Gol Trend", "Automóvil", "car"),
    ("JCI617", "Fiat", "Palio Fire", "Automóvil", "car"),
    ("JCI817", "Genérica", "Automóvil Sin Especificar", "Automóvil", "car"),
    ("KCC81", "Fiat", "Uno [Patente a Validar]", "Automóvil", "car"),  # Revisar último dígito
    ("LAD887", "Fiat", "Strada", "Pick-up", "car"),
    ("MINIAVANT750", "Turbosol", "Mini Avant 750", "Maquinaria", "car"),
    ("MQZ088", "Volkswagen", "Suran", "Automóvil", "car"),
    ("PEV293", "Fiat", "500", "Automóvil", "car"),
    ("XMH424", "Fiat", "600", "Automóvil", "car"),

    # Motocicletas
    ("009KGN", "Genérica", "Motocicleta", "Motocicleta", "bike"),
    ("182IXF", "Genérica", "Motocicleta", "Motocicleta", "bike"),
    ("A002LLL", "Genérica", "Motocicleta", "Motocicleta", "bike"),
    ("A038GNK", "Genérica", "Motocicleta", "Motocicleta", "bike"),
    ("A084LUW", "Gilera", "Smash 110", "Motocicleta", "bike"),
    ("A202CCE", "Genérica", "Motocicleta", "Motocicleta", "bike"),
    ("A236YAW", "Genérica", "Motocicleta", "Motocicleta", "bike"),

    # Unidades comerciales y utilitarios
    ("AA223IJ", "Volkswagen", "Amarok", "Pick-up", "car"),
    ("AA468WR", "Ford", "Focus", "Automóvil", "car"),
    ("AA876HD", "Ford", "Ranger DC 2016", "Pick-up", "car"),
    ("AB690PR", "Volkswagen", "Gol Trend", "Automóvil", "car"),
    ("AB746KM", "Mercedes-Benz", "Vehículo Comercial", "Camión", "car"),
    ("AB773MO", "Volvo", "Camión", "Camión", "car"),
    ("AB773MP", "Volvo", "Camión", "Camión", "car"),
    ("AC088EK", "Volvo", "Camión", "Camión", "car"),
    ("AC739PS", "Ford", "Ranger DC 2018", "Pick-up", "car"),
    ("AC739PT", "Ford", "Ranger DC 2018", "Pick-up", "car"),
    ("AC864ZD", "Mercedes-Benz", "Sprinter", "Utilitario", "car"),
    ("AD074EW", "Volkswagen", "Up!", "Automóvil", "car"),
    ("AD213ME", "Ford", "Ranger DC 2018", "Pick-up", "car"),
    ("AD213MF", "Ford", "Ranger DC 2018", "Pick-up", "car"),
    ("AD213MG", "Ford", "Ranger DC 2018", "Pick-up", "car"),
    ("AD213MH", "Ford", "Ranger DC 2018", "Pick-up", "car"),
    ("AD213MI", "Ford", "Ranger DC 2018", "Pick-up", "car"),
    ("AD213MU", "Genérica", "Hidrogrúa", "Camión", "car"),
    ("AD407UK", "Ford", "Ranger DC 2018", "Pick-up", "car"),
    ("AD407UL", "Ford", "Ranger DC 2018", "Pick-up", "car"),
    ("AD607MM", "Volkswagen", "Gol Trend", "Automóvil", "car"),
    ("AE461MO", "Ford", "F-150 Raptor 2020", "Pick-up", "car"),
    ("AE663RY", "Ford", "Sedan", "Automóvil", "car"),
    ("AF115QV", "Volvo", "Camión", "Camión", "car"),
    ("AF540IR", "Indumix", "Mixer", "Camión", "car"),
    ("AF540IT", "Volvo", "Camión", "Camión", "car"),
    ("AF846CL", "Volvo", "Mixer", "Camión", "car"),
    ("AG215OE", "Ford", "Ranger DC 2023", "Pick-up", "car"),
    ("AG225QX", "Ford", "Ranger", "Pick-up", "car"),
    ("AG458LI", "Ford", "Territory", "Automóvil", "car"),
    ("AH124TG", "Toyota", "Hilux SW4", "SUV", "car"),

    # Bombas de Hormigón y Maquinaria
    ("BH-2025", "Genérica", "Bomba de Hormigón 2025", "Maquinaria", "car"),
    ("BH-2010", "Genérica", "Bomba Hormigón 2010", "Maquinaria", "car"),
    ("BH-2015", "Genérica", "Bomba Hormigón 2015", "Maquinaria", "car"),
    ("BXA341", "Fiat", "Duna", "Automóvil", "car"),
    ("CAP006", "Peugeot", "306", "Automóvil", "car"),
    ("CAT320D", "Caterpillar", "320D Retroexcavadora", "Maquinaria", "car"),
    ("CAT938H", "Caterpillar", "938H Pala Cargadora", "Maquinaria", "car"),
    ("CAT416E", "Caterpillar", "416E Retroexcavadora", "Maquinaria", "car"),
    ("DOE429", "Mercedes-Benz", "Vehículo Comercial", "Camión", "car"),
    ("DPB100", "Mercedes-Benz", "Camión", "Camión", "car"),
    ("EUY515", "Genérica", "Semirremolque", "Semirremolque", "car"),
    ("GBJ066", "Land Rover", "Vehículo Todo Terreno", "SUV", "car"),
    ("HLS374", "Genérica", "Batea Blanca", "Semirremolque", "car"),
    ("HOE061", "Mercedes-Benz", "L 1624", "Camión", "car"),
    ("HSQ109", "Mercedes-Benz", "Vehículo Comercial", "Camión", "car"),
    ("HYZ460", "Mercedes-Benz", "Automóvil", "Automóvil", "car"),
    ("IMT681", "Genérica", "Semirremolque", "Semirremolque", "car"),
    ("IOW885", "Mercedes-Benz", "Automóvil", "Automóvil", "car"),
    ("ISF023", "Ford", "Ranger DC 2010", "Pick-up", "car"),
    ("JRJ784", "Genérica", "Batea Azul", "Semirremolque", "car"),
    ("JXX177", "Iveco", "Camión", "Camión", "car"),
    ("KFM236", "Iveco", "Camión", "Camión", "car"),
    ("OBI043", "Volkswagen", "Saveiro", "Pick-up", "car"),
    ("OQT881", "Mercedes-Benz", "Coupé", "Automóvil", "car"),
    ("OVP969", "Volkswagen", "Fox", "Automóvil", "car"),
    ("CDM833", "Lonking", "CDM833 Pala Cargadora", "Maquinaria", "car"),
    ("VALMET-TRAC", "Valmet", "Tractor", "Maquinaria", "car"),
    ("VPU084", "Torino", "Torino Coupé", "Automóvil", "car"),
    ("CASE-W20E", "Case", "W20E Pala Cargadora Frontal", "Maquinaria", "car"),
    ("WICHI-TOLEDO", "Toledo", "Acoplado / Tolva", "Semirremolque", "car"),
]


def run_fleet_import(odoo_env, dry_run=False):
    """
    Ejecuta el proceso de importación normalizado sobre el entorno Odoo provisto.
    """
    print("=" * 80)
    print(f"[*] INICIANDO IMPORTACIÓN DE FLOTA (DRY_RUN = {dry_run})")
    print("=" * 80)

    BrandModel = odoo_env["fleet.vehicle.model.brand"]
    CategoryModel = odoo_env["fleet.vehicle.model.category"]
    VehicleModel = odoo_env["fleet.vehicle.model"]
    FleetVehicle = odoo_env["fleet.vehicle"]

    # Pre-cargar cachés para minimizar consultas a base de datos
    brand_cache = {b.name.upper(): b.id for b in BrandModel.search([])}
    cat_cache = {c.name.upper(): c.id for c in CategoryModel.search([])}
    model_cache = {}
    for m in VehicleModel.search([]):
        model_cache[(m.brand_id.id, m.name.upper())] = m.id

    stats = {
        "marcas_creadas": 0,
        "categorias_creadas": 0,
        "modelos_creados": 0,
        "vehiculos_creados": 0,
        "vehiculos_existentes": 0,
    }

    try:
        # Savepoint para control de aislamiento transaccional
        with odoo_env.cr.savepoint():
            for item in RAW_DATA:
                plate, brand_name, model_name, category_name, vtype = item
                plate_clean = plate.strip().upper().replace(" ", "").replace("-", "")

                # 1. Categoría
                cat_key = category_name.strip().upper()
                if cat_key not in cat_cache:
                    new_cat = CategoryModel.create({"name": category_name.strip()})
                    cat_cache[cat_key] = new_cat.id
                    stats["categorias_creadas"] += 1
                cat_id = cat_cache[cat_key]

                # 2. Marca
                brand_key = brand_name.strip().upper()
                if brand_key not in brand_cache:
                    new_brand = BrandModel.create({"name": brand_name.strip()})
                    brand_cache[brand_key] = new_brand.id
                    stats["marcas_creadas"] += 1
                brand_id = brand_cache[brand_key]

                # 3. Modelo
                model_key = (brand_id, model_name.strip().upper())
                if model_key not in model_cache:
                    new_model = VehicleModel.create({
                        "name": model_name.strip(),
                        "brand_id": brand_id,
                        "category_id": cat_id,
                        "vehicle_type": vtype,
                    })
                    model_cache[model_key] = new_model.id
                    stats["modelos_creados"] += 1
                model_id = model_cache[model_key]

                # 4. Vehículo (Validación de duplicados por patente limpia)
                existing = FleetVehicle.search([("license_plate", "=ilike", plate_clean)], limit=1)
                if existing:
                    print(f"[-] Omitido (Ya existe): {plate_clean} (ID: {existing.id})")
                    stats["vehiculos_existentes"] += 1
                    continue

                new_vehicle = FleetVehicle.create({
                    "model_id": model_id,
                    "license_plate": plate_clean,
                    "category_id": cat_id,
                })
                print(f"[+] Creado: {plate_clean} -> {brand_name} {model_name} (ID: {new_vehicle.id})")
                stats["vehiculos_creados"] += 1

            if dry_run:
                print("\n[!] AVISO: DRY_RUN = True. Revirtiendo transacción (Rollback de prueba)...")
                raise Exception("DRY_RUN_ROLLBACK")

        # Confirmación definitiva en Base de Datos si no es simulación
        if not dry_run:
            odoo_env.cr.commit()
            print("\n[✓] COMMIT REALIZADO CON ÉXITO: Datos persistidos en PostgreSQL.")

    except Exception as e:
        if str(e) == "DRY_RUN_ROLLBACK":
            print("[✓] Simulación completada sin errores. Ningún cambio impactó la BD.")
        else:
            odoo_env.cr.rollback()
            print(f"[X] Error fatal durante la ejecución: {e}")
            raise e

    print("-" * 80)
    print("RESUMEN DE RESULTADOS:")
    for key, val in stats.items():
        print(f" • {key.replace('_', ' ').capitalize()}: {val}")
    print("=" * 80)


# ------------------------------------------------------------------------------
# PUNTO DE ENTRADA
# ------------------------------------------------------------------------------
if "env" in globals():
    # Ejecutado dentro de odoo-bin shell
    run_fleet_import(env, dry_run=DRY_RUN)
else:
    print("Este script debe ejecutarse dentro del entorno de Odoo (odoo-bin shell).")
    print("Ejemplo: odoo-bin shell -d <nombre_bd> --no-http < import_fleet.py")
