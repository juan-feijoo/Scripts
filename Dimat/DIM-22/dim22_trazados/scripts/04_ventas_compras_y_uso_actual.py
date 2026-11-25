# -*- coding: utf-8 -*-
# 04 - Análisis histórico de Ventas, Compras, Inventario y Facturas con productos "/" (solo lectura)
from collections import Counter

h('04 - HISTÓRICO DE VENTAS, COMPRAS, STOCK Y FACTURAS CON PRODUCTOS %r' % TRACED_PREFIX)

PT = env['product.template'].with_context(active_test=False)
traced_tmpls = PT.search([('name', '=like', TRACED_PREFIX + '%')])
leading_ws = PT.search([('name', 'ilike', TRACED_PREFIX)]).filtered(
    lambda p: (p.name or '').lstrip().startswith(TRACED_PREFIX) and p.id not in traced_tmpls.ids
)
traced_tmpls = traced_tmpls | leading_ws
traced_prods = env['product.product'].with_context(active_test=False).search([
    ('product_tmpl_id', 'in', traced_tmpls.ids),
])
print('Templates detectados: %s | Variantes product.product: %s' % (len(traced_tmpls), len(traced_prods)))

if not traced_prods:
    print('No se encontraron productos con prefijo %r. Fin del análisis.' % TRACED_PREFIX)
else:
    # ------------------------------------------------------------------ VENTAS
    if 'sale.order.line' in env:
        sub('Ventas (sale.order.line) con productos trazados')
        sols = env['sale.order.line'].search([('product_id', 'in', traced_prods.ids)])
        print('Total líneas sale.order.line: %s | Pedidos distintos: %s' % (len(sols), len(sols.mapped('order_id'))))
        state_cnt = Counter(sols.mapped('order_id.state'))
        print('Líneas por estado de pedido: %s' % dict(state_cnt))
        if sols:
            dates = [d for d in sols.mapped('order_id.date_order') if d]
            if dates:
                print('Rango date_order: %s .. %s' % (min(dates), max(dates)))

        # Analizar clientes compradores reales (confirmados o todos) para descubrir cómo marcan habilitación
        buyer_counts = Counter()
        confirmed_buyer_counts = Counter()
        for line in sols:
            cp = line.order_id.partner_id.commercial_partner_id
            if cp:
                buyer_counts[cp.id] += 1
                if line.order_id.state in ('sale', 'done'):
                    confirmed_buyer_counts[cp.id] += 1

        print('Clientes comerciales distintos (todos los presupuestos/pedidos): %s' % len(buyer_counts))
        print('Clientes comerciales distintos (pedidos confirmados): %s' % len(confirmed_buyer_counts))

        # Inspeccionar los top 50 clientes confirmados (o todos si <= 50)
        top_ids = [pid for pid, _ in (confirmed_buyer_counts or buyer_counts).most_common(50)]
        Att = env['ir.attachment'].with_context(active_test=False)
        Doc = env['documents.document'].with_context(active_test=False) if 'documents.document' in env else None

        sub('Perfil de los clientes que compraron productos "/" (top %s)' % len(top_ids))
        partners = env['res.partner'].with_context(active_test=False).browse(top_ids)
        x_fnames = [fname for fname in sorted(env['res.partner']._fields) if fname.startswith('x_')]
        for p in partners:
            family_ids = (p | p.child_ids).ids
            att_cnt = Att.search_count([('res_model', '=', 'res.partner'), ('res_id', 'in', family_ids)])
            att_names = Att.search([('res_model', '=', 'res.partner'), ('res_id', 'in', family_ids)], limit=5).mapped('name')
            doc_cnt = 0
            if Doc is not None and has_field('documents.document', 'partner_id'):
                doc_cnt = Doc.search_count([('partner_id', 'in', family_ids)])
            extras = []
            if p.category_id:
                extras.append('tags=%s' % p.category_id.mapped('name'))
            if has_field('res.partner', 'industry_id') and p.industry_id:
                extras.append('ind=%r' % p.industry_id.name)
            if has_field('res.partner', 'sale_warn') and p.sale_warn != 'no-message':
                extras.append('warn=%s:%r' % (p.sale_warn, p.sale_warn_msg))
            if p.ref:
                extras.append('ref=%r' % p.ref)
            if p.comment:
                extras.append('comment=%r' % strip_html(p.comment)[:100])
            if att_cnt:
                extras.append('atts=%s %s' % (att_cnt, att_names))
            if doc_cnt:
                extras.append('docs=%s' % doc_cnt)
            x_non_empty = {fn: fmt(p, fn, max_len=60) for fn in x_fnames if fmt(p, fn, max_len=60) not in (False, None, '', 0, 0.0, '[]')}
            if x_non_empty:
                extras.append('x_=%s' % x_non_empty)

            print('  id=%-6s | conf=%-3s | tot=%-3s | vat=%-13r | %-35r%s' % (
                p.id, confirmed_buyer_counts.get(p.id, 0), buyer_counts.get(p.id, 0),
                p.vat or '', p.name, (' | ' + ' | '.join(extras)) if extras else '',
            ))

    # ------------------------------------------------------------------ COMPRAS
    if 'purchase.order.line' in env:
        sub('Compras (purchase.order.line) con productos trazados')
        pols = env['purchase.order.line'].search([('product_id', 'in', traced_prods.ids)])
        print('Total líneas purchase.order.line: %s | Órdenes: %s' % (len(pols), len(pols.mapped('order_id'))))
        print('Líneas por estado: %s' % dict(Counter(pols.mapped('order_id.state'))))
        sup_cnt = Counter(
            l.order_id.partner_id.commercial_partner_id.id
            for l in pols if l.order_id.partner_id
        )
        print('Proveedores comerciales distintos: %s' % len(sup_cnt))
        for sid, cnt in sup_cnt.most_common(25):
            sp = env['res.partner'].with_context(active_test=False).browse(sid)
            print('  id=%-6s | lineas=%-4s | vat=%-13r | %-35r | tags=%s' % (
                sp.id, cnt, sp.vat or '', sp.name, sp.category_id.mapped('name'),
            ))

    # ------------------------------------------------------------------ INVENTARIO / LOTES
    if 'stock.move' in env:
        sub('Movimientos de stock (stock.move / stock.move.line) con productos trazados')
        moves = env['stock.move'].search([('product_id', 'in', traced_prods.ids)])
        print('Total stock.move: %s' % len(moves))
        print('Por estado: %s' % dict(Counter(moves.mapped('state'))))
        print('Por tipo de operación: %s' % dict(Counter(m.picking_type_id.code or '?' for m in moves)))
        smls = env['stock.move.line'].search([('product_id', 'in', traced_prods.ids)])
        has_lot_name = has_field('stock.move.line', 'lot_name')
        with_lot = smls.filtered(lambda l: l.lot_id or (has_lot_name and l.lot_name))
        print('stock.move.line totales: %s | con lote/serie asignado: %s' % (len(smls), len(with_lot)))

    # ------------------------------------------------------------------ FACTURACIÓN
    if 'account.move.line' in env:
        sub('Facturas/NC (account.move.line) con productos trazados')
        amls = env['account.move.line'].search([
            ('product_id', 'in', traced_prods.ids),
            ('move_id.move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']),
        ])
        print('Total account.move.line: %s | Comprobantes distintos: %s' % (len(amls), len(amls.mapped('move_id'))))
        print('Por (move_type, state): %s' % dict(Counter((l.move_id.move_type, l.move_id.state) for l in amls)))
        if has_field('account.move', 'l10n_latam_document_type_id'):
            posted_amls = amls.filtered(lambda l: l.move_id.state == 'posted')
            print('Tipos de comprobante ARCA (posted): %s' % dict(Counter(
                l.move_id.l10n_latam_document_type_id.name or 'Sin tipo' for l in posted_amls
            )))
