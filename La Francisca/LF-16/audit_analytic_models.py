# -*- coding: utf-8 -*-
"""
Script de Auditoría: Modelos de Distribución Analítica, Cuentas y Planes
========================================================================
Entorno: Odoo 17.0+e / 18.0+e / 19+e (Odoo.sh)
Modo: Solo Lectura / Auditoría (Safe execution)

Instrucciones de ejecución en Odoo.sh (vía shell):
-------------------------------------------------
Opción 1: Dentro de la shell interactiva de Odoo:
    $ odoo-bin shell -c /home/odoo/src/odoo.conf -d <nombre_bd>
    >>> exec(open('audit_analytic_models.py').read())

Opción 2: Redirigiendo entrada:
    $ python3 odoo-bin shell -c /home/odoo/src/odoo.conf -d <nombre_bd> < audit_analytic_models.py
"""

import json
import logging
from pprint import pformat

_logger = logging.getLogger("odoo.analytic.audit")

def run_audit(env):
    print("=" * 80)
    print(" AUDITORÍA DE CONFIGURACIÓN ANALÍTICA Y MODELOS DE DISTRIBUCIÓN")
    print("=" * 80)
    
    # 1. Información del Entorno
    try:
        import odoo.release as release
        odoo_version = release.version
    except Exception:
        odoo_version = "Desconocida"
        
    print(f"[*] Base de datos : {env.cr.dbname}")
    print(f"[*] Versión Odoo  : {odoo_version}")
    print(f"[*] Usuario actual: {env.user.name} (ID: {env.user.id})")
    print(f"[*] Compañía actual: {env.company.name} (ID: {env.company.id})")
    print("-" * 80)

    audit_data = {
        "database": env.cr.dbname,
        "odoo_version": odoo_version,
        "companies": [],
        "analytic_plans": [],
        "analytic_accounts": [],
        "pasta_categories": [],
        "distribution_models": [],
    }

    # 2. Compañías / Sucursales
    print("\n--- [1] COMPAÑÍAS / SUCURSALES (res.company) ---")
    companies = env['res.company'].sudo().search([])
    for comp in companies:
        comp_info = {
            "id": comp.id,
            "name": comp.name,
            "parent_id": [comp.parent_id.id, comp.parent_id.name] if comp.parent_id else False,
        }
        audit_data["companies"].append(comp_info)
        parent_str = f" (Padre: {comp.parent_id.name})" if comp.parent_id else ""
        print(f"  - ID: {comp.id:2d} | Empresa: {comp.name}{parent_str}")

    # 3. Planes Analíticos
    print("\n--- [2] PLANES ANALÍTICOS (account.analytic.plan) ---")
    plans = env['account.analytic.plan'].sudo().search([])
    for plan in plans:
        plan_info = {
            "id": plan.id,
            "name": plan.name,
            "parent_id": [plan.parent_id.id, plan.parent_id.name] if getattr(plan, 'parent_id', False) else False,
        }
        audit_data["analytic_plans"].append(plan_info)
        print(f"  - Plan ID: {plan.id:2d} | Nombre: {plan.name}")

    # 4. Cuentas Analíticas
    print("\n--- [3] CUENTAS ANALÍTICAS (account.analytic.account) ---")
    accounts = env['account.analytic.account'].sudo().search([], order="plan_id, company_id, name")
    for acc in accounts:
        plan_name = acc.plan_id.name if acc.plan_id else "Sin Plan"
        comp_name = acc.company_id.name if acc.company_id else "Todas las Compañías"
        acc_info = {
            "id": acc.id,
            "code": acc.code or "",
            "name": acc.name,
            "plan_id": [acc.plan_id.id, acc.plan_id.name] if acc.plan_id else False,
            "company_id": [acc.company_id.id, acc.company_id.name] if acc.company_id else False,
            "active": acc.active,
        }
        audit_data["analytic_accounts"].append(acc_info)
        print(f"  - ID: {acc.id:3d} | [{acc.code or 'S/C'}] {acc.name:<35} | Plan: {plan_name:<20} | Empresa: {comp_name}")

    # 5. Categorías de Productos relacionadas con Pastas
    print("\n--- [4] CATEGORÍAS DE PRODUCTO (Búsqueda: 'Pastas') ---")
    pasta_categs = env['product.category'].sudo().search([('name', 'ilike', 'pasta')])
    if not pasta_categs:
        print("  [!] No se encontraron categorías con la palabra 'pasta'. Mostrando categorías raíz:")
        pasta_categs = env['product.category'].sudo().search([], limit=15)
        
    for cat in pasta_categs:
        cat_info = {
            "id": cat.id,
            "name": cat.name,
            "complete_name": cat.complete_name,
            "parent_id": [cat.parent_id.id, cat.parent_id.name] if cat.parent_id else False,
        }
        audit_data["pasta_categories"].append(cat_info)
        print(f"  - Categ ID: {cat.id:3d} | Nombre Completo: {cat.complete_name}")

    # 6. Modelos de Distribución Analítica Existentes
    print("\n--- [5] MODELOS DE DISTRIBUCIÓN ANALÍTICA (account.analytic.distribution.model) ---")
    dist_models = env['account.analytic.distribution.model'].sudo().search([], order="company_id, id")
    print(f"  Total modelos encontrados: {len(dist_models)}")

    # Mapeo rápido de cuentas analíticas para resolver nombres en el JSON
    account_map = {acc.id: f"{acc.name} (Plan: {acc.plan_id.name if acc.plan_id else 'S/P'})" for acc in accounts}

    for model in dist_models:
        comp_str = model.company_id.name if model.company_id else "Global (Todas)"
        prod_str = model.product_id.display_name if model.product_id else "-"
        categ_str = model.product_categ_id.complete_name if model.product_categ_id else "-"
        partner_str = model.partner_id.name if model.partner_id else "-"
        prefix_str = model.account_prefix or "-"
        
        raw_dist = model.analytic_distribution or {}
        
        # Desglosar cuentas en la distribución
        readable_dist = []
        if isinstance(raw_dist, dict):
            for key, percentage in raw_dist.items():
                # En Odoo 16/17/18 las claves pueden ser "3" o combinaciones como "3,7"
                acc_ids_str = str(key).split(",")
                resolved_accounts = []
                for a_id_s in acc_ids_str:
                    try:
                        a_id = int(a_id_s.strip())
                        acc_label = account_map.get(a_id, f"Cuenta ID {a_id} (No encontrada)")
                        resolved_accounts.append(f"[{a_id}] {acc_label}")
                    except ValueError:
                        resolved_accounts.append(f"[Key: {a_id_s}]")
                accounts_joined = " + ".join(resolved_accounts)
                readable_dist.append(f"{accounts_joined} => {percentage}%")
        else:
            readable_dist.append(str(raw_dist))

        model_info = {
            "id": model.id,
            "company_id": [model.company_id.id, model.company_id.name] if model.company_id else False,
            "partner_id": [model.partner_id.id, model.partner_id.name] if model.partner_id else False,
            "partner_category_id": [model.partner_category_id.id, model.partner_category_id.name] if model.partner_category_id else False,
            "product_id": [model.product_id.id, model.product_id.display_name] if model.product_id else False,
            "product_categ_id": [model.product_categ_id.id, model.product_categ_id.complete_name] if model.product_categ_id else False,
            "account_prefix": model.account_prefix or False,
            "analytic_distribution": raw_dist,
            "distribution_analytic_account_ids": model.distribution_analytic_account_ids.ids if hasattr(model, 'distribution_analytic_account_ids') else [],
            "readable_distribution": readable_dist,
        }
        audit_data["distribution_models"].append(model_info)

        print(f"\n  * Modelo ID: {model.id} (Empresa: {comp_str})")
        print(f"    - Filtro Producto  : {prod_str}")
        print(f"    - Filtro Categoría : {categ_str}")
        print(f"    - Filtro Contacto  : {partner_str}")
        print(f"    - Prefijo Cuenta   : {prefix_str}")
        print(f"    - JSON RAW         : {raw_dist}")
        print(f"    - Distribución     : {'; '.join(readable_dist) if readable_dist else '(Vacía)'}")

    print("\n" + "=" * 80)
    print(" FIN DE AUDITORÍA")
    print("=" * 80)
    
    # Intento de guardar informe en JSON local si es posible
    try:
        out_filename = "analytic_audit_output.json"
        with open(out_filename, "w", encoding="utf-8") as f:
            json.dump(audit_data, f, indent=2, ensure_ascii=False)
        print(f"\n[+] Informe JSON exportado exitosamente a: {out_filename}")
    except Exception as e:
        print(f"\n[!] Nota: No se pudo escribir archivo local ({e}), pero todos los datos se imprimieron arriba.")

    # Rollback preventivo garantizado (auditoría es 100% de solo lectura)
    env.cr.rollback()
    return audit_data


# Punto de entrada para ejecución en Odoo Shell
if 'env' in locals() or 'env' in globals():
    run_audit(env)
else:
    print("[!] Este script debe ejecutarse dentro de la shell de Odoo (odoo-bin shell).")
