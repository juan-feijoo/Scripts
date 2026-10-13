#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inspección detallada, estrictamente de solo lectura, del esquema fiscal de Odoo."""

if 'env' not in globals():
    raise RuntimeError(
        "Ejecuta este archivo dentro de 'odoo-bin shell', donde 'env' está definido."
    )

COMPANY_ID = None  # None usa la compañía activa; también se puede indicar un ID.

KEYWORDS = (
    'iibb',
    'ingresos brutos',
    'wth',
    'withhold',
    'ganancias',
    'profit',
    'percep',
    'perc',
)


def has_model(model_name):
    return model_name in env.registry.models


def has_field(model_name, field_name):
    return has_model(model_name) and field_name in env[model_name]._fields


def display(record):
    if not record:
        return '-'
    return f'[{record.id}] {record.display_name}'


def field_description(model_name, field_name):
    field = env[model_name]._fields[field_name]
    description = f'{field_name} ({field.type})'
    if getattr(field, 'comodel_name', None):
        description += f' -> {field.comodel_name}'
    selection = getattr(field, 'selection', None)
    if isinstance(selection, (list, tuple)):
        options = ', '.join(f'{key}={label}' for key, label in selection)
        if options:
            description += f' [{options}]'
    return description


def relevant_fields(model_name):
    if not has_model(model_name):
        print(f'  Modelo {model_name}: NO DISPONIBLE')
        return
    keywords = ('l10n_ar', 'afip', 'fiscal', 'tax', 'position', 'auto_apply')
    names = sorted(
        name for name in env[model_name]._fields
        if any(keyword in name.casefold() for keyword in keywords)
    )
    print(f'  Modelo {model_name}:')
    for name in names:
        print(f'    - {field_description(model_name, name)}')


def relation_names(record, field_name):
    if field_name not in record._fields:
        return 'campo no disponible'
    values = record[field_name]
    field_type = record._fields[field_name].type
    if field_type in ('many2one', 'many2many', 'one2many'):
        return ', '.join(values.mapped('display_name')) if values else '-'
    return str(values) if values not in (False, None, '') else '-'


def tax_keywords(tax):
    group = tax.tax_group_id.name if tax.tax_group_id else ''
    description = tax.description or ''
    return f'{tax.name} {description} {group}'.casefold()


def print_tax_details(tax):
    company = display(tax.company_id) if tax.company_id else 'Compartido'
    group = display(tax.tax_group_id)
    print(
        f'  [{tax.id}] {tax.name} | {"activo" if tax.active else "archivado"} | '
        f'compañía={company} | uso={tax.type_tax_use} | '
        f'tipo={tax.amount_type} | alícuota={tax.amount:g}% | grupo={group}'
    )

    for field_name in (
        'l10n_ar_tax_type',
        'country_id',
        'include_base_amount',
        'is_base_affected',
        'children_tax_ids',
        'original_tax_ids',
        'replacing_tax_ids',
    ):
        if field_name not in tax._fields:
            continue
        value = tax[field_name]
        if getattr(value, '_name', None):
            value = ', '.join(value.mapped('display_name')) if value else '-'
        print(f'      {field_name}={value}')

    for repartition_field in ('invoice_repartition_line_ids', 'refund_repartition_line_ids'):
        if repartition_field not in tax._fields:
            continue
        lines = tax[repartition_field]
        details = []
        for line in lines:
            repartition_type = getattr(line, 'repartition_type', '-')
            factor = getattr(line, 'factor_percent', '-')
            account = display(line.account_id) if 'account_id' in line._fields else '-'
            tags = (
                ', '.join(line.tag_ids.mapped('display_name'))
                if 'tag_ids' in line._fields and line.tag_ids
                else '-'
            )
            details.append(
                f'{repartition_type} {factor}% cuenta={account} etiquetas={tags}'
            )
        print(f'      {repartition_field}: {"; ".join(details) if details else "-"}')


def run_diagnostic():
    company = env['res.company'].browse(COMPANY_ID) if COMPANY_ID else env.company
    if not company.exists():
        raise ValueError(f'No existe la compañía configurada: {COMPANY_ID}')

    print('=' * 100)
    print(f'DIAGNÓSTICO FISCAL DE SOLO LECTURA | [{company.id}] {company.name}')
    print('=' * 100)

    print('\n1. VERSIONES Y MÓDULOS DE LOCALIZACIÓN INSTALADOS')
    modules = env['ir.module.module'].sudo().search([
        ('state', '=', 'installed'),
        '|',
        ('name', '=', 'account'),
        ('name', 'ilike', 'l10n_ar'),
    ], order='name')
    for module in modules:
        print(
            f'  {module.name}: versión={module.latest_version or "-"} | '
            f'estado={module.state}'
        )

    print('\n2. CAMPOS DISPONIBLES EN LOS MODELOS FISCALES')
    for model_name in (
        'account.tax',
        'account.tax.group',
        'account.fiscal.position',
        'account.fiscal.position.l10n_ar_tax',
        'res.partner',
        'l10n_ar.afip.responsibility.type',
    ):
        relevant_fields(model_name)

    tax_model = env['account.tax'].with_context(active_test=False)
    taxes = tax_model.search([
        ('company_id', 'in', [False, company.id]),
    ], order='name, id')
    matched_taxes = taxes.filtered(
        lambda tax: any(keyword in tax_keywords(tax) for keyword in KEYWORDS)
    )
    print(
        f'\n3. IMPUESTOS RELACIONADOS POR NOMBRE/GRUPO: {len(matched_taxes)} '
        f'(de {len(taxes)} impuestos de la compañía y compartidos)'
    )
    print('   Cada registro incluye uso, estado, grupo, cuentas y etiquetas contables disponibles.')
    for tax in matched_taxes:
        print_tax_details(tax)

    fiscal_position_model = env['account.fiscal.position'].with_context(active_test=False)
    positions = fiscal_position_model.search([
        ('company_id', 'in', [False, company.id]),
    ], order='name, id')
    print(f'\n4. POSICIONES FISCALES Y VÍNCULOS: {len(positions)}')
    for position in positions:
        print(
            f'  [{position.id}] {position.name} | '
            f'{"activa" if position.active else "archivada"} | '
            f'compañía={display(position.company_id) if position.company_id else "Compartida"}'
        )
        for field_name in (
            'l10n_ar_tax_type',
            'auto_apply',
            'country_id',
            'tax_ids',
            'l10n_ar_afip_responsibility_type_ids',
            'l10n_ar_tax_ids',
        ):
            if field_name in position._fields:
                print(f'      {field_name}={relation_names(position, field_name)}')

        if 'l10n_ar_tax_ids' in position._fields:
            for line in position.l10n_ar_tax_ids:
                print(
                    f'        Regla [{line.id}] | '
                    f'tipo={getattr(line, "tax_type", "-")} | '
                    f'impuesto={display(line.default_tax_id) if "default_tax_id" in line._fields else "-"} | '
                    f'grupo={display(line.tax_group_id) if "tax_group_id" in line._fields else "-"} | '
                    f'alícuota={getattr(line, "aliquot", "-")}'
                )

    print('\n5. RESPONSABILIDADES AFIP Y CONTACTOS COMERCIALES')
    if has_model('l10n_ar.afip.responsibility.type'):
        responsibilities = env['l10n_ar.afip.responsibility.type'].search([], order='code, id')
        for responsibility in responsibilities:
            print(
                f'  AFIP [{responsibility.id}] código={getattr(responsibility, "code", "-")} '
                f'nombre={responsibility.display_name}'
            )
    else:
        print('  Modelo de responsabilidades AFIP no disponible.')

    partners = env['res.partner'].search([
        ('active', '=', True),
        ('parent_id', '=', False),
        '|',
        ('company_id', '=', False),
        ('company_id', '=', company.id),
    ], order='id')
    for partner in partners:
        responsibility = (
            partner.l10n_ar_afip_responsibility_type_id
            if 'l10n_ar_afip_responsibility_type_id' in partner._fields
            else False
        )
        print(
            f'  Contacto [{partner.id}] {partner.name} | '
            f'AFIP={getattr(responsibility, "code", "-") if responsibility else "-"} '
            f'{responsibility.display_name if responsibility else ""} | '
            f'posición={display(partner.property_account_position_id)}'
        )

    print('\nDiagnóstico finalizado. No se ejecutaron create, write, unlink, commit ni rollback.')


if __name__ == '__main__' or 'env' in globals():
    run_diagnostic()
