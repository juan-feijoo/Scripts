# -*- coding: utf-8 -*-
# ==============================================================================
# SCRIPT DE MIGRACIÓN Y CARGA DE FLOTA Y MAQUINARIA - ODOO 19.0+e (ENTERPRISE)
# Base de Datos: outsource-argentina-beton-produccion-38993232
# Entorno: Odoo.sh / Standalone Shell (odoo-bin shell)
# ==============================================================================
"""
Instrucciones de uso en Odoo.sh:
1. Subir este archivo al servidor (ej. /tmp/import_fleet.py)
2. Ejecutar mediante tubería a la shell de Odoo:
   python3 odoo-bin shell -d $ODOO_STAGE --no-http < /tmp/import_fleet.py

O bien dentro de una sesión interactiva de odoo-bin shell:
   exec(open('import_fleet.py').read())
"""

import logging

_logger = logging.getLogger("fleet_import")

# ------------------------------------------------------------------------------
# PARÁMETROS DE EJECUCIÓN
# ------------------------------------------------------------------------------
# DRY_RUN = True  -> Simulación: recorre, valida y hace ROLLBACK (no impacta la BD)
# DRY_RUN = False -> Producción: crea los registros y ejecuta env.cr.commit()
DRY_RUN = False

# ------------------------------------------------------------------------------
# DATASET NORMALIZADO Y CONSOLIDADO (88 ACTIVOS: VEHÍCULOS + MAQUINARIA + EQUIPOS)
# ------------------------------------------------------------------------------
RAW_DATA = [   {   'brand': 'Fiat',
        'category': 'AUTO',
        'chassis': '',
        'detail': '',
        'model': '500',
        'motor': '',
        'plate': 'PEV293',
        'unit': 'km',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Fiat',
        'category': 'AUTO',
        'chassis': '',
        'detail': '',
        'model': '600',
        'motor': '',
        'plate': 'XMH424',
        'unit': 'km',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Fiat',
        'category': 'AUTO',
        'chassis': '',
        'detail': '',
        'model': 'Duna',
        'motor': '',
        'plate': 'BXA341',
        'unit': 'km',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Fiat',
        'category': 'AUTO',
        'chassis': '',
        'detail': 'Fire',
        'model': 'Palio',
        'motor': '',
        'plate': 'JCI617',
        'unit': 'km',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Fiat',
        'category': 'AUTO',
        'chassis': '',
        'detail': 'Fire 1.3 MPI 8V sedán 5 ptas',
        'model': 'Uno',
        'motor': '178E80117708208',
        'plate': 'GOY890',
        'unit': 'km',
        'vtype': 'car',
        'year': '2007'},
    {   'brand': 'Ford',
        'category': 'AUTO',
        'chassis': '',
        'detail': '',
        'model': 'Focus',
        'motor': '',
        'plate': 'AA468WR',
        'unit': 'km',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'IKA-Renault',
        'category': 'AUTO',
        'chassis': '',
        'detail': '',
        'model': 'Torino',
        'motor': '',
        'plate': 'VPU084',
        'unit': 'km',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Peugeot',
        'category': 'AUTO',
        'chassis': '',
        'detail': '',
        'model': '306',
        'motor': '',
        'plate': 'CAP006',
        'unit': 'km',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Volkswagen',
        'category': 'AUTO',
        'chassis': '',
        'detail': '',
        'model': 'Fox',
        'motor': '',
        'plate': 'OVP969',
        'unit': 'km',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Volkswagen',
        'category': 'AUTO',
        'chassis': '',
        'detail': '',
        'model': 'Gol Trend',
        'motor': '',
        'plate': 'AB690PR',
        'unit': 'km',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Volkswagen',
        'category': 'AUTO',
        'chassis': '',
        'detail': '',
        'model': 'Gol Trend',
        'motor': '',
        'plate': 'AD607MM',
        'unit': 'km',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Volkswagen',
        'category': 'AUTO',
        'chassis': '',
        'detail': '',
        'model': 'Gol Trend',
        'motor': '',
        'plate': 'IYQ813',
        'unit': 'km',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Volkswagen',
        'category': 'AUTO',
        'chassis': '',
        'detail': '',
        'model': 'Suran',
        'motor': '',
        'plate': 'MQZ088',
        'unit': 'km',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Volkswagen',
        'category': 'AUTO',
        'chassis': '',
        'detail': '',
        'model': 'Up',
        'motor': '',
        'plate': 'AD074EW',
        'unit': 'km',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Ford',
        'category': 'CAMIONETA',
        'chassis': '',
        'detail': '',
        'model': 'Territory',
        'motor': '',
        'plate': 'AG458LI',
        'unit': 'km',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Toyota',
        'category': 'CAMIONETA',
        'chassis': '',
        'detail': '',
        'model': 'Hilux SW4',
        'motor': '',
        'plate': 'AH124TG',
        'unit': 'km',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Fiat',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'Adventure 1.6',
        'model': 'Strada',
        'motor': '178F40552182610',
        'plate': 'LAD887',
        'unit': 'km',
        'vtype': 'car',
        'year': '2012'},
    {   'brand': 'Ford',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'Raptor',
        'model': 'F-150',
        'motor': '',
        'plate': 'AE461MO',
        'unit': 'km',
        'vtype': 'car',
        'year': '2020'},
    {   'brand': 'Ford',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'XLT Diesel 4x2 DC',
        'model': 'Ranger',
        'motor': 'SA2Q HJ451491',
        'plate': 'AA876HD',
        'unit': 'km',
        'vtype': 'car',
        'year': '2017'},
    {   'brand': 'Ford',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'XL 2.2 D 4x4 DC',
        'model': 'Ranger',
        'motor': 'QW2PHJ008395',
        'plate': 'AC739PS',
        'unit': 'km',
        'vtype': 'car',
        'year': '2018'},
    {   'brand': 'Ford',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'XL 2.2 D 4x4 DC',
        'model': 'Ranger',
        'motor': 'QW2PHJ008400',
        'plate': 'AC739PT',
        'unit': 'km',
        'vtype': 'car',
        'year': '2018'},
    {   'brand': 'Ford',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'XLT 3.2 D AT 4x4 DC',
        'model': 'Ranger',
        'motor': 'SA2SKJ111976',
        'plate': 'AD213ME',
        'unit': 'km',
        'vtype': 'car',
        'year': '2018'},
    {   'brand': 'Ford',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'XL 2.2 D 4x4 DC',
        'model': 'Ranger',
        'motor': 'QJ2RKJ097858',
        'plate': 'AD213MF',
        'unit': 'km',
        'vtype': 'car',
        'year': '2018'},
    {   'brand': 'Ford',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'XLT 3.2 D AT 4x4 DC',
        'model': 'Ranger',
        'motor': 'SA2SKJ118499',
        'plate': 'AD213MG',
        'unit': 'km',
        'vtype': 'car',
        'year': '2018'},
    {   'brand': 'Ford',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'XLT 3.2 D AT 4x4 DC',
        'model': 'Ranger',
        'motor': 'SA2SKJ111978',
        'plate': 'AD213MH',
        'unit': 'km',
        'vtype': 'car',
        'year': '2018'},
    {   'brand': 'Ford',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'XL 2.2 D 4x4 DC',
        'model': 'Ranger',
        'motor': 'QJ2RKJ101205',
        'plate': 'AD213MI',
        'unit': 'km',
        'vtype': 'car',
        'year': '2018'},
    {   'brand': 'Ford',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'XL 2.2 D 4x4 DC',
        'model': 'Ranger',
        'motor': 'QJ2R KJ088517',
        'plate': 'AD407UK',
        'unit': 'km',
        'vtype': 'car',
        'year': '2019'},
    {   'brand': 'Ford',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'XL 2.2 D 4x4 DC',
        'model': 'Ranger',
        'motor': 'QJ2R JJ074214',
        'plate': 'AD407UL',
        'unit': 'km',
        'vtype': 'car',
        'year': '2019'},
    {   'brand': 'Ford',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'DC',
        'model': 'Ranger',
        'motor': '',
        'plate': 'AG215OE',
        'unit': 'km',
        'vtype': 'car',
        'year': '2023'},
    {   'brand': 'Ford',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'XL 2.2 D 4x4 DC',
        'model': 'Ranger',
        'motor': 'QJ2S PJ343470',
        'plate': 'AG225QX',
        'unit': 'km',
        'vtype': 'car',
        'year': '2023'},
    {   'brand': 'Ford',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'XLT 3.0 D 4x2 CS',
        'model': 'Ranger',
        'motor': 'C34262538',
        'plate': 'HNA991',
        'unit': 'km',
        'vtype': 'car',
        'year': '2008'},
    {   'brand': 'Ford',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'XLT 3.0 D 4x2 CS',
        'model': 'Ranger',
        'motor': 'C35262589',
        'plate': 'HNI828',
        'unit': 'km',
        'vtype': 'car',
        'year': '2008'},
    {   'brand': 'Ford',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'Plus XLT 3.0 D 4x4 DC',
        'model': 'Ranger',
        'motor': 'C34263525',
        'plate': 'IBH238',
        'unit': 'km',
        'vtype': 'car',
        'year': '2009'},
    {   'brand': 'Ford',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'Plus XLT 3.0 D 4x4 DC',
        'model': 'Ranger',
        'motor': 'D56288513',
        'plate': 'ISF023',
        'unit': 'km',
        'vtype': 'car',
        'year': '2010'},
    {   'brand': 'Ford',
        'category': 'PICK UP',
        'chassis': '',
        'detail': 'Plus XLT 3.0 D 4x4',
        'model': 'Ranger',
        'motor': 'D56296165',
        'plate': 'IXT348',
        'unit': 'km',
        'vtype': 'car',
        'year': '2010'},
    {   'brand': 'Volkswagen',
        'category': 'PICK UP',
        'chassis': '',
        'detail': '',
        'model': 'Saveiro',
        'motor': '',
        'plate': 'OBI043',
        'unit': 'km',
        'vtype': 'car',
        'year': '2014'},
    {   'brand': 'Mercedes-Benz',
        'category': 'UTILITARIO',
        'chassis': '',
        'detail': '515 CDI chasis 4325',
        'model': 'Sprinter',
        'motor': '',
        'plate': 'AC864ZD',
        'unit': 'km',
        'vtype': 'car',
        'year': '2018'},
    {   'brand': 'Mercedes-Benz',
        'category': 'UTILITARIO',
        'chassis': '',
        'detail': '413 CDI chasis 4025',
        'model': 'Sprinter',
        'motor': '',
        'plate': 'ILH364',
        'unit': 'km',
        'vtype': 'car',
        'year': '2009'},
    {   'brand': 'Yamaha',
        'category': 'MOTO',
        'chassis': '',
        'detail': '',
        'model': 'T110',
        'motor': 'E3L6E-285291',
        'plate': 'A038GNK',
        'unit': 'km',
        'vtype': 'bike',
        'year': '2017'},
    {   'brand': 'Yamaha',
        'category': 'MOTO',
        'chassis': '',
        'detail': '125 cc',
        'model': 'YBR 125 Z',
        'motor': '',
        'plate': 'A236YAW',
        'unit': 'km',
        'vtype': 'bike',
        'year': ''},
    {   'brand': 'Iveco',
        'category': 'CAMIÓN',
        'chassis': '',
        'detail': 'Chasis c/cabina',
        'model': 'TECTOR 170',
        'motor': '',
        'plate': 'AC703FG',
        'unit': 'km',
        'vtype': 'car',
        'year': '2018'},
    {   'brand': 'Iveco',
        'category': 'CAMIÓN',
        'chassis': '',
        'detail': 'Chasis c/cabina',
        'model': 'CAVALLINO 320',
        'motor': '',
        'plate': 'JXX177',
        'unit': 'km',
        'vtype': 'car',
        'year': '2011'},
    {   'brand': 'Iveco',
        'category': 'CAMIÓN',
        'chassis': '',
        'detail': 'Chasis c/cabina',
        'model': 'CURSOR 330',
        'motor': 'IVECO003839',
        'plate': 'DJQ598',
        'unit': 'km',
        'vtype': 'car',
        'year': '2000'},
    {   'brand': 'Iveco',
        'category': 'CAMIÓN',
        'chassis': '',
        'detail': 'Chasis c/cabina',
        'model': '260 E 25',
        'motor': '',
        'plate': 'KFM236',
        'unit': 'km',
        'vtype': 'car',
        'year': '2011'},
    {   'brand': 'Mercedes-Benz',
        'category': 'CAMIÓN',
        'chassis': '',
        'detail': 'Chasis c/cabina — 180 HP',
        'model': '2318',
        'motor': '376958-10-392455',
        'plate': 'DOE429',
        'unit': 'km',
        'vtype': 'car',
        'year': '1998'},
    {   'brand': 'Mercedes-Benz',
        'category': 'CAMIÓN',
        'chassis': '',
        'detail': 'Chasis c/cabina — 180 HP',
        'model': '2318',
        'motor': '376958-10-392048',
        'plate': 'DPB100',
        'unit': 'km',
        'vtype': 'car',
        'year': '1998'},
    {   'brand': 'Mercedes-Benz',
        'category': 'CAMIÓN',
        'chassis': '9BM6966969B609649',
        'detail': 'Chasis c/cabina',
        'model': '2324',
        'motor': '',
        'plate': 'HSQ109',
        'unit': 'km',
        'vtype': 'car',
        'year': '2008'},
    {   'brand': 'Mercedes-Benz',
        'category': 'CAMIÓN',
        'chassis': '',
        'detail': 'Chasis c/cabina dormitorio',
        'model': 'AXOR 2036',
        'motor': '457910U1015120',
        'plate': 'AB746KM',
        'unit': 'km',
        'vtype': 'car',
        'year': '2017'},
    {   'brand': 'Mercedes-Benz',
        'category': 'CAMIÓN',
        'chassis': '',
        'detail': 'Chasis c/cabina',
        'model': 'L 1624',
        'motor': '906973U0786331',
        'plate': 'HOE061',
        'unit': 'km',
        'vtype': 'car',
        'year': '2008'},
    {   'brand': 'Volvo',
        'category': 'CAMIÓN',
        'chassis': '',
        'detail': 'Chasis c/cabina',
        'model': 'VM220',
        'motor': 'Y1A035677',
        'plate': 'AB773MO',
        'unit': 'km',
        'vtype': 'car',
        'year': '2017'},
    {   'brand': 'Volvo',
        'category': 'CAMIÓN',
        'chassis': '',
        'detail': 'Chasis c/cabina dormitorio + hidrogrúa',
        'model': 'VM220',
        'motor': 'Y1A036569',
        'plate': 'AD213MU',
        'unit': 'km',
        'vtype': 'car',
        'year': '2018'},
    {   'brand': 'Volvo',
        'category': 'CAMIÓN',
        'chassis': '',
        'detail': 'Chasis c/cabina',
        'model': 'VM270',
        'motor': 'Y1A036339',
        'plate': 'AB773MP',
        'unit': 'km',
        'vtype': 'car',
        'year': '2017'},
    {   'brand': 'Volvo',
        'category': 'CAMIÓN',
        'chassis': '',
        'detail': 'Chasis c/cabina',
        'model': 'VM270',
        'motor': 'Y1A036938',
        'plate': 'AC088EK',
        'unit': 'km',
        'vtype': 'car',
        'year': '2017'},
    {   'brand': 'Volvo',
        'category': 'CAMIÓN',
        'chassis': '',
        'detail': 'Chasis c/cabina dormitorio',
        'model': 'VM270',
        'motor': 'Y1A059281',
        'plate': 'AF115QV',
        'unit': 'km',
        'vtype': 'car',
        'year': '2017'},
    {   'brand': 'Volvo',
        'category': 'CAMIÓN',
        'chassis': '',
        'detail': 'Chasis c/cabina',
        'model': 'VM270',
        'motor': 'Y1A067728',
        'plate': 'AF540IT',
        'unit': 'km',
        'vtype': 'car',
        'year': '2022'},
    {   'brand': 'Volvo',
        'category': 'CAMIÓN',
        'chassis': '',
        'detail': 'Mixer',
        'model': 'VM270',
        'motor': 'Y1A072099',
        'plate': 'AF846CL',
        'unit': 'km',
        'vtype': 'car',
        'year': '2023'},
    {   'brand': 'Comar',
        'category': 'SEMIRREMOLQUE',
        'chassis': '',
        'detail': 'Carretón',
        'model': 'S12-28',
        'motor': '',
        'plate': 'IMT681',
        'unit': 'Sin medidor',
        'vtype': 'car',
        'year': '2009'},
    {   'brand': 'Indumix',
        'category': 'SEMIRREMOLQUE',
        'chassis': '8E90209CFNX100619',
        'detail': '28.450 kg',
        'model': 'Semirremolque hormigonero',
        'motor': '',
        'plate': 'AF540IR',
        'unit': 'Sin medidor',
        'vtype': 'car',
        'year': '2022'},
    {   'brand': 'Indumix',
        'category': 'SEMIRREMOLQUE',
        'chassis': '8E90209CF8X100208',
        'detail': '10.000 kg',
        'model': 'Semirremolque motohormigonero',
        'motor': '',
        'plate': 'HMJ617',
        'unit': 'Sin medidor',
        'vtype': 'car',
        'year': '2008'},
    {   'brand': 'Navarro',
        'category': 'SEMIRREMOLQUE',
        'chassis': '',
        'detail': '3 ejes',
        'model': 'Navarro',
        'motor': '',
        'plate': 'EUY515',
        'unit': 'Sin medidor',
        'vtype': 'car',
        'year': '2004'},
    {   'brand': 'Navatuc',
        'category': 'SEMIRREMOLQUE',
        'chassis': '8A9S0803V8ANAV11',
        'detail': 'Volcador bilateral 24.000 kg (batea blanca)',
        'model': 'NT',
        'motor': '',
        'plate': 'HLS374',
        'unit': 'Sin medidor',
        'vtype': 'car',
        'year': '2008'},
    {   'brand': 'Pluscarga',
        'category': 'SEMIRREMOLQUE',
        'chassis': '',
        'detail': 'Batea azul',
        'model': 'Pluscarga',
        'motor': '',
        'plate': 'JRJ784',
        'unit': 'Sin medidor',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Milei',
        'category': 'ACOPLADO',
        'chassis': '',
        'detail': 'Tanque cisterna',
        'model': 'ACT-3',
        'motor': '',
        'plate': 'VQM289',
        'unit': 'Sin medidor',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Caterpillar',
        'category': 'EXCAVADORA',
        'chassis': '',
        'detail': '138 HP',
        'model': '320D L',
        'motor': 'GDC34379',
        'plate': 'BYZ59',
        'unit': 'Horas',
        'vtype': 'car',
        'year': '2010'},
    {   'brand': 'Caterpillar',
        'category': 'RETROEXCAVADORA',
        'chassis': '',
        'detail': '75 HP',
        'model': '416C',
        'motor': '5HK49915',
        'plate': 'CAT-416C',
        'unit': 'Horas',
        'vtype': 'car',
        'year': '1997'},
    {   'brand': 'Caterpillar',
        'category': 'RETROEXCAVADORA',
        'chassis': 'G416EKCBD03028',
        'detail': '75 HP',
        'model': '416E',
        'motor': '',
        'plate': 'BYZ57',
        'unit': 'Horas',
        'vtype': 'car',
        'year': '2008'},
    {   'brand': 'Case',
        'category': 'CARGADORA FRONTAL',
        'chassis': '',
        'detail': '2 m3 — 157 HP',
        'model': 'W20D',
        'motor': '',
        'plate': 'CASE-W20D',
        'unit': 'Horas',
        'vtype': 'car',
        'year': '1994'},
    {   'brand': 'Case',
        'category': 'CARGADORA FRONTAL',
        'chassis': '',
        'detail': 'Cargadora frontal Case W20E',
        'model': 'W20E',
        'motor': '6T590',
        'plate': 'CASE-W20E',
        'unit': 'Horas',
        'vtype': 'car',
        'year': '1996'},
    {   'brand': 'Caterpillar',
        'category': 'CARGADORA FRONTAL',
        'chassis': 'G9G04260',
        'detail': '180 HP',
        'model': '938H',
        'motor': '',
        'plate': 'CAT-938H',
        'unit': 'Horas',
        'vtype': 'car',
        'year': '2011'},
    {   'brand': 'Lonking',
        'category': 'CARGADORA FRONTAL',
        'chassis': '',
        'detail': 'Cargadora frontal Lonking CDM833',
        'model': 'CDM833',
        'motor': '',
        'plate': 'LONK-CDM833',
        'unit': 'Horas',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Avant',
        'category': 'MINICARGADORA',
        'chassis': '',
        'detail': '(+ zanjadora 900x100 mm)',
        'model': '750',
        'motor': '7HU3002',
        'plate': 'AVANT-750',
        'unit': 'Horas',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Caterpillar',
        'category': 'TOPADORA',
        'chassis': 'THX35651',
        'detail': '200 HP',
        'model': 'D6T XL',
        'motor': '',
        'plate': 'CAT-D6T',
        'unit': 'Horas',
        'vtype': 'car',
        'year': '2011'},
    {   'brand': 'John Deere',
        'category': 'MOTONIVELADORA',
        'chassis': '',
        'detail': 'Motoniveladora John Deere 770CH',
        'model': '770CH',
        'motor': '',
        'plate': 'JD-770CH',
        'unit': 'Horas',
        'vtype': 'car',
        'year': '1997'},
    {   'brand': 'XCMG',
        'category': 'MOTONIVELADORA',
        'chassis': '1607010',
        'detail': 'chasis 1607010',
        'model': 'GR180BR',
        'motor': '36467344',
        'plate': 'XCMG-GR180',
        'unit': 'Horas',
        'vtype': 'car',
        'year': '2017'},
    {   'brand': 'Lonking',
        'category': 'COMPACTADOR / RODILLO',
        'chassis': '68822',
        'detail': 'chasis 68822',
        'model': 'CDM514',
        'motor': '4587',
        'plate': 'LONK-CDM514',
        'unit': 'Horas',
        'vtype': 'car',
        'year': '2017'},
    {   'brand': 'Wacker Neuson',
        'category': 'COMPACTADOR / RODILLO',
        'chassis': '',
        'detail': 'Compactador Wacker Neuson RD12 A90',
        'model': 'RD12 A90',
        'motor': '24342067',
        'plate': 'WN-RD12',
        'unit': 'Horas',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Michigan',
        'category': 'VOLQUETE',
        'chassis': '',
        'detail': '1.600 kg — 43 HP',
        'model': 'D15GM',
        'motor': '17186427',
        'plate': 'MICH-D15GM',
        'unit': 'Horas',
        'vtype': 'car',
        'year': '2022'},
    {   'brand': 'Deutz',
        'category': 'TRACTOR',
        'chassis': '',
        'detail': 'Tractor Deutz DX120',
        'model': 'DX120',
        'motor': '',
        'plate': 'DEUTZ-DX120',
        'unit': 'Horas',
        'vtype': 'car',
        'year': '1982'},
    {   'brand': 'Valmet',
        'category': 'TRACTOR',
        'chassis': '',
        'detail': 'Tractor Valmet 1580',
        'model': '1580',
        'motor': '',
        'plate': 'VALMET-1580',
        'unit': 'Horas',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Volkswagen',
        'category': 'PICK UP',
        'chassis': '',
        'detail': '',
        'model': 'Amarok',
        'motor': '',
        'plate': 'AA223IJ',
        'unit': 'km',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'Gilera',
        'category': 'MOTO',
        'chassis': '',
        'detail': '110 cc',
        'model': 'Smash 110',
        'motor': '',
        'plate': 'A084LUW',
        'unit': 'km',
        'vtype': 'bike',
        'year': ''},
    {   'brand': 'Putzmeister',
        'category': 'BOMBA DE HORMIGÓN',
        'chassis': '',
        'detail': '',
        'model': 'Bomba Hormigón',
        'motor': '',
        'plate': 'BOMBA-PUTZ-01',
        'unit': 'Horas',
        'vtype': 'car',
        'year': '2015'},
    {   'brand': 'Putzmeister',
        'category': 'BOMBA DE HORMIGÓN',
        'chassis': '',
        'detail': 'Bomba Hormigón TK40',
        'model': 'TK40',
        'motor': '',
        'plate': 'BOMBA-TK40',
        'unit': 'Horas',
        'vtype': 'car',
        'year': '2010'},
    {   'brand': 'Schwing',
        'category': 'BOMBA DE HORMIGÓN',
        'chassis': '',
        'detail': 'Capacidad 24 m3/h',
        'model': '24/30 D',
        'motor': 'A441114',
        'plate': 'BOMBA-SCHWING',
        'unit': 'Horas',
        'vtype': 'car',
        'year': ''},
    {   'brand': 'TZR',
        'category': 'BOMBA DE HORMIGÓN',
        'chassis': '',
        'detail': '50 m3/h — 125 CV',
        'model': 'Bomba Hormigón',
        'motor': '',
        'plate': 'BOMBA-TZR',
        'unit': 'Horas',
        'vtype': 'car',
        'year': '2025'},
    {   'brand': 'Gentili',
        'category': 'ACOPLADO TANQUE',
        'chassis': '',
        'detail': 'Acoplado tanque 1.500 lts',
        'model': 'Tanque 1500L',
        'motor': '',
        'plate': 'TANQ-GENT-01',
        'unit': 'Sin medidor',
        'vtype': 'car',
        'year': '2010'},
    {   'brand': 'Gentili',
        'category': 'ACOPLADO TANQUE',
        'chassis': '',
        'detail': 'Acoplado tanque 8.000 lts',
        'model': 'G-6',
        'motor': '',
        'plate': 'TANQ-G6-01',
        'unit': 'Sin medidor',
        'vtype': 'car',
        'year': '2009'},
    {   'brand': 'Gentili',
        'category': 'ACOPLADO TANQUE',
        'chassis': '',
        'detail': 'Acoplado tanque 8.000 lts (Unidad 2)',
        'model': 'G-6',
        'motor': '',
        'plate': 'TANQ-G6-02',
        'unit': 'Sin medidor',
        'vtype': 'car',
        'year': '2009'}]


def determine_fuel_type(category, brand, model):
    cat_u = category.upper().strip()
    mod_u = model.upper().strip()

    # 1. Remolques y tanques (Sin motor ni combustible)
    if any(k in cat_u for k in ["SEMIRREMOLQUE", "ACOPLADO"]):
        return False

    # 2. Motos (Nafta / Gasoline)
    if cat_u in ["MOTO", "MOTOCICLETA"]:
        return "gasoline"

    # 3. Autos livianos particulares (Nafta / Gasoline)
    if cat_u in ["AUTO", "AUTOMOVIL", "AUTOMÓVIL"]:
        return "gasoline"

    # 4. Pick-ups y utilitarios livianos
    if cat_u in ["PICK UP", "CAMIONETA"]:
        if any(k in mod_u for k in ["SAVEIRO", "STRADA", "TERRITORY"]):
            return "gasoline"
        return "diesel"  # Ranger, Amarok, Hilux, F-150

    # 5. Todo lo demás: Camiones, Sprinter, Maquinaria vial (Cat, Case, Lonking), Bombas, Tractores
    return "diesel"


def run_fleet_import(odoo_env, dry_run=True):
    print("=" * 80)
    print("[*] INICIANDO IMPORTACIÓN DE FLOTA Y MAQUINARIA (ODOO 19+e)")
    print(f"[*] BD: {odoo_env.cr.dbname} | Modo: {'SIMULACIÓN (DRY_RUN=True)' if dry_run else 'PRODUCCIÓN (DRY_RUN=False)'}")
    print("=" * 80)

    BrandModel = odoo_env["fleet.vehicle.model.brand"]
    CategoryModel = odoo_env["fleet.vehicle.model.category"]
    VehicleModel = odoo_env["fleet.vehicle.model"]
    FleetVehicle = odoo_env["fleet.vehicle"]

    # 1. Cachés para optimizar queries
    brand_cache = {b.name.strip().upper(): b.id for b in BrandModel.search([])}
    cat_cache = {c.name.strip().upper(): c.id for c in CategoryModel.search([])}
    model_cache = {}
    for m in VehicleModel.search([]):
        model_cache[(m.brand_id.id, m.name.strip().upper())] = m.id

    # 2. Introspección de campos dinámicos en fleet.vehicle (Odoo 19)
    # Validar opciones permitidas en model_year (Selection en v19)
    year_field = FleetVehicle._fields.get("model_year")
    allowed_years = set()
    if year_field and year_field.type == "selection":
        try:
            raw_sel = year_field.selection(FleetVehicle) if callable(year_field.selection) else year_field.selection
            if raw_sel:
                for item in raw_sel:
                    if isinstance(item, (list, tuple)) and len(item) > 0:
                        allowed_years.add(str(item[0]))
                    else:
                        allowed_years.add(str(item))
            sample = sorted(list(allowed_years))[:5]
            print(f"[i] Opciones de 'model_year' detectadas: {len(allowed_years)} valores permitidos (ej: {sample}).")
        except Exception as err_sel:
            print(f"[!] Advertencia al leer selección de model_year: {err_sel}")

    # Detectar si existe campo de motor (Studio o Custom)
    motor_field_candidate = None
    for candidate in ["engine_number", "x_engine_number", "x_studio_nro_motor", "x_motor"]:
        if candidate in FleetVehicle._fields:
            motor_field_candidate = candidate
            print(f"[✓] Campo específico de motor detectado: '{candidate}'")
            break
    if not motor_field_candidate:
        print("[i] No se detectó campo específico para motor; se incluirá formateado en la descripción HTML.")

    stats = {
        "marcas_creadas": 0,
        "categorias_creadas": 0,
        "modelos_creados": 0,
        "vehiculos_creados": 0,
        "vehiculos_existentes": 0,
    }

    try:
        # Savepoint para aislamiento transaccional seguro
        with odoo_env.cr.savepoint():
            for item in RAW_DATA:
                plate = item["plate"].strip().upper()
                brand_name = item["brand"].strip()
                model_name = item["model"].strip()
                detail = item["detail"].strip()
                category_name = item["category"].strip()
                year = item["year"].strip()
                motor = item["motor"].strip()
                chassis = item["chassis"].strip()
                unit = item["unit"].strip()
                vtype = item["vtype"]

                # A. Categoría
                cat_key = category_name.upper()
                if cat_key not in cat_cache:
                    new_cat = CategoryModel.create({"name": category_name})
                    cat_cache[cat_key] = new_cat.id
                    stats["categorias_creadas"] += 1
                cat_id = cat_cache[cat_key]

                # B. Marca
                brand_key = brand_name.upper()
                if brand_key not in brand_cache:
                    new_brand = BrandModel.create({"name": brand_name})
                    brand_cache[brand_key] = new_brand.id
                    stats["marcas_creadas"] += 1
                brand_id = brand_cache[brand_key]

                # C. Modelo
                fuel_type = determine_fuel_type(category_name, brand_name, model_name)

                model_key = (brand_id, model_name.upper())
                if model_key not in model_cache:
                    model_vals = {
                        "name": model_name,
                        "brand_id": brand_id,
                        "category_id": cat_id,
                        "vehicle_type": vtype,
                    }
                    if fuel_type and "default_fuel_type" in VehicleModel._fields:
                        model_vals["default_fuel_type"] = fuel_type
                    new_model = VehicleModel.create(model_vals)
                    model_cache[model_key] = new_model.id
                    stats["modelos_creados"] += 1
                model_id = model_cache[model_key]

                # D. Validar duplicados de vehículo por patente
                existing = FleetVehicle.search([("license_plate", "=ilike", plate)], limit=1)
                if existing:
                    # Si ya existe (ej. reejecución en Staging), actualizar combustible
                    if "fuel_type" in FleetVehicle._fields and existing.fuel_type != fuel_type:
                        existing.write({"fuel_type": fuel_type})
                        print(f"[*] Actualizado combustible en existente: {plate:<14} -> {fuel_type or 'Sin combustible'}")
                        stats["vehiculos_actualizados"] = stats.get("vehiculos_actualizados", 0) + 1
                    else:
                        print(f"[-] Omitido (Ya existe): {plate} (ID: {existing.id})")
                    stats["vehiculos_existentes"] += 1
                    continue

                # E. Construcción de valores del vehículo
                vehicle_vals = {
                    "license_plate": plate,
                    "model_id": model_id,
                    "category_id": cat_id,
                    "odometer_unit": "kilometers",
                    "fuel_type": fuel_type,
                }

                if chassis:
                    vehicle_vals["vin_sn"] = chassis

                # Asignar año si es válido para la selección en v19
                if year:
                    if not allowed_years or year in allowed_years:
                        vehicle_vals["model_year"] = year

                # Asignar campo de motor si existe
                if motor_field_candidate and motor:
                    vehicle_vals[motor_field_candidate] = motor

                # Armar ficha técnica en HTML para el campo 'description'
                desc_html_parts = []
                if motor:
                    desc_html_parts.append(f"<p><strong>N° Motor:</strong> {motor}</p>")
                if chassis:
                    desc_html_parts.append(f"<p><strong>N° Chasis / VIN:</strong> {chassis}</p>")
                if year:
                    desc_html_parts.append(f"<p><strong>Año Modelo:</strong> {year}</p>")
                if detail:
                    desc_html_parts.append(f"<p><strong>Detalle / Capacidad:</strong> {detail}</p>")
                if unit and unit.lower() != "km":
                    desc_html_parts.append(f"<p><strong>Medición de Uso Original:</strong> {unit}</p>")

                if desc_html_parts:
                    vehicle_vals["description"] = "".join(desc_html_parts)

                try:
                    new_vehicle = FleetVehicle.create(vehicle_vals)
                except Exception as e_create:
                    # Fallback preventivo si model_year no está dentro del rango del Selection de Odoo 19
                    if "model_year" in vehicle_vals:
                        print(f"[!] Año '{vehicle_vals['model_year']}' no aceptado por Selection de Odoo 19 en {plate}. Reintentando con año en ficha técnica...")
                        del vehicle_vals["model_year"]
                        new_vehicle = FleetVehicle.create(vehicle_vals)
                    else:
                        raise e_create

                print(f"[+] Creado: {plate:<14} | {brand_name} {model_name:<18} | Cat: {category_name:<16} (ID: {new_vehicle.id})")
                stats["vehiculos_creados"] += 1

            if dry_run:
                print("\n[!] AVISO: DRY_RUN = True. Revirtiendo transacción (Rollback de prueba)... No se guardó ningún cambio.")
                raise Exception("DRY_RUN_ROLLBACK")

        # Confirmación definitiva en Base de Datos si no es simulación
        if not dry_run:
            odoo_env.cr.commit()
            print("\n[✓] COMMIT REALIZADO CON ÉXITO: 88 registros persistidos en PostgreSQL.")

    except Exception as e:
        if str(e) == "DRY_RUN_ROLLBACK":
            print("[✓] Simulación completada exitosamente sin errores de validación.")
        else:
            odoo_env.cr.rollback()
            print(f"[X] Error fatal durante la ejecución: {e}")
            raise e

    print("-" * 80)
    print("RESUMEN FINAL:")
    for key, val in stats.items():
        print(f" • {key.replace('_', ' ').capitalize()}: {val}")
    print("=" * 80)


# ------------------------------------------------------------------------------
# PUNTO DE ENTRADA
# ------------------------------------------------------------------------------
if "env" in globals():
    run_fleet_import(env, dry_run=DRY_RUN)
else:
    print("Este script debe ejecutarse dentro del entorno de Odoo (odoo-bin shell).")
    print("Ejemplo: python3 odoo-bin shell -d $ODOO_STAGE --no-http < import_fleet.py")
