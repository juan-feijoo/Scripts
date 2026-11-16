# -*- coding: utf-8 -*-
# 04 - Simulación controlada (ROLLBACK) del circuito completo de padrón, posición fiscal, pago y factura
import base64
import io
import os
import re
import shutil
import zipfile
from datetime import date
from odoo import fields

company = get_company()
h('04 - SIMULACIÓN DEL CIRCUITO COMPLETO (100%% ROLLBACK / SIN COMMIT) (%s)' % company.name)


class _EndSavepoint(Exception):
    pass


def run_isolated(title, fn):
    """Ejecuta fn dentro de un SAVEPOINT y siempre lo revierte al finalizar."""
    sub(title)
    try:
        with env.cr.savepoint():
            safe(fn)
            raise _EndSavepoint()
    except _EndSavepoint:
        pass


# 1. Ubicar padrón cargado (prioriza Buenos Aires / ARBA)
ba_state = env.ref('base.state_ar_b', raise_if_not_found=False)
padron = env['res.company.jurisdiction.padron'].search([
    ('company_id', '=', company.id),
    ('state_id', '=', ba_state.id if ba_state else False),
], limit=1)
if not padron:
    padron = env['res.company.jurisdiction.padron'].search([('company_id', '=', company.id)], limit=1)

if not padron:
    print('[!] No hay ningún padrón cargado en res.company.jurisdiction.padron para %s.' % company.name)
    test_date = fields.Date.today()
else:
    print('[*] Padrón encontrado: ID=%d | state=%s | %s..%s | file=%r' % (
        padron.id, padron.state_id.name, padron.l10n_ar_padron_from_date,
        padron.l10n_ar_padron_to_date, padron.filename
    ))
    test_date = padron.l10n_ar_padron_from_date or fields.Date.today()

# 2. Cruzar en memoria contra el ZIP del padrón (si existe) para elegir casos testigo reales
partners = env['res.partner'].search([('is_company', '=', True), ('vat', '!=', False)])
cuit_to_partner = {}
for p in partners:
    c = re.sub(r'\D', '', p.vat or '')
    if len(c) == 11 and c not in cuit_to_partner:
        cuit_to_partner[c] = p

ret_rates = {}
per_rates = {}
if padron and padron.file_padron:
    raw = base64.b64decode(padron.file_padron)
    buf = io.BytesIO(raw)
    if zipfile.is_zipfile(buf):
        buf.seek(0)
        with zipfile.ZipFile(buf, 'r') as zf:
            for info in zf.infolist():
                if info.is_dir() or info.file_size == 0:
                    continue
                low = info.filename.lower()
                target = ret_rates if 'ret' in low else (per_rates if 'per' in low else None)
                if target is None:
                    continue
                with zf.open(info.filename) as f:
                    for line_b in f:
                        parts = line_b.decode('latin1', errors='replace').rstrip('\r\n').split(';')
                        if len(parts) >= 9:
                            cuit_line = parts[4].strip()
                            if cuit_line in cuit_to_partner:
                                try:
                                    target[cuit_line] = float(parts[8].strip().replace(',', '.'))
                                except ValueError:
                                    pass

print('[*] En el ZIP del padrón matchearon con contactos de BD: Ret=%d, Per=%d' % (
    len(ret_rates), len(per_rates)
))

# Resumen rápido de contactos no-proveedores y comprobantes (explica customer_rank=0)
non_sup = partners.filtered(lambda p: p.supplier_rank == 0)
print('[*] Empresas totales=%d | supplier_rank>0=%d | supplier_rank==0=%d' % (
    len(partners), len(partners) - len(non_sup), len(non_sup)
))
if has_field('res.partner', 'l10n_ar_afip_responsibility_type_id'):
    resp_counts = {}
    for p in non_sup:
        rn = p.l10n_ar_afip_responsibility_type_id.name if p.l10n_ar_afip_responsibility_type_id else 'SIN_RESP_AFIP'
        resp_counts[rn] = resp_counts.get(rn, 0) + 1
    print('[*] Desglose resp_afip en supplier_rank==0: %s' % resp_counts)
for mt in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
    cnt = env['account.move'].search_count([('company_id', '=', company.id), ('move_type', '=', mt)])
    print('[*] account.move (%s) en %s: %d' % (mt, company.name, cnt))
if 'sale.order' in env:
    print('[*] sale.order en %s: %d' % (company.name, env['sale.order'].search_count([('company_id', '=', company.id)])))

# Seleccionar casos testigo reales de la BD
samples = []

def pick_partner(label, pred):
    for c, p in cuit_to_partner.items():
        if pred(c, p) and p not in [s[1] for s in samples]:
            samples.append((label, p, ret_rates.get(c), per_rates.get(c)))
            return

pick_partner('PROV_RET_MENOR_2_5', lambda c, p: p.supplier_rank > 0 and 0.0 < ret_rates.get(c, 0.0) < 2.50)
pick_partner('PROV_RET_MAYOR_IGUAL_2_5', lambda c, p: p.supplier_rank > 0 and ret_rates.get(c, 0.0) >= 2.50)
pick_partner('PROV_RESP_INSC_RET', lambda c, p: p.supplier_rank > 0 and has_field('res.partner', 'l10n_ar_afip_responsibility_type_id') and p.l10n_ar_afip_responsibility_type_id and 'Inscripto' in (p.l10n_ar_afip_responsibility_type_id.name or '') and c in ret_rates)
pick_partner('PROV_SOLO_EN_PER_NO_RET', lambda c, p: p.supplier_rank > 0 and c in per_rates and c not in ret_rates)
pick_partner('CLI_CON_PER_GT_0', lambda c, p: p.customer_rank > 0 and per_rates.get(c, 0.0) > 0.0)
if not any(s[0] == 'CLI_CON_PER_GT_0' for s in samples):
    pick_partner('NO_PROV_PER_GT_0', lambda c, p: p.supplier_rank == 0 and per_rates.get(c, 0.0) > 0.0)
pick_partner('NO_EN_PADRON', lambda c, p: (p.supplier_rank > 0 or p.customer_rank > 0) and c not in ret_rates and c not in per_rates)

if not samples and partners:
    for p in partners[:3]:
        c = re.sub(r'\D', '', p.vat or '')
        samples.append(('MUESTRA_GENERAL', p, ret_rates.get(c), per_rates.get(c)))

print('\n[*] Casos testigo seleccionados (%d):' % len(samples))
for lbl, p, rr, pr in samples:
    print('    - %-25s | [%d] %-35s | CUIT=%s | sup=%d | cus=%d | country=%s | state=%s | resp=%s | ZIP(ret=%s, per=%s)' % (
        lbl, p.id, (p.name or '')[:35], p.vat, p.supplier_rank, p.customer_rank,
        p.country_id.code if p.country_id else False,
        p.state_id.name if p.state_id else False,
        p.l10n_ar_afip_responsibility_type_id.name if has_field('res.partner', 'l10n_ar_afip_responsibility_type_id') and p.l10n_ar_afip_responsibility_type_id else False,
        rr, pr
    ))

# 3. Probar lectura directa de res.company.jurisdiction.padron._get_aliquot
if padron:
    tmp_dir_expected = padron._get_parp_tmp_dir()
    existed_before = os.path.exists(tmp_dir_expected)

    def test_padron_direct():
        print('  tmp_dir esperado: %s (existía antes: %s)' % (tmp_dir_expected, existed_before))
        for lbl, p, rr, pr in samples:
            res = safe(padron._get_aliquot, p)
            print('  [%s] partner=[%d] vat=%s -> _get_aliquot()=%r (esperado ZIP: ret=%s, per=%s)' % (
                lbl, p.id, p.vat, res, rr, pr
            ))
        if os.path.exists(tmp_dir_expected):
            print('\n  Árbol extraído en %s:' % tmp_dir_expected)
            for root, dirs, files in os.walk(tmp_dir_expected):
                for fn in files:
                    print('    %s' % os.path.join(root, fn))
        else:
            print('\n  [!] tmp_dir NO existe después de llamar a _get_aliquot.')
        print('  find_file(tmp_dir, "Per") = %r' % safe(padron.find_file, tmp_dir_expected, 'Per'))
        print('  find_file(tmp_dir, "Ret") = %r' % safe(padron.find_file, tmp_dir_expected, 'Ret'))

    run_isolated('A. Prueba directa de padron._get_aliquot() y estructura /tmp', test_padron_direct)

# 4. Probar auto-detección de Posición Fiscal (Pagos vs Ventas)
def test_fpos_detection():
    FP = env['account.fiscal.position'].with_company(company)
    for lbl, p, rr, pr in samples:
        fp_pay = FP.with_context(l10n_ar_withholding=True, active_test=True)._get_fiscal_position(p)
        fp_sale = FP.with_context(active_test=True)._get_fiscal_position(p)
        print('  [%s] [%d] %s:' % (lbl, p.id, (p.name or '')[:35]))
        print('      Pago (l10n_ar_withholding=True) -> %s' % (('[%d] %s' % (fp_pay.id, fp_pay.name)) if fp_pay else 'NINGUNA (False)'))
        print('      Venta/Factura (sin flag wth)    -> %s' % (('[%d] %s' % (fp_sale.id, fp_sale.name)) if fp_sale else 'NINGUNA (False)'))

run_isolated('B. Auto-detección de Posición Fiscal en Pagos vs Ventas', test_fpos_detection)

# 5. Simular pagos (Proveedor vs Cliente) y Factura de Venta
bank_journal = env['account.journal'].search([
    ('company_id', '=', company.id),
    ('type', 'in', ['bank', 'cash']),
], limit=1)
sale_journal = env['account.journal'].search([
    ('company_id', '=', company.id),
    ('type', '=', 'sale'),
], limit=1)
sale_product = env['product.product'].search([('sale_ok', '=', True)], limit=1)

for lbl, p, rr, pr in samples:
    def test_payment_and_invoice(partner=p, label=lbl):
        print('  Partner: [%d] %s (CUIT=%s)' % (partner.id, partner.name, partner.vat))
        if bank_journal:
            pml_out = bank_journal.outbound_payment_method_line_ids[:1]
            pay_sup = env['account.payment'].with_company(company).new({
                'company_id': company.id,
                'payment_type': 'outbound',
                'partner_type': 'supplier',
                'partner_id': partner.id,
                'journal_id': bank_journal.id,
                'payment_method_line_id': pml_out.id if pml_out else False,
                'date': test_date,
                'amount': 10000.0,
            })
            safe(pay_sup._compute_fiscal_position_id)
            safe(pay_sup._compute_l10n_ar_withholding_line_ids)
            fp_name = pay_sup.l10n_ar_fiscal_position_id.name if has_field('account.payment', 'l10n_ar_fiscal_position_id') and pay_sup.l10n_ar_fiscal_position_id else 'False'
            print('  -> Pago PROVEEDOR (outbound/supplier): FP=%s | Líneas retención=%d' % (
                fp_name, len(pay_sup.l10n_ar_withholding_line_ids) if has_field('account.payment', 'l10n_ar_withholding_line_ids') else -1
            ))
            if has_field('account.payment', 'l10n_ar_withholding_line_ids'):
                for wl in pay_sup.l10n_ar_withholding_line_ids:
                    print('       * tax=[%s] %s (%.2f%%) | base=%.2f | amount=%.2f | ref=%r' % (
                        wl.tax_id.id, wl.tax_id.name, wl.tax_id.amount, wl.base_amount, wl.amount, wl.ref
                    ))

            pml_in = bank_journal.inbound_payment_method_line_ids[:1]
            pay_cus = env['account.payment'].with_company(company).new({
                'company_id': company.id,
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': partner.id,
                'journal_id': bank_journal.id,
                'payment_method_line_id': pml_in.id if pml_in else False,
                'date': test_date,
                'amount': 10000.0,
            })
            safe(pay_cus._compute_fiscal_position_id)
            safe(pay_cus._compute_l10n_ar_withholding_line_ids)
            fp_cus = pay_cus.l10n_ar_fiscal_position_id.name if has_field('account.payment', 'l10n_ar_fiscal_position_id') and pay_cus.l10n_ar_fiscal_position_id else 'False'
            print('  -> Cobro CLIENTE (inbound/customer):   FP=%s | Líneas retención=%d' % (
                fp_cus, len(pay_cus.l10n_ar_withholding_line_ids) if has_field('account.payment', 'l10n_ar_withholding_line_ids') else -1
            ))

        if sale_journal and sale_product:
            inv = env['account.move'].with_company(company).new({
                'company_id': company.id,
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'journal_id': sale_journal.id,
                'invoice_date': test_date,
                'date': test_date,
                'invoice_line_ids': [(0, 0, {
                    'product_id': sale_product.id,
                    'quantity': 1.0,
                    'price_unit': 10000.0,
                })],
            })
            safe(inv._compute_fiscal_position_id)
            line = inv.invoice_line_ids[:1]
            computed_taxes = safe(line._get_computed_taxes) if line else None
            print('  -> Factura VENTA (out_invoice): FP=%s | _get_computed_taxes=%s' % (
                inv.fiscal_position_id.name if inv.fiscal_position_id else 'False',
                [(t.id, t.name, t.amount) for t in computed_taxes] if computed_taxes else []
            ))

        # Verificar qué habría quedado en l10n_ar.partner.tax dentro de este savepoint antes de revertir
        new_pt = env['l10n_ar.partner.tax'].search([('partner_id', '=', partner.id), ('company_id', '=', company.id)])
        if new_pt:
            print('  -> l10n_ar.partner.tax en savepoint (%d):' % len(new_pt))
            for pt in new_pt:
                print('       * [%s] %s (%s..%s) ref=%r' % (
                    pt.tax_id.id, pt.tax_id.name, pt.from_date, pt.to_date, pt.ref
                ))

    run_isolated('C. Simulación Pago Proveedor / Cobro Cliente / Factura Venta - %s' % lbl, test_payment_and_invoice)

# 6. Simulación controlada CON Posición Fiscal RI + webservice='padron' en SAVEPOINT
def test_with_temp_fp():
    ar_country = env.ref('base.ar', raise_if_not_found=False)
    ri_resp = env['l10n_ar.afip.responsibility.type'].search([('code', '=', '1')], limit=1)
    ba_tax_state = ba_state.id if ba_state else False
    wth_0 = env['account.tax'].with_company(company).with_context(active_test=False).search([
        ('company_id', '=', company.id),
        ('l10n_ar_withholding_payment_type', '=', 'supplier'),
        ('l10n_ar_state_id', '=', ba_tax_state),
        ('amount', '=', 0.0),
    ], limit=1)
    per_0 = env['account.tax'].with_company(company).with_context(active_test=False).search([
        ('company_id', '=', company.id),
        ('type_tax_use', '=', 'sale'),
        ('l10n_ar_state_id', '=', ba_tax_state),
        ('amount', '=', 0.0),
    ], limit=1)
    print('  Base wth_0=%s | per_0=%s (active=%s) | ri_resp=%s' % (
        wth_0.id if wth_0 else None,
        per_0.id if per_0 else None,
        per_0.active if per_0 else None,
        ri_resp.name if ri_resp else None,
    ))
    if not (ar_country and ri_resp and wth_0 and per_0):
        print('  [!] Faltan registros base para armar la FP temporal.')
        return
    if not per_0.active:
        per_0.active = True
    temp_fp = env['account.fiscal.position'].with_company(company).create({
        'name': 'TEST TEMP RI ARBA PADRON',
        'company_id': company.id,
        'auto_apply': True,
        'country_id': ar_country.id,
        'l10n_ar_afip_responsibility_type_ids': [(6, 0, [ri_resp.id])],
        'l10n_ar_tax_ids': [
            (0, 0, {'tax_type': 'withholding', 'default_tax_id': wth_0.id, 'webservice': 'padron'}),
            (0, 0, {'tax_type': 'perception', 'default_tax_id': per_0.id, 'webservice': 'padron'}),
        ],
    })
    print('  FP temporal creada en savepoint: id=%d' % temp_fp.id)
    if samples:
        lbl, p, rr, pr = samples[0]
        if not p.l10n_ar_afip_responsibility_type_id:
            p.l10n_ar_afip_responsibility_type_id = ri_resp
        FP = env['account.fiscal.position'].with_company(company)
        fp_pay = FP.with_context(l10n_ar_withholding=True, active_test=True)._get_fiscal_position(p)
        fp_sale = FP.with_context(active_test=True)._get_fiscal_position(p)
        print('  Sample=%s (%s) -> _get_fiscal_position(pay)=%s | (sale)=%s' % (
            lbl, p.name, fp_pay.name if fp_pay else False, fp_sale.name if fp_sale else False
        ))
        if bank_journal:
            pml_out = bank_journal.outbound_payment_method_line_ids[:1]
            pay_sup = env['account.payment'].with_company(company).new({
                'company_id': company.id,
                'payment_type': 'outbound',
                'partner_type': 'supplier',
                'partner_id': p.id,
                'journal_id': bank_journal.id,
                'payment_method_line_id': pml_out.id if pml_out else False,
                'date': test_date,
                'amount': 10000.0,
            })
            safe(pay_sup._compute_fiscal_position_id)
            safe(pay_sup._compute_l10n_ar_withholding_line_ids)
            print('  Con FP temporal -> Pago PROV wth_lines=%s' % [
                (wl.tax_id.name, wl.tax_id.amount, wl.amount) for wl in pay_sup.l10n_ar_withholding_line_ids
            ])
        if sale_journal and sale_product:
            inv = env['account.move'].with_company(company).new({
                'company_id': company.id,
                'move_type': 'out_invoice',
                'partner_id': p.id,
                'journal_id': sale_journal.id,
                'invoice_date': test_date,
                'date': test_date,
                'invoice_line_ids': [(0, 0, {
                    'product_id': sale_product.id,
                    'quantity': 1.0,
                    'price_unit': 10000.0,
                })],
            })
            safe(inv._compute_fiscal_position_id)
            computed = safe(inv.invoice_line_ids[:1]._get_computed_taxes)
            print('  Con FP temporal -> Factura VENTA computed_taxes=%s' % (
                [(t.id, t.name, t.amount) for t in computed] if computed else []
            ))

run_isolated('D. Simulación en SAVEPOINT CON Fiscal Position RI + webservice="padron"', test_with_temp_fp)

if padron and not existed_before and os.path.exists(tmp_dir_expected):
    shutil.rmtree(tmp_dir_expected, ignore_errors=True)
    print('\n[*] Limpieza de %s completada.' % tmp_dir_expected)

env.cr.rollback()
print('\n[OK] Simulación finalizada con env.cr.rollback() completo. Base de datos intacta.')
