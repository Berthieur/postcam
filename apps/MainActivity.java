package com.trackingsystem.apps;

import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.util.Log;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.cardview.widget.CardView;
import androidx.core.view.WindowCompat;

import com.google.android.material.floatingactionbutton.FloatingActionButton;
import com.trackingsystem.apps.database.DatabaseHelper;
import com.trackingsystem.apps.models.Employee;
import com.trackingsystem.apps.models.EmployeesResponse;
import com.trackingsystem.apps.network.ApiClient;
import com.trackingsystem.apps.network.ApiService;

import java.util.List;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class MainActivity extends AppCompatActivity {

    private static final String TAG = "MainActivity";
    private DatabaseHelper databaseHelper;
    private SharedPreferences sharedPreferences;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        supportRequestWindowFeature(WindowCompat.FEATURE_ACTION_BAR_OVERLAY);
        if (getSupportActionBar() != null) {
            getSupportActionBar().hide();
        }
        setContentView(R.layout.activity_main);

        sharedPreferences = getSharedPreferences("TrackingApp", MODE_PRIVATE);
        databaseHelper = new DatabaseHelper(this);

        // Vérifie login
        if (!isUserLoggedIn()) {
            startActivity(new Intent(this, LoginActivity.class));
            finish();
            return;
        }

        initializeViews();
        syncFromServer();
    }

    /**
     * Initialisation des vues et listeners
     */
    private void initializeViews() {
        CardView scanQRCard = findViewById(R.id.scanQRCard);
        CardView trackingCard = findViewById(R.id.trackingCard);
        CardView salaryCard = findViewById(R.id.salaryCard);
        CardView statisticsCard = findViewById(R.id.statisticsCard);
        CardView employeeListCard = findViewById(R.id.employeeListCard);
        CardView pointageReceiverCard = findViewById(R.id.pointageReceiverCard);
        CardView esp32CamCard = findViewById(R.id.esp32CamCard);
        FloatingActionButton logoutFab = findViewById(R.id.logoutFab);
        FloatingActionButton iaChatFab = findViewById(R.id.iaChatFab);

        scanQRCard.setOnClickListener(v -> startActivity(new Intent(MainActivity.this, QRScanActivity.class)));
        esp32CamCard.setOnClickListener(v -> startActivity(new Intent(MainActivity.this, Esp32CamActivity.class)));
        trackingCard.setOnClickListener(v -> startActivity(new Intent(MainActivity.this, TrackingActivity.class)));
        salaryCard.setOnClickListener(v -> startActivity(new Intent(MainActivity.this, SalaryManagementActivity.class)));
        statisticsCard.setOnClickListener(v -> startActivity(new Intent(MainActivity.this, StatisticsActivity.class)));
        employeeListCard.setOnClickListener(v -> startActivity(new Intent(MainActivity.this, EmployeeListActivity.class)));
        pointageReceiverCard.setOnClickListener(v -> startActivity(new Intent(MainActivity.this, PointageReceiverActivity.class)));
        iaChatFab.setOnClickListener(v -> startActivity(new Intent(MainActivity.this, IAChatActivity.class)));
        logoutFab.setOnClickListener(v -> logout());
    }

    /**
     * Vérifie si utilisateur connecté
     */
    private boolean isUserLoggedIn() {
        return sharedPreferences.getBoolean("isLoggedIn", false);
    }

    /**
     * Déconnexion
     */
    private void logout() {
        SharedPreferences.Editor editor = sharedPreferences.edit();
        editor.putBoolean("isLoggedIn", false);
        editor.apply();
        startActivity(new Intent(this, LoginActivity.class));
        finish();
    }

    /**
     * Synchronisation employés depuis le serveur
     */
    private void syncFromServer() {
        ApiService apiService = ApiClient.getClient().create(ApiService.class);
        Call<EmployeesResponse> call = apiService.getAllEmployees();

        call.enqueue(new Callback<EmployeesResponse>() {
            @Override
            public void onResponse(Call<EmployeesResponse> call, Response<EmployeesResponse> response) {
                if (response.isSuccessful() && response.body() != null) {
                    EmployeesResponse body = response.body();

                    if (body.isSuccess() && body.getEmployees() != null) {
                        List<Employee> employees = body.getEmployees();
                        Log.d(TAG, "Synchronisation: " + employees.size() + " employés reçus");

                        // Vider et remplir la base locale
                        databaseHelper.clearDatabase();
                        for (Employee emp : employees) {
                            databaseHelper.addEmployee(emp);
                        }

                        Toast.makeText(MainActivity.this,
                                "Synchronisation réussie: " + employees.size() + " employés",
                                Toast.LENGTH_SHORT).show();
                    } else {
                        Log.e(TAG, "Réponse non success: " + body.getMessage());
                        Toast.makeText(MainActivity.this,
                                "Erreur: " + body.getMessage(),
                                Toast.LENGTH_SHORT).show();
                    }
                } else {
                    Log.e(TAG, "Erreur HTTP: " + response.code());
                    Toast.makeText(MainActivity.this,
                            "Erreur serveur (code " + response.code() + ")",
                            Toast.LENGTH_SHORT).show();
                }
            }

            @Override
            public void onFailure(Call<EmployeesResponse> call, Throwable t) {
                Log.e(TAG, "Erreur réseau: " + t.getMessage(), t);
                Toast.makeText(MainActivity.this,
                        "Erreur réseau: " + t.getMessage(),
                        Toast.LENGTH_SHORT).show();
            }
        });
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        // Nettoyage si nécessaire
    }
}