package com.trackingsystem.apps;

import android.Manifest;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.ImageView;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.cardview.widget.CardView;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.core.view.WindowCompat;

import com.google.android.material.button.MaterialButton;
import com.google.zxing.BinaryBitmap;
import com.google.zxing.LuminanceSource;
import com.google.zxing.MultiFormatReader;
import com.google.zxing.RGBLuminanceSource;
import com.google.zxing.ReaderException;
import com.google.zxing.Result;
import com.google.zxing.common.HybridBinarizer;
import com.trackingsystem.apps.database.DatabaseHelper;
import com.trackingsystem.apps.models.Employee;
import com.trackingsystem.apps.models.Pointage;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.TimeUnit;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;
import okio.ByteString;

public class Esp32CamActivity extends AppCompatActivity {

    private static final String TAG = "Esp32CamActivity";
    private static final int INTERNET_PERMISSION_REQUEST_CODE = 102;
    private static final String WEBSOCKET_URL = "wss://cames-2.onrender.com"; // URL Render

    private MaterialButton scanButton;
    private MaterialButton flashButton;
    private ProgressBar scanProgressBar;
    private CardView statusCard;
    private TextView statusEmployeeName;
    private TextView statusMessage;
    private TextView statusTime;
    private ImageView statusIcon;
    private ImageView livePreview;
    private TextView ipAddressText;

    private DatabaseHelper databaseHelper;
    private boolean isFlashOn = false;
    private boolean isScanning = false;
    private OkHttpClient okHttpClient;
    private WebSocket webSocket;
    private boolean isClientIdentified = false; // Suivre l'identification

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        supportRequestWindowFeature(WindowCompat.FEATURE_ACTION_BAR_OVERLAY);
        if (getSupportActionBar() != null) {
            getSupportActionBar().hide();
        }
        setContentView(R.layout.layout_esp32_cam_standalone);

        okHttpClient = new OkHttpClient.Builder()
                .connectTimeout(15, TimeUnit.SECONDS)
                .readTimeout(15, TimeUnit.SECONDS)
                .writeTimeout(15, TimeUnit.SECONDS)
                .build();

        databaseHelper = new DatabaseHelper(this);
        initializeViews();

        checkPermissions(Manifest.permission.INTERNET, INTERNET_PERMISSION_REQUEST_CODE);
    }

    private void initializeViews() {
        scanButton = findViewById(R.id.scanButton);
        flashButton = findViewById(R.id.flashButton);
        scanProgressBar = findViewById(R.id.scanProgressBar);
        statusCard = findViewById(R.id.statusCard);
        statusEmployeeName = findViewById(R.id.statusEmployeeName);
        statusMessage = findViewById(R.id.statusMessage);
        statusTime = findViewById(R.id.statusTime);
        statusIcon = findViewById(R.id.statusIcon);
        livePreview = findViewById(R.id.livePreview);
        ipAddressText = findViewById(R.id.ipAddressText);

        ipAddressText.setText("Connecté au serveur Render");

        scanButton.setOnClickListener(v -> {
            if (!isScanning) {
                startScanning();
            } else {
                stopScanning();
            }
        });

        flashButton.setOnClickListener(v -> toggleFlash());
    }

    private void startScanning() {
        isScanning = true;
        isClientIdentified = false; // Réinitialiser l'identification
        scanButton.setText("Arrêter le scan");
        scanProgressBar.setVisibility(View.VISIBLE);
        Toast.makeText(this, "Connexion au serveur Render...", Toast.LENGTH_SHORT).show();

        Request request = new Request.Builder().url(WEBSOCKET_URL).build();
        webSocket = okHttpClient.newWebSocket(request, new WebSocketListener() {
            @Override
            public void onOpen(WebSocket webSocket, Response response) {
                Log.d(TAG, "Connexion WebSocket ouverte");
                isClientIdentified = true;
                webSocket.send("android-client");
                try {
                    Thread.sleep(100); // Délai pour stabilité
                } catch (InterruptedException e) {
                    Log.e(TAG, "Erreur d'attente: ", e);
                }
                webSocket.send("start-stream");
                runOnUiThread(() -> scanProgressBar.setVisibility(View.GONE));
            }

            @Override
            public void onMessage(WebSocket webSocket, ByteString bytes) {
                long startTime = System.currentTimeMillis();
                Log.d(TAG, "Image reçue via WebSocket, taille: " + bytes.size() + " octets");
                BitmapFactory.Options options = new BitmapFactory.Options();
                options.inSampleSize = 2;
                Bitmap bitmap = BitmapFactory.decodeByteArray(bytes.toByteArray(), 0, bytes.size(), options);
                if (bitmap != null) {
                    runOnUiThread(() -> livePreview.setImageBitmap(bitmap));
                    String qrData = decodeQRCode(bitmap);
                    if (qrData != null) {
                        runOnUiThread(() -> {
                            handleQRCodeResult(qrData);
                            stopScanning();
                        });
                    }
                } else {
                    Log.e(TAG, "Échec du décodage de l'image WebSocket");
                }
                Log.d(TAG, "Traitement de l'image en " + (System.currentTimeMillis() - startTime) + "ms");
            }

            @Override
            public void onMessage(WebSocket webSocket, String text) {
                Log.d(TAG, "Message texte reçu: " + text);
                if (text.contains("error")) {
                    runOnUiThread(() -> {
                        Toast.makeText(Esp32CamActivity.this, "Erreur serveur: " + text, Toast.LENGTH_LONG).show();
                        stopScanning();
                    });
                }
            }

            @Override
            public void onFailure(WebSocket webSocket, Throwable t, Response response) {
                Log.e(TAG, "Erreur WebSocket: ", t);
                runOnUiThread(() -> {
                    Toast.makeText(Esp32CamActivity.this, "Échec de la connexion WebSocket: " + t.getMessage(), Toast.LENGTH_LONG).show();
                    stopScanning();
                });
            }

            @Override
            public void onClosing(WebSocket webSocket, int code, String reason) {
                Log.d(TAG, "WebSocket fermé: " + reason);
                webSocket.close(1000, null);
                runOnUiThread(() -> stopScanning());
            }
        });
    }

    private void stopScanning() {
        isScanning = false;
        isClientIdentified = false;
        scanButton.setText("Lancer le scan");
        scanProgressBar.setVisibility(View.GONE);
        if (webSocket != null) {
            webSocket.close(1000, "Arrêt du scan");
            webSocket = null;
        }
        livePreview.setImageBitmap(null);
        Toast.makeText(this, "Scan arrêté.", Toast.LENGTH_SHORT).show();
    }

    private void toggleFlash() {
        flashButton.setEnabled(false);
        if (webSocket != null && isScanning && isClientIdentified) {
            webSocket.send(isFlashOn ? "flash-off" : "flash-on");
            isFlashOn = !isFlashOn;
            flashButton.setText(isFlashOn ? "Flash ON" : "Flash OFF");
            flashButton.setEnabled(true);
            Log.d(TAG, "Commande flash envoyée: " + (isFlashOn ? "flash-on" : "flash-off"));
        } else {
            Toast.makeText(this, "WebSocket non connecté ou scan non actif", Toast.LENGTH_SHORT).show();
            flashButton.setEnabled(true);
            Log.e(TAG, "Échec envoi commande flash: WebSocket=" + (webSocket == null ? "null" : "non null") + ", isScanning=" + isScanning + ", isClientIdentified=" + isClientIdentified);
        }
    }

    private void checkPermissions(String permission, int requestCode) {
        if (ContextCompat.checkSelfPermission(this, permission) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, new String[]{permission}, requestCode);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == INTERNET_PERMISSION_REQUEST_CODE) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                Log.d(TAG, "Permission Internet accordée.");
            } else {
                Log.w(TAG, "Permission Internet refusée.");
                Toast.makeText(this, "La permission d'accès à Internet est nécessaire.", Toast.LENGTH_LONG).show();
                finish();
            }
        }
    }

    private String decodeQRCode(Bitmap bitmap) {
        try {
            int width = bitmap.getWidth();
            int height = bitmap.getHeight();
            int[] pixels = new int[width * height];
            bitmap.getPixels(pixels, 0, width, 0, 0, width, height);

            LuminanceSource source = new RGBLuminanceSource(width, height, pixels);
            BinaryBitmap binaryBitmap = new BinaryBitmap(new HybridBinarizer(source));
            MultiFormatReader reader = new MultiFormatReader();
            Result result = reader.decode(binaryBitmap);
            return result.getText();
        } catch (ReaderException e) {
            return null;
        }
    }

    private void handleQRCodeResult(String qrData) {
        try {
            String employeeId = qrData;
            Employee employee = databaseHelper.getEmployee(employeeId);
            if (employee == null) {
                Log.e(TAG, "Employé non trouvé pour l'ID : " + employeeId);
                Toast.makeText(this, "Employé non trouvé dans la base de données", Toast.LENGTH_SHORT).show();
                return;
            }

            Log.d(TAG, "Employé trouvé : " + employee.getNom() + " " + employee.getPrenom());
            registerAttendance(employee);
        } catch (Exception e) {
            Log.e(TAG, "QR Code invalide: ", e);
            Toast.makeText(this, "QR Code invalide", Toast.LENGTH_SHORT).show();
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

        long result = databaseHelper.addPointage(pointage);
        if (result != -1) {
            Log.d(TAG, "Pointage enregistré avec succès: " + pointageType);
            showAttendanceStatus(employee, pointageType);
        } else {
            Log.e(TAG, "Erreur lors de l'enregistrement du pointage.");
            Toast.makeText(this, "Erreur lors de l'enregistrement", Toast.LENGTH_SHORT).show();
        }
    }

    private void showAttendanceStatus(Employee employee, String pointageType) {
        statusEmployeeName.setText(employee.getNom() + " " + employee.getPrenom());
        statusMessage.setText(pointageType.equals("arrivee") ? "Arrivée enregistrée" : "Sortie enregistrée");
        statusTime.setText(new SimpleDateFormat("HH:mm", Locale.getDefault()).format(new Date()));

        statusCard.setVisibility(View.VISIBLE);
        statusCard.postDelayed(() -> statusCard.setVisibility(View.GONE), 3000);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        stopScanning();
    }
}