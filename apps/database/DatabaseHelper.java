package com.trackingsystem.apps.database;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.util.Log;
import com.trackingsystem.apps.models.Employee;
import com.trackingsystem.apps.models.Pointage;
import com.trackingsystem.apps.models.SalaryRecord;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.Date;
import java.util.List;
import java.util.Locale;

public class DatabaseHelper extends SQLiteOpenHelper {

    private static final String TAG = "DatabaseHelper";
    private static final String COL_SAL_IS_SYNCED = "is_synced";
    private static final String DATABASE_NAME = "QRTrackingDB";
    private static final int DATABASE_VERSION = 2;

    // Noms des tables
    private static final String TABLE_EMPLOYEES = "employees";
    private static final String TABLE_POINTAGES = "pointages";
    private static final String TABLE_SALARIES = "salaries";

    // Colonnes pour employees
    private static final String COL_EMP_ID = "id";
    private static final String COL_EMP_NOM = "nom";
    private static final String COL_EMP_PRENOM = "prenom";
    private static final String COL_EMP_DATE_NAISSANCE = "date_naissance";
    private static final String COL_EMP_LIEU_NAISSANCE = "lieu_naissance";
    private static final String COL_EMP_TELEPHONE = "telephone";
    private static final String COL_EMP_EMAIL = "email";
    private static final String COL_EMP_PROFESSION = "profession";
    private static final String COL_EMP_TYPE = "type";
    private static final String COL_EMP_TAUX_HORAIRE = "taux_horaire";
    private static final String COL_EMP_FRAIS_ECOLAGE = "frais_ecolage";
    private static final String COL_EMP_QR_CODE = "qr_code";
    private static final String COL_EMP_IS_ACTIVE = "is_active";
    private static final String COL_EMP_CREATED_AT = "created_at";

    // Colonnes pour pointages
    private static final String COL_POINT_ID = "id";
    private static final String COL_POINT_EMPLOYEE_ID = "employee_id";
    private static final String COL_POINT_EMPLOYEE_NAME = "employee_name";
    private static final String COL_POINT_TYPE = "type";
    private static final String COL_POINT_TIMESTAMP = "timestamp";
    private static final String COL_POINT_DATE = "date";

    // Colonnes pour salaries
    private static final String COL_SAL_ID = "id";
    private static final String COL_SAL_EMPLOYEE_ID = "employee_id";
    private static final String COL_SAL_EMPLOYEE_NAME = "employee_name";
    private static final String COL_SAL_TYPE = "type";
    private static final String COL_SAL_AMOUNT = "amount";
    private static final String COL_SAL_HOURS_WORKED = "hours_worked";
    private static final String COL_SAL_PERIOD = "period";
    private static final String COL_SAL_DATE = "date";

    // ✅ CORRECTION : Utiliser les mêmes valeurs que dans QRScanActivity
    public static final String POINTAGE_TYPE_ARRIVAL = "arrivee";
    public static final String POINTAGE_TYPE_DEPARTURE = "sortie";

    public DatabaseHelper(Context context) {
        super(context, DATABASE_NAME, null, DATABASE_VERSION);
    }

    @Override
    public void onCreate(SQLiteDatabase db) {
        String createEmployeesTable = "CREATE TABLE " + TABLE_EMPLOYEES + "("
                + COL_EMP_ID + " TEXT PRIMARY KEY,"
                + COL_EMP_NOM + " TEXT NOT NULL,"
                + COL_EMP_PRENOM + " TEXT NOT NULL,"
                + COL_EMP_DATE_NAISSANCE + " TEXT,"
                + COL_EMP_LIEU_NAISSANCE + " TEXT,"
                + COL_EMP_TELEPHONE + " TEXT,"
                + COL_EMP_EMAIL + " TEXT,"
                + COL_EMP_PROFESSION + " TEXT,"
                + COL_EMP_TYPE + " TEXT NOT NULL,"
                + COL_EMP_TAUX_HORAIRE + " REAL,"
                + COL_EMP_FRAIS_ECOLAGE + " REAL,"
                + COL_EMP_QR_CODE + " TEXT,"
                + COL_EMP_IS_ACTIVE + " INTEGER DEFAULT 1,"
                + COL_EMP_CREATED_AT + " INTEGER"
                + ")";

        String createPointagesTable = "CREATE TABLE " + TABLE_POINTAGES + "("
                + COL_POINT_ID + " TEXT PRIMARY KEY,"
                + COL_POINT_EMPLOYEE_ID + " TEXT NOT NULL,"
                + COL_POINT_EMPLOYEE_NAME + " TEXT NOT NULL,"
                + COL_POINT_TYPE + " TEXT NOT NULL,"
                + COL_POINT_TIMESTAMP + " INTEGER NOT NULL,"
                + COL_POINT_DATE + " TEXT NOT NULL,"
                + "FOREIGN KEY(" + COL_POINT_EMPLOYEE_ID + ") REFERENCES " + TABLE_EMPLOYEES + "(" + COL_EMP_ID + ")"
                + ")";

        String createSalariesTable = "CREATE TABLE " + TABLE_SALARIES + "("
                + COL_SAL_ID + " TEXT PRIMARY KEY,"
                + COL_SAL_EMPLOYEE_ID + " TEXT NOT NULL,"
                + COL_SAL_EMPLOYEE_NAME + " TEXT NOT NULL,"
                + COL_SAL_TYPE + " TEXT NOT NULL,"
                + COL_SAL_AMOUNT + " REAL NOT NULL,"
                + COL_SAL_HOURS_WORKED + " REAL,"
                + COL_SAL_PERIOD + " TEXT NOT NULL,"
                + COL_SAL_DATE + " INTEGER NOT NULL,"
                + COL_SAL_IS_SYNCED + " INTEGER DEFAULT 0,"
                + "FOREIGN KEY(" + COL_SAL_EMPLOYEE_ID + ") REFERENCES " + TABLE_EMPLOYEES + "(" + COL_EMP_ID + ")"
                + ")";

        db.execSQL(createEmployeesTable);
        db.execSQL(createPointagesTable);
        db.execSQL(createSalariesTable);
    }

    @Override
    public void onOpen(SQLiteDatabase db) {
        super.onOpen(db);
        if (!db.isReadOnly()) {
            db.execSQL("PRAGMA foreign_keys=ON;");
        }
    }

    @Override
    public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        Log.w(TAG, "Mise à jour de la base de données de la version " + oldVersion + " vers " + newVersion);
        if (oldVersion < 2) {
            db.execSQL("ALTER TABLE " + TABLE_SALARIES + " ADD COLUMN " + COL_SAL_IS_SYNCED + " INTEGER DEFAULT 0");
        }
    }

    public long addEmployee(Employee employee) {
        if (employee.getId() == null || employee.getNom() == null || employee.getPrenom() == null) {
            Log.e(TAG, "Erreur : id, nom ou prenom de l'employé est null");
            return -1;
        }

        SQLiteDatabase db = this.getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put(COL_EMP_ID, employee.getId());
        values.put(COL_EMP_NOM, employee.getNom());
        values.put(COL_EMP_PRENOM, employee.getPrenom());
        values.put(COL_EMP_DATE_NAISSANCE, employee.getDateNaissance());
        values.put(COL_EMP_LIEU_NAISSANCE, employee.getLieuNaissance());
        values.put(COL_EMP_TELEPHONE, employee.getTelephone());
        values.put(COL_EMP_EMAIL, employee.getEmail());
        values.put(COL_EMP_PROFESSION, employee.getProfession());
        values.put(COL_EMP_TYPE, employee.getType());
        values.put(COL_EMP_TAUX_HORAIRE, employee.getTauxHoraire());
        values.put(COL_EMP_FRAIS_ECOLAGE, employee.getFraisEcolage());
        values.put(COL_EMP_QR_CODE, employee.getQrCode());
        values.put(COL_EMP_IS_ACTIVE, employee.isActive() ? 1 : 0);
        values.put(COL_EMP_CREATED_AT, employee.getCreatedAt());

        Cursor cursor = db.query(TABLE_EMPLOYEES, new String[]{COL_EMP_ID},
                COL_EMP_ID + "=?", new String[]{employee.getId()}, null, null, null);
        long result;
        if (cursor.moveToFirst()) {
            result = db.update(TABLE_EMPLOYEES, values, COL_EMP_ID + "=?", new String[]{employee.getId()});
            Log.d(TAG, "Employé mis à jour avec ID: " + employee.getId());
        } else {
            result = db.insert(TABLE_EMPLOYEES, null, values);
            Log.d(TAG, "Nouvel employé inséré avec ID: " + employee.getId());
        }
        cursor.close();
        db.close();
        return result;
    }

    public Employee getEmployee(String id) {
        SQLiteDatabase db = this.getReadableDatabase();
        Cursor cursor = db.query(TABLE_EMPLOYEES, null, COL_EMP_ID + "=?",
                new String[]{id}, null, null, null);
        Employee employee = null;
        if (cursor.moveToFirst()) {
            employee = cursorToEmployee(cursor);
        }
        cursor.close();
        db.close();
        return employee;
    }

    public List<Employee> getAllEmployees() {
        List<Employee> employees = new ArrayList<>();
        SQLiteDatabase db = this.getReadableDatabase();
        Cursor cursor = db.query(TABLE_EMPLOYEES, null, null, null, null, null, COL_EMP_CREATED_AT + " DESC");
        if (cursor.moveToFirst()) {
            do {
                employees.add(cursorToEmployee(cursor));
            } while (cursor.moveToNext());
        }
        cursor.close();
        db.close();
        return employees;
    }

    public boolean updateEmployee(Employee employee) {
        SQLiteDatabase db = this.getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put(COL_EMP_NOM, employee.getNom());
        values.put(COL_EMP_PRENOM, employee.getPrenom());
        values.put(COL_EMP_DATE_NAISSANCE, employee.getDateNaissance());
        values.put(COL_EMP_LIEU_NAISSANCE, employee.getLieuNaissance());
        values.put(COL_EMP_TELEPHONE, employee.getTelephone());
        values.put(COL_EMP_EMAIL, employee.getEmail());
        values.put(COL_EMP_PROFESSION, employee.getProfession());
        values.put(COL_EMP_TYPE, employee.getType());
        values.put(COL_EMP_TAUX_HORAIRE, employee.getTauxHoraire());
        values.put(COL_EMP_FRAIS_ECOLAGE, employee.getFraisEcolage());
        values.put(COL_EMP_IS_ACTIVE, employee.isActive() ? 1 : 0);

        int rowsAffected = db.update(TABLE_EMPLOYEES, values, COL_EMP_ID + "=?", new String[]{employee.getId()});
        db.close();
        return rowsAffected > 0;
    }

    public void deleteEmployee(String id) {
        SQLiteDatabase db = this.getWritableDatabase();
        db.beginTransaction();
        try {
            db.delete(TABLE_POINTAGES, COL_POINT_EMPLOYEE_ID + "=?", new String[]{id});
            db.delete(TABLE_SALARIES, COL_SAL_EMPLOYEE_ID + "=?", new String[]{id});
            db.delete(TABLE_EMPLOYEES, COL_EMP_ID + "=?", new String[]{id});
            db.setTransactionSuccessful();
        } finally {
            db.endTransaction();
            db.close();
        }
    }

    public long addPointage(Pointage pointage) {
        if (pointage.getEmployeeId() == null || pointage.getEmployeeName() == null) {
            Log.e(TAG, "Erreur : employeeId ou employeeName du pointage est null");
            return -1;
        }

        SQLiteDatabase db = this.getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put(COL_POINT_ID, String.valueOf(System.currentTimeMillis()));
        values.put(COL_POINT_EMPLOYEE_ID, pointage.getEmployeeId());
        values.put(COL_POINT_EMPLOYEE_NAME, pointage.getEmployeeName());
        values.put(COL_POINT_TYPE, pointage.getType());
        values.put(COL_POINT_TIMESTAMP, pointage.getTimestamp());
        values.put(COL_POINT_DATE, pointage.getDate());
        long result = db.insert(TABLE_POINTAGES, null, values);
        Log.d(TAG, "Pointage ajouté : ID=" + values.getAsString(COL_POINT_ID) + ", Type=" + pointage.getType() + ", EmployeeID=" + pointage.getEmployeeId());
        db.close();
        return result;
    }

    public Pointage getLastPointageForEmployee(String employeeId, String date) {
        SQLiteDatabase db = this.getReadableDatabase();
        Cursor cursor = db.query(TABLE_POINTAGES, null,
                COL_POINT_EMPLOYEE_ID + "=? AND " + COL_POINT_DATE + " =?",
                new String[]{employeeId, date}, null, null, COL_POINT_TIMESTAMP + " DESC", "1");
        Pointage pointage = null;
        if (cursor.moveToFirst()) {
            pointage = cursorToPointage(cursor);
            Log.d(TAG, "Dernier pointage trouvé pour employeeId=" + employeeId + ", date=" + date + ", type=" + pointage.getType());
        } else {
            Log.w(TAG, "Aucun pointage trouvé pour employeeId=" + employeeId + ", date=" + date);
        }
        cursor.close();
        db.close();
        return pointage;
    }

    public Pointage getFirstEmployeeArrivalToday() {
        SQLiteDatabase db = this.getReadableDatabase();
        Pointage firstArrival = null;
        SimpleDateFormat dateFormat = new SimpleDateFormat("yyyy-MM-dd", Locale.getDefault());
        String today = dateFormat.format(new Date());

        String selectQuery = "SELECT * FROM " + TABLE_POINTAGES +
                " WHERE " + COL_POINT_DATE + " = ?" +
                " AND " + COL_POINT_TYPE + " = ?" +
                " ORDER BY " + COL_POINT_TIMESTAMP + " ASC" +
                " LIMIT 1";

        Cursor c = db.rawQuery(selectQuery, new String[]{today, POINTAGE_TYPE_ARRIVAL});
        if (c != null && c.moveToFirst()) {
            firstArrival = cursorToPointage(c);
            Log.d(TAG, "Premier pointage d'arrivée aujourd'hui : " + firstArrival.getEmployeeId() + ", " + firstArrival.getType());
        } else {
            Log.w(TAG, "Aucun pointage d'arrivée trouvé pour aujourd'hui");
        }
        if (c != null) {
            c.close();
        }
        db.close();
        return firstArrival;
    }

    public Pointage getLastEmployeeDepartureToday() {
        SQLiteDatabase db = this.getReadableDatabase();
        Pointage lastDeparture = null;
        SimpleDateFormat dateFormat = new SimpleDateFormat("yyyy-MM-dd", Locale.getDefault());
        String today = dateFormat.format(new Date());

        String selectQuery = "SELECT * FROM " + TABLE_POINTAGES +
                " WHERE " + COL_POINT_DATE + " = ?" +
                " AND " + COL_POINT_TYPE + " = ?" +
                " ORDER BY " + COL_POINT_TIMESTAMP + " DESC" +
                " LIMIT 1";

        Cursor c = db.rawQuery(selectQuery, new String[]{today, POINTAGE_TYPE_DEPARTURE});
        if (c != null && c.moveToFirst()) {
            lastDeparture = cursorToPointage(c);
            Log.d(TAG, "Dernier pointage de départ aujourd'hui : " + lastDeparture.getEmployeeId() + ", " + lastDeparture.getType());
        } else {
            Log.w(TAG, "Aucun pointage de départ trouvé pour aujourd'hui");
        }
        if (c != null) {
            c.close();
        }
        db.close();
        return lastDeparture;
    }

    public List<Pointage> getPointagesForPeriod(String startDate, String endDate) {
        List<Pointage> pointages = new ArrayList<>();
        SQLiteDatabase db = this.getReadableDatabase();
        Cursor cursor = db.query(TABLE_POINTAGES, null,
                COL_POINT_DATE + " BETWEEN ? AND ?",
                new String[]{startDate, endDate}, null, null, COL_POINT_TIMESTAMP + " DESC");
        if (cursor.moveToFirst()) {
            do {
                Pointage pointage = cursorToPointage(cursor);
                pointages.add(pointage);
                Log.d(TAG, "Pointage période : ID=" + pointage.getId() + ", employee_id=" + pointage.getEmployeeId() + ", type=" + pointage.getType() + ", date=" + pointage.getDate());
            } while (cursor.moveToNext());
        } else {
            Log.w(TAG, "Aucun pointage trouvé pour la période : " + startDate + " à " + endDate);
        }
        cursor.close();
        db.close();
        return pointages;
    }

    public List<Pointage> getAllPointages() {
        List<Pointage> pointages = new ArrayList<>();
        SQLiteDatabase db = this.getReadableDatabase();
        Cursor cursor = db.query(TABLE_POINTAGES, null, null, null, null, null, COL_POINT_TIMESTAMP + " DESC");
        if (cursor.moveToFirst()) {
            do {
                Pointage pointage = cursorToPointage(cursor);
                pointages.add(pointage);
                Log.d(TAG, "Pointage local : ID=" + pointage.getId() + ", employee_id=" + pointage.getEmployeeId() + ", type=" + pointage.getType() + ", date=" + pointage.getDate());
            } while (cursor.moveToNext());
        } else {
            Log.w(TAG, "Aucun pointage trouvé dans la base locale");
        }
        cursor.close();
        db.close();
        Log.d(TAG, "Nombre total de pointages locaux : " + pointages.size());
        return pointages;
    }

    public long addSalaryRecord(SalaryRecord record) {
        if (record.getEmployeeId() == null || record.getEmployeeName() == null) {
            Log.e(TAG, "Erreur : employeeId ou employeeName est null");
            return -1;
        }
        if (record.getAmount() <= 0) {
            Log.e(TAG, "Erreur : montant du salaire invalide (amount=" + record.getAmount() + ")");
            return -1;
        }

        SQLiteDatabase db = this.getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put(COL_SAL_ID, record.getId() != null ? record.getId() : String.valueOf(System.currentTimeMillis()));
        values.put(COL_SAL_EMPLOYEE_ID, record.getEmployeeId());
        values.put(COL_SAL_EMPLOYEE_NAME, record.getEmployeeName());
        values.put(COL_SAL_TYPE, record.getType());
        values.put(COL_SAL_AMOUNT, record.getAmount());
        values.put(COL_SAL_HOURS_WORKED, record.getHoursWorked());
        values.put(COL_SAL_PERIOD, record.getPeriod());
        values.put(COL_SAL_DATE, record.getDate());
        values.put(COL_SAL_IS_SYNCED, record.isSynced() ? 1 : 0);

        Cursor cursor = db.query(TABLE_SALARIES, new String[]{COL_SAL_ID, COL_SAL_IS_SYNCED},
                COL_SAL_ID + "=?", new String[]{values.getAsString(COL_SAL_ID)}, null, null, null);
        long result;
        if (cursor.moveToFirst()) {
            int isSynced = cursor.getInt(cursor.getColumnIndexOrThrow(COL_SAL_IS_SYNCED));
            if (isSynced == 0) {
                result = db.update(TABLE_SALARIES, values, COL_SAL_ID + "=?", new String[]{values.getAsString(COL_SAL_ID)});
                Log.d(TAG, "Mise à jour salaire : ID=" + values.getAsString(COL_SAL_ID));
            } else {
                Log.w(TAG, "Saut de mise à jour : salaire synchronisé, ID=" + values.getAsString(COL_SAL_ID));
                result = -1;
            }
        } else {
            result = db.insert(TABLE_SALARIES, null, values);
            Log.d(TAG, "Salaire inséré : ID=" + values.getAsString(COL_SAL_ID));
        }
        cursor.close();
        db.close();
        return result;
    }

    public List<SalaryRecord> getUnsyncedSalaryRecords() {
        List<SalaryRecord> records = new ArrayList<>();
        SQLiteDatabase db = this.getReadableDatabase();
        Cursor cursor = db.query(TABLE_SALARIES, null, COL_SAL_IS_SYNCED + "=0",
                null, null, null, COL_SAL_DATE + " DESC");
        if (cursor.moveToFirst()) {
            do {
                SalaryRecord record = cursorToSalaryRecord(cursor);
                records.add(record);
                Log.d(TAG, "Enregistrement non synchronisé : ID=" + record.getId() +
                        ", employee_id=" + record.getEmployeeId() +
                        ", employee_name=" + record.getEmployeeName() +
                        ", type=" + record.getType() +
                        ", amount=" + record.getAmount());
            } while (cursor.moveToNext());
        }
        cursor.close();
        db.close();
        Log.d(TAG, "Nombre total d'enregistrements non synchronisés : " + records.size());
        return records;
    }

    public List<SalaryRecord> getSalaryRecordsForPeriod(String period) {
        List<SalaryRecord> records = new ArrayList<>();
        SQLiteDatabase db = this.getReadableDatabase();
        Cursor cursor = db.query(TABLE_SALARIES, null, COL_SAL_PERIOD + "=?",
                new String[]{period}, null, null, COL_SAL_DATE + " DESC");
        if (cursor.moveToFirst()) {
            do {
                records.add(cursorToSalaryRecord(cursor));
            } while (cursor.moveToNext());
        }
        cursor.close();
        db.close();
        return records;
    }

    // ✅ CORRECTION: Méthode getAllSalaryRecords avec logs détaillés
    public List<SalaryRecord> getAllSalaryRecords() {
        List<SalaryRecord> records = new ArrayList<>();
        SQLiteDatabase db = this.getReadableDatabase();
        Cursor cursor = db.query(TABLE_SALARIES, null, null, null, null, null, COL_SAL_DATE + " DESC");

        if (cursor.moveToFirst()) {
            do {
                SalaryRecord record = cursorToSalaryRecord(cursor);

                // Validation avant ajout
                if (record.getEmployeeId() != null &&
                        record.getEmployeeName() != null &&
                        !record.getEmployeeName().trim().isEmpty() &&
                        record.getAmount() > 0) {

                    records.add(record);
                    Log.d(TAG, "Record valide: ID=" + record.getId() +
                            ", employeeId=" + record.getEmployeeId() +
                            ", employeeName=" + record.getEmployeeName() +
                            ", type=" + record.getType() +
                            ", amount=" + record.getAmount() +
                            ", period=" + record.getPeriod() +
                            ", synced=" + record.isSynced());
                } else {
                    Log.w(TAG, "Record invalide ignoré: ID=" + record.getId() +
                            ", employeeId=" + record.getEmployeeId() +
                            ", employeeName=" + record.getEmployeeName() +
                            ", amount=" + record.getAmount());
                }
            } while (cursor.moveToNext());
        }

        cursor.close();
        db.close();

        Log.d(TAG, "Total records valides récupérés: " + records.size());
        return records;
    }


    public void markSalaryRecordAsSynced(String recordId) {
        SQLiteDatabase db = this.getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put(COL_SAL_IS_SYNCED, 1);
        db.update(TABLE_SALARIES, values, COL_SAL_ID + "=?", new String[]{recordId});
        db.close();
        Log.d(TAG, "Enregistrement de salaire marqué comme synchronisé avec ID: " + recordId);
    }

    private Employee cursorToEmployee(Cursor cursor) {
        Employee employee = new Employee();
        try {
            int idIndex = cursor.getColumnIndex(COL_EMP_ID);
            int nomIndex = cursor.getColumnIndex(COL_EMP_NOM);
            int prenomIndex = cursor.getColumnIndex(COL_EMP_PRENOM);
            int dateNaissanceIndex = cursor.getColumnIndex(COL_EMP_DATE_NAISSANCE);
            int lieuNaissanceIndex = cursor.getColumnIndex(COL_EMP_LIEU_NAISSANCE);
            int telephoneIndex = cursor.getColumnIndex(COL_EMP_TELEPHONE);
            int emailIndex = cursor.getColumnIndex(COL_EMP_EMAIL);
            int professionIndex = cursor.getColumnIndex(COL_EMP_PROFESSION);
            int typeIndex = cursor.getColumnIndex(COL_EMP_TYPE);
            int tauxHoraireIndex = cursor.getColumnIndex(COL_EMP_TAUX_HORAIRE);
            int fraisEcolageIndex = cursor.getColumnIndex(COL_EMP_FRAIS_ECOLAGE);
            int qrCodeIndex = cursor.getColumnIndex(COL_EMP_QR_CODE);
            int isActiveIndex = cursor.getColumnIndex(COL_EMP_IS_ACTIVE);
            int createdAtIndex = cursor.getColumnIndex(COL_EMP_CREATED_AT);

            if (idIndex != -1) employee.setId(cursor.getString(idIndex));
            if (nomIndex != -1) employee.setNom(cursor.getString(nomIndex));
            if (prenomIndex != -1) employee.setPrenom(cursor.getString(prenomIndex));
            if (dateNaissanceIndex != -1) employee.setDateNaissance(cursor.getString(dateNaissanceIndex));
            if (lieuNaissanceIndex != -1) employee.setLieuNaissance(cursor.getString(lieuNaissanceIndex));
            if (telephoneIndex != -1) employee.setTelephone(cursor.getString(telephoneIndex));
            if (emailIndex != -1) employee.setEmail(cursor.getString(emailIndex));
            if (professionIndex != -1) employee.setProfession(cursor.getString(professionIndex));
            if (typeIndex != -1) employee.setType(cursor.getString(typeIndex));
            if (tauxHoraireIndex != -1 && !cursor.isNull(tauxHoraireIndex)) employee.setTauxHoraire(cursor.getDouble(tauxHoraireIndex));
            if (fraisEcolageIndex != -1 && !cursor.isNull(fraisEcolageIndex)) employee.setFraisEcolage(cursor.getDouble(fraisEcolageIndex));
            if (qrCodeIndex != -1) employee.setQrCode(cursor.getString(qrCodeIndex));
            if (isActiveIndex != -1) employee.setActive(cursor.getInt(isActiveIndex) == 1);
            if (createdAtIndex != -1) employee.setCreatedAt(cursor.getLong(createdAtIndex));
        } catch (Exception e) {
            Log.e(TAG, "Erreur lors de l'analyse du curseur employé", e);
        }
        return employee;
    }

    private Pointage cursorToPointage(Cursor cursor) {
        Pointage pointage = new Pointage();
        try {
            int idIndex = cursor.getColumnIndex(COL_POINT_ID);
            int employeeIdIndex = cursor.getColumnIndex(COL_POINT_EMPLOYEE_ID);
            int employeeNameIndex = cursor.getColumnIndex(COL_POINT_EMPLOYEE_NAME);
            int typeIndex = cursor.getColumnIndex(COL_POINT_TYPE);
            int timestampIndex = cursor.getColumnIndex(COL_POINT_TIMESTAMP);
            int dateIndex = cursor.getColumnIndex(COL_POINT_DATE);

            if (idIndex != -1) pointage.setId(cursor.getString(idIndex));
            if (employeeIdIndex != -1) pointage.setEmployeeId(cursor.getString(employeeIdIndex));
            if (employeeNameIndex != -1) pointage.setEmployeeName(cursor.getString(employeeNameIndex));
            if (typeIndex != -1) pointage.setType(cursor.getString(typeIndex));
            if (timestampIndex != -1) pointage.setTimestamp(cursor.getLong(timestampIndex));
            if (dateIndex != -1) pointage.setDate(cursor.getString(dateIndex));
        } catch (Exception e) {
            Log.e(TAG, "Erreur lors de l'analyse du curseur pointage", e);
        }
        return pointage;
    }

    private SalaryRecord cursorToSalaryRecord(Cursor cursor) {
        SalaryRecord record = new SalaryRecord();
        try {
            int idIndex = cursor.getColumnIndex(COL_SAL_ID);
            int employeeIdIndex = cursor.getColumnIndex(COL_SAL_EMPLOYEE_ID);
            int employeeNameIndex = cursor.getColumnIndex(COL_SAL_EMPLOYEE_NAME);
            int typeIndex = cursor.getColumnIndex(COL_SAL_TYPE);
            int amountIndex = cursor.getColumnIndex(COL_SAL_AMOUNT);
            int hoursWorkedIndex = cursor.getColumnIndex(COL_SAL_HOURS_WORKED);
            int periodIndex = cursor.getColumnIndex(COL_SAL_PERIOD);
            int dateIndex = cursor.getColumnIndex(COL_SAL_DATE);
            int isSyncedIndex = cursor.getColumnIndex(COL_SAL_IS_SYNCED);

            if (idIndex != -1) record.setId(cursor.getString(idIndex));
            if (employeeIdIndex != -1) record.setEmployeeId(cursor.getString(employeeIdIndex));
            if (employeeNameIndex != -1) record.setEmployeeName(cursor.getString(employeeNameIndex));
            if (typeIndex != -1) record.setType(cursor.getString(typeIndex));
            if (amountIndex != -1) record.setAmount(cursor.getDouble(amountIndex));
            if (hoursWorkedIndex != -1 && !cursor.isNull(hoursWorkedIndex)) record.setHoursWorked(cursor.getDouble(hoursWorkedIndex));
            if (periodIndex != -1) record.setPeriod(cursor.getString(periodIndex));
            if (dateIndex != -1) record.setDate(cursor.getLong(dateIndex));
            if (isSyncedIndex != -1) record.setSynced(cursor.getInt(isSyncedIndex) == 1);
        } catch (Exception e) {
            Log.e(TAG, "Erreur lors de l'analyse du curseur salaire", e);
        }
        return record;
    }

    public void clearDatabase() {
        SQLiteDatabase db = this.getWritableDatabase();
        db.beginTransaction();
        try {
            db.delete(TABLE_SALARIES, null, null);
            db.delete(TABLE_POINTAGES, null, null);
            db.delete(TABLE_EMPLOYEES, null, null);
            db.setTransactionSuccessful();
            Log.d(TAG, "Base de données vidée");
        } finally {
            db.endTransaction();
            db.close();
        }
    }
    // ✅ CORRECTION: Méthode addOrUpdateSalaryRecord améliorée
    public long addOrUpdateSalaryRecord(SalaryRecord record) {
        if (record.getEmployeeId() == null || record.getEmployeeName() == null || record.getAmount() <= 0) {
            Log.w(TAG, "Record ignoré (invalide) : ID=" + record.getId() +
                    ", employeeId=" + record.getEmployeeId() +
                    ", employeeName=" + record.getEmployeeName() +
                    ", amount=" + record.getAmount());
            return -1;
        }

        SQLiteDatabase db = this.getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put(COL_SAL_ID, record.getId());
        values.put(COL_SAL_EMPLOYEE_ID, record.getEmployeeId());
        values.put(COL_SAL_EMPLOYEE_NAME, record.getEmployeeName());
        values.put(COL_SAL_TYPE, record.getType());
        values.put(COL_SAL_AMOUNT, record.getAmount());
        values.put(COL_SAL_HOURS_WORKED, record.getHoursWorked());
        values.put(COL_SAL_PERIOD, record.getPeriod());
        values.put(COL_SAL_DATE, record.getDate());
        values.put(COL_SAL_IS_SYNCED, record.isSynced() ? 1 : 0);

        Cursor cursor = db.query(TABLE_SALARIES, new String[]{COL_SAL_ID},
                COL_SAL_ID + "=?", new String[]{record.getId()},
                null, null, null);

        long result;
        if (cursor.moveToFirst()) {
            // Mise à jour
            result = db.update(TABLE_SALARIES, values, COL_SAL_ID + "=?", new String[]{record.getId()});
            Log.d(TAG, "Record mis à jour: " + record.getId() + ", amount=" + record.getAmount());
        } else {
            // Insertion
            result = db.insert(TABLE_SALARIES, null, values);
            Log.d(TAG, "Record inséré: " + record.getId() + ", amount=" + record.getAmount());
        }

        cursor.close();
        db.close();
        return result;
    }



    public long mergeSalaryRecord(SalaryRecord record) {
        if (record.getEmployeeId() == null || record.getEmployeeName() == null || record.getAmount() <= 0) {
            Log.w(TAG, "Record serveur ignoré (invalide) : " + record.getId());
            return -1;
        }

        SQLiteDatabase db = this.getWritableDatabase();
        Cursor cursor = db.query(TABLE_SALARIES, null, COL_SAL_ID + "=?",
                new String[]{record.getId()}, null, null, null);

        long result;
        if (cursor.moveToFirst()) {
            // Record existant, fusionner
            SalaryRecord local = cursorToSalaryRecord(cursor);
            ContentValues values = new ContentValues();
            values.put(COL_SAL_EMPLOYEE_ID, local.getEmployeeId()); // garder l'ID local
            values.put(COL_SAL_EMPLOYEE_NAME, record.getEmployeeName() != null ? record.getEmployeeName() : local.getEmployeeName());
            values.put(COL_SAL_TYPE, record.getType() != null ? record.getType() : local.getType());
            values.put(COL_SAL_AMOUNT, record.getAmount() > 0 ? record.getAmount() : local.getAmount());
            values.put(COL_SAL_HOURS_WORKED, record.getHoursWorked() != null ? record.getHoursWorked() : local.getHoursWorked());
            values.put(COL_SAL_PERIOD, record.getPeriod() != null ? record.getPeriod() : local.getPeriod());
            values.put(COL_SAL_DATE, record.getDate() != 0 ? record.getDate() : local.getDate());
            values.put(COL_SAL_IS_SYNCED, 1); // serveur = synchronisé

            result = db.update(TABLE_SALARIES, values, COL_SAL_ID + "=?", new String[]{record.getId()});
            Log.d(TAG, "Record fusionné : " + record.getId());
        } else {
            // Record inexistant, insertion
            ContentValues values = new ContentValues();
            values.put(COL_SAL_ID, record.getId());
            values.put(COL_SAL_EMPLOYEE_ID, record.getEmployeeId());
            values.put(COL_SAL_EMPLOYEE_NAME, record.getEmployeeName());
            values.put(COL_SAL_TYPE, record.getType());
            values.put(COL_SAL_AMOUNT, record.getAmount());
            values.put(COL_SAL_HOURS_WORKED, record.getHoursWorked());
            values.put(COL_SAL_PERIOD, record.getPeriod());
            values.put(COL_SAL_DATE, record.getDate());
            values.put(COL_SAL_IS_SYNCED, 1);

            result = db.insert(TABLE_SALARIES, null, values);
            Log.d(TAG, "Record inséré : " + record.getId());
        }

        cursor.close();
        db.close();
        return result;
    }
    public SalaryRecord getSalaryRecordById(String id) {
        SQLiteDatabase db = this.getReadableDatabase();
        Cursor cursor = db.query(TABLE_SALARIES, null, COL_SAL_ID + "=?",
                new String[]{id}, null, null, null);
        SalaryRecord record = null;
        if (cursor.moveToFirst()) {
            record = cursorToSalaryRecord(cursor);
        }
        cursor.close();
        db.close();
        return record;
    }
    public void syncServerSalaryRecords(JSONArray serverRecords) {
        new Thread(() -> {
            if (serverRecords == null || serverRecords.length() == 0) {
                Log.w(TAG, "Aucun enregistrement serveur à synchroniser");
                return;
            }

            List<SalaryRecord> validRecords = new ArrayList<>();

            for (int i = 0; i < serverRecords.length(); i++) {
                try {
                    JSONObject obj = serverRecords.getJSONObject(i);
                    String id = obj.optString("id", null);
                    String employeeId = obj.optString("employee_id", null);
                    String employeeName = obj.optString("employee_name", null);
                    String type = obj.optString("type", null);
                    double amount = obj.optDouble("amount", -1);
                    Double hoursWorked = obj.has("hours_worked") ? obj.getDouble("hours_worked") : null;
                    String period = obj.optString("period", null);
                    long date = obj.optLong("date", 0);

                    // ✅ Validation minimale
                    if (id != null && employeeId != null && employeeName != null && type != null && amount > 0) {
                        SalaryRecord record = new SalaryRecord();
                        record.setId(id);
                        record.setEmployeeId(employeeId);
                        record.setEmployeeName(employeeName);
                        record.setType(type);
                        record.setAmount(amount);
                        record.setHoursWorked(hoursWorked);
                        record.setPeriod(period);
                        record.setDate(date);
                        record.setSynced(true); // serveur = déjà synchronisé

                        validRecords.add(record);
                    } else {
                        Log.w(TAG, "Enregistrement serveur ignoré (invalide) : " + obj);
                    }
                } catch (Exception e) {
                    Log.e(TAG, "Erreur lors de la lecture d'un enregistrement serveur", e);
                }
            }

            // Insérer ou fusionner chaque enregistrement
            for (SalaryRecord record : validRecords) {
                mergeSalaryRecord(record); // utilise ta méthode existante
            }

            Log.d(TAG, "Synchronisation serveur terminée : " + validRecords.size() + " enregistrements traités");
        }).start();
    }
    // ✅ NOUVEAU: Méthode pour nettoyer les records invalides
    public void cleanInvalidSalaryRecords() {
        SQLiteDatabase db = this.getWritableDatabase();

        // Supprimer les records avec employeeId null
        int deleted1 = db.delete(TABLE_SALARIES, COL_SAL_EMPLOYEE_ID + " IS NULL OR " + COL_SAL_EMPLOYEE_ID + " = ''", null);

        // Supprimer les records avec employeeName null/vide
        int deleted2 = db.delete(TABLE_SALARIES, COL_SAL_EMPLOYEE_NAME + " IS NULL OR " + COL_SAL_EMPLOYEE_NAME + " = '' OR " + COL_SAL_EMPLOYEE_NAME + " = ' '", null);

        // Supprimer les records avec amount <= 0
        int deleted3 = db.delete(TABLE_SALARIES, COL_SAL_AMOUNT + " <= 0", null);

        db.close();

        int totalDeleted = deleted1 + deleted2 + deleted3;
        if (totalDeleted > 0) {
            Log.i(TAG, "Nettoyage base: " + totalDeleted + " records invalides supprimés");
        }}
    // ✅ NOUVELLE MÉTHODE: Récupérer tous les pointages d'un employé spécifique
    public List<Pointage> getAllPointagesForEmployee(String employeeId) {
        List<Pointage> pointages = new ArrayList<>();
        SQLiteDatabase db = this.getReadableDatabase();

        Cursor cursor = db.query(TABLE_POINTAGES, null,
                COL_POINT_EMPLOYEE_ID + "=?",
                new String[]{employeeId},
                null, null,
                COL_POINT_TIMESTAMP + " ASC"); // ✅ Trier par ordre chronologique

        if (cursor.moveToFirst()) {
            do {
                Pointage pointage = cursorToPointage(cursor);
                pointages.add(pointage);
                Log.d(TAG, "Pointage employé " + employeeId + ": type=" + pointage.getType() +
                        ", date=" + pointage.getDate());
            } while (cursor.moveToNext());
        }

        cursor.close();
        db.close();

        Log.d(TAG, "Total pointages pour employé " + employeeId + ": " + pointages.size());
        return pointages;
    }public void resetPointagesForEmployee(String employeeId, String startDate, String endDate) {
        SQLiteDatabase db = this.getWritableDatabase();
        db.execSQL("DELETE FROM pointages WHERE employee_id = ? AND date BETWEEN ? AND ?",
                new String[]{ employeeId, startDate, endDate });
    }
}
