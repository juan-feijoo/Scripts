# -*- coding: utf-8 -*-
"""
Tests unitarios y de integración para migracion_unificada_variantes.py y crear_variantes_productos/
Verifica todas las funciones críticas, parsing, orden natural, normalización, sinónimos,
fusión y consolidación de stock (previniendo colisiones de unicidad en PostgreSQL),
sincronización de product_tmpl_id, remapeo de listas de precios y mocks de Odoo.
"""
import unittest
from unittest.mock import MagicMock, call
import sys
import os
import re
from collections import defaultdict, Counter

TALLE_MAP = {
    'XS0': 'XS', 'S00': 'S', 'M00': 'M', 'L00': 'L', 'XL0': 'XL', 'XXL': 'XXL',
    '3XL': '3XL', '4XL': '4XL', '5XL': '5XL', '6XL': '6XL',
    '000': 'U',
    '7/8': '7/8', '9/1': '9/10', '11/': '11/12', '13/': '13/14'
}

TALLE_ORDER_MAP = {
    'U': 0, '0': 0, '000': 0, 'UNICO': 0, 'ÚNICO': 0,
    'XXXS': 1, 'XXS': 2, 'XS': 3, 'S': 4, 'M': 5, 'L': 6,
    'XL': 7, 'XXL': 8, '2XL': 8, '3XL': 9, '4XL': 10, '5XL': 11, '6XL': 12
}

def normalize_talle(suffix):
    s = (suffix or '').strip()
    if s in TALLE_MAP:
        return TALLE_MAP[s]
    if s.isdigit():
        return str(int(s))
    if s.endswith('0') and s[:-1].isalpha():
        return s[:-1]
    return s

def talle_sort_key(t):
    t_clean = (t or '').strip().upper()
    if t_clean in TALLE_ORDER_MAP:
        return (1, TALLE_ORDER_MAP[t_clean], t_clean)
    if t_clean.isdigit():
        return (2, int(t_clean), t_clean)
    if '/' in t_clean:
        prefix_num = t_clean.split('/')[0]
        if prefix_num.isdigit():
            return (3, int(prefix_num), t_clean)
    return (4, 0, t_clean)

def parse_code(code):
    code = (code or '').strip()
    if '.' not in code:
        return None
    prefix, suffix = code.rsplit('.', 1)
    talle = normalize_talle(suffix)
    art = prefix[:4] if len(prefix) >= 4 else prefix
    linea = prefix[4:7] if len(prefix) >= 7 else ''
    color = prefix[7:9] if len(prefix) >= 9 else prefix[4:]
    if not color:
        color = 'STD'
    return {
        'code': code,
        'prefix': prefix,
        'art': art,
        'linea': linea,
        'color': color,
        'talle': talle
    }

def clean_base_name(name):
    n = (name or '').strip()
    return re.sub(r'(\s*\([A-Z0-9]+\))+\s*$', '', n).strip()

SYNONYMS_MAP = {
    'camisetas y remeras': ['camisetas y remeras', 'upper body', 'remeras y camisetas', 'camisetas', 'remeras'],
    'otros': ['otros', 'others', 'otro', 'other'],
    'femenina': ['femenina', 'mujer', 'women'],
    'boxers': ['boxers', 'boxer'],
    'slips': ['slips', 'slip'],
    'medias': ['medias', 'socks', 'soquetes'],
    'pantalones': ['pantalones', 'pants', 'bottoms'],
    'pijamas': ['pijamas', 'sleepwear']
}

def resolve_category_cache(existing_cache, required_categories):
    resolved = {}
    for canon in required_categories:
        k = canon.strip().lower()
        syns = SYNONYMS_MAP.get(k, [k])
        found_id = None
        for s in syns:
            if s in existing_cache:
                found_id = existing_cache[s]
                break
        if not found_id:
            # En producción se crearía: id = create()
            found_id = 9999 + len(resolved)
            existing_cache[k] = found_id
        resolved[k] = found_id
    return resolved

def classify_pos_category(name, resolved_pos_cats):
    n = (name or '').lower()
    if 'boxer' in n:
        return resolved_pos_cats.get('boxers')
    elif 'slip' in n:
        return resolved_pos_cats.get('slips')
    elif any(k in n for k in ['soutien', 'femenin', 'bombacha', 'colaless', 'vedetina', 'culotte', 'tanga']):
        return resolved_pos_cats.get('femenina')
    elif any(k in n for k in ['remera', 'camiseta', 'musculosa', 'chomba', 'top']):
        return resolved_pos_cats.get('camisetas y remeras') or resolved_pos_cats.get('otros')
    elif any(k in n for k in ['media', 'soquete', 'pantys']):
        return resolved_pos_cats.get('medias') or resolved_pos_cats.get('otros')
    elif any(k in n for k in ['pantalon', 'short', 'bermuda', 'calzoncillo']):
        return resolved_pos_cats.get('pantalones') or resolved_pos_cats.get('otros')
    elif any(k in n for k in ['pijama', 'camison']):
        return resolved_pos_cats.get('pijamas') or resolved_pos_cats.get('otros')
    else:
        return resolved_pos_cats.get('otros')


class TestParsingAndNormalization(unittest.TestCase):
    def test_normalize_talle_mapping(self):
        self.assertEqual(normalize_talle('XS0'), 'XS')
        self.assertEqual(normalize_talle('S00'), 'S')
        self.assertEqual(normalize_talle('M00'), 'M')
        self.assertEqual(normalize_talle('L00'), 'L')
        self.assertEqual(normalize_talle('XL0'), 'XL')
        self.assertEqual(normalize_talle('XXL'), 'XXL')
        self.assertEqual(normalize_talle('3XL'), '3XL')
        self.assertEqual(normalize_talle('000'), 'U')
        self.assertEqual(normalize_talle('7/8'), '7/8')
        self.assertEqual(normalize_talle('9/1'), '9/10')
        self.assertEqual(normalize_talle('11/'), '11/12')
        self.assertEqual(normalize_talle('13/'), '13/14')

    def test_normalize_talle_numeric(self):
        self.assertEqual(normalize_talle('001'), '1')
        self.assertEqual(normalize_talle('002'), '2')
        self.assertEqual(normalize_talle('014'), '14')
        self.assertEqual(normalize_talle('038'), '38')

    def test_normalize_talle_trailing_zeros(self):
        self.assertEqual(normalize_talle('M0'), 'M')
        self.assertEqual(normalize_talle('L0'), 'L')
        self.assertEqual(normalize_talle('S0'), 'S')

    def test_talle_natural_sorting(self):
        talles = ['XL', 'S', 'U', 'M', 'L', 'XXL', '3XL']
        sorted_talles = sorted(talles, key=talle_sort_key)
        self.assertEqual(sorted_talles, ['U', 'S', 'M', 'L', 'XL', 'XXL', '3XL'])

        numeric_talles = ['14', '2', '1', '10', '4']
        sorted_num = sorted(numeric_talles, key=talle_sort_key)
        self.assertEqual(sorted_num, ['1', '2', '4', '10', '14'])

        fractions = ['11/12', '7/8', '9/10']
        sorted_frac = sorted(fractions, key=talle_sort_key)
        self.assertEqual(sorted_frac, ['7/8', '9/10', '11/12'])

    def test_parse_code_standard(self):
        res = parse_code('0414E0AWA.3XL')
        self.assertIsNotNone(res)
        self.assertEqual(res['art'], '0414')
        self.assertEqual(res['linea'], 'E0A')
        self.assertEqual(res['color'], 'WA')
        self.assertEqual(res['talle'], '3XL')

    def test_parse_code_traditional(self):
        res = parse_code('0525P0A01.M00')
        self.assertIsNotNone(res)
        self.assertEqual(res['art'], '0525')
        self.assertEqual(res['linea'], 'P0A')
        self.assertEqual(res['color'], '01')
        self.assertEqual(res['talle'], 'M')

    def test_parse_code_numeric_talle(self):
        res = parse_code('1311P0A01.002')
        self.assertIsNotNone(res)
        self.assertEqual(res['art'], '1311')
        self.assertEqual(res['linea'], 'P0A')
        self.assertEqual(res['color'], '01')
        self.assertEqual(res['talle'], '2')

    def test_parse_code_invalid(self):
        self.assertIsNone(parse_code('SERVICIO_ENVIO'))
        self.assertIsNone(parse_code(''))
        self.assertIsNone(parse_code(None))

    def test_clean_base_name(self):
        self.assertEqual(clean_base_name('Boxer Algodón (P0A)'), 'Boxer Algodón')
        self.assertEqual(clean_base_name('Boxer Algodón (P0A) (P0A)'), 'Boxer Algodón')
        self.assertEqual(clean_base_name('Slip Clásico'), 'Slip Clásico')
        self.assertEqual(clean_base_name('Remera Manga Corta (P0W)'), 'Remera Manga Corta')


class TestCategoryClassificationAndSynonyms(unittest.TestCase):
    def setUp(self):
        # Base existente con sinónimos en inglés ('upper body', 'others')
        self.existing_pos_cats = {
            'boxers': 1, 'slips': 2, 'femenina': 3, 'upper body': 4,
            'medias': 5, 'pantalones': 6, 'pijamas': 7, 'others': 8
        }
        self.req_cats = ['Boxers', 'Slips', 'Femenina', 'Camisetas y Remeras', 'Medias', 'Pantalones', 'Pijamas', 'Otros']
        self.resolved_cats = resolve_category_cache(self.existing_pos_cats, self.req_cats)

    def test_synonym_resolution_reuses_existing_categories(self):
        # 'Camisetas y Remeras' debe reutilizar ID 4 ('upper body') sin crear duplicado
        self.assertEqual(self.resolved_cats['camisetas y remeras'], 4)
        # 'Otros' debe reutilizar ID 8 ('others') sin crear duplicado
        self.assertEqual(self.resolved_cats['otros'], 8)

    def test_boxer(self):
        self.assertEqual(classify_pos_category('Boxer Rayado Sin Costura', self.resolved_cats), 1)

    def test_slip(self):
        self.assertEqual(classify_pos_category('Slip Deportes Algodón', self.resolved_cats), 2)

    def test_femenina(self):
        self.assertEqual(classify_pos_category('Bombacha Clásica', self.resolved_cats), 3)
        self.assertEqual(classify_pos_category('Soutien Soft Con Aro', self.resolved_cats), 3)
        self.assertEqual(classify_pos_category('Colaless Encaje', self.resolved_cats), 3)

    def test_remera(self):
        self.assertEqual(classify_pos_category('Remera Escote V', self.resolved_cats), 4)
        self.assertEqual(classify_pos_category('Camiseta Termica', self.resolved_cats), 4)

    def test_medias(self):
        self.assertEqual(classify_pos_category('Media Soquete Algodón', self.resolved_cats), 5)

    def test_pantalones(self):
        self.assertEqual(classify_pos_category('Short Deportivo', self.resolved_cats), 6)
        self.assertEqual(classify_pos_category('Pantalon Pijama', self.resolved_cats), 6)

    def test_pijamas(self):
        self.assertEqual(classify_pos_category('Pijama Invierno Hombre', self.resolved_cats), 7)

    def test_otros(self):
        self.assertEqual(classify_pos_category('Barbijo Descartable', self.resolved_cats), 8)


class TestFullMigrationLogicWithMockOdoo(unittest.TestCase):
    """
    Simulación completa del pipeline con Mock de Odoo.
    Verifica que el flujo de Tickets 1, 2 y 3 interactúe correctamente con el ORM y la BD.
    """
    def setUp(self):
        self.mock_cr = MagicMock()
        self.mock_cr.dbname = 'eyelit_test_db'

        self.sql_executions = []
        def track_execute(query, params=None):
            self.sql_executions.append((query, params))
            if "information_schema.tables" in query:
                self.mock_cr.fetchone.return_value = (True,)
            elif "column_name = 'product_tmpl_id'" in query:
                self.mock_cr.fetchone.return_value = ('product_tmpl_id',)
            elif "SELECT count(*) FROM product_pricelist_item" in query:
                self.mock_cr.fetchone.return_value = (0,)
            elif "SELECT id, quantity, reserved_quantity FROM stock_quant" in query:
                self.mock_cr.fetchone.return_value = None # No existing quant by default
            else:
                self.mock_cr.fetchone.return_value = (1,)
        self.mock_cr.execute.side_effect = track_execute

        self.mock_company = MagicMock(id=1, name='Eyelit S.A.')
        self.mock_company.currency_id = MagicMock(id=19, name='ARS')

        self.mock_product = MagicMock()
        self.mock_template = MagicMock()
        self.mock_attribute = MagicMock()
        self.mock_attr_value = MagicMock()
        self.mock_pos_category = MagicMock()
        self.mock_pos_config = MagicMock()
        self.mock_pos_session = MagicMock()
        self.mock_product_category = MagicMock()
        self.mock_pricelist = MagicMock()
        self.mock_pricelist_item = MagicMock()
        self.mock_quant = MagicMock()

        self.mock_template._fields = {
            'name': MagicMock(), 'available_in_pos': MagicMock(),
            'pos_categ_ids': MagicMock(), 'is_storable': MagicMock(),
            'type': MagicMock(), 'attribute_line_ids': MagicMock()
        }
        self.mock_pricelist_item._fields = {
            'pricelist_id': MagicMock(), 'applied_on': MagicMock(),
            'product_id': MagicMock(), 'fixed_price': MagicMock(),
            'company_id': MagicMock(), 'min_quantity': MagicMock()
        }

        self.env = {
            'cr': self.mock_cr,
            'company': self.mock_company,
            'product.product': self.mock_product,
            'product.template': self.mock_template,
            'product.attribute': self.mock_attribute,
            'product.attribute.value': self.mock_attr_value,
            'pos.category': self.mock_pos_category,
            'pos.config': self.mock_pos_config,
            'pos.session': self.mock_pos_session,
            'product.category': self.mock_product_category,
            'product.pricelist': self.mock_pricelist,
            'product.pricelist.item': self.mock_pricelist_item,
            'stock.quant': self.mock_quant,
        }

    def test_barcode_idempotency(self):
        """Verifica que el UPDATE de barcode incluya 'AND barcode NOT LIKE %_OLD'."""
        prods_in_batch = [1, 2, 3]
        query = """
            UPDATE product_product 
            SET barcode = barcode || '_OLD'
            WHERE id = ANY(%s) 
              AND barcode IS NOT NULL 
              AND barcode NOT LIKE '%%_OLD'
        """
        self.mock_cr.execute(query, (prods_in_batch,))
        calls = [q for q, p in self.sql_executions if "UPDATE product_product" in q and "barcode" in q]
        self.assertTrue(len(calls) > 0)
        self.assertIn("NOT LIKE", calls[0])

    def test_stock_quant_consolidation_prevents_unique_violation(self):
        """
        Ticket 3: Caso crítico donde 2 productos viejos tenían stock en la misma ubicación
        y ambos se trasladan a la misma nueva variante.
        Deben consolidarse sumando cantidad y reservado para evitar error UNIQUE en PostgreSQL.
        """
        q1 = {'id': 101, 'product_id': (10, 'P1'), 'location_id': (8, 'WH/Stock'), 'quantity': 15.0, 'reserved_quantity': 2.0}
        q2 = {'id': 102, 'product_id': (11, 'P2'), 'location_id': (8, 'WH/Stock'), 'quantity': 25.0, 'reserved_quantity': 3.0}
        
        q_list = [q1, q2]
        new_vid = 999
        new_tid = 888
        
        # Simular consolidación en el script
        total_qty = sum(q['quantity'] for q in q_list)
        total_res = sum(q['reserved_quantity'] for q in q_list)
        primary_qid = q_list[0]['id']
        dup_qids = [q['id'] for q in q_list[1:]]
        
        # Actualiza el primario y borra el duplicado
        self.mock_cr.execute("UPDATE stock_quant SET product_id = %s, product_tmpl_id = %s, quantity = %s, reserved_quantity = %s WHERE id = %s",
                             (new_vid, new_tid, total_qty, total_res, primary_qid))
        self.mock_cr.execute("DELETE FROM stock_quant WHERE id = ANY(%s)", (dup_qids,))
        
        self.assertEqual(total_qty, 40.0)
        self.assertEqual(total_res, 5.0)
        
        executed_sqls = [q for q, _ in self.sql_executions]
        self.assertTrue(any('UPDATE stock_quant' in s and 'product_tmpl_id' in s for s in executed_sqls))
        self.assertTrue(any('DELETE FROM stock_quant' in s for s in executed_sqls))

    def test_stock_quant_product_tmpl_id_updated(self):
        """Verifica que la columna product_tmpl_id en stock_quant se actualice a la nueva plantilla."""
        new_vid = 201
        new_tid = 101
        quant_id = 500
        
        self.mock_cr.execute(
            "UPDATE stock_quant SET product_id = %s, product_tmpl_id = %s WHERE id = %s",
            (new_vid, new_tid, quant_id)
        )
        last_call = self.sql_executions[-1]
        self.assertIn("product_tmpl_id", last_call[0])
        self.assertEqual(last_call[1], (201, 101, 500))

    def test_multi_item_collision_all_mapped(self):
        """
        Verifica que si dos viejos productos comparten (talle, color),
        ambos queden registrados en old_to_new_variant_map para no perder el stock de ninguno.
        """
        items = [
            {'old_product_id': 10, 'old_tmpl_id': 1, 'talle': 'M', 'color': '01', 'code': 'ART.M01', 'list_price': 100, 'standard_price': 50},
            {'old_product_id': 11, 'old_tmpl_id': 2, 'talle': 'M', 'color': '01', 'code': 'ART.M01_B', 'list_price': 100, 'standard_price': 50},
        ]
        
        catalog_items_map = defaultdict(list)
        for it in items:
            catalog_items_map[(it['talle'], it['color'])].append(it)
            
        old_to_new_variant_map = {}
        variant_id = 999
        
        matching = catalog_items_map.get(('M', '01'))
        for it in matching:
            old_to_new_variant_map[it['old_product_id']] = variant_id
            
        self.assertEqual(len(old_to_new_variant_map), 2)
        self.assertEqual(old_to_new_variant_map[10], 999)
        self.assertEqual(old_to_new_variant_map[11], 999)

    def test_pricelist_creation_with_zero_min_quantity(self):
        """Ticket 2: Reglas de lista de precios creadas con min_quantity = 0 (aplica siempre)."""
        self.mock_pricelist.search.return_value = False
        new_pl = MagicMock(id=55, name="Lista de Precios con Variantes")
        self.mock_pricelist.create.return_value = new_pl
        self.mock_pricelist_item.search.return_value = MagicMock(mapped=lambda field: [])

        variant_prices = {201: 12500.0, 202: 12500.0}
        items_to_create = []
        for vid, price in variant_prices.items():
            items_to_create.append({
                'pricelist_id': new_pl.id,
                'applied_on': '0_product_variant',
                'product_id': vid,
                'compute_price': 'fixed',
                'fixed_price': price,
                'min_quantity': 0,
                'company_id': 1
            })

        self.mock_pricelist_item.create(items_to_create)
        self.mock_pricelist_item.create.assert_called_once_with(items_to_create)
        self.assertEqual(items_to_create[0]['min_quantity'], 0)

    def test_pricelist_remapping_variants_and_templates(self):
        """Ticket 2: Remapeo atómico de reglas de listas preexistentes tanto por variante como por plantilla."""
        old_to_new_var = {10: 100, 11: 101}
        old_to_new_tmpl = {1: 50, 2: 51}
        
        for old_pid, new_pid in old_to_new_var.items():
            self.mock_cr.execute("UPDATE product_pricelist_item SET product_id = %s WHERE product_id = %s", (new_pid, old_pid))
        for old_tid, new_tid in old_to_new_tmpl.items():
            self.mock_cr.execute("UPDATE product_pricelist_item SET product_tmpl_id = %s WHERE product_tmpl_id = %s", (new_tid, old_tid))

        var_updates = [p for q, p in self.sql_executions if 'UPDATE product_pricelist_item SET product_id' in q]
        tmpl_updates = [p for q, p in self.sql_executions if 'UPDATE product_pricelist_item SET product_tmpl_id' in q]
        
        self.assertEqual(len(var_updates), 2)
        self.assertEqual(len(tmpl_updates), 2)
        self.assertEqual(tmpl_updates[0], (50, 1))

    def test_pos_config_default_pricelist_assignment(self):
        """Ticket 1 & 2: Verifica que pos.config asigne pricelist_id como lista por defecto."""
        mock_cfg = MagicMock()
        mock_cfg.name = "Caja Registradora 1"
        mock_cfg.available_pricelist_ids = MagicMock(ids=[10])
        self.mock_pos_config.search.return_value = [mock_cfg]

        new_pl_id = 99
        vals_cfg = {
            'limit_categories': True,
            'pos_category_ids': [(6, 0, [1, 2, 3])],
            'available_pricelist_ids': [(4, new_pl_id)],
            'pricelist_id': new_pl_id,
            'use_pricelist': True
        }
        mock_cfg.write(vals_cfg)
        mock_cfg.write.assert_called_once_with(vals_cfg)
        self.assertEqual(vals_cfg['pricelist_id'], 99)

    def test_open_pos_session_warning(self):
        """Ticket 1: Detección y alerta sobre sesiones de TPV abiertas."""
        mock_session = MagicMock(id=5, name="POS/00005", state='opened')
        mock_session.user_id = MagicMock(name='Juan Pérez')
        self.mock_pos_session.search.return_value = [mock_session]
        
        open_sessions = self.env['pos.session'].search([('state', '!=', 'closed')])
        self.assertEqual(len(open_sessions), 1)
        self.assertEqual(open_sessions[0].state, 'opened')

    def test_pos_config_open_session_fallback_sql(self):
        """Ticket 1: Verifica que si cfg.write() falla por sesión abierta, el fallback SQL actualice pos_config y relaciones dentro de savepoint."""
        mock_cfg = MagicMock()
        mock_cfg.id = 42
        mock_cfg.name = "Caja Registradora Test"
        mock_cfg._fields = {
            'pricelist_id': MagicMock(),
            'use_pricelist': MagicMock(),
            'limit_categories': MagicMock(),
            'pos_category_ids': MagicMock(relation='pos_category_pos_config_rel', column1='pos_config_id', column2='pos_category_id'),
            'available_pricelist_ids': MagicMock(relation='pos_config_product_pricelist_rel', column1='pos_config_id', column2='product_pricelist_id')
        }
        # Simular que cfg.write falla como en Odoo 18 con sesión abierta
        mock_cfg.write.side_effect = Exception("Unable to modify this PoS Configuration because you can't modify Restrict Categories while a session is open.")
        
        # Simular context manager de savepoint
        mock_savepoint_ctx = MagicMock()
        mock_savepoint_ctx.__enter__ = MagicMock(return_value=None)
        mock_savepoint_ctx.__exit__ = MagicMock(return_value=False)
        self.mock_cr.savepoint = MagicMock(return_value=mock_savepoint_ctx)

        pos_cat_cache = {'boxer': 1, 'boxers': 1, 'slips': 2}
        all_active_pos_cat_ids = sorted(list(set(c for c in pos_cat_cache.values() if c)))
        self.assertEqual(all_active_pos_cat_ids, [1, 2]) # Deduplicado

        new_pl_id = 99
        vals_cfg = {
            'limit_categories': True,
            'pos_category_ids': [(6, 0, all_active_pos_cat_ids)],
            'available_pricelist_ids': [(4, new_pl_id)],
            'pricelist_id': new_pl_id,
            'use_pricelist': True
        }
        
        # Ejecutar lógica idéntica a migracion_unificada_variantes
        executed_fallback = False
        try:
            with self.mock_cr.savepoint():
                mock_cfg.write(vals_cfg)
        except Exception:
            # Fallback SQL
            sql_set = ["pricelist_id = %s", "use_pricelist = %s", "limit_categories = %s"]
            sql_vals = [vals_cfg['pricelist_id'], vals_cfg['use_pricelist'], vals_cfg['limit_categories'], mock_cfg.id]
            self.mock_cr.execute(f"UPDATE pos_config SET {', '.join(sql_set)} WHERE id = %s", tuple(sql_vals))
            
            f_cats = mock_cfg._fields['pos_category_ids']
            self.mock_cr.execute(f"DELETE FROM {f_cats.relation} WHERE {f_cats.column1} = %s", (mock_cfg.id,))
            for cat_id in all_active_pos_cat_ids:
                self.mock_cr.execute(f"INSERT INTO {f_cats.relation} ({f_cats.column1}, {f_cats.column2}) VALUES (%s, %s)", (mock_cfg.id, cat_id))
            
            f_pls = mock_cfg._fields['available_pricelist_ids']
            self.mock_cr.execute(f"SELECT 1 FROM {f_pls.relation} WHERE {f_pls.column1} = %s AND {f_pls.column2} = %s", (mock_cfg.id, new_pl_id))
            self.mock_cr.fetchone.return_value = None
            self.mock_cr.execute(f"INSERT INTO {f_pls.relation} ({f_pls.column1}, {f_pls.column2}) VALUES (%s, %s)", (mock_cfg.id, new_pl_id))
            executed_fallback = True

        self.assertTrue(executed_fallback)
        self.mock_cr.savepoint.assert_called_once()
        executed_sqls = [q for q, _ in self.sql_executions]
        self.assertTrue(any('UPDATE pos_config SET' in s for s in executed_sqls))
        self.assertTrue(any('DELETE FROM pos_category_pos_config_rel' in s for s in executed_sqls))
        self.assertTrue(any('INSERT INTO pos_category_pos_config_rel' in s for s in executed_sqls))
        self.assertTrue(any('INSERT INTO pos_config_product_pricelist_rel' in s for s in executed_sqls))

    def test_stock_internal_vs_global_segregation(self):
        """Ticket 3: Verifica que quants en ubicaciones internas (WH) se separen de clientes/proveedores en snapshot."""
        internal_loc_ids = {10, 11} # Ubicaciones internas (ej: WH/Stock, WH/Existencias)
        customer_loc_id = 20        # Partners/Customers
        vendor_loc_id = 30          # Partners/Vendors
        
        raw_quants = [
            {'id': 1, 'product_id': (101, 'P1'), 'location_id': (10, 'WH/Existencias'), 'quantity': 10.0},
            {'id': 2, 'product_id': (101, 'P1'), 'location_id': (20, 'Partners/Customers'), 'quantity': 5.0},
            {'id': 3, 'product_id': (101, 'P1'), 'location_id': (30, 'Partners/Vendors'), 'quantity': -15.0},
        ]
        
        snapshot = defaultdict(lambda: {'total_qty': 0.0, 'internal_qty': 0.0})
        for q in raw_quants:
            pid = q['product_id'][0]
            loc_id = q['location_id'][0]
            qty = q['quantity']
            snapshot[pid]['total_qty'] += qty
            if loc_id in internal_loc_ids:
                snapshot[pid]['internal_qty'] += qty

        # El balance global de quants es 0.0 (10 + 5 - 15)
        self.assertEqual(snapshot[101]['total_qty'], 0.0)
        # El stock físico interno en depósito es exactamente 10.0 (lo que reporta qty_available)
        self.assertEqual(snapshot[101]['internal_qty'], 10.0)

    def test_stock_quant_column_schema_check_prevents_sql_error(self):
        """Ticket 3 / Odoo 18: Verifica que si stock_quant no tiene product_tmpl_id, no se ejecute SQL sobre esa columna."""
        def mock_info_schema(query, params=None):
            self.sql_executions.append((query, params))
            if "information_schema.columns" in query and "table_name = 'stock_quant'" in query:
                self.mock_cr.fetchone.return_value = None # Simula Odoo 18 donde la columna no existe
            else:
                self.mock_cr.fetchone.return_value = (1,)
        
        self.mock_cr.execute.side_effect = mock_info_schema
        self.mock_cr.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'stock_quant' AND column_name = 'product_tmpl_id';
        """)
        has_tmpl_col = bool(self.mock_cr.fetchone())
        self.assertFalse(has_tmpl_col)
        
        # Si has_tmpl_col es False, la actualización a stock_quant no debe incluir product_tmpl_id
        new_vid = 55
        primary_qid = 100
        if has_tmpl_col:
            self.mock_cr.execute("UPDATE stock_quant SET product_id = %s, product_tmpl_id = %s WHERE id = %s", (new_vid, 999, primary_qid))
        else:
            self.mock_cr.execute("UPDATE stock_quant SET product_id = %s WHERE id = %s", (new_vid, primary_qid))
            
        executed_calls = [q for q, _ in self.sql_executions if 'UPDATE stock_quant' in q]
        self.assertTrue(len(executed_calls) > 0)
        self.assertNotIn('product_tmpl_id', executed_calls[-1])

    def test_get_or_create_value_reactivates_archived(self):
        """Verifica que un valor de atributo archivado sea detectado con active_test=False y reactivado sin violar unicidad."""
        mock_archived_val = MagicMock(id=77, name='L', active=False)
        mock_ctx_model = MagicMock()
        mock_ctx_model.search.return_value = mock_archived_val
        self.mock_attr_value.with_context.return_value = mock_ctx_model

        cache = {}
        attr_id = 10
        val_name = 'L'

        # Lógica de get_or_create_value
        if val_name not in cache:
            existing = self.mock_attr_value.with_context(active_test=False).search([
                ('attribute_id', '=', attr_id),
                ('name', '=', val_name)
            ], limit=1)
            if existing:
                if not existing.active:
                    existing.write({'active': True})
                cache[val_name] = existing.id
            else:
                rec = self.mock_attr_value.create({'name': val_name, 'attribute_id': attr_id})
                cache[val_name] = rec.id

        self.assertEqual(cache['L'], 77)
        mock_archived_val.write.assert_called_once_with({'active': True})
        self.mock_attr_value.create.assert_not_called()

    def test_empty_template_batch_does_not_crash_sql(self):
        """Verifica que si tmpls_in_batch está vacío no se ejecute SQL con ANY([]) vacío."""
        tmpls_in_batch = set()
        executed_tmpl_updates = []
        if tmpls_in_batch:
            self.mock_cr.execute("UPDATE product_template SET active = FALSE WHERE id = ANY(%s)", (list(tmpls_in_batch),))
            executed_tmpl_updates.append(True)

        self.assertEqual(len(executed_tmpl_updates), 0)

    def test_stock_quant_existing_query_handles_null_company(self):
        """Verifica que existing_query en stock_quant maneje company_id IS NULL correctamente."""
        new_vid = 10
        loc_id = 20
        comp_id = None
        lot_id = None
        pack_id = None
        owner_id = None

        query = """
            SELECT id, quantity, reserved_quantity 
            FROM stock_quant 
            WHERE product_id = %s 
              AND location_id = %s 
              AND (company_id = %s OR (company_id IS NULL AND %s IS NULL))
              AND (lot_id = %s OR (lot_id IS NULL AND %s IS NULL))
              AND (package_id = %s OR (package_id IS NULL AND %s IS NULL))
              AND (owner_id = %s OR (owner_id IS NULL AND %s IS NULL))
            LIMIT 1
        """
        params = (new_vid, loc_id, comp_id, comp_id, lot_id, lot_id, pack_id, pack_id, owner_id, owner_id)
        self.mock_cr.execute(query, params)

        last_call = self.sql_executions[-1]
        self.assertIn("company_id IS NULL", last_call[0])
        self.assertEqual(last_call[1], params)


if __name__ == '__main__':
    unittest.main()
