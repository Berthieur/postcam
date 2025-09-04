import os
import logging
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_cors import CORS
from datetime import datetime
import uuid

# === Configuration Flask ===
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "3fb5222037e2be9d7d09019e1b46e268ec470fa2974a3981")
CORS(app, resources={r"/api/*": {"origins": "*"}})

# === Logger ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === DB imports ===
try:
    from database import init_db, get_db, verify_schema, DB_DRIVER
    logger.info("✅ database.py importé")
except Exception as e:
    logger.error(f"❌ Échec import database.py : {e}")
    raise

# === Placeholder SQL (Postgres = %s, SQLite = ?) ===
PLACEHOLDER = "?" if DB_DRIVER == "sqlite" else "%s"

# --- Initialisation DB ---
try:
    init_db()
    verify_schema()
    logger.info("✅ Base initialisée et schéma vérifié")
except Exception as e:
    logger.error(f"❌ Échec init_db/verify_schema : {e}")
    raise

# === Filtres Jinja2 ===
@app.template_filter("timestamp_to_datetime")
def timestamp_to_datetime_filter(timestamp):
    try:
        return datetime.fromtimestamp(int(timestamp) / 1000).strftime("%d/%m/%Y")
    except:
        return "-"

@app.template_filter("timestamp_to_datetime_full")
def timestamp_to_datetime_full_filter(timestamp):
    try:
        dt = datetime.fromtimestamp(int(timestamp) / 1000)
        return dt.strftime("%d/%m/%Y à %H:%M")
    except:
        return "-"

# === Routes Web ===
@app.route("/")
@app.route("/login")
def login_page():
    logger.info("📄 Page de connexion")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    logger.info("✅ Déconnexion")
    return redirect(url_for("login_page"))

# === API Login ===
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or request.form

    if not data:
        return jsonify({"success": False, "message": "Données manquantes"}), 400

    username = data.get("username")
    password = data.get("password")

    if username == "admin" and password == "1234":
        session["logged_in"] = True
        return jsonify({
            "success": True,
            "token": "fake-jwt-token-123",
            "role": "admin",
            "redirect_url": url_for("dashboard")
        })

    return jsonify({"success": False, "message": "Identifiants invalides"}), 401

# === GET employés ===
@app.route("/api/employees", methods=["GET"])
def get_all_employees():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM employees ORDER BY nom, prenom")
        rows = cursor.fetchall()

        employees = (
            [dict(row) for row in rows] if DB_DRIVER == "postgres"
            else [dict(zip([col[0] for col in cursor.description], row)) for row in rows]
        )

        conn.close()
        return jsonify({"success": True, "employees": employees})
    except Exception as e:
        logger.error(f"❌ get_all_employees: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# === POST ajouter employé ===
@app.route("/api/employees", methods=["POST"])
def add_employee():
    record = request.get_json(silent=True)
    required = ["nom", "prenom", "type"]
    for field in required:
        if not record or field not in record:
            return jsonify({"success": False, "message": f"Champ manquant: {field}"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()

        # ⚡ Génère toujours un UUID côté serveur
        new_id = str(uuid.uuid4())
        created_at = int(datetime.now().timestamp() * 1000)

        cursor.execute(f"""
            INSERT INTO employees (id, nom, prenom, type, is_active, created_at)
            VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
        """, [new_id, record["nom"], record["prenom"], record["type"], record.get("is_active", 1), created_at])

        conn.commit()
        conn.close()

        logger.info(f"✅ Employé ajouté: {record['prenom']} {record['nom']} (id={new_id})")

        # ⚡ Retourne l’ID généré
        return jsonify({
            "success": True,
            "message": "Employé ajouté avec succès",
            "id": new_id
        }), 201

    except Exception as e:
        logger.error(f"❌ add_employee: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# === POST ajouter salaire ===
@app.route("/api/salary", methods=["POST"])
def add_salary():
    data = request.get_json(silent=True)
    logger.info(f"📥 Données reçues: {data}")

    if not data:
        return jsonify({"success": False, "message": "Requête vide"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()

        emp_id = data.get("employeeId")
        emp_name = (data.get("employeeName") or "").strip().split(" ")

        # Vérifier si l’employé existe
        cur.execute(f"SELECT id FROM employees WHERE id = {PLACEHOLDER}", (emp_id,))
        employee = cur.fetchone()

        if not employee:
            new_id = emp_id or str(uuid.uuid4())
            nom = emp_name[-1] if len(emp_name) > 1 else emp_name[0] if emp_name else "Inconnu"
            prenom = emp_name[0] if len(emp_name) > 1 else "Inconnu"

            cur.execute(f"""
                INSERT INTO employees (id, nom, prenom, type, is_active, created_at)
                VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
            """, [new_id, nom, prenom, data.get("type", "inconnu"), 1, int(datetime.now().timestamp() * 1000)])

            emp_id = new_id

        salary_date = int(data.get("date")) if isinstance(data.get("date"), (int, float)) else int(datetime.now().timestamp() * 1000)
        period = data.get("period") or datetime.now().strftime("%Y-%m")

        cur.execute(f"""
            INSERT INTO salaries (id, employee_id, employee_name, amount, hours_worked, type, period, date)
            VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
        """, [str(uuid.uuid4()), emp_id, data.get("employeeName"), data.get("amount"), data.get("hoursWorked", 0), data.get("type"), period, salary_date])

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Salaire enregistré", "employeeId": emp_id}), 201
    except Exception as e:
        logger.error(f"❌ add_salary: {e}")
        return jsonify({"success": False, "message": str(e)}), 400
        # === PUT modifier employé ===
@app.route("/api/employees/<id>", methods=["PUT"])
def update_employee(id):
    record = request.get_json(silent=True)
    if not record:
        return jsonify({"success": False, "message": "Requête vide"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(f"""
            UPDATE employees
            SET nom = {PLACEHOLDER}, prenom = {PLACEHOLDER}, type = {PLACEHOLDER}, is_active = {PLACEHOLDER}
            WHERE id = {PLACEHOLDER}
        """, [record.get("nom"), record.get("prenom"), record.get("type"),
              record.get("is_active", 1), id])

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Employé modifié"}), 200
    except Exception as e:
        logger.error(f"❌ update_employee: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# === DELETE supprimer employé ===
@app.route("/api/employees/<id>", methods=["DELETE"])
def delete_employee(id):
    try:
        conn = get_db()
        cur = conn.cursor()

        # Supprimer d'abord les salaires liés (clé étrangère)
        cur.execute(f"DELETE FROM salaries WHERE employee_id = {PLACEHOLDER}", [id])

        # Supprimer l’employé
        cur.execute(f"DELETE FROM employees WHERE id = {PLACEHOLDER}", [id])

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Employé supprimé"}), 200
    except Exception as e:
        logger.error(f"❌ delete_employee: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# === Dashboard ===
@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT e.nom, e.prenom, e.type, s.employee_name, s.type AS payment_type, s.amount, s.period, s.date
            FROM salaries s
            INNER JOIN employees e ON e.id = s.employee_id
            WHERE e.is_active = 1
            ORDER BY s.date DESC
        """)
        rows = cursor.fetchall()

        payments = (
            [dict(row) for row in rows] if DB_DRIVER == "postgres"
            else [dict(zip([col[0] for col in cursor.description], row)) for row in rows]
        )

        conn.close()
        return render_template("dashboard.html", payments=payments)
    except Exception as e:
        logger.error(f"❌ dashboard: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# --- Démarrage ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
