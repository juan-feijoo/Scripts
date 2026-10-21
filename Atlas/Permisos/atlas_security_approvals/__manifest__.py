# -*- coding: utf-8 -*-
{
    'name': 'Atlas - Seguridad y Reglas de Aprobación',
    'version': '18.0.1.0.0',
    'category': 'Customizations',
    'summary': 'Control de aprobaciones Studio, restricción de borrado y permisos de roles Atlas',
    'author': 'Outsource Argentina',
    'license': 'OPL-1',
    'depends': [
        'sale_management',
        'purchase',
        'account_accountant',
        'web_studio',
    ],
    'data': [
        'security/security_groups.xml',
        'data/studio_approval_rules.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
