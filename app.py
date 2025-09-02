# app.py
import os
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# === Configuration de l'application ===
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'super-secret-key-change-in-production')
CORS(app, resources={r"/api/*": {"origins": "*"}})

# === Connexion à PostgreSQL (Neon.tech) ===
# 🔥 Ton URL complète depuis Neon
DATABASE_URL = os.getenv('DATABASE_URL')

def get_db():
    """Retourne une connexion à la base PostgreSQL"""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    """Crée les tables si elles n'existent pas"""
    try:
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
                type TEXT NOT NULL,&²²²&&
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
        print("✅ Tables créées ou vérifiées avec succès.")
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de la base : {e}")
    finally:
        if conn:
            conn.close()

# --- Initialisation ---
init_db()

# === Filtres Jinja2 pour les templates ===
@app.template_filter('timestamp_to_datetime')
def timestamp_to_datetime_filter(timestamp):
    try:
        return datetime.fromtimestamp(int(timestamp) / 1000).strftime('%d/%m/%Y')
    except:
        return '-'

@app.template_filter('timestamp_to_datetime_full')
def timestamp_to_datetime_full_filter(timestamp):
    try:
        dt = datetime.fromtimestamp(int(timestamp) / 1000)
        return dt.strftime('%d/%m/%Y à %H:%M')
    except:
        return '-'

# === Routes API et Web ===

# 🔐 Page de connexion
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
    data = request.get_json()
    if data.get('username') == 'admin' and data.get('password') == '1234':
        session['logged_in'] = True
        return jsonify({
            "token": "fake-jwt-token-123",
            "role": "admin",
            "userId": "ADMIN001",
            "redirect_url": url_for('dashboard')
        })
    return jsonify({"error": "Identifiants invalides"}), 401

# 👥 Liste des employés
@app.route('/api/employees', methods=['GET'])
def get_all_employees():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM employees ORDER BY nom, prenom")
        employees = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(employees)
    except Exception as e:
        return jsonify({"error": f"Erreur base: {str(e)}"}), 500

# 💰 Enregistrer un salaire
@app.route('/api/salary', methods=['POST'])
def save_salary_record():
    record = request.get_json()
    required = ['employeeId', 'employeeName', 'type', 'amount', 'period', 'date']
    for field in required:
        if field not in record:
            return jsonify({"error": f"Champ manquant: {field}"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO salaries 
            (id, employee_id, employee_name, type, amount, hours_worked, period, date, is_synced)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0)
        ''', [
            record.get('id', str(int(record['date']))),
            record['employeeId'],
            record['employeeName'],
            record['type'],
            record['amount'],
            record.get('hoursWorked'),
            record['period'],
            record['date']
        ])
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Salaire enregistré"}), 201
    except Exception as e:
        return jsonify({"error": f"Échec : {str(e)}"}), 500

# 📅 Historique des salaires
@app.route('/api/salary/history', methods=['GET'])
def get_salary_history():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM salaries ORDER BY date DESC")
        records = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(records)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 📊 Tableau de bord
@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login_page'))
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT e.nom, e.prenom, e.type, s.employee_name, s.type AS payment_type,
                   s.amount, s.period, s.date
            FROM salaries s
            INNER JOIN employees e ON e.id = s.employee_id
            WHERE e.is_active = 1
            ORDER BY s.date DESC
        ''')
        payments = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return render_template('dashboard.html', payments=payments)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Démarrage du serveur ---
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)