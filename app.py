from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import sqlite3
import os

app = Flask(__name__)
CORS(app)

# --- Configuration ---
DB_TYPE = os.getenv("DB_TYPE", "postgresql")  # "sqlite" ou "postgresql"

# --- Connexion DB ---
def get_db():
    if DB_TYPE == "sqlite":
        conn = sqlite3.connect("payroll.db")
        conn.row_factory = sqlite3.Row
    else:
        conn = psycopg2.connect(
            dbname="payroll",
            user="postgres",
            password="123456",
            host="localhost",
            port="5432"
        )
    return conn

# --- ROUTES AUTH ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    conn = get_db()
    cur = conn.cursor()
    if DB_TYPE == "sqlite":
        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    else:
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))

    user = cur.fetchone()
    cur.close()
    conn.close()

    if user:
        return jsonify({"success": True, "message": "Connexion réussie"})
    return jsonify({"success": False, "message": "Nom d'utilisateur ou mot de passe incorrect"}), 401

# --- ROUTES EMPLOYÉS ---
@app.route('/api/employees', methods=['GET'])
def get_employees():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM employees")
    rows = cur.fetchall()

    employees = []
    for row in rows:
        if DB_TYPE == "sqlite":
            employees.append(dict(zip([column[0] for column in cur.description], row)))
        else:
            employees.append(dict(zip([desc[0] for desc in cur.description], row)))

    cur.close()
    conn.close()
    return jsonify(employees)

# --- ROUTES SALAIRES ---
@app.route('/api/salary', methods=['POST'])
def save_salary_record():
    record = request.json

    # Champs obligatoires
    required = ['employeeId', 'employeeName', 'type', 'amount', 'date']
    for field in required:
        if field not in record:
            return jsonify({"error": f"Champ manquant: {field}"}), 400

    # Champs optionnels
    period = record.get('period', '') or ''
    hoursWorked = record.get('hoursWorked', 0.0) or 0.0

    # ID unique si non fourni
    salary_id = record.get('id', str(int(record['date'])))

    # Requête SQL
    query = """
        INSERT INTO salaries (id, employeeId, employeeName, type, amount, hoursWorked, period, date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """ if DB_TYPE == "postgresql" else """
        INSERT INTO salaries (id, employeeId, employeeName, type, amount, hoursWorked, period, date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    values = [
        salary_id,
        record['employeeId'],
        record['employeeName'],
        record['type'],
        record['amount'],
        hoursWorked,
        period,
        record['date']
    ]

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(query, values)
        conn.commit()
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": str(e)}), 500

    cur.close()
    conn.close()
    return jsonify({"success": True, "message": "Enregistrement du salaire réussi"})

# --- ROUTES DASHBOARD ---
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

    return jsonify({
        "total_employees": total_employees,
        "total_salaries": total_salaries
    })

if __name__ == '__main__':
    app.run(debug=True)
