# -*- coding: utf-8 -*-
"""
Script de Auditoría para Odoo Shell: Módulos y Configuración de Cheques de Terceros
Ticket: AG-3
Entorno: Odoo 17.0+e / 18.0+e / 19.0+e (Odoo.sh)
"""

def auditar_modulos_y_configuracion(env):
    print("=" * 80)
    print("AUDITORÍA DE MÓDULOS INSTALADOS (ADHOC & CHEQUES & PAGOS)")
    print("=" * 80)
    
    # 1. Módulos instalados relacionados
    domain = [
        ('state', '=', 'installed'),
        '|', '|', '|', '|',
        ('name', 'ilike', 'check'),
        ('name', 'ilike', 'payment'),
        ('name', 'ilike', 'latam'),
        ('name', 'ilike', 'adhoc'),
        ('name', 'ilike', 'l10n_ar')
    ]
    modules = env['ir.module.module'].search(domain, order='author, name')
    
    adhoc_mods = []
    odoo_mods = []
    other_mods = []
    
    for mod in modules:
        author = mod.author or ''
        if 'adhoc' in author.lower() or 'adhoc' in mod.name.lower():
            adhoc_mods.append(mod)
        elif 'odoo' in author.lower():
            odoo_mods.append(mod)
        else:
            other_mods.append(mod)
            
    print(f"\n[+] Módulos de ADHOC instalados ({len(adhoc_mods)}):")
    for m in adhoc_mods:
        print(f"  - {m.name:40} | v{m.installed_version:15} | {m.shortdesc}")

    print(f"\n[+] Módulos Odoo / Localización estándar instalados ({len(odoo_mods)}):")
    relevant_odoo = [m for m in odoo_mods if any(k in m.name for k in ['check', 'payment_group', 'latam', 'l10n_ar'])]
    for m in relevant_odoo:
        print(f"  - {m.name:40} | v{m.installed_version:15} | {m.shortdesc}")

    # 2. Configuración de Diarios de Cheques de Terceros
    print("\n" + "=" * 80)
    print("AUDITORÍA DE DIARIOS DE CHEQUES")
    print("=" * 80)
    journals = env['account.journal'].search([
        '|', '|',
        ('name', 'ilike', 'cheque'),
        ('code', 'ilike', 'ch'),
        ('type', 'in', ['cash', 'bank'])
    ])
    
    for j in journals:
        print(f"\nDiario: [{j.id}] {j.name} (Código: {j.code}, Tipo: {j.type})")
        print(f"  - Empresa: {j.company_id.name} [ID {j.company_id.id}]")
        print(f"  - Cuenta por defecto (default_account_id): {j.default_account_id.code if j.default_account_id else 'None'} - {j.default_account_id.name if j.default_account_id else 'None'}")
        
        # Cuentas de pagos / cobros pendientes si existen en la versión
        suspense = getattr(j, 'suspense_account_id', None)
        if suspense:
            print(f"  - Cuenta transitoria (suspense_account_id): {suspense.code} - {suspense.name}")
            
        use_checkbooks = getattr(j, 'l10n_latam_use_checkbooks', 'N/A')
        print(f"  - Usa chequeras (l10n_latam_use_checkbooks): {use_checkbooks}")
        
        # Métodos de pago salientes (outbound)
        print("  - Métodos de pago salientes (outbound):")
        for line in j.outbound_payment_method_line_ids:
            acc = line.payment_account_id or getattr(j, 'default_account_id', False)
            print(f"    * Línea [{line.id}] {line.name} | Código: {line.code} | Cuenta de Pago: {acc.code if acc else 'None'} - {acc.name if acc else 'None'}")
            
        # Métodos de pago entrantes (inbound)
        print("  - Métodos de pago entrantes (inbound):")
        for line in j.inbound_payment_method_line_ids:
            acc = line.payment_account_id or getattr(j, 'default_account_id', False)
            print(f"    * Línea [{line.id}] {line.name} | Código: {line.code} | Cuenta de Cobro: {acc.code if acc else 'None'} - {acc.name if acc else 'None'}")

# Para ejecutar en Odoo Shell:
# from AG_3.audit_modulos_y_configuracion import auditar_modulos_y_configuracion
# auditar_modulos_y_configuracion(env)
if __name__ == '__main__' or 'env' in locals():
    if 'env' in locals():
        auditar_modulos_y_configuracion(env)
    else:
        print("Este script debe ejecutarse dentro de la shell de Odoo (odoo-bin shell / python3 odoo-bin shell).")
