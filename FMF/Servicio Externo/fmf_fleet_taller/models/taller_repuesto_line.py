# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class FmfTallerRepuestoLine(models.Model):
    _name = 'fmf.taller.repuesto.line'
    _description = 'Línea de Repuesto Utilizado en Taller Mecánico'
    _order = 'id asc'

    task_id = fields.Many2one(
        'project.task',
        string='Orden de Trabajo',
        required=True,
        ondelete='cascade',
        index=True
    )
    product_id = fields.Many2one(
        'product.product',
        string='Repuesto / Producto',
        required=True,
        domain="[('type', '=', 'product')]"
    )
    default_code = fields.Char(
        string='Código / Referencia',
        related='product_id.default_code',
        readonly=True
    )
    product_uom_qty = fields.Float(
        string='Cantidad',
        required=True,
        default=1.0,
        digits='Product Unit of Measure'
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='UdM',
        related='product_id.uom_id',
        readonly=True
    )
    medidas = fields.Char(
        string='Medidas',
        help='Ejemplo: 13 x 90, 7/8 x 135 x 400, etc.'
    )
    observaciones = fields.Char(
        string='Observaciones'
    )
    stock_move_id = fields.Many2one(
        'stock.move',
        string='Movimiento de Stock',
        readonly=True,
        copy=False
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('done', 'Consumido'),
    ], string='Estado', default='draft', readonly=True)
