import os
import re

DATABASE_URL = os.environ.get('DATABASE_URL')

# ── SQLite → PostgreSQL SQL translations ──────────────────────────────────────
_TRANSLATIONS = [
    # Schema DDL
    (re.compile(r'\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b', re.I), 'SERIAL PRIMARY KEY'),
    (re.compile(r"DEFAULT\s+\(datetime\('now'\)\)",               re.I), "DEFAULT NOW()"),
    (re.compile(r"DEFAULT\s+\(date\('now'\)\)",                   re.I), "DEFAULT CURRENT_DATE"),
    # DML date functions
    (re.compile(r"datetime\('now'\)",                             re.I), "to_char(NOW(),'YYYY-MM-DD HH24:MI:SS')"),
    (re.compile(r"date\('now'\)",                                 re.I), "to_char(NOW(),'YYYY-MM-DD')"),
    (re.compile(r"strftime\('%Y-%m',\s*'now'\)",                  re.I), "to_char(NOW(),'YYYY-MM')"),
    (re.compile(r"strftime\('%Y-%m',\s*(\w+)\)",                  re.I), r"to_char(\1::timestamp,'YYYY-MM')"),
]

_INSERT_OR_IGNORE_RE = re.compile(r'\bINSERT\s+OR\s+IGNORE\b', re.I)
_INSERT_RE           = re.compile(r'^\s*INSERT\b', re.I)


def _translate(sql):
    for pattern, repl in _TRANSLATIONS:
        sql = pattern.sub(repl, sql)
    # INSERT OR IGNORE → INSERT (ON CONFLICT clause added in execute())
    sql = _INSERT_OR_IGNORE_RE.sub('INSERT', sql)
    sql = sql.replace('?', '%s')
    return sql


if DATABASE_URL:
    import psycopg2
    import psycopg2.extras

    class _Cur:
        def __init__(self, raw):
            self._raw = raw
            self.lastrowid = None

        def execute(self, sql, params=()):
            is_ignore = bool(_INSERT_OR_IGNORE_RE.search(sql))
            t = _translate(sql)
            is_insert = bool(_INSERT_RE.match(t))
            if is_insert and 'RETURNING' not in t.upper():
                suffix = ' ON CONFLICT DO NOTHING RETURNING id' if is_ignore else ' RETURNING id'
                t = t.rstrip().rstrip(';') + suffix
            self._raw.execute(t, params or ())
            if is_insert:
                row = self._raw.fetchone()
                self.lastrowid = row[0] if row else None
            return self

        def fetchone(self):
            return self._raw.fetchone()

        def fetchall(self):
            return self._raw.fetchall()

    class _Conn:
        def __init__(self):
            url = DATABASE_URL
            if url.startswith('postgres://'):
                url = url.replace('postgres://', 'postgresql://', 1)
            self._pg = psycopg2.connect(url, cursor_factory=psycopg2.extras.DictCursor)

        def execute(self, sql, params=()):
            cur = _Cur(self._pg.cursor())
            return cur.execute(sql, params)

        def executescript(self, sql):
            self._pg.autocommit = True
            cur = self._pg.cursor()
            for stmt in sql.split(';'):
                s = _translate(stmt.strip())
                if s:
                    try:
                        cur.execute(s)
                    except Exception as e:
                        print(f"[executescript] {e}")
            self._pg.autocommit = False

        def commit(self):
            self._pg.commit()

        def close(self):
            self._pg.close()

    def get_db():
        return _Conn()

    DB_PATH = None

else:
    import sqlite3

    DB_PATH = os.path.join(os.path.dirname(__file__), 'legislativa.db')

    def get_db():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn
