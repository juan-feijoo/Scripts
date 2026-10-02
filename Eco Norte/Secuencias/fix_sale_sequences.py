# -*- coding: utf-8 -*-
"""
Script para asignar secuencias independientes con prefijos personalizados por Compañía.
Soporta Odoo 17.0+e, 18.0+e, 19.0+e.
"""

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
DRY_RUN = False  # ⬅️ Listo para aplicar cambios definitivos en la base de datos

# Mapa de configuración por Compañía (ID de Compañía: {'prefix': ..., 'padding': ..., 'next_num': ...})
COMPANY_CONFIG = {
    1: {'prefix': 'S',     'padding': 5, 'name': 'Eco Norte (Mantiene histórica)'}, # Próximo número será 1009
    6: {'prefix': 'GT-',   'padding': 5, 'next_num': 1, 'name': 'Greentek'},
    2: {'prefix': 'SP-',   'padding': 5, 'next_num': 1, 'name': 'Sucursal Partidarios'},
    4: {'prefix': 'S10-',  'padding': 5, 'next_num': 1, 'name': 'Sucursal 10 de Octubre'},
    5: {'prefix': 'SJ-',   'padding': 5, 'next_num': 1, 'name': 'Sucursal Jujuy (ID 5)'},
    9: {'prefix': 'SJ2-',  'padding': 5, 'next_num': 1, 'name': 'Sucursal Jujuy (ID 9)'},
}

# Mantener S01007 como orden histórica sin modificar (Recomendado)
RENAME_GREENTEK_S01007 = False

# ==============================================================================

print("\n" + "=" * 65)
print(f" APLICANDO SECUENCIAS MULTI-COMPAÑÍA (DRY_RUN = {DRY_RUN})")
print("=" * 65)

base_seq = env['ir.sequence'].browse(17)
if not base_seq.exists():
    raise ValueError("No se encontró la secuencia base ID 17.")

# 1. Asignar secuencia base ID 17 a Eco Norte (ID 1)
print("\n[1] Asignando secuencia base a ECO NORTE SRL:")
base_seq.write({
    'company_id': 1,
    'name': f"Sales Order - {env['res.company'].browse(1).name}",
    'prefix': COMPANY_CONFIG[1]['prefix'],
})
print(f"  ✔ Secuencia base ID 17 vinculada a Compañía ID 1 (Prefijo: '{COMPANY_CONFIG[1]['prefix']}', Próx: {base_seq.number_next_actual})")

# 2. Crear secuencias independientes para las demás compañías
print("\n[2] Creando secuencias para el resto de compañías:")
for comp_id, conf in COMPANY_CONFIG.items():
    if comp_id == 1:
        continue
    comp = env['res.company'].browse(comp_id)
    if not comp.exists():
        print(f"  ⚠️ Compañía ID {comp_id} no existe en la base de datos.")
        continue

    existing = env['ir.sequence'].search([
        ('code', '=', 'sale.order'),
        ('company_id', '=', comp_id)
    ], limit=1)

    if existing:
        print(f"  ℹ Compañía [{comp.id}] {comp.name} ya cuenta con la secuencia ID {existing.id}. Omitiendo.")
        continue

    new_seq = env['ir.sequence'].create({
        'name': f"Sales Order - {comp.name}",
        'code': 'sale.order',
        'prefix': conf['prefix'],
        'padding': conf['padding'],
        'number_next': conf['next_num'],
        'number_increment': 1,
        'company_id': comp_id,
        'implementation': 'standard',
    })
    print(f"  ✔ Creada secuencia ID {new_seq.id} para [{comp.id}] {comp.name} con prefijo '{conf['prefix']}' (Inicia en: {conf['next_num']})")

# 3. Renombrar si se hubiera activado la opción
if RENAME_GREENTEK_S01007:
    ov_gt = env['sale.order'].search([('name', '=', 'S01007'), ('company_id', '=', 6)], limit=1)
    if ov_gt:
        new_name = f"{COMPANY_CONFIG[6]['prefix']}00001"
        ov_gt.write({'name': new_name})
        print(f"\n[3] ✔ Orden S01007 renombrada a '{new_name}'")

# Confirmación explícita en BD
env.cr.commit()
print("\n" + "=" * 65)
print(" ✅ CAMBIOS CONFIRMADOS Y APLICADOS EN BASE DE DATOS (COMMIT EXITOSO)")
print("=" * 65 + "\n")
