package com.trackingsystem.apps.models;

public class ESP32Status {
    private boolean routerConnected;
    private boolean badgeConnected;
    private String routerIP;
    private int connectedBadges;
    private long lastUpdate;
    
    public ESP32Status() {}
    
    // Getters
    public boolean isRouterConnected() { return routerConnected; }
    public boolean isBadgeConnected() { return badgeConnected; }
    public String getRouterIP() { return routerIP; }
    public int getConnectedBadges() { return connectedBadges; }
    public long getLastUpdate() { return lastUpdate; }
    
    // Setters
    public void setRouterConnected(boolean routerConnected) { this.routerConnected = routerConnected; }
    public void setBadgeConnected(boolean badgeConnected) { this.badgeConnected = badgeConnected; }
    public void setRouterIP(String routerIP) { this.routerIP = routerIP; }
    public void setConnectedBadges(int connectedBadges) { this.connectedBadges = connectedBadges; }
    public void setLastUpdate(long lastUpdate) { this.lastUpdate = lastUpdate; }
}