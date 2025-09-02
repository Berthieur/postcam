from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
import time
import uuid

app = Flask(__name__)
CORS(app)

# === Configuration ===
DATABASE_URL = os.getenv('DATABASE_URL')  # Si vide, SQLite sera utilisé

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

# --- Initialisation DB ---
def init_db():
    """Initialise les tables."""
    conn = get_db()
    cursor = conn.cursor()

    if DATABASE_URL:  # PostgreSQL
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
    conn.close()
    print("✅ Base de données initialisée")

# --- Routes API ---

# Login simple (exemple)
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    conn = get_db()
    cur = conn.cursor()
    if DATABASE_URL:
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        user = cur.fetchone()
    else:
        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cur.fetchone()
    cur.close()
    conn.close()

    if user:
        return jsonify({"success": True, "message": "Connexion réussie"})
    return jsonify({"success": False, "message": "Nom d'utilisateur ou mot de passe incorrect"}), 401

# Liste employés
@app.route('/api/employees', methods=['GET'])
def get_employees():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM employees")
    rows = cur.fetchall()
    employees = [dict(row) for row in rows] if not DATABASE_URL else [dict(row) for row in rows]
    cur.close()
    conn.close()
    return jsonify(employees)

# Ajouter un employé
@app.route('/api/employees', methods=['POST'])
def add_employee():
    data = request.json
    nom = data.get('nom')
    prenom = data.get('prenom')
    type_emp = data.get('type', 'employe')
    emp_id = str(uuid.uuid4())
    created_at = int(time.time())

    conn = get_db()
    cur = conn.cursor()
    query = "INSERT INTO employees (id, nom, prenom, type, created_at) VALUES (%s, %s, %s, %s, %s)" if DATABASE_URL else \
            "INSERT INTO employees (id, nom, prenom, type, created_at) VALUES (?, ?, ?, ?, ?)"
    cur.execute(query, (emp_id, nom, prenom, type_emp, created_at))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True, "id": emp_id})

# Ajouter salaire
@app.route('/api/salary', methods=['POST'])
def add_salary():
    record = request.json

    required = ['employeeId', 'employeeName', 'type', 'amount', 'date']
    for field in required:
        if field not in record:
            return jsonify({"error": f"Champ manquant: {field}"}), 400

    period = record.get('period', '') or ''
    hours_worked = float(record.get('hoursWorked', 0) or 0)
    salary_id = str(uuid.uuid4())
    date_val = int(record['date'])
    if date_val > 1e12:
        date_val = int(date_val / 1000)  # conversion ms -> s

    conn = get_db()
    cur = conn.cursor()
    query = """
        INSERT INTO salaries (id, employee_id, employee_name, type, amount, hours_worked, period, date)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """ if DATABASE_URL else """
        INSERT INTO salaries (id, employee_id, employee_name, type, amount, hours_worked, period, date)
        VALUES (?,?,?,?,?,?,?,?)
    """
    try:
        cur.execute(query, (salary_id, record['employeeId'], record['employeeName'], record['type'],
                            record['amount'], hours_worked, period, date_val))
        conn.commit()
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": str(e)}), 500

    cur.close()
    conn.close()
    return jsonify({"success": True, "message": "Salaire ajouté"})

# Dashboard
@app.route('/api/dashboard', methods=['GET'])
def dashboard():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM employees")
    total_employees = cur.fetchone()[0]
    cur.execute("SELECT SUM(amount) FROM salaries")
    total_salaries = cur.fetchone()[0] or 0
    cur.close()
    conn.close()
    return jsonify({"total_employees": total_employees, "total_salaries": total_salaries})

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
