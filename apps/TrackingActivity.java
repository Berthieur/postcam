package com.trackingsystem.apps;

import android.os.Bundle;
import android.os.Handler;
import android.widget.TextView;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.WindowCompat;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.trackingsystem.apps.adapters.EmployeeAdapter;
import com.trackingsystem.apps.models.Employee;
import com.trackingsystem.apps.models.EmployeesResponse;
import com.trackingsystem.apps.network.ApiClient;
import com.trackingsystem.apps.network.ApiService;
import com.trackingsystem.apps.views.FloorPlanView;

import android.app.AlertDialog;
import android.graphics.Bitmap;
import android.graphics.Matrix;
import android.widget.ImageView;
import com.google.zxing.BarcodeFormat;
import com.google.zxing.MultiFormatWriter;
import com.google.zxing.WriterException;
import com.google.zxing.common.BitMatrix;
import com.journeyapps.barcodescanner.BarcodeEncoder;

import java.util.ArrayList;
import java.util.List;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class TrackingActivity extends AppCompatActivity implements EmployeeAdapter.OnItemClickListener, FloorPlanView.OnBadgeClickListener {

    private TextView connectionStatus;
    private FloorPlanView floorPlanView;
    private RecyclerView employeeRecyclerView;
    private EmployeeAdapter employeeAdapter;
    private ApiService apiService;
    private Handler updateHandler;
    private Runnable updateRunnable;
    private List<Employee> activeEmployees = new ArrayList<>();

    // Constantes pour la sauvegarde de l'état du zoom
    private static final String STATE_MATRIX_VALUES = "matrix_values";
    private static final String STATE_SCALE_FACTOR = "scale_factor";

    // Constantes pour la détection du badge
    private static final float BADGE_X = 0.4f;
    private static final float BADGE_Y = 2.5f;
    private static final float PROXIMITY_THRESHOLD = 0.5f;

    // Intervalle de mise à jour (2 secondes)
    private static final long UPDATE_INTERVAL = 2000;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        supportRequestWindowFeature(WindowCompat.FEATURE_ACTION_BAR_OVERLAY);
        if (getSupportActionBar() != null) {
            getSupportActionBar().hide();
        }
        setContentView(R.layout.activity_tracking);

        apiService = ApiClient.getClient().create(ApiService.class);
        updateHandler = new Handler();

        initializeViews();
        setupRecyclerView();

        // Définir le listener de clic du badge
        floorPlanView.setOnBadgeClickListener(this);

        // Restaurer l'état du zoom/panoramique
        if (savedInstanceState != null) {
            float[] matrixValues = savedInstanceState.getFloatArray(STATE_MATRIX_VALUES);
            float scale = savedInstanceState.getFloat(STATE_SCALE_FACTOR);
            if (matrixValues != null) {
                Matrix savedMatrix = new Matrix();
                savedMatrix.setValues(matrixValues);
                floorPlanView.setDrawingMatrix(savedMatrix, scale);
            }
        }

        // Démarrer les mises à jour en temps réel (HTTP polling)
        startRealTimeUpdates();
    }

    // --- Sauvegarde de l'état du zoom/panoramique ---
    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);

        Matrix currentMatrix = floorPlanView.getDrawingMatrix();
        float[] matrixValues = new float[9];
        currentMatrix.getValues(matrixValues);

        outState.putFloatArray(STATE_MATRIX_VALUES, matrixValues);
        outState.putFloat(STATE_SCALE_FACTOR, floorPlanView.getScaleFactor());
    }

    private void initializeViews() {
        connectionStatus = findViewById(R.id.connectionStatus);
        floorPlanView = findViewById(R.id.floorPlanView);
        employeeRecyclerView = findViewById(R.id.employeeRecyclerView);

        // Afficher statut initial
        connectionStatus.setText("Connexion...");
        connectionStatus.setTextColor(getResources().getColor(android.R.color.holo_orange_light));
    }

    private void setupRecyclerView() {
        employeeAdapter = new EmployeeAdapter(new ArrayList<>(), this);
        employeeRecyclerView.setLayoutManager(new LinearLayoutManager(this));
        employeeRecyclerView.setAdapter(employeeAdapter);
    }

    /**
     * Démarre les mises à jour périodiques via HTTP polling
     */
    private void startRealTimeUpdates() {
        updateRunnable = new Runnable() {
            @Override
            public void run() {
                updateEmployeePositions();
                // Replanifier la prochaine mise à jour
                updateHandler.postDelayed(this, UPDATE_INTERVAL);
            }
        };

        // Démarrer immédiatement
        updateHandler.post(updateRunnable);
    }

    /**
     * Récupère les positions des employés actifs via API REST
     */
    private void updateEmployeePositions() {
        Call<EmployeesResponse> call = apiService.getActiveEmployees();

        call.enqueue(new Callback<EmployeesResponse>() {
            @Override
            public void onResponse(Call<EmployeesResponse> call, Response<EmployeesResponse> response) {
                if (response.isSuccessful() && response.body() != null) {
                    EmployeesResponse body = response.body();

                    if (body.isSuccess() && body.getEmployees() != null) {
                        List<Employee> employees = body.getEmployees();

                        // Mettre à jour la liste locale
                        activeEmployees = new ArrayList<>(employees);

                        // Mettre à jour l'interface
                        employeeAdapter.updateEmployees(employees);
                        floorPlanView.updateEmployeePositions(employees);

                        // Statut connecté (Vert)
                        connectionStatus.setText("Connecté (" + employees.size() + " actifs)");
                        connectionStatus.setTextColor(getResources().getColor(R.color.safe_zone));
                        floorPlanView.setConnectionStatus(true);

                    } else {
                        // Réponse vide ou erreur
                        handleConnectionError("Aucune donnée disponible");
                    }
                } else {
                    // Erreur HTTP
                    handleConnectionError("Erreur serveur: " + response.code());
                }
            }

            @Override
            public void onFailure(Call<EmployeesResponse> call, Throwable t) {
                // Erreur réseau
                handleConnectionError("Erreur réseau: " + t.getMessage());
            }
        });
    }

    /**
     * Gère les erreurs de connexion
     */
    private void handleConnectionError(String errorMessage) {
        runOnUiThread(() -> {
            connectionStatus.setText("Déconnecté");
            connectionStatus.setTextColor(getResources().getColor(R.color.forbidden_zone));
            floorPlanView.setConnectionStatus(false);

            // Log l'erreur (optionnel)
            System.err.println("TrackingActivity: " + errorMessage);
        });
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        // Arrêter les mises à jour
        if (updateHandler != null && updateRunnable != null) {
            updateHandler.removeCallbacks(updateRunnable);
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        // Arrêter les mises à jour quand l'app est en arrière-plan
        if (updateHandler != null && updateRunnable != null) {
            updateHandler.removeCallbacks(updateRunnable);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        // Reprendre les mises à jour
        if (updateHandler != null && updateRunnable != null) {
            updateHandler.post(updateRunnable);
        }
    }

    // --- Gère le clic sur le badge ---
    @Override
    public void onBadgeClick() {
        StringBuilder badgeInfo = new StringBuilder("Employés détectés près du badge:\n\n");
        boolean employeeFound = false;

        for (Employee emp : activeEmployees) {
            Float x = emp.getLastPositionX();
            Float y = emp.getLastPositionY();

            if (x != null && y != null) {
                float distance = (float) Math.sqrt(
                        Math.pow(x - BADGE_X, 2) + Math.pow(y - BADGE_Y, 2)
                );

                if (distance < PROXIMITY_THRESHOLD) {
                    String fullName = emp.getPrenom() + " " + emp.getNom();
                    badgeInfo.append("• ").append(fullName).append("\n");
                    badgeInfo.append("  Position: (").append(String.format("%.2f", x))
                            .append(", ").append(String.format("%.2f", y)).append(")\n");
                    badgeInfo.append("  Distance: ").append(String.format("%.2f", distance)).append(" m\n\n");
                    employeeFound = true;
                }
            }
        }

        if (!employeeFound) {
            Toast.makeText(this, "Aucun employé détecté près du badge", Toast.LENGTH_SHORT).show();
        } else {
            new AlertDialog.Builder(this)
                    .setTitle("Informations du Badge")
                    .setMessage(badgeInfo.toString())
                    .setPositiveButton("OK", null)
                    .show();
        }
    }

    // --- RecyclerView & QR Code ---
    public void showForbiddenZoneAlert(String employeeName, String zoneName) {
        runOnUiThread(() -> {
            Toast.makeText(this,
                    employeeName + " est entré dans la zone interdite : " + zoneName,
                    Toast.LENGTH_LONG).show();
        });
    }

    @Override
    public void onItemClick(Employee employee) {
        showQrCodeDialog(employee);
    }

    @Override
    public void onEditClick(Employee employee) {
        Toast.makeText(this,
                "Modifier " + employee.getPrenom() + " " + employee.getNom(),
                Toast.LENGTH_SHORT).show();
    }

    @Override
    public void onDeleteClick(Employee employee) {
        new AlertDialog.Builder(this)
                .setTitle("Confirmation")
                .setMessage("Supprimer " + employee.getPrenom() + " " + employee.getNom() + " ?")
                .setPositiveButton("Oui", (dialog, which) -> {
                    // TODO: Appeler API de suppression
                    Toast.makeText(this, "Employé supprimé", Toast.LENGTH_SHORT).show();
                })
                .setNegativeButton("Non", null)
                .show();
    }

    /**
     * Affiche le QR code de l'employé
     */
    private void showQrCodeDialog(Employee employee) {
        String qrCodeContent = employee.getId();

        if (qrCodeContent == null || qrCodeContent.isEmpty()) {
            Toast.makeText(this,
                    "Impossible de générer le QR code : ID manquant",
                    Toast.LENGTH_LONG).show();
            return;
        }

        try {
            MultiFormatWriter multiFormatWriter = new MultiFormatWriter();
            BitMatrix bitMatrix = multiFormatWriter.encode(
                    qrCodeContent,
                    BarcodeFormat.QR_CODE,
                    500,
                    500
            );

            BarcodeEncoder barcodeEncoder = new BarcodeEncoder();
            Bitmap bitmap = barcodeEncoder.createBitmap(bitMatrix);

            ImageView imageView = new ImageView(this);
            imageView.setImageBitmap(bitmap);
            imageView.setPadding(20, 20, 20, 20);

            String employeeName = employee.getPrenom() + " " + employee.getNom();

            new AlertDialog.Builder(this)
                    .setTitle("QR Code - " + employeeName)
                    .setView(imageView)
                    .setPositiveButton("Fermer", (dialog, which) -> dialog.dismiss())
                    .show();

        } catch (WriterException e) {
            e.printStackTrace();
            Toast.makeText(this,
                    "Erreur lors de la génération du QR code",
                    Toast.LENGTH_LONG).show();
        }
    }
}