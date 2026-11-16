# -*- coding: utf-8 -*-
# 02 - Auditoría completa de impuestos (account.tax), posiciones fiscales y diarios
from collections import Counter

company = get_company()
h('02 - IMPUESTOS, POSICIONES FISCALES Y DIARIOS (%s)' % company.name)

# 1. Resumen general de account.tax
sub('Resumen de account.tax (active_test=False)')
all_taxes = env['account.tax'].with_context(active_test=False).search([
    ('company_id', '=', company.id),
], order='type_tax_use, id')
print('  Total impuestos en compañía: %d' % len(all_taxes))

by_use_group = Counter((t.type_tax_use, t.active, t.tax_group_id.name if t.tax_group_id else 'Sin Grupo') for t in all_taxes)
for (use, act, grp), cnt in sorted(by_use_group.items()):
    print('    uso=%-8s | active=%-5s | grupo=%-30s : %d' % (use, act, grp, cnt))

# 2. Impuestos relevantes: Retenciones, Percepciones, IIBB, ARBA, Jurisdicción AR
sub('Detalle de impuestos de Retención / Percepción / IIBB / Jurisdicción AR')
rel_taxes = all_taxes.filtered(lambda t: (
    t.type_tax_use == 'none'
    or (has_field('account.tax', 'l10n_ar_withholding_payment_type') and t.l10n_ar_withholding_payment_type)
    or (has_field('account.tax', 'l10n_ar_state_id') and t.l10n_ar_state_id)
    or (t.tax_group_id and getattr(t.tax_group_id, 'l10n_ar_tribute_afip_code', False))
    or any(k in (t.name or '').lower() for k in ('arba', 'iibb', 'perc', 'ret', 'bs', 'buenos aires', 'agip', 'sire', 'sicore'))
))
print('  Impuestos relevantes encontrados: %d' % len(rel_taxes))
for t in rel_taxes:
    tg = t.tax_group_id
    tg_info = '%s (id=%s, afip=%s)' % (
        tg.name, tg.id, getattr(tg, 'l10n_ar_tribute_afip_code', False)
    ) if tg else 'Sin Grupo'
    state = getattr(t, 'l10n_ar_state_id', False)
    state_info = '%s (cod=%s)' % (state.name, getattr(state, 'jurisdiction_code', '?')) if state else 'Sin Prov.'
    seq = getattr(t, 'l10n_ar_withholding_sequence_id', False)
    seq_info = '%s (id=%s)' % (seq.name, seq.id) if seq else 'SIN SECUENCIA'
    wtype = getattr(t, 'l10n_ar_withholding_payment_type', False)
    ttype = getattr(t, 'l10n_ar_tax_type', False)
    print('\n  [%d] %s | active=%s | use=%s | amount_type=%s | amount=%.4f' % (
        t.id, t.name, t.active, t.type_tax_use, t.amount_type, t.amount
    ))
    print('      grupo=%s | prov=%s | wth_pay_type=%s | l10n_ar_tax_type=%s | seq=%s' % (
        tg_info, state_info, wtype, ttype, seq_info
    ))
    if has_field('account.tax', 'l10n_ar_minimum_threshold'):
        print('      umbrales: min_tax=%s | min_base=%s | min_pay=%s | non_taxable=%s' % (
            getattr(t, 'l10n_ar_minimum_threshold', None),
            getattr(t, 'l10n_ar_base_minimum_threshold', None),
            getattr(t, 'l10n_ar_payment_minimum_threshold', None),
            getattr(t, 'l10n_ar_non_taxable_amount', None),
        ))
    for rep in t.invoice_repartition_line_ids:
        acc = rep.account_id
        tags = ', '.join(rep.tag_ids.mapped('name'))
        print('      rep(inv)  %-6s | cuenta=%s | tags=[%s]' % (
            rep.repartition_type, ('%s %s' % (acc.code, acc.name)) if acc else 'False', tags
        ))
    for rep in t.refund_repartition_line_ids:
        acc = rep.account_id
        tags = ', '.join(rep.tag_ids.mapped('name'))
        print('      rep(ref)  %-6s | cuenta=%s | tags=[%s]' % (
            rep.repartition_type, ('%s %s' % (acc.code, acc.name)) if acc else 'False', tags
        ))

# 3. Grupos de impuestos
sub('Grupos de Impuestos (account.tax.group) de la compañía o globales')
groups = env['account.tax.group'].search(['|', ('company_id', '=', company.id), ('company_id', '=', False)])
for g in groups:
    print('  [%3d] %-35s | cia=%s | afip_tribute=%s | vat_code=%s' % (
        g.id, g.name, g.company_id.id if g.company_id else 'Global',
        getattr(g, 'l10n_ar_tribute_afip_code', False),
        getattr(g, 'l10n_ar_vat_afip_code', False),
    ))

# 4. Posiciones Fiscales
sub('Posiciones Fiscales (account.fiscal.position, active_test=False)')
fpos_list = env['account.fiscal.position'].with_context(active_test=False).search([
    ('company_id', '=', company.id),
], order='sequence, id')
print('  Total posiciones fiscales: %d' % len(fpos_list))
for fp in fpos_list:
    resp = ', '.join(fp.l10n_ar_afip_responsibility_type_ids.mapped('name')) if has_field('account.fiscal.position', 'l10n_ar_afip_responsibility_type_ids') else 'N/A'
    states = ', '.join(fp.state_ids.mapped('name')) if fp.state_ids else 'Todas'
    print('\n  [%d] %s | active=%s | seq=%s | auto_apply=%s | vat_req=%s | country=%s' % (
        fp.id, fp.name, fp.active, fp.sequence, fp.auto_apply, fp.vat_required,
        fp.country_id.code if fp.country_id else 'Cualquiera',
    ))
    print('      estados=[%s] | resp_afip=[%s]' % (states, resp))
    if fp.tax_ids:
        print('      mapeo tax_ids (%d):' % len(fp.tax_ids))
        for m in fp.tax_ids[:15]:
            print('        %s -> %s' % (m.tax_src_id.name, m.tax_dest_id.name if m.tax_dest_id else 'QUITAR'))
    if has_field('account.fiscal.position', 'l10n_ar_tax_ids'):
        if fp.l10n_ar_tax_ids:
            print('      líneas l10n_ar_tax_ids (%d):' % len(fp.l10n_ar_tax_ids))
            for lt in fp.l10n_ar_tax_ids:
                dt = lt.default_tax_id
                dt_state = dt.l10n_ar_state_id.name if (dt and has_field('account.tax', 'l10n_ar_state_id') and dt.l10n_ar_state_id) else 'Sin Prov.'
                print('        - [%d] tax_type=%-11s | webservice=%-15s | default_tax=[%d] %s (%.2f%%, active=%s, use=%s, wth=%s, prov=%s, grp=%s)' % (
                    lt.id, lt.tax_type, lt.webservice or 'Manual/Fijo',
                    dt.id if dt else 0, dt.name if dt else 'NONE', dt.amount if dt else 0.0,
                    dt.active if dt else False, dt.type_tax_use if dt else '',
                    getattr(dt, 'l10n_ar_withholding_payment_type', False) if dt else False,
                    dt_state, dt.tax_group_id.name if (dt and dt.tax_group_id) else ''
                ))
        else:
            print('      líneas l10n_ar_tax_ids: (vacío)')

# 5. Diarios de pago y facturación
sub('Diarios de la compañía (bank/cash/sale/purchase)')
journals = env['account.journal'].with_context(active_test=False).search([
    ('company_id', '=', company.id),
    ('type', 'in', ['bank', 'cash', 'sale', 'purchase']),
], order='type, id')
for j in journals:
    extra = ''
    if j.type in ('sale', 'purchase'):
        extra = ' | use_docs=%s | pos_sys=%s | default_taxes=%s' % (
            getattr(j, 'l10n_latam_use_documents', None),
            getattr(j, 'l10n_ar_afip_pos_system', None),
            j.default_account_id.tax_ids.mapped('name') if j.default_account_id else []
        )
    print('  [%3d] %-8s | active=%-5s | %s%s' % (j.id, j.type, j.active, j.name, extra))
