package com.trackingsystem.apps.models;

public class LoginResponse {
    private boolean success;
    private String token;
    private String message;
    
    public boolean isSuccess() { return success; }
    public String getToken() { return token; }
    public String getMessage() { return message; }
    
    public void setSuccess(boolean success) { this.success = success; }
    public void setToken(String token) { this.token = token; }
    public void setMessage(String message) { this.message = message; }
}