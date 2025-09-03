import os
import sqlite3
import psycopg2
import logging
from psycopg2.extras import RealDictCursor

# --- Logger ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URL fournie automatiquement par Render pour Postgres
DATABASE_URL = os.getenv("DATABASE_URL")

# Driver courant : "postgres" si DATABASE_URL défini, sinon "sqlite"
DB_DRIVER = "postgres" if DATABASE_URL else "sqlite"


def get_db():
    """Retourne une connexion DB (Postgres si DATABASE_URL, sinon SQLite)."""
    if DB_DRIVER == "postgres":
        try:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            return conn
        except Exception as e:
            logger.error(f"❌ Connexion PostgreSQL échouée : {e}")
            raise
    else:
        conn = sqlite3.connect("tracking.db")
        conn.row_factory = sqlite3.Row
        return conn


def init_db():
    """Crée les tables nécessaires si elles n'existent pas."""
    if DB_DRIVER == "postgres":
        conn = None
        try:
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    id TEXT PRIMARY KEY,
                    nom TEXT NOT NULL,
                    prenom TEXT NOT NULL,
                    type TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at BIGINT
                )
            """)

            cursor.execute("""
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
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pointages (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT REFERENCES employees(id),
                    employee_name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    timestamp BIGINT NOT NULL,
                    date TEXT NOT NULL,
                    is_synced INTEGER DEFAULT 0
                )
            """)

            conn.commit()
            logger.info("✅ Tables PostgreSQL initialisées")
        except Exception as e:
            logger.error(f"❌ init_db PostgreSQL : {e}")
            raise
        finally:
            if conn:
                conn.close()
    else:
        try:
            with sqlite3.connect("tracking.db") as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS employees (
                        id TEXT PRIMARY KEY,
                        nom TEXT NOT NULL,
                        prenom TEXT NOT NULL,
                        type TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        created_at BIGINT
                    )
                """)

                cursor.execute("""
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
                """)

                cursor.execute("""
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
                """)

                conn.commit()
                logger.info("✅ Tables SQLite initialisées")
        except Exception as e:
            logger.error(f"❌ init_db SQLite : {e}")
            raise


def verify_schema():
    """Vérifie la structure de la table employees."""
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()

        if DB_DRIVER == "postgres":
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'employees';
            """)
            rows = cursor.fetchall()
            columns = [row["column_name"] for row in rows]
        else:
            cursor.execute("PRAGMA table_info(employees);")
            rows = cursor.fetchall()
            columns = [row[1] for row in rows]

        logger.info(f"📋 Colonnes trouvées dans employees : {columns}")

        expected = ["id", "nom", "prenom", "type", "is_active", "created_at"]
        missing = [col for col in expected if col not in columns]

        if missing:
            logger.error(f"❌ Colonnes manquantes : {missing}")
        else:
            logger.info("✅ Schéma employees correct")

        cursor.close()
    except Exception as e:
        logger.error(f"❌ Erreur verify_schema : {e}")
        raise
    finally:
        if conn:
            conn.close()
