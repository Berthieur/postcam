// Correction du fichier SalaryAdapter.java

package com.trackingsystem.apps.adapters;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;
import com.trackingsystem.apps.R;
import com.trackingsystem.apps.models.SalaryRecord;
import java.text.DecimalFormat;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;

public class SalaryAdapter extends RecyclerView.Adapter<SalaryAdapter.SalaryViewHolder> {

    private List<SalaryRecord> salaryRecords;
    private DecimalFormat decimalFormat;
    private SimpleDateFormat dateFormat;

    public SalaryAdapter(List<SalaryRecord> salaryRecords) {
        this.salaryRecords = salaryRecords;
        this.decimalFormat = new DecimalFormat("#.##");
        this.dateFormat = new SimpleDateFormat("dd/MM/yyyy", Locale.getDefault());
    }

    @NonNull
    @Override
    public SalaryViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_salary, parent, false);
        return new SalaryViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull SalaryViewHolder holder, int position) {
        SalaryRecord record = salaryRecords.get(position);
        holder.bind(record, decimalFormat, dateFormat);
    }

    @Override
    public int getItemCount() {
        return salaryRecords.size();
    }

    public void updateSalaryRecords(List<SalaryRecord> newRecords) {
        this.salaryRecords = newRecords;
        notifyDataSetChanged();
    }

    static class SalaryViewHolder extends RecyclerView.ViewHolder {
        private TextView employeeName;
        private TextView salaryAmount;
        private TextView hoursWorked;
        private TextView calculationDate;

        public SalaryViewHolder(@NonNull View itemView) {
            super(itemView);
            employeeName = itemView.findViewById(R.id.employeeName);
            salaryAmount = itemView.findViewById(R.id.salaryAmount);
            hoursWorked = itemView.findViewById(R.id.hoursWorked);
            calculationDate = itemView.findViewById(R.id.calculationDate);
        }

        public void bind(SalaryRecord record, DecimalFormat decimalFormat, SimpleDateFormat dateFormat) {
            employeeName.setText(record.getEmployeeName());
            // Correction : Utilisation de getAmount() à la place de getSalary()
            salaryAmount.setText( decimalFormat.format(record.getAmount())+ "Ar" );

            // Correction : La méthode getHoursWorked() peut retourner null, donc on vérifie.
            if (record.getHoursWorked() != null) {
                hoursWorked.setText(decimalFormat.format(record.getHoursWorked()) + "h");
            } else {
                hoursWorked.setText(""); // Ou un texte par défaut si les heures ne sont pas applicables
            }

            // Correction : Utilisation de getDate() à la place de getCalculationDate()
            calculationDate.setText(dateFormat.format(new Date(record.getDate())));
        }
    }
}