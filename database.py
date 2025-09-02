# database.py
import os
import sqlite3

DATABASE_URL = os.getenv('DATABASE_URL')

def get_db():
    if DATABASE_URL:
        # PostgreSQL
        import psycopg2
        from psycopg2.extras import RealDictCursor
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    else:
        # SQLite local
        conn = sqlite3.connect('tracking.db')
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    if DATABASE_URL:
        # PostgreSQL
        conn = None
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS employees (
                    id TEXT PRIMARY KEY,
                    nom TEXT NOT NULL,
                    prenom TEXT NOT NULL,
                    type TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at BIGINT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS salaries (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT REFERENCES employees(id),
                    amount REAL NOT NULL,
                    period TEXT NOT NULL,
                    date BIGINT NOT NULL
                )
            ''')

            conn.commit()
            print("✅ Tables PostgreSQL créées")
        except Exception as e:
            print(f"❌ Erreur PostgreSQL : {e}")
        finally:
            if conn:
                conn.close()
    else:
        # SQLite
        with sqlite3.connect('tracking.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS employees (
                    id TEXT PRIMARY KEY,
                    nom TEXT NOT NULL,
                    prenom TEXT NOT NULL,
                    type TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS salaries (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    period TEXT NOT NULL,
                    date INTEGER NOT NULL,
                    FOREIGN KEY(employee_id) REFERENCES employees(id)
                )
            ''')
            conn.commit()
        print("✅ Tables SQLite créées")
