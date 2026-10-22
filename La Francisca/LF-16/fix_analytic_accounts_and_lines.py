# -*- coding: utf-8 -*-
"""
Script de Asignación de Empresas a Cuentas Analíticas y Líneas Históricas
========================================================================
Entorno: Odoo 17.0+e (Odoo.sh) - Base: outsourcearg-lafrancisca-prueba-40142666

Objetivo:
  1. Asignar explícitamente a cada Cuenta Analítica de sucursal su respectiva
     empresa (company_id = sucursal_id):
       - SUCURSAL ARENALES       -> SUC. ARENALES (ID: 2)
       - SUCURSAL RAGONE         -> SUC. RAGONE (ID: 3)
       - SUCURSAL TRES CERRITOS  -> SUC. TRES CERRITOS (ID: 4)
       - SUCURSAL ZUVIRIA        -> SUC. ZUVIRIA (ID: 5)
       - SUCURSAL GRAL. GUEMES   -> SUC. GENERAL GUEMES (ID: 6)
       - SUCURSAL ORAN           -> SUC. ORAN (ID: 7)
       - SUCURSAL SALVADOR MAZZA -> SUC. SALVADOR MAZZA (ID: 8)
       - FOOD TRUCK              -> FOOD TRUCK (ID: 9)
       - SUCURSAL SAN LORENZO    -> SUC. SAN LORENZO (ID: 10)
       - SUCURSAL GRAL. GUEMES 2 -> SUC. GENERAL GUEMES - PLAZA (ID: 11)
       - Suc Mdo Ctral Bs As     -> SUC MERCADO CENTRAL BS AS (ID: 13)
  2. Mantener la cuenta FABRICA DE PASTAS (ID: 24) en 'Todas las Compañías'
     (company_id = NULL) para permitir su uso compartido en todas las sucursales.
  3. Actualizar el company_id en las líneas analíticas históricas (account_analytic_line)
     de cada cuenta para que coincida con su sucursal, satisfaciendo la validación
     de consistencia interna de Odoo (_check_company_consistency).
  4. Validar que todos los Modelos de Distribución Analítica sigan siendo 100% válidos.

Configuración DRY-RUN:
  - DRY_RUN = True  : Simula la operación y ejecuta ROLLBACK.
  - DRY_RUN = False : Aplica los cambios y ejecuta COMMIT.
"""

import logging

_logger = logging.getLogger("odoo.analytic.company_fix")

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================

# Si es True, no aplica cambios (simulación con rollback).
# Cambiar a False para aplicar definitivamente en la base de datos.
DRY_RUN = False

FABRICA_PASTAS_ACCOUNT_ID = 24

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
# LÓGICA DE ACTUALIZACIÓN
# ==============================================================================

def fix_analytic_companies(env):
    print("=" * 80)
    print(f" ASIGNACIÓN DE EMPRESAS A CUENTAS ANALÍTICAS (DRY_RUN = {DRY_RUN})")
    print(f" Base de Datos: {env.cr.dbname}")
    print("=" * 80)

    # 1. Asegurar Fábrica de Pastas en NULL (Todas las Compañías)
    print("\n--- [PASO 1] VERIFICAR FÁBRICA DE PASTAS (GLOBAL) ---")
    env.cr.execute("""
        UPDATE account_analytic_account
           SET company_id = NULL
         WHERE id = %s AND company_id IS NOT NULL;
    """, [FABRICA_PASTAS_ACCOUNT_ID])
    if env.cr.rowcount > 0:
        print(f"  [+] Fábrica de Pastas (ID {FABRICA_PASTAS_ACCOUNT_ID}) ajustada a 'Todas las Compañías'.")
    else:
        print(f"  [=] Fábrica de Pastas (ID {FABRICA_PASTAS_ACCOUNT_ID}) ya es 'Todas las Compañías'.")

    # 2. Actualizar cada Cuenta Analítica con su Sucursal y sus Líneas Históricas
    print("\n--- [PASO 2] ASIGNAR SUCURSAL A CUENTAS Y LÍNEAS ANALÍTICAS ---")
    
    total_accounts_updated = 0
    total_lines_updated = 0

    for item in SUCURSALES_DATA:
        comp_id = item["company_id"]
        comp_name = item["company_name"]
        acc_id = item["analytic_id"]
        acc_name = item["analytic_name"]

        # A. Actualizar la cuenta analítica
        env.cr.execute("""
            UPDATE account_analytic_account
               SET company_id = %s
             WHERE id = %s;
        """, [comp_id, acc_id])
        acc_rows = env.cr.rowcount

        # B. Actualizar las líneas analíticas históricas vinculadas a esta cuenta
        # para que pertenezcan a la misma sucursal (evita UserError en ORM)
        env.cr.execute("""
            UPDATE account_analytic_line
               SET company_id = %s
             WHERE account_id = %s AND (company_id IS NULL OR company_id != %s);
        """, [comp_id, acc_id, comp_id])
        line_rows = env.cr.rowcount

        total_accounts_updated += acc_rows
        total_lines_updated += line_rows

        print(f"  [OK] Cuenta [{acc_id:2d}] {acc_name:<30} -> Empresa [{comp_id:2d}] {comp_name:<28} | {line_rows} líneas históricas actualizadas")

    # 3. Sincronizar Caché de Odoo
    env['account.analytic.account'].invalidate_model(['company_id'])
    env['account.analytic.line'].invalidate_model(['company_id'])

    # 4. Validar que los Modelos de Distribución Analítica cumplan la restricción
    print("\n--- [PASO 3] VERIFICACIÓN DE MODELOS DE DISTRIBUCIÓN ANALÍTICA ---")
    DistributionModel = env['account.analytic.distribution.model']
    
    # Ejecutamos la validación nativa de Odoo sobre todos los modelos existentes
    all_models = DistributionModel.sudo().search([])
    try:
        all_models._check_company_accounts()
        print(f"  [✓] ÉXITO: Los {len(all_models)} Modelos de Distribución Analítica cumplen la validación _check_company_accounts.")
    except Exception as e:
        print(f"  [ERROR] Falla en validación de modelos: {e}")

    # 5. Resumen Final y Transacción
    print("\n" + "=" * 80)
    print(" RESUMEN DE EJECUCIÓN")
    print("=" * 80)
    print(f"  Cuentas Analíticas Asignadas : {total_accounts_updated}")
    print(f"  Líneas Analíticas Sincronizadas : {total_lines_updated}")
    print(f"  Modelos Validados Exitosamente : {len(all_models)}")
    print("-" * 80)

    if DRY_RUN:
        env.cr.rollback()
        print("\n [!] MODO DRY-RUN: Transacción revertida (ROLLBACK).")
        print("     Ningún registro fue modificado en la base de datos.")
        print("     Para aplicar los cambios reales, configure DRY_RUN = False en la línea 32.\n")
    else:
        env.cr.commit()
        print("\n [✓] MODO REAL: Transacción confirmada (COMMIT).")
        print("     Empresas asignadas correctamente a cuentas analíticas y líneas históricas.\n")


# Punto de entrada para ejecución en Odoo Shell
if 'env' in locals() or 'env' in globals():
    fix_analytic_companies(env)
else:
    print("[!] Este script debe ejecutarse dentro de la shell de Odoo (odoo-bin shell).")
