# -*- coding: utf-8 -*-
{
    'name': 'Sabra - Personalización de Etiquetas de Productos',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Etiquetas 2x7 con Proveedor Principal, Precios Minorista y Mayorista con IVA incluido',
    'description': """
Módulo de personalización de etiquetas de productos para Sabra (Odoo 19 Enterprise):
===================================================================================
* Asistente 'product.label.layout':
  - Selección de segunda lista de precios (Lista Mayorista).
  - Visualización del Proveedor Principal del producto.
  - Parámetro para activar/desactivar impresión de datos de proveedor.
* Reporte QWeb de Etiquetas 2x7:
  - Cálculo dinámico de precio con IVA incluido (compute_all).
  - Visualización simultánea de Precio Minorista y Precio Mayorista con IVA.
  - Inclusión del nombre y código de artículo del proveedor principal.
    """,
    'author': 'Sabra',
    'website': 'https://sabra.com.ar',
    'depends': [
        'product',
        'stock',
    ],
    'data': [
        'views/product_label_layout_views.xml',
        'views/report_product_labels.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OEEL-1',
}
