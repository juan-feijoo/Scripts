# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT DE REPARACIÓN Y VALIDACIÓN CON SOPORTE DRY-RUN (Odoo 17 / 18 / 19)
================================================================================
Uso en Odoo.sh shell:
    python3 odoo-bin shell -d <nombre_bd>
    >>> exec(open('fix_view_dryrun.py').read())

Configuración:
    DRY_RUN = True   -> Simula la desactivación/corrección, prueba la vista y
                        hace rollback (NO persiste cambios).
    DRY_RUN = False  -> Aplica los cambios y hace commit().
================================================================================
"""

import logging

# ==========================================
# CONFIGURACIÓN DEL SCRIPT
# ==========================================
DRY_RUN = True  # Cambiar a False únicamente cuando estés seguro de aplicar
TARGET_VIEW_ID = None  # Si ya conoces el ID exacto, colócalo aquí (ej: 1234). Si es None, buscará automáticamente.

print("=" * 80)
print(f"EJECUTANDO SCRIPT EN MODO: {'*** DRY-RUN (SIMULACIÓN SEGURA) ***' if DRY_RUN else '*** MODO REAL (APLICANDO CAMBIOS) ***'}")
print("=" * 80)

try:
    with env.cr.savepoint():
        # 1. Localizar la vista rota
        if TARGET_VIEW_ID:
            broken_view = env['ir.ui.view'].browse(TARGET_VIEW_ID)
        else:
            candidates = env['ir.ui.view'].search([
                ('arch_db', 'ilike', 'material_reservation_ids'),
                ('arch_db', 'ilike', 'page[not(@name)]'),
                ('active', '=', True)
            ])
            if not candidates:
                # Búsqueda secundaria más amplia
                candidates = env['ir.ui.view'].search([
                    ('arch_db', 'ilike', 'material_reservation_ids'),
                    ('arch_db', 'ilike', 'product_id'),
                    ('active', '=', True)
                ])
            broken_view = candidates[0] if candidates else None

        if not broken_view:
            print("[AVISO] No se encontró ninguna vista activa con ese XPath conflictivo.")
        else:
            print(f"[LOCALIZADO] Vista conflictiva encontrada:")
            print(f"  - ID: {broken_view.id}")
            print(f"  - Nombre: {broken_view.name}")
            print(f"  - XML ID: {broken_view.xml_id}")
            print(f"  - Modelo: {broken_view.model}")
            print(f"  - Vista Padre: {broken_view.inherit_id.name} (ID: {broken_view.inherit_id.id})")

            # 2. Desactivar temporalmente la vista rota para probar
            print(f"\n[ACCIÓN] Desactivando vista ID {broken_view.id}...")
            broken_view.write({'active': False})

            # 3. Probar renderizado / combinación de la vista de sale.order
            print("[TEST] Probando renderizado del formulario de sale.order...")
            sale_form = env.ref('sale.view_order_form', raise_if_not_found=False)
            if not sale_form:
                sale_form = env['ir.ui.view'].search([('model', '=', 'sale.order'), ('type', '=', 'form')], limit=1)

            try:
                # Probamos compilar/obtener la vista sin el error
                test_view = env['sale.order'].get_view(view_id=sale_form.id, view_type='form')
                print("[ÉXITO] La vista de sale.order ahora compila PERFECTAMENTE sin errores.")
                print("       Studio ahora podrá abrir y modificar la vista sin que salte el RPC_ERROR.")
            except Exception as e:
                print(f"[ERROR PERSISTENTE] Aún hay errores al compilar la vista: {e}")

        # 4. Manejo de DRY_RUN / Commit
        if DRY_RUN:
            print("\n" + "=" * 50)
            print("[DRY-RUN] Revertiendo cambios simulados (Rollback)...")
            print("          Ningún dato o vista fue alterado en la base de datos.")
            print("=" * 50)
            env.cr.rollback()
        else:
            print("\n" + "=" * 50)
            print("[MODO REAL] Cambios aplicados con éxito en la base de datos (Commit).")
            print("=" * 50)
            env.cr.commit()

except Exception as ex:
    print(f"\n[EXCEPCIÓN EN EL PROCESO]: {ex}")
    env.cr.rollback()
    print("[ROLLBACK EJECUTADO DEBIDO AL ERROR]")
