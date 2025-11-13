package com.trackingsystem.apps;

import android.content.SharedPreferences;
import android.os.Bundle;
import android.text.TextUtils;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.WindowCompat;

/**
 * Écran Paramètres
 * - Permet de changer le nom d'utilisateur et le mot de passe
 * - Pour confirmer le changement : il faut saisir l'ancien mot de passe (si déjà défini)
 * - Bouton "Réinitialiser" pour remettre les identifiants par défaut
 */
public class PointageReceiverActivity extends AppCompatActivity {

    public static final String PREF_NAME = "APP_SETTINGS";
    private static final String KEY_USER = "USER";
    private static final String KEY_PASSWORD = "PASSWORD";

    private EditText edtUser;
    private EditText edtOldPassword;
    private EditText edtNewPassword;
    private Button btnConfirm;
    private Button btnReset;

    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        supportRequestWindowFeature(WindowCompat.FEATURE_ACTION_BAR_OVERLAY);
        if (getSupportActionBar() != null) getSupportActionBar().hide();
        setContentView(R.layout.activity_pointage_receiver); // on réutilise le layout

        edtUser = findViewById(R.id.edtUser);
        edtOldPassword = findViewById(R.id.edtOldPassword);
        edtNewPassword = findViewById(R.id.edtNewPassword);
        btnConfirm = findViewById(R.id.btnSave);
        btnReset = findViewById(R.id.btnReset); // ajouter bouton Reset dans le layout

        prefs = getSharedPreferences(PREF_NAME, MODE_PRIVATE);

        // Charger valeurs existantes ou défaut
        String savedUser = prefs.getString(KEY_USER, "admin");
        edtUser.setText(savedUser);

        boolean hasPassword = !TextUtils.isEmpty(prefs.getString(KEY_PASSWORD, ""));
        if (!hasPassword) {
            btnConfirm.setText("Enregistrer (première configuration)");
            edtOldPassword.setHint("Ancien mot de passe (non requis)");
        } else {
            btnConfirm.setText("Confirmer les modifications");
            edtOldPassword.setHint("Ancien mot de passe (requis)");
        }

        btnConfirm.setOnClickListener(v -> attemptSave());

        btnReset.setOnClickListener(v -> resetDefaults());
    }

    private void attemptSave() {
        String userInput = edtUser.getText().toString().trim();
        String oldPwdInput = edtOldPassword.getText().toString();
        String newPwdInput = edtNewPassword.getText().toString();

        if (TextUtils.isEmpty(userInput)) {
            Toast.makeText(this, "Veuillez saisir le nom d'utilisateur.", Toast.LENGTH_SHORT).show();
            return;
        }
        if (TextUtils.isEmpty(newPwdInput)) {
            Toast.makeText(this, "Veuillez saisir le nouveau mot de passe.", Toast.LENGTH_SHORT).show();
            return;
        }

        String savedPwd = prefs.getString(KEY_PASSWORD, "");

        // Vérifier ancien mot de passe si déjà défini
        if (!TextUtils.isEmpty(savedPwd)) {
            if (TextUtils.isEmpty(oldPwdInput)) {
                Toast.makeText(this, "Veuillez saisir l'ancien mot de passe pour confirmer.", Toast.LENGTH_SHORT).show();
                return;
            }
            if (!savedPwd.equals(oldPwdInput)) {
                Toast.makeText(this, "Ancien mot de passe incorrect.", Toast.LENGTH_SHORT).show();
                return;
            }
        }

        // Sauvegarder les nouveaux identifiants
        SharedPreferences.Editor editor = prefs.edit();
        editor.putString(KEY_USER, userInput);
        editor.putString(KEY_PASSWORD, newPwdInput);
        editor.apply();

        Toast.makeText(this, "Identifiants mis à jour avec succès.", Toast.LENGTH_SHORT).show();
        finish();
    }

    private void resetDefaults() {
        SharedPreferences.Editor editor = prefs.edit();
        editor.putString(KEY_USER, "admin");
        editor.putString(KEY_PASSWORD, "1234");
        editor.apply();
        Toast.makeText(this, "Identifiants réinitialisés par défaut (admin / 1234).", Toast.LENGTH_SHORT).show();
    }
}
