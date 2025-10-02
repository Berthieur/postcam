import logging
import os
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_cors import CORS
import sqlite3
import psycopg2
from psycopg2.extras import DictCursor

# Configuration des logs
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = '3fb5222037e2be9d7d09019e1b46e268ec470fa2974a3981'
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- Database Configuration ---
DB_DRIVER = os.getenv("DB_DRIVER", "sqlite")  # 'sqlite' for local, 'postgres' for production
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///postcam.db")  # Fallback to local SQLite

def get_db():
    try:
        if DB_DRIVER == "postgres":
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)
        else:
            conn = sqlite3.connect(DATABASE_URL.replace("sqlite:///", ""))
            conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"❌ Échec connexion DB ({DB_DRIVER}): {e}")
        raise

def init_db():
    try:
        conn = get_db()
        cursor = conn.cursor()
        if DB_DRIVER == "postgres":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    id TEXT PRIMARY KEY,
                    nom TEXT NOT NULL,
                    prenom TEXT NOT NULL,
                    type TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at BIGINT,
                    email TEXT,
                    telephone TEXT,
                    taux_horaire FLOAT,
                    frais_ecolage FLOAT,
                    profession TEXT,
                    date_naissance TEXT,
                    lieu_naissance TEXT,
                    qr_code TEXT,
                    is_synced INTEGER DEFAULT 1
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS salaries (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT NOT NULL,
                    employee_name TEXT NOT NULL,
                    amount FLOAT NOT NULL,
                    hours_worked FLOAT,
                    type TEXT NOT NULL,
                    period TEXT,
                    date BIGINT,
                    is_synced INTEGER DEFAULT 0,
                    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pointages (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT NOT NULL,
                    employee_name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    timestamp BIGINT,
                    date TEXT,
                    is_synced INTEGER DEFAULT 0,
                    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id SERIAL PRIMARY KEY,
                    employeeId TEXT NOT NULL,
                    employeeName TEXT NOT NULL,
                    zone_name TEXT NOT NULL,
                    timestamp BIGINT,
                    FOREIGN KEY (employeeId) REFERENCES employees(id) ON DELETE CASCADE
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    id TEXT PRIMARY KEY,
                    nom TEXT NOT NULL,
                    prenom TEXT NOT NULL,
                    type TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at INTEGER,
                    email TEXT,
                    telephone TEXT,
                    taux_horaire REAL,
                    frais_ecolage REAL,
                    profession TEXT,
                    date_naissance TEXT,
                    lieu_naissance TEXT,
                    qr_code TEXT,
                    is_synced INTEGER DEFAULT 1
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS salaries (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT NOT NULL,
                    employee_name TEXT NOT NULL,
                    amount REAL NOT NULL,
                    hours_worked REAL,
                    type TEXT NOT NULL,
                    period TEXT,
                    date INTEGER,
                    is_synced INTEGER DEFAULT 0,
                    FOREIGN KEY (employee_id) REFERENCES employees(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pointages (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT NOT NULL,
                    employee_name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    timestamp INTEGER,
                    date TEXT,
                    is_synced INTEGER DEFAULT 0,
                    FOREIGN KEY (employee_id) REFERENCES employees(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employeeId TEXT NOT NULL,
                    employeeName TEXT NOT NULL,
                    zone_name TEXT NOT NULL,
                    timestamp INTEGER,
                    FOREIGN KEY (employeeId) REFERENCES employees(id)
                )
            """)
        conn.commit()
        logger.info(f"✅ Base de données initialisée ({DB_DRIVER})")
    except Exception as e:
        logger.error(f"❌ Échec init_db ({DB_DRIVER}): {e}")
        raise
    finally:
        cursor.close()
        conn.close()

# --- Initialisation ---
try:
    init_db()
except Exception as e:
    logger.error(f"❌ Échec initialisation DB: {e}")
    raise

# --- Filtres Jinja2 ---
def timestamp_to_datetime_full(timestamp):
    try:
        dt = datetime.fromtimestamp(timestamp / 1000, tz=datetime.utcnow().astimezone().tzinfo)
        dt_eat = dt + timedelta(hours=3)  # Forcer EAT (UTC+3)
        return dt_eat.strftime('%d/%m/%Y %H:%M:%S')
    except (TypeError, ValueError):
        return '-'
app.jinja_env.filters['timestamp_to_datetime_full'] = timestamp_to_datetime_full

# --- Middleware ---
@app.before_request
def check_session():
    if request.path.startswith('/api/') and request.method in ['POST', 'GET'] and not session.get('logged_in'):
        logger.error(f"Session check failed for {request.path}, session={session}, logged_in={session.get('logged_in')}")
        return jsonify({"error": "Non autorisé"}), 403
    logger.debug(f"Session check passed for {request.path}, session={session}, logged_in={session.get('logged_in')}")

# --- Routes API ---

# 1. 🔐 Login
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    logger.debug(f"Login attempt: {data}")
    if data.get('username') == 'admin' and data.get('password') == '1234':
        session['logged_in'] = True
        session['role'] = 'admin'
        session['userId'] = 'ADMIN001'
        logger.info("✅ Login successful, session updated")
        return jsonify({"status": "success", "message": "Connexion réussie"})
    logger.warning("⚠️ Login failed")
    return jsonify({"error": "Identifiants invalides"}), 401

# 2. 🔓 Déconnexion
@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    session.pop('role', None)
    session.pop('userId', None)
    logger.info("✅ Logout successful")
    return jsonify({"status": "success", "message": "Déconnexion réussie"})

# 3. 👥 Enregistrement employé
@app.route('/api/employees', methods=['POST'])
def register_employee():
    emp = request.get_json()
    required = ['id', 'nom', 'prenom', 'type']
    for field in required:
        if field not in emp or emp[field] is None:
            logger.error(f"❌ Champ manquant: {field}")
            return jsonify({"error": f"Champ manquant: {field}"}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        placeholder = "%s" if DB_DRIVER == "postgres" else "?"
        query = f"""
            INSERT INTO employees 
            (id, nom, prenom, type, is_active, created_at, email, telephone, taux_horaire, 
             frais_ecolage, profession, date_naissance, lieu_naissance, qr_code, is_synced)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, 
                    {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
        """
        if DB_DRIVER == "postgres":
            query += " ON CONFLICT (id) DO UPDATE SET nom = EXCLUDED.nom, prenom = EXCLUDED.prenom, type = EXCLUDED.type, is_active = EXCLUDED.is_active, created_at = EXCLUDED.created_at, email = EXCLUDED.email, telephone = EXCLUDED.telephone, taux_horaire = EXCLUDED.taux_horaire, frais_ecolage = EXCLUDED.frais_ecolage, profession = EXCLUDED.profession, date_naissance = EXCLUDED.date_naissance, lieu_naissance = EXCLUDED.lieu_naissance, qr_code = EXCLUDED.qr_code, is_synced = EXCLUDED.is_synced"
        else:
            query = query.replace("INSERT", "INSERT OR REPLACE")
        cursor.execute(query, [
            emp['id'],
            emp['nom'],
            emp['prenom'],
            emp['type'],
            emp.get('isActive', 1),
            emp.get('createdAt', int(time.time() * 1000)),
            emp.get('email'),
            emp.get('telephone'),
            emp.get('tauxHoraire'),
            emp.get('fraisEcolage'),
            emp.get('profession'),
            emp.get('dateNaissance'),
            emp.get('lieuNaissance'),
            emp.get('qrCode'),
            1
        ])
        conn.commit()
        logger.info(f"✅ Employee registered: {emp['id']}")
        return jsonify({"status": "success", "message": "Employé enregistré"}), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error registering employee: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 4. 📋 Liste de tous les employés
@app.route('/api/employees', methods=['GET'])
def get_all_employees():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM employees ORDER BY nom, prenom")
        employees = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"📤 Retrieved {len(employees)} employees")
        return jsonify(employees)
    except Exception as e:
        logger.error(f"❌ Error retrieving employees: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 5. 👷 Employés actifs
@app.route('/api/employees/active', methods=['GET'])
def get_active_employees():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM employees WHERE is_active = 1 ORDER BY nom")
        employees = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"📤 Retrieved {len(employees)} active employees")
        return jsonify(employees)
    except Exception as e:
        logger.error(f"❌ Error retrieving active employees: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 6. 📍 Position (dernier pointage)
@app.route('/api/employees/<employeeId>/position', methods=['GET'])
def get_employee_position(employeeId):
    conn = get_db()
    cursor = conn.cursor()
    try:
        placeholder = "%s" if DB_DRIVER == "postgres" else "?"
        cursor.execute(f"""
            SELECT employee_id, employee_name, type, timestamp, date
            FROM pointages
            WHERE employee_id = {placeholder}
            ORDER BY timestamp DESC
            LIMIT 1
        """, [employeeId])
        row = cursor.fetchone()
        if row:
            logger.debug(f"📤 Retrieved position for employee {employeeId}")
            return jsonify(dict(row))
        logger.warning(f"⚠️ No position found for employee {employeeId}")
        return jsonify({"error": "Aucun pointage trouvé"}), 404
    except Exception as e:
        logger.error(f"❌ Error retrieving position for {employeeId}: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 7. 💰 Enregistrer un salaire
@app.route('/api/salary', methods=['POST'])
def save_salary_record():
    record = request.get_json()
    required = ['employeeId', 'employeeName', 'type', 'amount', 'period', 'date']
    for field in required:
        if field not in record or record[field] is None:
            logger.error(f"❌ Champ manquant ou vide: {field}")
            return jsonify({"error": f"Champ manquant: {field}"}), 400

    try:
        amount = float(record['amount'])
        if amount <= 0:
            logger.error(f"❌ Montant invalide: {amount}")
            return jsonify({"error": "Le montant doit être supérieur à 0"}), 400
    except (ValueError, TypeError):
        logger.error(f"❌ Montant non numérique: {record.get('amount')}")
        return jsonify({"error": "Le montant doit être un nombre valide"}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        # Verify employee exists
        placeholder = "%s" if DB_DRIVER == "postgres" else "?"
        cursor.execute(f"SELECT id, nom, prenom FROM employees WHERE id = {placeholder}", [record['employeeId']])
        employee = cursor.fetchone()
        if not employee:
            logger.warning(f"⚠️ Employé {record['employeeId']} non trouvé, création automatique")
            emp_name_parts = record['employeeName'].split(" ")
            nom = emp_name_parts[-1] if len(emp_name_parts) > 1 else record['employeeName']
            prenom = emp_name_parts[0] if len(emp_name_parts) > 1 else "Inconnu"
            cursor.execute(f"""
                INSERT INTO employees (id, nom, prenom, type, is_active, created_at)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
            """, [record['employeeId'], nom, prenom, record.get('type', 'inconnu'), 1, int(time.time() * 1000)])
            conn.commit()
            logger.info(f"✅ Employé créé: ID={record['employeeId']}")

        salary_id = record.get('id', str(int(record['date'])))
        query = f"""
            INSERT INTO salaries 
            (id, employee_id, employee_name, type, amount, hours_worked, period, date, is_synced)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
        """
        if DB_DRIVER == "postgres":
            query += " ON CONFLICT (id) DO NOTHING"
        else:
            query = query.replace("INSERT", "INSERT OR IGNORE")
        cursor.execute(query, [
            salary_id,
            record['employeeId'],
            record['employeeName'],
            record['type'],
            amount,
            record.get('hoursWorked', 0.0),
            record['period'],
            record['date'],
            0
        ])
        conn.commit()
        logger.info(f"✅ Salary recorded: ID={salary_id}, employee_id={record['employeeId']}, amount={amount}")
        return jsonify({"status": "success", "id": salary_id}), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error recording salary: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 8. 📅 Historique des salaires
@app.route('/api/salary/history', methods=['GET'])
def get_salary_history():
    conn = get_db()
    cursor = conn.cursor()
    try:
        query = """
            SELECT s.*, e.nom, e.prenom, e.type AS employee_type
            FROM salaries s
            LEFT JOIN employees e ON e.id = s.employee_id
            ORDER BY s.date DESC
        """
        cursor.execute(query)
        salaries = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"📤 Retrieved {len(salaries)} salary records")
        for salary in salaries:
            logger.debug(f"Salary: ID={salary['id']}, employee_id={salary['employee_id']}, amount={salary['amount']}, type={salary['type']}")
        return jsonify(salaries)
    except Exception as e:
        logger.error(f"❌ Error retrieving salary history: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 9. 📊 Statistiques par zone (exemple fictif)
@app.route('/api/statistics/zones/<employeeId>', methods=['GET'])
def get_zone_statistics(employeeId):
    try:
        stats = [{"zone_name": "Zone A", "duration_seconds": 2700}, {"zone_name": "Zone B", "duration_seconds": 1800}]
        logger.debug(f"📤 Retrieved zone statistics for {employeeId}")
        return jsonify(stats)
    except Exception as e:
        logger.error(f"❌ Error retrieving zone statistics for {employeeId}: {e}")
        return jsonify({"error": str(e)}), 500

# 10. 🚶 Historique des mouvements (pointages)
@app.route('/api/movements/<employeeId>', methods=['GET'])
def get_movement_history(employeeId):
    conn = get_db()
    cursor = conn.cursor()
    try:
        placeholder = "%s" if DB_DRIVER == "postgres" else "?"
        cursor.execute(f"""
            SELECT employee_id, employee_name, type, timestamp, date
            FROM pointages
            WHERE employee_id = {placeholder}
            ORDER BY timestamp DESC
        """, [employeeId])
        movements = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"📤 Retrieved {len(movements)} movements for {employeeId}")
        return jsonify(movements)
    except Exception as e:
        logger.error(f"❌ Error retrieving movements for {employeeId}: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 11. ⚠️ Alerte zone interdite
@app.route('/api/alerts/forbidden-zone', methods=['POST'])
def report_forbidden_zone():
    alert = request.get_json()
    required = ['employeeId', 'employeeName', 'zoneName', 'timestamp']
    for field in required:
        if field not in alert or alert[field] is None:
            logger.error(f"❌ Champ manquant: {field}")
            return jsonify({"error": f"Champ manquant: {field}"}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        placeholder = "%s" if DB_DRIVER == "postgres" else "?"
        cursor.execute(f"""
            INSERT INTO alerts (employeeId, employeeName, zone_name, timestamp)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})
        """, [
            alert['employeeId'],
            alert['employeeName'],
            alert['zoneName'],
            alert['timestamp']
        ])
        conn.commit()
        logger.info(f"✅ Forbidden zone alert recorded for {alert['employeeId']}")
        return jsonify({"status": "alerte_enregistrée"}), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error recording forbidden zone alert: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 12. 📡 État ESP32
@app.route('/api/esp32/status', methods=['GET'])
def get_esp32_status():
    try:
        status = {
            "is_online": True,
            "last_seen": int(time.time() * 1000),
            "firmware_version": "1.2.0",
            "uptime_seconds": 3672
        }
        logger.debug("📤 ESP32 status retrieved")
        return jsonify(status)
    except Exception as e:
        logger.error(f"❌ Error retrieving ESP32 status: {e}")
        return jsonify({"error": str(e)}), 500

# 13. 🔊 Activer le buzzer
@app.route('/api/esp32/buzzer', methods=['POST'])
def activate_buzzer():
    data = request.get_json()
    duration = data.get('durationMs', 1000)
    try:
        response = {
            "status": "buzzer_activé",
            "durationMs": duration,
            "timestamp": int(time.time() * 1000)
        }
        logger.info(f"✅ Buzzer activated for {duration}ms")
        return jsonify(response)
    except Exception as e:
        logger.error(f"❌ Error activating buzzer: {e}")
        return jsonify({"error": str(e)}), 500

# 14. 🔄 Synchronisation : Récupérer les pointages non synchronisés
@app.route('/api/sync/pointages', methods=['GET'])
def get_unsynced_pointages():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM pointages WHERE is_synced = 0")
        pointages = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"📤 Retrieved {len(pointages)} unsynced pointages")
        return jsonify(pointages)
    except Exception as e:
        logger.error(f"❌ Error retrieving unsynced pointages: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 15. 🔄 Envoyer des pointages depuis Android
@app.route('/api/pointages', methods=['POST'])
def add_pointage():
    p = request.get_json()
    required = ['id', 'employeeId', 'employeeName', 'type', 'timestamp', 'date']
    for field in required:
        if field not in p or p[field] is None:
            logger.error(f"❌ Champ manquant: {field}")
            return jsonify({"error": f"Champ manquant: {field}"}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        placeholder = "%s" if DB_DRIVER == "postgres" else "?"
        query = f"""
            INSERT INTO pointages 
            (id, employee_id, employee_name, type, timestamp, date, is_synced)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
        """
        if DB_DRIVER == "postgres":
            query += " ON CONFLICT (id) DO NOTHING"
        else:
            query = query.replace("INSERT", "INSERT OR IGNORE")
        cursor.execute(query, [
            p['id'],
            p['employeeId'],
            p['employeeName'],
            p['type'],
            p['timestamp'],
            p['date'],
            1
        ])
        conn.commit()
        logger.info(f"✅ Pointage recorded: {p['id']}")
        return jsonify({"status": "pointage_enregistré"}), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error recording pointage: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 16. 📥 Télécharger tous les pointages
@app.route('/api/pointages', methods=['GET'])
def get_all_pointages():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM pointages ORDER BY timestamp DESC")
        pointages = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"📤 Retrieved {len(pointages)} pointages")
        return jsonify(pointages)
    except Exception as e:
        logger.error(f"❌ Error retrieving all pointages: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 17. 💸 Liste des employés avec leurs paiements
@app.route('/api/employee_payments', methods=['GET'])
def get_employee_payments():
    conn = get_db()
    cursor = conn.cursor()
    try:
        query = """
            SELECT e.nom, e.prenom, e.type, s.employee_name, s.type AS payment_type, 
                   s.amount, s.period, s.date
            FROM employees e
            LEFT JOIN salaries s ON e.id = s.employee_id
            WHERE e.is_active = 1
            ORDER BY s.date DESC
        """
        cursor.execute(query)
        payments = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"📤 Retrieved {len(payments)} employee payments")
        return jsonify(payments)
    except Exception as e:
        logger.error(f"❌ Error retrieving employee payments: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 18. 📊 Tableau de bord HTML
@app.route('/dashboard', methods=['GET'])
def dashboard():
    if not session.get('logged_in'):
        logger.warning("⚠️ Unauthorized access to dashboard, redirecting to login")
        return redirect(url_for('login_page'))
    try:
        conn = get_db()
        cursor = conn.cursor()
        if DB_DRIVER == "postgres":
            query = """
                SELECT 
                    COALESCE(e.nom, SPLIT_PART(s.employee_name, ' ', 1)) AS nom,
                    COALESCE(e.prenom, SPLIT_PART(s.employee_name, ' ', 2)) AS prenom,
                    COALESCE(e.type, s.type) AS type,
                    s.employee_name,
                    s.type AS payment_type,
                    s.amount,
                    s.period,
                    s.date
                FROM salaries s
                LEFT JOIN employees e ON e.id = s.employee_id
                ORDER BY s.date DESC
            """
        else:
            query = """
                SELECT 
                    COALESCE(e.nom, SUBSTR(s.employee_name, 1, INSTR(s.employee_name, ' ') - 1)) AS nom,
                    COALESCE(e.prenom, SUBSTR(s.employee_name, INSTR(s.employee_name, ' ') + 1)) AS prenom,
                    COALESCE(e.type, s.type) AS type,
                    s.employee_name,
                    s.type AS payment_type,
                    s.amount,
                    s.period,
                    s.date
                FROM salaries s
                LEFT JOIN employees e ON e.id = s.employee_id
                ORDER BY s.date DESC
            """
        cursor.execute(query)
        payments = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"📤 Number of payments retrieved for dashboard: {len(payments)}")
        for payment in payments:
            logger.debug(f"Payment: nom={payment['nom']}, prenom={payment['prenom']}, type={payment['type']}, payment_type={payment['payment_type']}, amount={payment['amount']}, date={payment['date']}")
        return render_template('dashboard.html', payments=payments)
    except Exception as e:
        logger.error(f"❌ Error loading dashboard: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 19. 📝 Page de login
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        logger.debug(f"Login attempt: username={username}")
        if username == 'admin' and password == '1234':
            session['logged_in'] = True
            session['role'] = 'admin'
            session['userId'] = 'ADMIN001'
            logger.info("✅ Login successful, session updated")
            return redirect(url_for('dashboard'))
        logger.warning("⚠️ Login failed")
        return render_template('login.html', error="Identifiants invalides")
    return render_template('login.html')

# 20. 🛠️ Debug endpoint pour inspecter la table salaries
@app.route('/api/salary/debug', methods=['GET'])
def debug_salaries():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM salaries")
        salaries = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"📤 Debug: Retrieved {len(salaries)} salaries")
        return jsonify({"success": True, "salaries": salaries}), 200
    except Exception as e:
        logger.error(f"❌ debug_salaries: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# --- Démarrage ---
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
