package com.trackingsystem.apps.models;

public class BuzzerRequest {
    private String employeeId;
    private String macAddress;
    private int duration;
    private String alertType;
    
    public BuzzerRequest() {}
    
    public BuzzerRequest(String employeeId, String macAddress, int duration, String alertType) {
        this.employeeId = employeeId;
        this.macAddress = macAddress;
        this.duration = duration;
        this.alertType = alertType;
    }
    
    // Getters
    public String getEmployeeId() { return employeeId; }
    public String getMacAddress() { return macAddress; }
    public int getDuration() { return duration; }
    public String getAlertType() { return alertType; }
    
    // Setters
    public void setEmployeeId(String employeeId) { this.employeeId = employeeId; }
    public void setMacAddress(String macAddress) { this.macAddress = macAddress; }
    public void setDuration(int duration) { this.duration = duration; }
    public void setAlertType(String alertType) { this.alertType = alertType; }
}