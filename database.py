import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor

# === Configuration ===
DATABASE_URL = os.getenv('DATABASE_URL')


# --- Connexion DB ---
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


# --- Initialisation ---
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

            # Vérification / Ajout colonnes manquantes dans salaries
            for col_def in [
                ("employee_name", "TEXT NOT NULL DEFAULT ''"),
                ("type", "TEXT NOT NULL DEFAULT 'salaire'"),
                ("hours_worked", "REAL"),
                ("is_synced", "INTEGER DEFAULT 0"),
            ]:
                col, definition = col_def
                cursor.execute(
                    f"SELECT column_name FROM information_schema.columns "
                    f"WHERE table_name = 'salaries' AND column_name = %s",
                    (col,),
                )
                if not cursor.fetchone():
                    cursor.execute(f"ALTER TABLE salaries ADD COLUMN {col} {definition}")
                    print(f"✅ Colonne {col} ajoutée à salaries")

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
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS pointages (
                        id TEXT PRIMARY KEY,
                        employee_id TEXT NOT NULL,
                        employee_name TEXT NOT NULL,
                        type TEXT NOT NULL,
                        timestamp BIGINT NOT NULL,
                        date TEXT NOT NULL,
                        is_synced INTEGER DEFAULT 0,
                        FOREIGN KEY(employee_id) REFERENCES employees(id)
                    )
                ''')
                conn.commit()
                print("✅ Tables SQLite créées")
        except Exception as e:
            print(f"❌ Erreur init_db SQLite: {e}")
            raise


# --- Vérification du schéma ---
def verify_schema():
    """Vérifie que le schéma de la base de données est correct."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        if DATABASE_URL:  # PostgreSQL
            for col in ["employee_name", "type", "hours_worked", "is_synced"]:
                cursor.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'salaries' AND column_name = %s",
                    (col,),
                )
                if not cursor.fetchone():
                    raise Exception(f"La colonne {col} n'existe pas dans salaries")
            print("✅ Schéma PostgreSQL vérifié avec succès")
        else:  # SQLite
            cursor.execute("PRAGMA table_info(salaries)")
            columns = [col["name"] for col in cursor.fetchall()]
            for col in ["employee_name", "type", "hours_worked", "is_synced"]:
                if col not in columns:
                    raise Exception(f"La colonne {col} n'existe pas dans salaries (SQLite)")
            print("✅ Schéma SQLite vérifié avec succès")
    except Exception as e:
        print(f"❌ Erreur vérification schéma: {e}")
        raise
    finally:
        conn.close()
