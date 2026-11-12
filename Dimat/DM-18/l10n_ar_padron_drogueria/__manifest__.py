# -*- coding: utf-8 -*-
{
    "name": "Padrón ARBA para Droguerías (RN 42/12)",
    "version": "18.0.1.0.0",
    "category": "Accounting/Localizations/Argentina",
    "summary": "Importación mensual del padrón ARBA con aplicación del piso mínimo del 2.50% para droguerías (RN 42/12)",
    "author": "Dimat",
    "license": "LGPL-3",
    "depends": [
        "l10n_ar",
        "l10n_ar_tax",
        "account_payment_pro",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/padron_drogueria_wizard_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
}
