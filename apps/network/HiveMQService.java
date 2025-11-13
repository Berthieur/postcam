package com.trackingsystem.apps.network;

import android.util.Log;

import org.json.JSONObject;

import io.socket.client.IO;
import io.socket.client.Socket;
import io.socket.emitter.Emitter;

public class HiveMQService {

    private static final String TAG = "HiveMQService";
    private static final String SOCKET_URL = "https://postcam-1.onrender.com"; // 🔗 ton backend Render

    private static HiveMQService instance;
    private Socket socket;
    private OnMessageListener listener;

    private HiveMQService() {
        try {
            socket = IO.socket(SOCKET_URL);
        } catch (Exception e) {
            Log.e(TAG, "❌ Erreur création socket: " + e.getMessage());
        }
    }

    // Singleton
    public static HiveMQService getInstance() {
        if (instance == null) {
            instance = new HiveMQService();
        }
        return instance;
    }

    public void connect() {
        if (socket == null) return;

        socket.on(Socket.EVENT_CONNECT, args -> Log.d(TAG, "✅ WebSocket connecté"));
        socket.on(Socket.EVENT_DISCONNECT, args -> Log.d(TAG, "🛑 WebSocket déconnecté"));
        socket.on(Socket.EVENT_CONNECT_ERROR, args -> Log.e(TAG, "❌ Erreur WebSocket: " + args[0]));

        // Exemple : écoute d’un événement "motion"
        socket.on("motion", new Emitter.Listener() {
            @Override
            public void call(Object... args) {
                try {
                    String message = args[0].toString();
                    Log.d(TAG, "📡 Motion event reçu: " + message);

                    if (listener != null) {
                        listener.onMessage("motion", message);
                    }
                } catch (Exception e) {
                    Log.e(TAG, "❌ Erreur parsing message: " + e.getMessage());
                }
            }
        });

        socket.connect();
    }

    public void disconnect() {
        if (socket != null) {
            socket.disconnect();
            socket.off();
            Log.d(TAG, "🛑 Socket déconnecté et listeners retirés");
        }
    }

    // Envoyer une commande
    public void sendMessage(String event, JSONObject data) {
        if (socket != null && socket.connected()) {
            socket.emit(event, data);
            Log.d(TAG, "📤 Message envoyé: " + event + " -> " + data.toString());
        }
    }

    public void setOnMessageListener(OnMessageListener listener) {
        this.listener = listener;
    }

    // Interface callback
    public interface OnMessageListener {
        void onMessage(String topic, String message);
    }
}
