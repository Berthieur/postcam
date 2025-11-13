package com.trackingsystem.apps.views;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.RectF;
import android.util.AttributeSet;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.view.View;

import androidx.annotation.Nullable;

import com.trackingsystem.apps.models.Employee;

import java.util.List;

public class FloorPlanView extends View {

    // --- Interface pour la gestion des clics sur le badge ---
    public interface OnBadgeClickListener {
        void onBadgeClick();
    }
    private OnBadgeClickListener badgeClickListener;

    // --- Variables de Gestion du Zoom et Panoramique ---
    private Matrix matrix = new Matrix();
    private float scaleFactor = 1.0f;
    private static final int NONE = 0;
    private static final int DRAG = 1;
    private static final int ZOOM = 2;
    private int mode = NONE;
    private float lastX, lastY; // Pour le glissement (panoramique)
    private ScaleGestureDetector scaleGestureDetector;

    // NOUVEAU: Variables pour la détection fiable du clic
    private boolean isClick = false;
    private static final float CLICK_TOLERANCE_PX = 10.0f; // Tolérance pour les micro-mouvements

    // Position et rayon du badge pour la détection de clic
    private float badgeXPixels;
    private float badgeYPixels;
    private float badgeRadius = 12;

    private Paint paintBorder;
    private Paint paintDoor;
    private Paint paintText;
    private List<Employee> employees;
    private boolean isConnected = false;

    // Constantes de dimensions du plan (6m x 5m)
    private static final float TOTAL_WIDTH_M = 6.0f;
    private static final float TOTAL_HEIGHT_M = 5.0f;
    private static final int NUM_COLS = 3;
    private static final int NUM_ROWS = 2;

    private static final float CORRIDOR_HEIGHT_M = 1.0f;
    private static final float DOOR_THICKNESS_PX = 8f;
    private static final float DOOR_WIDTH_M = 0.5f;

    private static final float BADGE_X_M = 0.4f;
    private static final float BADGE_Y_M = TOTAL_HEIGHT_M / 2f;


    public FloorPlanView(Context context) {
        super(context);
        init(context);
    }

    public FloorPlanView(Context context, @Nullable AttributeSet attrs) {
        super(context, attrs);
        init(context);
    }

    public FloorPlanView(Context context, @Nullable AttributeSet attrs, int defStyleAttr) {
        super(context, attrs, defStyleAttr);
        init(context);
    }

    private void init(Context context) {
        paintBorder = new Paint();
        paintBorder.setColor(Color.BLACK);
        paintBorder.setStyle(Paint.Style.STROKE);
        paintBorder.setStrokeWidth(4f);

        paintDoor = new Paint();
        paintDoor.setColor(Color.WHITE);
        paintDoor.setStyle(Paint.Style.FILL);

        paintText = new Paint();
        paintText.setColor(Color.BLACK);
        paintText.setTextSize(32f);
        paintText.setFakeBoldText(true);

        scaleGestureDetector = new ScaleGestureDetector(context, new ScaleListener());
    }

    // --- Méthodes pour la persistance d'état ---
    public Matrix getDrawingMatrix() {
        return new Matrix(matrix); // Retourne une copie
    }

    public float getScaleFactor() {
        return scaleFactor;
    }

    public void setDrawingMatrix(Matrix newMatrix, float newScaleFactor) {
        this.matrix.set(newMatrix);
        this.scaleFactor = newScaleFactor;
        invalidate();
    }
    // ------------------------------------------

    public void setOnBadgeClickListener(OnBadgeClickListener listener) {
        this.badgeClickListener = listener;
    }

    public void setConnectionStatus(boolean isConnected) {
        this.isConnected = isConnected;
        invalidate();
    }

    // --- Détecteur de Geste de Zoom ---
    private class ScaleListener extends ScaleGestureDetector.SimpleOnScaleGestureListener {
        @Override
        public boolean onScale(ScaleGestureDetector detector) {
            scaleFactor *= detector.getScaleFactor();
            scaleFactor = Math.max(1.0f, Math.min(scaleFactor, 5.0f)); // Limiter le zoom entre 1x et 5x
            matrix.postScale(detector.getScaleFactor(), detector.getScaleFactor(),
                    detector.getFocusX(), detector.getFocusY());
            invalidate();
            return true;
        }
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);

        // Appliquer la matrice de transformation (zoom/panoramique)
        canvas.save();
        canvas.concat(matrix);

        int width = getWidth();
        int height = getHeight();

        // Calcul de l'échelle initiale (Pixels par Mètre)
        float scaleX = width / TOTAL_WIDTH_M;
        float scaleY = height / TOTAL_HEIGHT_M;

        // Dimensions
        float colWidthM = TOTAL_WIDTH_M / NUM_COLS;
        float rowHeightM = TOTAL_HEIGHT_M / NUM_ROWS;

        // Coordonnées clés en pixels (basées sur l'échelle initiale)
        float doorLengthPixelsX = DOOR_WIDTH_M * scaleX;
        float doorLengthPixelsY = DOOR_WIDTH_M * scaleY;
        float centerLineY = rowHeightM * scaleY;
        float corridorHeightPixels = CORRIDOR_HEIGHT_M * scaleY;

        // Coordonnées du Couloir (centré sur 2.5m)
        float corridorYStart = centerLineY - corridorHeightPixels / 2f;
        float corridorYEnd = centerLineY + corridorHeightPixels / 2f;

        // --- Murs intérieurs et bordure ---
        Paint paintGrid = new Paint(paintBorder);
        paintGrid.setStrokeWidth(4f / scaleFactor);

        // Dessin des murs, portes et bordures (code omis pour la concision, mais reste identique à la version précédente)

        // --- Murs Horizontaux du Couloir (Portes intérieures) ---
        for (int i = 0; i < NUM_COLS; i++) {
            float startColX = i * colWidthM * scaleX;
            float endColX = (i + 1) * colWidthM * scaleX;
            float doorStartRefX = (startColX + endColX) / 2.0f - (doorLengthPixelsX / 2.0f);
            float doorEndRefX = doorStartRefX + doorLengthPixelsX;

            // Mur du haut
            canvas.drawLine(startColX, corridorYStart, doorStartRefX, corridorYStart, paintGrid);
            canvas.drawLine(doorEndRefX, corridorYStart, endColX, corridorYStart, paintGrid);
            RectF doorRectTopInner = new RectF(doorStartRefX, corridorYStart - DOOR_THICKNESS_PX, doorEndRefX, corridorYStart);
            canvas.drawRect(doorRectTopInner, paintDoor);

            // Mur du bas
            canvas.drawLine(startColX, corridorYEnd, doorStartRefX, corridorYEnd, paintGrid);
            canvas.drawLine(doorEndRefX, corridorYEnd, endColX, corridorYEnd, paintGrid);
            RectF doorRectBottomInner = new RectF(doorStartRefX, corridorYEnd, doorEndRefX, corridorYEnd + DOOR_THICKNESS_PX);
            canvas.drawRect(doorRectBottomInner, paintDoor);
        }

        // --- Murs Verticaux ---
        for (int i = 1; i < NUM_COLS; i++) {
            float x = i * colWidthM * scaleX;
            canvas.drawLine(x, 0, x, corridorYStart, paintGrid);
            canvas.drawLine(x, corridorYEnd, x, height, paintGrid);
        }


        // --- Portes sur le mur vertical Gauche (Portes extérieures) ---
        float roomHeightPixels = (height - corridorHeightPixels) / 2f;
        float doorMarginTop = (roomHeightPixels - doorLengthPixelsY) / 2;
        float doorTopY1 = doorMarginTop;
        float doorTopY2 = corridorYStart - doorMarginTop;
        canvas.drawLine(0, 0, 0, doorTopY1, paintBorder);
        canvas.drawLine(0, doorTopY2, 0, corridorYStart, paintBorder);
        RectF doorRectTop = new RectF(0, doorTopY1, DOOR_THICKNESS_PX, doorTopY2);
        canvas.drawRect(doorRectTop, paintDoor);
        float doorBottomY1 = corridorYEnd + doorMarginTop;
        float doorBottomY2 = height - doorMarginTop;
        canvas.drawLine(0, corridorYEnd, 0, doorBottomY1, paintBorder);
        canvas.drawLine(0, doorBottomY2, 0, height, paintBorder);
        RectF doorRectBottom = new RectF(0, doorBottomY1, DOOR_THICKNESS_PX, doorBottomY2);
        canvas.drawRect(doorRectBottom, paintDoor);


        // --- Bordure Extérieure Finale ---
        canvas.drawRect(0, 0, width, height, paintGrid);


        // --- Équipements : ESP32 (Bleu) ---
        Paint paintESP = new Paint();
        paintESP.setColor(Color.BLUE);
        paintESP.setStyle(Paint.Style.FILL);
        float espRadius = 15 / scaleFactor;
        float espX = 0.2f;
        float espY = 0.2f;
        paintText.setTextSize(32f / scaleFactor);


        // --- Badge (Couleur dynamique VERT ou ROUGE) ---
        badgeXPixels = BADGE_X_M * scaleX;
        badgeYPixels = BADGE_Y_M * scaleY;

        Paint paintBadge = new Paint();
        paintBadge.setColor(isConnected ? Color.GREEN : Color.RED);
        paintBadge.setStyle(Paint.Style.FILL);
        badgeRadius = 12 / scaleFactor;

        canvas.drawCircle(badgeXPixels, badgeYPixels, badgeRadius, paintBadge);
        canvas.drawText("badge", (badgeXPixels + 15 / scaleFactor), (badgeYPixels), paintText);


        if (employees != null) {
            android.util.Log.d("FloorPlanView", "Nombre d'employés à dessiner : " + employees.size());

            Paint paintEmployee = new Paint();
            paintEmployee.setColor(Color.GREEN);
            paintEmployee.setStyle(Paint.Style.FILL);
            Paint paintName = new Paint();
            paintName.setColor(Color.BLACK);
            paintName.setTextSize(28f / scaleFactor);

            for (Employee emp : employees) {
                Float x = emp.getLastPositionX();
                Float y = emp.getLastPositionY();

                android.util.Log.d("FloorPlanView", "Employé: " + emp.getPrenom() +
                        " | Position: x=" + x + ", y=" + y);

                if (x != null && y != null) {
                    float px = x * scaleX;
                    float py = y * scaleY;

                    android.util.Log.d("FloorPlanView", "  -> Dessin à pixels: px=" + px + ", py=" + py);

                    canvas.drawCircle(px, py, 20 / scaleFactor, paintEmployee);
                    canvas.drawText(emp.getPrenom(), px + 25 / scaleFactor, py + 5 / scaleFactor, paintName);
                } else {
                    android.util.Log.w("FloorPlanView", "  -> Position NULL, employé non affiché");
                }
            }
        } else {
            android.util.Log.w("FloorPlanView", "Liste d'employés NULL");
        }

        canvas.restore(); }
    @Override
    public boolean onTouchEvent(MotionEvent event) {
        // 1. Gérer le zoom en premier
        scaleGestureDetector.onTouchEvent(event);

        // Obtenir la matrice pour le calcul du clic/panoramique
        float[] values = new float[9];
        matrix.getValues(values);
        float currentScale = values[Matrix.MSCALE_X];

        // Coordonnées touchées transformées (pour le clic et le calcul de distance)
        float touchX = (event.getX() - values[Matrix.MTRANS_X]) / currentScale;
        float touchY = (event.getY() - values[Matrix.MTRANS_Y]) / currentScale;

        switch (event.getAction() & MotionEvent.ACTION_MASK) {
            case MotionEvent.ACTION_DOWN:
                // Enregistre les coordonnées de départ
                lastX = event.getX();
                lastY = event.getY();
                mode = DRAG;
                isClick = true; // On assume que c'est un clic au début
                break;

            case MotionEvent.ACTION_POINTER_DOWN:
                // Deuxième doigt -> passe au mode ZOOM
                mode = ZOOM;
                isClick = false; // Ce n'est plus un clic simple
                break;

            case MotionEvent.ACTION_MOVE:
                // Calculer la distance de déplacement pour annuler le clic
                float deltaX = event.getX() - lastX;
                float deltaY = event.getY() - lastY;

                if (Math.abs(deltaX) > CLICK_TOLERANCE_PX || Math.abs(deltaY) > CLICK_TOLERANCE_PX) {
                    isClick = false; // Mouvement excessif, ce n'est pas un clic
                }

                if (mode == DRAG) {
                    // Gestion du Panoramique
                    matrix.postTranslate(deltaX, deltaY);
                    lastX = event.getX();
                    lastY = event.getY();
                    invalidate();
                }
                break;

            case MotionEvent.ACTION_UP:
                if (isClick && mode == DRAG) {
                    // Si c'était un clic simple (peu ou pas de mouvement)

                    float dx = touchX - badgeXPixels;
                    float dy = touchY - badgeYPixels;
                    double distance = Math.sqrt(dx * dx + dy * dy);

                    // Détection de la zone du badge (rayon * 2 pour faciliter le clic)
                    if (distance < (12 * 2) && badgeClickListener != null) {
                        badgeClickListener.onBadgeClick();
                        return true; // Événement consommé (le clic a fonctionné)
                    }
                }
                mode = NONE;
                isClick = false;
                break;

            case MotionEvent.ACTION_POINTER_UP:
                mode = NONE;
                isClick = false;
                break;
        }

        return true;
    }

    public void updateEmployeePositions(List<Employee> employees) {
        this.employees = employees;
        invalidate();
    }
    public void updateSingleEmployeePosition(String employeeId, float x, float y, int rssi) {
        if (employees == null) return;

        boolean updated = false;
        for (Employee emp : employees) {
            if (emp.getId().equals(employeeId)) {
                emp.setLastPositionX(x);
                emp.setLastPositionY(y);
                emp.setLastRssi(rssi); // tu peux ajouter ce champ dans Employee
                updated = true;
                break;
            }
        }

        // Si l’employé n’existait pas dans la liste, on peut l’ajouter
        if (!updated) {
            Employee newEmp = new Employee();
            newEmp.setId(employeeId);
            newEmp.setLastPositionX(x);
            newEmp.setLastPositionY(y);
            newEmp.setLastRssi(rssi);
            employees.add(newEmp);
        }

        // Redessiner le plan
        postInvalidate();
    }
}