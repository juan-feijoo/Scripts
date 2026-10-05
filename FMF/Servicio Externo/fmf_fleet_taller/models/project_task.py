# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


CHECK_OPTIONS = [
    ('ok', 'OK'),
    ('no', 'NO'),
    ('na', 'N/A'),
]

REQ_OPTIONS = [
    ('si', 'SÍ'),
    ('no', 'NO'),
    ('na', 'N/A'),
]


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # -------------------------------------------------------------------------
    # ESTADO Y CONTROL DE OT
    # -------------------------------------------------------------------------
    ot_finalizada = fields.Boolean(
        string='OT Finalizada',
        default=False,
        tracking=True,
        copy=False
    )
    has_repuestos_pendientes = fields.Boolean(
        string='Tiene Repuestos Pendientes',
        compute='_compute_repuestos_status'
    )

    # -------------------------------------------------------------------------
    # CABECERA GENERAL DE TALLER
    # -------------------------------------------------------------------------
    tipo_ot = fields.Selection([
        ('tmec_01', 'OT-TMEC-01 (Tractor / Equipo de Arrastre)'),
        ('tmec_02', 'OT-TMEC-02 (Unidad Liviana)'),
    ], string='Tipo de OT', default='tmec_01', tracking=True)

    numero_ot = fields.Char(string='N° O.T.', tracking=True)
    hora_ot = fields.Char(string='Hora Recepción', default='10:30')

    # Flota: Tractor / Pesados
    tractor_id = fields.Many2one(
        'fleet.vehicle',
        string='Tractor',
        tracking=True
    )
    tractor_dominio = fields.Char(
        string='Dominio Tractor',
        related='tractor_id.license_plate',
        readonly=True
    )
    tractor_marca = fields.Char(
        string='Marca Tractor',
        related='tractor_id.model_id.brand_id.name',
        readonly=True
    )
    tractor_modelo = fields.Char(
        string='Modelo Tractor',
        related='tractor_id.model_id.name',
        readonly=True
    )
    obs_tractor = fields.Text(string='Observaciones de Tractor')

    # Flota: Arrastre (Cisterna, Semirremolque, Carreton, Bitren)
    arrastre_id = fields.Many2one(
        'fleet.vehicle',
        string='Equipo de Arrastre',
        tracking=True
    )
    arrastre_dominio = fields.Char(
        string='Dominio Arrastre',
        related='arrastre_id.license_plate',
        readonly=True
    )
    arrastre_tipo = fields.Char(
        string='Tipo de Arrastre',
        related='arrastre_id.model_id.category_id.name',
        readonly=True
    )
    arrastre_modelo = fields.Char(
        string='Modelo Arrastre',
        related='arrastre_id.model_id.name',
        readonly=True
    )
    obs_arrastre = fields.Text(string='Observaciones de Equipo de Arrastre')

    # Segundo equipo de arrastre (para Bitrenes)
    arrastre_2_id = fields.Many2one(
        'fleet.vehicle',
        string='Segundo Arrastre (Bitren)',
        tracking=True
    )
    obs_arrastre_2 = fields.Text(string='Observaciones Arrastre 2')

    # Flota: Unidad Liviana (OT-TMEC-02)
    vehiculo_liviano_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehículo Liviano',
        tracking=True
    )
    obs_liviano = fields.Text(string='Observaciones Trabajos Realizados')

    # Chofer y Kilómetros
    chofer_id = fields.Many2one(
        'res.partner',
        string='Chofer',
        tracking=True
    )
    chofer_nombre = fields.Char(
        string='Nombre Chofer',
        compute='_compute_chofer_nombre',
        store=True
    )
    km_actual = fields.Float(string='KM Actual', tracking=True)
    km_service = fields.Float(string='KM Próximo Service', tracking=True)
    km_restantes = fields.Float(
        string='Rem KM',
        compute='_compute_km_restantes',
        store=True,
        readonly=True
    )

    # -------------------------------------------------------------------------
    # CHECKLIST TRACTOR (OT-TMEC-01)
    # -------------------------------------------------------------------------
    chk_tr_aceite_motor = fields.Selection(CHECK_OPTIONS, string='Nivel Aceite Motor', default='ok')
    chk_tr_liq_refrigerante = fields.Selection(CHECK_OPTIONS, string='Nivel Líquido Refrigerante', default='ok')
    chk_tr_liq_frenos = fields.Selection(CHECK_OPTIONS, string='Nivel Líquido de Frenos', default='ok')
    chk_tr_aceite_diferencial = fields.Selection(CHECK_OPTIONS, string='Nivel Aceite Diferencial', default='ok')
    chk_tr_aceite_transmision = fields.Selection(CHECK_OPTIONS, string='Nivel Aceite Transmisión', default='ok')
    chk_tr_limpiaparabrisas = fields.Selection(CHECK_OPTIONS, string='Nivel Limpiaparabrisas', default='ok')
    chk_tr_combustible = fields.Selection(CHECK_OPTIONS, string='Nivel de Combustible', default='ok')
    chk_tr_fuga_fluidos = fields.Selection(CHECK_OPTIONS, string='Presenta Fuga de Fluidos', default='ok')

    chk_tr_estado_neumaticos = fields.Selection(CHECK_OPTIONS, string='Buen Estado Neumáticos', default='ok')
    chk_tr_rueda_auxilio = fields.Selection(CHECK_OPTIONS, string='Rueda de Auxilio', default='ok')
    chk_tr_checkpoint = fields.Selection(CHECK_OPTIONS, string='Check Point', default='ok')
    chk_tr_calibrado_neumaticos = fields.Selection(CHECK_OPTIONS, string='Calibrado Neumáticos', default='ok')
    chk_tr_torque_rueda = fields.Selection(CHECK_OPTIONS, string='Torque de Rueda', default='ok')

    chk_tr_bateria_bornes = fields.Selection(CHECK_OPTIONS, string='Estado Batería y Bornes', default='ok')
    chk_tr_bocina = fields.Selection(CHECK_OPTIONS, string='Bocina', default='ok')
    chk_tr_alarma_retroceso = fields.Selection(CHECK_OPTIONS, string='Alarma de Retroceso', default='ok')
    chk_tr_calefaccion_aa = fields.Selection(CHECK_OPTIONS, string='Calefacción / Aire Acondicionado', default='ok')
    chk_tr_luces_delanteras_traseras = fields.Selection(CHECK_OPTIONS, string='Control Luces Delanteras/Traseras', default='ok')
    chk_tr_luces_posicion = fields.Selection(CHECK_OPTIONS, string='Luces de Posición', default='ok')
    chk_tr_luces_bajas = fields.Selection(CHECK_OPTIONS, string='Luces Bajas', default='ok')
    chk_tr_luces_altas = fields.Selection(CHECK_OPTIONS, string='Luces Altas', default='ok')
    chk_tr_luces_freno = fields.Selection(CHECK_OPTIONS, string='Luces de Freno', default='ok')
    chk_tr_luces_retroceso = fields.Selection(CHECK_OPTIONS, string='Luces Retroceso', default='ok')
    chk_tr_luces_giro = fields.Selection(CHECK_OPTIONS, string='Luces de Giro', default='ok')
    chk_tr_luces_balizas = fields.Selection(CHECK_OPTIONS, string='Luces de Balizas', default='ok')
    chk_tr_luces_antinieblas = fields.Selection(CHECK_OPTIONS, string='Luces Antinieblas', default='ok')
    chk_tr_luces_testigos = fields.Selection(CHECK_OPTIONS, string='Luces Testigos del Tablero', default='ok')

    chk_tr_tren_delantero = fields.Selection(CHECK_OPTIONS, string='Control Tren Delantero', default='ok')
    chk_tr_tren_trasero = fields.Selection(CHECK_OPTIONS, string='Control Tren Trasero', default='ok')
    chk_tr_frenos = fields.Selection(CHECK_OPTIONS, string='Control de Frenos', default='ok')
    chk_tr_cintas_pastillas = fields.Selection(CHECK_OPTIONS, string='Control Cintas/Pastillas de Freno', default='ok')
    chk_tr_amortiguadores = fields.Selection(CHECK_OPTIONS, string='Control de Amortiguadores', default='ok')
    chk_tr_paquetes_elasticos = fields.Selection(CHECK_OPTIONS, string='Control Paquetes Elásticos', default='ok')
    chk_tr_bujes = fields.Selection(CHECK_OPTIONS, string='Control de Bujes', default='ok')

    chk_tr_correa = fields.Selection(CHECK_OPTIONS, string='Control de Correa', default='ok')
    chk_tr_radiador = fields.Selection(CHECK_OPTIONS, string='Control de Radiador', default='ok')
    chk_tr_arranque = fields.Selection(CHECK_OPTIONS, string='Control de Arranque', default='ok')
    chk_tr_mangueras_cableado = fields.Selection(CHECK_OPTIONS, string='Buen Estado Mangueras y Cableado', default='ok')

    chk_tr_req_tercero = fields.Selection(REQ_OPTIONS, string='Necesita Revisión de Tercero', default='no')
    chk_tr_req_repuesto = fields.Selection(REQ_OPTIONS, string='Necesita Algún Repuesto', default='no')

    # -------------------------------------------------------------------------
    # CHECKLIST EQUIPO DE ARRASTRE (OT-TMEC-01)
    # -------------------------------------------------------------------------
    chk_ar_sistema_electrico = fields.Selection(CHECK_OPTIONS, string='Buen Estado Sistema Eléctrico', default='ok')
    chk_ar_luces_posicion = fields.Selection(CHECK_OPTIONS, string='Luces de Posición', default='ok')
    chk_ar_luces_giro = fields.Selection(CHECK_OPTIONS, string='Luces de Giro', default='ok')
    chk_ar_luces_freno = fields.Selection(CHECK_OPTIONS, string='Luces de Freno', default='ok')
    chk_ar_luces_marcha_atras = fields.Selection(CHECK_OPTIONS, string='Luces Marcha Atrás', default='ok')
    chk_ar_luces_3_marias = fields.Selection(CHECK_OPTIONS, string='Luces 3 Marías', default='ok')
    chk_ar_alarma_retroceso = fields.Selection(CHECK_OPTIONS, string='Alarma de Retroceso', default='ok')

    chk_ar_estado_neumaticos = fields.Selection(CHECK_OPTIONS, string='Buen Estado Neumáticos', default='ok')
    chk_ar_rueda_auxilio = fields.Selection(CHECK_OPTIONS, string='Rueda de Auxilio', default='ok')
    chk_ar_checkpoint = fields.Selection(CHECK_OPTIONS, string='Check Point', default='ok')
    chk_ar_calibrado_neumaticos = fields.Selection(CHECK_OPTIONS, string='Calibrado Neumáticos', default='ok')
    chk_ar_torque_rueda = fields.Selection(CHECK_OPTIONS, string='Torque de Rueda', default='ok')

    chk_ar_cintas_pastillas = fields.Selection(CHECK_OPTIONS, string='Control Cintas/Pastillas de Freno', default='ok')
    chk_ar_campanas_discos = fields.Selection(CHECK_OPTIONS, string='Estado Campanas/Discos', default='ok')
    chk_ar_levas_registros = fields.Selection(CHECK_OPTIONS, string='Estado Levas, Registros y Complementos', default='ok')
    chk_ar_engrase_freno = fields.Selection(CHECK_OPTIONS, string='Engrase Sistema de Freno', default='ok')
    chk_ar_sensores_abs_ebs = fields.Selection(CHECK_OPTIONS, string='Estado Sensores y Cableado ABS/EBS', default='ok')
    chk_ar_sistema_abs_ebs = fields.Selection(CHECK_OPTIONS, string='Sistema Frenos ABS/EBS', default='ok')
    chk_ar_pulmones_spring = fields.Selection(CHECK_OPTIONS, string='Estado Pulmones de Freno Spring', default='ok')

    chk_ar_mangueras_acoples = fields.Selection(CHECK_OPTIONS, string='Estado Mangueras y Acoples', default='ok')
    chk_ar_tanque_aire = fields.Selection(CHECK_OPTIONS, string='Estado Tanque de Aire', default='ok')
    chk_ar_valvulas_aire = fields.Selection(CHECK_OPTIONS, string='Estado Válvulas de Aire', default='ok')
    chk_ar_pulmones_fuelle = fields.Selection(CHECK_OPTIONS, string='Estado Pulmones con Fuelle', default='ok')
    chk_ar_manguera_espiral = fields.Selection(CHECK_OPTIONS, string='Estado Manguera Espiral y Trailer', default='ok')
    chk_ar_perdida_aire = fields.Selection(CHECK_OPTIONS, string='Presenta Pérdida de Aire', default='ok')

    chk_ar_amortiguadores = fields.Selection(CHECK_OPTIONS, string='Control de Amortiguadores', default='ok')
    chk_ar_estabilizadores = fields.Selection(CHECK_OPTIONS, string='Control de Estabilizadores', default='ok')
    chk_ar_paq_elasticos_grampas = fields.Selection(CHECK_OPTIONS, string='Control Paquetes Elásticos y Grampas', default='ok')
    chk_ar_tensores_bujes_pernos = fields.Selection(CHECK_OPTIONS, string='Control Tensores, Bujes y Pernos', default='ok')
    chk_ar_balancines_bujes_pernos = fields.Selection(CHECK_OPTIONS, string='Revisar Balancines, Bujes y Pernos', default='ok')

    chk_ar_estado_mazas = fields.Selection(CHECK_OPTIONS, string='Controlar Estado de Mazas', default='ok')
    chk_ar_rulemanes_reten = fields.Selection(CHECK_OPTIONS, string='Revisión Rulemanes y Retén de Maza', default='ok')
    chk_ar_esparragos = fields.Selection(CHECK_OPTIONS, string='Estado de Espárragos', default='ok')
    chk_ar_tapa_maza = fields.Selection(CHECK_OPTIONS, string='Tapa de Maza', default='ok')
    chk_ar_engrase_mazas = fields.Selection(CHECK_OPTIONS, string='Engrase de Mazas', default='ok')

    chk_ar_req_tercero = fields.Selection(REQ_OPTIONS, string='Necesita Revisión de Tercero', default='no')
    chk_ar_req_repuesto = fields.Selection(REQ_OPTIONS, string='Necesita Algún Repuesto', default='no')

    # -------------------------------------------------------------------------
    # REPUESTOS UTILIZADOS E INVENTARIO
    # -------------------------------------------------------------------------
    taller_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Almacén Taller',
        default=lambda self: self._default_taller_warehouse()
    )
    repuesto_line_ids = fields.One2many(
        'fmf.taller.repuesto.line',
        'task_id',
        string='Repuestos Utilizados'
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Vale de Entrega Stock',
        readonly=True,
        copy=False
    )
    picking_state = fields.Selection(
        related='picking_id.state',
        string='Estado de Entrega Stock',
        readonly=True
    )

    # -------------------------------------------------------------------------
    # FIRMAS Y CIERRE
    # -------------------------------------------------------------------------
    supervisor_id = fields.Many2one('hr.employee', string='Supervisor de Taller')
    jefe_taller_id = fields.Many2one('hr.employee', string='Jefe de Taller')
    firma_supervisor = fields.Binary(string='Firma Supervisor', copy=False)
    firma_jefe_taller = fields.Binary(string='Firma Jefe de Taller', copy=False)

    # -------------------------------------------------------------------------
    # MÉTODOS Y CÁLCULOS
    # -------------------------------------------------------------------------
    @api.model
    def _default_taller_warehouse(self):
        wh = self.env['stock.warehouse'].search([('code', '=', 'TALL')], limit=1)
        if not wh:
            wh = self.env['stock.warehouse'].browse(104)
        if not wh.exists():
            wh = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        return wh

    @api.depends('km_service', 'km_actual')
    def _compute_km_restantes(self):
        for task in self:
            if task.km_service and task.km_actual:
                task.km_restantes = task.km_service - task.km_actual
            else:
                task.km_restantes = 0.0

    @api.depends('chofer_id')
    def _compute_chofer_nombre(self):
        for task in self:
            # sudo() para resolver el nombre sin importar restricciones multicompañía del contacto
            task.chofer_nombre = task.chofer_id.sudo().name if task.chofer_id else ''

    @api.depends('repuesto_line_ids.state')
    def _compute_repuestos_status(self):
        for task in self:
            task.has_repuestos_pendientes = any(line.state == 'draft' for line in task.repuesto_line_ids)

    def action_consumir_repuestos(self):
        """
        Genera el vale de salida (stock.picking) desde la ubicación de taller
        hacia consumo interno, descontando automáticamente del stock.
        """
        self.ensure_one()
        lineas_pendientes = self.repuesto_line_ids.filtered(lambda l: l.state == 'draft')
        if not lineas_pendientes:
            raise UserError(_('No hay repuestos pendientes de consumo en la tabla.'))

        warehouse = self.taller_warehouse_id or self._default_taller_warehouse()
        if not warehouse:
            raise UserError(_('No se encontró el almacén de Taller Mecánico.'))

        origen_loc = warehouse.lot_stock_id
        destino_loc = self.env['stock.location'].search([
            ('usage', '=', 'customer'),
            '|', ('company_id', '=', False), ('company_id', '=', warehouse.company_id.id)
        ], limit=1)
        if not destino_loc:
            destino_loc = self.env.ref('stock.stock_location_customers')

        picking_type = self.env['stock.picking.type'].search([
            ('warehouse_id', '=', warehouse.id),
            ('code', '=', 'outgoing')
        ], limit=1)
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([('warehouse_id', '=', warehouse.id)], limit=1)

        picking = self.picking_id
        if not picking or picking.state in ['done', 'cancel']:
            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'location_id': origen_loc.id,
                'location_dest_id': destino_loc.id,
                'origin': f"OT {self.numero_ot or self.name}",
                'company_id': warehouse.company_id.id,
            })
            self.picking_id = picking.id

        for line in lineas_pendientes:
            move = self.env['stock.move'].create({
                'name': f"Consumo OT {self.name}: {line.product_id.name}",
                'product_id': line.product_id.id,
                'product_uom_qty': line.product_uom_qty,
                'product_uom': line.product_uom_id.id or line.product_id.uom_id.id,
                'picking_id': picking.id,
                'location_id': origen_loc.id,
                'location_dest_id': destino_loc.id,
                'company_id': warehouse.company_id.id,
            })
            line.write({
                'stock_move_id': move.id,
                'state': 'done'
            })

        picking.action_confirm()
        picking.action_assign()

        for ml in picking.move_line_ids:
            ml.quantity = ml.quantity_product_uom

        try:
            picking.button_validate()
        except Exception:
            pass

        return True

    def action_finalizar_ot(self):
        """
        Cierre integral de la Orden de Trabajo de Taller:
        1. Descuenta repuestos pendientes si los hubiera.
        2. Registra el odómetro en Flota.
        3. Crea el registro de mantenimiento en fleet.vehicle.log.services.
        4. Marca la OT como finalizada y oculta botones de acción.
        """
        self.ensure_one()
        # 1. Consumir repuestos si hay pendientes
        if any(l.state == 'draft' for l in self.repuesto_line_ids):
            self.action_consumir_repuestos()

        vehiculo = self.tractor_id or self.vehiculo_liviano_id

        # 2. Registrar Odómetro
        if vehiculo and self.km_actual > 0:
            self.env['fleet.vehicle.odometer'].create({
                'vehicle_id': vehiculo.id,
                'value': self.km_actual,
                'date': fields.Date.context_today(self),
            })

        # 3. Registrar Log de Servicio en Flota
        if vehiculo:
            tipo_servicio = self.env['fleet.service.type'].search([
                ('name', 'ilike', 'Mantenimiento')
            ], limit=1)
            if not tipo_servicio:
                tipo_servicio = self.env['fleet.service.type'].search([], limit=1)

            costo_repuestos = sum(
                l.product_uom_qty * l.product_id.standard_price 
                for l in self.repuesto_line_ids
            )

            desc = f"OT N° {self.numero_ot or self.id} - Taller Mecánico.\n"
            if self.obs_arrastre:
                desc += f"Arrastre: {self.obs_arrastre}\n"

            self.env['fleet.vehicle.log.services'].create({
                'vehicle_id': vehiculo.id,
                'service_type_id': tipo_servicio.id if tipo_servicio else False,
                'amount': costo_repuestos,
                'description': desc,
                'date': fields.Date.context_today(self),
                'odometer': self.km_actual,
            })

        # 4. Actualizar Estado de la Tarea / OT
        self.ot_finalizada = True

        if hasattr(self, 'fsm_done'):
            self.fsm_done = True

        # En Odoo 17 se utiliza el campo 'state' para marcar tareas como hechas
        if 'state' in self._fields:
            try:
                self.state = '1_done'
            except Exception:
                pass

        # Si el proyecto tiene etapa de finalizado / plegada, mover la tarea
        if self.project_id:
            stage_done = self.env['project.task.type'].search([
                ('project_ids', 'in', self.project_id.ids),
                ('fold', '=', True)
            ], limit=1)
            if stage_done:
                self.stage_id = stage_done.id

        return True

    def action_reabrir_ot(self):
        """Permite reabrir una OT finalizada si requiere correcciones."""
        self.ensure_one()
        self.ot_finalizada = False
        if hasattr(self, 'fsm_done'):
            self.fsm_done = False
        if 'state' in self._fields:
            try:
                self.state = '01_in_progress'
            except Exception:
                pass
        return True

    def action_ver_picking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Entrega de Repuestos'),
            'res_model': 'stock.picking',
            'res_id': self.picking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
