#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Crea posiciones fiscales de retenciones IIBB y Ganancias en Odoo Argentina."""

import re

if 'env' not in globals():
    raise RuntimeError(
        "Ejecuta este archivo dentro de 'odoo-bin shell', donde 'env' está definido."
    )

# Ejecutar primero con DRY_RUN=True. La simulación escribe dentro de la
# transacción actual y la revierte al terminar; no asigna posiciones a contactos.
DRY_RUN = False
COMPANY_ID = None

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


def iibb_code(tax):
    match = re.fullmatch(
        r'\s*iibb\s+wth\s+([a-z]+)(?:\s+0%)?\s*',
        tax.name,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    code = match.group(1).upper()
    return code if code in PROVINCES else None


def field_selection_values(field, recordset):
    selection = field.selection
    if callable(selection):
        selection = selection(recordset)
    if isinstance(selection, (list, tuple)):
        return {value for value, _label in selection}
    return set()


def require_schema(company):
    required_position_fields = {
        'name',
        'company_id',
        'country_id',
        'auto_apply',
        'l10n_ar_tax_type',
        'l10n_ar_tax_ids',
    }
    position_model = env['account.fiscal.position']
    missing = required_position_fields - set(position_model._fields)
    if missing:
        raise RuntimeError(
            'Faltan campos requeridos en account.fiscal.position: '
            + ', '.join(sorted(missing))
        )

    line_model_name = 'account.fiscal.position.l10n_ar_tax'
    if line_model_name not in env.registry.models:
        raise RuntimeError(f'No está disponible el modelo {line_model_name}.')
    line_model = env[line_model_name]
    required_line_fields = {
        'fiscal_position_id',
        'tax_type',
        'default_tax_id',
        'tax_group_id',
        'aliquot',
    }
    missing = required_line_fields - set(line_model._fields)
    if missing:
        raise RuntimeError(
            f'Faltan campos requeridos en {line_model_name}: '
            + ', '.join(sorted(missing))
        )

    position_types = field_selection_values(
        position_model._fields['l10n_ar_tax_type'], position_model
    )
    if position_types and 'withholding' not in position_types:
        raise RuntimeError(
            "El campo account.fiscal.position.l10n_ar_tax_type no admite "
            "'withholding' en esta base."
        )
    line_types = field_selection_values(line_model._fields['tax_type'], line_model)
    if line_types and 'withholding' not in line_types:
        raise RuntimeError(
            f"El campo {line_model_name}.tax_type no admite 'withholding'."
        )

    if not company.country_id:
        raise RuntimeError(
            f"La compañía [{company.id}] no tiene país configurado; "
            'no se puede asignar con seguridad el país de la posición.'
        )
    if company.country_id.code != 'AR':
        raise RuntimeError(
            f"La compañía [{company.id}] está configurada con país "
            f"{company.country_id.display_name}, no Argentina."
        )
    return position_model, line_model


def get_candidates(company):
    taxes = env['account.tax'].with_context(active_test=False).search([
        ('company_id', 'in', [False, company.id]),
    ], order='name, id')
    active_taxes = taxes.filtered('active')

    iibb_by_code = {}
    for tax in active_taxes:
        code = iibb_code(tax)
        if (
            code
            and tax.type_tax_use == 'none'
            and tax.amount > 0
            and tax.tax_group_id
        ):
            iibb_by_code.setdefault(code, []).append(tax)

    duplicates = {
        code: matches for code, matches in iibb_by_code.items() if len(matches) != 1
    }
    if duplicates:
        details = '; '.join(
            f"{PROVINCES[code]}: "
            + ', '.join(f'[{tax.id}] {tax.name}' for tax in matches)
            for code, matches in sorted(duplicates.items())
        )
        raise RuntimeError(
            'Hay más de un impuesto IIBB activo elegible por jurisdicción; '
            f'no se aplicó ningún cambio. Revisar: {details}'
        )

    if 'l10n_ar_tax_type' not in env['account.tax']._fields:
        raise RuntimeError('No existe account.tax.l10n_ar_tax_type.')
    earnings = active_taxes.filtered(
        lambda tax: (
            tax.type_tax_use == 'none'
            and tax.tax_group_id
            and tax.l10n_ar_tax_type in ('earnings', 'earnings_scale')
        )
    )

    if not iibb_by_code and not earnings:
        raise RuntimeError(
            'No se encontraron impuestos activos de retención IIBB ni de Ganancias '
            'con los criterios del plan.'
        )
    return iibb_by_code, earnings, len(taxes), len(active_taxes)


def plan_entries(iibb_by_code, earnings):
    entries = []
    for code in sorted(iibb_by_code, key=lambda value: PROVINCES[value]):
        tax = iibb_by_code[code][0]
        entries.append((
            f'Retención IIBB {PROVINCES[code]}',
            tax,
        ))
    for tax in earnings:
        entries.append((
            f'Retención Ganancias - {tax.name}',
            tax,
        ))
    return entries


def locate_position(position_model, company, name):
    matches = position_model.with_context(active_test=False).search([
        ('company_id', 'in', [False, company.id]),
        ('name', '=', name),
    ], order='id')
    if len(matches) > 1:
        raise RuntimeError(
            f"Hay {len(matches)} posiciones llamadas '{name}' para la compañía "
            f"[{company.id}]; resolver la duplicación antes de continuar."
        )
    if matches and not matches.active:
        raise RuntimeError(
            f"La posición [{matches.id}] '{name}' está archivada; "
            'reactivarla/revisarla manualmente antes de continuar.'
        )
    if matches and not matches.company_id:
        raise RuntimeError(
            f"La posición [{matches.id}] '{name}' es compartida. "
            'No se modificarán posiciones globales automáticamente.'
        )
    return matches


def configure_entry(position_model, line_model, company, name, tax):
    position = locate_position(position_model, company, name)
    created = not bool(position)
    if created:
        position = position_model.create({
            'name': name,
            'company_id': company.id,
            'country_id': company.country_id.id,
            'l10n_ar_tax_type': 'withholding',
            'auto_apply': False,
        })
        print(f'  [+ POSICIÓN] {name}')
    else:
        print(f'  [EXISTENTE] [{position.id}] {name}')
        if position.l10n_ar_tax_type not in ('none', 'withholding'):
            raise RuntimeError(
                f"La posición [{position.id}] '{name}' tiene "
                f"l10n_ar_tax_type={position.l10n_ar_tax_type!r}; "
                'no se sobrescribirá.'
            )
        unrelated_lines = position.l10n_ar_tax_ids.filtered(
            lambda line: line.default_tax_id != tax
        )
        if unrelated_lines:
            raise RuntimeError(
                f"La posición [{position.id}] '{name}' tiene otras reglas L10N "
                'asociadas; no se sobrescribirá.'
            )
        if position.l10n_ar_tax_type != 'withholding' or position.auto_apply:
            position.write({
                'l10n_ar_tax_type': 'withholding',
                'auto_apply': False,
            })

    matching_lines = position.l10n_ar_tax_ids.filtered(
        lambda line: line.default_tax_id == tax
    )
    if len(matching_lines) > 1:
        raise RuntimeError(
            f"La posición [{position.id}] '{name}' ya tiene "
            f"{len(matching_lines)} reglas para el impuesto [{tax.id}]."
        )

    values = {
        'fiscal_position_id': position.id,
        'tax_type': 'withholding',
        'default_tax_id': tax.id,
        'tax_group_id': tax.tax_group_id.id,
        'aliquot': tax.amount,
    }
    if matching_lines:
        line = matching_lines[0]
        current_values = (
            line.tax_type,
            line.default_tax_id.id,
            line.tax_group_id.id if line.tax_group_id else False,
            line.aliquot,
        )
        desired_values = (
            values['tax_type'],
            tax.id,
            tax.tax_group_id.id,
            tax.amount,
        )
        if current_values != desired_values:
            line.write(values)
            print(
                f'    [ACTUALIZADA] Regla [{line.id}] con alícuota '
                f'{tax.amount:g}%'
            )
        else:
            print(f'    [REGLA OK] [{line.id}] alícuota {tax.amount:g}%')
    else:
        line_model.create(values)
        print(
            f'    [+ REGLA] {tax.l10n_ar_tax_type if "l10n_ar_tax_type" in tax._fields else "IIBB"} '
            f'| impuesto [{tax.id}] {tax.name} | alícuota {tax.amount:g}%'
        )

    return created


def execute():
    company = env['res.company'].browse(COMPANY_ID) if COMPANY_ID else env.company
    if not company.exists():
        raise ValueError(f'No existe la compañía configurada: {COMPANY_ID}')

    try:
        position_model, line_model = require_schema(company)
        iibb_by_code, earnings, total_taxes, active_taxes = get_candidates(company)
        entries = plan_entries(iibb_by_code, earnings)

        print('=' * 100)
        print(
            f"CONFIGURACIÓN DE RETENCIONES | [{company.id}] {company.name} | "
            f"{'DRY-RUN' if DRY_RUN else 'APLICANDO CAMBIOS'}"
        )
        print(
            f'Impuestos revisados: {total_taxes} total, {active_taxes} activos. '
            'No se crearán/modificarán impuestos ni se tocarán contactos.'
        )
        print(
            f'Candidatos confirmados: {len(iibb_by_code)} posiciones IIBB y '
            f'{len(earnings)} posiciones de Ganancias.'
        )
        print('=' * 100)

        created_count = 0
        for name, tax in entries:
            print(
                f'\n{ name } <- impuesto [{tax.id}] {tax.name} | '
                f'tipo={tax.l10n_ar_tax_type or "IIBB"} | '
                f'alícuota={tax.amount:g}%'
            )
            if configure_entry(position_model, line_model, company, name, tax):
                created_count += 1

        if DRY_RUN:
            env.cr.rollback()
            print(
                f'\n[DRY-RUN] Simulación revertida: {len(entries)} posición(es) '
                f'revisada(s), {created_count} simulada(s) como nueva(s). '
                'No quedó ningún cambio guardado.'
            )
            print('Para persistir, revisa el resultado y cambia DRY_RUN = False.')
        else:
            env.cr.commit()
            print(
                f'\n[OK] Transacción confirmada: {len(entries)} posición(es) '
                f'procesada(s), {created_count} creada(s).'
            )
    except Exception:
        env.cr.rollback()
        raise


if __name__ == '__main__' or 'env' in globals():
    execute()
