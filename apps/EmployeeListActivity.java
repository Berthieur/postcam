package com.trackingsystem.apps;

import android.app.DatePickerDialog;
import android.app.Dialog;
import android.content.ContentValues;
import android.content.Intent;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.pdf.PdfDocument;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.text.Editable;
import android.text.TextWatcher;
import android.util.Log;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.AutoCompleteTextView;
import android.widget.LinearLayout;
import android.widget.Toast;
import android.widget.ImageView;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.WindowCompat;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import com.google.android.material.button.MaterialButton;
import com.google.android.material.textfield.TextInputEditText;
import com.google.android.material.textfield.TextInputLayout;
import com.trackingsystem.apps.adapters.EmployeeAdapter;
import com.trackingsystem.apps.database.DatabaseHelper;
import com.trackingsystem.apps.models.ApiResponse;
import com.trackingsystem.apps.models.Employee;
import com.trackingsystem.apps.network.ApiClient;
import com.trackingsystem.apps.network.ApiService;
import com.trackingsystem.apps.utils.QRCodeUtils;
import com.google.zxing.BarcodeFormat;
import com.google.zxing.WriterException;
import com.google.zxing.common.BitMatrix;
import com.google.zxing.qrcode.QRCodeWriter;
import android.graphics.Bitmap;
import android.graphics.Color;
import androidx.cardview.widget.CardView;
import java.io.OutputStream;
import java.io.Serializable;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.List;
import java.util.Locale;

import retrofit2.Call;

/**
 * Activité principale qui affiche la liste des employés.
 * Elle permet de rechercher, filtrer et gérer les employés (ajouter, modifier, supprimer).
 */
public class EmployeeListActivity extends AppCompatActivity {

    private static final String TAG = "EmployeeListActivity"; // ✅ Pour logs
    private RecyclerView employeeRecyclerView;
    private EmployeeAdapter employeeAdapter;
    private List<Employee> allEmployees = new ArrayList<>();
    private List<Employee> filteredEmployees = new ArrayList<>();

    private TextInputEditText searchEditText;
    private AutoCompleteTextView filterSpinner;
    private MaterialButton addEmployeeButton;
    private View emptyStateLayout;

    private DatabaseHelper databaseHelper; // ✅ Gestion SQLite locale
    private Bitmap generatedQrBitmap = null;
    private Employee currentEmployee = null; // ✅ Stocke l’employé en cours de création

    private TextInputEditText dateNaissanceEditText;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        supportRequestWindowFeature(WindowCompat.FEATURE_ACTION_BAR_OVERLAY);
        if (getSupportActionBar() != null) {
            getSupportActionBar().hide();
        }
        setContentView(R.layout.activity_employee_list);
        Log.d(TAG, "L'activité de la liste des employés a été créée.");

        databaseHelper = new DatabaseHelper(this); // ✅ Initialisation SQLite

        employeeRecyclerView = findViewById(R.id.employeeRecyclerView);
        searchEditText = findViewById(R.id.searchEditText);
        filterSpinner = findViewById(R.id.filterSpinner);
        addEmployeeButton = findViewById(R.id.addEmployeeButton);
        emptyStateLayout = findViewById(R.id.emptyStateLayout);

        // ✅ Initialisation de l'adaptateur avec les actions (clic, éditer, supprimer)
        employeeAdapter = new EmployeeAdapter(filteredEmployees, new EmployeeAdapter.OnItemClickListener() {
            @Override
            public void onItemClick(Employee employee) {
                Log.d(TAG, "Clic sur la carte pour : " + employee.getNom());
                Intent intent = new Intent(EmployeeListActivity.this, QRCodeDisplayActivity.class);
                String employeeFullName = employee.getNom() + " " + employee.getPrenom();
                intent.putExtra("employeeData", employee.getJsonString());
                intent.putExtra("employeeName", employeeFullName);
                startActivity(intent);
            }

            @Override
            public void onEditClick(Employee employee) {
                Log.d(TAG, "Clic sur 'Modifier' pour : " + employee.getNom());
                Intent intent = new Intent(EmployeeListActivity.this, EditEmployeeActivity.class);
                intent.putExtra("employee_to_edit", (Serializable) employee);
                startActivity(intent);
                // ⚠️ Vérifie que EditEmployeeActivity appelle aussi l’API (PUT/PATCH) côté Neon pour synchroniser
            }

            @Override
            public void onDeleteClick(Employee employee) {
                Log.d(TAG, "Clic sur 'Supprimer' pour : " + employee.getNom());
                showDeleteConfirmationDialog(employee); // ✅ Supprime localement + tente serveur
            }
        });

        employeeRecyclerView.setLayoutManager(new LinearLayoutManager(this));
        employeeRecyclerView.setAdapter(employeeAdapter);

        addEmployeeButton.setOnClickListener(v -> {
            Log.d(TAG, "Bouton 'Ajouter un employé' cliqué. Ouverture du dialogue.");
            showGenerateQRDialog(); // ✅ Lance la fenêtre pour ajouter + générer QR
        });

        // ✅ Recherche dynamique
        searchEditText.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override
            public void onTextChanged(CharSequence s, int start, int before, int count) {
                Log.d(TAG, "Texte de recherche modifié : " + s.toString());
                filterList(s.toString(), filterSpinner.getText().toString());
            }
            @Override
            public void afterTextChanged(Editable s) {}
        });

        setupFilterSpinner(); // ✅ Prépare la liste de filtres
    }

    @Override
    protected void onResume() {
        super.onResume();
        Log.d(TAG, "Activité reprise. Chargement des données de la base.");
        loadEmployeesFromDatabase(); // ✅ Recharge les données locales
    }

    private void loadEmployeesFromDatabase() {
        allEmployees.clear();
        allEmployees.addAll(databaseHelper.getAllEmployees());
        Log.d(TAG, "Données de la base de données chargées. Nombre d'employés : " + allEmployees.size());
        filterList(searchEditText.getText().toString(), filterSpinner.getText().toString());
    }

    private void setupFilterSpinner() {
        String[] types = new String[]{"Tous", "employe", "etudiant"};
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_dropdown_item_1line, types);
        filterSpinner.setAdapter(adapter);
        filterSpinner.setOnItemClickListener((parent, view, position, id) -> {
            Log.d(TAG, "Filtre sélectionné : " + types[position]);
            filterList(searchEditText.getText().toString(), types[position]);
        });
    }

    private void filterList(String query, String type) {
        filteredEmployees.clear();
        String lowerCaseQuery = query.toLowerCase();

        for (Employee employee : allEmployees) {
            boolean matchesQuery = employee.getNom().toLowerCase().contains(lowerCaseQuery) ||
                    employee.getPrenom().toLowerCase().contains(lowerCaseQuery) ||
                    (employee.getProfession() != null && employee.getProfession().toLowerCase().contains(lowerCaseQuery));

            boolean matchesType = "Tous".equals(type) || employee.getType().equalsIgnoreCase(type);

            if (matchesQuery && matchesType) {
                filteredEmployees.add(employee);
            }
        }
        Log.d(TAG, "Filtrage terminé. Nombre d'employés filtrés : " + filteredEmployees.size());
        employeeAdapter.updateEmployees(filteredEmployees);
        updateUI();
    }

    private void updateUI() {
        if (filteredEmployees.isEmpty()) {
            employeeRecyclerView.setVisibility(View.GONE);
            emptyStateLayout.setVisibility(View.VISIBLE);
            Log.d(TAG, "Affichage de l'état vide.");
        } else {
            employeeRecyclerView.setVisibility(View.VISIBLE);
            emptyStateLayout.setVisibility(View.GONE);
            Log.d(TAG, "Affichage de la liste d'employés.");
        }
    }

    /**
     * ✅ Suppression employé (SQLite + Serveur Neon)
     */
    private void showDeleteConfirmationDialog(Employee employee) {
        new AlertDialog.Builder(this)
                .setTitle("Supprimer l'employé")
                .setMessage("Êtes-vous sûr de vouloir supprimer " + employee.getNom() + " " + employee.getPrenom() + " ?")
                .setPositiveButton("Oui", (dialog, which) -> {
                    // ✅ Suppression locale SQLite
                    databaseHelper.deleteEmployee(employee.getId());
                    loadEmployeesFromDatabase();

                    // ✅ Suppression côté serveur Neon
                    ApiService apiService = ApiClient.getClient().create(ApiService.class);
                    Call<ApiResponse> call = apiService.deleteEmployee(employee.getId());
                    // ⚠️ Vérifie que dans ApiService tu as bien :
                    // @DELETE("employees/{id}") Call<ApiResponse> deleteEmployee(@Path("id") String id);

                    call.enqueue(new retrofit2.Callback<ApiResponse>() {
                        @Override
                        public void onResponse(Call<ApiResponse> call, retrofit2.Response<ApiResponse> response) {
                            if (response.isSuccessful() && response.body() != null) {
                                if (response.body().isSuccess()) {
                                    Toast.makeText(EmployeeListActivity.this,
                                            "Employé supprimé (local + serveur) ✅",
                                            Toast.LENGTH_SHORT).show();
                                } else {
                                    Toast.makeText(EmployeeListActivity.this,
                                            "Erreur serveur ❌ : " + response.body().getMessage(),
                                            Toast.LENGTH_SHORT).show();
                                }
                            } else {
                                Toast.makeText(EmployeeListActivity.this,
                                        "Supprimé localement ✅ mais erreur HTTP (" + response.code() + ") ❌",
                                        Toast.LENGTH_SHORT).show();
                            }
                        }

                        @Override
                        public void onFailure(Call<ApiResponse> call, Throwable t) {
                            Toast.makeText(EmployeeListActivity.this,
                                    "Supprimé localement ✅ mais pas de connexion serveur 🌐",
                                    Toast.LENGTH_SHORT).show();
                            Log.e(TAG, "Erreur API delete:", t);
                        }
                    });
                })
                .setNegativeButton("Non", (dialog, which) -> dialog.dismiss())
                .show();
    }

    // ⚠️ Je ne recopie pas tout (showGenerateQRDialog, saveQrCodeImage, generatePdf, etc.)
    // car ton fichier est déjà correct.
    // → Ils fonctionnent bien, tu peux les garder tels quels.
    // → L’important à corriger est dans ApiService côté serveur.




/**
     * Nouvelle méthode pour afficher le dialogue de génération de QR code.
     */
    private void showGenerateQRDialog() {
        Dialog dialog = new Dialog(this);
        dialog.setContentView(R.layout.dialog_generate_qr);
        dialog.getWindow().setLayout(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);

        AutoCompleteTextView typeSpinner = dialog.findViewById(R.id.typeSpinner);
        TextInputEditText nomEditText = dialog.findViewById(R.id.nomEditText);
        TextInputEditText prenomEditText = dialog.findViewById(R.id.prenomEditText);
        dateNaissanceEditText = dialog.findViewById(R.id.dateNaissanceEditText);
        TextInputEditText lieuNaissanceEditText = dialog.findViewById(R.id.lieuNaissanceEditText);
        TextInputEditText telephoneEditText = dialog.findViewById(R.id.telephoneEditText);
        TextInputEditText emailEditText = dialog.findViewById(R.id.emailEditText);
        TextInputEditText professionEditText = dialog.findViewById(R.id.professionEditText);
        TextInputEditText tauxHoraireEditText = dialog.findViewById(R.id.tauxHoraireEditText);
        TextInputEditText fraisEcolageEditText = dialog.findViewById(R.id.fraisEcolageEditText);

        TextInputLayout tauxHoraireLayout = dialog.findViewById(R.id.tauxHoraireLayout);
        TextInputLayout fraisEcolageLayout = dialog.findViewById(R.id.fraisEcolageLayout);

        CardView qrCodeCard = dialog.findViewById(R.id.qrCodeCard);
        ImageView qrImageView = dialog.findViewById(R.id.qrCodeImageView);
        MaterialButton generateButton = dialog.findViewById(R.id.generateButton);
        MaterialButton cancelButton = dialog.findViewById(R.id.cancelButton);

        // NOUVEAU : Bouton pour enregistrer l'image
        MaterialButton saveImageButton = dialog.findViewById(R.id.saveImageButton);
        // NOUVEAU : Bouton pour générer le PDF
        MaterialButton generatePdfButton = dialog.findViewById(R.id.generatePdfButton);

        String[] types = {"Employé", "Étudiant"};
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_dropdown_item_1line, types);
        typeSpinner.setAdapter(adapter);
        typeSpinner.setText("Employé", false);
        typeSpinner.setOnItemClickListener((parent, view, position, id) -> {
            if (position == 0) {
                tauxHoraireLayout.setVisibility(View.VISIBLE);
                fraisEcolageLayout.setVisibility(View.GONE);
            } else {
                tauxHoraireLayout.setVisibility(View.GONE);
                fraisEcolageLayout.setVisibility(View.VISIBLE);
            }
        });

        dateNaissanceEditText.setOnClickListener(v -> {
            Log.d(TAG, "Clic sur le champ de date de naissance dans le dialogue détecté.");
            showDatePickerDialog();
        });


        generateButton.setOnClickListener(v -> {
            String nom = nomEditText.getText().toString().trim();
            String prenom = prenomEditText.getText().toString().trim();
            String type = typeSpinner.getText().toString().equals("Employé") ? "employe" : "etudiant";

            if (nom.isEmpty() || prenom.isEmpty()) {
                Toast.makeText(this, "Les champs Nom et Prénom sont obligatoires.", Toast.LENGTH_SHORT).show();
                return;
            }

            currentEmployee = new Employee();
            currentEmployee.setId(String.valueOf(System.currentTimeMillis()));
            currentEmployee.setNom(nom);
            currentEmployee.setPrenom(prenom);
            currentEmployee.setType(type);
            currentEmployee.setDateNaissance(dateNaissanceEditText.getText().toString().trim());
            currentEmployee.setLieuNaissance(lieuNaissanceEditText.getText().toString().trim());
            currentEmployee.setTelephone(telephoneEditText.getText().toString().trim());
            currentEmployee.setEmail(emailEditText.getText().toString().trim());
            currentEmployee.setProfession(professionEditText.getText().toString().trim());
            // Pour taux horaire (si type = employe)
            double tauxHoraire = 0;
            try {
                if (!tauxHoraireEditText.getText().toString().trim().isEmpty()) {
                    tauxHoraire = Double.parseDouble(tauxHoraireEditText.getText().toString().trim());
                }
            } catch (NumberFormatException e) {
                tauxHoraire = 0;
            }
            currentEmployee.setTauxHoraire(tauxHoraire);

// Pour frais d’écolage (si type = etudiant)
            double fraisEcolage = 0;
            try {
                if (!fraisEcolageEditText.getText().toString().trim().isEmpty()) {
                    fraisEcolage = Double.parseDouble(fraisEcolageEditText.getText().toString().trim());
                }
            } catch (NumberFormatException e) {
                fraisEcolage = 0;
            }
            currentEmployee.setFraisEcolage(fraisEcolage);

            // 1️⃣ Sauvegarde locale SQLite
            long result = databaseHelper.addEmployee(currentEmployee);
            if (result != -1) {
                // 2️⃣ Sauvegarde serveur
                ApiService apiService = ApiClient.getClient().create(ApiService.class);
                apiService.registerEmployee(currentEmployee).enqueue(new retrofit2.Callback<ApiResponse>() {
                    @Override
                    public void onResponse(Call<ApiResponse> call, retrofit2.Response<ApiResponse> response) {
                        if (response.isSuccessful() && response.body() != null) {
                            ApiResponse apiResponse = response.body();
                            if (apiResponse.isSuccess()) {
                                Toast.makeText(EmployeeListActivity.this,
                                        "Employé ajouté et synchronisé ✅ " + apiResponse.getMessage(),
                                        Toast.LENGTH_SHORT).show();
                            } else {
                                Toast.makeText(EmployeeListActivity.this,
                                        "Erreur serveur ❌ : " + apiResponse.getMessage(),
                                        Toast.LENGTH_SHORT).show();
                            }
                        } else {
                            Toast.makeText(EmployeeListActivity.this,
                                    "Ajout local OK mais erreur HTTP (" + response.code() + ") ❌",
                                    Toast.LENGTH_SHORT).show();
                        }
                    }

                    @Override
                    public void onFailure(Call<ApiResponse> call, Throwable t) {
                        Toast.makeText(EmployeeListActivity.this,
                                "Ajout local OK mais pas de connexion au serveur 🌐",
                                Toast.LENGTH_SHORT).show();
                        Log.e(TAG, "Erreur API :", t);
                    }
                });

                // 3️⃣ Générer le QR Code pour l’employé
                try {
                    generatedQrBitmap = generateQRCode(currentEmployee.getJsonString());
                    qrImageView.setImageBitmap(generatedQrBitmap);
                    qrCodeCard.setVisibility(View.VISIBLE);
                    saveImageButton.setVisibility(View.VISIBLE);
                    generatePdfButton.setVisibility(View.VISIBLE);
                } catch (WriterException e) {
                    e.printStackTrace();
                    Toast.makeText(this, "Erreur lors de la génération du QR Code ❌", Toast.LENGTH_SHORT).show();
                }

                // Rafraîchir la liste
                loadEmployeesFromDatabase();

            } else {
                Toast.makeText(this, "Erreur lors de l'ajout en base locale", Toast.LENGTH_SHORT).show();
            }
        });



        // NOUVEAU : Ajout de l'écouteur de clic pour le bouton d'enregistrement d'image
        saveImageButton.setOnClickListener(v -> {
            if (generatedQrBitmap != null && currentEmployee != null) {
                Log.d(TAG, "Bouton 'Enregistrer l'image' cliqué. Lancement de la sauvegarde.");
                saveQrCodeImage(generatedQrBitmap, currentEmployee);
            } else {
                Toast.makeText(this, "Générez un QR Code d'abord.", Toast.LENGTH_SHORT).show();
            }
        });

        // NOUVEAU : Ajout de l'écouteur de clic pour le bouton de génération de PDF
        generatePdfButton.setOnClickListener(v -> {
            if (currentEmployee != null) {
                Log.d(TAG, "Bouton 'Générer PDF' cliqué. Lancement de la génération.");
                generatePdf(currentEmployee);
            } else {
                Toast.makeText(this, "Générez un QR Code d'abord.", Toast.LENGTH_SHORT).show();
            }
        });


        cancelButton.setOnClickListener(v -> dialog.dismiss());
        dialog.show();
    }

    private void showDatePickerDialog() {
        final Calendar c = Calendar.getInstance();
        int year = c.get(Calendar.YEAR);
        int month = c.get(Calendar.MONTH);
        int day = c.get(Calendar.DAY_OF_MONTH);

        DatePickerDialog datePickerDialog = new DatePickerDialog(this,
                (view, selectedYear, selectedMonth, selectedDay) -> {
                    Log.d(TAG, "Date sélectionnée dans le dialogue : " + selectedYear + "-" + (selectedMonth + 1) + "-" + selectedDay);

                    String formattedDate = String.format(Locale.getDefault(), "%04d-%02d-%02d",
                            selectedYear, selectedMonth + 1, selectedDay);
                    dateNaissanceEditText.setText(formattedDate);
                }, year, month, day);

        datePickerDialog.show();
    }


    /**
     * Génère un Bitmap à partir d'une chaîne de données pour un QR code.
     */
    private Bitmap generateQRCode(String data) throws WriterException {
        QRCodeWriter writer = new QRCodeWriter();
        BitMatrix bitMatrix = writer.encode(data, BarcodeFormat.QR_CODE, 512, 512);
        int width = bitMatrix.getWidth();
        int height = bitMatrix.getHeight();
        Bitmap bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.RGB_565);

        for (int x = 0; x < width; x++) {
            for (int y = 0; y < height; y++) {
                bitmap.setPixel(x, y, bitMatrix.get(x, y) ? Color.BLACK : Color.WHITE);
            }
        }
        return bitmap;
    }

    /**
     * NOUVEAU : Sauvegarde le Bitmap du QR Code dans la galerie de l'appareil.
     */
    private void saveQrCodeImage(Bitmap bitmap, Employee employee) {
        // Crée un nom de fichier basé sur le nom de l'employé
        String fileName = employee.getNom().replaceAll("\\s+", "_") + "_" + employee.getPrenom().replaceAll("\\s+", "_") + ".png";

        ContentValues values = new ContentValues();
        values.put(MediaStore.Images.Media.DISPLAY_NAME, fileName);
        values.put(MediaStore.Images.Media.MIME_TYPE, "image/png");
        values.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/TrackingSystem");

        Uri uri = null;
        try {
            Uri collection = MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
            uri = getContentResolver().insert(collection, values);
            if (uri != null) {
                try (OutputStream outputStream = getContentResolver().openOutputStream(uri)) {
                    bitmap.compress(Bitmap.CompressFormat.PNG, 100, outputStream);
                    Toast.makeText(this, "QR Code enregistré dans la galerie sous " + fileName, Toast.LENGTH_LONG).show();
                    Log.d(TAG, "Image du QR Code enregistrée avec succès : " + uri.toString());
                }
            } else {
                Toast.makeText(this, "Erreur : Impossible de créer le fichier image.", Toast.LENGTH_SHORT).show();
                Log.e(TAG, "Erreur : L'URI pour l'image est nulle.");
            }
        } catch (Exception e) {
            Toast.makeText(this, "Erreur lors de l'enregistrement de l'image.", Toast.LENGTH_SHORT).show();
            Log.e(TAG, "Erreur lors de l'enregistrement de l'image.", e);
        }
    }

    /**
     * NOUVEAU : Génère un document PDF contenant le QR Code et les informations de l'employé.
     */
    private void generatePdf(Employee employee) {
        // Crée un document PDF
        PdfDocument pdfDocument = new PdfDocument();
        // Définit les dimensions de la page (A4 en points)
        PdfDocument.PageInfo pageInfo = new PdfDocument.PageInfo.Builder(595, 842, 1).create();
        PdfDocument.Page page = pdfDocument.startPage(pageInfo);

        Canvas canvas = page.getCanvas();
        Paint paint = new Paint();

        int xPos = 100;
        int yPos = 100;

        // Dessine le QR Code au centre de la page
        if (generatedQrBitmap != null) {
            // Mise à l'échelle du bitmap pour le PDF si nécessaire
            Bitmap scaledBitmap = Bitmap.createScaledBitmap(generatedQrBitmap, 300, 300, false);
            int qrCodeX = (pageInfo.getPageWidth() - scaledBitmap.getWidth()) / 2;
            int qrCodeY = 150;
            canvas.drawBitmap(scaledBitmap, qrCodeX, qrCodeY, paint);
        }

        // Dessine les informations de l'employé
        paint.setColor(Color.BLACK);
        paint.setTextSize(24);
        paint.setTextAlign(Paint.Align.CENTER);
        int textX = pageInfo.getPageWidth() / 2;

        canvas.drawText("Fiche d'identification de l'employé", textX, 100, paint);

        paint.setTextAlign(Paint.Align.LEFT);
        paint.setTextSize(18);
        canvas.drawText("Nom : " + employee.getNom(), 100, 500, paint);
        canvas.drawText("Prénom : " + employee.getPrenom(), 100, 530, paint);
        canvas.drawText("Date de naissance : " + employee.getDateNaissance(), 100, 560, paint);
        canvas.drawText("Téléphone : " + employee.getTelephone(), 100, 590, paint);
        canvas.drawText("Email : " + employee.getEmail(), 100, 620, paint);

        pdfDocument.finishPage(page);

        // Sauvegarde le document
        String fileName = employee.getNom().replaceAll("\\s+", "_") + "_" + employee.getPrenom().replaceAll("\\s+", "_") + ".pdf";
        ContentValues values = new ContentValues();
        values.put(MediaStore.Files.FileColumns.DISPLAY_NAME, fileName);
        values.put(MediaStore.Files.FileColumns.MIME_TYPE, "application/pdf");
        values.put(MediaStore.Files.FileColumns.RELATIVE_PATH, Environment.DIRECTORY_DOCUMENTS + "/TrackingSystem");

        Uri uri = null;
        try {
            Uri collection = MediaStore.Files.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
            uri = getContentResolver().insert(collection, values);
            if (uri != null) {
                try (OutputStream outputStream = getContentResolver().openOutputStream(uri)) {
                    pdfDocument.writeTo(outputStream);
                    Toast.makeText(this, "PDF enregistré sous " + fileName, Toast.LENGTH_LONG).show();
                    Log.d(TAG, "PDF généré et enregistré avec succès : " + uri.toString());
                }
            } else {
                Toast.makeText(this, "Erreur : Impossible de créer le fichier PDF.", Toast.LENGTH_SHORT).show();
                Log.e(TAG, "Erreur : L'URI pour le PDF est nulle.");
            }
        } catch (Exception e) {
            Toast.makeText(this, "Erreur lors de la génération du PDF.", Toast.LENGTH_SHORT).show();
            Log.e(TAG, "Erreur lors de la génération du PDF.", e);
        } finally {
            pdfDocument.close();
        }
    }
}
