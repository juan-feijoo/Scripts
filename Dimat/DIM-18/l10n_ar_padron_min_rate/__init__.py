from . import models
from . import wizard


def post_init_setup_arba_padron(env):
    """Inicializa parámetros RN 42/12, Posición Fiscal e impuestos ARBA en compañías AR."""
    ba_state = env.ref("base.state_ar_b", raise_if_not_found=False)
    ar_companies = env["res.company"].search(
        [
            ("country_id.code", "=", "AR"),
            ("chart_template", "in", ("ar_ri", "ar_base", "ar_ex")),
        ]
    )
    for company in ar_companies:
        if not company.with_company(company)._get_arba_wth_default_tax():
            continue
        if not company.l10n_ar_arba_wth_min_enabled:
            company.l10n_ar_arba_wth_min_enabled = True
        company.action_auto_configure_arba_wth()
        if ba_state:
            padrons = env["res.company.jurisdiction.padron"].search(
                [
                    ("company_id", "=", company.id),
                    ("state_id", "=", ba_state.id),
                    ("file_padron", "!=", False),
                ]
            )
            if padrons:
                padrons.with_company(company).action_sync_taxes_from_padron()
