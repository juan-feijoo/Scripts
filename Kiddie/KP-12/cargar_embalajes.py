#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para Odoo Shell (odoo-bin shell):
Carga de presentaciones de compra y bultos en Embalajes (product.packaging)

Uso en Odoo.sh:
1. Subir 'datos_embalajes.json' y 'cargar_embalajes.py' a ~/tmp/KP-12/
2. Ejecutar prueba dry-run:
   python3 odoo-bin shell -d $PGDATABASE --no-http --log-level=warn < ~/tmp/KP-12/cargar_embalajes.py
3. Para persistir los cambios, cambiar DRY_RUN = False o pasar DRY_RUN=0:
   DRY_RUN=0 python3 odoo-bin shell -d $PGDATABASE --no-http --log-level=warn < ~/tmp/KP-12/cargar_embalajes.py
"""

import os
import sys
import json
import logging

_logger = logging.getLogger('cargar_embalajes')

# =========================================================================
# CONFIGURACIÓN
# =========================================================================
# Si la variable de entorno DRY_RUN está definida en '0' o 'false', persiste.
# Por defecto siempre es True (simulación con rollback).
env_dry_run = os.environ.get('DRY_RUN', '1').lower()
DRY_RUN = env_dry_run not in ('0', 'false', 'no')

# Ruta al archivo JSON con los datos procesados
# Busca primero en la ruta relativa actual, luego en ~/tmp/KP-12/, o variable JSON_FILE
json_path_env = os.environ.get('JSON_FILE')
candidate_paths = [
    json_path_env,
    'datos_embalajes.json',
    os.path.expanduser('~/tmp/KP-12/datos_embalajes.json'),
    os.path.join(os.path.dirname(__file__) if '__file__' in locals() else '.', 'datos_embalajes.json')
]
JSON_FILE = next((p for p in candidate_paths if p and os.path.exists(p)), 'datos_embalajes.json')

# =========================================================================
# EJECUCIÓN
# =========================================================================
def run():
    print("=" * 70)
    print("  CARGA DE PRESENTACIONES Y EMBALAJES (product.packaging)")
    print(f"  Versión Odoo: {env.ref('base.module_base').installed_version}")
    print(f"  Base de datos: {env.cr.dbname}")
    print(f"  Modo DRY_RUN: {'ACTIVADO (Simulación sin commit)' if DRY_RUN else 'DESACTIVADO (MODO PERSISTENTE / COMMIT)'}")
    print(f"  Archivo datos: {JSON_FILE}")
    print("=" * 70)

    if not os.path.exists(JSON_FILE):
        print(f"\n[ERROR] No se encontró el archivo de datos: {JSON_FILE}")
        return

    # Verificar si el feature de embalajes está activo en res.config.settings o grupos
    group_packaging = env.ref('stock.group_stock_packaging', raise_if_not_found=False)
    if group_packaging:
        users_in_group = len(group_packaging.users)
        print(f"[*] Grupo stock.group_stock_packaging: {'ACTIVO' if users_in_group > 0 else 'ADVERTENCIA: Sin usuarios asignados (verificar Ajustes de Inventario)'}")

    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"[*] Total productos a procesar desde JSON: {len(data)}")

    # Pre-cargar productos por default_code para agilizar búsqueda en bulk
    codes = [item['default_code'] for item in data]
    products = env['product.product'].search([('default_code', 'in', codes)])
    product_by_code = {p.default_code: p for p in products}

    # También buscar si faltan por product.template
    missing_codes = [c for c in codes if c not in product_by_code]
    if missing_codes:
        tmpls = env['product.template'].search([('default_code', 'in', missing_codes)])
        for t in tmpls:
            if t.product_variant_id:
                product_by_code[t.default_code] = t.product_variant_id

    print(f"[*] Productos encontrados en Odoo: {len(product_by_code)} de {len(codes)}")

    # Contadores de auditoría
    stats = {
        'total_productos': len(data),
        'productos_encontrados': len(product_by_code),
        'productos_no_encontrados': 0,
        'embalajes_creados': 0,
        'embalajes_actualizados': 0,
        'embalajes_sin_cambios': 0,
        'errores': 0
    }

    no_encontrados = []

    for item in data:
        code = item['default_code']
        product = product_by_code.get(code)
        if not product:
            stats['productos_no_encontrados'] += 1
            if len(no_encontrados) < 20:
                no_encontrados.append((code, item.get('name')))
            continue

        for pack in item['packagings']:
            pack_name = pack['name']
            pack_qty = float(pack['qty'])
            pack_sales = bool(pack.get('sales', True))
            pack_purchase = bool(pack.get('purchase', True))

            try:
                # Buscar si ya existe un embalaje para este producto con la misma cantidad o nombre
                existing_pack = env['product.packaging'].search([
                    ('product_id', '=', product.id),
                    ('qty', '=', pack_qty)
                ], limit=1)

                if existing_pack:
                    # Si ya existe, verificar si hace falta actualizar flags o nombre
                    vals_to_update = {}
                    if existing_pack.sales != pack_sales:
                        vals_to_update['sales'] = pack_sales
                    if existing_pack.purchase != pack_purchase:
                        vals_to_update['purchase'] = pack_purchase
                    if not existing_pack.name:
                        vals_to_update['name'] = pack_name

                    if vals_to_update:
                        existing_pack.write(vals_to_update)
                        stats['embalajes_actualizados'] += 1
                    else:
                        stats['embalajes_sin_cambios'] += 1
                else:
                    # Crear nuevo embalaje
                    create_vals = {
                        'name': pack_name,
                        'product_id': product.id,
                        'qty': pack_qty,
                        'sales': pack_sales,
                        'purchase': pack_purchase,
                    }
                    env['product.packaging'].create(create_vals)
                    stats['embalajes_creados'] += 1

            except Exception as e:
                stats['errores'] += 1
                print(f"[!] Error procesando [{code}] embalaje '{pack_name}': {e}")

    # Resumen
    print("\n" + "=" * 70)
    print("  RESUMEN DE RESULTADOS")
    print("=" * 70)
    for k, v in stats.items():
        print(f"  {k.replace('_', ' ').capitalize():<30}: {v}")

    if no_encontrados:
        print("\n  Ejemplo de productos no encontrados en Odoo (primeros 20):")
        for c, n in no_encontrados:
            print(f"    - [{c}] {n}")

    # Cierre transaccional
    if DRY_RUN:
        env.cr.rollback()
        print("\n" + ">" * 15 + " DRY_RUN = True -> Se ejecutó ROLLBACK (sin cambios en BD) " + "<" * 15)
    else:
        env.cr.commit()
        print("\n" + ">" * 15 + " DRY_RUN = False -> Se ejecutó COMMIT (cambios PERSISTIDOS en BD) " + "<" * 15)

# En odoo-bin shell, 'env' ya está inyectado en el contexto global
if 'env' in locals():
    run()
else:
    print("Este script debe ejecutarse dentro de 'odoo-bin shell'.")
