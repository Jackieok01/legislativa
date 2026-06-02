"""
Creates all tables. Safe to re-run (CREATE TABLE IF NOT EXISTS).
    python init_db.py
"""
from db import get_db

SCHEMA = """
    CREATE TABLE IF NOT EXISTS usuarios (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        username    TEXT    NOT NULL UNIQUE,
        password    TEXT    NOT NULL DEFAULT '',
        nombre      TEXT    NOT NULL,
        email       TEXT,
        google_id   TEXT    UNIQUE,
        rol         TEXT    DEFAULT 'staff' CHECK(rol IN ('admin','presidente','staff')),
        activo      INTEGER DEFAULT 1,
        created_at  TEXT    DEFAULT (datetime('now'))
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


def init():
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()
    print("Tables ready.")


if __name__ == '__main__':
    init()
