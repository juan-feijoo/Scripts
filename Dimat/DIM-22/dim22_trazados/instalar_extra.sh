#!/bin/bash
# Pegar completo en el shell de Odoo.sh. Crea/actualiza ~/tmp/dim22_trazados
mkdir -p ~/tmp/dim22_trazados/scripts && cd ~/tmp/dim22_trazados
cat > ~/tmp/dim22_trazados/scripts/07_inspeccion_xml_objetivo.py <<'__EOF_AUDIT__'
# -*- coding: utf-8 -*-
# 07 - Inspección de XMLs reales de Odoo 18 (vistas y QWeb a heredar) + universo completo de trazados (solo lectura)
import re

h('07 - VISTAS REALES ODOO 18, QWEB Y CATÁLOGO COMPLETO DE TRAZADOS')

VIEW_XMLIDS = [
    # Productos
    'product.product_template_kanban_view',
    'product.product_kanban_view',
    'product.product_normal_form_view',
    'product.product_product_tree_view',
    # Contactos
    'base.view_partner_form',
    'base.view_partner_tree',
    'base.view_res_partner_filter',
    # Ventas
    'sale.view_quotation_tree',
    'sale.view_order_tree',
    'sale.view_sales_order_filter',
    # Compras
    'purchase.purchase_order_kpis_tree',
    'purchase.purchase_order_view_tree',
    'purchase.view_purchase_order_filter',
    # Stock
    'stock.view_picking_form',
    'stock.vpicktree',
    'stock.view_picking_internal_search',
    # Facturas / Asientos
    'account.view_move_form',
    'account.view_out_invoice_tree',
    'account.view_in_invoice_bill_tree',
    'account.view_invoice_tree',
    'account.view_account_invoice_filter',
]

QWEB_XMLIDS = [
    'sale.report_saleorder_document',
    'purchase.report_purchaseorder_document',
    'l10n_ar_purchase.report_purchaseorder_document',
    'stock.report_delivery_document',
    'account.report_invoice_document',
    'l10n_ar.report_invoice_document',
    'sale.sale_order_portal_content',
    'account.portal_invoice_page',
]

sub('Vistas UI objetivo (arch combinado real en Odoo 18)')
for xmlid in VIEW_XMLIDS:
    v = env.ref(xmlid, raise_if_not_found=False)
    if not v:
        print('  [NO EXISTE] %s' % xmlid)
        continue
    print('\n>>> %s (id=%s, type=%s, model=%s)' % (xmlid, v.id, v.type, v.model))
    arch = safe(v.get_combined_arch) or v.arch_db or ''
    lines = arch.splitlines()
    if v.type in ('list', 'tree', 'kanban', 'search') or len(lines) <= 140:
        print('\n'.join('  ' + ln for ln in lines[:220]))
        if len(lines) > 220:
            print('  ... <truncado, %s líneas totales>' % len(lines))
    else:
        # En form views largas mostramos nodos estructurales clave
        interesting = re.compile(
            r'<form|<header|<sheet|button_box|web_ribbon|<notebook|<page|move_ids_without_package|'
            r'invoice_line_ids|order_line|<list|<tree|fiscal_data|sales_purchases|vat|category_id|comment'
        )
        for idx, ln in enumerate(lines, 1):
            if idx <= 45 or interesting.search(ln):
                print('  L%-4d %s' % (idx, ln))

sub('Reportes QWeb y Portal (arch_db y estructura de tabla/totales)')
for xmlid in QWEB_XMLIDS:
    v = env.ref(xmlid, raise_if_not_found=False)
    if not v:
        print('  [NO EXISTE] %s' % xmlid)
        continue
    print('\n>>> QWEB %s (id=%s, inherit_id=%s)' % (
        xmlid, v.id, (v.inherit_id.xml_id if has_field('ir.ui.view', 'xml_id') else v.inherit_id.name) if v.inherit_id else '-',
    ))
    arch = v.arch_db or ''
    lines = arch.splitlines()
    print('  --- arch_db (%s líneas) ---' % len(lines))
    for idx, ln in enumerate(lines[:180], 1):
        print('  L%-4d %s' % (idx, ln))
    if len(lines) > 180:
        print('  ... <truncado arch_db, %s líneas>' % len(lines))
    comb = safe(v.get_combined_arch)
    if comb and comb != arch:
        clines = comb.splitlines()
        print('  --- combined_arch líneas clave (%s líneas) ---' % len(clines))
        qinteresting = re.compile(
            r'o_main_table|th_|td_|line\.name|move_line|product_id|invoice_tbody|'
            r'payment_term|comment|narration|note|informations|footer'
        )
        for idx, ln in enumerate(clines, 1):
            if qinteresting.search(ln):
                print('  CL%-4d %s' % (idx, ln))

sub('Universo completo de posibles productos trazados/controlados en product.template')
PT = env['product.template'].with_context(active_test=False)
all_prods = PT.search([], order='name')
kw_re = re.compile(r'traz|psico|estup|sedro|renpre|anmat|precur|informar|\binf\b', re.I)

slash_prods = PT.browse()
matched_kw = []
for p in all_prods:
    name = p.name or ''
    marca = (p.x_studio_marca or '') if has_field('product.template', 'x_studio_marca') else ''
    starts_slash = name.lstrip().startswith(TRACED_PREFIX)
    if starts_slash:
        slash_prods |= p
    if kw_re.search(name) or kw_re.search(marca):
        matched_kw.append((p, starts_slash, marca))

print('Total con prefijo "/": %s' % len(slash_prods))
print('Total con match de keyword (name o x_studio_marca): %s' % len(matched_kw))
print('\nDetalle de los que NO empiezan con "/" pero matchean keyword (%s):' % sum(1 for _, s, _ in matched_kw if not s))
for p, starts_slash, marca in matched_kw:
    if not starts_slash:
        print('  id=%-5s | act=%-5s | ref=%-15r | marca=%-25r | name=%r' % (
            p.id, p.active, p.default_code or '', marca, p.name,
        ))
__EOF_AUDIT__
chmod +x ~/tmp/dim22_trazados/run_all.sh 2>/dev/null
echo 'Instalado en ~/tmp/dim22_trazados:'; ls -R ~/tmp/dim22_trazados | head -50
