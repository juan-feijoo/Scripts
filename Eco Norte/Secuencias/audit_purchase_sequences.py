# -*- coding: utf-8 -*-
"""
Script de Auditoría para secuencias de Órdenes de Compra (purchase.order).
Soporta Odoo 17.0+e, 18.0+e, 19.0+e.

Ejecución en Odoo Shell:
  odoo-bin shell -c <config> -d <database> < audit_purchase_sequences.py
"""

print("\n" + "=" * 65)
print(" INICIANDO AUDITORÍA DE SECUENCIAS DE COMPRAS (PURCHASE.ORDER)")
print("=" * 65 + "\n")

# 1. Compañías activas
companies = env['res.company'].search([])
print(f"📍 Compañías Activas en la BD ({len(companies)}):")
for comp in companies:
    print(f"  - ID: {comp.id} | Nombre: {comp.name}")

# 2. Secuencias existentes para 'purchase.order'
sequences = env['ir.sequence'].search([('code', '=', 'purchase.order')])
print(f"\n📍 Secuencias encontradas para 'purchase.order' ({len(sequences)}):")
for seq in sequences:
    company_name = seq.company_id.name if seq.company_id else 'COMPARTIDA (Sin Compañía Asignada)'
    print(f"  - ID: {seq.id} | Nombre: {seq.name} | Prefijo: '{seq.prefix}' | Próx: {seq.number_next_actual} | Compañía: {company_name}")

# 3. Analizar las últimas 15 Órdenes de Compra registradas
print("\n📍 Análisis de las últimas 15 Órdenes de Compra (Ordenadas por creación):")
purchases = env['purchase.order'].search([], order='create_date desc', limit=15)
if purchases:
    for po in purchases:
        print(f"  - Creada: {po.create_date.strftime('%Y-%m-%d %H:%M:%S')} | OC: {po.name:<10} | Compañía: {po.company_id.name} | Estado: {po.state}")
else:
    print("  (No hay órdenes de compra registradas en el sistema aún)")

# 4. Diagnóstico
print("\n" + "=" * 65)
print(" RESULTADO DEL DIAGNÓSTICO (DRY-RUN)")
print("=" * 65)

shared_sequences = sequences.filtered(lambda s: not s.company_id)
if shared_sequences:
    print("\n🚨 PROBLEMA DETECTADO: Tienes secuencias de compra sin compañía asignada (Compartidas).")
    print("   Las compras de distintas empresas están compartiendo la misma numeración.")

if len(sequences) < len(companies):
    print(f"\n⚠️ ADVERTENCIA: Hay menos secuencias ({len(sequences)}) que compañías ({len(companies)}).")

print("\n" + "=" * 65)
print(" FIN DE LA AUDITORÍA DE COMPRAS")
print("=" * 65 + "\n")
