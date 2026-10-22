# -*- coding: utf-8 -*-
"""
Script de Verificación y Simulación: Evaluación de Reglas Analíticas
===================================================================
Entorno: Odoo 17.0+e (Odoo.sh) - Base: outsourcearg-lafrancisca-prueba-40142666
Calibrado con datos de Auditoría (Categoría PASTAS ID: 254)

Objetivo:
  Simular la creación de líneas de facturación en memoria para comprobar que:
  1. Venta de producto estándar -> Aplica analítica de la Sucursal.
  2. Venta de producto de pastas -> Aplica analítica de Sucursal + Fábrica de Pastas.
  
Seguridad:
  Ejecuta ROLLBACK garantizado. No impacta en la base de datos.
"""

import logging

_logger = logging.getLogger("odoo.analytic.test")

PASTAS_CATEGORY_ID = 254

def simulate_analytic_distribution(env):
    print("=" * 80)
    print(" SIMULACIÓN DE EVALUACIÓN DE DISTRIBUCIÓN ANALÍTICA EN FACTURAS")
    print(f" Base de Datos: {env.cr.dbname}")
    print("=" * 80)

    # 1. Probar en SUC. ARENALES (ID: 2) y en SUC. RAGONE (ID: 3)
    test_companies = env['res.company'].sudo().browse([2, 3]).filtered(lambda c: c.exists())
    if not test_companies:
        test_companies = env['res.company'].sudo().search([('parent_id', '!=', False)], limit=2)

    pastas_category = env['product.category'].sudo().browse(PASTAS_CATEGORY_ID)
    if not pastas_category.exists():
        print(f"[ERROR] Categoría Pastas ID {PASTAS_CATEGORY_ID} no encontrada.")
        return

    # Buscar un producto de Pastas y uno No-Pastas
    pasta_product = env['product.product'].sudo().search([
        ('categ_id', 'child_of', pastas_category.id)
    ], limit=1)

    other_product = env['product.product'].sudo().search([
        ('categ_id', 'not child_of', pastas_category.id),
        ('type', '!=', 'service')
    ], limit=1)

    print(f"[*] Producto Pastas   : {pasta_product.display_name if pasta_product else 'No encontrado'} (ID: {pasta_product.id if pasta_product else '-'})")
    print(f"[*] Producto Estándar : {other_product.display_name if other_product else 'No encontrado'} (ID: {other_product.id if other_product else '-'})")
    print("-" * 80)

    partner = env['res.partner'].sudo().search([('customer_rank', '>', 0)], limit=1)
    if not partner:
        partner = env['res.partner'].sudo().search([], limit=1)

    for company in test_companies:
        print(f"\n>> PROBANDO EN EMPRESA: [{company.id}] {company.name}")

        # PRUEBA A: Producto Estándar
        if other_product:
            move_std = env['account.move'].with_company(company).new({
                'move_type': 'out_invoice',
                'company_id': company.id,
                'partner_id': partner.id,
                'invoice_line_ids': [
                    (0, 0, {
                        'product_id': other_product.id,
                        'quantity': 1.0,
                        'price_unit': 1500.0,
                    })
                ]
            })
            line_std = move_std.invoice_line_ids[0]
            line_std._compute_analytic_distribution()
            print(f"  [A] Venta Estándar ('{other_product.name}')")
            print(f"      -> analytic_distribution computado: {line_std.analytic_distribution}")

        # PRUEBA B: Producto Pastas
        if pasta_product:
            move_pasta = env['account.move'].with_company(company).new({
                'move_type': 'out_invoice',
                'company_id': company.id,
                'partner_id': partner.id,
                'invoice_line_ids': [
                    (0, 0, {
                        'product_id': pasta_product.id,
                        'quantity': 1.0,
                        'price_unit': 2500.0,
                    })
                ]
            })
            line_pasta = move_pasta.invoice_line_ids[0]
            line_pasta._compute_analytic_distribution()
            print(f"  [B] Venta de Pastas ('{pasta_product.name}')")
            print(f"      -> analytic_distribution computado: {line_pasta.analytic_distribution}")

    print("\n" + "=" * 80)
    print(" FIN DE SIMULACIÓN (Transacción revertida - Rollback ejecutado)")
    print("=" * 80)
    env.cr.rollback()


# Punto de entrada para ejecución en Odoo Shell
if 'env' in locals() or 'env' in globals():
    simulate_analytic_distribution(env)
else:
    print("[!] Este script debe ejecutarse dentro de la shell de Odoo (odoo-bin shell).")
