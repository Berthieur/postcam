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

            # Vérifier et ajouter employee_name si nécessaire
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'salaries' AND column_name = 'employee_name'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE salaries ADD COLUMN employee_name TEXT NOT NULL DEFAULT ''")
                print("✅ Colonne employee_name ajoutée à la table salaries")
                cursor.execute('''
                    UPDATE salaries
                    SET employee_name = (
                        SELECT nom || ' ' || prenom
                        FROM employees
                        WHERE employees.id = salaries.employee_id
                    )
                    WHERE employee_name = ''
                ''')

            # Vérifier et ajouter type si nécessaire
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'salaries' AND column_name = 'type'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE salaries ADD COLUMN type TEXT NOT NULL DEFAULT 'salaire'")
                print("✅ Colonne type ajoutée à la table salaries")
                # Optionnel : mettre à jour les enregistrements existants
                cursor.execute("UPDATE salaries SET type = 'salaire' WHERE type = ''")

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
                        is_active INTEGER DEFAULT 1
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
                        date INTEGER NOT NULL,
                        FOREIGN KEY(employee_id) REFERENCES employees(id)
                    )
                ''')
                conn.commit()
                print("✅ Tables SQLite créées")
        except Exception as e:
            print(f"❌ Erreur init_db SQLite: {e}")
            raise

def verify_schema():
    """Vérifie que le schéma de la base de données est correct."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        if DATABASE_URL:
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'salaries' AND column_name = 'employee_name'")
            if not cursor.fetchone():
                raise Exception("La colonne employee_name n'existe pas dans la table salaries")
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'salaries' AND column_name = 'type'")
            if not cursor.fetchone():
                raise Exception("La colonne type n'existe pas dans la table salaries")
            print("✅ Schéma vérifié avec succès")
        else:
            cursor.execute("PRAGMA table_info(salaries)")
            columns = [col['name'] for col in cursor.fetchall()]
            if 'employee_name' not in columns:
                raise Exception("La colonne employee_name n'existe pas dans la table salaries (SQLite)")
            if 'type' not in columns:
                raise Exception("La colonne type n'existe pas dans la table salaries (SQLite)")
            print("✅ Schéma SQLite vérifié avec succès")
    except Exception as e:
        print(f"❌ Erreur vérification schéma: {e}")
        raise
    finally:
        conn.close()
