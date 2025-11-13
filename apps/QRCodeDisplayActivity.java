package com.trackingsystem.apps;

import android.graphics.Bitmap;
import android.os.Bundle;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.WindowCompat;

import com.google.zxing.WriterException;
import com.google.zxing.qrcode.QRCodeWriter;
import com.journeyapps.barcodescanner.BarcodeEncoder;

public class QRCodeDisplayActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        supportRequestWindowFeature(WindowCompat.FEATURE_ACTION_BAR_OVERLAY);
        if (getSupportActionBar() != null) {
            getSupportActionBar().hide();
        }
        setContentView(R.layout.activity_qr_code_display);

        ImageView qrCodeImageView = findViewById(R.id.qrCodeImageView);
        TextView employeeNameQr = findViewById(R.id.employeeNameQr);

        // Récupérer les données de l'Intent
        if (getIntent().hasExtra("employeeData") && getIntent().hasExtra("employeeName")) {
            String employeeData = getIntent().getStringExtra("employeeData");
            String employeeName = getIntent().getStringExtra("employeeName");

            // Afficher le nom de l'employé
            employeeNameQr.setText(employeeName);

            // Générer le code QR à partir de la chaîne 'employeeData'
            try {
                // Utilisation de BarcodeEncoder pour simplifier la génération
                BarcodeEncoder barcodeEncoder = new BarcodeEncoder();
                // Générer le code QR en tant que bitmap
                Bitmap bitmap = barcodeEncoder.encodeBitmap(employeeData, com.google.zxing.BarcodeFormat.QR_CODE, 400, 400);
                // Afficher le bitmap dans l'ImageView
                qrCodeImageView.setImageBitmap(bitmap);
            } catch (WriterException e) {
                // Gérer l'erreur si le QR code ne peut pas être généré
                e.printStackTrace();
                Toast.makeText(this, "Erreur lors de la génération du QR code", Toast.LENGTH_SHORT).show();
            }
        } else {
            // Afficher un message d'erreur si les données sont manquantes
            Toast.makeText(this, "Données d'employé non trouvées", Toast.LENGTH_SHORT).show();
            finish(); // Fermer l'activité si les données sont absentes
        }
    }
}
