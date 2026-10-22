# -*- coding: utf-8 -*-
"""
Script de Creación / Actualización Masiva de Modelos de Distribución Analítica
=============================================================================
Entorno: Odoo 17.0+e (Odoo.sh) - Base: outsourcearg-lafrancisca-prueba-40142666
Calibrado con datos exactos de la Auditoría del 22/10/2026

Objetivo:
  1. Liberar la restricción multi-compañía (company_id = NULL) en la tabla
     account_analytic_account para todas las cuentas de sucursales, replicando
     la configuración ya existente en 'SUCURSAL ARENALES' y 'FABRICA DE PASTAS'.
     Esto satisface la restricción SQL nativa de Odoo 17:
       account.company_id IS NOT NULL AND (model.company_id IS NULL OR model.company_id != account.company_id)
  2. Configurar la distribución analítica general por Sucursal:
     - analytic_distribution: {'<id_sucursal>': 100.0}
  3. Configurar la distribución analítica de Pastas (Sucursal + Fábrica de Pastas)
     para la categoría PASTAS (ID 254):
     - analytic_distribution: {'<id_sucursal>': 100.0, '24': 100.0}

Configuración DRY-RUN:
  - DRY_RUN = True  : Simula la operación, muestra el plan de acción y ejecuta ROLLBACK.
  - DRY_RUN = False : Aplica las creaciones/actualizaciones y ejecuta COMMIT.
"""

import logging

_logger = logging.getLogger("odoo.analytic.setup")

# ==============================================================================
# CONFIGURACIÓN (CALIBRADA CON AUDITORÍA REAL)
# ==============================================================================

# Si es True, simula y revierte (ROLLBACK). Cambiar a False para guardar cambios (COMMIT).
DRY_RUN = False

# ID de la Cuenta Analítica de FÁBRICA DE PASTAS (ID 24 detectado en auditoría)
FABRICA_PASTAS_ACCOUNT_ID = 24

# ID de la Categoría de Productos PASTAS (ID 254 detectado en auditoría)
PASTAS_CATEGORY_ID = 254

# Mapeo exacto verificado entre Compañía (Sucursal) y Cuenta Analítica
SUCURSALES_DATA = [
    {"company_id": 2,  "company_name": "SUC. ARENALES",                "analytic_id": 3,  "analytic_name": "SUCURSAL ARENALES"},
    {"company_id": 3,  "company_name": "SUC. RAGONE",                  "analytic_id": 4,  "analytic_name": "SUCURSAL RAGONE"},
    {"company_id": 4,  "company_name": "SUC. TRES CERRITOS",           "analytic_id": 2,  "analytic_name": "SUCURSAL TRES CERRITOS"},
    {"company_id": 5,  "company_name": "SUC. ZUVIRIA",                 "analytic_id": 6,  "analytic_name": "SUCURSAL ZUVIRIA"},
    {"company_id": 6,  "company_name": "SUC. GENERAL GUEMES",          "analytic_id": 5,  "analytic_name": "SUCURSAL GRAL. GUEMES"},
    {"company_id": 7,  "company_name": "SUC. ORAN",                    "analytic_id": 7,  "analytic_name": "SUCURSAL ORAN"},
    {"company_id": 8,  "company_name": "SUC. SALVADOR MAZZA",          "analytic_id": 8,  "analytic_name": "SUCURSAL SALVADOR MAZZA"},
    {"company_id": 9,  "company_name": "FOOD TRUCK",                   "analytic_id": 9,  "analytic_name": "FOOD TRUCK"},
    {"company_id": 10, "company_name": "SUC. SAN LORENZO",             "analytic_id": 19, "analytic_name": "SUCURSAL SAN LORENZO"},
    {"company_id": 11, "company_name": "SUC. GENERAL GUEMES - PLAZA",  "analytic_id": 22, "analytic_name": "SUCURSAL GRAL. GUEMES 2"},
    {"company_id": 13, "company_name": "SUC MERCADO CENTRAL BS AS",   "analytic_id": 25, "analytic_name": "Suc Mdo Ctral Bs As"},
]


# ==============================================================================
# LÓGICA PRINCIPAL
# ==============================================================================

def setup_analytic_models(env):
    print("=" * 80)
    print(f" CONFIGURACIÓN DE MODELOS ANALÍTICOS (DRY_RUN = {DRY_RUN})")
    print(f" Base de Datos: {env.cr.dbname}")
    print("=" * 80)

    # 1. Validar Cuenta Fábrica de Pastas y Categoría Pastas
    fabrica_acc = env['account.analytic.account'].sudo().browse(FABRICA_PASTAS_ACCOUNT_ID)
    pastas_categ = env['product.category'].sudo().browse(PASTAS_CATEGORY_ID)

    if not fabrica_acc.exists():
        print(f"[ERROR] No existe la cuenta analítica ID {FABRICA_PASTAS_ACCOUNT_ID}.")
        return
    if not pastas_categ.exists():
        print(f"[ERROR] No existe la categoría de producto ID {PASTAS_CATEGORY_ID}.")
        return

    print(f"[OK] Fábrica de Pastas : ID {fabrica_acc.id} - '{fabrica_acc.name}'")
    print(f"[OK] Categoría Pastas  : ID {pastas_categ.id} - '{pastas_categ.complete_name}'")

    # 2. Paso fundamental: Actualizar en PostgreSQL las cuentas de sucursales a company_id = NULL
    # La restricción SQL de Odoo es: account.company_id IS NOT NULL AND model.company_id != account.company_id
    # Al hacerlas NULL (Todas las Compañías), la condición evaluará siempre a False.
    all_analytic_ids = [item["analytic_id"] for item in SUCURSALES_DATA] + [FABRICA_PASTAS_ACCOUNT_ID]

    print("\n--- [PASO 1] SINCRONIZACIÓN DE CUENTAS ANALÍTICAS A NIVEL POSTGRESQL ---")
    if not DRY_RUN:
        env.cr.execute("""
            UPDATE account_analytic_account
               SET company_id = NULL
             WHERE id = ANY(%s) AND company_id IS NOT NULL;
        """, [all_analytic_ids])
        updated_sql_rows = env.cr.rowcount
        # Sincronizar ORM Cache
        env['account.analytic.account'].invalidate_model(['company_id'])
        print(f"  [+] {updated_sql_rows} cuentas analíticas ajustadas a 'Todas las Compañías' en base de datos.")
    else:
        env.cr.execute("""
            SELECT id, name, company_id
              FROM account_analytic_account
             WHERE id = ANY(%s) AND company_id IS NOT NULL;
        """, [all_analytic_ids])
        to_fix = env.cr.dictfetchall()
        print(f"  [*] [DRY-RUN] Se ajustarían {len(to_fix)} cuentas analíticas a 'Todas las Compañías'.")

    # 3. Procesar creación y actualización de modelos de distribución
    print("\n--- [PASO 2] PROCESAMIENTO DE MODELOS DE DISTRIBUCIÓN POR SUCURSAL ---")
    DistributionModel = env['account.analytic.distribution.model'].sudo()

    created_count = 0
    updated_count = 0
    skipped_count = 0

    for item in SUCURSALES_DATA:
        comp_id = item["company_id"]
        comp_name = item["company_name"]
        suc_acc_id = item["analytic_id"]
        suc_acc_name = item["analytic_name"]

        company = env['res.company'].sudo().browse(comp_id)
        suc_acc = env['account.analytic.account'].sudo().browse(suc_acc_id)

        if not company.exists():
            print(f"  [!] Empresa ID {comp_id} ('{comp_name}') no existe. Se omite.")
            continue
        if not suc_acc.exists():
            print(f"  [!] Cuenta analítica ID {suc_acc_id} ('{suc_acc_name}') no existe. Se omite.")
            continue

        print(f"\n>> Sucursal: [{comp_id}] {company.name}  <==>  Cuenta: [{suc_acc_id}] {suc_acc.name}")

        # ----------------------------------------------------------------------
        # A. REGLA GENERAL (Por defecto para todos los productos en la sucursal)
        # Formato: {'<id_suc>': 100.0}
        # ----------------------------------------------------------------------
        expected_dist_general = {
            str(suc_acc.id): 100.0
        }

        domain_general = [
            ('company_id', '=', company.id),
            ('product_categ_id', '=', False),
            ('product_id', '=', False),
            ('partner_id', '=', False),
            ('partner_category_id', '=', False),
            ('account_prefix', '=', False),
        ]
        existing_general = DistributionModel.search(domain_general, limit=1)

        if not existing_general:
            vals_general = {
                'company_id': company.id,
                'analytic_distribution': expected_dist_general,
            }
            if not DRY_RUN:
                rec = DistributionModel.create(vals_general)
                print(f"  [+] CREADO (General): Modelo ID {rec.id} -> {expected_dist_general}")
            else:
                print(f"  [*] [DRY-RUN] SE CREARÍA (General): -> {expected_dist_general}")
            created_count += 1
        else:
            if existing_general.analytic_distribution != expected_dist_general:
                if not DRY_RUN:
                    existing_general.write({'analytic_distribution': expected_dist_general})
                    print(f"  [~] ACTUALIZADO (General): Modelo ID {existing_general.id} -> {expected_dist_general}")
                else:
                    print(f"  [*] [DRY-RUN] SE ACTUALIZARÍA (General): Modelo ID {existing_general.id} -> {expected_dist_general}")
                updated_count += 1
            else:
                print(f"  [=] SIN CAMBIOS (General): Modelo ID {existing_general.id} ya tiene {expected_dist_general}")
                skipped_count += 1

        # ----------------------------------------------------------------------
        # B. REGLA PASTAS (Sucursal + Fábrica de Pastas para Categoría PASTAS)
        # Formato: {'<id_suc>': 100.0, '24': 100.0}
        # ----------------------------------------------------------------------
        expected_dist_pastas = {
            str(suc_acc.id): 100.0,
            str(fabrica_acc.id): 100.0,
        }

        domain_pastas = [
            ('company_id', '=', company.id),
            ('product_categ_id', '=', pastas_categ.id),
            ('product_id', '=', False),
            ('partner_id', '=', False),
            ('partner_category_id', '=', False),
            ('account_prefix', '=', False),
        ]
        existing_pastas = DistributionModel.search(domain_pastas, limit=1)

        if not existing_pastas:
            vals_pastas = {
                'company_id': company.id,
                'product_categ_id': pastas_categ.id,
                'analytic_distribution': expected_dist_pastas,
            }
            if not DRY_RUN:
                rec = DistributionModel.create(vals_pastas)
                print(f"  [+] CREADO (Pastas): Modelo ID {rec.id} -> {expected_dist_pastas}")
            else:
                print(f"  [*] [DRY-RUN] SE CREARÍA (Pastas): -> {expected_dist_pastas}")
            created_count += 1
        else:
            if existing_pastas.analytic_distribution != expected_dist_pastas:
                if not DRY_RUN:
                    existing_pastas.write({'analytic_distribution': expected_dist_pastas})
                    print(f"  [~] ACTUALIZADO (Pastas): Modelo ID {existing_pastas.id} -> {expected_dist_pastas}")
                else:
                    print(f"  [*] [DRY-RUN] SE ACTUALIZARÍA (Pastas): Modelo ID {existing_pastas.id} -> {expected_dist_pastas}")
                updated_count += 1
            else:
                print(f"  [=] SIN CAMBIOS (Pastas): Modelo ID {existing_pastas.id} ya tiene {expected_dist_pastas}")
                skipped_count += 1

    # 4. Resumen y Control de Transacción
    print("\n" + "=" * 80)
    print(" RESUMEN DE PROCESAMIENTO")
    print("=" * 80)
    print(f"  Modelos a Crear               : {created_count}")
    print(f"  Modelos a Actualizar          : {updated_count}")
    print(f"  Modelos Sin Cambios           : {skipped_count}")
    print(f"  Total Sucursales Procesadas   : {len(SUCURSALES_DATA)}")
    print("-" * 80)

    if DRY_RUN:
        env.cr.rollback()
        print("\n [!] MODO DRY-RUN: Transacción revertida (ROLLBACK).")
        print("     Ningún registro fue creado ni modificado en la base de datos.")
        print("     Para aplicar los cambios reales, configure DRY_RUN = False en la línea 30.\n")
    else:
        env.cr.commit()
        print("\n [✓] MODO REAL: Transacción confirmada (COMMIT).")
        print("     Cuentas analíticas y modelos de distribución guardados exitosamente.\n")


# Punto de entrada para ejecución en Odoo Shell
if 'env' in locals() or 'env' in globals():
    setup_analytic_models(env)
else:
    print("[!] Este script debe ejecutarse dentro de la shell de Odoo (odoo-bin shell).")
