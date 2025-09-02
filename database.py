# database.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Récupère l'URL depuis une variable d'environnement
DATABASE_URL = os.getenv('DATABASE_URL')

def get_db():
    """Retourne une connexion à la base PostgreSQL"""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    """Crée les tables si elles n'existent pas"""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Table employees
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id TEXT PRIMARY KEY,
            nom TEXT NOT NULL,
            prenom TEXT NOT NULL,
            date_naissance TEXT,
            lieu_naissance TEXT,
            telephone TEXT,
            email TEXT,
            profession TEXT,
            type TEXT NOT NULL,
            taux_horaire REAL,
            frais_ecolage REAL,
            qr_code TEXT,
            is_active INTEGER DEFAULT 1,
            created_at BIGINT,
            is_synced INTEGER DEFAULT 0
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

    # Table alerts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id SERIAL PRIMARY KEY,
            employeeId TEXT REFERENCES employees(id),
            employeeName TEXT NOT NULL,
            zone_name TEXT NOT NULL,
            timestamp BIGINT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()