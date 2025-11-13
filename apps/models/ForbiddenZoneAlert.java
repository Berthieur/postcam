package com.trackingsystem.apps.models;

public class ForbiddenZoneAlert {
    private String employeeId;
    private String employeeName;
    private String zoneName;
    private long timestamp;
    private double x;
    private double y;
    
    public ForbiddenZoneAlert() {}
    
    public ForbiddenZoneAlert(String employeeId, String employeeName, String zoneName) {
        this.employeeId = employeeId;
        this.employeeName = employeeName;
        this.zoneName = zoneName;
        this.timestamp = System.currentTimeMillis();
    }
    
    // Getters
    public String getEmployeeId() { return employeeId; }
    public String getEmployeeName() { return employeeName; }
    public String getZoneName() { return zoneName; }
    public long getTimestamp() { return timestamp; }
    public double getX() { return x; }
    public double getY() { return y; }
    
    // Setters
    public void setEmployeeId(String employeeId) { this.employeeId = employeeId; }
    public void setEmployeeName(String employeeName) { this.employeeName = employeeName; }
    public void setZoneName(String zoneName) { this.zoneName = zoneName; }
    public void setTimestamp(long timestamp) { this.timestamp = timestamp; }
    public void setX(double x) { this.x = x; }
    public void setY(double y) { this.y = y; }
}