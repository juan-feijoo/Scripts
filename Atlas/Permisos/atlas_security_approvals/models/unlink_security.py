# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError


def _check_atlas_unlink_permission(self, doc_description):
    """
    Centraliza la validación de eliminación según la matriz de perfiles Atlas.
    Permite el borrado a administradores/superusuarios o a miembros del grupo
    'Atlas: Permitir Eliminación de Movimientos' (Resp. Administración y Resp. General).
    """
    env = self.env
    if env.is_admin() or env.su:
        return
    if not env.user.has_group('atlas_security_approvals.group_atlas_can_unlink'):
        raise UserError(_(
            "Acción denegada: Su rol no tiene permisos para eliminar registros de %s.\n\n"
            "Según las políticas de seguridad de Atlas, la eliminación de documentos y movimientos "
            "está restringida exclusivamente a Responsable de Administración y Responsable General.",
            doc_description
        ))


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def unlink(self):
        _check_atlas_unlink_permission(self, _("Órdenes de Venta"))
        return super().unlink()


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def unlink(self):
        _check_atlas_unlink_permission(self, _("Órdenes de Compra"))
        return super().unlink()


class AccountMove(models.Model):
    _inherit = 'account.move'

    def unlink(self):
        _check_atlas_unlink_permission(self, _("Facturas y Asientos Contables"))
        return super().unlink()


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def unlink(self):
        _check_atlas_unlink_permission(self, _("Pagos y Cobros"))
        return super().unlink()
