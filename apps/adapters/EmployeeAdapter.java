package com.trackingsystem.apps.adapters;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.TextView;
import androidx.annotation.NonNull;
import androidx.core.content.ContextCompat;
import androidx.recyclerview.widget.RecyclerView;

import com.trackingsystem.apps.R;
import com.trackingsystem.apps.models.Employee;

import java.util.ArrayList;
import java.util.List;

public class EmployeeAdapter extends RecyclerView.Adapter<EmployeeAdapter.EmployeeViewHolder> {

    private List<Employee> employeeList;

    // Interface pour gérer les clics sur les éléments
    public interface OnItemClickListener {
        void onItemClick(Employee employee);
        void onEditClick(Employee employee);
        void onDeleteClick(Employee employee);
    }

    private OnItemClickListener listener;

    public EmployeeAdapter(List<Employee> employeeList, OnItemClickListener listener) {
        this.employeeList = employeeList != null ? employeeList : new ArrayList<>();
        this.listener = listener;
    }

    /**
     * Crée de nouveaux ViewHolder.
     */
    @NonNull
    @Override
    public EmployeeViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_employee, parent, false);
        return new EmployeeViewHolder(view, listener, employeeList);
    }

    /**
     * Remplace le contenu d'une vue avec les données d'un employé.
     */
    @Override
    public void onBindViewHolder(@NonNull EmployeeViewHolder holder, int position) {
        Employee employee = employeeList.get(position);

        if (employee != null) {
            // Mise à jour des vues
            holder.employeeName.setText(String.format("%s %s", employee.getNom(), employee.getPrenom()));
            holder.employeeProfession.setText(employee.getProfession());
            holder.employeeEmail.setText(employee.getEmail());
            holder.employeePhone.setText(employee.getTelephone());
            holder.employeeType.setText(employee.getType());

            // Logique pour le taux horaire ou les frais d'écolage
            if ("employe".equalsIgnoreCase(employee.getType())) {
                if (employee.getTauxHoraire() != null) {
                    holder.employeeRate.setText(String.format("%.2f Ar/h", employee.getTauxHoraire()));
                    holder.employeeRate.setTextColor(ContextCompat.getColor(holder.itemView.getContext(), R.color.primary_green));
                } else {
                    holder.employeeRate.setText("N/A");
                    holder.employeeRate.setTextColor(ContextCompat.getColor(holder.itemView.getContext(), R.color.text_gray));
                }
            } else if ("etudiant".equalsIgnoreCase(employee.getType())) {
                if (employee.getFraisEcolage() != null) {
                    holder.employeeRate.setText(String.format("%.2f Ar", employee.getFraisEcolage()));
                    holder.employeeRate.setTextColor(ContextCompat.getColor(holder.itemView.getContext(), R.color.primary_orange));
                } else {
                    holder.employeeRate.setText("N/A");
                    holder.employeeRate.setTextColor(ContextCompat.getColor(holder.itemView.getContext(), R.color.text_gray));
                }
            } else {
                holder.employeeRate.setText("N/A");
                holder.employeeRate.setTextColor(ContextCompat.getColor(holder.itemView.getContext(), R.color.text_gray));
            }
        }
    }

    @Override
    public int getItemCount() {
        return employeeList.size();
    }

    /**
     * Met à jour la liste des employés et notifie l'adaptateur des changements.
     */
    public void updateEmployees(List<Employee> newEmployeeList) {
        this.employeeList = newEmployeeList != null ? newEmployeeList : new ArrayList<>();
        notifyDataSetChanged();
    }

    /**
     * Le ViewHolder contient les vues pour chaque élément de la liste.
     */
    public static class EmployeeViewHolder extends RecyclerView.ViewHolder {
        public TextView employeeName, employeeProfession, employeeEmail, employeePhone, employeeType, employeeRate;
        public ImageButton editButton, deleteButton;
        public ImageView employeeAvatar;

        public EmployeeViewHolder(@NonNull View itemView, OnItemClickListener listener, List<Employee> employeeList) {
            super(itemView);
            // Initialisation de toutes les vues en fonction de l'XML
            employeeName = itemView.findViewById(R.id.employeeName);
            employeeProfession = itemView.findViewById(R.id.employeeProfession);
            employeeEmail = itemView.findViewById(R.id.employeeEmail);
            employeePhone = itemView.findViewById(R.id.employeePhone);
            employeeType = itemView.findViewById(R.id.employeeType);
            employeeRate = itemView.findViewById(R.id.employeeRate);
            employeeAvatar = itemView.findViewById(R.id.employeeAvatar);
            editButton = itemView.findViewById(R.id.editButton);
            deleteButton = itemView.findViewById(R.id.deleteButton);

            // Ajout des écouteurs de clic dans le constructeur du ViewHolder
            itemView.setOnClickListener(v -> {
                int position = getAdapterPosition();
                if (listener != null && position != RecyclerView.NO_POSITION) {
                    listener.onItemClick(employeeList.get(position));
                }
            });

            editButton.setOnClickListener(v -> {
                int position = getAdapterPosition();
                if (listener != null && position != RecyclerView.NO_POSITION) {
                    listener.onEditClick(employeeList.get(position));
                }
            });

            deleteButton.setOnClickListener(v -> {
                int position = getAdapterPosition();
                if (listener != null && position != RecyclerView.NO_POSITION) {
                    listener.onDeleteClick(employeeList.get(position));
                }
            });
        }
    }
}
