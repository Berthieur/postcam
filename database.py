import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
import time
import uuid

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
                    employee_name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    hours_worked REAL,
                    period TEXT NOT NULL,
                    date BIGINT NOT NULL,
                    is_synced INTEGER DEFAULT 0
                )
            ''')
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
        finally:
            if conn:
                conn.close()
    else:
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

# --- Insertion exemple ---
def add_employee(nom, prenom, type_emp="employe"):
    conn = get_db()
    cursor = conn.cursor()
    emp_id = str(uuid.uuid4())
    created_at = int(time.time())
    cursor.execute(
        "INSERT INTO employees (id, nom, prenom, type, created_at) VALUES (?, ?, ?, ?, ?)" if not DATABASE_URL else
        "INSERT INTO employees (id, nom, prenom, type, created_at) VALUES (%s, %s, %s, %s, %s)",
        (emp_id, nom, prenom, type_emp, created_at)
    )
    conn.commit()
    conn.close()
    print(f"✅ Employé {nom} {prenom} ajouté avec ID {emp_id}")
    return emp_id

# --- Récupération exemple ---
def get_employees():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# --- Exemple d'utilisation ---
if __name__ == "__main__":
    init_db()
    emp_id = add_employee("Doe", "John")
    employees = get_employees()
    print("Liste des employés :", employees)
