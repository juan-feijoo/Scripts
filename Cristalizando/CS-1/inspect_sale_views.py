# -*- coding: utf-8 -*-
"""
Script para inspeccionar todas las vistas heredadas de sale.order.form
y revisar exactamente el contenido XML de la vista Studio 3922 y la página 'Detalles Técnicos'.
"""
print("=" * 80)
print("INSPECCIÓN DETALLADA DE VISTAS DE sale.order")
print("=" * 80)

# 1. Inspeccionar la vista 3922 completa
v3922 = env['ir.ui.view'].browse(3922)
print(f"\n--- CONTENIDO COMPLETO DE VISTA 3922 ({v3922.name}) ---")
print(v3922.arch_db)

# 2. Buscar qué vista agregó la página "Detalles Técnicos"
print("\n--- BUSCANDO VISTA QUE AGREGA 'Detalles Técnicos' ---")
views_detalles = env['ir.ui.view'].search([
    ('model', '=', 'sale.order'),
    ('arch_db', 'ilike', 'Detalles Técnicos')
])
for v in views_detalles:
    print(f"ID: {v.id} | Nombre: {v.name} | XML ID: {v.xml_id} | Activa: {v.active}")

# 3. Listar todas las vistas heredadas activas de sale.order.form
print("\n--- TODAS LAS VISTAS HEREDADAS ACTIVAS DE sale.view_order_form ---")
sale_form = env.ref('sale.view_order_form')
inherited = env['ir.ui.view'].search([
    ('model', '=', 'sale.order'),
    ('inherit_id', '=', sale_form.id),
    ('active', '=', True)
], order='priority, id')

for v in inherited:
    has_studio = 'studio' in (v.xml_id or '').lower() or 'Studio' in (v.name or '')
    print(f"ID: {v.id:5d} | Prio: {v.priority:3d} | Studio: {'SÍ' if has_studio else 'NO':2s} | Nombre: {v.name} ({v.xml_id})")
