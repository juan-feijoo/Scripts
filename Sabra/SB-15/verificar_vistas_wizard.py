# -*- coding: utf-8 -*-
"""
Verificar XML ID de la vista formulario de product.label.layout
Ejecución: python3 odoo-bin shell -c $ODOO_RC -d $ODOO_DATABASE < verificar_vistas_wizard.py
"""
wizard_model = env['product.label.layout']
views = env['ir.ui.view'].search([('model', '=', 'product.label.layout'), ('type', '=', 'form')])
for v in views:
    xml_id = v.get_external_id().get(v.id, 'Sin XML ID')
    print(f"Vista: [ID: {v.id}] XML_ID: {xml_id} | Name: {v.name} | Inherit: {v.inherit_id.name if v.inherit_id else 'None'}")
