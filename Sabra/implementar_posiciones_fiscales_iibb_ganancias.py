#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configura posiciones de IIBB y retención de Ganancias en Odoo Argentina."""

if 'env' not in globals():
    raise RuntimeError(
        "Ejecuta este archivo dentro de 'odoo-bin shell', donde 'env' está definido."
    )

# Seguridad: revisar primero la salida de la auditoría; cambiar a False solo
# después de confirmar los impuestos que se detectaron en la compañía.
DRY_RUN = True
COMPANY_ID = None
CONFIGURAR_IIBB = True
CONFIGURAR_RETENCION_GANANCIAS = True
ASIGNAR_POSICION_BASE_AFIP = True

BASE_AFIP_CODES = {'1', '4', '5', '6', '9'}
WITHHOLDING_WORDS = ('retenc', 'withhold', 'wth')


def field_exists(model_name, field_name):
    return model_name in env.registry.models and field_name in env[model_name]._fields


def tax_text(tax):
    group = tax.tax_group_id.name if tax.tax_group_id else ''
    return f"{tax.name} {tax.description or ''} {group}".casefold()


def tax_kind(tax):
    text = tax_text(tax)
    is_iibb = ('iibb' in text or 'ingresos brutos' in text)
    if CONFIGURAR_IIBB and is_iibb and 'perc' in text and tax.type_tax_use == 'sale':
        return 'perception'
    has_ganancias = 'ganancias' in text
    has_withholding_marker = any(word in text for word in WITHHOLDING_WORDS)
    if (
        CONFIGURAR_RETENCION_GANANCIAS
        and has_ganancias
        and has_withholding_marker
        and tax.type_tax_use in ('purchase', 'none')
    ):
        return 'withholding'
    return None


def position_name(tax, kind):
    prefix = 'Percepción IIBB' if kind == 'perception' else 'Retención Ganancias'
    return f"{prefix} - {tax.name}"


def ensure_position(tax, kind, company, country, line_model):
    FiscalPosition = env['account.fiscal.position']
    name = position_name(tax, kind)
    position = FiscalPosition.with_context(active_test=False).search([
        ('company_id', '=', company.id),
        ('name', '=', name),
    ], limit=1)

    if position:
        if not position.active:
            raise RuntimeError(
                f"La posición [{position.id}] '{name}' está archivada. "
                "Revisa y reactiva el registro manualmente antes de continuar."
            )
        unrelated_taxes = position.tax_ids - tax
        unrelated_lines = position.l10n_ar_tax_ids.filtered(
            lambda line: line.default_tax_id and line.default_tax_id != tax
        )
        if unrelated_taxes or unrelated_lines:
            raise RuntimeError(
                f"La posición [{position.id}] '{name}' ya tiene otros impuestos asociados. "
                "No se modificó para evitar sobrescribir su configuración."
            )
        print(f"  [EXISTENTE] Posición [{position.id}] {name}")
    else:
        values = {
            'name': name,
            'company_id': company.id,
            'auto_apply': False,
            'l10n_ar_tax_type': kind,
        }
        if country and field_exists('account.fiscal.position', 'country_id'):
            values['country_id'] = country.id
        position = FiscalPosition.create(values)
        print(f"  [+ CREADA] Posición [{position.id}] {name}")

    if position.l10n_ar_tax_type != kind or position.auto_apply:
        position.write({
            'l10n_ar_tax_type': kind,
            'auto_apply': False,
        })

    line = position.l10n_ar_tax_ids.filtered(
        lambda current: current.default_tax_id == tax
    )[:1]
    line_values = {
        'fiscal_position_id': position.id,
        'tax_type': kind,
        'default_tax_id': tax.id,
        'tax_group_id': tax.tax_group_id.id if tax.tax_group_id else False,
        'aliquot': tax.amount,
    }
    if line:
        if any(getattr(line, field) != value for field, value in (
            ('tax_type', kind),
            ('default_tax_id', tax),
            ('tax_group_id', tax.tax_group_id),
            ('aliquot', tax.amount),
        )):
            line.write(line_values)
            print(f"    [ACTUALIZADA] Regla L10N [{line.id}] para impuesto [{tax.id}] {tax.name}")
    else:
        line = line_model.create(line_values)
        print(f"    [+ REGLA] Regla L10N [{line.id}] para impuesto [{tax.id}] {tax.name}")

    if tax not in position.tax_ids:
        position.write({'tax_ids': [(4, tax.id)]})
        print(f"    [+ VINCULADO] Impuesto [{tax.id}] agregado a tax_ids")


def base_positions_by_responsibility(company):
    if not field_exists(
        'account.fiscal.position', 'l10n_ar_afip_responsibility_type_ids'
    ):
        raise RuntimeError(
            "No existe l10n_ar_afip_responsibility_type_ids en account.fiscal.position; "
            "no se pueden asignar posiciones base automáticamente."
        )
    if not field_exists('res.partner', 'l10n_ar_afip_responsibility_type_id'):
        raise RuntimeError(
            "No existe l10n_ar_afip_responsibility_type_id en res.partner; "
            "no se pueden asignar posiciones base automáticamente."
        )
    if 'l10n_ar.afip.responsibility.type' not in env.registry.models:
        raise RuntimeError(
            "No está disponible l10n_ar.afip.responsibility.type; "
            "revisa que la localización argentina esté instalada."
        )

    responsibilities = env['l10n_ar.afip.responsibility.type'].search([
        ('code', 'in', list(BASE_AFIP_CODES)),
    ])
    positions = env['account.fiscal.position'].search([
        ('company_id', 'in', [False, company.id]),
    ])
    result = {}
    for responsibility in responsibilities:
        matches = positions.filtered(
            lambda position: (
                responsibility in position.l10n_ar_afip_responsibility_type_ids
                and (
                    not field_exists('account.fiscal.position', 'l10n_ar_tax_type')
                    or position.l10n_ar_tax_type in (False, 'none')
                )
            )
        )
        if len(matches) == 1:
            result[responsibility.id] = matches
            print(
                f"  AFIP {responsibility.code} ({responsibility.name}) -> "
                f"[{matches.id}] {matches.name}"
            )
        elif len(matches) > 1:
            print(
                f"  [AMBIGUO] AFIP {responsibility.code} ({responsibility.name}): "
                f"{len(matches)} posiciones base; no se asignará."
            )
        else:
            print(
                f"  [SIN MAPEO] AFIP {responsibility.code} ({responsibility.name}): "
                "no hay posición base vinculada."
            )
    return result


def assign_base_positions(company, mapping):
    partners = env['res.partner'].search([
        ('active', '=', True),
        ('parent_id', '=', False),
        '|',
        ('company_id', '=', False),
        ('company_id', '=', company.id),
    ], order='id')
    updated = 0
    skipped_existing = 0
    skipped_unmapped = 0
    for partner in partners:
        if partner.property_account_position_id:
            skipped_existing += 1
            continue
        responsibility = partner.l10n_ar_afip_responsibility_type_id
        target = mapping.get(responsibility.id) if responsibility else False
        if not target:
            skipped_unmapped += 1
            continue
        partner.write({'property_account_position_id': target.id})
        print(
            f"  [ASIGNADO] Contacto [{partner.id}] {partner.name} -> "
            f"[{target.id}] {target.name}"
        )
        updated += 1

    print(
        f"Contactos: {updated} asignados; {skipped_existing} conservan posición actual; "
        f"{skipped_unmapped} sin mapeo AFIP."
    )


def execute():
    company = env['res.company'].browse(COMPANY_ID) if COMPANY_ID else env.company
    if not company.exists():
        raise ValueError(f"No existe la compañía configurada: {COMPANY_ID}")
    if 'l10n_ar_tax_type' not in env['account.fiscal.position']._fields:
        raise RuntimeError(
            "No existe account.fiscal.position.l10n_ar_tax_type. "
            "Verifica la versión de Odoo y la localización l10n_ar."
        )
    if 'account.fiscal.position.l10n_ar_tax' not in env.registry.models:
        raise RuntimeError(
            "No está disponible account.fiscal.position.l10n_ar_tax; "
            "instala/actualiza el módulo de localización fiscal antes de continuar."
        )

    line_model = env['account.fiscal.position.l10n_ar_tax']
    required_line_fields = {
        'fiscal_position_id', 'tax_type', 'default_tax_id', 'tax_group_id', 'aliquot',
    }
    missing_fields = required_line_fields - set(line_model._fields)
    if missing_fields:
        raise RuntimeError(
            "Faltan campos requeridos en account.fiscal.position.l10n_ar_tax: "
            + ', '.join(sorted(missing_fields))
        )

    taxes = env['account.tax'].search([
        ('company_id', 'in', [False, company.id]),
        ('active', '=', True),
    ], order='name, id')
    candidates = [(tax, tax_kind(tax)) for tax in taxes]
    candidates = [(tax, kind) for tax, kind in candidates if kind]

    print("=" * 90)
    print(
        f"CONFIGURACIÓN FISCAL | [{company.id}] {company.name} | "
        f"{'SIMULACIÓN (DRY-RUN)' if DRY_RUN else 'APLICANDO CAMBIOS'}"
    )
    print("Los impuestos no se crean; se reutilizan solo los ya existentes.")
    print("=" * 90)
    print(f"Impuestos identificados para configurar: {len(candidates)}")
    for tax, kind in candidates:
        print(
            f"  [{tax.id}] {tax.name} | tipo={kind} | "
            f"uso={tax.type_tax_use} | alícuota={tax.amount:g}% | "
            f"grupo={tax.tax_group_id.name if tax.tax_group_id else '-'}"
        )

    country = env.ref('base.ar', raise_if_not_found=False)
    for tax, kind in candidates:
        ensure_position(tax, kind, company, country, line_model)

    if ASIGNAR_POSICION_BASE_AFIP:
        print("\nAsignación de posiciones base por responsabilidad AFIP:")
        mapping = base_positions_by_responsibility(company)
        assign_base_positions(company, mapping)
        print(
            "Las posiciones específicas de IIBB y Ganancias no se asignan a contactos "
            "automáticamente; requieren revisión de jurisdicción/condición fiscal."
        )

    if DRY_RUN:
        env.cr.rollback()
        print("\n[DRY-RUN] Se ejecutó rollback: ningún cambio quedó guardado.")
        print("Luego de revisar la auditoría, cambia DRY_RUN a False para aplicar.")
    else:
        env.cr.commit()
        print("\n[OK] Cambios confirmados en la base de datos.")


if __name__ == '__main__' or 'env' in globals():
    execute()
