// Fichier : Employee.java
package com.trackingsystem.apps.models;

import com.google.gson.Gson;
import com.google.gson.annotations.SerializedName;
import java.io.Serializable;

/**
 * Classe représentant un employé ou un étudiant.
 * Sérialisable pour être passée entre activités.
 */
public class Employee implements Serializable {

    private static final long serialVersionUID = 1L;

    // Champs
    @SerializedName("id")
    private String id;

    @SerializedName("nom")
    private String nom;

    @SerializedName("prenom")
    private String prenom;

    @SerializedName("date_naissance")
    private String dateNaissance;

    @SerializedName("lieu_naissance")
    private String lieuNaissance;

    @SerializedName("telephone")
    private String telephone;

    @SerializedName("email")
    private String email;

    @SerializedName("profession")
    private String profession;

    @SerializedName("type") // "employe" ou "etudiant"
    private String type;

    @SerializedName("taux_horaire")
    private Double tauxHoraire; // Pour employés

    @SerializedName("frais_ecolage")
    private Double fraisEcolage; // Pour étudiants

    @SerializedName("qr_code")
    private String qrCode;

    @SerializedName("is_active")
    private int isActive;

    @SerializedName("created_at")
    private long createdAt;

    @SerializedName("current_zone")
    private String currentZone;

    // Ajout pour les coordonnées
    @SerializedName("last_position_x")
    private Float lastPositionX;

    @SerializedName("last_position_y")
    private Float lastPositionY;

    // Ajout pour le RSSI (force du signal)
    @SerializedName("last_rssi")
    private Integer lastRssi;

    // Constructeur par défaut
    public Employee() {}
    public Integer getLastRssi() { return lastRssi; }
    public void setLastRssi(Integer lastRssi) { this.lastRssi = lastRssi; }
    // --- Getters ---
    public String getId() { return id; }
    public String getNom() { return nom; }
    public String getPrenom() { return prenom; }
    public String getDateNaissance() { return dateNaissance; }
    public String getLieuNaissance() { return lieuNaissance; }
    public String getTelephone() { return telephone; }
    public String getEmail() { return email; }
    public String getProfession() { return profession; }
    public String getType() { return type; }
    public Double getTauxHoraire() { return tauxHoraire; }
    public Double getFraisEcolage() { return fraisEcolage; }
    public String getQrCode() { return qrCode; }
    public boolean isActive() { return isActive == 1; }
    public long getCreatedAt() { return createdAt; }
    public String getCurrentZone() { return currentZone; }
    public Float getLastPositionX() { return lastPositionX; }
    public Float getLastPositionY() { return lastPositionY; }

    // --- Setters ---
    public void setId(String id) { this.id = id; }
    public void setNom(String nom) { this.nom = nom; }
    public void setPrenom(String prenom) { this.prenom = prenom; }
    public void setDateNaissance(String dateNaissance) { this.dateNaissance = dateNaissance; }
    public void setLieuNaissance(String lieuNaissance) { this.lieuNaissance = lieuNaissance; }
    public void setTelephone(String telephone) { this.telephone = telephone; }
    public void setEmail(String email) { this.email = email; }
    public void setProfession(String profession) { this.profession = profession; }
    public void setType(String type) { this.type = type; }
    public void setTauxHoraire(Double tauxHoraire) { this.tauxHoraire = tauxHoraire; }
    public void setFraisEcolage(Double fraisEcolage) { this.fraisEcolage = fraisEcolage; }
    public void setQrCode(String qrCode) { this.qrCode = qrCode; }
    public void setActive(boolean active) { this.isActive = active ? 1 : 0; }
    public void setCreatedAt(long createdAt) { this.createdAt = createdAt; }
    public void setCurrentZone(String currentZone) { this.currentZone = currentZone; }
    public void setLastPositionX(Float lastPositionX) { this.lastPositionX = lastPositionX; }
    public void setLastPositionY(Float lastPositionY) { this.lastPositionY = lastPositionY; }

    // Convertit l'objet en JSON
    public String getJsonString() {
        return new Gson().toJson(this);
    }
}
