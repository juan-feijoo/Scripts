# -*- coding: utf-8 -*-
"""
Script de Simulación de Prueba del Circuito (DRY-RUN / Rollback):
Demuestra por qué el circuito actual falla y cómo el cambio de configuración
logra que los pagos de cheques de terceros queden en 'paid' como efectivo.
Ticket: AG-3
"""

def simular_comportamiento(env):
    print("=" * 95)
    print("SIMULACIÓN DE COMPORTAMIENTO: CONFIGURACIÓN ACTUAL VS CONFIGURACIÓN PROPUESTA")
    print("=" * 95)
    
    j69 = env['account.journal'].browse(69)
    method_line_153 = env['account.payment.method.line'].browse(153)
    
    print(f"\nDiario 69: {j69.name} (Tipo: {j69.type})")
    print(f"  Cuenta por defecto (default_account_id): [{j69.default_account_id.id}] {j69.default_account_id.display_name}")
    print(f"\nMétodo Saliente Línea [153] {method_line_153.name}:")
    print(f"  Cuenta asignada actual (payment_account_id): [{method_line_153.payment_account_id.id if method_line_153.payment_account_id else 'None'}] {method_line_153.payment_account_id.display_name if method_line_153.payment_account_id else 'None'}")
    
    # Explicación de la condición de Odoo 18
    default_id = j69.default_account_id.id
    current_payment_account_id = method_line_153.payment_account_id.id if method_line_153.payment_account_id else default_id
    
    print("\n" + "-" * 95)
    print("1. EVALUACIÓN DE LA FÓRMULA DE ODOO 18 CON LA CONFIGURACIÓN ACTUAL:")
    print("-" * 95)
    print(f"Condición: pay.journal_id.default_account_id in liquidity_lines.account_id")
    print(f"  default_account_id del diario = [{default_id}] ({j69.default_account_id.code})")
    print(f"  cuenta de la línea generada   = [{current_payment_account_id}] ({method_line_153.payment_account_id.code if method_line_153.payment_account_id else 'None'})")
    
    coincide_actual = (default_id == current_payment_account_id)
    print(f"  ¿Coinciden?: {coincide_actual}")
    if not coincide_actual:
        print("  --> RESULTADO ACTUAL: Odoo entra al branch 'else' y exige extracto bancario.")
        print("      is_matched = False  -->  state = 'in_process' (EL PAGO QUEDA TRABADO)")
    else:
        print("  --> RESULTADO ACTUAL: is_matched = True --> state = 'paid'")

    print("\n" + "-" * 95)
    print("2. EVALUACIÓN SI payment_account_id SE DEJA EN BLANCO O SE ASIGNA A default_account_id:")
    print("-" * 95)
    print(f"Si method_line_153.payment_account_id = False (o {default_id}):")
    print(f"  cuenta de la línea generada pasará a ser [{default_id}] ({j69.default_account_id.code})")
    print(f"  ¿Coincide con default_account_id del diario?: TRUE")
    print("  --> RESULTADO: Odoo ejecuta:")
    print("      'pay.is_matched = True'")
    print("      'pay.state = paid'")
    print("      EL PAGO FUNCIONA EXACTAMENTE COMO EFECTIVO AL VALIDARSE.")

if __name__ == '__main__' or 'env' in locals():
    if 'env' in locals():
        simular_comportamiento(env)
    else:
        print("Ejecutar en la shell de Odoo: python3 odoo-bin shell")
