# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'

    wholesale_pricelist_id = fields.Many2one(
        comodel_name='product.pricelist',
        string="Lista Mayorista",
        help="Segunda lista de precios para calcular y mostrar el precio mayorista en la etiqueta.",
    )
    print_vendor = fields.Boolean(
        string="Mostrar Proveedor Principal",
        default=True,
        help="Si está activo, incluye el nombre/código del proveedor principal en la etiqueta impresa.",
    )
    main_seller_id = fields.Many2one(
        comodel_name='res.partner',
        string="Proveedor Principal",
        compute='_compute_main_seller_id',
        help="Informativo: proveedor principal si se imprime un único producto o si comparten el mismo.",
    )

    @api.depends('product_ids', 'product_tmpl_ids')
    def _compute_main_seller_id(self):
        for wizard in self:
            products = wizard.product_ids or wizard.product_tmpl_ids
            if len(products) == 1 and products.seller_ids:
                wizard.main_seller_id = products.seller_ids[0].partner_id
            elif products:
                # Si todos los seleccionados tienen el mismo proveedor
                sellers = products.mapped('seller_ids')
                first_partners = set()
                for p in products:
                    if p.seller_ids:
                        first_partners.add(p.seller_ids[0].partner_id.id)
                if len(first_partners) == 1:
                    wizard.main_seller_id = list(first_partners)[0]
                else:
                    wizard.main_seller_id = False
            else:
                wizard.main_seller_id = False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        # 1. Lista Minorista por defecto: Si no vino seteada, priorizar 'Lista ARS' (ID: 5)
        if 'pricelist_id' in fields_list and not res.get('pricelist_id'):
            pl_min = self.env['product.pricelist'].browse(5)
            if not pl_min.exists():
                pl_min = self.env['product.pricelist'].search([
                    ('name', 'ilike', 'Lista ARS'),
                    ('company_id', 'in', [self.env.company.id, False])
                ], limit=1)
            if pl_min:
                res['pricelist_id'] = pl_min.id

        # 2. Lista Mayorista por defecto: Priorizar ID 7 'MAYORISTA'
        if 'wholesale_pricelist_id' in fields_list and not res.get('wholesale_pricelist_id'):
            pl_may = self.env['product.pricelist'].browse(7)
            if not pl_may.exists():
                pl_may = self.env['product.pricelist'].search([
                    ('name', 'ilike', 'mayorista'),
                    ('company_id', 'in', [self.env.company.id, False])
                ], limit=1)
            if pl_may:
                res['wholesale_pricelist_id'] = pl_may.id

        return res

    def _prepare_report_data(self):
        xml_id, data = super()._prepare_report_data()
        data.update({
            'wholesale_pricelist_id': self.wholesale_pricelist_id.id if self.wholesale_pricelist_id else False,
            'print_vendor': self.print_vendor,
        })
        return xml_id, data

    def process(self):
        extra_ctx = {}
        if self.wholesale_pricelist_id:
            extra_ctx['wholesale_pricelist_id'] = self.wholesale_pricelist_id.id
        extra_ctx['print_vendor'] = self.print_vendor
        
        action = super(ProductLabelLayout, self.with_context(**extra_ctx)).process()
        if isinstance(action, dict):
            # Odoo devuelve action['context'] como un frozendict inmutable
            action_ctx = dict(action.get('context') or {})
            action_ctx.update(extra_ctx)
            action['context'] = action_ctx
        return action
