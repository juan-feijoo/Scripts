# -*- coding: utf-8 -*-
"""
Script de Diagnóstico: Inspección de la Validación _check_company_accounts
=========================================================================
Entorno: Odoo 17.0+e (Odoo.sh)
"""

import inspect

def inspect_validation(env):
    print("=" * 80)
    print(" INSPECCIÓN DE LA VALIDACIÓN _check_company_accounts")
    print("=" * 80)

    Model = env['account.analytic.distribution.model']

    # 1. Imprimir código fuente de la función
    print("\n--- [1] CÓDIGO FUENTE DE _check_company_accounts ---")
    try:
        src = inspect.getsource(Model._check_company_accounts)
        print(src)
    except Exception as e:
        print(f"[!] Error al obtener código fuente con inspect: {e}")

    # 2. Consultar estado en PostgreSQL de las cuentas de prueba
    print("\n--- [2] ESTADO REAL EN BD (account_analytic_account) ---")
    env.cr.execute("""
        SELECT a.id, a.name, a.company_id, c.name AS company_name
        FROM account_analytic_account a
        LEFT JOIN res_company c ON c.id = a.company_id
        WHERE a.id IN (3, 4, 24)
        ORDER BY a.id;
    """)
    for row in env.cr.dictfetchall():
        raw_name = row['name']
        name_str = raw_name.get('es_AR') or raw_name.get('en_US') or str(raw_name) if isinstance(raw_name, dict) else str(raw_name)
        comp_str = row['company_name'].get('es_AR') if isinstance(row['company_name'], dict) else row['company_name']
        print(f"  Cuenta ID: {row['id']} | Nombre: {name_str:<25} | company_id: {row['company_id']} ({comp_str})")

    # 3. Consultar los modelos de SUC. ARENALES existentes
    print("\n--- [3] MODELOS EXISTENTES EN BD (account_analytic_distribution_model) ---")
    env.cr.execute("""
        SELECT m.id, m.company_id, c.name AS company_name, m.analytic_distribution
        FROM account_analytic_distribution_model m
        LEFT JOIN res_company c ON c.id = m.company_id
        WHERE m.company_id IN (2, 3)
        ORDER BY m.id;
    """)
    for row in env.cr.dictfetchall():
        comp_str = row['company_name'].get('es_AR') if isinstance(row['company_name'], dict) else row['company_name']
        print(f"  Modelo ID: {row['id']} | Empresa: {row['company_id']} ({comp_str}) | Dist: {row['analytic_distribution']}")

    # 4. Probar simulación de consulta SQL de _check_company_accounts
    print("\n--- [4] EVALUACIÓN DEL QUERY DE VALIDACIÓN PARA RAGONE ---")
    test_account_ids = [4]
    env.cr.execute("""
        SELECT a.id, a.company_id
        FROM account_analytic_account a
        WHERE a.id = 4;
    """)
    acc_row = env.cr.dictfetchone()
    print(f"  En BD PostgreSQL, Cuenta 4 tiene company_id: {acc_row['company_id']}")

    print("\n" + "=" * 80)
    print(" FIN DE INSPECCIÓN")
    print("=" * 80)
    env.cr.rollback()

if 'env' in locals() or 'env' in globals():
    inspect_validation(env)
else:
    print("[!] Ejecutar dentro de odoo-bin shell.")
