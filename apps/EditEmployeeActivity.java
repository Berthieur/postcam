package com.trackingsystem.apps;

import android.app.DatePickerDialog;
import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.AutoCompleteTextView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.WindowCompat;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.textfield.TextInputEditText;
import com.google.android.material.textfield.TextInputLayout;
import com.trackingsystem.apps.database.DatabaseHelper;
import com.trackingsystem.apps.models.ApiResponse;
import com.trackingsystem.apps.models.Employee;
import com.trackingsystem.apps.network.ApiClient;
import com.trackingsystem.apps.network.ApiService;

import java.io.Serializable;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.Date;
import java.util.Locale;

import retrofit2.Call;

/**
 * Activité pour modifier les informations d'un employé existant.
 * Elle utilise le layout activity_edit_employee.xml
 */
public class EditEmployeeActivity extends AppCompatActivity {

    private static final String TAG = "EditEmployeeActivity";

    // Déclaration des vues de l'interface utilisateur
    private TextView editHeaderTitleTextView;
    private AutoCompleteTextView editTypeSpinner;
    private TextInputEditText editNom, editPrenom, editDateNaissance, editLieuNaissance;
    private TextInputEditText editTelephone, editEmail, editProfession;
    private TextInputEditText editTauxHoraire, editFraisEcolage;
    private TextInputLayout editTauxHoraireLayout, editFraisEcolageLayout;
    private MaterialButton editSaveButton, editCancelButton;

    private DatabaseHelper databaseHelper;
    private Employee employeeToEdit;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // Assurez-vous d'avoir le bon nom de fichier de layout ici
        supportRequestWindowFeature(WindowCompat.FEATURE_ACTION_BAR_OVERLAY);
        if (getSupportActionBar() != null) {
            getSupportActionBar().hide();
        }
        setContentView(R.layout.activity_edit_employee);

        Log.d(TAG, "L'activité de modification a été créée. Tentative d'initialisation des vues.");

        databaseHelper = new DatabaseHelper(this);

        // Initialisation des vues et gestion des erreurs potentielles
        try {
            initViews();
        } catch (Exception e) {
            Log.e(TAG, "Une erreur est survenue lors de l'initialisation des vues. Vérifiez les IDs dans activity_edit_employee.xml", e);
            Toast.makeText(this, "Erreur de configuration de l'interface. Veuillez contacter le support.", Toast.LENGTH_LONG).show();
            finish();
            return; // Arrêter l'exécution si les vues ne sont pas initialisées
        }

        Intent intent = getIntent();
        if (intent != null && intent.hasExtra("employee_to_edit")) {
            Serializable serializableExtra = intent.getSerializableExtra("employee_to_edit");
            if (serializableExtra instanceof Employee) {
                employeeToEdit = (Employee) serializableExtra;
                Log.d(TAG, "Objet Employee reçu. Tentative de peuplement des champs.");
                populateFields();
            } else {
                Log.e(TAG, "L'objet Employee passé est nul ou incorrect.");
                Toast.makeText(this, "Erreur: Données de l'employé non trouvées.", Toast.LENGTH_SHORT).show();
                finish();
            }
        } else {
            Log.e(TAG, "Aucun objet Employee trouvé dans l'Intent.");
            Toast.makeText(this, "Erreur: Données de l'employé non trouvées.", Toast.LENGTH_SHORT).show();
            finish();
        }

        setupListeners();
    }

    private void initViews() {
        editHeaderTitleTextView = findViewById(R.id.editHeaderTitleTextView);
        editTypeSpinner = findViewById(R.id.editTypeSpinner);
        editNom = findViewById(R.id.editNom);
        editPrenom = findViewById(R.id.editPrenom);
        editDateNaissance = findViewById(R.id.editDateNaissance);
        editLieuNaissance = findViewById(R.id.editLieuNaissance);
        editTelephone = findViewById(R.id.editTelephone);
        editEmail = findViewById(R.id.editEmail);
        editProfession = findViewById(R.id.editProfession);
        editTauxHoraire = findViewById(R.id.editTauxHoraire);
        editFraisEcolage = findViewById(R.id.editFraisEcolage);
        editTauxHoraireLayout = findViewById(R.id.editTauxHoraireLayout);
        editFraisEcolageLayout = findViewById(R.id.editFraisEcolageLayout);
        editSaveButton = findViewById(R.id.editSaveButton);
        editCancelButton = findViewById(R.id.editCancelButton);

        // Ajout de logs pour vérifier si les vues sont trouvées
        if (editHeaderTitleTextView == null) Log.e(TAG, "editHeaderTitleTextView est nul");
        if (editTypeSpinner == null) Log.e(TAG, "editTypeSpinner est nul");
        if (editSaveButton == null) Log.e(TAG, "editSaveButton est nul");
        if (editCancelButton == null) Log.e(TAG, "editCancelButton est nul");
    }

    private void populateFields() {
        try {
            editHeaderTitleTextView.setText("Modifier " + employeeToEdit.getNom() + " " + employeeToEdit.getPrenom());

            String[] types = new String[]{"Employé", "Étudiant"};
            ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_dropdown_item_1line, types);
            editTypeSpinner.setAdapter(adapter);

            if ("employe".equalsIgnoreCase(employeeToEdit.getType())) {
                editTypeSpinner.setText("Employé", false);
                editTauxHoraire.setText(String.valueOf(employeeToEdit.getTauxHoraire()));
                updateFinancialFieldsVisibility("Employé");
            } else {
                editTypeSpinner.setText("Étudiant", false);
                editFraisEcolage.setText(String.valueOf(employeeToEdit.getFraisEcolage()));
                updateFinancialFieldsVisibility("Étudiant");
            }

            editNom.setText(employeeToEdit.getNom());
            editPrenom.setText(employeeToEdit.getPrenom());
            editDateNaissance.setText(employeeToEdit.getDateNaissance());
            editLieuNaissance.setText(employeeToEdit.getLieuNaissance());
            editTelephone.setText(employeeToEdit.getTelephone());
            editEmail.setText(employeeToEdit.getEmail());
            editProfession.setText(employeeToEdit.getProfession());

        } catch (Exception e) {
            Log.e(TAG, "Erreur lors du peuplement des champs.", e);
        }
    }

    private void setupListeners() {
        if (editTypeSpinner != null) {
            editTypeSpinner.setOnItemClickListener((parent, view, position, id) -> {
                String selectedType = (String) parent.getItemAtPosition(position);
                updateFinancialFieldsVisibility(selectedType);
            });
        }

        if (editDateNaissance != null) {
            editDateNaissance.setOnClickListener(v -> showDatePickerDialog());
        }

        if (editCancelButton != null) {
            editCancelButton.setOnClickListener(v -> {
                Log.d(TAG, "Bouton Annuler cliqué. Fermeture de l'activité.");
                finish();
            });
        }

        if (editSaveButton != null) {
            editSaveButton.setOnClickListener(v -> saveEmployeeChanges());
        }
    }

    private void updateFinancialFieldsVisibility(String type) {
        if (editTauxHoraireLayout != null && editFraisEcolageLayout != null) {
            if ("Employé".equalsIgnoreCase(type)) {
                editTauxHoraireLayout.setVisibility(View.VISIBLE);
                editFraisEcolageLayout.setVisibility(View.GONE);
            } else {
                editTauxHoraireLayout.setVisibility(View.GONE);
                editFraisEcolageLayout.setVisibility(View.VISIBLE);
            }
        }
    }

    private void showDatePickerDialog() {
        Calendar calendar = Calendar.getInstance();
        SimpleDateFormat dateFormat = new SimpleDateFormat("dd/MM/yyyy", Locale.getDefault());
        if (employeeToEdit != null && employeeToEdit.getDateNaissance() != null && !employeeToEdit.getDateNaissance().isEmpty()) {
            try {
                Date date = dateFormat.parse(employeeToEdit.getDateNaissance());
                calendar.setTime(date);
            } catch (ParseException e) {
                Log.e(TAG, "Erreur de parsing de la date de naissance.", e);
            }
        }

        int year = calendar.get(Calendar.YEAR);
        int month = calendar.get(Calendar.MONTH);
        int day = calendar.get(Calendar.DAY_OF_MONTH);

        DatePickerDialog datePickerDialog = new DatePickerDialog(this,
                (view, selectedYear, selectedMonth, selectedDay) -> {
                    String date = String.format(Locale.getDefault(), "%02d/%02d/%04d", selectedDay, selectedMonth + 1, selectedYear);
                    editDateNaissance.setText(date);
                }, year, month, day);

        datePickerDialog.show();
    }

    private void saveEmployeeChanges() {
        // ... ton code existant (validation + mise à jour de l'objet employeeToEdit)
        // ✅ Récupérer les nouvelles valeurs des champs
        employeeToEdit.setNom(editNom.getText().toString().trim());
        employeeToEdit.setPrenom(editPrenom.getText().toString().trim());
        employeeToEdit.setDateNaissance(editDateNaissance.getText().toString().trim());
        employeeToEdit.setLieuNaissance(editLieuNaissance.getText().toString().trim());
        employeeToEdit.setTelephone(editTelephone.getText().toString().trim());
        employeeToEdit.setEmail(editEmail.getText().toString().trim());
        employeeToEdit.setProfession(editProfession.getText().toString().trim());
        employeeToEdit.setType(editTypeSpinner.getText().toString().trim());

        String selectedType = editTypeSpinner.getText().toString().trim();

        if ("Employé".equalsIgnoreCase(selectedType)) {
            employeeToEdit.setType("employe"); // 🔹 en minuscules pour cohérence DB
            String taux = editTauxHoraire.getText().toString().trim();
            employeeToEdit.setTauxHoraire(taux.isEmpty() ? 0.0 : Double.parseDouble(taux));
            // ❌ ne pas écraser fraisEcolage
        } else {
            employeeToEdit.setType("etudiant"); // 🔹 en minuscules
            String frais = editFraisEcolage.getText().toString().trim();
            employeeToEdit.setFraisEcolage(frais.isEmpty() ? 0.0 : Double.parseDouble(frais));
            // ❌ ne pas écraser tauxHoraire
        }



        boolean success = databaseHelper.updateEmployee(employeeToEdit);

        if (success) {
            // ✅ Mise à jour locale OK
            Toast.makeText(this, "Modifications sauvegardées en local.", Toast.LENGTH_SHORT).show();

            // 🔄 Synchronisation serveur
            ApiService apiService = ApiClient.getClient().create(ApiService.class);
            Call<ApiResponse> call = apiService.updateEmployee(employeeToEdit.getId(), employeeToEdit);

            call.enqueue(new retrofit2.Callback<ApiResponse>() {
                @Override
                public void onResponse(Call<ApiResponse> call, retrofit2.Response<ApiResponse> response) {
                    if (response.isSuccessful() && response.body() != null) {
                        if (response.body().isSuccess()) {
                            Toast.makeText(EditEmployeeActivity.this,
                                    "Synchronisé avec le serveur ✅", Toast.LENGTH_SHORT).show();
                        } else {
                            Toast.makeText(EditEmployeeActivity.this,
                                    "Erreur serveur ❌ : " + response.body().getMessage(),
                                    Toast.LENGTH_SHORT).show();
                        }
                    } else {
                        Toast.makeText(EditEmployeeActivity.this,
                                "Erreur HTTP ❌ : " + response.code(),
                                Toast.LENGTH_SHORT).show();
                    }
                    setResult(RESULT_OK);
                    finish();
                }

                @Override
                public void onFailure(Call<ApiResponse> call, Throwable t) {
                    Toast.makeText(EditEmployeeActivity.this,
                            "Erreur réseau ❌ : " + t.getMessage(),
                            Toast.LENGTH_SHORT).show();
                    setResult(RESULT_OK);
                    finish();
                }
            });

        } else {
            Toast.makeText(this, "Erreur lors de la sauvegarde locale ❌", Toast.LENGTH_SHORT).show();
        }
    }
}