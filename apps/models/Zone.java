package com.trackingsystem.apps.models;

import android.graphics.RectF;

public class Zone {
    private String name;
    private RectF bounds;
    private ZoneType type;
    private int color;
    
    public enum ZoneType {
        SAFE, WARNING, FORBIDDEN
    }
    
    public Zone(String name, RectF bounds, ZoneType type, int color) {
        this.name = name;
        this.bounds = bounds;
        this.type = type;
        this.color = color;
    }
    
    public boolean contains(float x, float y) {
        return bounds.contains(x, y);
    }
    
    // Getters
    public String getName() { return name; }
    public RectF getBounds() { return bounds; }
    public ZoneType getType() { return type; }
    public int getColor() { return color; }
    
    // Setters
    public void setName(String name) { this.name = name; }
    public void setBounds(RectF bounds) { this.bounds = bounds; }
    public void setType(ZoneType type) { this.type = type; }
    public void setColor(int color) { this.color = color; }
}