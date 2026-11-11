import openpyxl

wb = openpyxl.load_workbook("Sistema Cristian 27-10 kiddie (1).xlsx", read_only=True)
ws = wb["produc_vista"]
headers = [c for c in next(ws.iter_rows(max_row=1, values_only=True))]

samples = [37303, 1051, 710, 2569, 12711]
for row in ws.iter_rows(min_row=2, values_only=True):
    d = dict(zip(headers, row))
    num = d.get("numpro")
    if num in samples:
        desc = (d.get("descri") or "").strip()[:40]
        prv = (d.get("nomprv") or "").strip()[:15]
        uc = d.get("uni_compra")
        ub = d.get("uni_bulto")
        costo = d.get("costoreal")
        print(f"numpro: {num} | desc: {desc} | prv: {prv} | uc: {uc} | ub: {ub} | costo: {costo}")
