# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT EXTERNO XML-RPC PARA CARGA DE INVENTARIO (ODOO 17 / 18)
================================================================================
Permite ejecutar la importación desde tu máquina local hacia Odoo.sh Staging o Prod.
Utiliza xmlrpc.client nativo (sin dependencias adicionales).

Soporta:
  --dry-run: Valida la existencia de productos y simula cantidades sin aplicar.
  --commit: Crea o actualiza stock.quant y llama a action_apply_inventory.
================================================================================
"""

import sys
import os
import csv
import argparse
import xmlrpc.client

# ==============================================================================
# CREDENCIALES Y CONFIGURACIÓN (Modificar para Staging o Producción)
# ==============================================================================
ODOO_URL = os.environ.get('ODOO_URL', 'https://sabrabazar-staging-40597816.dev.odoo.com')
ODOO_DB = os.environ.get('ODOO_DB', 'sabrabazar-staging-40597816')
ODOO_USER = os.environ.get('ODOO_USER', 'admin')           # Email del usuario Odoo
ODOO_PASSWORD = os.environ.get('ODOO_API_KEY', '')         # API Key o Password de Odoo
DEFAULT_FILE = 'inventario_preparado.csv'


def main():
    parser = argparse.ArgumentParser(description="Importador de Inventario Inicial Odoo 17/18")
    parser.add_argument('--file', default=DEFAULT_FILE, help="Ruta al archivo CSV o Excel")
    parser.add_argument('--dry-run', action='store_true', default=True, help="Modo simulación (por defecto)")
    parser.add_argument('--commit', action='store_true', help="Aplica y confirma los cambios de inventario")
    parser.add_argument('--batch-size', type=int, default=100, help="Tamaño de lote para action_apply_inventory")
    parser.add_argument('--url', default=ODOO_URL, help="URL de Odoo")
    parser.add_argument('--db', default=ODOO_DB, help="Base de datos de Odoo")
    parser.add_argument('--user', default=ODOO_USER, help="Usuario Odoo")
    parser.add_argument('--key', default=ODOO_PASSWORD, help="API Key / Contraseña Odoo")
    parser.add_argument('--all-qty', action='store_true', help="Incluye filas con cantidad 0")

    args = parser.parse_args()

    # Si se pasa --commit explícitamente, se desactiva dry-run
    dry_run = not args.commit

    print("=" * 80)
    print(f" SCRIPT DE CARGA REMOTA XML-RPC | MODO: {'[DRY-RUN - SIMULACIÓN]' if dry_run else '[EJECUCIÓN REAL - COMMIT]'}")
    print("=" * 80)
    print(f"Destino: {args.url} (BD: {args.db})")
    print(f"Archivo: {args.file}")

    if not args.key:
        print("\n[AVISO] No se proporcionó API Key o contraseña.")
        print("Puedes proporcionarla con el argumento --key <tu_api_key> o configurar la variable ODOO_API_KEY.")
        sys.exit(1)

    # 1. Autenticación
    common = xmlrpc.client.ServerProxy(f"{args.url}/xmlrpc/2/common")
    try:
        uid = common.authenticate(args.db, args.user, args.key, {})
    except Exception as e:
        print(f"[ERROR] Falló la conexión con {args.url}: {e}")
        sys.exit(1)

    if not uid:
        print("[ERROR] Credenciales incorrectas o autenticación rechazada.")
        sys.exit(1)

    print(f"Autenticado exitosamente. UID del usuario: {uid}")
    models = xmlrpc.client.ServerProxy(f"{args.url}/xmlrpc/2/object")

    # 2. Obtener almacén y ubicación de stock
    warehouses = models.execute_kw(args.db, uid, args.key, 'stock.warehouse', 'search_read', [[]], {'fields': ['name', 'lot_stock_id'], 'limit': 1})
    if not warehouses:
        print("[ERROR] No se encontró almacén en la base de datos.")
        sys.exit(1)
    
    loc_id = warehouses[0]['lot_stock_id'][0]
    loc_name = warehouses[0]['lot_stock_id'][1]
    print(f"Ubicación destino: {loc_name} (ID: {loc_id})")

    # 3. Leer archivo
    if not os.path.exists(args.file):
        print(f"[ERROR] No existe el archivo: {args.file}")
        sys.exit(1)

    items = []
    with open(args.file, mode='r', encoding='utf-8-sig', errors='replace') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=2):
            code = (row.get('code') or row.get('código') or row.get('codigo') or '').strip()
            name = (row.get('name') or row.get('nombre') or '').strip()
            qty_raw = (row.get('qty') or row.get('cantidad') or '0').strip().replace(',', '.')
            if not code:
                continue
            try:
                qty = float(qty_raw)
            except ValueError:
                qty = 0.0

            if not args.all_qty and qty <= 0:
                continue

            items.append({'code': code, 'name': name, 'qty': qty, 'line': idx})

    print(f"Registros a procesar: {len(items)}")

    # 4. Agrupar duplicados
    grouped = {}
    for it in items:
        c = it['code']
        if c in grouped:
            grouped[c]['qty'] += it['qty']
        else:
            grouped[c] = dict(it)

    print(f"Códigos únicos: {len(grouped)}")

    # 5. Buscar productos en Odoo
    codes = list(grouped.keys())
    batch_size = 500
    products_by_code = {}

    print("Consultando productos en Odoo...")
    for i in range(0, len(codes), batch_size):
        chunk = codes[i:i + batch_size]
        res = models.execute_kw(
            args.db, uid, args.key, 'product.product', 'search_read',
            [['|', ('barcode', 'in', chunk), ('default_code', 'in', chunk)]],
            {'fields': ['id', 'display_name', 'barcode', 'default_code', 'type', 'is_storable', 'active'], 'context': {'active_test': False}}
        )
        for p in res:
            if p.get('barcode'):
                products_by_code[p['barcode']] = p
            if p.get('default_code'):
                products_by_code[p['default_code']] = p

    matched = []
    not_found = []
    non_storable = []

    for code, it in grouped.items():
        if code in products_by_code:
            p = products_by_code[code]
            # Validar storable
            is_storable = p.get('is_storable') if 'is_storable' in p else (p.get('type') == 'product')
            if not is_storable:
                non_storable.append((code, p['display_name']))
            else:
                matched.append((p, it['qty']))
        else:
            not_found.append((code, it['name'], it['qty']))

    print(f"\nResumen de Validación:")
    print(f" - Coincidentes almacenables: {len(matched)}")
    print(f" - No encontrados en Odoo: {len(not_found)}")
    print(f" - No almacenables (omitidos): {len(non_storable)}")

    if not_found:
        print("\nEjemplos de códigos no encontrados:")
        for nf in not_found[:10]:
            print(f"   * Código: {nf[0]} | {nf[1]} | Qty: {nf[2]}")

    if dry_run:
        print("\n" + "=" * 80)
        print(" [DRY-RUN COMPLETADO] Modo simulación finalizado. No se realizaron cambios.")
        print(" Para aplicar los cambios reales en producción/staging ejecuta:")
        print(f"   python {os.path.basename(__file__)} --commit --key <TU_API_KEY>")
        print("=" * 80)
        return

    # 6. Modo Commit: Crear / Escribir stock.quant
    print("\nCreando / actualizando stock.quant...")
    quant_ids = []
    for idx, (p, qty) in enumerate(matched, start=1):
        # Buscar quant
        existing = models.execute_kw(
            args.db, uid, args.key, 'stock.quant', 'search',
            [[
                ('product_id', '=', p['id']),
                ('location_id', '=', loc_id),
                ('lot_id', '=', False),
                ('package_id', '=', False),
                ('owner_id', '=', False),
            ]],
            {'limit': 1}
        )

        if existing:
            q_id = existing[0]
            models.execute_kw(
                args.db, uid, args.key, 'stock.quant', 'write',
                [[q_id], {'inventory_quantity': qty}],
                {'context': {'inventory_mode': True}}
            )
        else:
            q_id = models.execute_kw(
                args.db, uid, args.key, 'stock.quant', 'create',
                [{
                    'product_id': p['id'],
                    'location_id': loc_id,
                    'inventory_quantity': qty,
                }],
                {'context': {'inventory_mode': True}}
            )
        quant_ids.append(q_id)

        if idx % 100 == 0 or idx == len(matched):
            print(f"   Progreso quants: {idx} / {len(matched)}")

    # 7. Confirmar ajustes (action_apply_inventory)
    print("\nAplicando ajustes de inventario...")
    batch_apply = args.batch_size
    for i in range(0, len(quant_ids), batch_apply):
        chunk_ids = quant_ids[i:i + batch_apply]
        models.execute_kw(
            args.db, uid, args.key, 'stock.quant', 'action_apply_inventory',
            [chunk_ids]
        )
        print(f"   Lote confirmado: {min(i + batch_apply, len(quant_ids))} / {len(quant_ids)}")

    print("\n" + "=" * 80)
    print(" [OK] INVENTARIO CONFIRMADO EXITOSAMENTE VÍA XML-RPC")
    print("=" * 80)


if __name__ == '__main__':
    main()
