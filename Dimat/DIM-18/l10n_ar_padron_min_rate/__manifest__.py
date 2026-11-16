{
    "name": "ARBA - Padrón Mínimo Retenciones (RN 42/12) y Auto-Configuración",
    "summary": (
        "Corrige lectura de subcarpetas en ZIP ARBA, aplica alícuota mínima parametrizable "
        "de retención IIBB (ej. 2,50% droguerías), auto-configura impuestos/posición fiscal "
        "y notifica nuevas alícuotas detectadas."
    ),
    "version": "18.0.1.0.0",
    "category": "Accounting/Localizations",
    "author": "Outsource Argentina",
    "website": "https://www.outsourcearg.com",
    "license": "LGPL-3",
    "depends": [
        "l10n_ar_tax",
        "mail",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/res_company_jurisdiction_padron_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "post_init_hook": "post_init_setup_arba_padron",
}
