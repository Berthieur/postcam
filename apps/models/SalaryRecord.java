package com.trackingsystem.apps.models;

import com.google.gson.annotations.SerializedName;

public class SalaryRecord {

    @SerializedName("id")
    private String id;

    @SerializedName("employee_id")   // ⚠️ NOM EXACT du backend
    private String employeeId;

    @SerializedName("employee_name")
    private String employeeName;

    @SerializedName("type")          // "salaire" ou "ecolage"
    private String type;

    @SerializedName("amount")
    private double amount;

    @SerializedName("hours_worked")
    private Double hoursWorked;      // Peut être null si salaire fixe

    @SerializedName("period")        // Format "yyyy-MM"
    private String period;

    @SerializedName("date")          // Timestamp en millisecondes
    private long date;

    // ⚠️ Ne pas annoter isSynced, il n'existe pas dans le JSON du serveur
    private boolean isSynced;

    // ===============================
    // ✅ Constructeurs
    // ===============================

    public SalaryRecord() {
        this.isSynced = false;
    }

    public SalaryRecord(String id, String employeeId, String employeeName, String type,
                        double amount, Double hoursWorked, String period, long date, boolean isSynced) {
        this.id = id;
        this.employeeId = employeeId;
        this.employeeName = employeeName;
        this.type = type;
        this.amount = amount;
        this.hoursWorked = hoursWorked;
        this.period = period;
        this.date = date;
        this.isSynced = isSynced;
    }

    // ===============================
    // ✅ Getters
    // ===============================

    public String getId() { return id; }
    public String getEmployeeId() { return employeeId; }
    public String getEmployeeName() { return employeeName; }
    public String getType() { return type; }
    public double getAmount() { return amount; }
    public Double getHoursWorked() { return hoursWorked; }
    public String getPeriod() { return period; }
    public long getDate() { return date; }
    public boolean isSynced() { return isSynced; }

    // ===============================
    // ✅ Setters
    // ===============================

    public void setId(String id) { this.id = id; }
    public void setEmployeeId(String employeeId) { this.employeeId = employeeId; }
    public void setEmployeeName(String employeeName) { this.employeeName = employeeName; }
    public void setType(String type) { this.type = type; }
    public void setAmount(double amount) { this.amount = amount; }
    public void setHoursWorked(Double hoursWorked) { this.hoursWorked = hoursWorked; }
    public void setPeriod(String period) { this.period = period; }
    public void setDate(long date) { this.date = date; }
    public void setSynced(boolean synced) { isSynced = synced; }

    // ===============================
    // ✅ Pour debug (affichage JSON style)
    // ===============================

    @Override
    public String toString() {
        return "SalaryRecord{" +
                "id='" + id + '\'' +
                ", employeeId='" + employeeId + '\'' +
                ", employeeName='" + employeeName + '\'' +
                ", type='" + type + '\'' +
                ", amount=" + amount +
                ", hoursWorked=" + hoursWorked +
                ", period='" + period + '\'' +
                ", date=" + date +
                ", isSynced=" + isSynced +
                '}';
    }
}
