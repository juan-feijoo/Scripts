# -*- coding: utf-8 -*-
"""
================================================================================
SCRIPT EXTRACTOR DE REFERENCIA DE IMPUESTOS Y POSICIONES FISCALES (ODOO 18+)
================================================================================
Entorno: Odoo 18.0+ Enterprise (Localización Argentina)
Propósito: Ejecutar en una base de datos modelo/sana para exportar la estructura
           exacta de impuestos de IIBB/Percepciones, cuentas contables y posiciones
           fiscales.

Modo de uso en odoo-bin shell:
    exec(open('export_tax_reference.py').read())
    o:
    python3 odoo-bin shell -d <base_sana> < export_tax_reference.py
================================================================================
"""
import json
import logging

_logger = logging.getLogger("TAX_EXPORT")

# ------------------------------------------------------------------------------
# CONFIGURACIÓN
# ------------------------------------------------------------------------------
# Si conoces el ID de compañía de la base sana ponlo aquí, o None para tomar la primera/activa
TARGET_COMPANY_ID = None  
OUTPUT_JSON_FILE = "tax_reference_export.json"

print("\n" + "=" * 90)
print(" [*] INICIANDO EXTRACCIÓN DE IMPUESTOS DE REFERENCIA (ODOO 18+)")
print("=" * 90 + "\n")

# Determinar compañía
if TARGET_COMPANY_ID:
    company = env["res.company"].browse(TARGET_COMPANY_ID)
else:
    company = env.company

print(f"[i] Compañía seleccionada: [{company.id}] {company.name} (País: {company.country_id.code})")

# Buscamos impuestos de ventas vinculados a IIBB, Percepciones o códigos AFIP de percepción
domain = [
    ("company_id", "=", company.id),
    ("type_tax_use", "in", ["sale", "purchase"]),
    "|", "|", "|",
    ("tax_group_id.name", "ilike", "perc"),
    ("tax_group_id.name", "ilike", "iibb"),
    ("name", "ilike", "iibb"),
    ("l10n_ar_tribute_afip_code", "in", ["06", "07", "08"]),
]

taxes = env["account.tax"].search(domain, order="type_tax_use desc, name asc")
print(f"[i] Total de impuestos de percepción/IIBB encontrados: {len(taxes)}\n")

reference_data = {
    "source_company": {
        "id": company.id,
        "name": company.name,
        "country_code": company.country_id.code,
    },
    "taxes": [],
}

print(f"{'ID':<5} | {'Nombre Impuesto':<30} | {'Tasa':<7} | {'Uso':<8} | {'Provincia':<15} | {'Cuenta Contable':<25}")
print("-" * 95)

for tax in taxes:
    # Obtener cuentas de repartición de tipo tax
    rep_tax_lines = tax.repartition_line_ids.filtered(lambda l: l.repartition_type == "tax")
    invoice_tax_line = rep_tax_lines.filtered(lambda l: l.document_type == "invoice")[:1]
    refund_tax_line = rep_tax_lines.filtered(lambda l: l.document_type == "refund")[:1]

    inv_account = invoice_tax_line.account_id if invoice_tax_line else env["account.account"]
    ref_account = refund_tax_line.account_id if refund_tax_line else env["account.account"]

    # Posiciones fiscales y reemplazos (Odoo 18)
    fps = [
        {"id": fp.id, "name": fp.name}
        for fp in tax.fiscal_position_ids
    ] if hasattr(tax, "fiscal_position_ids") else []

    replaces = [
        {"id": orig.id, "name": orig.name, "amount": orig.amount}
        for orig in tax.original_tax_ids
    ] if hasattr(tax, "original_tax_ids") else []

    tax_entry = {
        "id": tax.id,
        "name": tax.name,
        "amount": tax.amount,
        "amount_type": tax.amount_type,
        "type_tax_use": tax.type_tax_use,
        "tax_label": getattr(tax, "tax_label", "") or "",
        "description": tax.description or "",
        "tax_group": {
            "id": tax.tax_group_id.id if tax.tax_group_id else False,
            "name": tax.tax_group_id.name if tax.tax_group_id else "",
        },
        "l10n_ar": {
            "state_id": tax.l10n_ar_state_id.id if hasattr(tax, "l10n_ar_state_id") and tax.l10n_ar_state_id else False,
            "state_name": tax.l10n_ar_state_id.name if hasattr(tax, "l10n_ar_state_id") and tax.l10n_ar_state_id else "",
            "state_code": tax.l10n_ar_state_id.code if hasattr(tax, "l10n_ar_state_id") and tax.l10n_ar_state_id else "",
            "code": getattr(tax, "l10n_ar_code", False) or False,
            "tribute_afip_code": getattr(tax, "l10n_ar_tribute_afip_code", False) or False,
            "tax_type": getattr(tax, "l10n_ar_tax_type", False) or False,
        },
        "accounts": {
            "invoice": {
                "account_id": inv_account.id if inv_account else False,
                "account_code": inv_account.code if inv_account else "",
                "account_name": inv_account.name if inv_account else "",
            },
            "refund": {
                "account_id": ref_account.id if ref_account else False,
                "account_code": ref_account.code if ref_account else "",
                "account_name": ref_account.name if ref_account else "",
            },
        },
        "fiscal_positions": fps,
        "replaces_taxes": replaces,
        "price_include": tax.price_include,
        "include_base_amount": tax.include_base_amount,
        "is_base_affected": getattr(tax, "is_base_affected", False),
    }

    reference_data["taxes"].append(tax_entry)

    acc_display = f"{inv_account.code} - {inv_account.name}" if inv_account else "[SIN CUENTA]"
    state_display = tax_entry["l10n_ar"]["state_name"] or "[S/PROV]"
    print(f"{tax.id:<5} | {tax.name[:30]:<30} | {tax.amount:<7.2f} | {tax.type_tax_use:<8} | {state_display[:15]:<15} | {acc_display[:25]:<25}")

# Guardar en archivo JSON
with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
    json.dump(reference_data, f, indent=2, ensure_ascii=False)

print("\n" + "=" * 90)
print(f"[+] Archivo JSON de referencia generado con éxito: {OUTPUT_JSON_FILE}")
print(f"[+] Total exportado: {len(reference_data['taxes'])} impuestos analizados con sus cuentas y mapeos.")
print("=" * 90 + "\n")

