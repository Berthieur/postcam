package com.trackingsystem.apps.network;

import android.util.Log;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import io.socket.client.IO;
import io.socket.client.Socket;
import io.socket.emitter.Emitter;

/**
 * Service WebSocket pour écouter les mises à jour RSSI (positions temps réel)
 */
public class WebSocketService {

    private static final String TAG = "WebSocketService";
    private Socket socket;
    private OnDataReceivedListener listener;

    /**
     * Interface callback pour renvoyer les données au TrackingActivity
     */
    public interface OnDataReceivedListener {
        void onDataReceived(JSONArray data);
    }

    /**
     * Constructeur
     * @param serverUrl ex: "https://ton-serveur-flask.koyeb.app"
     * @param listener fonction de rappel pour transmettre les données
     */
    public WebSocketService(String serverUrl, OnDataReceivedListener listener) {
        this.listener = listener;
        try {
            IO.Options opts = new IO.Options();
            opts.forceNew = true;
            opts.reconnection = true;
            opts.reconnectionAttempts = 9999;
            opts.reconnectionDelay = 2000;

            socket = IO.socket(serverUrl, opts);

            socket.on(Socket.EVENT_CONNECT, args -> {
                Log.i(TAG, "✅ Connecté au WebSocket");
                socket.emit("subscribe_rssi", "client_android");
            });

            socket.on(Socket.EVENT_DISCONNECT, args ->
                    Log.w(TAG, "❌ Déconnecté du WebSocket"));

            socket.on(Socket.EVENT_CONNECT_ERROR, args ->
                    Log.e(TAG, "⚠️ Erreur de connexion WebSocket : " + args[0]));

            // 📡 Réception des mises à jour RSSI
            socket.on("rssi_update", new Emitter.Listener() {
                @Override
                public void call(Object... args) {
                    try {
                        if (args.length > 0 && args[0] != null) {
                            Object data = args[0];
                            JSONArray arr;

                            if (data instanceof JSONArray) {
                                arr = (JSONArray) data;
                            } else if (data instanceof JSONObject) {
                                arr = new JSONArray().put((JSONObject) data);
                            } else if (data instanceof String) {
                                arr = new JSONArray((String) data);
                            } else {
                                return;
                            }

                            if (listener != null) {
                                listener.onDataReceived(arr);
                            }
                        }
                    } catch (JSONException e) {
                        Log.e(TAG, "Erreur parsing JSON RSSI: " + e.getMessage());
                    }
                }
            });

            socket.connect();

        } catch (Exception e) {
            Log.e(TAG, "Erreur initialisation WebSocket: " + e.getMessage());
        }
    }

    public void disconnect() {
        try {
            if (socket != null) {
                socket.disconnect();
                socket.close();
            }
        } catch (Exception e) {
            Log.e(TAG, "Erreur lors de la déconnexion: " + e.getMessage());
        }
    }
}
