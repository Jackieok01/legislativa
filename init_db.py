"""
Creates all tables and seeds sample data. Safe to re-run.
    python init_db.py
"""
import random
import secrets
from werkzeug.security import generate_password_hash
from db import get_db

random.seed(42)

SCHEMA = """
    CREATE TABLE IF NOT EXISTS usuarios (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        username        TEXT    NOT NULL UNIQUE,
        password        TEXT    NOT NULL DEFAULT '',
        nombre          TEXT    NOT NULL,
        email           TEXT,
        google_id       TEXT    UNIQUE,
        rol             TEXT    DEFAULT 'asesor' CHECK(rol IN ('admin','presidente','legislador','asesor')),
        legislador_id   INTEGER REFERENCES legisladores(id) ON DELETE SET NULL,
        activo          INTEGER DEFAULT 1,
        created_at      TEXT    DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS email_roles (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        email           TEXT    NOT NULL UNIQUE,
        rol             TEXT    NOT NULL CHECK(rol IN ('admin','presidente','legislador','asesor')),
        legislador_id   INTEGER REFERENCES legisladores(id) ON DELETE SET NULL,
        created_at      TEXT    DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS legisladores (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre          TEXT    NOT NULL,
        apellido        TEXT    NOT NULL,
        sector          TEXT    CHECK(sector IN ('Ala A','Ala B','Independiente')),
        email           TEXT,
        telefono        TEXT,
        foto_url        TEXT,
        fecha_inicio    TEXT,
        fecha_fin       TEXT,
        activo          INTEGER DEFAULT 1,
        notas           TEXT,
        created_at      TEXT    DEFAULT (datetime('now')),
        updated_at      TEXT    DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS comisiones (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre      TEXT    NOT NULL,
        tipo        TEXT    NOT NULL CHECK(tipo IN ('Permanente','Especial','Bicameral')),
        activa      INTEGER DEFAULT 1,
        created_at  TEXT    DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS legislador_comision (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        legislador_id   INTEGER NOT NULL REFERENCES legisladores(id) ON DELETE CASCADE,
        comision_id     INTEGER NOT NULL REFERENCES comisiones(id)   ON DELETE CASCADE,
        rol             TEXT    DEFAULT 'Vocal' CHECK(rol IN ('Presidente','Vicepresidente','Vocal','Suplente')),
        fecha_desde     TEXT,
        fecha_hasta     TEXT,
        UNIQUE(legislador_id, comision_id)
    );

    CREATE TABLE IF NOT EXISTS eventos (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo              TEXT    NOT NULL,
        tipo                TEXT    NOT NULL CHECK(tipo IN ('Sesion Plenaria','Reunion Comision','Reunion Bloque','Otra')),
        fecha               TEXT    NOT NULL,
        comision_id         INTEGER REFERENCES comisiones(id) ON DELETE SET NULL,
        agenda              TEXT,
        estado              TEXT    DEFAULT 'Programado' CHECK(estado IN ('Programado','Realizado','Cancelado')),
        asistencia_cargada  INTEGER DEFAULT 0,
        token               TEXT    UNIQUE,
        created_at          TEXT    DEFAULT (datetime('now')),
        updated_at          TEXT    DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS asistencia (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        legislador_id   INTEGER NOT NULL REFERENCES legisladores(id) ON DELETE CASCADE,
        evento_id       INTEGER NOT NULL REFERENCES eventos(id)      ON DELETE CASCADE,
        estado          TEXT    DEFAULT 'Ausente' CHECK(estado IN ('Presente','Ausente','Justificado','En Mision','Llego Tarde')),
        observacion     TEXT,
        created_at      TEXT    DEFAULT (datetime('now')),
        UNIQUE(legislador_id, evento_id)
    );

    CREATE TABLE IF NOT EXISTS proyectos (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo              TEXT    NOT NULL,
        numero_expediente   TEXT,
        comision_id         INTEGER REFERENCES comisiones(id) ON DELETE SET NULL,
        estado              TEXT    DEFAULT 'Borrador' CHECK(estado IN ('Borrador','En Comision','Con Dictamen','En Plenario','Aprobado','Rechazado','Archivado')),
        prioridad           TEXT    DEFAULT 'Media' CHECK(prioridad IN ('Alta','Media','Baja')),
        descripcion         TEXT,
        fecha_ingreso       TEXT    DEFAULT (date('now')),
        created_at          TEXT    DEFAULT (datetime('now')),
        updated_at          TEXT    DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS proyecto_autores (
        proyecto_id     INTEGER NOT NULL REFERENCES proyectos(id)    ON DELETE CASCADE,
        legislador_id   INTEGER NOT NULL REFERENCES legisladores(id) ON DELETE CASCADE,
        PRIMARY KEY(proyecto_id, legislador_id)
    );

    CREATE TABLE IF NOT EXISTS documentos (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo          TEXT    NOT NULL,
        tipo            TEXT,
        archivo_url     TEXT,
        evento_id       INTEGER REFERENCES eventos(id)   ON DELETE SET NULL,
        proyecto_id     INTEGER REFERENCES proyectos(id) ON DELETE SET NULL,
        resumen_ia      TEXT,
        procesado_ia    INTEGER DEFAULT 0,
        created_at      TEXT    DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_asistencia_legislador ON asistencia(legislador_id);
    CREATE INDEX IF NOT EXISTS idx_asistencia_evento     ON asistencia(evento_id);
    CREATE INDEX IF NOT EXISTS idx_eventos_fecha         ON eventos(fecha);
    CREATE INDEX IF NOT EXISTS idx_proyectos_estado      ON proyectos(estado)
"""

MIGRATIONS = [
    "ALTER TABLE usuarios ADD COLUMN email TEXT",
    "ALTER TABLE usuarios ADD COLUMN google_id TEXT",
    "ALTER TABLE usuarios ADD COLUMN legislador_id INTEGER REFERENCES legisladores(id) ON DELETE SET NULL",
]


def _safe(db, sql, params=()):
    try:
        db.execute(sql, params)
        db.commit()
    except Exception as e:
        print(f"  skip: {e}")
        try: db.rollback()
        except Exception: pass


def seed(db):
    """Insert sample data. Uses INSERT OR IGNORE — safe to re-run."""

    # ── Admin user ───────────────────────────────────────────
    _safe(db,
        "INSERT OR IGNORE INTO usuarios (username, password, nombre, email, rol) VALUES (?,?,?,?,?)",
        ('admin', generate_password_hash('admin123'), 'Administrador', 'ocampojacqueline83@gmail.com', 'admin')
    )

    # ── Legisladores ────────────────────────────────────────
    legs = [
        ('María',     'García',    'Ala A',        'mgarcia@legislatura.gov.ar'),
        ('Carlos',    'Rodríguez', 'Ala A',        'crodriguez@legislatura.gov.ar'),
        ('Ana',       'González',  'Ala A',        'agonzalez@legislatura.gov.ar'),
        ('Jorge',     'Martínez',  'Ala A',        'jmartinez@legislatura.gov.ar'),
        ('Laura',     'Sánchez',   'Ala A',        'lsanchez@legislatura.gov.ar'),
        ('Roberto',   'Pérez',     'Ala B',        'rperez@legislatura.gov.ar'),
        ('Valentina', 'López',     'Ala B',        'vlopez@legislatura.gov.ar'),
        ('Héctor',    'Díaz',      'Ala B',        'hdiaz@legislatura.gov.ar'),
        ('Claudia',   'Torres',    'Ala B',        'ctorres@legislatura.gov.ar'),
        ('Martín',    'Ramírez',   'Ala B',        'mramirez@legislatura.gov.ar'),
        ('Patricia',  'Flores',    'Independiente','pflores@legislatura.gov.ar'),
        ('Daniel',    'Herrera',   'Independiente','dherrera@legislatura.gov.ar'),
        ('Sofía',     'Morales',   'Ala A',        'smorales@legislatura.gov.ar'),
        ('Fernando',  'Castro',    'Ala B',        'fcastro@legislatura.gov.ar'),
        ('Gabriela',  'Ortiz',     'Independiente','gortiz@legislatura.gov.ar'),
    ]
    for nombre, apellido, sector, email in legs:
        _safe(db,
            "INSERT OR IGNORE INTO legisladores (nombre, apellido, sector, email, fecha_inicio, activo) VALUES (?,?,?,?,'2023-12-10',1)",
            (nombre, apellido, sector, email)
        )

    # ── Email roles ──────────────────────────────────────────
    for email, rol, leg_id in [
        ('ocampojacqueline83@gmail.com',    'admin',      None),
        ('mgarcia@legislatura.gov.ar',      'presidente', 1),
        ('crodriguez@legislatura.gov.ar',   'legislador', 2),
        ('agonzalez@legislatura.gov.ar',    'legislador', 3),
        ('jmartinez@legislatura.gov.ar',    'legislador', 4),
        ('lsanchez@legislatura.gov.ar',     'legislador', 5),
        ('rperez@legislatura.gov.ar',       'legislador', 6),
        ('vlopez@legislatura.gov.ar',       'legislador', 7),
        ('hdiaz@legislatura.gov.ar',        'legislador', 8),
        ('ctorres@legislatura.gov.ar',      'legislador', 9),
        ('mramirez@legislatura.gov.ar',     'legislador', 10),
        ('pflores@legislatura.gov.ar',      'legislador', 11),
        ('dherrera@legislatura.gov.ar',     'legislador', 12),
        ('smorales@legislatura.gov.ar',     'legislador', 13),
        ('fcastro@legislatura.gov.ar',      'legislador', 14),
        ('gortiz@legislatura.gov.ar',       'legislador', 15),
    ]:
        _safe(db,
            "INSERT OR IGNORE INTO email_roles (email, rol, legislador_id) VALUES (?,?,?)",
            (email, rol, leg_id)
        )

    # ── Comisiones ──────────────────────────────────────────
    for nombre, tipo in [
        ('Presupuesto y Hacienda', 'Permanente'),
        ('Legislación General',    'Permanente'),
        ('Salud Pública',          'Permanente'),
        ('Educación y Cultura',    'Permanente'),
    ]:
        _safe(db, "INSERT OR IGNORE INTO comisiones (nombre, tipo) VALUES (?,?)", (nombre, tipo))

    for leg_id, com_id, rol in [
        (1,1,'Presidente'),(2,1,'Vocal'),(6,1,'Vocal'),(7,1,'Vocal'),(11,1,'Vocal'),
        (3,2,'Presidente'),(4,2,'Vocal'),(8,2,'Vocal'),(9,2,'Vocal'),(12,2,'Vocal'),
        (5,3,'Presidente'),(6,3,'Vocal'),(10,3,'Vocal'),(11,3,'Vocal'),(13,3,'Vocal'),
        (4,4,'Presidente'),(7,4,'Vocal'),(9,4,'Vocal'),(12,4,'Vocal'),(14,4,'Vocal'),(15,4,'Vocal'),
    ]:
        _safe(db,
            "INSERT OR IGNORE INTO legislador_comision (legislador_id, comision_id, rol) VALUES (?,?,?)",
            (leg_id, com_id, rol)
        )

    # ── Eventos pasados ──────────────────────────────────────
    past_events = [
        ("Sesión Ordinaria N° 1/2026",                    "Sesion Plenaria",  "2026-03-05 10:00", None),
        ("Reunión de Bloque — Agenda Marzo",              "Reunion Bloque",   "2026-03-11 15:30", None),
        ("Sesión Ordinaria N° 2/2026",                    "Sesion Plenaria",  "2026-03-19 10:00", None),
        ("Reunión Comisión Presupuesto — Anteproyecto",   "Reunion Comision", "2026-03-25 14:00", 1),
        ("Sesión Ordinaria N° 3/2026",                    "Sesion Plenaria",  "2026-04-02 10:00", None),
        ("Reunión Comisión Salud — Reforma hospitalaria", "Reunion Comision", "2026-04-09 14:30", 3),
        ("Sesión Ordinaria N° 4/2026",                    "Sesion Plenaria",  "2026-04-16 10:00", None),
        ("Reunión de Bloque — Revisión legislativa",      "Reunion Bloque",   "2026-04-23 16:00", None),
        ("Reunión Comisión Legislación General",          "Reunion Comision", "2026-04-30 14:00", 2),
        ("Sesión Ordinaria N° 5/2026",                    "Sesion Plenaria",  "2026-05-07 10:00", None),
        ("Reunión Comisión Educación — Plan curricular",  "Reunion Comision", "2026-05-14 14:30", 4),
        ("Sesión Ordinaria N° 6/2026",                    "Sesion Plenaria",  "2026-05-21 10:00", None),
    ]
    past_ids = []
    for titulo, tipo, fecha, com_id in past_events:
        existing = db.execute("SELECT id FROM eventos WHERE titulo=?", (titulo,)).fetchone()
        if existing:
            past_ids.append(existing[0])
            continue
        cur = db.execute(
            "INSERT INTO eventos (titulo, tipo, fecha, comision_id, estado, asistencia_cargada, token) VALUES (?,?,?,?,'Realizado',1,?)",
            (titulo, tipo, fecha, com_id, secrets.token_urlsafe(12))
        )
        db.commit()
        past_ids.append(cur.lastrowid)

    # Próximos eventos
    for titulo, tipo, fecha, com_id in [
        ("Sesión Ordinaria N° 7/2026",                      "Sesion Plenaria",  "2026-06-04 10:00", None),
        ("Reunión de Bloque — Planificación Junio",         "Reunion Bloque",   "2026-06-11 15:00", None),
        ("Reunión Comisión Presupuesto — Presupuesto 2027", "Reunion Comision", "2026-06-18 14:00", 1),
    ]:
        _safe(db,
            "INSERT OR IGNORE INTO eventos (titulo, tipo, fecha, comision_id, estado, asistencia_cargada, token) VALUES (?,?,?,?,'Programado',0,?)",
            (titulo, tipo, fecha, com_id, secrets.token_urlsafe(12))
        )

    # ── Asistencia ──────────────────────────────────────────
    reliability = [0.97,0.95,0.93,0.90,0.92,0.88,0.85,0.87,0.68,0.72,0.65,0.60,0.42,0.38,0.50]
    for ev_id in past_ids:
        for i, rel in enumerate(reliability):
            leg_id = i + 1
            estado = 'Presente' if random.random() < rel else ('Justificado' if random.random() < 0.3 else 'Ausente')
            _safe(db,
                "INSERT OR IGNORE INTO asistencia (legislador_id, evento_id, estado) VALUES (?,?,?)",
                (leg_id, ev_id, estado)
            )

    # ── Proyectos ───────────────────────────────────────────
    projects = [
        ("Regulación del uso de IA en servicios públicos", "0142-D-2026", 2, "En Plenario",  "Alta",  "Propuesta de regulación para uso responsable de IA en servicios públicos municipales.", "2026-02-15"),
        ("Presupuesto Municipal 2027",                      "0098-D-2026", 1, "Con Dictamen", "Alta",  "Proyecto de ley de presupuesto para el ejercicio fiscal 2027.", "2026-02-10"),
        ("Reforma del sistema de salud municipal",          "0203-D-2026", 3, "En Comision",  "Alta",  "Reestructuración del sistema de atención primaria y gestión hospitalaria.", "2026-03-01"),
        ("Programa de vivienda social para jóvenes",        "0156-D-2026", None,"Borrador",   "Media", "Acceso a vivienda para menores de 30 años con ingresos medios-bajos.", "2026-03-15"),
        ("Protocolo de emergencias climáticas",             "0087-D-2026", None,"Con Dictamen","Media", "Marco normativo para gestión de emergencias por fenómenos climáticos extremos.", "2026-01-20"),
        ("Digitalización del registro civil",               "0167-D-2026", 2, "En Comision",  "Media", "Modernización del sistema de registro civil con plataforma digital unificada.", "2026-03-22"),
        ("Ordenanza de ruidos molestos — Actualización",    "0034-D-2026", 2, "Aprobado",     "Baja",  "Actualización de límites máximos de ruido en zonas residenciales.", "2026-01-10"),
        ("Subsidios para PyMEs afectadas",                  "0189-D-2026", 1, "Rechazado",    "Media", "Subsidios para pequeñas y medianas empresas afectadas por la inflación.", "2026-02-28"),
    ]
    project_authors = [[1,3,5],[1,2,6],[5,10,13],[7,14],[4,9],[3,8,12],[2,7],[6,11]]
    for i, (titulo, numero, com_id, estado, prioridad, desc, fecha) in enumerate(projects):
        existing = db.execute("SELECT id FROM proyectos WHERE numero_expediente=?", (numero,)).fetchone()
        if existing:
            continue
        cur = db.execute(
            "INSERT INTO proyectos (titulo, numero_expediente, comision_id, estado, prioridad, descripcion, fecha_ingreso) VALUES (?,?,?,?,?,?,?)",
            (titulo, numero, com_id, estado, prioridad, desc, fecha)
        )
        db.commit()
        for leg_id in project_authors[i]:
            _safe(db,
                "INSERT OR IGNORE INTO proyecto_autores (proyecto_id, legislador_id) VALUES (?,?)",
                (cur.lastrowid, leg_id)
            )

    print("Seed complete.")


def init():
    db = get_db()
    db.executescript(SCHEMA)

    for sql in MIGRATIONS:
        try:
            db.execute(sql)
            db.commit()
        except Exception:
            try: db.rollback()
            except Exception: pass

    seed(db)
    print("Tables ready.")


if __name__ == '__main__':
    init()
