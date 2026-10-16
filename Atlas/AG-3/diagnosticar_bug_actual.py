# -*- coding: utf-8 -*-
"""
Script de Diagnóstico Profundo del Bug Actual en Odoo 18:
- Inspección de MRO y origen de _compute_state y is_matched
- Configuración de las cuentas 1471, 1770, 1774 (reconcile, type)
- Por qué se eligen distintas cuentas en la creación actual del pago
Ticket: AG-3
"""
import inspect

def diagnosticar_bug_actual(env):
    print("=" * 95)
    print("1. ORIGEN DE LA LÓGICA DE ESTADOS Y CAMPOS COMPUTADOS")
    print("=" * 95)
    
    Payment = env['account.payment']
    
    # Rastrear qué módulos modifican _compute_state
    print("\n[+] Clases en MRO que implementan '_compute_state':")
    for cls in Payment.__class__.__mro__:
        if '_compute_state' in cls.__dict__:
            try:
                src_file = inspect.getfile(cls)
                print(f"  - Clase: {cls.__name__:30} | Archivo: {src_file}")
            except Exception:
                print(f"  - Clase: {cls.__name__}")

    # Rastrear campo is_matched
    is_matched_field = Payment._fields.get('is_matched')
    if is_matched_field:
        print(f"\n[+] Campo 'is_matched':")
        print(f"    compute: {is_matched_field.compute}")
        if is_matched_field.compute:
            try:
                method = getattr(Payment, is_matched_field.compute)
                print(f"    Código de {is_matched_field.compute}:\n{inspect.getsource(method)}")
            except Exception as e:
                print(f"    No se pudo extraer código de {is_matched_field.compute}: {e}")

    # Rastrear super()._compute_state() de Odoo base
    print("\n" + "=" * 95)
    print("2. INSPECCIÓN DE LAS 3 CUENTAS INVOLUCRADAS (1471, 1774, 1770)")
    print("=" * 95)
    Account = env['account.account']
    accounts = Account.browse([1471, 1774, 1770])
    for acc in accounts:
        print(f"Cuenta ID [{acc.id}] {acc.display_name}:")
        print(f"  - Código: {acc.code}")
        print(f"  - Nombre: {acc.name}")
        print(f"  - Tipo interno (account_type): {acc.account_type}")
        print(f"  - ¿Permite Conciliación? (reconcile): {acc.reconcile}")

    print("\n" + "=" * 95)
    print("3. CONFIGURACIÓN EXACTA DE MÉTODOS DEL DIARIO [69] CHEQUES DE TERCEROS")
    print("=" * 95)
    journal_69 = env['account.journal'].browse(69)
    print(f"Diario: [{journal_69.id}] {journal_69.name} (Tipo: {journal_69.type})")
    print(f"Cuenta por defecto (default_account_id): [{journal_69.default_account_id.id}] {journal_69.default_account_id.display_name}")
    
    print("\nMétodos Salientes (Outbound):")
    for l in journal_69.outbound_payment_method_line_ids:
        print(f"  Línea [{l.id}] {l.name} (código: {l.code})")
        print(f"    - payment_account_id: [{l.payment_account_id.id if l.payment_account_id else 'None'}] {l.payment_account_id.display_name if l.payment_account_id else 'None'}")
        
    print("\nMétodos Entrantes (Inbound):")
    for l in journal_69.inbound_payment_method_line_ids:
        print(f"  Línea [{l.id}] {l.name} (código: {l.code})")
        print(f"    - payment_account_id: [{l.payment_account_id.id if l.payment_account_id else 'None'}] {l.payment_account_id.display_name if l.payment_account_id else 'None'}")

    print("\n" + "=" * 95)
    print("4. SIMULACIÓN: ¿QUÉ CUENTA ASIGNA ODOO AL CREAR UN PAGO HOY?")
    print("=" * 95)
    # Ver cómo se calcula outstanding_account_id en account.payment
    out_field = Payment._fields.get('outstanding_account_id')
    if out_field:
        print(f"Campo 'outstanding_account_id' compute: {out_field.compute}")
        try:
            if out_field.compute:
                method = getattr(Payment, out_field.compute)
                print(f"Código fuente de {out_field.compute}:\n{inspect.getsource(method)}")
        except Exception as e:
            print(f"No se pudo extraer código de outstanding_account_id: {e}")

if __name__ == '__main__' or 'env' in locals():
    if 'env' in locals():
        diagnosticar_bug_actual(env)
    else:
        print("Ejecutar en la shell de Odoo: python3 odoo-bin shell")
