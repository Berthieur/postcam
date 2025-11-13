package com.trackingsystem.apps;

import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.speech.RecognizerIntent;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.util.Log;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.WindowCompat;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.textfield.TextInputEditText;
import com.google.ai.client.generativeai.GenerativeModel;
import com.google.ai.client.generativeai.java.GenerativeModelFutures;
import com.google.ai.client.generativeai.type.Content;
import com.google.ai.client.generativeai.type.GenerateContentResponse;
import com.google.common.util.concurrent.FutureCallback;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;

import com.trackingsystem.apps.adapters.MessageAdapter;
import com.trackingsystem.apps.database.DatabaseHelper;
import com.trackingsystem.apps.models.Employee;
import com.trackingsystem.apps.models.Message;
import com.trackingsystem.apps.models.Pointage;
import com.trackingsystem.apps.models.SalaryRecord;

import java.text.DecimalFormat;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class IAChatActivity extends AppCompatActivity implements TextToSpeech.OnInitListener {

    private static final String TAG = "IAChatActivity";
    private RecyclerView chatRecyclerView;
    private MessageAdapter messageAdapter;
    private TextInputEditText messageEditText;
    private MaterialButton sendButton;
    private MaterialButton voiceButton;

    private List<Message> messageList = new ArrayList<>();
    private DatabaseHelper databaseHelper;
    private GenerativeModelFutures generativeModel;
    private ExecutorService executorService = Executors.newSingleThreadExecutor();

    // TTS
    private TextToSpeech textToSpeech;
    private boolean ttsReady = false;

    // Clé API Gemini
    private static final String API_KEY = "AIzaSyCeP-TrUOH91Yb-VWDKqLHPc9jTaYcJLpU";

    // Launcher reconnaissance vocale
    private final ActivityResultLauncher<Intent> voiceRecognitionLauncher =
            registerForActivityResult(new ActivityResultContracts.StartActivityForResult(), result -> {
                if (result.getResultCode() == RESULT_OK && result.getData() != null) {
                    ArrayList<String> matches = result.getData().getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
                    if (matches != null && !matches.isEmpty()) {
                        String voiceInput = matches.get(0);
                        messageEditText.setText(voiceInput);
                        sendMessage(voiceInput);
                    }
                }
            });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        supportRequestWindowFeature(WindowCompat.FEATURE_ACTION_BAR_OVERLAY);
        if (getSupportActionBar() != null) {
            getSupportActionBar().hide();
        }

        // Permission micro
        if (checkSelfPermission(android.Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{android.Manifest.permission.RECORD_AUDIO}, 1);
        }

        setContentView(R.layout.activity_ia_chat);

        initViews();
        setupRecyclerView();
        setupListeners();
        setupGenerativeModel();
        initTTS();

        databaseHelper = new DatabaseHelper(this);

        // Message de bienvenue
        addMessage(new Message(
                "Bonjour ! Je suis votre assistant IA. Je peux répondre à vos questions sur l'entreprise (employés, salaires, pointages) ET à toutes vos questions générales. Comment puis-je vous aider ?",
                Message.SENDER_AI
        ));

        // TEST VOCAL AUTOMATIQUE (3 sec après lancement)
        new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(() -> {
            if (ttsReady) {
                speakOut("Test vocal. L'assistant est prêt et parle à voix haute.");
            } else {
                Toast.makeText(this, "TTS non prêt. Vérifiez la voix française.", Toast.LENGTH_LONG).show();
            }
        }, 3000);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == 1) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                Toast.makeText(this, "Microphone autorisé", Toast.LENGTH_SHORT).show();
            } else {
                Toast.makeText(this, "Permission du micro refusée", Toast.LENGTH_LONG).show();
            }
        }
    }

    private void initViews() {
        chatRecyclerView = findViewById(R.id.chatRecyclerView);
        messageEditText = findViewById(R.id.messageEditText);
        sendButton = findViewById(R.id.sendButton);
        voiceButton = findViewById(R.id.voiceButton);
    }

    private void setupRecyclerView() {
        messageAdapter = new MessageAdapter(messageList);
        chatRecyclerView.setLayoutManager(new LinearLayoutManager(this));
        chatRecyclerView.setAdapter(messageAdapter);
    }

    private void setupListeners() {
        sendButton.setOnClickListener(v -> {
            String messageText = Objects.requireNonNull(messageEditText.getText()).toString().trim();
            if (!messageText.isEmpty()) {
                sendMessage(messageText);
                messageEditText.setText("");
            }
        });

        voiceButton.setOnClickListener(v -> startVoiceRecognition());
    }

    private void setupGenerativeModel() {
        Log.d(TAG, "Initialisation Gemini AI...");

        if (API_KEY == null || API_KEY.isEmpty() || API_KEY.equals("VOTRE_CLE_API_ICI")) {
            Log.e(TAG, "CLÉ API MANQUANTE !");
            generativeModel = null;
            Toast.makeText(this, "Configurez votre clé API Gemini dans le code", Toast.LENGTH_LONG).show();
            return;
        }

        try {
            GenerativeModel baseModel = new GenerativeModel("gemini-pro", API_KEY);
            generativeModel = GenerativeModelFutures.from(baseModel);
            Log.d(TAG, "Gemini AI initialisé avec succès");
            Toast.makeText(this, "IA Gemini activée", Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Log.e(TAG, "Erreur initialisation Gemini", e);
            generativeModel = null;
            Toast.makeText(this, "Erreur initialisation IA : " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    // === INITIALISATION TTS (CORRIGÉE) ===
    private void initTTS() {
        textToSpeech = new TextToSpeech(this, status -> {
            if (status == TextToSpeech.SUCCESS) {
                int result = textToSpeech.setLanguage(Locale.FRENCH);
                if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                    Log.e(TAG, "Langue française non supportée pour TTS");
                    Toast.makeText(this, "Voix française non disponible. Installez Google TTS.", Toast.LENGTH_LONG).show();
                    ttsReady = false;
                } else {
                    ttsReady = true;
                    Log.d(TAG, "TTS PRÊT ET ACTIVÉ");

                    textToSpeech.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                        @Override
                        public void onStart(String utteranceId) {
                            Log.d(TAG, "TTS commencé : " + utteranceId);
                        }

                        @Override
                        public void onDone(String utteranceId) {
                            Log.d(TAG, "TTS terminé : " + utteranceId);
                            runOnUiThread(() -> ttsReady = true);
                        }

                        @Override
                        public void onError(String utteranceId) {
                            Log.e(TAG, "Erreur TTS : " + utteranceId);
                            runOnUiThread(() -> ttsReady = true);
                        }
                    });
                }
            } else {
                Log.e(TAG, "Échec initialisation TTS");
                ttsReady = false;
            }
        });
    }

    @Override
    public void onInit(int status) {
        // Géré dans initTTS()
    }

    // === RECONNAISSANCE VOCALE ===
    private void startVoiceRecognition() {
        if (checkSelfPermission(android.Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            Toast.makeText(this, "Permission micro refusée", Toast.LENGTH_SHORT).show();
            return;
        }

        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault());
        intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "Parlez maintenant...");

        try {
            voiceRecognitionLauncher.launch(intent);
            Toast.makeText(this, "Parlez maintenant...", Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Log.e(TAG, "Erreur lancement reconnaissance vocale", e);
            Toast.makeText(this, "Reconnaissance vocale non disponible", Toast.LENGTH_LONG).show();
        }
    }

    private void sendMessage(String messageText) {
        addMessage(new Message(messageText, Message.SENDER_USER));

        executorService.execute(() -> {
            try {
                String dbResponse = getDatabaseResponse(messageText);
                if (dbResponse != null) {
                    runOnUiThread(() -> addMessage(new Message(dbResponse, Message.SENDER_AI)));
                } else {
                    if (generativeModel != null) {
                        getAIResponse(messageText);
                    } else {
                        runOnUiThread(() -> addMessage(new Message(
                                "IA non disponible (clé API manquante). Tapez 'aide' pour voir les commandes.",
                                Message.SENDER_AI
                        )));
                    }
                }
            } catch (Exception e) {
                Log.e(TAG, "Erreur traitement message", e);
                runOnUiThread(() -> addMessage(new Message(
                        "Erreur : " + e.getMessage(),
                        Message.SENDER_AI
                )));
            }
        });
    }

    private void addMessage(Message message) {
        messageList.add(message);
        messageAdapter.notifyItemInserted(messageList.size() - 1);
        chatRecyclerView.scrollToPosition(messageList.size() - 1);

        // LIRE TOUTES LES RÉPONSES IA À VOIX HAUTE
        if (message.getSender() == Message.SENDER_AI && ttsReady) {
            String cleanText = message.getText()
                    .replace("\n", ". ")
                    .replace("\r", "")
                    .replace("*", "")
                    .replace("#", "")
                    .replace("€", "euros")
                    .replace("  ", " ")
                    .replace("..", ".")
                    .replace(" .", ".")
                    .trim();

            if (cleanText.length() > 3900) {
                cleanText = cleanText.substring(0, 3900) + ".";
            }

            String finalCleanText = cleanText;
            new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(() -> {
                speakOut(finalCleanText);
            }, 200);
        }
    }

    // === SYNTHÈSE VOCALE FIABLE (QUEUE_FLUSH + utteranceId) ===
    private void speakOut(String text) {
        if (textToSpeech == null || !ttsReady || text.isEmpty()) {
            Log.w(TAG, "TTS non prêt ou texte vide");
            return;
        }

        HashMap<String, String> params = new HashMap<>();
        params.put(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID, "ia_response");

        int result = textToSpeech.speak(text, TextToSpeech.QUEUE_FLUSH, params);
        if (result == TextToSpeech.ERROR) {
            Log.e(TAG, "Erreur speak() TTS");
        } else {
            Log.d(TAG, "TTS parle : " + text.substring(0, Math.min(50, text.length())) + "...");
        }
    }

    // === MÉTHODES BASE DE DONNÉES (inchangées) ===
    private String getDatabaseResponse(String query) {
        String q = query.toLowerCase().trim();

        if ((q.contains("qui") || q.contains("quel")) && q.contains("premier") && q.contains("arriv")) {
            return getFirstArrival();
        }
        if ((q.contains("qui") || q.contains("quel")) && q.contains("dernier") && (q.contains("parti") || q.contains("sorti"))) {
            return getLastDeparture();
        }
        if (q.contains("pointage") && q.contains("aujourd'hui")) {
            return getTodayPointages();
        }
        if ((q.contains("combien") || q.contains("nombre")) && (q.contains("employ") || q.contains("personnel"))) {
            return getEmployeeCount();
        }
        if ((q.contains("combien") || q.contains("nombre")) && q.contains("étudiant")) {
            return getStudentCount();
        }
        if ((q.contains("liste") || q.contains("qui sont")) && q.contains("employ")) {
            return getEmployeeList();
        }
        if ((q.contains("liste") || q.contains("qui sont")) && q.contains("étudiant")) {
            return getStudentList();
        }
        if (q.contains("liste") && (q.contains("tout") || q.contains("tous") || q.contains("complet"))) {
            return getAllPersonnelList();
        }
        if ((q.contains("qui est") || q.contains("info") || q.contains("rôle") || q.contains("profession"))
                && !q.contains("premier") && !q.contains("dernier")) {
            String result = searchEmployee(query);
            if (!result.contains("Aucun")) return result;
        }
        if (q.contains("statistique") || q.contains("stat") || q.contains("financ") || q.contains("bénéfice")) {
            return getFinancialStats();
        }
        if (q.contains("salaire") && (q.contains("total") || q.contains("somme"))) {
            return getTotalSalaries();
        }
        if (q.contains("écolage") && (q.contains("total") || q.contains("somme"))) {
            return getTotalEcolage();
        }
        if (q.contains("salaire") && !q.contains("total") && !q.contains("stat")) {
            return getSalaryDetails(query);
        }
        if (q.contains("aide") || q.contains("help") || q.equals("?")) {
            return getHelpMessage();
        }
        return null;
    }

    private String getFirstArrival() {
        Pointage first = databaseHelper.getFirstEmployeeArrivalToday();
        if (first != null) {
            return String.format("Le premier arrivé aujourd'hui est %s à %s.",
                    first.getEmployeeName(),
                    new SimpleDateFormat("HH:mm", Locale.getDefault()).format(new Date(first.getTimestamp())));
        }
        return "Aucun pointage d'arrivée aujourd'hui.";
    }

    private String getLastDeparture() {
        Pointage last = databaseHelper.getLastEmployeeDepartureToday();
        if (last != null) {
            return String.format("Le dernier parti aujourd'hui est %s à %s.",
                    last.getEmployeeName(),
                    new SimpleDateFormat("HH:mm", Locale.getDefault()).format(new Date(last.getTimestamp())));
        }
        return "Aucun pointage de départ aujourd'hui.";
    }

    private String getTodayPointages() {
        List<Pointage> all = databaseHelper.getAllPointages();
        String today = new SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(new Date());
        int count = 0;
        for (Pointage p : all) {
            if (p.getDate().equals(today)) count++;
        }
        return String.format("Il y a %d pointages enregistrés aujourd'hui.", count);
    }

    private String getEmployeeCount() {
        int count = 0;
        for (Employee e : databaseHelper.getAllEmployees()) {
            if ("employe".equalsIgnoreCase(e.getType())) count++;
        }
        return String.format("Il y a actuellement %d employés dans l'entreprise.", count);
    }

    private String getStudentCount() {
        int count = 0;
        for (Employee e : databaseHelper.getAllEmployees()) {
            if ("etudiant".equalsIgnoreCase(e.getType())) count++;
        }
        return String.format("Il y a actuellement %d étudiants inscrits.", count);
    }

    private String getEmployeeList() {
        StringBuilder sb = new StringBuilder("Liste des employés :\n\n");
        int count = 0;
        for (Employee e : databaseHelper.getAllEmployees()) {
            if ("employe".equalsIgnoreCase(e.getType())) {
                count++;
                sb.append(String.format("%d. %s %s", count, e.getNom(), e.getPrenom()));
                if (e.getProfession() != null) sb.append(" - ").append(e.getProfession());
                if (e.getTauxHoraire() != null) sb.append(String.format(" (%.2f€/h)", e.getTauxHoraire()));
                sb.append("\n");
            }
        }
        return count == 0 ? "Aucun employé enregistré." : sb.toString();
    }

    private String getStudentList() {
        StringBuilder sb = new StringBuilder("Liste des étudiants :\n\n");
        int count = 0;
        for (Employee e : databaseHelper.getAllEmployees()) {
            if ("etudiant".equalsIgnoreCase(e.getType())) {
                count++;
                sb.append(String.format("%d. %s %s", count, e.getNom(), e.getPrenom()));
                if (e.getFraisEcolage() != null) sb.append(String.format(" (%.2f€)", e.getFraisEcolage()));
                sb.append("\n");
            }
        }
        return count == 0 ? "Aucun étudiant enregistré." : sb.toString();
    }

    private String getAllPersonnelList() {
        StringBuilder sb = new StringBuilder("Liste complète du personnel :\n\n=== EMPLOYÉS ===\n");
        int empCount = 0, studCount = 0;

        for (Employee e : databaseHelper.getAllEmployees()) {
            if ("employe".equalsIgnoreCase(e.getType())) {
                empCount++;
                sb.append(String.format("• %s %s", e.getNom(), e.getPrenom()));
                if (e.getProfession() != null) sb.append(" - ").append(e.getProfession());
                sb.append("\n");
            }
        }

        sb.append("\n=== ÉTUDIANTS ===\n");
        for (Employee e : databaseHelper.getAllEmployees()) {
            if ("etudiant".equalsIgnoreCase(e.getType())) {
                studCount++;
                sb.append(String.format("• %s %s\n", e.getNom(), e.getPrenom()));
            }
        }

        sb.append(String.format("\nTotal : %d employés, %d étudiants", empCount, studCount));
        return sb.toString();
    }

    private String searchEmployee(String query) {
        String q = query.toLowerCase();
        for (Employee e : databaseHelper.getAllEmployees()) {
            String fullName = (e.getNom() + " " + e.getPrenom()).toLowerCase();
            if (q.contains(e.getNom().toLowerCase()) || q.contains(e.getPrenom().toLowerCase()) || q.contains(fullName)) {
                StringBuilder info = new StringBuilder();
                info.append(String.format("Informations sur %s %s :\n\n", e.getNom(), e.getPrenom()));
                info.append("Type : ").append("employe".equalsIgnoreCase(e.getType()) ? "Employé" : "Étudiant").append("\n");
                if (e.getProfession() != null) info.append("Profession : ").append(e.getProfession()).append("\n");
                if (e.getTauxHoraire() != null) info.append(String.format("Taux horaire : %.2f€/h\n", e.getTauxHoraire()));
                if (e.getFraisEcolage() != null) info.append(String.format("Frais d'écolage : %.2f€\n", e.getFraisEcolage()));
                if (e.getEmail() != null) info.append("Email : ").append(e.getEmail()).append("\n");
                if (e.getTelephone() != null) info.append("Téléphone : ").append(e.getTelephone()).append("\n");
                return info.toString();
            }
        }
        return "Aucun employé trouvé avec ce nom.";
    }

    private String getFinancialStats() {
        double incoming = 0, outgoing = 0;
        int salCount = 0, ecolCount = 0;

        for (SalaryRecord r : databaseHelper.getAllSalaryRecords()) {
            if ("salaire".equalsIgnoreCase(r.getType())) {
                outgoing += r.getAmount();
                salCount++;
            } else if ("ecolage".equalsIgnoreCase(r.getType())) {
                incoming += r.getAmount();
                ecolCount++;
            }
        }

        DecimalFormat df = new DecimalFormat("#,##0.00");
        return String.format(
                "=== STATISTIQUES FINANCIÈRES ===\n\n" +
                        "Argent entrant (écolage) : %s€ (%d paiements)\n" +
                        "Argent sortant (salaires) : %s€ (%d paiements)\n" +
                        "Bénéfice net : %s€",
                df.format(incoming), ecolCount,
                df.format(outgoing), salCount,
                df.format(incoming - outgoing)
        );
    }

    private String getTotalSalaries() {
        double total = 0;
        int count = 0;
        for (SalaryRecord r : databaseHelper.getAllSalaryRecords()) {
            if ("salaire".equalsIgnoreCase(r.getType())) {
                total += r.getAmount();
                count++;
            }
        }
        return String.format("Total des salaires versés : %s€ (%d paiements)",
                new DecimalFormat("#,##0.00").format(total), count);
    }

    private String getTotalEcolage() {
        double total = 0;
        int count = 0;
        for (SalaryRecord r : databaseHelper.getAllSalaryRecords()) {
            if ("ecolage".equalsIgnoreCase(r.getType())) {
                total += r.getAmount();
                count++;
            }
        }
        return String.format("Total des frais d'écolage perçus : %s€ (%d paiements)",
                new DecimalFormat("#,##0.00").format(total), count);
    }

    private String getSalaryDetails(String query) {
        String q = query.toLowerCase();
        for (SalaryRecord r : databaseHelper.getAllSalaryRecords()) {
            if (q.contains(r.getEmployeeName().toLowerCase())) {
                return String.format(
                        "Dernier paiement pour %s :\n" +
                                "Montant : %s€\n" +
                                "Type : %s\n" +
                                "Période : %s",
                        r.getEmployeeName(),
                        new DecimalFormat("#,##0.00").format(r.getAmount()),
                        r.getType(),
                        r.getPeriod() != null ? r.getPeriod() : "N/A"
                );
            }
        }
        return getTotalSalaries();
    }

    private String getHelpMessage() {
        return "Je peux répondre à TOUTES vos questions !\n\n" +
                "QUESTIONS SUR L'ENTREPRISE :\n" +
                "• Employés, étudiants, salaires\n" +
                "• Pointages et statistiques\n" +
                "• Informations financières\n\n" +
                "QUESTIONS GÉNÉRALES :\n" +
                "• Culture, histoire, science\n" +
                "• Actualités, conseils\n" +
                "• Programmation, maths\n" +
                "• Et bien plus encore !\n\n" +
                "Posez votre question naturellement.";
    }

    private void getAIResponse(String query) {
        if (generativeModel == null) {
            runOnUiThread(() -> addMessage(new Message(
                    "L'IA n'est pas disponible. Vérifiez votre clé API.",
                    Message.SENDER_AI
            )));
            return;
        }

        Content content = new Content.Builder().addText(query).build();
        ListenableFuture<GenerateContentResponse> response = generativeModel.generateContent(content);

        Futures.addCallback(response, new FutureCallback<GenerateContentResponse>() {
            @Override
            public void onSuccess(GenerateContentResponse result) {
                String text = result.getText();
                if (text != null && !text.isEmpty()) {
                    runOnUiThread(() -> addMessage(new Message(text, Message.SENDER_AI)));
                } else {
                    runOnUiThread(() -> addMessage(new Message(
                            "Désolé, je n'ai pas compris.",
                            Message.SENDER_AI
                    )));
                }
            }

            @Override
            public void onFailure(Throwable t) {
                String errorMsg;
                if (t.getMessage() != null) {
                    String msg = t.getMessage().toLowerCase();
                    if (msg.contains("api key") || msg.contains("unauthorized")) {
                        errorMsg = "Clé API invalide. Vérifiez votre clé Gemini.";
                    } else if (msg.contains("quota")) {
                        errorMsg = "Quota API dépassé.";
                    } else if (msg.contains("network")) {
                        errorMsg = "Pas de connexion internet.";
                    } else {
                        errorMsg = "Erreur IA";
                    }
                } else {
                    errorMsg = "Erreur IA";
                }
                runOnUiThread(() -> addMessage(new Message(errorMsg, Message.SENDER_AI)));
            }
        }, executorService);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (textToSpeech != null) {
            textToSpeech.stop();
            textToSpeech.shutdown();
        }
        executorService.shutdown();
    }
}