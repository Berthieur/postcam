package com.trackingsystem.apps;

import android.graphics.Color;
import android.os.Bundle;
import android.util.Log;
import android.widget.TextView;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.WindowCompat;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import com.github.mikephil.charting.charts.BarChart;
import com.github.mikephil.charting.charts.LineChart;
import com.github.mikephil.charting.charts.PieChart;
import com.github.mikephil.charting.data.*;
import com.github.mikephil.charting.components.XAxis;
import com.github.mikephil.charting.components.YAxis;
import com.github.mikephil.charting.formatter.IndexAxisValueFormatter;
import com.trackingsystem.apps.adapters.MovementAdapter;
import com.trackingsystem.apps.models.Employee;
import com.trackingsystem.apps.models.EmployeesResponse;
import com.trackingsystem.apps.models.MovementRecord;
import com.trackingsystem.apps.models.Pointage;
import com.trackingsystem.apps.database.DatabaseHelper;
import com.trackingsystem.apps.models.SalaryRecord;
import com.trackingsystem.apps.models.SalaryResponse;
import com.trackingsystem.apps.network.ApiClient;
import com.trackingsystem.apps.network.ApiService;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import retrofit2.Callback;
import retrofit2.Call;
import retrofit2.Response;

public class StatisticsActivity extends AppCompatActivity {

    private static final String TAG = "StatisticsActivity";
    private LineChart dailyActivityChart;
    private TextView totalEmployeesText;
    private TextView totalStudentsText;
    private TextView presenceRateText;
    private TextView absenceRateText;
    private BarChart financialChart;
    private PieChart presenceChart;
    private TextView employeePresenceRateText;
    private TextView employeeAbsenceRateText;
    private TextView studentPresenceRateText;
    private TextView studentAbsenceRateText;
    private RecyclerView pointageListRecyclerView;
    private MovementAdapter pointageAdapter;

    private DatabaseHelper databaseHelper;
    private List<Employee> employees;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        supportRequestWindowFeature(WindowCompat.FEATURE_ACTION_BAR_OVERLAY);
        if (getSupportActionBar() != null) {
            getSupportActionBar().hide();
        }
        setContentView(R.layout.activity_statistics);

        databaseHelper = new DatabaseHelper(this);
        employees = new ArrayList<>();

        initializeViews();
        setupCharts();

        // Charger les données locales d'abord
        loadLocalData();

        // Puis synchroniser avec le serveur
        loadEmployees();
        loadFinancialDataFromServer();
    }

    private void initializeViews() {
        dailyActivityChart = findViewById(R.id.dailyActivityChart);
        totalEmployeesText = findViewById(R.id.totalEmployeesText);
        totalStudentsText = findViewById(R.id.totalStudentsText);
        presenceRateText = findViewById(R.id.presenceRateText);
        absenceRateText = findViewById(R.id.absenceRateText);

        financialChart = findViewById(R.id.financialChart);
        presenceChart = findViewById(R.id.presenceChart);

        pointageListRecyclerView = findViewById(R.id.pointageListRecyclerView);
        pointageListRecyclerView.setLayoutManager(new LinearLayoutManager(this));

        employeePresenceRateText = findViewById(R.id.employeePresenceRateText);
        employeeAbsenceRateText = findViewById(R.id.employeeAbsenceRateText);
        studentPresenceRateText = findViewById(R.id.studentPresenceRateText);
        studentAbsenceRateText = findViewById(R.id.studentAbsenceRateText);
    }

    private void setupCharts() {
        financialChart.setNoDataText("Chargement...");
        presenceChart.setNoDataText("Chargement...");
        dailyActivityChart.setNoDataText("Chargement...");
    }

    private void loadLocalData() {
        employees = databaseHelper.getAllEmployees();
        if (employees != null) {
            updateEmployeeKpis(employees);
            loadPresenceData(employees);
        }
        loadFinancialData();
        loadDailyActivityData();
        loadPointageList();
    }

    private void loadEmployees() {
        employees = databaseHelper.getAllEmployees();
        if (employees != null) {
            updateEmployeeKpis(employees);
            loadPresenceData(employees);
        }

        ApiService apiService = ApiClient.getClient().create(ApiService.class);
        Call<EmployeesResponse> call = apiService.getAllEmployees();
        call.enqueue(new Callback<EmployeesResponse>() {
            @Override
            public void onResponse(Call<EmployeesResponse> call, Response<EmployeesResponse> response) {
                if (response.isSuccessful() && response.body() != null && response.body().isSuccess()) {
                    List<Employee> serverEmployees = response.body().getEmployees();

                    for (Employee emp : serverEmployees) {
                        databaseHelper.addEmployee(emp);
                    }

                    employees = databaseHelper.getAllEmployees();
                    updateEmployeeKpis(employees);
                    loadPresenceData(employees);

                    Log.d(TAG, "Employés synchronisés: " + serverEmployees.size());
                } else {
                    Log.e(TAG, "Erreur synchro employés: " + response.code());
                }
            }

            @Override
            public void onFailure(Call<EmployeesResponse> call, Throwable t) {
                Log.e(TAG, "Erreur réseau employés", t);
            }
        });
    }

    private void updateEmployeeKpis(List<Employee> employees) {
        int totalEmployees = 0;
        int totalStudents = 0;

        for (Employee emp : employees) {
            if ("employe".equalsIgnoreCase(emp.getType())) {
                totalEmployees++;
            } else if ("etudiant".equalsIgnoreCase(emp.getType())) {
                totalStudents++;
            }
        }

        totalEmployeesText.setText(String.valueOf(totalEmployees));
        totalStudentsText.setText(String.valueOf(totalStudents));

        Log.d(TAG, "Employés: " + totalEmployees + ", Étudiants: " + totalStudents);
    }

    private void loadFinancialDataFromServer() {
        ApiService apiService = ApiClient.getClient().create(ApiService.class);
        Call<SalaryResponse> call = apiService.getSalaryHistory();

        call.enqueue(new Callback<SalaryResponse>() {
            @Override
            public void onResponse(Call<SalaryResponse> call, Response<SalaryResponse> response) {
                if (response.isSuccessful() && response.body() != null && response.body().isSuccess()) {
                    List<SalaryRecord> serverRecords = response.body().getSalaries();
                    if (serverRecords != null) {
                        Log.d(TAG, "Records financiers reçus: " + serverRecords.size());

                        // Sauvegarder en local
                        for (SalaryRecord record : serverRecords) {
                            if (record.getEmployeeId() != null && record.getAmount() > 0) {
                                record.setSynced(true);
                                databaseHelper.addSalaryRecord(record);
                            }
                        }

                        // Recharger les graphiques
                        runOnUiThread(() -> loadFinancialData());
                    }
                } else {
                    Log.e(TAG, "Erreur synchro finances: " + response.code());
                }
            }

            @Override
            public void onFailure(Call<SalaryResponse> call, Throwable t) {
                Log.e(TAG, "Erreur réseau finances", t);
            }
        });
    }

    private void loadFinancialData() {
        List<SalaryRecord> allSalaryRecords = databaseHelper.getAllSalaryRecords();

        if (allSalaryRecords == null || allSalaryRecords.isEmpty()) {
            financialChart.setNoDataText("Aucune donnée financière");
            financialChart.invalidate();
            return;
        }

        Map<String, Double> monthlyRevenues = new HashMap<>();
        Map<String, Double> monthlyExpenses = new HashMap<>();
        SimpleDateFormat yearMonthFormat = new SimpleDateFormat("yyyy-MM", Locale.FRENCH);

        Log.d(TAG, "Traitement de " + allSalaryRecords.size() + " records financiers");

        for (SalaryRecord record : allSalaryRecords) {
            try {
                Date recordDate = new Date(record.getDate());
                String monthKey = yearMonthFormat.format(recordDate);
                double amount = record.getAmount();

                if ("ecolage".equalsIgnoreCase(record.getType())) {
                    monthlyRevenues.put(monthKey, monthlyRevenues.getOrDefault(monthKey, 0.0) + amount);
                } else if ("salaire".equalsIgnoreCase(record.getType())) {
                    monthlyExpenses.put(monthKey, monthlyExpenses.getOrDefault(monthKey, 0.0) + amount);
                }
            } catch (Exception e) {
                Log.e(TAG, "Erreur traitement record", e);
            }
        }

        List<String> months = new ArrayList<>(monthlyRevenues.keySet());
        months.addAll(monthlyExpenses.keySet());
        Set<String> uniqueMonthsSet = new HashSet<>(months);
        List<String> uniqueMonths = new ArrayList<>(uniqueMonthsSet);
        Collections.sort(uniqueMonths);

        List<BarEntry> revenueEntries = new ArrayList<>();
        List<BarEntry> expenseEntries = new ArrayList<>();

        for (int i = 0; i < uniqueMonths.size(); i++) {
            String monthKey = uniqueMonths.get(i);
            revenueEntries.add(new BarEntry(i, monthlyRevenues.getOrDefault(monthKey, 0.0).floatValue()));
            expenseEntries.add(new BarEntry(i, monthlyExpenses.getOrDefault(monthKey, 0.0).floatValue()));
        }

        BarDataSet revenueDataSet = new BarDataSet(revenueEntries, "Revenus (Écolage)");
        revenueDataSet.setColor(Color.parseColor("#38A03E"));

        BarDataSet expenseDataSet = new BarDataSet(expenseEntries, "Dépenses (Salaires)");
        expenseDataSet.setColor(Color.parseColor("#FF4500"));

        BarData barData = new BarData(revenueDataSet, expenseDataSet);

        financialChart.setData(barData);
        financialChart.getBarData().setBarWidth(0.35f);
        financialChart.getXAxis().setAxisMinimum(-0.5f);
        financialChart.getXAxis().setAxisMaximum(barData.getGroupWidth(0.4f, 0.2f) * uniqueMonths.size());
        financialChart.groupBars(0f, 0.4f, 0.2f);
        financialChart.getDescription().setEnabled(false);

        XAxis xAxis = financialChart.getXAxis();
        xAxis.setValueFormatter(new IndexAxisValueFormatter(uniqueMonths));
        xAxis.setPosition(XAxis.XAxisPosition.BOTTOM);
        xAxis.setGranularity(1f);
        xAxis.setCenterAxisLabels(true);

        YAxis leftAxis = financialChart.getAxisLeft();
        leftAxis.setAxisMinimum(0f);

        YAxis rightAxis = financialChart.getAxisRight();
        rightAxis.setEnabled(false);

        financialChart.invalidate();
    }

    private void loadPresenceData(List<Employee> allEmployees) {
        int totalEmployees = 0;
        int totalStudents = 0;
        Map<String, String> employeeTypeMap = new HashMap<>();

        for (Employee emp : allEmployees) {
            employeeTypeMap.put(emp.getId(), emp.getType());
            if ("employe".equalsIgnoreCase(emp.getType())) {
                totalEmployees++;
            } else if ("etudiant".equalsIgnoreCase(emp.getType())) {
                totalStudents++;
            }
        }

        Set<String> presentIds = new HashSet<>();
        SimpleDateFormat dateFormat = new SimpleDateFormat("yyyy-MM-dd", Locale.getDefault());
        String todayDate = dateFormat.format(new Date());

        List<Pointage> allPointages = databaseHelper.getAllPointages();
        if (allPointages != null) {
            for (Pointage pointage : allPointages) {
                if ("arrivee".equalsIgnoreCase(pointage.getType()) && todayDate.equals(pointage.getDate())) {
                    presentIds.add(pointage.getEmployeeId());
                }
            }
        }

        int presentEmployeesCount = 0;
        int presentStudentsCount = 0;

        for (String id : presentIds) {
            String type = employeeTypeMap.get(id);
            if ("employe".equalsIgnoreCase(type)) {
                presentEmployeesCount++;
            } else if ("etudiant".equalsIgnoreCase(type)) {
                presentStudentsCount++;
            }
        }

        float employeePresenceRate = (totalEmployees > 0) ? ((float) presentEmployeesCount / totalEmployees) * 100 : 0;
        float employeeAbsenceRate = 100 - employeePresenceRate;

        float studentPresenceRate = (totalStudents > 0) ? ((float) presentStudentsCount / totalStudents) * 100 : 0;
        float studentAbsenceRate = 100 - studentPresenceRate;

        employeePresenceRateText.setText(String.format("%.0f%%", employeePresenceRate));
        employeeAbsenceRateText.setText(String.format("%.0f%%", employeeAbsenceRate));
        studentPresenceRateText.setText(String.format("%.0f%%", studentPresenceRate));
        studentAbsenceRateText.setText(String.format("%.0f%%", studentAbsenceRate));

        int totalPresent = presentEmployeesCount + presentStudentsCount;
        int totalPopulation = totalEmployees + totalStudents;

        float globalPresenceRate = (totalPopulation > 0) ? ((float) totalPresent / totalPopulation) * 100 : 0;
        float globalAbsenceRate = 100 - globalPresenceRate;

        presenceRateText.setText(String.format("%.0f%%", globalPresenceRate));
        absenceRateText.setText(String.format("%.0f%%", globalAbsenceRate));

        List<PieEntry> entries = new ArrayList<>();
        entries.add(new PieEntry(globalPresenceRate, "Présent"));
        entries.add(new PieEntry(globalAbsenceRate, "Absent"));

        PieDataSet dataSet = new PieDataSet(entries, "");
        dataSet.setSliceSpace(3f);
        dataSet.setSelectionShift(5f);
        dataSet.setColors(new int[]{Color.GREEN, Color.RED});

        PieData data = new PieData(dataSet);
        data.setValueTextSize(15f);
        data.setValueTextColor(Color.WHITE);

        presenceChart.setData(data);
        presenceChart.invalidate();
    }

    private void loadDailyActivityData() {
        List<Pointage> allPointages = databaseHelper.getAllPointages();

        Map<String, Integer> dailyEntries = new HashMap<>();
        Map<String, Integer> dailyExits = new HashMap<>();  // ✅ Ajouter les sorties
        List<String> dates = new ArrayList<>();

        if (allPointages != null && !allPointages.isEmpty()) {
            for (Pointage pointage : allPointages) {
                String date = pointage.getDate();
                if ("arrivee".equalsIgnoreCase(pointage.getType())) {
                    dailyEntries.put(date, dailyEntries.getOrDefault(date, 0) + 1);
                } else if ("sortie".equalsIgnoreCase(pointage.getType())) {  // ✅ Comptabiliser les sorties
                    dailyExits.put(date, dailyExits.getOrDefault(date, 0) + 1);
                }
            }

            // Récupérer toutes les dates uniques
            Set<String> allDates = new HashSet<>();
            allDates.addAll(dailyEntries.keySet());
            allDates.addAll(dailyExits.keySet());
            dates.addAll(allDates);
            Collections.sort(dates);
        }

        // ✅ Créer deux courbes : entrées et sorties
        List<Entry> entryList = new ArrayList<>();
        List<Entry> exitList = new ArrayList<>();

        for (int i = 0; i < dates.size(); i++) {
            String date = dates.get(i);
            entryList.add(new Entry(i, dailyEntries.getOrDefault(date, 0)));
            exitList.add(new Entry(i, dailyExits.getOrDefault(date, 0)));
        }

        LineDataSet entryDataSet = new LineDataSet(entryList, "Entrées");
        entryDataSet.setColor(Color.GREEN);
        entryDataSet.setLineWidth(2f);
        entryDataSet.setCircleColor(Color.GREEN);

        LineDataSet exitDataSet = new LineDataSet(exitList, "Sorties");
        exitDataSet.setColor(Color.RED);
        exitDataSet.setLineWidth(2f);
        exitDataSet.setCircleColor(Color.RED);

        LineData data = new LineData(entryDataSet, exitDataSet);
        dailyActivityChart.setData(data);

        XAxis xAxis = dailyActivityChart.getXAxis();
        xAxis.setValueFormatter(new IndexAxisValueFormatter(dates));
        xAxis.setGranularity(1f);
        xAxis.setPosition(XAxis.XAxisPosition.BOTTOM);
        xAxis.setLabelRotationAngle(45);

        dailyActivityChart.invalidate();
    }
    private void loadPointageList() {
        List<Pointage> allPointages = databaseHelper.getAllPointages();
        List<MovementRecord> movementRecords = new ArrayList<>();

        if (allPointages != null && !allPointages.isEmpty()) {
            for (Pointage pointage : allPointages) {
                // ✅ Charger TOUS les pointages (entrées ET sorties)
                MovementRecord record = new MovementRecord();
                record.setEmployeeId(pointage.getEmployeeId());
                record.setTimestamp(pointage.getTimestamp());
                record.setType(pointage.getType());  // ✅ Ajouter le type (arrivee/sortie)

                Employee employee = databaseHelper.getEmployee(pointage.getEmployeeId());
                if (employee != null) {
                    record.setNom(employee.getNom());
                    record.setPrenom(employee.getPrenom());
                }

                movementRecords.add(record);
            }
        }

        // ✅ Trier par date décroissante (plus récent en premier)
        Collections.sort(movementRecords, (r1, r2) -> Long.compare(r2.getTimestamp(), r1.getTimestamp()));

        pointageAdapter = new MovementAdapter(movementRecords, this, databaseHelper);
        pointageListRecyclerView.setAdapter(pointageAdapter);
    }
    @Override
    protected void onResume() {
        super.onResume();
        loadLocalData();
    }
}