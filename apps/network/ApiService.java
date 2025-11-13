package com.trackingsystem.apps.network;

import com.trackingsystem.apps.models.*;

import java.util.List;

import retrofit2.Call;
import retrofit2.http.*;

public interface ApiService {

    @POST("api/login")
    Call<LoginResponse> login(@Body LoginRequest loginRequest);

    @POST("api/employees")
    Call<ApiResponse> registerEmployee(@Body Employee employee);

    // ✅ Corrigé : utilise le wrapper EmployeesResponse
    @GET("api/employees")
    Call<EmployeesResponse> getAllEmployees();

    @GET("api/employees/active")
    Call<EmployeesResponse> getActiveEmployees();

    @GET("api/employees/{id}/position")
    Call<Employee> getEmployeePosition(@Path("id") String employeeId);

    @POST("api/salary")
    Call<ApiResponse> saveSalaryRecord(@Body SalaryRecord salaryRecord);

    @GET("api/salary/history")
    Call<SalaryResponse> getSalaryHistory();

    @GET("api/statistics/zones/{employeeId}")
    Call<List<ZoneStatistics>> getZoneStatistics(@Path("employeeId") String employeeId);

    @GET("api/movements/{employeeId}")
    Call<List<MovementRecord>> getMovementHistory(@Path("employeeId") String employeeId);

    @POST("api/alerts/forbidden-zone")
    Call<ApiResponse> reportForbiddenZoneEntry(@Body ForbiddenZoneAlert alert);

    @GET("api/esp32/status")
    Call<ESP32Status> getESP32Status();

    @POST("api/esp32/buzzer")
    Call<ApiResponse> activateBuzzer(@Body BuzzerRequest request);

    @PUT("api/employees/{id}")
    Call<ApiResponse> updateEmployee(@Path("id") String id, @Body Employee employee);

    @DELETE("api/employees/{id}")
    Call<ApiResponse> deleteEmployee(@Path("id") String id);
    // Enregistrer un pointage (arrivée/sortie)
    @POST("api/pointages")
    Call<ApiResponse> addPointage(@Body Pointage pointage);

    // Récupérer l’historique des pointages
    @GET("api/pointages/history")
    Call<List<Pointage>> getPointageHistory();
    @POST("api/movements")
    Call<ApiResponse> sendMovement(@Body MovementRecord movement);

    @GET("api/movements/last")
    Call<MovementRecord> getLastMovement();

}
