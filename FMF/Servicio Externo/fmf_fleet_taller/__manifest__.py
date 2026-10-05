# -*- coding: utf-8 -*-
{
    'name': 'FMF - Órdenes de Trabajo de Taller y Flota',
    'version': '17.0.1.0.0',
    'category': 'Services/Field Service',
    'summary': 'Gestión integral de Órdenes de Trabajo para Flota (Tractor, Arrastre, Livianos), Checklists y Descuento de Repuestos en Taller',
    'description': """
Módulo de Gestión de Taller Mecánico para FMF Group
===================================================
* Adaptado a formularios OT-TMEC-01 (Pesados: Tractor/Arrastre/Bitren) y OT-TMEC-02 (Livianos).
* Integración de Flota (fleet) con Servicio Externo (industry_fsm).
* Checklists completos con opciones OK / NO / NA.
* Descuento automático de inventario (stock) desde Almacén TALL (Taller Mecánico).
* Registro de tiempos de mecánicos por tareas (hr_timesheet).
* Actualización automática de odómetro (fleet.vehicle.odometer) y servicios de flota (fleet.vehicle.log.services).
* Reporte impreso en PDF QWeb idéntico a la Orden de Trabajo física (Rev. 9).
    """,
    'author': 'Odoo Noa',
    'depends': [
        'base',
        'fleet',
        'project',
        'industry_fsm',
        'industry_fsm_stock',
        'stock',
        'hr_timesheet',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/project_task_views.xml',
        'report/report_actions.xml',
        'report/report_ot_template.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OEEL-1',
}
