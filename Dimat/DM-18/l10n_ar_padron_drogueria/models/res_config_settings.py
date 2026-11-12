# -*- coding: utf-8 -*-
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ar_drogueria_min_retention = fields.Float(
        related="company_id.l10n_ar_drogueria_min_retention",
        readonly=False,
        string="Piso Mínimo Retención Droguerías (%)"
    )
