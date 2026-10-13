#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audita impuestos, posiciones fiscales y asignaciones de contactos en Odoo."""

if 'env' not in globals():
    raise RuntimeError(
        "Ejecuta este archivo dentro de 'odoo-bin shell', donde 'env' está definido."
    )

COMPANY_ID = None  # None usa la compañía activa; también se puede indicar un ID.


def field_exists(model_name, field_name):
    return model_name in env.registry.models and field_name in env[model_name]._fields


def tax_keywords(tax):
    group = tax.tax_group_id.name if tax.tax_group_id else ''
    return f"{tax.name} {tax.description or ''} {group}".casefold()


def run_audit():
    company = env['res.company'].browse(COMPANY_ID) if COMPANY_ID else env.company
    if not company.exists():
        raise ValueError(f"No existe la compañía configurada: {COMPANY_ID}")

    print("=" * 100)
    print(f"AUDITORÍA FISCAL | Compañía [{company.id}] {company.name}")
    print("Modo: solo lectura; este script no crea ni modifica registros.")
    print("=" * 100)

    Tax = env['account.tax'].with_context(active_test=False)
    taxes = Tax.search([
        ('company_id', 'in', [False, company.id]),
    ], order='type_tax_use, name, id')

    print(f"\nIMPUESTOS: {len(taxes)} (incluye archivados y compartidos)")
    print("-" * 100)
    print(f"{'ID':>7}  {'Estado':<9} {'Uso':<10} {'Tipo':<12} {'Alícuota':>10}  {'Grupo':<28} Nombre")
    for tax in taxes:
        group = tax.tax_group_id.name if tax.tax_group_id else '-'
        state = 'Activo' if tax.active else 'Archivado'
        print(
            f"{tax.id:>7}  {state:<9} {tax.type_tax_use:<10} "
            f"{tax.amount_type:<12} {tax.amount:>9.4f}%  {group[:28]:<28} {tax.name}"
        )

    iibb = taxes.filtered(
        lambda tax: 'iibb' in tax_keywords(tax) or 'ingresos brutos' in tax_keywords(tax)
    )
    ganancias = taxes.filtered(lambda tax: 'ganancias' in tax_keywords(tax))
    print(f"\nResumen: {len(iibb)} impuesto(s) relacionado(s) con IIBB; "
          f"{len(ganancias)} relacionado(s) con Ganancias.")

    FiscalPosition = env['account.fiscal.position'].with_context(active_test=False)
    positions = FiscalPosition.search([
        ('company_id', 'in', [False, company.id]),
    ], order='name, id')
    has_ar_tax_lines = (
        'account.fiscal.position.l10n_ar_tax' in env.registry.models
        and field_exists('account.fiscal.position', 'l10n_ar_tax_ids')
    )
    has_afip_positions = field_exists(
        'account.fiscal.position', 'l10n_ar_afip_responsibility_type_ids'
    )
    print(f"\nPOSICIONES FISCALES: {len(positions)}")
    print("-" * 100)
    for position in positions:
        position_type = (
            position.l10n_ar_tax_type
            if field_exists('account.fiscal.position', 'l10n_ar_tax_type')
            else 'no disponible'
        )
        responsibilities = (
            ', '.join(position.l10n_ar_afip_responsibility_type_ids.mapped('name'))
            if has_afip_positions
            else 'no disponible'
        )
        print(
            f"[{position.id}] {position.name} | tipo={position_type} | "
            f"activa={position.active} | impuestos mapeados={len(position.tax_ids)} | "
            f"responsabilidades AFIP={responsibilities or '-'}"
        )
        if has_ar_tax_lines:
            for line in position.l10n_ar_tax_ids:
                tax_name = line.default_tax_id.name if line.default_tax_id else '-'
                group_name = line.tax_group_id.name if line.tax_group_id else '-'
                print(
                    f"    Regla [{line.id}] {line.tax_type} | grupo={group_name} | "
                    f"alícuota={line.aliquot:g}% | impuesto=[{line.default_tax_id.id or '-'}] "
                    f"{tax_name}"
                )

    Partner = env['res.partner'].with_context(active_test=False)
    partners = Partner.search([
        ('active', '=', True),
        ('parent_id', '=', False),
        '|',
        ('company_id', '=', False),
        ('company_id', '=', company.id),
    ], order='name, id')
    has_partner_afip = field_exists(
        'res.partner', 'l10n_ar_afip_responsibility_type_id'
    )
    without_position = partners.filtered(lambda partner: not partner.property_account_position_id)
    without_afip = (
        partners.filtered(lambda partner: not partner.l10n_ar_afip_responsibility_type_id)
        if has_partner_afip
        else Partner.browse()
    )

    print(f"\nCONTACTOS COMERCIALES: {len(partners)}")
    print(f"  Sin posición fiscal: {len(without_position)}")
    print(f"  Sin responsabilidad AFIP: "
          f"{len(without_afip) if has_partner_afip else 'campo no instalado'}")
    if has_partner_afip:
        print("  Situación AFIP / posición fiscal actual:")
        for partner in partners:
            responsibility = partner.l10n_ar_afip_responsibility_type_id
            position = partner.property_account_position_id
            print(
                f"    Contacto [{partner.id}] {partner.name} | "
                f"AFIP={responsibility.code if responsibility else '-'} "
                f"{responsibility.name if responsibility else ''} | "
                f"posición={f'[{position.id}] {position.name}' if position else '-'}"
            )

    print("\nAuditoría finalizada. No se ejecutó commit ni rollback porque no hubo escrituras.")


if __name__ == '__main__' or 'env' in globals():
    run_audit()
