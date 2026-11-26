# -*- coding: utf-8 -*-
# 03 - Relevamiento del motor Studio Approvals (código real del build) y reglas actuales
import inspect

h('03 - STUDIO APPROVALS: REGLAS, HISTORIAL Y CÓDIGO DEL MOTOR')

if 'studio.approval.rule' not in env:
    print('!! El modelo studio.approval.rule NO existe (¿web_studio instalado?)')
else:
    Rule = env['studio.approval.rule'].with_context(active_test=False)

    sub('Campos de studio.approval.rule')
    for fname, field in sorted(Rule._fields.items()):
        if not field.automatic and not fname.startswith(('message_', 'website_message', 'activity_')):
            print('  %-28s | %-12s | store=%-5s | %s' % (fname, field.type, field.store, field.string))
            if field.help:
                print('      help: %s' % field.help.replace('\n', ' '))

    sub('Todas las reglas studio.approval.rule en la base (activas e inactivas)')
    rules = Rule.search([], order='id')
    if not rules:
        print('  (Sin reglas registradas)')
    for r in rules:
        xmlid = r.get_external_id().get(r.id, '-')
        print('\n  REGLA id=%s | active=%s | xmlid=%s | name=%s' % (r.id, r.active, xmlid, r.name))
        dump(
            r,
            names=[
                'name', 'active', 'model_id', 'model_name', 'method', 'action_id',
                'approval_group_id', 'approver_ids', 'users_to_notify',
                'notification_order', 'exclusive_user', 'domain', 'message',
                'conditional', 'can_validate',
            ],
            full=['domain', 'message'],
        )
        if r.approval_group_id:
            print('  %-45s %s' % ('approval_group_id.users', r.approval_group_id.users.mapped('login')))

    sub('Últimas 20 entradas (studio.approval.entry)')
    if 'studio.approval.entry' in env:
        entries = env['studio.approval.entry'].search([], order='id desc', limit=20)
        if not entries:
            print('  (Sin studio.approval.entry)')
        for e in entries:
            print(
                '  id=%-5s | rule=%-35s | model=%-15s res_id=%-5s | user=%-32s | approved=%-5s | date=%s'
                % (
                    e.id,
                    (e.rule_id.name or '-')[:35],
                    e.model if has_field('studio.approval.entry', 'model') else '-',
                    e.res_id,
                    e.user_id.login if e.user_id else '-',
                    e.approved,
                    e.create_date,
                )
            )

    sub('Últimas 20 solicitudes (studio.approval.request)')
    if 'studio.approval.request' in env:
        reqs = env['studio.approval.request'].search([], order='id desc', limit=20)
        if not reqs:
            print('  (Sin studio.approval.request)')
        for q in reqs:
            act = q.mail_activity_id if has_field('studio.approval.request', 'mail_activity_id') else None
            print(
                '  id=%-5s | rule=%-35s | res_id=%-5s | act_id=%-5s | act_user=%-32s | date=%s'
                % (
                    q.id,
                    (q.rule_id.name or '-')[:35],
                    q.res_id,
                    act.id if act else 0,
                    act.user_id.login if act and act.user_id else '-',
                    q.create_date,
                )
            )

    sub('Código fuente de studio.approval.rule en este build (notificaciones, menciones y actividades)')
    cls = type(Rule)
    methods_to_inspect = [
        '_compute_can_validate',
        'check_approval',
        '_check_approval',
        '_create_request',
        '_get_approval_spec',
        'get_approval_spec',
        'set_approval',
        '_set_approval',
        '_notify_approval',
        '_send_approval_notification',
        'delete_approval',
        '_get_rule_domain',
    ]
    for mname in methods_to_inspect:
        fn = getattr(cls, mname, None)
        if fn:
            print('\n  >>> studio.approval.rule.%s%s' % (mname, safe(inspect.signature, fn) or ''))
            src = safe(inspect.getsource, fn)
            if src:
                print(src[:4500])

    def _srcfile(obj):
        try:
            return (inspect.getsourcefile(obj) or '').replace('\\', '/')
        except Exception:
            return ''

    sub('Líneas de web_studio/models/studio_approval.py relacionadas con notificaciones / menciones / actividades')
    mod_file = None
    for k in cls.__mro__:
        p = _srcfile(k)
        if p and 'web_studio' in p:
            mod_file = p
            break
    print('  Archivo fuente: %s' % mod_file)
    if mod_file and os.path.isfile(mod_file):
        with open(mod_file, 'r', encoding='utf-8', errors='replace') as fh:
            lines = fh.readlines()
        keywords = ('users_to_notify', 'approver_ids', 'message_post', 'activity_schedule', 'partner_ids', 'mail.notification', '_notify', 'create_request', 'Grant Approval')
        for idx, line in enumerate(lines, 1):
            if any(k in line for k in keywords):
                print('  L%04d: %s' % (idx, line.rstrip()))

    if 'studio.approval.entry' in env:
        sub('Código fuente de studio.approval.entry (clases en web_studio / custom)')
        ecls = type(env['studio.approval.entry'])
        for k in ecls.__mro__:
            p = _srcfile(k)
            if 'web_studio' in p or '/src/user/' in p:
                print('\n  >>> %s (%s)' % (k.__module__, p))
                src = safe(inspect.getsource, k)
                if src:
                    print(src[:4500])

    if 'studio.approval.request' in env:
        sub('Código fuente de studio.approval.request (clases en web_studio / custom)')
        qcls = type(env['studio.approval.request'])
        for k in qcls.__mro__:
            p = _srcfile(k)
            if 'web_studio' in p or '/src/user/' in p:
                print('\n  >>> %s (%s)' % (k.__module__, p))
                src = safe(inspect.getsource, k)
                if src:
                    print(src[:4500])

    sub('Vistas heredadas de Studio / custom sobre sale.order y purchase.order')
    views = env['ir.ui.view'].with_context(active_test=False).search([
        ('model', 'in', ['sale.order', 'purchase.order']),
        '|',
        ('name', 'ilike', 'studio'),
        ('arch_db', 'ilike', 'studio_approval'),
    ])
    print('  Vistas encontradas: %s' % len(views))
    for v in views:
        print('  VIEW id=%s active=%s model=%s name=%s' % (v.id, v.active, v.model, v.name))
        dump(v, names=['arch_db'], full=['arch_db'])
