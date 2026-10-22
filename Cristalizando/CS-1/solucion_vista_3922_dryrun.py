# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT DE REPARACIÓN DE VISTA STUDIO 3922 CON SOPORTE DRY-RUN
================================================================================
Este script inspecciona y sanea la vista Studio 3922 de sale.order:
1. Revisa si contiene el xpath conflictivo que apunta a material_reservation_ids.
2. Limpia el nodo o corrige el xpath para que no use selectores frágiles.
3. Prueba la compilación completa de la vista de sale.order.
4. Con DRY_RUN = True simula y hace rollback. Con DRY_RUN = False aplica commit.
================================================================================
"""

from lxml import etree

# ==============================================================================
# CONFIGURACIÓN:
# Cambia a False cuando desees aplicar los cambios definitivamente en Odoo.sh
# ==============================================================================
DRY_RUN = False

print("=" * 80)
print(f"INICIANDO REPARACIÓN DE VISTA STUDIO 3922 (MODO: {'DRY-RUN' if DRY_RUN else 'REAL'})")
print("=" * 80)

try:
    view_3922 = env['ir.ui.view'].browse(3922)
    if not view_3922.exists():
        raise Exception("No se encontró la vista con ID 3922.")

    print(f"Vista encontrada: {view_3922.name} (ID: {view_3922.id})")
    
    # Parsear el XML actual
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.fromstring(view_3922.arch_db.encode('utf-8'), parser)

    # Buscar los nodos xpath problemáticos sobre material_reservation_ids
    xpaths_problematicos = tree.xpath("//xpath[contains(@expr, 'material_reservation_ids')]")
    print(f"Cantidad de XPaths problemáticos encontrados en vista 3922: {len(xpaths_problematicos)}")

    for xp in xpaths_problematicos:
        expr = xp.get('expr')
        print(f"  -> Eliminando XPath conflictivo: {expr}")
        xp.getparent().remove(xp)

    # Generar el nuevo arch limpio
    nuevo_arch = etree.tostring(tree, encoding='unicode')

    print("\nActualizando arquitectura en vista 3922...")
    view_3922.write({'arch_db': nuevo_arch})

    # Probar la validación de la vista completa
    print("Probando compilación get_view en sale.order...")
    sale_form = env.ref('sale.view_order_form')
    test_view = env['sale.order'].get_view(view_id=sale_form.id, view_type='form')
    
    print("\n" + "=" * 80)
    print("[ÉXITO TOTAL] ¡La vista de sale.order compila sin ningún error!")
    print("              Studio ya puede abrirse y operar con total normalidad.")
    print("=" * 80)

    if DRY_RUN:
        print("\n[DRY-RUN] Ejecutando rollback... Ningún cambio persistido en la base.")
        print("          Para aplicar de forma permanente, cambia DRY_RUN = False y re-ejecuta.")
        env.cr.rollback()
    else:
        print("\n[MODO REAL] Cambios guardados permanentemente (Commit).")
        env.cr.commit()

except Exception as e:
    print(f"\n[ERROR DURANTE LA EJECUCIÓN]: {e}")
    env.cr.rollback()
