# -*- coding: utf-8 -*-
"""
Prueba unitaria y de integración local con Mock Odoo Environment
Valida que 'cargar_productos_odoo_shell.py' ejecute limpiamente con los datos preparados.
"""

import sys
import json
from unittest.mock import MagicMock

def test_script_with_mock_odoo():
    print("Iniciando prueba con Mock Environment de Odoo...")
    
    # Mock de modelos de Odoo
    mock_env = {}
    
    # Mock Cursor
    mock_cr = MagicMock()
    mock_cr.dbname = "kiddie_prod_mock"
    
    # Mock Company
    mock_company = MagicMock()
    mock_company.id = 1
    mock_company.name = "Kiddie Argentina S.A."
    
    # Mock Taxes
    tax_21 = MagicMock()
    tax_21.id = 10
    tax_21.amount = 21.0
    tax_21.name = "IVA 21%"
    tax_21.active = True

    tax_105 = MagicMock()
    tax_105.id = 11
    tax_105.amount = 10.5
    tax_105.name = "IVA 10.5%"
    tax_105.active = True

    tax_0 = MagicMock()
    tax_0.id = 12
    tax_0.amount = 0.0
    tax_0.name = "IVA 0%"
    tax_0.active = True

    mock_tax_model = MagicMock()
    mock_tax_model.search.return_value = MagicMock(
        filtered=lambda func: [t for t in [tax_21, tax_105, tax_0] if func(t)]
    )
    mock_env['account.tax'] = mock_tax_model

    # Mock Category
    mock_categ_model = MagicMock()
    mock_categ_model.search.return_value = False
    created_cats = {}
    def mock_categ_create(vals):
        cat = MagicMock()
        cat.id = len(created_cats) + 100
        cat.name = vals.get('name')
        created_cats[cat.id] = vals
        return cat
    mock_categ_model.create.side_effect = mock_categ_create
    mock_env['product.category'] = mock_categ_model

    # Mock Partner
    mock_partner_model = MagicMock()
    mock_partner_model.search.return_value = False
    mock_partner_model.create.return_value = MagicMock(id=500)
    mock_env['res.partner'] = mock_partner_model

    # Mock ProductTemplate
    mock_tmpl_model = MagicMock()
    mock_tmpl_model._fields = {
        'name': MagicMock(),
        'default_code': MagicMock(),
        'list_price': MagicMock(),
        'standard_price': MagicMock(),
        'is_storable': MagicMock(),
        'type': MagicMock(),
        'categ_id': MagicMock(),
        'taxes_id': MagicMock(),
        'barcode': MagicMock()
    }
    mock_tmpl_model.search_read.return_value = []
    created_prods = {}
    def mock_prod_create(vals):
        p = MagicMock()
        p.id = len(created_prods) + 1000
        created_prods[p.id] = vals
        return p
    mock_tmpl_model.create.side_effect = mock_prod_create
    mock_env['product.template'] = mock_tmpl_model

    # Mock SupplierInfo
    mock_supp_model = MagicMock()
    mock_supp_model.search.return_value = False
    mock_env['product.supplierinfo'] = mock_supp_model

    # Mock Product Tag
    mock_tag_model = MagicMock()
    mock_tag_model.search.return_value = False
    mock_tag_model.create.return_value = MagicMock(id=1)
    mock_env['product.tag'] = mock_tag_model

    # Environment object wrapper
    class MockEnv:
        def __init__(self, models, cr, company):
            self.models = models
            self.cr = cr
            self.company = company

        def __getitem__(self, item):
            return self.models.get(item, MagicMock())

        def __contains__(self, item):
            return item in self.models

        def ref(self, xmlid):
            m = MagicMock()
            m.id = 1
            return m

    env = MockEnv(mock_env, mock_cr, mock_company)

    # Import and run function from cargar_productos_odoo_shell
    import cargar_productos_odoo_shell
    
    # Test batch with only first 100 products to verify speed
    with open('productos_preparados.json', 'r', encoding='utf-8') as f:
        full_prods = json.load(f)
    
    with open('productos_preparados_test.json', 'w', encoding='utf-8') as f:
        json.dump(full_prods[:100], f)

    cargar_productos_odoo_shell.JSON_PRODUCTOS = "productos_preparados_test.json"
    cargar_productos_odoo_shell.ejecutar_migracion(env)

    # Verify rollback was called in dry-run
    assert mock_cr.rollback.called, "El rollback DEBE haberse ejecutado en modo DRY_RUN!"
    assert not mock_cr.commit.called, "El commit NO debe haberse ejecutado en modo DRY_RUN!"
    print(f"VERIFICACIÓN EXITOSA: {len(created_prods)} productos mockeados creados y rollback verificado.")

if __name__ == '__main__':
    test_script_with_mock_odoo()

