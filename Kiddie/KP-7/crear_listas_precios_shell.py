# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT DE LISTAS DE PRECIOS CON LOG ULTRA-DETALLADO Y CONTROL DE LOCKS
Versiones soportadas: 17.0+e, 18.0+e, 19.0+e Enterprise
================================================================================
"""

import os
import sys
import json
import logging
from datetime import datetime

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
DRY_RUN = False                   # True: Simulación con ROLLBACK | False: Escritura con COMMIT
CREAR_LISTA_USD = True           # Crear lista en Dólares con los 972 productos dolarizados
CREAR_LISTA_MAYORISTA = False    # Dejar en False para máxima velocidad
RENOMBRAR_PREDETERMINADA = True  # Renombrar lista pública
CHUNK_SIZE = 250                 # Lotes pequeños para reporte continuo

JSON_LISTAS = "listas_precios_preparadas.json"
LOG_FILE = "listas_precios_shell.log"

# Configurar logger de Odoo y consola
_logger = logging.getLogger("odoo.migracion_listas")
_logger.setLevel(logging.INFO)

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except:
        pass

def ejecutar_creacion_listas(env):
    log("=" * 80)
    log("INICIANDO CONFIGURACIÓN DE LISTAS DE PRECIOS EN ODOO ENTERPRISE")
    log(f"Modo: {'*** DRY-RUN (SIMULACIÓN - ROLLBACK FINAL) ***' if DRY_RUN else '*** PRODUCCIÓN (COMMIT DEFINITIVO) ***'}")
    log(f"Base de Datos: {env.cr.dbname}")
    log(f"Compañía: {env.company.name} (ID: {env.company.id})")
    log("=" * 80)

    # --------------------------------------------------------------------------
    # 0. Limpieza previa de transacción (evita bloqueos o transacciones abortadas)
    # --------------------------------------------------------------------------
    log("[PASO 0] Limpiando estado de transacción (rollback preventivo)...")
    try:
        env.cr.rollback()
        log("  -> Transacción reiniciada limpiamente.")
    except Exception as e:
        log(f"  [AVISO] No se pudo hacer rollback inicial: {e}")

    # Verificar si hay sesiones bloqueantes en PostgreSQL
    try:
        env.cr.execute("""
            SELECT pid, state, query, age(clock_timestamp(), query_start)
            FROM pg_stat_activity
            WHERE state != 'idle' 
              AND pid != pg_backend_pid()
              AND query ILIKE '%product_pricelist%'
            LIMIT 5;
        """)
        bloqueos = env.cr.fetchall()
        if bloqueos:
            log(f"  [ATENCIÓN] Hay {len(bloqueos)} consultas concurrentes bloqueando product_pricelist:")
            for b in bloqueos:
                pid = b[0]
                duracion = b[3]
                log(f"    * PID {pid} (duración: {duracion}) -> Liberando bloqueo (terminando sesión colgada)...")
                try:
                    env.cr.execute("SELECT pg_terminate_backend(%s);", (pid,))
                    log(f"      -> PID {pid} terminado exitosamente.")
                except Exception as ex_term:
                    log(f"      [AVISO] No se pudo terminar PID {pid}: {ex_term}")
            env.cr.rollback()
            log("  -> Bloqueos liberados. Continuando...")
    except Exception as e:
        log(f"  (Verificación de bloqueos omitida: {e})")

    if not os.path.exists(JSON_LISTAS):
        log(f"ERROR: No se encuentra '{JSON_LISTAS}'.")
        return

    with open(JSON_LISTAS, 'r', encoding='utf-8') as f:
        data_listas = json.load(f)

    Pricelist = env['product.pricelist']
    PricelistItem = env['product.pricelist.item']
    ProductTemplate = env['product.template']
    Currency = env['res.currency']

    item_fields = set(PricelistItem._fields.keys())
    def clean_item_vals(vals):
        return {k: v for k, v in vals.items() if k in item_fields}

    # --------------------------------------------------------------------------
    # 1. Monedas
    # --------------------------------------------------------------------------
    log("\n[PASO 1/4] Verificando Monedas en el Sistema...")
    currency_ars = env.company.currency_id
    currency_usd = Currency.search([('name', '=', 'USD')], limit=1)

    if not currency_usd:
        try:
            currency_usd = env.ref('base.USD')
        except:
            pass

    if currency_usd and not currency_usd.active:
        log("  -> Activando moneda USD en el sistema...")
        currency_usd.active = True

    log(f"  -> Moneda Base: {currency_ars.name} (ID: {currency_ars.id})")
    log(f"  -> Moneda USD:  {currency_usd.name if currency_usd else 'NO ENCONTRADA'} (ID: {currency_usd.id if currency_usd else 'N/A'})")

    if not currency_usd and CREAR_LISTA_USD:
        log("ERROR CRÍTICO: No se encontró la moneda USD.")
        return

    # --------------------------------------------------------------------------
    # 2. Indexación de productos
    # --------------------------------------------------------------------------
    log("\n[PASO 2/4] Indexando productos en memoria...")
    prods = ProductTemplate.search_read([('default_code', '!=', False)], ['id', 'default_code', 'name'])
    prod_cache = {p['default_code']: p['id'] for p in prods}
    log(f"  -> {len(prod_cache)} productos indexados por default_code.")

    # --------------------------------------------------------------------------
    # 3. Lista Predeterminada (ARS)
    # --------------------------------------------------------------------------
    log("\n[PASO 3/4] Gestionando Lista de Precios Predeterminada (ARS)...")
    lista_default = Pricelist.search([
        ('company_id', 'in', [env.company.id, False]),
        ('currency_id', '=', currency_ars.id)
    ], order='id asc', limit=1)

    if lista_default:
        if RENOMBRAR_PREDETERMINADA:
            nuevo_nombre = "Lista Predeterminada - Minorista 1 (ARS)"
            # Actualizar en todos los idiomas activos (es_AR, es_ES, en_US)
            for lang in env['res.lang'].search([('active', '=', True)]):
                lista_default.with_context(lang=lang.code).write({'name': nuevo_nombre})
            log(f"  -> Lista predeterminada (ID: {lista_default.id}) renombrada en todos los idiomas a '{nuevo_nombre}'.")
    else:
        lista_default = Pricelist.create({
            'name': 'Lista Predeterminada - Minorista 1 (ARS)',
            'currency_id': currency_ars.id,
            'company_id': env.company.id
        })
        log(f"  + Lista predeterminada creada (ID: {lista_default.id}).")

    # --------------------------------------------------------------------------
    # 4. Lista en Dólares (USD)
    # --------------------------------------------------------------------------
    total_reglas_usd = 0
    if CREAR_LISTA_USD:
        log("\n[PASO 4/4] Configurando 'Lista de Precios en Dólares (USD)'...")
        nombre_usd = "Lista de Precios en Dólares (USD)"
        
        log("  [4.1] Buscando si ya existe la lista USD...")
        lista_usd = Pricelist.search([
            ('name', '=', nombre_usd),
            ('currency_id', '=', currency_usd.id)
        ], limit=1)

        if not lista_usd:
            log("  [4.2] Creando registro de lista de precios USD...")
            lista_usd = Pricelist.create({
                'name': nombre_usd,
                'currency_id': currency_usd.id,
                'company_id': env.company.id
            })
            log(f"  + Lista creada: '{nombre_usd}' (ID: {lista_usd.id})")
        else:
            log(f"  -> Lista existente encontrada: '{nombre_usd}' (ID: {lista_usd.id})")

        # Regla global
        log("  [4.3] Verificando regla global de conversión ARS -> USD...")
        regla_global = PricelistItem.search([
            ('pricelist_id', '=', lista_usd.id),
            ('applied_on', '=', '3_global')
        ], limit=1)

        if not regla_global:
            log("  [4.3.1] Creando regla global de conversión...")
            PricelistItem.create(clean_item_vals({
                'pricelist_id': lista_usd.id,
                'applied_on': '3_global',
                'compute_price': 'formula',
                'base': 'list_price'
            }))
            log("  + Creada regla global de conversión automática de ARS a USD al tipo de cambio.")
        else:
            log("  -> Regla global ya existe.")

        # Items con precio fijo en USD
        items_usd = data_listas['lista_usd']['items']
        log(f"  [4.4] Procesando {len(items_usd)} productos con precio fijo en USD...")

        # Cache de reglas existentes
        existing_items = PricelistItem.search([
            ('pricelist_id', '=', lista_usd.id),
            ('applied_on', '=', '1_product')
        ])
        existing_rules_map = {item.product_tmpl_id.id: item for item in existing_items}
        log(f"  -> Reglas existentes en lista USD: {len(existing_rules_map)}")

        to_create_usd = []
        actualizados_usd = 0

        for item in items_usd:
            numpro = item['default_code']
            tmpl_id = prod_cache.get(numpro)
            if not tmpl_id:
                continue

            p_usd = item['precio_usd']
            if tmpl_id in existing_rules_map:
                existing_rules_map[tmpl_id].write({'fixed_price': p_usd, 'compute_price': 'fixed'})
                actualizados_usd += 1
            else:
                to_create_usd.append(clean_item_vals({
                    'pricelist_id': lista_usd.id,
                    'applied_on': '1_product',
                    'product_tmpl_id': tmpl_id,
                    'compute_price': 'fixed',
                    'fixed_price': p_usd
                }))

        log(f"  [4.5] Insertando {len(to_create_usd)} nuevas reglas en lotes de {CHUNK_SIZE}...")
        for i in range(0, len(to_create_usd), CHUNK_SIZE):
            chunk = to_create_usd[i:i + CHUNK_SIZE]
            PricelistItem.create(chunk)
            log(f"     ... {min(i + CHUNK_SIZE, len(to_create_usd))}/{len(to_create_usd)} reglas USD insertadas.")

        total_reglas_usd = len(to_create_usd) + actualizados_usd
        log(f"  -> Éxito Lista USD: {len(to_create_usd)} creadas, {actualizados_usd} actualizadas.")

    # --------------------------------------------------------------------------
    # RESUMEN Y ROLLBACK/COMMIT
    # --------------------------------------------------------------------------
    log("\n" + "=" * 80)
    log("RESUMEN DE GESTIÓN DE LISTAS DE PRECIOS")
    log(f"- Lista Predeterminada (ARS): ID={lista_default.id} ('{lista_default.name}')")
    if CREAR_LISTA_USD:
        log(f"- Lista en Dólares (USD):      ID={lista_usd.id} ({total_reglas_usd} reglas de precio en USD)")
    log("=" * 80)

    if DRY_RUN:
        env.cr.rollback()
        log("\n>>> MODO DRY-RUN: Transacción REVERTIDA (ROLLBACK). Ningún dato fue modificado en la base. <<<")
        log("Para aplicar definitivamente en producción, establece 'DRY_RUN = False' y vuelve a ejecutar.\n")
    else:
        env.cr.commit()
        log("\n>>> MODO PRODUCCIÓN: Transacción CONFIRMADA (COMMIT). Listas aplicadas exitosamente. <<<\n")

if 'env' in locals():
    ejecutar_creacion_listas(env)
else:
    print("[INFO] Este script está diseñado para ejecutarse dentro de Odoo Shell ('odoo-bin shell').")
