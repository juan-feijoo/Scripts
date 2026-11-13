# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT DE PRUEBA Y AUDITORÍA DE PRECIOS POR LÍNEA
Tarea: KP-9 - Prueba de cálculo de precios con múltiples listas
================================================================================
Uso en Odoo.sh:
  odoo-bin shell -d $PGDATABASE --no-http --log-level=warn < scripts/02_test_calculo_lista_linea.py
"""

from datetime import datetime

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def auditar_listas_y_precios(env):
    log("=" * 80)
    log("AUDITORÍA DE LISTAS DE PRECIOS DISPONIBLES EN EL SISTEMA")
    log("=" * 80)

    Pricelist = env['product.pricelist']
    Product = env['product.product']

    pricelists = Pricelist.search([])
    log(f"Total de listas de precios configuradas: {len(pricelists)}")
    for pl in pricelists:
        log(f"  * [ID: {pl.id}] {pl.name} (Moneda: {pl.currency_id.name}) - Reglas activas: {len(pl.item_ids)}")

    # Buscar un producto testigo (ej. marcador 38550 / 38552 o repuesto 37303)
    sample_codes = ['38550', '38552', '37303', '1051']
    test_product = False
    for code in sample_codes:
        prod = Product.search([('default_code', '=', code)], limit=1)
        if prod:
            test_product = prod
            break

    if not test_product:
        test_product = Product.search([('sale_ok', '=', True)], limit=1)

    if not test_product:
        log("No se encontraron productos para probar.")
        return

    log("\n" + "=" * 80)
    log(f"PRUEBA DE PRECIOS TESTIGO CON PRODUCTO: [{test_product.default_code}] {test_product.name}")
    log(f"Costo estándar (standard_price): ${test_product.standard_price:.2f}")
    log(f"Precio venta base (list_price):   ${test_product.list_price:.2f}")
    log("=" * 80)

    print(f"{'ID':<5} | {'Nombre Lista':<35} | {'Precio Unit. Calculado':<22} | {'Margen s/Costo':<15}")
    print("-" * 85)

    for pl in pricelists:
        try:
            precio = pl._get_product_price(test_product, 1.0, uom=test_product.uom_id)
            margen_pct = ((precio - test_product.standard_price) / test_product.standard_price * 100) if test_product.standard_price else 0.0
            print(f"{pl.id:<5} | {pl.name[:35]:<35} | ${precio:>20.2f} | {margen_pct:>13.1f}%")
        except Exception as e:
            print(f"{pl.id:<5} | {pl.name[:35]:<35} | ERROR: {str(e)[:30]}")

    log("=" * 80)

if 'env' in locals():
    auditar_listas_y_precios(env)
else:
    print("[ERROR] Ejecutar dentro de odoo-bin shell.")
