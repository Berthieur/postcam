package com.trackingsystem.apps.adapters;

import android.content.Context;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.trackingsystem.apps.R;
import com.trackingsystem.apps.database.DatabaseHelper;
import com.trackingsystem.apps.models.Employee;
import com.trackingsystem.apps.models.MovementRecord;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;

public class MovementAdapter extends RecyclerView.Adapter<MovementAdapter.MovementViewHolder> {

    private List<MovementRecord> movements;
    private SimpleDateFormat dateTimeFormat;
    private Context context;
    // Déclarer databaseHelper mais ne pas l'utiliser directement ici car les données
    // sont déjà intégrées dans MovementRecord.
    private DatabaseHelper databaseHelper;

    public MovementAdapter(List<MovementRecord> movements, Context context, DatabaseHelper databaseHelper) {
        this.movements = movements;
        this.context = context;
        this.databaseHelper = databaseHelper;
        // Format pour la date et l'heure (ex: 2025-08-13 17:30)
        this.dateTimeFormat = new SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault());
    }

    @NonNull
    @Override
    public MovementViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_movement, parent, false);
        return new MovementViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull MovementViewHolder holder, int position) {
        MovementRecord movement = movements.get(position);

        // Liaison des données du modèle MovementRecord aux vues
        holder.movementEmployeeName.setText(String.format("%s %s", movement.getNom(), movement.getPrenom()));
        holder.movementEmployeeId.setText(String.format("ID: %s", movement.getEmployeeId()));
        holder.movementType.setText(movement.getType());
        holder.movementDateTime.setText(dateTimeFormat.format(new Date(movement.getTimestamp())));

        // Mettre à jour la couleur d'arrière-plan du TextView en fonction du type de mouvement
        if ("arrivee".equalsIgnoreCase(movement.getType())) {
            holder.movementType.setBackgroundResource(R.drawable.rounded_background_green);
        } else if ("sortie".equalsIgnoreCase(movement.getType())) {
            holder.movementType.setBackgroundResource(R.drawable.rounded_background_red);
        }

        // Il n'y a plus de champ pour la zone ou la durée dans le nouveau layout XML.
        // Les lignes suivantes sont donc commentées ou supprimées.
        // holder.movementZone.setText(movement.getZoneName());
        // holder.movementDuration.setText(...);
    }

    @Override
    public int getItemCount() {
        return movements.size();
    }

    public void updateMovements(List<MovementRecord> newMovements) {
        this.movements = newMovements;
        notifyDataSetChanged();
    }

    static class MovementViewHolder extends RecyclerView.ViewHolder {
        TextView movementEmployeeName;
        TextView movementEmployeeId;
        TextView movementType;
        TextView movementDateTime;
        // Les vues pour la zone et la durée ont été supprimées du layout
        // TextView movementZone;
        // TextView movementDuration;

        public MovementViewHolder(@NonNull View itemView) {
            super(itemView);
            movementEmployeeName = itemView.findViewById(R.id.movementEmployeeName);
            movementEmployeeId = itemView.findViewById(R.id.movementEmployeeId);
            movementType = itemView.findViewById(R.id.movementType);
            movementDateTime = itemView.findViewById(R.id.movementDateTime);
        }
    }
}
