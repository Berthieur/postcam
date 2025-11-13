package com.trackingsystem.apps;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import androidx.core.app.NotificationCompat;

public class ChatKeepAliveService extends Service {

    private static final String CHANNEL_ID = "chat_ia";
    private static final int NOTIF_ID = 999;

    @Override
    public IBinder onBind(Intent intent) { return null; }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        createChannel();
        Notification n = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("IA Active")
                .setContentText("En attente de votre voix...")
                .setSmallIcon(android.R.drawable.ic_dialog_info)  // ICÔNE SYSTÈME
                .setPriority(NotificationCompat.PRIORITY_MIN)
                .build();
        startForeground(NOTIF_ID, n);
        return START_STICKY;
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel c = new NotificationChannel(CHANNEL_ID, "IA", NotificationManager.IMPORTANCE_MIN);
            getSystemService(NotificationManager.class).createNotificationChannel(c);
        }
    }
}