// Fichier : QRScanActivity.java
package com.trackingsystem.apps;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.Toast;
import android.widget.TextView;
import android.widget.ImageView;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.cardview.widget.CardView;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.core.view.WindowCompat;

import com.google.android.material.button.MaterialButton;
import com.journeyapps.barcodescanner.BarcodeCallback;
import com.journeyapps.barcodescanner.BarcodeResult;
import com.journeyapps.barcodescanner.DecoratedBarcodeView;
import com.trackingsystem.apps.database.DatabaseHelper;
import com.trackingsystem.apps.models.ApiResponse;
import com.trackingsystem.apps.models.Employee;
import com.trackingsystem.apps.models.Pointage;
import com.trackingsystem.apps.network.ApiClient;
import com.trackingsystem.apps.network.ApiService;

import org.json.JSONException;
import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

/**
 * Activité qui gère le scan des QR codes pour le pointage.
 * Cette activité est maintenant uniquement dédiée au scan.
 */
public class QRScanActivity extends AppCompatActivity {

    private static final String TAG = "QRScanActivity";
    private static final int CAMERA_PERMISSION_REQUEST_CODE = 101;

    // Déclaration des vues de l'UI
    private DecoratedBarcodeView barcodeScanner;
    private MaterialButton flashButton;
    private CardView statusCard;
    private TextView statusEmployeeName;
    private TextView statusMessage;
    private TextView statusTime;
    private ImageView statusIcon;

    private DatabaseHelper databaseHelper;
    private boolean isFlashOn = false;

    // Callback pour gérer le résultat du scan de QR code
    private BarcodeCallback callback = new BarcodeCallback() {
        @Override
        public void barcodeResult(BarcodeResult result) {
            if (result.getText() != null) {
                Log.d(TAG, "QR Code scanné avec succès.");
                barcodeScanner.pause();
                handleQRCodeResult(result.getText());
            }
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        supportRequestWindowFeature(WindowCompat.FEATURE_ACTION_BAR_OVERLAY);
        if (getSupportActionBar() != null) {
            getSupportActionBar().hide();
        }
        setContentView(R.layout.activity_qr_scan);

        databaseHelper = new DatabaseHelper(this);
        initializeViews();

        checkPermissions();
    }

    /**
     * Initialise toutes les vues de l'interface utilisateur.
     */
    private void initializeViews() {
        barcodeScanner = findViewById(R.id.barcodeScanner);
        flashButton = findViewById(R.id.flashButton);
        statusCard = findViewById(R.id.statusCard);
        statusEmployeeName = findViewById(R.id.statusEmployeeName);
        statusMessage = findViewById(R.id.statusMessage);
        statusTime = findViewById(R.id.statusTime);
        statusIcon = findViewById(R.id.statusIcon);

        flashButton.setOnClickListener(v -> toggleFlash());
    }

    /**
     * Vérifie et demande la permission de la caméra.
     */
    private void checkPermissions() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this,
                    new String[]{Manifest.permission.CAMERA},
                    CAMERA_PERMISSION_REQUEST_CODE);
        } else {
            startScanning();
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == CAMERA_PERMISSION_REQUEST_CODE) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                Log.d(TAG, "Permission de la caméra accordée.");
                startScanning();
            } else {
                Log.w(TAG, "Permission de la caméra refusée.");
                Toast.makeText(this, "La permission de la caméra est nécessaire pour scanner les QR codes.", Toast.LENGTH_LONG).show();
            }
        }
    }

    private void startScanning() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED) {
            barcodeScanner.decodeContinuous(callback);
        } else {
            Log.e(TAG, "Impossible de démarrer le scan, la permission de la caméra n'est pas accordée.");
        }
    }

    private void handleQRCodeResult(String qrData) {
        try {
            JSONObject employeeData = new JSONObject(qrData);
            String employeeId = employeeData.getString("id");

            Employee employee = databaseHelper.getEmployee(employeeId);
            if (employee == null) {
                Log.e(TAG, "Employé non trouvé pour l'ID : " + employeeId);
                Toast.makeText(this, "Employé non trouvé dans la base de données", Toast.LENGTH_SHORT).show();
                barcodeScanner.resume();
                return;
            }

            Log.d(TAG, "Employé trouvé : " + employee.getNom() + " " + employee.getPrenom());
            registerAttendance(employee);

        } catch (JSONException e) {
            Log.e(TAG, "QR Code invalide: ", e);
            Toast.makeText(this, "QR Code invalide", Toast.LENGTH_SHORT).show();
            barcodeScanner.resume();
        }
    }
    private void registerAttendance(Employee employee) {
        String today = new SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(new Date());
        Pointage lastPointage = databaseHelper.getLastPointageForEmployee(employee.getId(), today);

        String pointageType = (lastPointage == null || "sortie".equals(lastPointage.getType())) ? "arrivee" : "sortie";

        Pointage pointage = new Pointage();
        pointage.setEmployeeId(employee.getId());
        pointage.setEmployeeName(employee.getNom() + " " + employee.getPrenom());
        pointage.setType(pointageType);
        pointage.setTimestamp(System.currentTimeMillis());
        pointage.setDate(today);

        // ✅ Envoyer au serveur
        ApiService apiService = ApiClient.getClient().create(ApiService.class);
        Call<ApiResponse> call = apiService.addPointage(pointage);
        call.enqueue(new Callback<ApiResponse>() {
            @Override
            public void onResponse(Call<ApiResponse> call, Response<ApiResponse> response) {
                 if (response.isSuccessful() && response.body() != null && response.body().isSuccess()) {
                    // ✅ Sauvegarder aussi en local
                    databaseHelper.addPointage(pointage);

                    Log.d(TAG, "Pointage synchronisé avec le serveur : " + pointageType);
                    showAttendanceStatus(employee, pointageType);
                } else {
                    Log.e(TAG, "❌ Erreur serveur pointage : " + response.code());
                    Toast.makeText(QRScanActivity.this, "Échec synchro serveur", Toast.LENGTH_SHORT).show();
                    barcodeScanner.resume();
                }
            }

            @Override
            public void onFailure(Call<ApiResponse> call, Throwable t) {
                Log.e(TAG, "🌐 Erreur réseau pointage : " + t.getMessage());
                Toast.makeText(QRScanActivity.this, "Hors ligne, sauvegarde locale", Toast.LENGTH_SHORT).show();

                // ✅ Sauvegarde locale uniquement si pas de connexion
                databaseHelper.addPointage(pointage);
                showAttendanceStatus(employee, pointageType);
            }
        });
    }


    private void showAttendanceStatus(Employee employee, String pointageType) {
        statusEmployeeName.setText(employee.getNom() + " " + employee.getPrenom());
        statusMessage.setText(pointageType.equals("arrivee") ? "Arrivée enregistrée" : "Sortie enregistrée");
        statusTime.setText(new SimpleDateFormat("HH:mm", Locale.getDefault()).format(new Date()));

        statusCard.setVisibility(View.VISIBLE);

        statusCard.postDelayed(() -> {
            statusCard.setVisibility(View.GONE);
            barcodeScanner.resume();
        }, 3000);
    }

    /**
     * Active ou désactive le flash de l'appareil photo.
     */
    private void toggleFlash() {
        if (isFlashOn) {
            barcodeScanner.setTorchOff();
            flashButton.setText("Flash");
            isFlashOn = false;
        } else {
            barcodeScanner.setTorchOn();
            flashButton.setText("Flash OFF");
            isFlashOn = true;
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED) {
            barcodeScanner.resume();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        barcodeScanner.pause();
    }
}
