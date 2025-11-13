package com.trackingsystem.apps.models;

public class Pointage {
    private String id;
    private String employeeId;
    private String employeeName;
    private String type; // "arrivee" ou "sortie"
    private long timestamp;
    private String date;

    public Pointage() {}

    // Getters
    public String getId() { return id; }
    public String getEmployeeId() { return employeeId; }
    public String getEmployeeName() { return employeeName; }
    public String getType() { return type; }
    public long getTimestamp() { return timestamp; }
    public String getDate() { return date; }

    // Setters
    public void setId(String id) { this.id = id; }
    public void setEmployeeId(String employeeId) { this.employeeId = employeeId; }
    public void setEmployeeName(String employeeName) { this.employeeName = employeeName; }
    public void setType(String type) { this.type = type; }
    public void setTimestamp(long timestamp) { this.timestamp = timestamp; }
    public void setDate(String date) { this.date = date; }
}