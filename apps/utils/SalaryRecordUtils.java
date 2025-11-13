package com.trackingsystem.apps.utils;

import com.trackingsystem.apps.models.SalaryRecord;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

public class SalaryRecordUtils {

    /**
     * Crée un enregistrement valide avec date actuelle
     */
    public static SalaryRecord createValidRecord(String employeeId, String employeeName, String type, double amount, Double hoursWorked, String period) {
        SalaryRecord record = new SalaryRecord();
        record.setId(UUID.randomUUID().toString());
        record.setEmployeeId(employeeId);
        record.setEmployeeName(employeeName);
        record.setType(type);
        record.setAmount(amount);
        record.setHoursWorked(hoursWorked);
        record.setPeriod(period);

        // Date actuelle en millisecondes
        record.setDate(System.currentTimeMillis());

        // Non synchronisé pour le moment
        record.setSynced(false);

        return record;
    }

    /**
     * Corrige une liste d'enregistrements invalides pour les rendre acceptables par le serveur
     */
    public static List<SalaryRecord> correctInvalidRecords(List<SalaryRecord> oldRecords) {
        List<SalaryRecord> corrected = new ArrayList<>();

        for (SalaryRecord rec : oldRecords) {
            // Vérifie type et montant minimal
            if (rec.getType() == null || rec.getType().isEmpty()) {
                rec.setType("salaire"); // valeur par défaut
            }
            if (rec.getAmount() <= 0) {
                rec.setAmount(1000.0); // valeur minimale
            }

            // Corrige date si invalide (date dans le futur)
            long now = System.currentTimeMillis();
            if (rec.getDate() > now || rec.getDate() < 0) {
                rec.setDate(now);
            }

            // ID valide ?
            if (rec.getId() == null || rec.getId().isEmpty()) {
                rec.setId(UUID.randomUUID().toString());
            }

            // Ajoute à la liste corrigée
            rec.setSynced(false);
            corrected.add(rec);
        }

        return corrected;
    }
}
