# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT 02: EXPORTACIÓN RÁPIDA DE CONTACTOS ACTIVOS (JSON)
================================================================================
Propósito:
    Exportar los CUITs de contactos comerciales activos en Odoo para cruzarlos
    con el padrón ARBA 11/2026 (PadronRGS112026.zip) en local.

Ejecución en Odoo Shell:
    python3 odoo-bin shell -d $PGDATABASE < scripts/02_export_partners_cuit.py
    o pegar en la consola shell. Genera 'partners_cuit.json' en la carpeta actual.
================================================================================
"""

import json
import re

company = env.company
partners = env['res.partner'].search([
    ('is_company', '=', True),
    ('vat', '!=', False)
])

data = []
for p in partners:
    raw_vat = re.sub(r'\D', '', p.vat or '')
    if len(raw_vat) == 11:
        # Extraer impuestos vigentes asignados si existe el modelo
        existing_taxes = []
        if hasattr(p, 'l10n_ar_partner_tax_ids'):
            for t in p.l10n_ar_partner_tax_ids:
                existing_taxes.append({
                    'type': 'withholding',
                    'tax_id': t.tax_id.id,
                    'tax_name': t.tax_id.name,
                    'from_date': str(t.from_date) if t.from_date else None,
                    'to_date': str(t.to_date) if t.to_date else None,
                })
        if hasattr(p, 'l10n_ar_partner_perception_ids'):
            for t in p.l10n_ar_partner_perception_ids:
                existing_taxes.append({
                    'type': 'perception',
                    'tax_id': t.tax_id.id,
                    'tax_name': t.tax_id.name,
                    'from_date': str(t.from_date) if t.from_date else None,
                    'to_date': str(t.to_date) if t.to_date else None,
                })

        data.append({
            'id': p.id,
            'name': p.name,
            'vat': raw_vat,
            'customer_rank': p.customer_rank,
            'supplier_rank': p.supplier_rank,
            'existing_taxes': existing_taxes
        })

output_file = 'partners_cuit.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\n[OK] Exportados {len(data):,} contactos con CUIT válido a '{output_file}'.")
print(f"     - Clientes (customer_rank > 0):    {sum(1 for x in data if x['customer_rank'] > 0):,}")
print(f"     - Proveedores (supplier_rank > 0): {sum(1 for x in data if x['supplier_rank'] > 0):,}")
