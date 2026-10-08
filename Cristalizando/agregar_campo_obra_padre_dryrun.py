# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT PARA AGREGAR EL CAMPO 'obra_padre_id' EN VENTAS (CON SOPORTE DRY-RUN)
================================================================================
Ubicación: Justo debajo de 'NV Numero de ORFA:' (x_studio_nv_numero_de_orfa)
Modelo: sale.order
Tipo: Many2one -> project.project (Relacionado con opportunity_id.obra_padre_id)
================================================================================
"""

from lxml import etree

DRY_RUN = False  # Cambiar a False para aplicar definitivamente

print("=" * 80)
print(f"AGREGANDO CAMPO OBRA PADRE EN VENTAS (MODO: {'DRY-RUN' if DRY_RUN else 'REAL'})")
print("=" * 80)

try:
    sale_model = env['ir.model'].search([('model', '=', 'sale.order')], limit=1)
    
    # 1. Verificar o crear el campo Many2one relacionado
    field_name = 'x_studio_obra_padre_id'
    existing_field = env['ir.model.fields'].search([
        ('model', '=', 'sale.order'),
        ('name', '=', field_name)
    ])

    if not existing_field:
        print(f"[CAMPO] Creando campo Many2one '{field_name}' relacionado con CRM...")
        env['ir.model.fields'].create({
            'name': field_name,
            'model_id': sale_model.id,
            'field_description': 'NV Numero de obra padre',
            'ttype': 'many2one',
            'relation': 'project.project',
            'related': 'opportunity_id.obra_padre_id',
            'store': True,
            'readonly': False,
            'state': 'manual',
        })
        print(f"[CAMPO] Campo '{field_name}' creado con éxito.")
    else:
        print(f"[CAMPO] El campo '{field_name}' ya existe.")

    # 2. Inyectar el campo en la vista Studio 3922 debajo de x_studio_nv_numero_de_orfa
    view_3922 = env['ir.ui.view'].browse(3922)
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.fromstring(view_3922.arch_db.encode('utf-8'), parser)

    # Verificar si ya está en la vista
    already_in_view = tree.xpath(f"//field[@name='{field_name}']")
    if already_in_view:
        print("[VISTA] El campo ya está presente en la arquitectura XML de la vista 3922.")
    else:
        # Ubicar el nodo de x_studio_nv_numero_de_orfa
        orfa_node = tree.xpath("//field[@name='x_studio_nv_numero_de_orfa']")
        if orfa_node:
            target = orfa_node[0]
            print("[VISTA] Ubicado nodo 'x_studio_nv_numero_de_orfa'. Insertando campo debajo...")
            new_field_node = etree.Element("field", {
                "name": field_name,
                "options": '{"no_create": true}'
            })
            target.addnext(new_field_node)
            
            nuevo_arch = etree.tostring(tree, encoding='unicode')
            view_3922.write({'arch_db': nuevo_arch})
            print("[VISTA] Arquitectura de vista 3922 actualizada con éxito.")
        else:
            print("[AVISO] No se encontró el nodo 'x_studio_nv_numero_de_orfa' directamente en vista 3922.")

    # 3. Probar la compilación de la vista completa
    print("\nProbando compilación de la vista formulario de sale.order...")
    sale_form = env.ref('sale.view_order_form')
    test_view = env['sale.order'].get_view(view_id=sale_form.id, view_type='form')
    print("[ÉXITO TOTAL] ¡El formulario de Ventas compila perfectamente con el nuevo campo!")

    if DRY_RUN:
        print("\n[DRY-RUN] Ejecutando rollback... Base de datos intacta.")
        print("          Para persistir, cambia DRY_RUN = False y vuelve a ejecutar.")
        env.cr.rollback()
    else:
        print("\n[MODO REAL] Cambios guardados permanentemente en la base de datos (Commit).")
        env.cr.commit()

except Exception as e:
    print(f"\n[ERROR]: {e}")
    env.cr.rollback()
