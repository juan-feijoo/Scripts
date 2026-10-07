# -*- coding: utf-8 -*-
"""
Script para solucionar y segregar secuencias de Órdenes de Compra (purchase.order) por Compañía.
Soporta Odoo 17.0+e, 18.0+e, 19.0+e.

Ejecución en Odoo Shell:
  odoo-bin shell -c <config> -d <database> < fix_purchase_sequences.py
"""

# ==============================================================================
# CONFIGURACIÓN DE EJECUCIÓN
# ==============================================================================
DRY_RUN = False  # ⬅️ Déjalo en True para simular; pon en False para aplicar cambios definitivos en BD

# Prefijos recomendados siguiendo la convención estándar Odoo ('P' para Compras):
COMPANY_CONFIG_PURCHASE = {
    1: {'prefix': 'P',     'padding': 5, 'name': 'Eco Norte (Mantiene histórica)'}, # Próximo continuará en 78280
    6: {'prefix': 'GT-P',  'padding': 5, 'next_num': 1, 'name': 'Greentek'},
    2: {'prefix': 'SP-P',  'padding': 5, 'next_num': 1, 'name': 'Sucursal Partidarios'},
    4: {'prefix': 'S10-P', 'padding': 5, 'next_num': 1, 'name': 'Sucursal 10 de Octubre'},
    5: {'prefix': 'SJ-P',  'padding': 5, 'next_num': 1, 'name': 'Sucursal Jujuy (ID 5)'},
    9: {'prefix': 'SJ2-P', 'padding': 5, 'next_num': 1, 'name': 'Sucursal Jujuy (ID 9)'},
}

BASE_SEQUENCE_ID = 12  # ID de la secuencia compartida actual encontrada en la auditoría

# ==============================================================================

print("\n" + "=" * 70)
print(f" SEPARACIÓN DE SECUENCIAS DE COMPRAS MULTI-COMPAÑÍA (DRY_RUN = {DRY_RUN})")
print("=" * 70)

base_seq = env['ir.sequence'].browse(BASE_SEQUENCE_ID)
if not base_seq.exists():
    raise ValueError(f"No se encontró la secuencia base ID {BASE_SEQUENCE_ID}.")

# 1. Inspeccionar secuencia base
print(f"\n[1] Secuencia Base actual (ID {base_seq.id}):")
print(f"    - Código: {base_seq.code} | Nombre: {base_seq.name}")
print(f"    - Prefijo: '{base_seq.prefix}' | Próx: {base_seq.number_next_actual} | Padding: {base_seq.padding}")
print(f"    - Acción: Se asignará a [{env['res.company'].browse(1).id}] {env['res.company'].browse(1).name}")

# 2. Plan por compañía
print("\n[2] Plan de creación de secuencias independientes de Compras:")
for comp_id, conf in COMPANY_CONFIG_PURCHASE.items():
    if comp_id == 1:
        continue
    comp = env['res.company'].browse(comp_id)
    if not comp.exists():
        print(f"  ⚠️ Compañía ID {comp_id} no encontrada en la base de datos.")
        continue

    existing = env['ir.sequence'].search([
        ('code', '=', 'purchase.order'),
        ('company_id', '=', comp_id)
    ], limit=1)

    if existing:
        print(f"  - [{comp.id}] {comp.name}: Ya posee secuencia ID {existing.id} (Prefijo: '{existing.prefix}', Próx: {existing.number_next_actual})")
    else:
        print(f"  - [{comp.id}] {comp.name}: Se creará con Prefijo: '{conf['prefix']}' | Inicia en: {conf['next_num']} (Ej: '{conf['prefix']}{str(conf['next_num']).zfill(conf['padding'])}')")

# 3. Aplicación de cambios
if DRY_RUN:
    print("\n" + "=" * 70)
    print(" ⚠️  MODO DRY-RUN ACTIVADO: NO SE APLICARON CAMBIOS EN LA BASE DE DATOS.")
    print(" Para aplicar los cambios reales, cambia 'DRY_RUN = False' y vuelve a ejecutar.")
    print("=" * 70 + "\n")
else:
    print("\n" + "=" * 70)
    print(" 🚀 APLICANDO CAMBIOS EN BASE DE DATOS...")
    print("=" * 70)

    # A. Asignar la secuencia base a Eco Norte (ID 1)
    base_seq.write({
        'company_id': 1,
        'name': f"Purchase Order - {env['res.company'].browse(1).name}",
        'prefix': COMPANY_CONFIG_PURCHASE[1]['prefix'],
    })
    print(f"  ✔ Secuencia base ID {BASE_SEQUENCE_ID} asignada exclusivamente a ECO NORTE SRL.")

    # B. Crear secuencias independientes para las demás compañías
    for comp_id, conf in COMPANY_CONFIG_PURCHASE.items():
        if comp_id == 1:
            continue
        comp = env['res.company'].browse(comp_id)
        if not comp.exists():
            continue

        existing = env['ir.sequence'].search([
            ('code', '=', 'purchase.order'),
            ('company_id', '=', comp_id)
        ], limit=1)

        if existing:
            print(f"  ℹ Compañía [{comp.id}] {comp.name} ya cuenta con la secuencia ID {existing.id}. Omitiendo.")
            continue

        new_seq = env['ir.sequence'].create({
            'name': f"Purchase Order - {comp.name}",
            'code': 'purchase.order',
            'prefix': conf['prefix'],
            'padding': conf['padding'],
            'number_next': conf['next_num'],
            'number_increment': 1,
            'company_id': comp_id,
            'implementation': 'standard',
        })
        print(f"  ✔ Creada secuencia ID {new_seq.id} para [{comp.id}] {comp.name} con prefijo '{conf['prefix']}'")

    env.cr.commit()
    print("\n✅ CAMBIOS CONFIRMADOS Y APLICADOS EN BASE DE DATOS (COMMIT EXITOSO).")
    print("=" * 70 + "\n")
