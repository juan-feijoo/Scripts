# -*- coding: utf-8 -*-
# 03 - Inspección de res.company.jurisdiction.padron, l10n_ar.partner.tax y datos fiscales de res.partner
import base64
import io
import re
import zipfile
from collections import Counter

company = get_company()
h('03 - PADRONES CARGADOS, PARTNER TAXES Y PREPARACIÓN DE CONTACTOS (%s)' % company.name)

# 1. Registros en res.company.jurisdiction.padron
sub('Registros en res.company.jurisdiction.padron')
if 'res.company.jurisdiction.padron' in env:
    padrons = env['res.company.jurisdiction.padron'].search([], order='id')
    print('  Total padrones en BD: %d' % len(padrons))
    for p in padrons:
        jcode = getattr(p.state_id, 'jurisdiction_code', '?') if p.state_id else None
        raw = base64.b64decode(p.file_padron) if p.file_padron else b''
        print('\n  Padron ID=%d | cia=[%s] %s | state=[%s] %s (jcode=%s)' % (
            p.id, p.company_id.id, p.company_id.name,
            p.state_id.id if p.state_id else 0, p.state_id.name if p.state_id else False, jcode
        ))
        print('    filename=%r | desde=%s | hasta=%s | bytes=%s' % (
            p.filename, p.l10n_ar_padron_from_date, p.l10n_ar_padron_to_date, f'{len(raw):,}'
        ))
        if raw:
            buf = io.BytesIO(raw)
            if zipfile.is_zipfile(buf):
                buf.seek(0)
                with zipfile.ZipFile(buf, 'r') as zf:
                    print('    Contenido ZIP (%d entradas):' % len(zf.infolist()))
                    for info in zf.infolist():
                        print('      - %-45s | dir=%-5s | size=%s bytes' % (
                            info.filename, info.is_dir(), f'{info.file_size:,}'
                        ))
                        if not info.is_dir() and info.file_size > 0:
                            with zf.open(info.filename) as f:
                                for idx in range(3):
                                    line = f.readline().decode('latin1', errors='replace').rstrip('\r\n')
                                    if not line:
                                        break
                                    print('          muestra[%d]: %s' % (idx + 1, line[:140]))
            else:
                print('    Archivo NO es ZIP. Primeras 3 líneas:')
                text_head = raw[:1024].decode('latin1', errors='replace').splitlines()[:3]
                for idx, line in enumerate(text_head, 1):
                    print('      muestra[%d]: %s' % (idx, line[:140]))
else:
    print('  [!] El modelo res.company.jurisdiction.padron NO está disponible.')

# 2. Registros existentes en l10n_ar.partner.tax
sub('Registros existentes en l10n_ar.partner.tax')
if 'l10n_ar.partner.tax' in env:
    all_pt = env['l10n_ar.partner.tax'].search([('company_id', '=', company.id)])
    print('  Total en compañía [%s]: %d' % (company.id, len(all_pt)))
    all_pt_global = env['l10n_ar.partner.tax'].search([])
    if len(all_pt_global) != len(all_pt):
        print('  Total en TODAS las compañías: %d' % len(all_pt_global))

    by_tax = Counter()
    by_period = Counter()
    for pt in all_pt:
        t = pt.tax_id
        tkey = '[%d] %s (use=%s, wth=%s)' % (
            t.id, t.name, t.type_tax_use, getattr(t, 'l10n_ar_withholding_payment_type', False)
        ) if t else 'Sin impuesto'
        by_tax[tkey] += 1
        by_period[(str(pt.from_date), str(pt.to_date))] += 1

    print('  Desglose por impuesto:')
    for tkey, cnt in by_tax.most_common(25):
        print('    %-70s : %d' % (tkey, cnt))
    print('  Desglose por vigencia (from_date, to_date):')
    for per, cnt in by_period.most_common(15):
        print('    %s : %d' % (per, cnt))
    print('  Muestra de hasta 10 registros:')
    for pt in all_pt[:10]:
        print('    - [%d] partner=[%d] %s (CUIT=%s) | tax=%s | %s..%s | ref=%r' % (
            pt.id, pt.partner_id.id, (pt.partner_id.name or '')[:30], pt.partner_id.vat,
            pt.tax_id.name if pt.tax_id else False, pt.from_date, pt.to_date, pt.ref
        ))
else:
    print('  [!] Modelo l10n_ar.partner.tax NO disponible.')

# 3. Auditoría de contactos comerciales (res.partner)
sub('Preparación de contactos comerciales (res.partner)')
partners = env['res.partner'].search([('is_company', '=', True)])
print('  Total empresas (is_company=True): %d' % len(partners))

# También verificar contactos individuales con parent_id=False que puedan operar como cliente/proveedor
indiv = env['res.partner'].search([('is_company', '=', False), ('parent_id', '=', False), '|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0)])
print('  Contactos individuales top-level con rank > 0: %d' % len(indiv))

stats = Counter()
combos_sup = Counter()
combos_cus = Counter()
manual_fp_count = 0

for p in partners:
    cuit_digits = re.sub(r'\D', '', p.vat or '')
    has_cuit = len(cuit_digits) == 11
    is_cus = p.customer_rank > 0
    is_sup = p.supplier_rank > 0
    if has_cuit:
        stats['con_cuit_11_dig'] += 1
    else:
        stats['sin_cuit_11_dig'] += 1
    if is_cus:
        stats['customer_rank>0'] += 1
    if is_sup:
        stats['supplier_rank>0'] += 1
    if is_cus and is_sup:
        stats['ambos_cus_y_sup'] += 1
    if p.with_company(company).property_account_position_id:
        manual_fp_count += 1

    key = (
        p.country_id.code if p.country_id else 'SIN_PAIS',
        p.state_id.name if p.state_id else 'SIN_PROV',
        p.l10n_ar_afip_responsibility_type_id.name if has_field('res.partner', 'l10n_ar_afip_responsibility_type_id') and p.l10n_ar_afip_responsibility_type_id else 'SIN_RESP_AFIP',
        'CUIT_OK' if has_cuit else 'SIN_CUIT',
    )
    if is_sup:
        combos_sup[key] += 1
    if is_cus:
        combos_cus[key] += 1

for k, v in sorted(stats.items()):
    print('    %-25s : %d' % (k, v))
print('    %-25s : %d' % ('con_pos_fiscal_manual', manual_fp_count))

print('\n  Top 15 perfiles fiscales de PROVEEDORES (supplier_rank > 0):')
for k, v in combos_sup.most_common(15):
    print('    %4d | %s' % (v, ' | '.join(k)))

print('\n  Top 15 perfiles fiscales de CLIENTES (customer_rank > 0):')
for k, v in combos_cus.most_common(15):
    print('    %4d | %s' % (v, ' | '.join(k)))
