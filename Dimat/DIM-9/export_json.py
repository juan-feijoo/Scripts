import json
import zipfile
import xml.etree.ElementTree as ET

def export_clean_json():
    with zipfile.ZipFile('Precios para costos.xlsx', 'r') as z:
        shared_strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
            ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            for si in tree.findall('.//main:si', ns):
                shared_strings.append(''.join([t.text for t in si.findall('.//main:t', ns) if t.text]))
                
        target_file = 'xl/worksheets/sheet1.xml'
        ns_wb = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        sheet_tree = ET.fromstring(z.read(target_file))
        rows = sheet_tree.findall('.//main:sheetData/main:row', ns_wb)
        
        items = []
        for r_idx, row in enumerate(rows[1:], start=2):
            row_dict = {}
            for c in row.findall('main:c', ns_wb):
                r_ref = c.attrib.get('r')
                col_letter = ''.join([ch for ch in r_ref if ch.isalpha()])
                val = c.find('main:v', ns_wb)
                cell_type = c.attrib.get('t')
                cell_val = val.text if val is not None else ''
                if cell_type == 's' and cell_val != '':
                    cell_val = shared_strings[int(cell_val)]
                row_dict[col_letter] = cell_val
                
            code = row_dict.get('A', '').strip()
            name = row_dict.get('B', '').strip()
            brand = row_dict.get('C', '').strip()
            curr = row_dict.get('D', '').strip()
            try:
                p_rep = float(row_dict.get('E', 0) or 0)
            except:
                p_rep = 0.0
            tag = row_dict.get('F', '').strip()
            try:
                p_uc = float(row_dict.get('H', 0) or 0)
            except:
                p_uc = 0.0
                
            items.append({
                'code': code,
                'name': name,
                'brand': brand,
                'currency': 'ARS' if curr == 'Corriente' else 'USD',
                'price_reposicion': p_rep,
                'price_ultima_compra': p_uc,
                'tag': tag
            })

    output_path = 'precios_procesados.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"Exported {len(items)} items to {output_path}")

if __name__ == '__main__':
    export_clean_json()
