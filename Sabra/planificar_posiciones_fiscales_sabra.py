#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plan de posiciones fiscales desde los impuestos existentes; no escribe en Odoo."""

import re

if 'env' not in globals():
    raise RuntimeError(
        "Ejecuta este archivo dentro de 'odoo-bin shell', donde 'env' está definido."
    )

COMPANY_ID = None  # None usa la compañía activa; también se puede indicar un ID.

PROVINCES = {
    'CABA': 'CABA',
    'PBA': 'Buenos Aires (ARBA)',
    'C': 'Catamarca',
    'CBA': 'Córdoba',
    'CTS': 'Corrientes',
    'ER': 'Entre Ríos',
    'J': 'Jujuy',
    'MZA': 'Mendoza',
    'LR': 'La Rioja',
    'S': 'Salta',
    'SJ': 'San Juan',
    'SL': 'San Luis',
    'SF': 'Santa Fe',
    'SE': 'Santiago del Estero',
    'T': 'Tucumán',
    'CHO': 'Chaco',
    'CHT': 'Chubut',
    'F': 'Formosa',
    'MS': 'Misiones',
    'N': 'Neuquén',
    'LP': 'La Pampa',
    'RN': 'Río Negro',
    'SC': 'Santa Cruz',
    'TAIS': 'Tierra del Fuego',
}


def normalize(value):
    return ' '.join((value or '').casefold().split())


def tax_text(tax):
    group = tax.tax_group_id.name if tax.tax_group_id else ''
    return normalize(f'{tax.name} {tax.description or ""} {group}')


def iibb_code(tax):
    match = re.search(r'\biibb\s+wth\s+([a-z]+)\b', normalize(tax.name))
    if not match:
        return None
    code = match.group(1).upper()
    return code if code in PROVINCES else None


def tax_kind(tax):
    text = tax_text(tax)
    if (
        'iibb' in text
        and ('wth' in text or 'withhold' in text or 'retenc' in text)
        and tax.type_tax_use == 'none'
        and tax.amount > 0
    ):
        code = iibb_code(tax)
        if code:
            return 'iibb_withholding', code
        return 'unclassified_iibb_withholding', None

    if (
        getattr(tax, 'l10n_ar_tax_type', False) in ('earnings', 'earnings_scale')
        and tax.type_tax_use == 'none'
    ):
        return 'earnings_withholding', None

    return None, None


def proposed_position_name(tax, kind, code):
    if kind == 'iibb_withholding':
        return f'Retención IIBB {PROVINCES[code]}'
    if kind == 'earnings_withholding':
        return f'Retención Ganancias - {tax.name}'
    return None


def matching_positions(company, name):
    return env['account.fiscal.position'].with_context(active_test=False).search([
        ('company_id', 'in', [False, company.id]),
        ('name', '=', name),
    ], order='id')


def run_plan():
    company = env['res.company'].browse(COMPANY_ID) if COMPANY_ID else env.company
    if not company.exists():
        raise ValueError(f'No existe la compañía configurada: {COMPANY_ID}')

    if 'l10n_ar_tax_type' not in env['account.tax']._fields:
        raise RuntimeError(
            "No existe account.tax.l10n_ar_tax_type. No es posible clasificar "
            "Ganancias por régimen con esta base."
        )

    taxes = env['account.tax'].with_context(active_test=False).search([
        ('company_id', 'in', [False, company.id]),
    ], order='name, id')
    active_taxes = taxes.filtered('active')

    iibb_by_code = {}
    earnings_taxes = []
    unclassified_iibb = []
    skipped_zero_iibb = []

    for tax in active_taxes:
        kind, code = tax_kind(tax)
        if kind == 'iibb_withholding':
            iibb_by_code.setdefault(code, []).append(tax)
        elif kind == 'earnings_withholding':
            earnings_taxes.append(tax)
        elif kind == 'unclassified_iibb_withholding':
            unclassified_iibb.append(tax)
        elif (
            'iibb' in tax_text(tax)
            and ('wth' in tax_text(tax) or 'withhold' in tax_text(tax))
            and tax.type_tax_use == 'none'
            and tax.amount <= 0
        ):
            skipped_zero_iibb.append(tax)

    print('=' * 100)
    print(f'PLAN DE POSICIONES FISCALES | [{company.id}] {company.name}')
    print('SOLO LECTURA: no crea, modifica ni elimina registros; no cambia contactos.')
    print('=' * 100)
    print(
        f'Impuestos revisados: {len(taxes)} total, {len(active_taxes)} activos '
        f'(incluye impuestos compartidos).'
    )

    print(f'\n1. RETENCIONES IIBB: {len(iibb_by_code)} jurisdicciones identificadas')
    planned_iibb = 0
    for code in sorted(iibb_by_code, key=lambda item: PROVINCES[item]):
        candidates = iibb_by_code[code]
        name = f'Retención IIBB {PROVINCES[code]}'
        positions = matching_positions(company, name)
        if len(candidates) != 1:
            print(
                f'  [REVISAR: {len(candidates)} IMPUESTOS] {name}: '
                + '; '.join(
                    f'[{tax.id}] {tax.name} ({tax.amount:g}%)'
                    for tax in candidates
                )
            )
            continue

        tax = candidates[0]
        if len(positions) > 1:
            print(
                f'  [REVISAR: {len(positions)} POSICIONES] {name} | '
                f'impuesto=[{tax.id}] {tax.name}'
            )
            continue

        state = (
            f'existe [{positions.id}]'
            if positions
            else 'sería nueva'
        )
        print(
            f'  [{tax.id}] {tax.name} ({tax.amount:g}%, grupo='
            f'{tax.tax_group_id.name if tax.tax_group_id else "-"}) -> '
            f'{name} ({state})'
        )
        planned_iibb += 1

    print(
        f'  Impuestos IIBB WTH activos con alícuota cero/negativa omitidos: '
        f'{len(skipped_zero_iibb)}'
    )
    for tax in skipped_zero_iibb:
        print(f'    [{tax.id}] {tax.name} ({tax.amount:g}%)')
    if unclassified_iibb:
        print(f'  Impuestos IIBB WTH sin código provincial reconocido: {len(unclassified_iibb)}')
        for tax in unclassified_iibb:
            print(f'    [{tax.id}] {tax.name} | grupo={tax.tax_group_id.name if tax.tax_group_id else "-"}')

    print(
        f'\n2. RETENCIONES DE GANANCIAS: {len(earnings_taxes)} impuestos '
        '(por tax l10n_ar_tax_type earnings / earnings_scale)'
    )
    planned_earnings = 0
    for tax in earnings_taxes:
        name = proposed_position_name(tax, 'earnings_withholding', None)
        positions = matching_positions(company, name)
        state = f'existe [{positions.id}]' if len(positions) == 1 else 'sería nueva'
        if len(positions) > 1:
            state = f'revisar: {len(positions)} posiciones coincidentes'
        print(
            f'  [{tax.id}] {tax.name} | tipo={tax.l10n_ar_tax_type} | '
            f'alícuota={tax.amount:g}% | grupo='
            f'{tax.tax_group_id.name if tax.tax_group_id else "-"} -> {name} ({state})'
        )
        planned_earnings += 1

    existing_positions = env['account.fiscal.position'].with_context(
        active_test=False
    ).search([
        ('company_id', 'in', [False, company.id]),
    ])
    contacts = env['res.partner'].search([
        ('active', '=', True),
        ('parent_id', '=', False),
        '|',
        ('company_id', '=', False),
        ('company_id', '=', company.id),
    ])
    print('\n3. POSICIONES Y CONTACTOS (SIN CAMBIOS)')
    print(f'  Posiciones fiscales existentes: {len(existing_positions)}')
    print(f'  Contactos comerciales revisados: {len(contacts)}')
    print('  Asignación de retenciones/IIBB a contactos: no incluida en este plan.')

    print('\nRESUMEN DEL PLAN')
    print(f'  Posiciones IIBB con una única tasa candidata: {planned_iibb}')
    print(f'  Posiciones de Ganancias propuestas por impuesto/régimen: {planned_earnings}')
    print('  Escrituras en Odoo: 0')


if __name__ == '__main__' or 'env' in globals():
    run_plan()
