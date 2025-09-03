import os
import logging
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_cors import CORS
from datetime import datetime
import uuid

# === Configuration de l'application ===
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', '3fb5222037e2be9d7d09019e1b46e268ec470fa2974a3981')
CORS(app, resources={r"/api/*": {"origins": "*"}})

# === Logging ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Connexion à la base ===
try:
    from database import init_db, get_db, verify_schema, DB_DRIVER
    logger.info("✅ database.py importé")
except Exception as e:
    logger.error(f"❌ Échec import database.py : {e}")
    raise

# --- Initialisation ---
try:
    init_db()
    verify_schema()
    logger.info("✅ Base initialisée et schéma vérifié")
except Exception as e:
    logger.error(f"❌ Échec init_db ou verify_schema : {e}")
    raise

# === Détection driver SQL ===
# sqlite → "?"
# psycopg2 (Postgres) → "%s"
PLACEHOLDER = "?" if DB_DRIVER == "sqlite" else "%s"

# === Routes Web ===
@app.route('/')
@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login_page'))

# 🔐 API Login
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or request.form

    if not data:
        return jsonify({"status": "error", "message": "Données manquantes"}), 400

    username = data.get('username')
    password = data.get('password')

    if username == 'admin' and password == '1234':
        session['logged_in'] = True
        return jsonify({
            "status": "success",
            "message": "Connexion réussie",
            "token": "fake-jwt-token-123",
            "role": "admin",
            "redirect_url": url_for('dashboard')
        })

    return jsonify({"status": "error", "message": "Identifiants invalides"}), 401

# 👥 Liste des employés
@app.route('/api/employees', methods=['GET'])
def get_all_employees():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM employees ORDER BY nom, prenom")
        employees = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({"status": "success", "employees": employees, "message": "Liste récupérée"})
    except Exception as e:
        logger.exception("❌ get_all_employees")
        return jsonify({"status": "error", "message": str(e)}), 500

# 👥 Ajouter un employé
@app.route('/api/employees', methods=['POST'])
def add_employee():
    record = request.get_json(silent=True)
    required = ['nom', 'prenom', 'type']
    for field in required:
        if not record.get(field):
            return jsonify({"status": "error", "message": f"Champ manquant: {field}"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()

        new_id = record.get('id') or str(uuid.uuid4())

        cursor.execute(f'''
            INSERT INTO employees (id, nom, prenom, type, is_active, created_at)
            VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
        ''', (
            new_id,
            record['nom'],
            record['prenom'],
            record['type'],
            record.get('is_active', 1),
            int(datetime.now().timestamp() * 1000)
        ))
        conn.commit()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f"Employé {record['prenom']} {record['nom']} ajouté",
            "id": new_id
        }), 201

    except Exception as e:
        logger.exception("❌ add_employee")
        return jsonify({"status": "error", "message": str(e)}), 500

# 💰 Ajouter un salaire
@app.route("/api/salary", methods=["POST"])
def add_salary():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "message": "Requête vide"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()

        emp_id = data.get("employeeId")
        emp_name = (data.get("employeeName") or "").strip().split(" ")

        cur.execute(f"SELECT id FROM employees WHERE id = {PLACEHOLDER}", (emp_id,))
        employee = cur.fetchone()

        if not employee:
            new_id = emp_id or str(uuid.uuid4())
            prenom = emp_name[0] if len(emp_name) > 0 else ""
            nom = " ".join(emp_name[1:]) if len(emp_name) > 1 else prenom
            type_emp = data.get("type", "inconnu")

            cur.execute(f'''
                INSERT INTO employees (id, nom, prenom, type, is_active, created_at)
                VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
            ''', (
                new_id,
                nom,
                prenom,
                type_emp,
                1,
                int(datetime.now().timestamp() * 1000)
            ))
            emp_id = new_id

        salary_date = int(datetime.now().timestamp() * 1000)
        if data.get("date"):
            if isinstance(data["date"], (int, float)):
                salary_date = int(data["date"])
            else:
                salary_date = int(datetime.strptime(data["date"], "%Y-%m-%d").timestamp() * 1000)

        period = data.get("period") or datetime.now().strftime("%Y-%m")

        cur.execute(f"""
            INSERT INTO salaries (id, employee_id, employee_name, amount, hours_worked, type, period, date)
            VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
        """, (
            str(uuid.uuid4()),
            emp_id,
            data.get("employeeName"),
            data.get("amount"),
            data.get("hoursWorked", 0),
            data.get("type"),
            period,
            salary_date
        ))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f"Salaire enregistré pour {data.get('employeeName')}"
        }), 201

    except Exception as e:
        logger.exception("❌ add_salary")
        return jsonify({"status": "error", "message": str(e)}), 500

# 📊 Dashboard
@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login_page'))

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(f'''
            SELECT e.nom, e.prenom, e.type, s.employee_name, s.type AS payment_type, s.amount, s.period, s.date
            FROM salaries s
            INNER JOIN employees e ON e.id = s.employee_id
            WHERE e.is_active = 1
            ORDER BY s.date DESC
        ''')
        payments = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return render_template('dashboard.html', payments=payments)
    except Exception as e:
        logger.exception("❌ dashboard")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Lancement ---
if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
