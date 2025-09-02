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
    from database import init_db, get_db, verify_schema, DATABASE_URL
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
    data = request.get_json(silent=True) or request.form
    if not data:
        return jsonify({"error": "Données manquantes"}), 400

    username = data.get('username')
    password = data.get('password')

    if username == 'admin' and password == '1234':
        session['logged_in'] = True
        logger.info("✅ Connexion réussie pour admin")
        return jsonify({
            "token": "fake-jwt-token-123",
            "role": "admin",
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
        return jsonify(employees)
    except Exception as e:
        logger.error(f"❌ get_all_employees: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            conn.close()
        except:
            pass

# 👥 Ajouter un employé
@app.route('/api/employees', methods=['POST'])
def add_employee():
    record = request.get_json()
    logger.info(f"📥 Reçu pour /api/employees: {record}")

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
        logger.info("✅ Employé ajouté")
        return jsonify({"status": "success"}), 201
    except Exception as e:
        logger.error(f"❌ add_employee: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            conn.close()
        except:
            pass

# 💰 Enregistrer un salaire
@app.route('/api/salary', methods=['POST'])
def save_salary_record():
    record = request.get_json()
    logger.info(f"📥 Reçu pour /api/salary: {record}")

    required = ['employeeId', 'employeeName', 'type', 'amount', 'period', 'date']
    for field in required:
        if field not in record:
            return jsonify({"error": f"Champ manquant: {field}"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()

        # Vérifier existence employé
        if DATABASE_URL:  # PostgreSQL
            cursor.execute("SELECT id FROM employees WHERE id = %s", (record['employeeId'],))
        else:  # SQLite
            cursor.execute("SELECT id FROM employees WHERE id = ?", (record['employeeId'],))
        employee = cursor.fetchone()
        if not employee:
            return jsonify({"error": f"Employé {record['employeeId']} non trouvé"}), 400

        # Vérifier colonnes existantes
        if DATABASE_URL:
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'salaries'")
            columns = [row[0] for row in cursor.fetchall()]
        else:
            cursor.execute("PRAGMA table_info(salaries)")
            columns = [col['name'] for col in cursor.fetchall()]

        hours_worked_exists = 'hours_worked' in columns
        is_synced_exists = 'is_synced' in columns

        if hours_worked_exists and is_synced_exists:
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
        else:
            query = '''
                INSERT INTO salaries (id, employee_id, employee_name, type, amount, period, date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            '''
            values = [
                record.get('id', str(int(record['date']))),
                record['employeeId'],
                record['employeeName'],
                record['type'],
                record['amount'],
                record['period'],
                record['date']
            ]

        cursor.execute(query, values)
        conn.commit()
        logger.info("✅ Salaire enregistré")
        return jsonify({"status": "success"}), 201
    except Exception as e:
        logger.error(f"❌ save_salary: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            conn.close()
        except:
            pass

# 📅 Historique des salaires
@app.route('/api/salary/history', methods=['GET'])
def get_salary_history():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM salaries ORDER BY date DESC")
        records = [dict(row) for row in cursor.fetchall()]
        return jsonify(records)
    except Exception as e:
        logger.error(f"❌ get_salary_history: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            conn.close()
        except:
            pass

# 📊 Tableau de bord
@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login_page'))

    try:
        conn = get_db()
        cursor = conn.cursor()

        if DATABASE_URL:
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'salaries' AND column_name = 'type'")
            type_exists = cursor.fetchone()
        else:
            cursor.execute("PRAGMA table_info(salaries)")
            cols = [col['name'] for col in cursor.fetchall()]
            type_exists = 'type' in cols

        if type_exists:
            query = '''
                SELECT e.nom, e.prenom, e.type, s.employee_name, s.type AS payment_type,
                       s.amount, s.period, s.date
                FROM salaries s
                INNER JOIN employees e ON e.id = s.employee_id
                WHERE e.is_active = 1
                ORDER BY s.date DESC
            '''
        else:
            query = '''
                SELECT e.nom, e.prenom, e.type, s.employee_name, 'salaire' AS payment_type,
                       s.amount, s.period, s.date
                FROM salaries s
                INNER JOIN employees e ON e.id = s.employee_id
                WHERE e.is_active = 1
                ORDER BY s.date DESC
            '''

        cursor.execute(query)
        payments = [dict(row) for row in cursor.fetchall()]
        return render_template('dashboard.html', payments=payments)
    except Exception as e:
        logger.error(f"❌ dashboard: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            conn.close()
        except:
            pass

# --- Démarrage ---
if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
