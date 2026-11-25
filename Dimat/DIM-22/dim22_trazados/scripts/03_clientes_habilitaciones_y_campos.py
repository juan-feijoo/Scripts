# -*- coding: utf-8 -*-
# 03 - Clientes, campos de res.partner, etiquetas, advertencias, notas, adjuntos y Documents (solo lectura)
import re

h('03 - CLIENTES: CAMPOS, ETIQUETAS, ADVERTENCIAS, NOTAS Y DOCUMENTOS')

KEYWORDS = ('hab', 'traz', 'renpre', 'sedro', 'precur', 'cert', 'lic', 'perm', 'vto', 'venc', 'expir', 'anmat', 'disp', 'inscrip', 'reg')
KW_RE = re.compile(r'hab|traz|renpre|sedro|precur|cert|lic|perm|vto|venc|expir|anmat|disp|inscrip', re.I)

sub('Campos custom o relevantes en res.partner (ir.model.fields)')
partner_fields = env['ir.model.fields'].search([('model', '=', 'res.partner')], order='name')
for f in partner_fields:
    blob = ('%s %s %s' % (f.name, f.field_description or '', f.modules or '')).lower()
    is_custom = f.name.startswith('x_') or f.state == 'manual'
    is_non_core = bool(f.modules) and any(m.strip().startswith(('l10n_', 'custom', 'dimat', 'studio')) for m in f.modules.split(','))
    has_kw = any(k in blob for k in KEYWORDS)
    if is_custom or is_non_core or has_kw or f.name in ('category_id', 'industry_id', 'comment', 'ref', 'sale_warn', 'sale_warn_msg', 'purchase_warn', 'purchase_warn_msg'):
        print('  %-38s | %-12s | state=%-7s | mods=%-25s | label=%r' % (
            f.name, f.ttype, f.state, (f.modules or '')[:25], f.field_description,
        ))

RP = env['res.partner'].with_context(active_test=False)
print('\nTotal res.partner (activos e inactivos): %s (activos=%s)' % (
    RP.search_count([]), env['res.partner'].search_count([]),
))

sub('Etiquetas de contacto (res.partner.category)')
cats = env['res.partner.category'].with_context(active_test=False).search([], order='name')
print('Total res.partner.category: %s' % len(cats))
for cat in cats:
    cnt = RP.search_count([('category_id', 'in', [cat.id])])
    print('  id=%-4s | active=%-5s | partners=%-5s | parent=%r | name=%r' % (
        cat.id, cat.active, cnt, cat.parent_id.name if cat.parent_id else '', cat.name,
    ))

sub('Industrias / Rubros (res.partner.industry)')
if 'res.partner.industry' in env:
    inds = env['res.partner.industry'].with_context(active_test=False).search([], order='name')
    print('Total res.partner.industry: %s' % len(inds))
    for ind in inds:
        cnt = RP.search_count([('industry_id', '=', ind.id)])
        print('  id=%-4s | active=%-5s | partners=%-5s | name=%r (%r)' % (
            ind.id, ind.active, cnt, ind.name, ind.full_name,
        ))

sub('Partners con advertencia nativa (sale_warn / purchase_warn != no-message)')
for wf in ('sale_warn', 'purchase_warn'):
    if has_field('res.partner', wf):
        wrecs = RP.search([(wf, '!=', 'no-message'), (wf, '!=', False)])
        print('  %s configurados: %s' % (wf, len(wrecs)))
        for p in wrecs[:40]:
            msg_f = wf + '_msg'
            print('    id=%-6s | vat=%-13r | %-35r | %s=%s | msg=%r' % (
                p.id, p.vat or '', p.name, wf, p[wf], p[msg_f] if has_field('res.partner', msg_f) else '',
            ))

sub('Partners con texto en Notas internas (comment) o ref que coincida con keywords')
comment_matches = []
# Búsqueda acotada por SQL ilike para no traer toda la tabla si es grande
kw_domain = ['|'] * (len(KEYWORDS) - 1)
for k in KEYWORDS:
    kw_domain.append(('comment', 'ilike', k))
for p in RP.search([('comment', '!=', False)] + kw_domain, limit=100):
    txt = strip_html(p.comment)
    if KW_RE.search(txt):
        comment_matches.append((p, txt))
print('Partners con match en comment (hasta 100 revisados): %s' % len(comment_matches))
for p, txt in comment_matches[:40]:
    print('  id=%-6s | vat=%-13r | %-35r | comment=%r' % (p.id, p.vat or '', p.name, txt[:180]))

sub('Partners con campos x_* cargados (no vacíos)')
x_partner_fields = [f.name for f in partner_fields if f.name.startswith('x_') and f.ttype not in ('one2many',)]
if x_partner_fields:
    for fname in x_partner_fields:
        ftype = env['res.partner']._fields[fname].type
        dom = [(fname, '!=', False)]
        if ftype in ('char', 'text', 'html'):
            dom.append((fname, '!=', ''))
        cnt = RP.search_count(dom)
        print('  Campo %-35s (%s): %s partners con valor' % (fname, ftype, cnt))
        if cnt:
            for p in RP.search(dom, limit=15):
                print('    id=%-6s | %-35r | val=%s' % (p.id, p.name, fmt(p, fname, max_len=100)))
else:
    print('  No hay campos x_* en res.partner.')

sub('Adjuntos (ir.attachment) vinculados a res.partner')
Att = env['ir.attachment'].with_context(active_test=False)
total_att = Att.search_count([('res_model', '=', 'res.partner')])
print('Total adjuntos en res.partner: %s' % total_att)
att_kw_dom = ['|'] * (len(KEYWORDS) - 1) + [('name', 'ilike', k) for k in KEYWORDS]
kw_atts = Att.search([('res_model', '=', 'res.partner')] + att_kw_dom, order='id desc', limit=50)
print('Adjuntos en res.partner con nombre por keyword (hasta 50): %s' % len(kw_atts))
for a in kw_atts:
    p = RP.browse(a.res_id).exists()
    print('  att_id=%-6s | partner_id=%-6s (%r) | %s | name=%r' % (
        a.id, a.res_id, p.display_name if p else '?', a.create_date, a.name,
    ))

print('Muestra de los últimos 20 adjuntos generales en res.partner:')
for a in Att.search([('res_model', '=', 'res.partner')], order='id desc', limit=20):
    p = RP.browse(a.res_id).exists()
    print('  att_id=%-6s | partner_id=%-6s (%r) | %s | name=%r' % (
        a.id, a.res_id, p.display_name if p else '?', a.create_date, a.name,
    ))

if 'documents.document' in env:
    sub('Módulo Documents (documents.document)')
    Doc = env['documents.document'].with_context(active_test=False)
    print('Total documents.document: %s' % Doc.search_count([]))
    if has_field('documents.document', 'type'):
        folders = Doc.search([('type', '=', 'folder')], order='name')
        print('Carpetas (type=folder): %s' % len(folders))
        for fl in folders[:50]:
            print('  id=%-5s | parent=%r | name=%r' % (
                fl.id, fl.folder_id.name if has_field('documents.document', 'folder_id') and fl.folder_id else '', fl.name,
            ))
    if 'documents.tag' in env:
        dtags = env['documents.tag'].search([], order='name')
        print('Etiquetas Documents (documents.tag): %s' % len(dtags))
        for dt in dtags[:50]:
            print('  id=%-5s | name=%r' % (dt.id, dt.display_name))
    doc_kw_dom = ['|'] * (len(KEYWORDS) - 1) + [('name', 'ilike', k) for k in KEYWORDS]
    kw_docs = Doc.search(doc_kw_dom, order='id desc', limit=40)
    print('Documentos por keyword (hasta 40): %s' % len(kw_docs))
    for d in kw_docs:
        print('  id=%-6s | partner=%s | folder=%s | name=%r' % (
            d.id,
            fmt(d, 'partner_id') if has_field('documents.document', 'partner_id') else '-',
            fmt(d, 'folder_id') if has_field('documents.document', 'folder_id') else '-',
            d.name,
        ))
