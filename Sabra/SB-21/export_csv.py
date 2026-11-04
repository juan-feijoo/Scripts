import json
import csv

with open('cheques_limpios.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

cheques = data['cheques']

with open('cheques_preparados.csv', 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f, delimiter=';')
    writer.writerow([
        'nro_cheque',
        'fecha_emision',
        'fecha_pago',
        'cuit',
        'razon_social',
        'importe',
        'estado_banco'
    ])
    for ch in cheques:
        writer.writerow([
            ch['number'],
            ch['issue_date'],
            ch['payment_date'],
            ch['cuit'],
            ch['partner_name'],
            f"{ch['amount']:.2f}",
            ch['state']
        ])

print(f"Exportados {len(cheques)} cheques a cheques_preparados.csv exitosamente.")
