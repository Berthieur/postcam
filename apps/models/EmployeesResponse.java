package com.trackingsystem.apps.models;

import com.google.gson.annotations.SerializedName;
import java.util.List;

public class EmployeesResponse {
    @SerializedName("success")
    private boolean success;

    @SerializedName("message")
    private String message;

    @SerializedName("employees")
    private List<Employee> employees;

    public boolean isSuccess() {
        return success;
    }

    public String getMessage() {
        return message;
    }

    public List<Employee> getEmployees() {
        return employees;
    }
}
