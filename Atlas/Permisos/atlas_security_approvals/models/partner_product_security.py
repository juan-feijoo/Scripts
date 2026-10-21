# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Restringe la carga/alta de nuevos contactos (clientes y proveedores)
        según la matriz de perfiles Atlas.
        """
        if not self.env.is_admin() and not self.env.su:
            if not self.env.context.get('skip_atlas_security_check'):
                if not self.env.user.has_group('atlas_security_approvals.group_atlas_can_manage_contacts'):
                    raise UserError(_(
                        "Acción denegada: Su rol no tiene permisos para dar de alta nuevos contactos (clientes o proveedores).\n\n"
                        "Según la matriz de perfiles Atlas, la creación de contactos está reservada exclusivamente "
                        "para los roles Administrativo, Responsable de Administración y Responsable General."
                    ))
        return super().create(vals_list)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Restringe la carga/alta de nuevos productos según la matriz de perfiles Atlas.
        """
        if not self.env.is_admin() and not self.env.su:
            if not self.env.context.get('skip_atlas_security_check'):
                if not self.env.user.has_group('atlas_security_approvals.group_atlas_can_manage_products'):
                    raise UserError(_(
                        "Acción denegada: Su rol no tiene permisos para dar de alta nuevos productos en el catálogo.\n\n"
                        "Según la matriz de perfiles Atlas, la creación de productos está reservada exclusivamente "
                        "para los roles Administrativo, Responsable de Administración y Responsable General."
                    ))
        return super().create(vals_list)
