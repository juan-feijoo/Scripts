# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT PARA CARGAR TODAS LAS LISTAS DE PRECIOS CON PRODUCTOS EXPLÍCITOS
Optimizado para Odoo.sh con CONTROL ESTRICTO DE MEMORIA RAM (Anti-OOM Killer)
- Limpieza de cache ORM (env.invalidate_all / env.flush_all) por lote
- Soporte para transacciones por lista
================================================================================
"""

import os
import sys
import gc
import json
from datetime import datetime

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
DRY_RUN = True           # True: Simulación con ROLLBACK | False: Escritura con COMMIT
CHUNK_SIZE = 500         # Tamaño de lote para inserción masiva
JSON_FILE = "todas_las_listas_preparadas.json"

# Listas a procesar (puedes comentar cualquiera si no la necesitas)
LISTAS_ACTIVAS = [
    'lista_min1',   # Minorista 1 (Predeterminada ARS - 3.747 clientes)
    'lista_min2',   # Minorista 2 (ARS - 70 clientes)
    'lista_may',    # Mayorista (ARS - 26 clientes)
    'lista_usd',    # Dólares (USD - 972 productos)
    'lista_min3',   # Minorista 3 (ARS - 2 clientes)
]

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def limpiar_memoria(env):
    """Libera la cache del ORM y memoria Python para evitar el OOM Killer en Odoo.sh"""
    try:
        env.flush_all()
    except:
        pass
    try:
        env.invalidate_all()
    except:
        try:
            env.cache.clear()
        except:
            pass
    gc.collect()

def ejecutar(env):
    log("=" * 80)
    log("CARGA INTEGRAL DE LISTAS DE PRECIOS Y PRODUCTOS EN ODOO ENTERPRISE")
    log(f"Modo: {'*** DRY-RUN (SIMULACIÓN - ROLLBACK FINAL) ***' if DRY_RUN else '*** PRODUCCIÓN (COMMIT DEFINITIVO) ***'}")
    log(f"Base de Datos: {env.cr.dbname} | Compañía: {env.company.name}")
    log("=" * 80)

    # 1. Rollback preventivo
    try:
        env.cr.rollback()
    except:
        pass

    # 2. Cargar datos
    if not os.path.exists(JSON_FILE):
        log(f"ERROR: No existe {JSON_FILE}. Ejecuta primero 'python preparar_todas_las_listas.py'.")
        return

    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        listas_dict = json.load(f)

    Pricelist = env['product.pricelist']
    PricelistItem = env['product.pricelist.item']
    ProductTemplate = env['product.template']
    Currency = env['res.currency']

    item_fields = set(PricelistItem._fields.keys())
    def clean_item(vals):
        return {k: v for k, v in vals.items() if k in item_fields}

    currency_ars = env.company.currency_id
    currency_usd = Currency.search([('name', '=', 'USD')], limit=1) or env.ref('base.USD')
    if currency_usd and not currency_usd.active:
        currency_usd.active = True

    # 3. Cache de productos por default_code
    log("Indexando productos existentes...")
    prods = ProductTemplate.search_read([('default_code', '!=', False)], ['id', 'default_code'])
    prod_cache = {p['default_code']: p['id'] for p in prods}
    log(f"-> {len(prod_cache)} productos indexados.")
    del prods
    limpiar_memoria(env)

    # Idiomas activos para guardar traducciones
    active_langs = env['res.lang'].search([('active', '=', True)])

    resumen_final = []

    # 4. Procesar cada lista
    for l_key in LISTAS_ACTIVAS:
        if l_key not in listas_dict:
            continue
        l_data = listas_dict[l_key]
        nombre = l_data['nombre']
        moneda_code = l_data['moneda']
        es_predeterminada = l_data.get('es_predeterminada', False)
        items = l_data['items']

        curr = currency_usd if moneda_code == 'USD' else currency_ars

        log(f"\n--- Procesando: '{nombre}' ({len(items)} productos) ---")

        # Buscar o crear la lista
        if es_predeterminada:
            lista = Pricelist.search([
                ('company_id', 'in', [env.company.id, False]),
                ('currency_id', '=', curr.id)
            ], order='id asc', limit=1)
            if not lista:
                lista = Pricelist.create({'name': nombre, 'currency_id': curr.id, 'company_id': env.company.id})
            for lang in active_langs:
                lista.with_context(lang=lang.code).write({'name': nombre})
        else:
            lista = Pricelist.search([
                ('name', '=', nombre),
                ('currency_id', '=', curr.id)
            ], limit=1)
            if not lista:
                lista = Pricelist.create({'name': nombre, 'currency_id': curr.id, 'company_id': env.company.id})
            for lang in active_langs:
                lista.with_context(lang=lang.code).write({'name': nombre})

        log(f"  -> Lista ID: {lista.id} ('{lista.name}')")

        # Si es la lista USD, asegurar regla global
        if moneda_code == 'USD':
            regla_glob = PricelistItem.search([('pricelist_id', '=', lista.id), ('applied_on', '=', '3_global')], limit=1)
            if not regla_glob:
                PricelistItem.create(clean_item({
                    'pricelist_id': lista.id,
                    'applied_on': '3_global',
                    'compute_price': 'formula',
                    'base': 'list_price'
                }))

        # Cache de reglas existentes en la lista
        existing_items = PricelistItem.search([
            ('pricelist_id', '=', lista.id),
            ('applied_on', '=', '1_product')
        ])
        existing_map = {item.product_tmpl_id.id: item for item in existing_items}
        log(f"  -> Reglas existentes en lista: {len(existing_map)}")

        to_create = []
        actualizados = 0

        for it in items:
            code = it['default_code']
            tmpl_id = prod_cache.get(code)
            if not tmpl_id:
                continue

            precio_fijo = it['precio']
            if tmpl_id in existing_map:
                existing_map[tmpl_id].write({'fixed_price': precio_fijo, 'compute_price': 'fixed'})
                actualizados += 1
            else:
                to_create.append(clean_item({
                    'pricelist_id': lista.id,
                    'applied_on': '1_product',
                    'product_tmpl_id': tmpl_id,
                    'compute_price': 'fixed',
                    'fixed_price': precio_fijo
                }))

        # Inserción masiva en lotes liberando memoria en cada paso
        log(f"  -> Insertando {len(to_create)} nuevas reglas en lotes de {CHUNK_SIZE} con limpieza de RAM...")
        for i in range(0, len(to_create), CHUNK_SIZE):
            chunk = to_create[i:i + CHUNK_SIZE]
            PricelistItem.create(chunk)
            limpiar_memoria(env)
            log(f"     ... {min(i + CHUNK_SIZE, len(to_create))}/{len(to_create)} reglas creadas.")

        total_reglas = len(to_create) + actualizados
        log(f"  -> Completado: {len(to_create)} creadas, {actualizados} actualizadas. Total en lista: {total_reglas}")
        
        resumen_final.append({
            'nombre': nombre,
            'id': lista.id,
            'moneda': moneda_code,
            'reglas': total_reglas
        })

        # Si estamos en modo Producción, confirmamos por cada lista para liberar WAL de Postgres
        if not DRY_RUN:
            env.cr.commit()
            log(f"  [COMMIT] Lista '{nombre}' guardada definitivamente.")

        limpiar_memoria(env)

    # 5. Resumen
    log("\n" + "=" * 80)
    log("RESUMEN GENERAL DE LISTAS Y PRODUCTOS CARGADOS")
    for r in resumen_final:
        log(f"- ID {r['id']:<2} | {r['nombre']:<45} | Moneda: {r['moneda']:<4} | Reglas: {r['reglas']}")
    log("=" * 80)

    if DRY_RUN:
        env.cr.rollback()
        log("\n>>> MODO DRY-RUN: Transacción REVERTIDA (ROLLBACK). Ningún dato fue modificado en la base. <<<")
        log("Para aplicar definitivamente en producción, establece 'DRY_RUN = False' y vuelve a ejecutar.\n")
    else:
        log("\n>>> MODO PRODUCCIÓN: Todas las listas fueron confirmadas (COMMIT) exitosamente. <<<\n")

if 'env' in locals():
    ejecutar(env)
else:
    print("[INFO] Ejecutar en Odoo Shell: python3 odoo-bin shell -d <bd> < cargar_todas_las_listas_shell.py")
