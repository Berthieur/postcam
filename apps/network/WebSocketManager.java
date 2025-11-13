package com.trackingsystem.apps.network;

import org.java_websocket.client.WebSocketClient;
import org.java_websocket.handshake.ServerHandshake;

import java.net.URI;

public class WebSocketManager {

    private WebSocketClient webSocketClient;
    private OnMessageListener listener;

    public interface OnMessageListener {
        void onMessage(String message);
        void onOpen();
        void onClose(int code, String reason, boolean remote);
        void onError(Exception ex);
    }

    public WebSocketManager(OnMessageListener listener) {
        this.listener = listener;
    }

    public void connect(String serverUrl) {
        URI uri = URI.create(serverUrl);

        webSocketClient = new WebSocketClient(uri) {
            @Override
            public void onOpen(ServerHandshake handshakedata) {
                if(listener != null) listener.onOpen();
            }

            @Override
            public void onMessage(String message) {
                if(listener != null) listener.onMessage(message);
            }

            @Override
            public void onClose(int code, String reason, boolean remote) {
                if(listener != null) listener.onClose(code, reason, remote);
            }

            @Override
            public void onError(Exception ex) {
                if(listener != null) listener.onError(ex);
            }
        };

        webSocketClient.connect();
    }

    public void sendMessage(String message) {
        if (webSocketClient != null && webSocketClient.isOpen()) {
            webSocketClient.send(message);
        }
    }

    public void close() {
        if (webSocketClient != null) {
            webSocketClient.close();
        }
    }
}
