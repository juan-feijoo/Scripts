# -*- coding: utf-8 -*-
# Helpers comunes para odoo-sh-shell-runner en Odoo.sh (env ya existe en odoo-bin shell)
import base64
import html
import inspect
import os
import re
import traceback
from collections import defaultdict, Counter

COMPANY_NAME = os.environ.get('COMPANY_NAME', '')

def h(title):
    print('\n' + '=' * 100)
    print(title)
    print('=' * 100)

def sub(title):
    print('\n--- %s %s' % (title, '-' * max(0, 94 - len(title))))

def fmt(rec, fname, max_len=None):
    field = rec._fields[fname]
    try:
        val = rec[fname]
    except Exception as e:
        return '<error leyendo: %s>' % e
    if field.type == 'binary':
        return '<binario vacío>' if not val else '<binario %s bytes>' % len(val)
    if field.type == 'many2one':
        return '%s (id=%s)' % (val.display_name, val.id) if val else False
    if field.type in ('one2many', 'many2many'):
        if not val:
            return '[]'
        items = ', '.join('%s(id=%s)' % (r.display_name, r.id) for r in val[:20])
        return '%s registros: %s%s' % (len(val), items, ' ...' if len(val) > 20 else '')
    if max_len and isinstance(val, str) and len(val) > max_len:
        return val[:max_len] + '... <truncado, %s chars>' % len(val)
    return val

def dump(rec, prefixes=None, names=None, max_len=300, full=None):
    full = full or []
    for fname in sorted(rec._fields):
        if (names and fname in names) or (prefixes and fname.startswith(tuple(prefixes))):
            print('  %-45s %s' % (fname, fmt(rec, fname, None if fname in full else max_len)))

def strip_html(s):
    return html.unescape(re.sub(r'<[^>]+>', ' ', s or '')).strip()

def get_company(name=None):
    name = name or COMPANY_NAME
    companies = env['res.company'].search([('name', 'ilike', name)]) if name else env.company
    if not companies:
        print('!! No se encontró compañía ilike %r' % name)
        return env['res.company']
    if len(companies) > 1:
        print('!! Varias compañías coinciden, uso la primera: %s' % companies.mapped('name'))
    return companies[0]

def safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        print('  !! ERROR:')
        print('  ' + traceback.format_exc().replace('\n', '\n  '))
        return None

def has_field(model, fname):
    return fname in env[model]._fields
