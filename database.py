import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv('DATABASE_URL')

def get_db():
    """Connexion à la base PostgreSQL ou SQLite"""
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    else:
        conn = sqlite3.connect('tracking.db')
        conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Création des tables"""
    conn = get_db()
    cursor = conn.cursor()
    if DATABASE_URL:
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
    else:  # SQLite
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
    conn.close()

def verify_schema():
    """Vérifie que la table salaries contient bien toutes les colonnes nécessaires"""
    conn = get_db()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'salaries'")
        columns = [row[0] for row in cursor.fetchall()]
    else:
        cursor.execute("PRAGMA table_info(salaries)")
        columns = [col['name'] for col in cursor.fetchall()]

    required = ['employee_name', 'type', 'hours_worked', 'is_synced']
    for col in required:
        if col not in columns:
            raise Exception(f"❌ Colonne manquante: {col}")
    conn.close()
