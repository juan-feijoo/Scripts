# -*- coding: utf-8 -*-
"""
Prueba unitaria local con Mock Environment para crear_listas_precios_shell.py
"""

from unittest.mock import MagicMock
import json

def test_pricelists_script():
    print("Iniciando prueba unitaria mock para crear_listas_precios_shell.py...")
    
    mock_env = {}
    mock_cr = MagicMock()
    mock_cr.dbname = "kiddie_prod_mock"
    
    mock_company = MagicMock()
    mock_company.id = 1
    mock_company.name = "Kiddie Distribuciones"
    mock_currency_ars = MagicMock(id=19, name="ARS")
    mock_company.currency_id = mock_currency_ars
    
    mock_currency_usd = MagicMock(id=2, name="USD", active=True)
    mock_currency_model = MagicMock()
    mock_currency_model.search.return_value = mock_currency_usd
    mock_env['res.currency'] = mock_currency_model
    
    # Mock ProductTemplate
    mock_tmpl_model = MagicMock()
    with open('productos_preparados.json', 'r', encoding='utf-8') as f:
        prods = json.load(f)
    mock_tmpl_model.search_read.return_value = [
        {'id': i + 1, 'default_code': p['default_code'], 'name': p['name']}
        for i, p in enumerate(prods)
    ]
    mock_env['product.template'] = mock_tmpl_model
    
    # Mock Pricelist
    mock_pricelist_model = MagicMock()
    mock_pl_default = MagicMock(id=1, name="Public Pricelist")
    mock_pricelist_model.search.side_effect = lambda domain, **kwargs: (
        mock_pl_default if any('currency_id' in str(d) for d in domain) and 'USD' not in str(domain) else False
    )
    mock_pricelist_model.create.side_effect = lambda vals: MagicMock(id=99, name=vals['name'])
    mock_env['product.pricelist'] = mock_pricelist_model
    
    # Mock PricelistItem
    mock_item_model = MagicMock()
    mock_item_model.search.return_value = []
    created_items = []
    mock_item_model.create.side_effect = lambda vals: created_items.extend(vals) if isinstance(vals, list) else created_items.append(vals)
    mock_env['product.pricelist.item'] = mock_item_model

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
            return MagicMock(id=2)

    env = MockEnv(mock_env, mock_cr, mock_company)
    
    import crear_listas_precios_shell
    crear_listas_precios_shell.ejecutar_creacion_listas(env)
    
    assert mock_cr.rollback.called, "El rollback DEBE ejecutarse en DRY_RUN!"
    assert len(created_items) > 900, "Debe haber creado las reglas de precios USD!"
    print(f"VERIFICACIÓN EXITOSA: {len(created_items)} reglas de lista de precios creadas con Rollback verificado.")

if __name__ == '__main__':
    test_pricelists_script()

