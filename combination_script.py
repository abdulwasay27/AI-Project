import os
import glob
import csv

def combine_csvs(input_folder, output_file):
    # Find all CSV files in the input folder
    csv_files = glob.glob(os.path.join(input_folder, "*.csv"))
    if not csv_files:
        print("No CSV files found in the specified folder.")
        return

    all_rows = []
    all_headers = set()

    # Read all rows and collect all headers
    for file in csv_files:
        with open(file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            all_rows.extend(rows)
            all_headers.update(reader.fieldnames)

    all_headers = sorted(all_headers)

    # Write combined CSV
    with open(output_file, "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=all_headers)
        writer.writeheader()
        for row in all_rows:
            # Fill missing columns with empty string
            full_row = {header: row.get(header, "") for header in all_headers}
            writer.writerow(full_row)

    print(f"Combined {len(csv_files)} CSV files into {output_file}")

if __name__ == "__main__":
    # Change 'data_folder' to the folder containing your CSV files
    data_folder = os.path.dirname("Dataset/")
    output_csv = os.path.join(data_folder, "combined_data.csv")
    combine_csvs(data_folder, output_csv)