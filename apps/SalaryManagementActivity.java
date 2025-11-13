package com.trackingsystem.apps;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.AutoCompleteTextView;
import android.widget.TextView;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;
import androidx.cardview.widget.CardView;
import androidx.core.view.WindowCompat;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import com.google.android.material.button.MaterialButton;
import com.google.android.material.datepicker.CalendarConstraints;
import com.google.android.material.datepicker.DateValidatorPointForward;
import com.google.android.material.datepicker.MaterialDatePicker;
import com.google.android.material.textfield.TextInputEditText;
import com.google.gson.Gson;
import com.trackingsystem.apps.adapters.SalaryAdapter;
import com.trackingsystem.apps.database.DatabaseHelper;
import com.trackingsystem.apps.models.ApiResponse;
import com.trackingsystem.apps.models.Employee;
import com.trackingsystem.apps.models.EmployeesResponse;
import com.trackingsystem.apps.models.Pointage;
import com.trackingsystem.apps.models.SalaryRecord;
import com.trackingsystem.apps.models.SalaryResponse;
import com.trackingsystem.apps.network.ApiClient;
import com.trackingsystem.apps.network.ApiService;
import java.text.DecimalFormat;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.Collections;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class SalaryManagementActivity extends AppCompatActivity {

    private static final String TAG = "SalaryManagement";

    private AutoCompleteTextView employeeSpinner;
    private TextInputEditText monthEditText;
    private MaterialButton calculateButton;
    private RecyclerView salaryRecyclerView;
    private SalaryAdapter salaryAdapter;
    private ArrayAdapter<String> spinnerAdapter;

    private TextView argentEntrantText;
    private TextView argentSortantText;
    private TextView beneficeText;

    private CardView employeeDetailsCard;
    private TextView selectedEmployeeName;
    private TextView selectedEmployeeProfession;
    private TextView hoursWorkedText;
    private TextView rateText;

    private DatabaseHelper databaseHelper;
    private List<Employee> employees = new ArrayList<>();
    private Employee selectedEmployee = null;
    private ApiService apiService;
    private boolean isLoadingSalaryHistory = false;
    private Gson gson = new Gson();  // Pour logger JSON

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        supportRequestWindowFeature(WindowCompat.FEATURE_ACTION_BAR_OVERLAY);
        if (getSupportActionBar() != null) {
            getSupportActionBar().hide();
        }
        setContentView(R.layout.activity_salary_management);

        databaseHelper = new DatabaseHelper(this);
        Log.d(TAG, "DatabaseHelper initialisé");

        apiService = ApiClient.getClient().create(ApiService.class);
        Log.d(TAG, "ApiService initialisé avec URL : " + ApiClient.BASE_URL);

        initializeViews();
        setupRecyclerView();
        addTestPointages();
        loadEmployeesFromDatabase();
        loadSalaryHistory();
        logPointages();
    }

    private void initializeViews() {
        employeeSpinner = findViewById(R.id.employeeSpinner);
        monthEditText = findViewById(R.id.monthEditText);
        calculateButton = findViewById(R.id.calculateButton);
        salaryRecyclerView = findViewById(R.id.salaryRecyclerView);

        argentEntrantText = findViewById(R.id.argentEntrantText);
        argentSortantText = findViewById(R.id.argentSortantText);
        beneficeText = findViewById(R.id.beneficeText);

        employeeDetailsCard = findViewById(R.id.employeeDetailsCard);
        selectedEmployeeName = findViewById(R.id.selectedEmployeeName);
        selectedEmployeeProfession = findViewById(R.id.selectedEmployeeProfession);
        hoursWorkedText = findViewById(R.id.hoursWorkedText);
        rateText = findViewById(R.id.rateText);

        calculateButton.setOnClickListener(v -> calculateSalary());
        monthEditText.setOnClickListener(v -> showMonthPicker());
        employeeSpinner.setOnItemClickListener((parent, view, position, id) -> {
            String selectedName = parent.getItemAtPosition(position).toString();
            Log.d(TAG, "Sélection dans le spinner : " + selectedName);
            if (selectedName.startsWith("Employé: ")) {
                String name = selectedName.replace("Employé: ", "");
                selectedEmployee = employees.stream()
                        .filter(emp -> (emp.getNom() + " " + emp.getPrenom()).equals(name) && "employe".equalsIgnoreCase(emp.getType()))
                        .findFirst()
                        .orElse(null);
            } else if (selectedName.startsWith("Étudiant: ")) {
                String name = selectedName.replace("Étudiant: ", "");
                selectedEmployee = employees.stream()
                        .filter(emp -> (emp.getNom() + " " + emp.getPrenom()).equals(name) && "etudiant".equalsIgnoreCase(emp.getType()))
                        .findFirst()
                        .orElse(null);
            }
            updateDetailsUI();
        });

        spinnerAdapter = new ArrayAdapter<>(this, android.R.layout.simple_dropdown_item_1line, new ArrayList<>());
        employeeSpinner.setAdapter(spinnerAdapter);
        employeeSpinner.setThreshold(1);
        Log.d(TAG, "Spinner initialisé avec seuil de complétion = 1");
    }

    private void showMonthPicker() {
        MaterialDatePicker<Long> picker = MaterialDatePicker.Builder.datePicker()
                .setTitleText("Sélectionner un mois")
                .setSelection(MaterialDatePicker.todayInUtcMilliseconds())
                .setCalendarConstraints(
                        new CalendarConstraints.Builder()
                                .setValidator(DateValidatorPointForward.now())
                                .build()
                )
                .build();

        picker.addOnPositiveButtonClickListener(selection -> {
            Calendar selectedDate = Calendar.getInstance();
            selectedDate.setTimeInMillis(selection);
            SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM", Locale.getDefault());
            monthEditText.setText(sdf.format(selectedDate.getTime()));
        });

        picker.show(getSupportFragmentManager(), "MONTH_PICKER");
    }

    private void updateDetailsUI() {
        if (selectedEmployee != null) {
            employeeDetailsCard.setVisibility(View.VISIBLE);
            selectedEmployeeName.setText(selectedEmployee.getNom() + " " + selectedEmployee.getPrenom());
            selectedEmployeeProfession.setText(selectedEmployee.getProfession() != null ?
                    selectedEmployee.getProfession() :
                    selectedEmployee.getType());

            if ("employe".equalsIgnoreCase(selectedEmployee.getType())) {
                String selectedPeriod = monthEditText.getText().toString();

                // ✅ CORRECTION: Ne calculer que si une période est sélectionnée
                if (!selectedPeriod.isEmpty()) {
                    SimpleDateFormat dateFormat = new SimpleDateFormat("yyyy-MM", Locale.getDefault());
                    String currentMonth = dateFormat.format(new Date());

                    String startDate = selectedPeriod + "-01";
                    String endDate;

                    // Si c'est le mois actuel, calculer jusqu'à aujourd'hui
                    if (selectedPeriod.equals(currentMonth)) {
                        SimpleDateFormat fullDateFormat = new SimpleDateFormat("yyyy-MM-dd", Locale.getDefault());
                        endDate = fullDateFormat.format(new Date());
                    } else {
                        endDate = getEndOfMonth(selectedPeriod);
                    }

                    Log.d(TAG, "Calcul heures pour période : " + startDate + " à " + endDate);

                    List<Pointage> pointages = databaseHelper.getPointagesForPeriod(startDate, endDate);

                    // Filtrer pour l'employé sélectionné
                    List<Pointage> employeePointages = new ArrayList<>();
                    for (Pointage p : pointages) {
                        if (p.getEmployeeId().equals(selectedEmployee.getId())) {
                            employeePointages.add(p);
                        }
                    }

                    Log.d(TAG, "Pointages trouvés pour " + selectedEmployee.getNom() + ": " + employeePointages.size());

                    double hours = calculateHoursWorked(employeePointages, selectedEmployee.getId());
                    hoursWorkedText.setText(new DecimalFormat("#.##").format(hours) + "h travaillées");

                    Log.d(TAG, "Heures calculées dans updateDetailsUI: " + hours);
                } else {
                    // ✅ Si pas de période sélectionnée, afficher un message
                    hoursWorkedText.setText("Sélectionnez une période");
                    Log.d(TAG, "Aucune période sélectionnée");
                }

                rateText.setText(selectedEmployee.getTauxHoraire() != null ?
                        new DecimalFormat("#.##").format(selectedEmployee.getTauxHoraire()) + " Ar/h" : "N/A");
            } else {
                hoursWorkedText.setText("N/A");
                rateText.setText(selectedEmployee.getFraisEcolage() != null ?
                        new DecimalFormat("#.##").format(selectedEmployee.getFraisEcolage()) + " Ar (frais)" : "N/A");
            }

            Log.d(TAG, "Détails mis à jour pour : " + selectedEmployee.getNom() + ", Type: " + selectedEmployee.getType());
        } else {
            employeeDetailsCard.setVisibility(View.GONE);
            Log.d(TAG, "Aucun employé/étudiant sélectionné");
        }
    }
    private void setupRecyclerView() {
        salaryAdapter = new SalaryAdapter(new ArrayList<>());
        salaryRecyclerView.setLayoutManager(new LinearLayoutManager(this));
        salaryRecyclerView.setAdapter(salaryAdapter);
        Log.d(TAG, "RecyclerView configuré avec SalaryAdapter");
    }

    private boolean isNetworkAvailable() {
        ConnectivityManager connectivityManager = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        NetworkInfo activeNetworkInfo = connectivityManager.getActiveNetworkInfo();
        return activeNetworkInfo != null && activeNetworkInfo.isConnected();
    }

    private void logPointages() {
        List<Pointage> pointages = databaseHelper.getAllPointages();
        SimpleDateFormat dateFormat = new SimpleDateFormat("yyyy-MM-dd", Locale.getDefault());
        String today = dateFormat.format(new Date());
        Pointage firstArrival = databaseHelper.getFirstEmployeeArrivalToday();
        Pointage lastDeparture = databaseHelper.getLastEmployeeDepartureToday();
        Log.d(TAG, "Premier pointage d'arrivée aujourd'hui : " + (firstArrival != null ? firstArrival.getEmployeeId() : "aucun"));
        Log.d(TAG, "Dernier pointage de départ aujourd'hui : " + (lastDeparture != null ? lastDeparture.getEmployeeId() : "aucun"));
        Log.d(TAG, "Nombre total de pointages locaux : " + pointages.size());
    }


    private void loadEmployeesFromDatabase() {
        employees.clear();
        employees.addAll(databaseHelper.getAllEmployees());
        Log.d(TAG, "Employés/Étudiants chargés localement : " + employees.size());

        if (!isNetworkAvailable()) {
            Log.w(TAG, "Pas de connexion réseau, utilisation des données locales");
            Toast.makeText(this, "Mode hors ligne : données locales utilisées", Toast.LENGTH_SHORT).show();
            if (employees.isEmpty()) {
                addTestData();
            }
            setupEmployeeSpinner();
            return;
        }

        Call<EmployeesResponse> call = apiService.getAllEmployees();
        call.enqueue(new Callback<EmployeesResponse>() {
            @Override
            public void onResponse(Call<EmployeesResponse> call, Response<EmployeesResponse> response) {
                if (response.isSuccessful() && response.body() != null && response.body().isSuccess()) {
                    List<Employee> serverEmployees = response.body().getEmployees();
                    for (Employee emp : serverEmployees) {
                        if (emp.getId() != null && emp.getNom() != null && emp.getPrenom() != null) {
                            long result = databaseHelper.addEmployee(emp);
                            if (result != -1) {
                                Log.d(TAG, "Employé synchronisé : " + emp.getId());
                            } else {
                                Log.w(TAG, "Échec synchronisation employé : " + emp.getId());
                            }
                        } else {
                            Log.w(TAG, "Saut de l'employé du serveur avec ID/nom/prenom null");
                        }
                    }
                    employees.clear();
                    employees.addAll(databaseHelper.getAllEmployees());
                    setupEmployeeSpinner();
                    Log.d(TAG, "✅ Employés/Étudiants synchronisés avec le serveur : " + serverEmployees.size());
                } else {
                    Log.e(TAG, "❌ Échec récupération employés, code : " + response.code());
                    Toast.makeText(SalaryManagementActivity.this, "Erreur serveur ❌ (code " + response.code() + ")", Toast.LENGTH_SHORT).show();
                }
            }

            @Override
            public void onFailure(Call<EmployeesResponse> call, Throwable t) {
                Log.e(TAG, "🌐 Erreur réseau employés : " + t.getMessage());
                Toast.makeText(SalaryManagementActivity.this, "Échec synchro : " + t.getMessage(), Toast.LENGTH_SHORT).show();
                if (employees.isEmpty()) {
                    addTestData();
                }
                setupEmployeeSpinner();
            }
        });

        if (employees.isEmpty()) {
            Log.d(TAG, "⚠️ Base locale vide → ajout données de test");
            Toast.makeText(this, "Aucun employé/étudiant trouvé localement", Toast.LENGTH_LONG).show();
            addTestData();
        }
        setupEmployeeSpinner();
    }

    private void addTestData() {
        employees.clear();

        Employee emp1 = new Employee();
        emp1.setId("1");
        emp1.setNom("Dupont");
        emp1.setPrenom("Jean");
        emp1.setType("employe");
        emp1.setTauxHoraire(15.0);
        emp1.setProfession("Professeur");
        employees.add(emp1);
        databaseHelper.addEmployee(emp1);

        Employee emp2 = new Employee();
        emp2.setId("2");
        emp2.setNom("Martin");
        emp2.setPrenom("Sophie");
        emp2.setType("etudiant");
        emp2.setFraisEcolage(500.0);
        employees.add(emp2);
        databaseHelper.addEmployee(emp2);

        Call<ApiResponse> call1 = apiService.registerEmployee(emp1);
        call1.enqueue(new Callback<ApiResponse>() {
            @Override
            public void onResponse(Call<ApiResponse> call, Response<ApiResponse> response) {
                if (response.isSuccessful() && response.body() != null) {
                    Log.d(TAG, "Employé de test (Dupont Jean) synchronisé ✅ " + response.body().getMessage());
                    setupEmployeeSpinner(); // Rafraîchir après synchro
                } else {
                    Log.e(TAG, "❌ Échec de la synchro de Dupont Jean, code : " + response.code());
                }
            }

            @Override
            public void onFailure(Call<ApiResponse> call, Throwable t) {
                Log.e(TAG, "🌐 Erreur réseau pour Dupont Jean : " + t.getMessage());
            }
        });

        Call<ApiResponse> call2 = apiService.registerEmployee(emp2);
        call2.enqueue(new Callback<ApiResponse>() {
            @Override
            public void onResponse(Call<ApiResponse> call, Response<ApiResponse> response) {
                if (response.isSuccessful() && response.body() != null) {
                    Log.d(TAG, "Employé de test (Martin Sophie) synchronisé ✅ " + response.body().getMessage());
                    setupEmployeeSpinner(); // Rafraîchir après synchro
                } else {
                    Log.e(TAG, "❌ Échec de la synchro de Martin Sophie, code : " + response.code());
                }
            }

            @Override
            public void onFailure(Call<ApiResponse> call, Throwable t) {
                Log.e(TAG, "🌐 Erreur réseau pour Martin Sophie : " + t.getMessage());
            }
        });

        Log.d(TAG, "Données de test ajoutées localement et tentative de synchronisation : " + employees.size());
    }

    private void setupEmployeeSpinner() {
        List<String> names = new ArrayList<>();
        for (Employee emp : employees) {
            String prefix = "employe".equalsIgnoreCase(emp.getType()) ? "Employé: " : "Étudiant: ";
            String fullName = emp.getNom() + " " + emp.getPrenom();
            names.add(prefix + fullName);
        }
        Log.d(TAG, "Noms dans le spinner : " + names.toString());

        spinnerAdapter.clear();
        spinnerAdapter.addAll(names);
        spinnerAdapter.notifyDataSetChanged();
        employeeSpinner.post(() -> {
            employeeSpinner.setAdapter(spinnerAdapter);
            Log.d(TAG, "Spinner mis à jour avec " + names.size() + " éléments");
        });
    }

    private String getEndOfMonth(String yearMonth) {
        try {
            Calendar cal = Calendar.getInstance(Locale.getDefault());
            cal.set(Calendar.YEAR, Integer.parseInt(yearMonth.substring(0, 4)));
            cal.set(Calendar.MONTH, Integer.parseInt(yearMonth.substring(5)) - 1); // Mois 0-based
            cal.set(Calendar.DAY_OF_MONTH, 1);
            cal.add(Calendar.MONTH, 1);
            cal.add(Calendar.DAY_OF_MONTH, -1); // Dernier jour du mois
            SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd", Locale.getDefault());
            return sdf.format(cal.getTime());
        } catch (Exception e) {
            Log.e(TAG, "Erreur calcul fin de mois pour " + yearMonth + " : " + e.getMessage());
            return yearMonth + "-31"; // Fallback
        }
    }

    // ✅ MODIFICATION 1: Dans calculateSalary() - Modifier la logique de période

    private void calculateSalary() {
        Log.d(TAG, "Début de calculateSalary()");

        if (selectedEmployee == null) {
            Log.e(TAG, "Erreur : aucun employé/étudiant sélectionné");
            Toast.makeText(this, "Veuillez sélectionner un employé ou un étudiant", Toast.LENGTH_SHORT).show();
            return;
        }

        if (monthEditText.getText().toString().isEmpty()) {
            Log.e(TAG, "Erreur : période non sélectionnée");
            Toast.makeText(this, "Veuillez sélectionner une période", Toast.LENGTH_SHORT).show();
            return;
        }

        Log.d(TAG, "Employé sélectionné : ID=" + selectedEmployee.getId() + ", Type=" + selectedEmployee.getType());

        // ✅ CAS : ETUDIANT → Frais d'écolage
        if ("etudiant".equalsIgnoreCase(selectedEmployee.getType())) {

            double frais = selectedEmployee.getFraisEcolage() != null ? selectedEmployee.getFraisEcolage() : 0.0;

            if (frais <= 0) {
                Log.e(TAG, "Erreur : les frais d'écolage sont invalides (0 Ar)");
                Toast.makeText(this, "Erreur : les frais d'écolage sont invalides (0 Ar)", Toast.LENGTH_SHORT).show();
                return;
            }

            Log.d(TAG, "Calcul frais d'écolage : " + frais + " Ar pour " + selectedEmployee.getNom());
            Toast.makeText(this, "Frais d'écolage : " + new DecimalFormat("#.##").format(frais) + " Ar", Toast.LENGTH_LONG).show();
            saveEcolageCalculation(frais);
            return;
        }

        // ✅ CAS : EMPLOYÉ → Salaire basé sur les pointages
        String selectedPeriod = monthEditText.getText().toString(); // Format : yyyy-MM
        String startDate = selectedPeriod + "-01";                  // Premier jour du mois
        String endDate = getEndOfMonth(selectedPeriod);             // Dernier jour du mois

        // Si le mois sélectionné est le mois actuel → jusqu'à aujourd'hui
        SimpleDateFormat dateFormat = new SimpleDateFormat("yyyy-MM", Locale.getDefault());
        String currentMonth = dateFormat.format(new Date());

        if (selectedPeriod.equals(currentMonth)) {
            SimpleDateFormat fullDateFormat = new SimpleDateFormat("yyyy-MM-dd", Locale.getDefault());
            endDate = fullDateFormat.format(new Date());
            Log.d(TAG, "Mois en cours détecté, calcul jusqu'à aujourd'hui : " + endDate);
        }

        Log.d(TAG, "🔍 Recherche pointages pour période: " + startDate + " à " + endDate);

        // 🚨 Récupération des pointages
        List<Pointage> allPointages = databaseHelper.getPointagesForPeriod(startDate, endDate);
        Log.d(TAG, "📊 Nombre TOTAL de pointages trouvés : " + allPointages.size());

        List<Pointage> employeePointages = new ArrayList<>();
        for (Pointage p : allPointages) {
            if (p.getEmployeeId().equals(selectedEmployee.getId())) {
                employeePointages.add(p);
                Log.d(TAG, "  ✅ Pointage valide: type=" + p.getType() +
                        ", date=" + p.getDate() +
                        ", timestamp=" + new Date(p.getTimestamp()));
            }
        }

        Log.d(TAG, "📊 Pointages filtrés pour cet employé : " + employeePointages.size());

        if (employeePointages.isEmpty()) {
            Log.w(TAG, "⚠ Aucun pointage dans cette période");
            Toast.makeText(this, "Aucun pointage trouvé pour cette période", Toast.LENGTH_LONG).show();
            return;
        }

        // ✅ Calcul des heures travaillées
        double hours = calculateHoursWorked(employeePointages, selectedEmployee.getId());
        double rate = selectedEmployee.getTauxHoraire() != null ? selectedEmployee.getTauxHoraire() : 15.0;
        double salary = hours * rate;

        Log.d(TAG, "💰 Calcul final: heures=" + hours + ", taux=" + rate + "Ar/h, salaire=" + salary + " Ar");

        if (salary <= 0) {
            Log.e(TAG, "❌ Salaire = 0 Ar");
            Toast.makeText(this, "Aucune heure valide détectée.", Toast.LENGTH_LONG).show();
            return;
        }

        // ✅ Sauvegarde du salaire
        saveSalaryCalculation(hours, rate, salary);

        // ✅ RÉINITIALISATION DES POINTAGES APRÈS PAIEMENT
        databaseHelper.resetPointagesForEmployee(selectedEmployee.getId(), startDate, endDate);

        Toast.makeText(this,
                "Salaire calculé ✅\n" +
                        "Montant : " + new DecimalFormat("#.##").format(salary) + " Ar\n" +
                        "Heures travaillées : " + hours + " h\n" +
                        "📌 Les heures ont été réinitialisées.",
                Toast.LENGTH_LONG).show();

        updateDetailsUI();  // Rafraîchit l’affichage
    }

    private double calculateHoursWorked(List<Pointage> pointages, String employeeId) {
        double totalHours = 0;
        Pointage arrival = null;
        int pairsFound = 0;

        Log.d(TAG, "=== Début calcul heures pour employeeId=" + employeeId + " ===");
        Log.d(TAG, "Nombre de pointages à traiter: " + pointages.size());

        // ✅ Trier par timestamp pour garantir l'ordre chronologique
        Collections.sort(pointages, (p1, p2) -> Long.compare(p1.getTimestamp(), p2.getTimestamp()));

        for (Pointage pointage : pointages) {
            if (!pointage.getEmployeeId().equals(employeeId)) {
                continue; // Ignorer les pointages d'autres employés
            }

            Log.d(TAG, "Traitement pointage: type=" + pointage.getType() +
                    ", date=" + pointage.getDate() +
                    ", timestamp=" + new SimpleDateFormat("dd/MM/yyyy HH:mm:ss", Locale.getDefault()).format(new Date(pointage.getTimestamp())));

            // ✅ Utiliser equalsIgnoreCase pour éviter les problèmes de casse
            if ("arrivee".equalsIgnoreCase(pointage.getType())) {
                if (arrival != null) {
                    Log.w(TAG, "⚠️ Arrivée sans sortie précédente détectée, remplacement");
                }
                arrival = pointage;
                Log.d(TAG, "✅ Pointage ARRIVÉE enregistré");
            }
            else if ("sortie".equalsIgnoreCase(pointage.getType())) {
                if (arrival != null) {
                    long durationMillis = pointage.getTimestamp() - arrival.getTimestamp();
                    double hours = durationMillis / (1000.0 * 60 * 60);

                    if (hours < 0) {
                        Log.e(TAG, "❌ Durée négative détectée ! Arrivée après sortie ?");
                    } else if (hours > 24) {
                        Log.w(TAG, "⚠️ Durée supérieure à 24h détectée: " + hours + "h");
                    } else {
                        totalHours += hours;
                        pairsFound++;

                        SimpleDateFormat timeFormat = new SimpleDateFormat("HH:mm:ss", Locale.getDefault());
                        Log.d(TAG, "✅ Paire complète #" + pairsFound + ": " +
                                timeFormat.format(new Date(arrival.getTimestamp())) + " → " +
                                timeFormat.format(new Date(pointage.getTimestamp())) +
                                " = " + String.format("%.2f", hours) + "h");
                    }

                    arrival = null; // Réinitialiser pour la prochaine paire
                } else {
                    Log.w(TAG, "⚠️ Pointage SORTIE sans ARRIVÉE correspondante (ignoré)");
                }
            } else {
                Log.w(TAG, "⚠️ Type de pointage inconnu: " + pointage.getType());
            }
        }

        if (arrival != null) {
            Log.w(TAG, "⚠️ Dernière arrivée sans sortie correspondante");
        }

        Log.d(TAG, "=== Résultat final ===");
        Log.d(TAG, "Paires complètes trouvées: " + pairsFound);
        Log.d(TAG, "Total heures calculées: " + String.format("%.2f", totalHours) + "h");
        Log.d(TAG, "=====================");

        return totalHours;
    }

// ✅ MODIFICATION 3: Corriger addTestPointages pour septembre

    private void addTestPointages() {
        Employee testEmployee = new Employee();
        testEmployee.setId("49876b20-faa0-4ad8-87eb-acace9f4e0ff");
        testEmployee.setNom("Tero");
        testEmployee.setPrenom("Fun");
        testEmployee.setType("employe");
        testEmployee.setTauxHoraire(15.0);
        testEmployee.setProfession("Professeur");
        long result = databaseHelper.addEmployee(testEmployee);
        if (result != -1) {
            Log.d(TAG, "Employé de test ajouté : Tero Fun");
        }

        Calendar calendar = Calendar.getInstance();

        // ✅ CORRECTION: Créer des pointages pour OCTOBRE 2025 (mois actuel)
        calendar.set(2025, Calendar.OCTOBER, 15); // 15 octobre 2025
        SimpleDateFormat dateFormat = new SimpleDateFormat("yyyy-MM-dd", Locale.getDefault());
        String testDate = dateFormat.format(calendar.getTime());

        // Arrivée à 8h00
        calendar.set(Calendar.HOUR_OF_DAY, 8);
        calendar.set(Calendar.MINUTE, 0);
        calendar.set(Calendar.SECOND, 0);

        Pointage arrival = new Pointage();
        arrival.setId(String.valueOf(System.currentTimeMillis()));
        arrival.setEmployeeId("49876b20-faa0-4ad8-87eb-acace9f4e0ff");
        arrival.setEmployeeName("Tero Fun");
        arrival.setType("arrivee"); // ✅ minuscules
        arrival.setTimestamp(calendar.getTimeInMillis());
        arrival.setDate(testDate);
        databaseHelper.addPointage(arrival);

        Log.d(TAG, "Pointage ARRIVÉE ajouté: " + testDate + " à 08:00");

        // Sortie à 17h00 (9 heures de travail)
        calendar.set(Calendar.HOUR_OF_DAY, 17);
        calendar.set(Calendar.MINUTE, 0);

        Pointage departure = new Pointage();
        departure.setId(String.valueOf(System.currentTimeMillis() + 1));
        departure.setEmployeeId("49876b20-faa0-4ad8-87eb-acace9f4e0ff");
        departure.setEmployeeName("Tero Fun");
        departure.setType("sortie"); // ✅ minuscules
        departure.setTimestamp(calendar.getTimeInMillis());
        departure.setDate(testDate);
        databaseHelper.addPointage(departure);

        Log.d(TAG, "Pointage SORTIE ajouté: " + testDate + " à 17:00");
        Log.d(TAG, "Heures attendues: 9h (de 8h à 17h)");
    }    private void saveSalaryCalculation(double hours, double rate, double salary) {
        if (selectedEmployee == null || selectedEmployee.getId() == null) {
            Log.e(TAG, "Erreur : employé non sélectionné ou ID null");
            Toast.makeText(this, "Veuillez sélectionner un employé valide", Toast.LENGTH_SHORT).show();
            return;
        }
        if (salary <= 0) {
            Log.e(TAG, "Erreur : salaire calculé invalide (0€)");
            Toast.makeText(this, "Erreur : salaire invalide", Toast.LENGTH_SHORT).show();
            return;
        }

        SalaryRecord record = new SalaryRecord();
        record.setId(String.valueOf(System.currentTimeMillis()));
        record.setEmployeeId(selectedEmployee.getId());
        record.setEmployeeName(selectedEmployee.getNom() + " " + selectedEmployee.getPrenom());
        record.setType("salaire");
        record.setAmount(salary);
        record.setHoursWorked(hours);
        record.setPeriod(monthEditText.getText().toString());
        record.setDate(System.currentTimeMillis());
        record.setSynced(false);

        long localResult = databaseHelper.addSalaryRecord(record);
        if (localResult != -1) {
            Log.d(TAG, "Salaire enregistré localement : ID=" + record.getId() + ", montant=" + salary);
            Toast.makeText(this, "Salaire enregistré localement ✅", Toast.LENGTH_SHORT).show();
            syncSalaryRecord(record);
            loadSalaryHistory();
        } else {
            Log.e(TAG, "Erreur lors de l'enregistrement local du salaire");
            Toast.makeText(this, "Erreur lors de l'enregistrement local ❌", Toast.LENGTH_SHORT).show();
        }
    }

    private void saveEcolageCalculation(double frais) {
        if (selectedEmployee == null || selectedEmployee.getId() == null) {
            Log.e(TAG, "Erreur : étudiant non sélectionné ou ID null");
            Toast.makeText(this, "Veuillez sélectionner un étudiant valide", Toast.LENGTH_SHORT).show();
            return;
        }
        if (frais <= 0) {
            Log.e(TAG, "Erreur : frais d'écolage invalide (0€)");
            Toast.makeText(this, "Erreur : frais d'écolage invalide", Toast.LENGTH_SHORT).show();
            return;
        }

        SalaryRecord record = new SalaryRecord();
        record.setId(String.valueOf(System.currentTimeMillis()));
        record.setEmployeeId(selectedEmployee.getId());
        record.setEmployeeName(selectedEmployee.getNom() + " " + selectedEmployee.getPrenom());
        record.setType("ecolage");
        record.setAmount(frais);
        record.setHoursWorked(0.0);
        record.setPeriod(monthEditText.getText().toString());
        record.setDate(System.currentTimeMillis());
        record.setSynced(false);

        long localResult = databaseHelper.addSalaryRecord(record);
        if (localResult != -1) {
            Log.d(TAG, "Frais d'écolage enregistré localement : ID=" + record.getId() + ", montant=" + frais);
            Toast.makeText(this, "Frais d'écolage enregistré localement ✅", Toast.LENGTH_SHORT).show();
            syncSalaryRecord(record);
            loadSalaryHistory();
        } else {
            Log.e(TAG, "Erreur lors de l'enregistrement local des frais d'écolage");
            Toast.makeText(this, "Erreur lors de l'enregistrement local ❌", Toast.LENGTH_SHORT).show();
        }
    }

    private void syncSalaryRecord(SalaryRecord record) {
        if (!isNetworkAvailable()) {
            Log.w(TAG, "Pas de connexion réseau, salaire/écolage enregistré localement");
            Toast.makeText(this, "Pas de connexion, enregistrement local", Toast.LENGTH_SHORT).show();
            return;
        }

        Call<ApiResponse> call = apiService.saveSalaryRecord(record);
        call.enqueue(new Callback<ApiResponse>() {
            @Override
            public void onResponse(Call<ApiResponse> call, Response<ApiResponse> response) {
                if (response.isSuccessful() && response.body() != null) {
                    databaseHelper.markSalaryRecordAsSynced(record.getId());
                    Log.d(TAG, "Enregistrement synchronisé ✅ : " + response.body().getMessage());
                    Toast.makeText(SalaryManagementActivity.this, "Synchronisation réussie ✅", Toast.LENGTH_SHORT).show();
                } else {
                    Log.e(TAG, "❌ Échec synchro serveur, code : " + response.code());
                    Toast.makeText(SalaryManagementActivity.this, "Erreur serveur ❌ (code " + response.code() + ")", Toast.LENGTH_SHORT).show();
                }
            }

            @Override
            public void onFailure(Call<ApiResponse> call, Throwable t) {
                Log.e(TAG, "🌐 Erreur réseau synchro : " + t.getMessage());
                Toast.makeText(SalaryManagementActivity.this, "Pas de connexion au serveur 🌐", Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void syncUnsyncedRecords() {
        if (!isNetworkAvailable()) {
            Log.w(TAG, "Pas de connexion réseau, synchronisation des enregistrements non effectuée");
            return;
        }

        List<SalaryRecord> unsyncedRecords = databaseHelper.getUnsyncedSalaryRecords();
        if (unsyncedRecords.isEmpty()) {
            Log.d(TAG, "Aucun enregistrement non synchronisé à envoyer");
            return;
        }

        for (SalaryRecord record : unsyncedRecords) {
            Call<ApiResponse> call = apiService.saveSalaryRecord(record);
            call.enqueue(new Callback<ApiResponse>() {
                @Override
                public void onResponse(Call<ApiResponse> call, Response<ApiResponse> response) {
                    if (response.isSuccessful() && response.body() != null) {
                        databaseHelper.markSalaryRecordAsSynced(record.getId());
                        Log.d(TAG, "Enregistrement non synchronisé envoyé : ID=" + record.getId());
                    } else {
                        Log.e(TAG, "❌ Échec synchro enregistrement non synchronisé, ID=" + record.getId() + ", code : " + response.code());
                    }
                }

                @Override
                public void onFailure(Call<ApiResponse> call, Throwable t) {
                    Log.e(TAG, "🌐 Erreur réseau pour enregistrement non synchronisé, ID=" + record.getId() + ": " + t.getMessage());
                }
            });
        }
    }
    private void loadSalaryHistory() {
        if (isLoadingSalaryHistory) return;
        isLoadingSalaryHistory = true;

        // Charger les enregistrements locaux
        List<SalaryRecord> localRecords = databaseHelper.getAllSalaryRecords();
        salaryAdapter.updateSalaryRecords(localRecords);
        updateFinancialStatistics(localRecords);
        Log.d(TAG, "📊 Enregistrements locaux affichés : " + localRecords.size());

        if (!isNetworkAvailable()) {
            Log.w(TAG, "Pas de connexion réseau, utilisation des données locales");
            Toast.makeText(this, "Mode hors ligne : données locales utilisées", Toast.LENGTH_SHORT).show();
            isLoadingSalaryHistory = false;
            return;
        }

        // Synchroniser les enregistrements non synchronisés
        syncUnsyncedRecords();

        // Récupérer les enregistrements du serveur
        Call<SalaryResponse> call = apiService.getSalaryHistory();
        call.enqueue(new Callback<SalaryResponse>() {
            @Override
            public void onResponse(Call<SalaryResponse> call, Response<SalaryResponse> response) {
                if (response.isSuccessful() && response.body() != null) {
                    SalaryResponse body = response.body();

                    if (body.isSuccess() && body.getSalaries() != null) {
                        List<SalaryRecord> serverRecords = body.getSalaries();
                        Log.d(TAG, "📥 Reçu du serveur : " + serverRecords.size() + " enregistrements");

                        // ✅ AJOUTER CES LOGS AVANT LE FILTRAGE
                        for (int i = 0; i < Math.min(3, serverRecords.size()); i++) {
                            SalaryRecord r = serverRecords.get(i);
                            Log.d(TAG, "🔍 Record " + i + ": " +
                                    "ID=" + r.getId() +
                                    ", EmployeeId=" + r.getEmployeeId() +
                                    ", EmployeeName='" + r.getEmployeeName() + "'" +
                                    ", Amount=" + r.getAmount() +
                                    ", Type=" + r.getType());
                        }

                        int added = 0;
                        int updated = 0;

                        for (SalaryRecord record : serverRecords) {
                            // ✅ LOG DÉTAILLÉ DU REJET
                            if (record.getEmployeeId() == null || record.getAmount() <= 0) {
                                Log.w(TAG, "⚠️ Record invalide ignoré : " + record.getId() +
                                        " | EmployeeId=" + record.getEmployeeId() +
                                        " | EmployeeName='" + record.getEmployeeName() + "'" +
                                        " | Amount=" + record.getAmount());
                                continue;
                            }
                            SalaryRecord localRecord = databaseHelper.getSalaryRecordById(record.getId());
                            if (localRecord == null) {
                                record.setSynced(true);
                                databaseHelper.addSalaryRecord(record);
                                added++;
                                Log.d(TAG, "➕ Nouveau record ajouté : " + record.getId());
                            } else if (!localRecord.isSynced()) {
                                // Mettre à jour seulement si pas encore synchronisé
                                record.setSynced(true);
                                databaseHelper.addOrUpdateSalaryRecord(record);
                                updated++;
                                Log.d(TAG, "🔄 Record mis à jour : " + record.getId());
                            }
                        }

                        // Recharger TOUTES les données locales après traitement
                        List<SalaryRecord> finalRecords = databaseHelper.getAllSalaryRecords();
                        Log.d(TAG, "✅ Total final dans la BD : " + finalRecords.size());

                        // Mettre à jour l'UI sur le thread principal
                        int finalAdded = added;
                        int finalUpdated = updated;
                        runOnUiThread(() -> {
                            salaryAdapter.updateSalaryRecords(finalRecords);
                            updateFinancialStatistics(finalRecords);

                            String message = String.format("Synchronisation : %d ajoutés, %d mis à jour", finalAdded, finalUpdated);
                            Toast.makeText(SalaryManagementActivity.this, message, Toast.LENGTH_SHORT).show();
                            Log.d(TAG, "🎨 UI mise à jour avec " + finalRecords.size() + " enregistrements");
                        });

                    } else {
                        Log.e(TAG, "❌ Réponse serveur non success : " + body.getMessage());
                        runOnUiThread(() -> {
                            Toast.makeText(SalaryManagementActivity.this,
                                    "Erreur : " + body.getMessage(), Toast.LENGTH_SHORT).show();
                        });
                    }
                } else {
                    Log.e(TAG, "❌ Erreur HTTP " + response.code());
                    runOnUiThread(() -> {
                        Toast.makeText(SalaryManagementActivity.this,
                                "Erreur serveur (code " + response.code() + ")", Toast.LENGTH_SHORT).show();
                    });
                }
                isLoadingSalaryHistory = false;
            }

            @Override
            public void onFailure(Call<SalaryResponse> call, Throwable t) {
                Log.e(TAG, "🌐 Erreur réseau : " + t.getMessage(), t);
                runOnUiThread(() -> {
                    Toast.makeText(SalaryManagementActivity.this,
                            "Pas de connexion au serveur", Toast.LENGTH_SHORT).show();
                });
                isLoadingSalaryHistory = false;
            }
        });
    }
    private void updateFinancialStatistics(List<SalaryRecord> records) {
        double totalIncoming = 0;
        double totalOutgoing = 0;

        Log.d(TAG, "Calcul des statistiques pour " + records.size() + " enregistrements:");

        for (SalaryRecord record : records) {
            Log.d(TAG, "Record: ID=" + record.getId() +
                    ", Type=" + record.getType() +
                    ", Amount=" + record.getAmount() +
                    ", Employee=" + record.getEmployeeName());

            if (record.getAmount() <= 0) {
                Log.w(TAG, "Record ignoré (montant <= 0): " + record.getId());
                continue;
            }

            if ("ecolage".equalsIgnoreCase(record.getType())) {
                totalIncoming += record.getAmount();
                Log.d(TAG, "Ajout écolage: +" + record.getAmount() + " (total: " + totalIncoming + ")");
            } else if ("salaire".equalsIgnoreCase(record.getType())) {
                totalOutgoing += record.getAmount();
                Log.d(TAG, "Ajout salaire: +" + record.getAmount() + " (total: " + totalOutgoing + ")");
            } else {
                Log.w(TAG, "Type non reconnu: " + record.getType() + " pour record " + record.getId());
            }
        }

        double netBenefit = totalIncoming - totalOutgoing;
        DecimalFormat df = new DecimalFormat("#,##0.00 Ar");

        // ✅ CORRECTION: S'assurer que l'UI est mise à jour sur le thread principal
        double finalTotalIncoming = totalIncoming;
        double finalTotalOutgoing = totalOutgoing;
        runOnUiThread(() -> {
            argentEntrantText.setText(df.format(finalTotalIncoming));
            argentSortantText.setText(df.format(finalTotalOutgoing));
            beneficeText.setText(df.format(netBenefit));

            Log.d(TAG, "✅ Statistiques mises à jour: " +
                    "Entrant=" + finalTotalIncoming +
                    ", Sortant=" + finalTotalOutgoing +
                    ", Bénéfice=" + netBenefit);
        });

        if (records.isEmpty()) {
            Log.w(TAG, "Aucun enregistrement de salaire ou écolage trouvé");
            runOnUiThread(() -> {
                Toast.makeText(this, "Aucun enregistrement trouvé", Toast.LENGTH_SHORT).show();
            });
        } else if (totalIncoming == 0 && totalOutgoing == 0) {
            Log.w(TAG, "Enregistrements trouvés mais aucun montant valide");
            runOnUiThread(() -> {
                Toast.makeText(this, "Données présentes mais montants invalides", Toast.LENGTH_SHORT).show();
            });
        }
    }}