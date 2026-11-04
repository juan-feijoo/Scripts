import json
from decimal import Decimal
from datetime import datetime

with open('cheques_extraidos.json', 'r', encoding='utf-8-sig') as f:
    data = json.load(f)

total_importe = Decimal('0.00')
partners = {}
estados = {}
cheques_parsed = []

for row in data:
    # Parse amount
    # e.g. '$ 1.135.295,00'
    raw_amt = row['Importe'].replace('$', '').replace('.', '').replace(',', '.').strip()
    amt = Decimal(raw_amt)
    total_importe += amt

    # Parse dates
    femis = datetime.strptime(row['FechaEmision'], '%d/%m/%Y').date()
    fpago = datetime.strptime(row['FechaPago'], '%d/%m/%Y').date()

    cuit = row['CUIT']
    rs = row['RazonSocial']
    estado = row['Estado']

    estados[estado] = estados.get(estado, 0) + 1

    if cuit not in partners:
        partners[cuit] = {'name': rs, 'count': 0, 'total': Decimal('0.00'), 'cheques': []}
    partners[cuit]['count'] += 1
    partners[cuit]['total'] += amt
    partners[cuit]['cheques'].append({
        'number': row['NroCheque'],
        'issue_date': str(femis),
        'payment_date': str(fpago),
        'amount': float(amt),
        'state': estado
    })

    cheques_parsed.append({
        'number': row['NroCheque'],
        'issue_date': str(femis),
        'payment_date': str(fpago),
        'cuit': cuit,
        'partner_name': rs,
        'amount': float(amt),
        'state': estado
    })

print(f"Total cheques: {len(data)}")
print(f"Total monto sumado: $ {total_importe:,.2f}")
print(f"\nDistribución por estados bancarios:")
for k, v in estados.items():
    print(f"  - {k}: {v} cheques")

print(f"\nProveedores únicos ({len(partners)}):")
for cuit, pinfo in sorted(partners.items(), key=lambda x: x[1]['total'], reverse=True):
    print(f"  - CUIT {cuit}: {pinfo['name']} | {pinfo['count']} cheques | Total: $ {pinfo['total']:,.2f}")

# Save clean structured data
with open('cheques_limpios.json', 'w', encoding='utf-8') as f:
    json.dump({
        'metadata': {
            'total_cheques': len(data),
            'total_amount': float(total_importe),
            'unique_partners': len(partners),
            'states': estados
        },
        'cheques': cheques_parsed
    }, f, indent=2, ensure_ascii=False)

print("\nArchivo 'cheques_limpios.json' generado con éxito.")
