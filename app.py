import os
import logging
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_cors import CORS
from datetime import datetime

# === Configuration de l'application ===
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', '3fb5222037e2be9d7d09019e1b46e268ec470fa2974a3981')
CORS(app, resources={r"/api/*": {"origins": "*"}})

# === Logging ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Connexion à la base ===
try:
    from database import init_db, get_db, verify_schema
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

# === Filtres Jinja2 ===
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

# === Routes Web ===
@app.route('/')
@app.route('/login')
def login_page():
    logger.info("📄 Affichage de la page de connexion")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    logger.info("✅ Déconnexion réussie")
    return redirect(url_for('login_page'))

# 🔐 API Login
@app.route('/api/login', methods=['POST'])
def login():
    content_type = request.headers.get('Content-Type', '')
    data = None

    if 'application/json' in content_type:
        data = request.get_json()
    elif 'application/x-www-form-urlencoded' in content_type:
        data = request.form

    if not data:
        logger.error("❌ Données manquantes à /api/login")
        return jsonify({"error": "Données manquantes"}), 400

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Nom d'utilisateur et mot de passe requis"}), 400

    if username == 'admin' and password == '1234':
        session['logged_in'] = True
        logger.info("✅ Connexion réussie pour admin")
        return jsonify({
            "token": "fake-jwt-token-123",
            "role": "admin",
            "redirect_url": url_for('dashboard')
        })

    logger.error("❌ Identifiants invalides")
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
        logger.info("✅ Liste des employés récupérée")
        return jsonify(employees)
    except Exception as e:
        logger.error(f"❌ get_all_employees: {e}")
        return jsonify({"error": str(e)}), 500

# 👥 Ajouter un employé
@app.route('/api/employees', methods=['POST'])
def add_employee():
    record = request.get_json()
    required = ['id', 'nom', 'prenom', 'type']
    for field in required:
        if field not in record:
            return jsonify({"error": f"Champ manquant: {field}"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO employees (id, nom, prenom, type, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', [
            record['id'],
            record['nom'],
            record['prenom'],
            record['type'],
            record.get('is_active', 1),
            record.get('created_at', int(datetime.now().timestamp() * 1000))
        ])
        conn.commit()
        conn.close()
        logger.info("✅ Employé ajouté")
        return jsonify({"status": "success"}), 201
    except Exception as e:
        logger.error(f"❌ Échec add_employee: {e}")
        return jsonify({"error": str(e)}), 500

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

        cursor.execute("SELECT id FROM employees WHERE id = %s", (record['employeeId'],))
        employee = cursor.fetchone()
        if not employee:
            return jsonify({"error": f"Employé {record['employeeId']} introuvable"}), 400

        query = '''
            INSERT INTO salaries (id, employee_id, employee_name, type, amount, hours_worked, period, date, is_synced)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0)
        '''
        values = [
            record.get('id', str(int(record['date']))),
            record['employeeId'],
            record['employeeName'],
            record['type'],
            record['amount'],
            record.get('hoursWorked', 0.0),
            record['period'],
            record['date']
        ]
        cursor.execute(query, values)
        conn.commit()
        conn.close()
        logger.info("✅ Salaire enregistré")
        return jsonify({"status": "success"}), 201
    except Exception as e:
        logger.error(f"❌ save_salary_record: {e}")
        return jsonify({"error": str(e)}), 500

# 📅 Historique des salaires
@app.route('/api/salary/history', methods=['GET'])
def get_salary_history():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM salaries ORDER BY date DESC")
        records = [dict(row) for row in cursor.fetchall()]
        conn.close()
        logger.info("✅ Historique des salaires récupéré")
        return jsonify(records)
    except Exception as e:
        logger.error(f"❌ get_salary_history: {e}")
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
        logger.error(f"❌ dashboard: {e}")
        return jsonify({"error": str(e)}), 500

# --- Démarrage ---
if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
