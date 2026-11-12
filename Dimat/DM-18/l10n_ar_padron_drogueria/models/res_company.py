# -*- coding: utf-8 -*-
from odoo import fields, models

class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ar_drogueria_min_retention = fields.Float(
        string="Piso Mínimo Retención Droguerías (%)",
        default=2.50,
        help="Alícuota mínima de retención exigida a droguerías según Resolución Normativa 42/12 de ARBA. "
             "Todo sujeto pasible con alícuota > 0 y menor a este valor se elevará a este piso."
    )
