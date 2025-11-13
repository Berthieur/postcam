package com.trackingsystem.apps.utils;

import com.trackingsystem.apps.models.Employee;

import org.json.JSONException;
import org.json.JSONObject;

public class QRCodeUtils {

    public static String generateQRData(Employee employee) throws JSONException {
        JSONObject qrData = new JSONObject();
        qrData.put("id", employee.getId());
        qrData.put("nom", employee.getNom());
        qrData.put("prenom", employee.getPrenom());
        qrData.put("type", employee.getType());
        return qrData.toString();
    }

    public static Employee parseQRCode(String qrData) throws JSONException {
        JSONObject jsonObject = new JSONObject(qrData);
        Employee employee = new Employee();
        employee.setId(jsonObject.getString("id"));
        employee.setNom(jsonObject.getString("nom"));
        employee.setPrenom(jsonObject.getString("prenom"));
        employee.setType(jsonObject.getString("type"));
        return employee;
    }
}