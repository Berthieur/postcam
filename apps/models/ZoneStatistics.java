package com.trackingsystem.apps.models;

public class ZoneStatistics {
    private String zoneName;
    private float timeSpent;
    private int visitCount;
    private String employeeId;
    
    public ZoneStatistics() {}
    
    // Getters
    public String getZoneName() { return zoneName; }
    public float getTimeSpent() { return timeSpent; }
    public int getVisitCount() { return visitCount; }
    public String getEmployeeId() { return employeeId; }
    
    // Setters
    public void setZoneName(String zoneName) { this.zoneName = zoneName; }
    public void setTimeSpent(float timeSpent) { this.timeSpent = timeSpent; }
    public void setVisitCount(int visitCount) { this.visitCount = visitCount; }
    public void setEmployeeId(String employeeId) { this.employeeId = employeeId; }
}