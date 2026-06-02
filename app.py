import json
import secrets
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db

app = Flask(__name__)
app.secret_key = "legislativa-secret-2025"

# ─────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Iniciá sesión para continuar', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('user_rol') not in roles:
                flash('No tenés permiso para esta sección', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated
    return decorator

@app.context_processor
def inject_user():
    if session.get('user_id'):
        return {'current_user': {
            'id':     session['user_id'],
            'nombre': session['user_nombre'],
            'rol':    session['user_rol'],
        }}
    return {'current_user': None}

# ─────────────────────────────────────────────
# LOGIN / LOGOUT
# ─────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect(url_for('index'))
    if request.method == 'POST':
        db = get_db()
        user = db.execute(
            "SELECT * FROM usuarios WHERE username=? AND activo=1",
            (request.form['username'].strip(),)
        ).fetchone()
        if user and check_password_hash(user['password'], request.form['password']):
            session['user_id']     = user['id']
            session['user_nombre'] = user['nombre']
            session['user_rol']    = user['rol']
            return redirect(url_for('index'))
        flash('Usuario o contraseña incorrectos', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ─────────────────────────────────────────────
# RECUPERAR CONTRASEÑA
# ─────────────────────────────────────────────

@app.route('/recuperar', methods=['GET', 'POST'])
def recuperar_password():
    if session.get('user_id'):
        return redirect(url_for('index'))
    found = not_found = False
    nombre = None
    if request.method == 'POST':
        db = get_db()
        user = db.execute(
            "SELECT nombre FROM usuarios WHERE username=? AND activo=1",
            (request.form['username'].strip(),)
        ).fetchone()
        if user:
            found  = True
            nombre = user['nombre']
        else:
            not_found = True
    return render_template('recuperar.html', found=found, not_found=not_found, nombre=nombre)

# ─────────────────────────────────────────────
# ADMIN — USUARIOS
# ─────────────────────────────────────────────

@app.route('/admin/usuarios')
@login_required
@role_required('admin')
def admin_usuarios():
    db = get_db()
    users = db.execute("SELECT * FROM usuarios ORDER BY rol, username").fetchall()
    return render_template('admin/usuarios.html', users=users)

@app.route('/admin/usuarios/nuevo', methods=['POST'])
@login_required
@role_required('admin')
def admin_usuario_nuevo():
    db = get_db()
    username  = request.form['username'].strip()
    password  = request.form['password'].strip()
    nombre    = request.form['nombre'].strip()
    rol       = request.form['rol']
    if len(password) < 6:
        flash('Contraseña mínimo 6 caracteres', 'danger')
    elif db.execute("SELECT id FROM usuarios WHERE username=?", (username,)).fetchone():
        flash(f'Usuario "{username}" ya existe', 'danger')
    else:
        db.execute(
            "INSERT INTO usuarios (username, password, nombre, rol) VALUES (?,?,?,?)",
            (username, generate_password_hash(password), nombre, rol)
        )
        db.commit()
        flash(f'Usuario "{username}" creado', 'success')
    return redirect(url_for('admin_usuarios'))

@app.route('/admin/usuarios/<int:id>/reset', methods=['POST'])
@login_required
@role_required('admin')
def admin_reset_password(id):
    db = get_db()
    nueva = request.form['nueva_password'].strip()
    if len(nueva) < 6:
        flash('Contraseña mínimo 6 caracteres', 'danger')
    else:
        db.execute("UPDATE usuarios SET password=? WHERE id=?",
                   (generate_password_hash(nueva), id))
        db.commit()
        flash('Contraseña actualizada', 'success')
    return redirect(url_for('admin_usuarios'))

@app.route('/admin/usuarios/<int:id>/toggle', methods=['POST'])
@login_required
@role_required('admin')
def admin_toggle_usuario(id):
    db = get_db()
    user = db.execute("SELECT activo, username FROM usuarios WHERE id=?", (id,)).fetchone()
    if user['username'] == session.get('user_nombre'):
        flash('No podés desactivar tu propio usuario', 'warning')
    else:
        nuevo = 0 if user['activo'] else 1
        db.execute("UPDATE usuarios SET activo=? WHERE id=?", (nuevo, id))
        db.commit()
        flash('Usuario ' + ('activado' if nuevo else 'desactivado'), 'success')
    return redirect(url_for('admin_usuarios'))

# ─────────────────────────────────────────────
# INDEX
# ─────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    db = get_db()
    stats = {
        'legisladores': db.execute("SELECT COUNT(*) FROM legisladores WHERE activo=1").fetchone()[0],
        'eventos':      db.execute("SELECT COUNT(*) FROM eventos").fetchone()[0],
        'proyectos':    db.execute("SELECT COUNT(*) FROM proyectos").fetchone()[0],
        'comisiones':   db.execute("SELECT COUNT(*) FROM comisiones WHERE activa=1").fetchone()[0],
    }
    eventos_recientes = db.execute("""
        SELECT e.*, c.nombre as comision_nombre
        FROM eventos e LEFT JOIN comisiones c ON c.id = e.comision_id
        ORDER BY e.fecha DESC LIMIT 5
    """).fetchall()
    return render_template('index.html', stats=stats, eventos=eventos_recientes)

# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

@app.route('/dashboard')
@login_required
@role_required('presidente', 'admin')
def dashboard():
    db = get_db()

    total_legs = db.execute("SELECT COUNT(*) FROM legisladores WHERE activo=1").fetchone()[0]
    total_proy = db.execute(
        "SELECT COUNT(*) FROM proyectos WHERE estado NOT IN ('Aprobado','Rechazado','Archivado')"
    ).fetchone()[0]

    pct_row = db.execute("""
        SELECT ROUND(SUM(CASE WHEN estado='Presente' THEN 1 ELSE 0 END)*100.0/COUNT(*),1)
        FROM asistencia
    """).fetchone()[0]
    pct_global = pct_row or 0

    eventos_mes = db.execute("""
        SELECT COUNT(*) FROM eventos
        WHERE strftime('%Y-%m', fecha) = strftime('%Y-%m', 'now')
    """).fetchone()[0]

    asistencia_rows = db.execute("""
        SELECT l.apellido || ', ' || l.nombre AS nombre,
               ROUND(SUM(CASE WHEN a.estado='Presente' THEN 1 ELSE 0 END)*100.0/COUNT(*),1) AS pct
        FROM legisladores l
        JOIN asistencia a ON a.legislador_id = l.id
        WHERE l.activo=1
        GROUP BY l.id ORDER BY pct DESC
    """).fetchall()

    proyectos_rows = db.execute(
        "SELECT estado, COUNT(*) as cnt FROM proyectos GROUP BY estado"
    ).fetchall()

    mas_ausentes = db.execute("""
        SELECT l.id,
               l.apellido || ', ' || l.nombre AS nombre,
               l.sector,
               SUM(CASE WHEN a.estado='Ausente' THEN 1 ELSE 0 END) AS ausencias,
               COUNT(*) AS total,
               ROUND(SUM(CASE WHEN a.estado='Presente' THEN 1 ELSE 0 END)*100.0/COUNT(*),1) AS pct
        FROM legisladores l
        JOIN asistencia a ON a.legislador_id = l.id
        WHERE l.activo=1
        GROUP BY l.id ORDER BY ausencias DESC LIMIT 5
    """).fetchall()

    proximos = db.execute("""
        SELECT e.*, c.nombre as comision_nombre
        FROM eventos e LEFT JOIN comisiones c ON c.id = e.comision_id
        WHERE e.estado='Programado' AND e.fecha >= datetime('now')
        ORDER BY e.fecha ASC LIMIT 5
    """).fetchall()

    proy_alta = db.execute("""
        SELECT p.*, c.nombre as comision_nombre
        FROM proyectos p LEFT JOIN comisiones c ON c.id = p.comision_id
        WHERE p.prioridad='Alta' AND p.estado NOT IN ('Aprobado','Rechazado','Archivado')
        ORDER BY p.fecha_ingreso DESC
    """).fetchall()

    return render_template('dashboard.html',
        total_legs=total_legs, total_proy=total_proy,
        pct_global=pct_global, eventos_mes=eventos_mes,
        mas_ausentes=mas_ausentes, proximos=proximos, proy_alta=proy_alta,
        asistencia_labels=json.dumps([r['nombre'] for r in asistencia_rows]),
        asistencia_values=json.dumps([r['pct'] for r in asistencia_rows]),
        proyectos_labels=json.dumps([r['estado'] for r in proyectos_rows]),
        proyectos_values=json.dumps([r['cnt'] for r in proyectos_rows]),
    )

# ─────────────────────────────────────────────
# CONFIRMAR ASISTENCIA (PÚBLICO — sin auth)
# ─────────────────────────────────────────────

@app.route('/confirmar/<token>', methods=['GET', 'POST'])
def confirmar_asistencia(token):
    db = get_db()
    evento = db.execute("SELECT * FROM eventos WHERE token=?", (token,)).fetchone()

    if not evento:
        return render_template('asistencia/confirmar.html', error="Link inválido o expirado.")
    if evento['estado'] == 'Cancelado':
        return render_template('asistencia/confirmar.html', error="Este evento fue cancelado.")

    if request.method == 'POST':
        leg_id = request.form.get('legislador_id')
        if not leg_id:
            flash('Seleccioná tu nombre', 'danger')
        else:
            db.execute("""
                INSERT INTO asistencia (legislador_id, evento_id, estado)
                VALUES (?,?,'Presente')
                ON CONFLICT(legislador_id, evento_id) DO UPDATE SET estado='Presente'
            """, (leg_id, evento['id']))
            db.commit()
            leg = db.execute("SELECT nombre, apellido FROM legisladores WHERE id=?", (leg_id,)).fetchone()
            return render_template('asistencia/confirmar.html', evento=evento,
                                   success=True, nombre=f"{leg['nombre']} {leg['apellido']}")

    legisladores = db.execute(
        "SELECT id, nombre, apellido FROM legisladores WHERE activo=1 ORDER BY apellido"
    ).fetchall()
    return render_template('asistencia/confirmar.html', evento=evento, legisladores=legisladores)

# ─────────────────────────────────────────────
# LEGISLADORES
# ─────────────────────────────────────────────

@app.route('/legisladores')
@login_required
def legisladores_lista():
    db = get_db()
    rows = db.execute("SELECT * FROM legisladores ORDER BY apellido, nombre").fetchall()
    return render_template('legisladores/lista.html', legisladores=rows)

@app.route('/legisladores/nuevo', methods=['GET', 'POST'])
@login_required
def legislador_nuevo():
    if request.method == 'POST':
        db = get_db()
        db.execute("""
            INSERT INTO legisladores (nombre, apellido, sector, email, telefono, notas, activo)
            VALUES (?,?,?,?,?,?,1)
        """, (
            request.form['nombre'].strip(),
            request.form['apellido'].strip(),
            request.form['sector'] or None,
            request.form['email'].strip() or None,
            request.form['telefono'].strip() or None,
            request.form['notas'].strip() or None,
        ))
        db.commit()
        flash('Legislador agregado correctamente', 'success')
        return redirect(url_for('legisladores_lista'))
    return render_template('legisladores/form.html', leg=None)

@app.route('/legisladores/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def legislador_editar(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("""
            UPDATE legisladores
            SET nombre=?, apellido=?, sector=?, email=?, telefono=?, notas=?, activo=?
            WHERE id=?
        """, (
            request.form['nombre'].strip(),
            request.form['apellido'].strip(),
            request.form['sector'] or None,
            request.form['email'].strip() or None,
            request.form['telefono'].strip() or None,
            request.form['notas'].strip() or None,
            1 if request.form.get('activo') else 0,
            id,
        ))
        db.commit()
        flash('Legislador actualizado', 'success')
        return redirect(url_for('legisladores_lista'))
    leg = db.execute('SELECT * FROM legisladores WHERE id=?', (id,)).fetchone()
    if not leg:
        flash('Legislador no encontrado', 'danger')
        return redirect(url_for('legisladores_lista'))
    return render_template('legisladores/form.html', leg=leg)

@app.route('/legisladores/<int:id>')
@login_required
def legislador_perfil(id):
    db = get_db()
    leg = db.execute('SELECT * FROM legisladores WHERE id=?', (id,)).fetchone()
    if not leg:
        flash('Legislador no encontrado', 'danger')
        return redirect(url_for('legisladores_lista'))
    comisiones = db.execute("""
        SELECT c.nombre, lc.rol FROM legislador_comision lc
        JOIN comisiones c ON c.id = lc.comision_id WHERE lc.legislador_id=?
    """, (id,)).fetchall()
    asistencias = db.execute("""
        SELECT e.titulo, e.fecha, e.tipo, a.estado, a.observacion
        FROM asistencia a JOIN eventos e ON e.id = a.evento_id
        WHERE a.legislador_id=? ORDER BY e.fecha DESC LIMIT 20
    """, (id,)).fetchall()
    stats = db.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN estado='Presente'    THEN 1 ELSE 0 END) as presentes,
               SUM(CASE WHEN estado='Ausente'     THEN 1 ELSE 0 END) as ausentes,
               SUM(CASE WHEN estado='Justificado' THEN 1 ELSE 0 END) as justificados
        FROM asistencia WHERE legislador_id=?
    """, (id,)).fetchone()
    return render_template('legisladores/perfil.html',
                           leg=leg, comisiones=comisiones, asistencias=asistencias, stats=stats)

# ─────────────────────────────────────────────
# COMISIONES
# ─────────────────────────────────────────────

@app.route('/comisiones')
@login_required
def comisiones_lista():
    db = get_db()
    rows = db.execute('SELECT * FROM comisiones ORDER BY nombre').fetchall()
    return render_template('comisiones/lista.html', comisiones=rows)

@app.route('/comisiones/nueva', methods=['GET', 'POST'])
@login_required
def comision_nueva():
    db = get_db()
    if request.method == 'POST':
        db.execute('INSERT INTO comisiones (nombre, tipo) VALUES (?,?)',
                   (request.form['nombre'].strip(), request.form['tipo']))
        db.commit()
        flash('Comisión creada', 'success')
        return redirect(url_for('comisiones_lista'))
    return render_template('comisiones/form.html', com=None)

@app.route('/comisiones/<int:id>')
@login_required
def comision_detalle(id):
    db = get_db()
    com = db.execute('SELECT * FROM comisiones WHERE id=?', (id,)).fetchone()
    miembros = db.execute("""
        SELECT l.id, l.nombre, l.apellido, lc.rol
        FROM legislador_comision lc JOIN legisladores l ON l.id = lc.legislador_id
        WHERE lc.comision_id=? ORDER BY lc.rol, l.apellido
    """, (id,)).fetchall()
    disponibles = db.execute("""
        SELECT id, nombre, apellido FROM legisladores
        WHERE activo=1 AND id NOT IN (
            SELECT legislador_id FROM legislador_comision WHERE comision_id=?
        ) ORDER BY apellido
    """, (id,)).fetchall()
    return render_template('comisiones/detalle.html', com=com, miembros=miembros, disponibles=disponibles)

@app.route('/comisiones/<int:id>/agregar_miembro', methods=['POST'])
@login_required
def comision_agregar_miembro(id):
    db = get_db()
    db.execute("""
        INSERT OR IGNORE INTO legislador_comision (legislador_id, comision_id, rol)
        VALUES (?,?,?)
    """, (request.form['legislador_id'], id, request.form['rol']))
    db.commit()
    flash('Miembro agregado', 'success')
    return redirect(url_for('comision_detalle', id=id))

@app.route('/comisiones/<int:com_id>/quitar_miembro/<int:leg_id>', methods=['POST'])
@login_required
def comision_quitar_miembro(com_id, leg_id):
    db = get_db()
    db.execute('DELETE FROM legislador_comision WHERE comision_id=? AND legislador_id=?', (com_id, leg_id))
    db.commit()
    flash('Miembro removido', 'success')
    return redirect(url_for('comision_detalle', id=com_id))

# ─────────────────────────────────────────────
# EVENTOS
# ─────────────────────────────────────────────

@app.route('/eventos')
@login_required
def eventos_lista():
    db = get_db()
    rows = db.execute("""
        SELECT e.*, c.nombre as comision_nombre
        FROM eventos e LEFT JOIN comisiones c ON c.id = e.comision_id
        ORDER BY e.fecha DESC
    """).fetchall()
    legisladores = db.execute(
        "SELECT id, nombre, apellido FROM legisladores WHERE activo=1 ORDER BY apellido"
    ).fetchall()
    return render_template('eventos/lista.html', eventos=rows, legisladores=legisladores)

@app.route('/api/eventos/<int:id>/confirmar', methods=['POST'])
@login_required
def api_confirmar_asistencia(id):
    data   = request.get_json()
    leg_id = data.get('legislador_id')
    db     = get_db()
    evento = db.execute("SELECT id FROM eventos WHERE id=? AND estado != 'Cancelado'", (id,)).fetchone()
    if not evento:
        return jsonify({'ok': False, 'error': 'Evento no encontrado o cancelado'})
    leg = db.execute("SELECT nombre, apellido FROM legisladores WHERE id=?", (leg_id,)).fetchone()
    if not leg:
        return jsonify({'ok': False, 'error': 'Legislador no encontrado'})
    db.execute("""
        INSERT INTO asistencia (legislador_id, evento_id, estado)
        VALUES (?,?,'Presente')
        ON CONFLICT(legislador_id, evento_id) DO UPDATE SET estado='Presente'
    """, (leg_id, id))
    db.commit()
    return jsonify({'ok': True, 'nombre': f"{leg['nombre']} {leg['apellido']}"})

@app.route('/eventos/nuevo', methods=['GET', 'POST'])
@login_required
def evento_nuevo():
    db = get_db()
    if request.method == 'POST':
        db.execute("""
            INSERT INTO eventos (titulo, tipo, fecha, comision_id, agenda, estado, token)
            VALUES (?,?,?,?,?,?,?)
        """, (
            request.form['titulo'].strip(),
            request.form['tipo'],
            request.form['fecha'],
            request.form['comision_id'] or None,
            request.form['agenda'].strip() or None,
            request.form['estado'],
            secrets.token_urlsafe(12),
        ))
        db.commit()
        flash('Evento creado', 'success')
        return redirect(url_for('eventos_lista'))
    comisiones = db.execute('SELECT * FROM comisiones WHERE activa=1 ORDER BY nombre').fetchall()
    return render_template('eventos/form.html', comisiones=comisiones)

# ─────────────────────────────────────────────
# ASISTENCIA BULK
# ─────────────────────────────────────────────

@app.route('/eventos/<int:id>/asistencia', methods=['GET', 'POST'])
@login_required
def asistencia_bulk(id):
    db = get_db()
    evento = db.execute('SELECT * FROM eventos WHERE id=?', (id,)).fetchone()
    if not evento:
        flash('Evento no encontrado', 'danger')
        return redirect(url_for('eventos_lista'))

    if request.method == 'POST':
        for leg in db.execute('SELECT id FROM legisladores WHERE activo=1').fetchall():
            db.execute("""
                INSERT INTO asistencia (legislador_id, evento_id, estado, observacion)
                VALUES (?,?,?,?)
                ON CONFLICT(legislador_id, evento_id)
                DO UPDATE SET estado=excluded.estado, observacion=excluded.observacion
            """, (leg['id'], id,
                  request.form.get(f"estado_{leg['id']}", 'Ausente'),
                  request.form.get(f"obs_{leg['id']}", '').strip()))
        db.execute('UPDATE eventos SET asistencia_cargada=1 WHERE id=?', (id,))
        db.commit()
        flash('Asistencia guardada correctamente', 'success')
        return redirect(url_for('eventos_lista'))

    legisladores = db.execute("""
        SELECT l.id, l.nombre, l.apellido,
               COALESCE(a.estado,'Presente') as estado_actual, a.observacion
        FROM legisladores l
        LEFT JOIN asistencia a ON a.legislador_id=l.id AND a.evento_id=?
        WHERE l.activo=1 ORDER BY l.apellido, l.nombre
    """, (id,)).fetchall()

    confirm_url = None
    if evento['token']:
        confirm_url = f"{request.host_url.rstrip('/')}/confirmar/{evento['token']}"

    return render_template('asistencia/bulk.html',
                           evento=evento, legisladores=legisladores, confirm_url=confirm_url)

# ─────────────────────────────────────────────
# PROYECTOS
# ─────────────────────────────────────────────

@app.route('/proyectos')
@login_required
def proyectos_lista():
    db = get_db()
    rows = db.execute("""
        SELECT p.*, c.nombre as comision_nombre
        FROM proyectos p LEFT JOIN comisiones c ON c.id = p.comision_id
        ORDER BY p.fecha_ingreso DESC
    """).fetchall()
    return render_template('proyectos/lista.html', proyectos=rows)

@app.route('/proyectos/nuevo', methods=['GET', 'POST'])
@login_required
def proyecto_nuevo():
    db = get_db()
    if request.method == 'POST':
        cur = db.execute("""
            INSERT INTO proyectos (titulo, numero_expediente, comision_id, estado, prioridad, descripcion, fecha_ingreso)
            VALUES (?,?,?,?,?,?,?)
        """, (
            request.form['titulo'].strip(),
            request.form['numero_expediente'].strip() or None,
            request.form['comision_id'] or None,
            request.form['estado'],
            request.form['prioridad'],
            request.form['descripcion'].strip() or None,
            request.form['fecha_ingreso'] or None,
        ))
        for leg_id in request.form.getlist('autores'):
            db.execute('INSERT OR IGNORE INTO proyecto_autores (proyecto_id, legislador_id) VALUES (?,?)',
                       (cur.lastrowid, leg_id))
        db.commit()
        flash('Proyecto creado', 'success')
        return redirect(url_for('proyectos_lista'))
    comisiones   = db.execute('SELECT * FROM comisiones WHERE activa=1 ORDER BY nombre').fetchall()
    legisladores = db.execute('SELECT * FROM legisladores WHERE activo=1 ORDER BY apellido').fetchall()
    return render_template('proyectos/form.html', comisiones=comisiones, legisladores=legisladores, proy=None)

@app.route('/proyectos/<int:id>/estado', methods=['POST'])
@login_required
def proyecto_estado(id):
    db = get_db()
    db.execute('UPDATE proyectos SET estado=? WHERE id=?', (request.form['estado'], id))
    db.commit()
    flash('Estado actualizado', 'success')
    return redirect(url_for('proyectos_lista'))

@app.route('/proyectos/kanban')
@login_required
def proyectos_kanban():
    db = get_db()
    proyectos = db.execute("""
        SELECT p.*, c.nombre as comision_nombre
        FROM proyectos p LEFT JOIN comisiones c ON c.id = p.comision_id
        ORDER BY
            CASE p.prioridad WHEN 'Alta' THEN 1 WHEN 'Media' THEN 2 ELSE 3 END,
            p.fecha_ingreso DESC
    """).fetchall()
    columns = [
        {'estado': 'Borrador',     'nombre': 'Borrador',     'color': '#6c757d'},
        {'estado': 'En Comision',  'nombre': 'En Comisión',  'color': '#0dcaf0'},
        {'estado': 'Con Dictamen', 'nombre': 'Con Dictamen', 'color': '#0d6efd'},
        {'estado': 'En Plenario',  'nombre': 'En Plenario',  'color': '#ffc107'},
        {'estado': 'Aprobado',     'nombre': 'Aprobado',     'color': '#198754'},
        {'estado': 'Rechazado',    'nombre': 'Rechazado',    'color': '#dc3545'},
    ]
    counts = {}
    for p in proyectos:
        counts[p['estado']] = counts.get(p['estado'], 0) + 1
    for col in columns:
        col['count'] = counts.get(col['estado'], 0)
    return render_template('proyectos/kanban.html', proyectos=proyectos, columns=columns)

# API para drag-and-drop kanban
@app.route('/api/proyectos/<int:id>/estado', methods=['POST'])
@login_required
def api_proyecto_estado(id):
    data = request.get_json()
    db = get_db()
    db.execute('UPDATE proyectos SET estado=? WHERE id=?', (data['estado'], id))
    db.commit()
    return jsonify({'ok': True})

# ─────────────────────────────────────────────
# REPORTES
# ─────────────────────────────────────────────

@app.route('/reportes/asistencia')
@login_required
def reporte_asistencia():
    db = get_db()
    rows = db.execute("""
        SELECT l.id,
               l.apellido || ', ' || l.nombre AS legislador,
               l.sector,
               SUM(CASE WHEN a.estado='Presente'    THEN 1 ELSE 0 END) AS presencias,
               SUM(CASE WHEN a.estado='Ausente'     THEN 1 ELSE 0 END) AS ausencias,
               SUM(CASE WHEN a.estado='Justificado' THEN 1 ELSE 0 END) AS justificados,
               COUNT(*) AS total,
               ROUND(SUM(CASE WHEN a.estado='Presente' THEN 1 ELSE 0 END)*100.0/COUNT(*),1) AS pct
        FROM legisladores l JOIN asistencia a ON a.legislador_id=l.id
        GROUP BY l.id ORDER BY pct DESC
    """).fetchall()
    return render_template('reportes/asistencia.html', rows=rows)

if __name__ == '__main__':
    app.run(debug=True)
