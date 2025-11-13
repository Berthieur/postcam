package com.trackingsystem.apps.models;

import com.google.gson.annotations.SerializedName;
import java.util.ArrayList;
import java.util.List;

public class SalaryResponse {

    @SerializedName("success")
    private boolean success;

    @SerializedName("message")
    private String message;

    // Corrigé pour correspondre au JSON backend : "salaries"
    @SerializedName("salaries")
    private List<SalaryRecord> salaries = new ArrayList<>(); // Initialisation pour éviter null

    public boolean isSuccess() {
        return success;
    }

    public void setSuccess(boolean success) {
        this.success = success;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public List<SalaryRecord> getSalaries() {
        return salaries != null ? salaries : new ArrayList<>(); // Sécurité supplémentaire
    }

    public void setSalaries(List<SalaryRecord> salaries) {
        this.salaries = salaries != null ? salaries : new ArrayList<>();
    }
}