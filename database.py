import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv('DATABASE_URL')

def get_db():
    """Ouvre une connexion à la base de données (PostgreSQL ou SQLite)."""
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            return conn
        except Exception as e:
            print(f"❌ Échec connexion PostgreSQL: {e}")
            raise
    else:
        conn = sqlite3.connect('tracking.db')
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    """Initialise les tables de la base de données."""
    if DATABASE_URL:
        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()

            # Table employees
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

            # Table salaries
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS salaries (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT REFERENCES employees(id),
                    employee_name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    hours_worked REAL,
                    period TEXT NOT NULL,
                    date BIGINT NOT NULL,
                    is_synced INTEGER DEFAULT 0
                )
            ''')

            # Table pointages
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pointages (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT REFERENCES employees(id),
                    employee_name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    timestamp BIGINT NOT NULL,
                    date TEXT NOT NULL,
                    is_synced INTEGER DEFAULT 0
                )
            ''')

            conn.commit()
            print("✅ Tables PostgreSQL créées ou mises à jour")
        except Exception as e:
            print(f"❌ Erreur init_db PostgreSQL: {e}")
            raise
        finally:
            if conn:
                conn.close()
    else:
        try:
            with sqlite3.connect('tracking.db') as conn:
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
                        employee_id TEXT NOT NULL,
                        employee_name TEXT NOT NULL,
                        type TEXT NOT NULL,
                        amount REAL NOT NULL,
                        hours_worked REAL,
                        period TEXT NOT NULL,
                        date BIGINT NOT NULL,
                        is_synced INTEGER DEFAULT 0,
                        FOREIGN KEY(employee_id) REFERENCES employees(id)
                    )
                ''')

                conn.commit()
                print("✅ Tables SQLite créées")
        except Exception as e:
            print(f"❌ Erreur init_db SQLite: {e}")
            raise

def verify_schema():
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Vérifie les colonnes de la table users
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users';
        """)
        columns = [row[0] if isinstance(row, tuple) else row["column_name"] for row in cursor.fetchall()]

        expected = ["id", "name", "email", "salary"]
        missing = [col for col in expected if col not in columns]

        if missing:
            logger.error(f"❌ Colonnes manquantes dans users: {missing}")
        else:
            logger.info("✅ Schéma users vérifié")

        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"❌ Erreur vérification schéma: {e}")
        raise
    finally:
        conn.close()
