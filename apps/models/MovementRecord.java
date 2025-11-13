package com.trackingsystem.apps.models;

public class MovementRecord {
    private String id;
    private String employeeId;
    private String nom; // Ajout du nom de l'employé
    private String prenom; // Ajout du prénom de l'employé
    private String zoneName;
    private String type; // Ajout du type de mouvement (arrivee ou sortie)
    private long timestamp;
    private long duration;
    private double x;
    private double y;

    public MovementRecord() {}

    // Getters
    public String getId() { return id; }
    public String getEmployeeId() { return employeeId; }
    public String getNom() { return nom; }
    public String getPrenom() { return prenom; }
    public String getZoneName() { return zoneName; }
    public String getType() { return type; }
    public long getTimestamp() { return timestamp; }
    public long getDuration() { return duration; }
    public double getX() { return x; }
    public double getY() { return y; }

    // Setters
    public void setId(String id) { this.id = id; }
    public void setEmployeeId(String employeeId) { this.employeeId = employeeId; }
    public void setNom(String nom) { this.nom = nom; }
    public void setPrenom(String prenom) { this.prenom = prenom; }
    public void setZoneName(String zoneName) { this.zoneName = zoneName; }
    public void setType(String type) { this.type = type; }
    public void setTimestamp(long timestamp) { this.timestamp = timestamp; }
    public void setDuration(long duration) { this.duration = duration; }
    public void setX(double x) { this.x = x; }
    public void setY(double y) { this.y = y; }
}
