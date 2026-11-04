# -*- coding: utf-8 -*-
"""
================================================================================
PASO 2: CARGA EN ODOO SHELL DE LISTAS DE PRECIOS BASADAS EN COSTO + % MARGEN
Carpeta: v2_listas_y_desglose
Compatible con: Odoo 17.0+e, 18.0+e y 19.0+e Enterprise (Odoo.sh)
================================================================================

CÓMO FUNCIONA:
1. Cada lista de precios (Público, Mayorista, 30 Días, Licitación, Lista 5, Lista 6)
   se configura con reglas de FÓRMULA basadas en el COSTO DEL PRODUCTO:
   - compute_price = 'formula'
   - base = 'standard_price' (Costo)
   - price_discount = -%Margen (ej. -85.0 significa +85% sobre el costo)
   De esta manera, si cambia el costo del producto en Odoo, todas las listas
   actualizan su precio automáticamente respetando su % de margen.

2. La lista 'Desglose - Venta por Unidad (ARS)' calcula automáticamente el precio
   de la unidad suelta dividiendo el costo del bulto por 'uni_bulto' y sumando
   el margen de desglose ('margen7').

3. Incluye control estricto de memoria RAM (env.flush_all / env.invalidate_all)
   para evitar el OOM Killer en Odoo.sh.
"""

import os
import sys
import gc
import json
from datetime import datetime

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
DRY_RUN = False                        # True: Simulación (ROLLBACK) | False: Confirmar (COMMIT)
CHUNK_SIZE = 500                      # Tamaño de lote para inserción masiva
LIMPIAR_LISTAS_PRUEBA_ANTERIORES = True  # Elimina listas de prueba creadas antes (ej. Minorista 2, 3)

# Buscar el JSON tanto en la carpeta actual como en subcarpeta v2_listas_y_desglose
JSON_PATHS = [
    "listas_por_margen_y_desglose.json",
    os.path.join("v2_listas_y_desglose", "listas_por_margen_y_desglose.json")
]

LISTAS_A_PROCESAR = [
    'publico',      # 1. Público (ARS) - Predeterminada (% margenmin1 sobre costo)
    'mayorista',    # 2. Mayorista (ARS) (% margenmin2 sobre costo)
    '30_dias',      # 3. 30 Días (ARS) (% margenmin3 sobre costo)
    'licitacion',   # 4. Licitación (ARS) (% margenmay sobre costo)
    'lista_5',      # 5. Lista 5 (ARS) (% margendis sobre costo)
    'lista_6',      # 6. Lista 6 (ARS) (% margen6 sobre costo)
    'desglose',     # 7. Desglose - Venta por Unidad (ARS) ((Costo / uni_bulto) + % margen7)
    'dolares',      # 8. Lista en Dólares (USD)
]

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def limpiar_memoria(env):
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
    log("CONFIGURACIÓN DE LISTAS DE PRECIOS POR % SOBRE COSTO Y DESGLOSE")
    log(f"Modo: {'*** DRY-RUN (SIMULACIÓN - ROLLBACK) ***' if DRY_RUN else '*** PRODUCCIÓN (COMMIT DEFINITIVO) ***'}")
    log(f"Base de Datos: {env.cr.dbname} | Compañía: {env.company.name}")
    log("=" * 80)

    try:
        env.cr.rollback()
    except:
        pass

    json_file = next((p for p in JSON_PATHS if os.path.exists(p)), None)
    if not json_file:
        log("ERROR: No se encontró 'listas_por_margen_y_desglose.json'.")
        return

    with open(json_file, 'r', encoding='utf-8') as f:
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

    active_langs = env['res.lang'].search([('active', '=', True)])

    # Limpieza opcional de listas creadas con nombres provisorios anteriores
    if LIMPIAR_LISTAS_PRUEBA_ANTERIORES:
        nombres_viejos = [
            'Lista 2 - Minorista 2 (ARS)',
            'Lista 3 - Minorista 3 (ARS)',
            'Lista 4 - Mayorista (ARS)',
            'Lista Minorista 2 (ARS)'
        ]
        viejas = Pricelist.search([('name', 'in', nombres_viejos)])
        if viejas:
            log(f"Limpiando {len(viejas)} listas provisorias anteriores: {viejas.mapped('name')}")
            viejas.unlink()
            limpiar_memoria(env)

    # Indexar productos por default_code
    log("Indexando productos de la base de datos...")
    prods = ProductTemplate.search_read([('default_code', '!=', False)], ['id', 'default_code'])
    prod_cache = {p['default_code']: p['id'] for p in prods}
    log(f"-> {len(prod_cache)} productos indexados.")
    del prods
    limpiar_memoria(env)

    resumen = []

    for l_key in LISTAS_A_PROCESAR:
        if l_key not in listas_dict:
            continue
        l_data = listas_dict[l_key]
        nombre = l_data['nombre']
        moneda_code = l_data['moneda']
        es_predeterminada = l_data.get('es_predeterminada', False)
        items = l_data['items']
        curr = currency_usd if moneda_code == 'USD' else currency_ars

        log(f"\n--- Procesando Lista: '{nombre}' ({len(items)} reglas) ---")

        if es_predeterminada:
            lista = Pricelist.search([
                ('company_id', 'in', [env.company.id, False]),
                ('currency_id', '=', curr.id)
            ], order='id asc', limit=1)
            if not lista:
                lista = Pricelist.create({'name': nombre, 'currency_id': curr.id, 'company_id': env.company.id})
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

        # Limpiar reglas previas de la lista para recargarlas limpias con la fórmula de costo
        reglas_previas = PricelistItem.search([('pricelist_id', '=', lista.id)])
        if reglas_previas:
            log(f"  -> Reemplazando {len(reglas_previas)} reglas previas...")
            reglas_previas.unlink()
            limpiar_memoria(env)

        to_create = []

        if moneda_code == 'USD':
            # Regla global de respaldo para convertir productos en ARS a USD
            to_create.append(clean_item({
                'pricelist_id': lista.id,
                'applied_on': '3_global',
                'compute_price': 'formula',
                'base': 'list_price'
            }))
            for it in items:
                tmpl_id = prod_cache.get(it['default_code'])
                if not tmpl_id:
                    continue
                to_create.append(clean_item({
                    'pricelist_id': lista.id,
                    'applied_on': '1_product',
                    'product_tmpl_id': tmpl_id,
                    'compute_price': 'fixed',
                    'fixed_price': it['precio_usd']
                }))
        else:
            # Listas en ARS basadas en FÓRMULA sobre el COSTO (standard_price)
            for it in items:
                tmpl_id = prod_cache.get(it['default_code'])
                if not tmpl_id:
                    continue
                to_create.append(clean_item({
                    'pricelist_id': lista.id,
                    'applied_on': '1_product',
                    'product_tmpl_id': tmpl_id,
                    'compute_price': 'formula',
                    'base': 'standard_price',
                    'price_discount': it['price_discount']
                }))

        log(f"  -> Insertando {len(to_create)} reglas en bloques de {CHUNK_SIZE}...")
        for i in range(0, len(to_create), CHUNK_SIZE):
            chunk = to_create[i:i + CHUNK_SIZE]
            PricelistItem.create(chunk)
            limpiar_memoria(env)
            log(f"     ... {min(i + CHUNK_SIZE, len(to_create))}/{len(to_create)} reglas insertadas.")

        resumen.append({
            'id': lista.id,
            'nombre': nombre,
            'moneda': moneda_code,
            'reglas': len(to_create)
        })

        if not DRY_RUN:
            env.cr.commit()
            log(f"  [COMMIT] Lista '{nombre}' confirmada en base de datos.")

        limpiar_memoria(env)

    log("\n" + "=" * 80)
    log("RESUMEN DE LISTAS CONFIGURADAS")
    for r in resumen:
        log(f"  * ID {r['id']:<3} | {r['nombre']:<38} | Moneda: {r['moneda']} | Reglas: {r['reglas']}")
    log("=" * 80)

    if DRY_RUN:
        env.cr.rollback()
        log("\n>>> MODO DRY-RUN: Transacción REVERTIDA (ROLLBACK). Ningún dato fue modificado. <<<")
        log("Para aplicar en producción, cambia 'DRY_RUN = False' y vuelve a ejecutar.\n")
    else:
        log("\n>>> MODO PRODUCCIÓN: Todas las listas fueron confirmadas (COMMIT) exitosamente. <<<\n")

if 'env' in locals():
    ejecutar(env)
else:
    print("[INFO] Ejecutar en Odoo Shell: python3 odoo-bin shell -d <bd> < v2_listas_y_desglose/02_cargar_listas_formula_costo_shell.py")

