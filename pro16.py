import re
import os
from flask import Flask, request, render_template, redirect, url_for
from PyPDF2 import PdfReader
from werkzeug.utils import secure_filename
from urllib.parse import unquote
import malaya
import csv
import pandas as pd 


# Flask app setup
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
OUTPUT_FOLDER = os.path.join('static', 'output')  # Save in static for easy serving
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# Ensure the upload and output folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Function to extract text from the PDF
def extract_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

 # Function to preprocess text using Malaya and normalize whitespace
def preprocess_text(text):
     # Tokenize using Malaya's tokenizer
     tokenizer = malaya.tokenizer.Tokenizer()
     return tokenizer.tokenize(text)


# Function to extract the Monthly Charges block
def extract_monthly_charges_block(text):
    start_marker = r"Caj Elektrik Anda Bagi Tempoh 6 Bulan"
    end_marker = r"\d+\s?Purata Caj Bulanan"
    pattern = f"{start_marker}.*?{end_marker}"

    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group()
    return "No matching charges section found."


# Function to extract month names and charges
def extract_months_and_charges(charges_text):
    months = []
    charges = []
    pattern = r"([A-Z]{3}-\d{2})\s*(?:\(BS\))?\s*([RM0-9,\.]+)"
    matches = re.findall(pattern, charges_text)

    for match in matches:
        month, charge = match
        months.append(month)
        charges.append(charge)


    return months, charges



# Function to extract the Detailed Charges block and save it to a .txt file
def extract_detailed_charges_block(text, filename="detailed_charges_block.txt"):
    start_marker = r"Keterangan Tanpa ST Dengan ST Jumlah"
    end_marker = r"Caj Semasa RM \d+\.\d{2}"
    pattern = f"{start_marker}.*?{end_marker}"

    match = re.search(pattern, text, re.DOTALL)
    if match:
        detailed_charges_text = match.group()

        # Save the extracted detailed charges block to a .txt file
        with open(filename, "w") as file:
            file.write(detailed_charges_text)

        return detailed_charges_text
    else:
        return "No matching detailed charges section found."





def extract_detailed_charges_data(detailed_charges_text):
    total_usage_no_st = ""
    total_usage_st = ""
    icpt_no_st = ""
    icpt_st = ""
    kwtbb = ""
    current_charge = ""

    # Update regex to handle negative numbers with spaces
    number_pattern = r"-?\s*[\d.,]+"  # Matches positive or negative numbers with optional spaces after '-'

    # Extract Total Usage (No ST) and (ST)
    total_usage_match = re.search(
        fr"Jumlah Penggunaan Anda\s*\(.*?\)\s*RM\s*({number_pattern})\s*({number_pattern})\s*({number_pattern})",
        detailed_charges_text,
    )
    if total_usage_match:
        total_usage_no_st = total_usage_match.group(1).replace(" ", "")  # Remove extra spaces
        total_usage_st = total_usage_match.group(2).replace(" ", "")

    # Extract ICPT (No ST) and (ST)
    icpt_match = re.search(
        fr"ICPT\s*\(.*?\)\s*RM\s*({number_pattern})\s*({number_pattern})\s*({number_pattern})",
        detailed_charges_text,
    )
    if icpt_match:
        icpt_no_st = icpt_match.group(1).replace(" ", "")
        icpt_st = icpt_match.group(2).replace(" ", "")

    # Extract KWTBB
    kwtbb_match = re.search(
        fr"Kumpulan Wang Tenaga Boleh Baharu\s*\(.*?\)\s*RM\s*({number_pattern})",
        detailed_charges_text,
    )
    if kwtbb_match:
        kwtbb = kwtbb_match.group(1).replace(" ", "")

    # Extract Current Charge
    current_charge_match = re.search(
        fr"Caj Semasa\s*RM\s*({number_pattern})", detailed_charges_text
    )
    if current_charge_match:
        current_charge = current_charge_match.group(1).replace(" ", "")

    return {
        "Total Usage (No ST)": total_usage_no_st,
        "Total Usage (ST)": total_usage_st,
        "ICPT (No ST)": icpt_no_st,
        "ICPT (ST)": icpt_st,
        "KWTBB (1.6%)": kwtbb,
        "Current Charge": current_charge,
    }






def parse_text_to_csv(txt_filename="detailed_charges_block.txt", csv_filename="detailed_charges_data.csv"):
    import csv  # Ensure the csv module is imported
    
    try:
        # Read the detailed charges block text from the .txt file
        with open(txt_filename, "r") as file:
            detailed_charges_text = file.read()

        # Extract the detailed charges data using the previous function
        extracted_data = extract_detailed_charges_data(detailed_charges_text)

        # Write the extracted data to a CSV file
        with open(csv_filename, 'w', newline='') as f:
            writer = csv.writer(f)

            # Write headers (attributes as columns)
            writer.writerow([
                "Total Usage (No ST)", 
                "Total Usage (ST)", 
                "ICPT (No ST)", 
                "ICPT (ST)", 
                "KWTBB (1.6%)", 
                "Current Charge"
            ])

            # Write values below the headers
            writer.writerow([
                f"RM {extracted_data['Total Usage (No ST)']}",
                f"RM {extracted_data['Total Usage (ST)']}",
                f"RM {extracted_data['ICPT (No ST)']}",
                f"RM {extracted_data['ICPT (ST)']}",
                f"RM {extracted_data['KWTBB (1.6%)']}",
                f"RM {extracted_data['Current Charge']}",
            ])

        print(f"Data has been successfully written to {csv_filename} (headers as columns).")

    except FileNotFoundError:
        print(f"Error: The file {txt_filename} does not exist.")
    except Exception as e:
        print(f"An error occurred: {e}")


# Function to extract the meter reading block from the text
def extract_meter_reading_block(text):
    start_marker = r"Maklumat Meter"
    end_marker = r"\s*PERBANKAN INTERNET"
    
    # Update the pattern to capture everything between the markers, including new lines and spaces
    pattern = f"{start_marker}(.*?){end_marker}"
    
    # Perform the search to find the block between the markers
    match = re.search(pattern, text, re.DOTALL)
    
    # If no match is found, return a message indicating no matching block
    if not match:
        return "no matching charges section found."
    
    # Extract the meter reading block
    meter_reading_text = match.group(1).strip()

    # Print the extracted meter reading text
    print("###", meter_reading_text, "###")

    # Return the isolated meter reading text
    return meter_reading_text


# Function to save meter readings into CSV
def save_meter_reading_to_csv(meter_reading_text, output_file_path):

    meter_reading_text = re.sub(r"(kWh|kW|kVARh)Saluran", r"\1", meter_reading_text)

    # Regular expression to capture the data fields in each row
    pattern = r"(M\s+\S+)\s+(\d{1,3}(?:,\d{3})*)\s+(\d{1,3}(?:,\d{3})*)\s+(\d+)\s+(\w+)"
    
    # List to hold the parsed data
    rows = []
    
    # Find all matches based on the pattern
    for match in re.finditer(pattern, meter_reading_text):
        meter_number = match.group(1).strip()
        prev_reading = int(match.group(2).replace(",", ""))
        curr_reading = int(match.group(3).replace(",", ""))
        usage = int(match.group(4))
        unit = match.group(5).strip()
        
        # Append the extracted data to rows
        rows.append([meter_number, prev_reading, curr_reading, usage, unit])
    
    # Write the rows to a CSV file
    with open(output_file_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        # Writing the header
        writer.writerow(["Meter Number", "Previous Meter Reading", "Current Meter Reading", "Usage", "Unit"])
        # Writing the data rows
        writer.writerows(rows)
    
    print(f"Data saved to {output_file_path}")



def combine_csv_files(monthly_csv, detailed_csv, meter_reading_csv, output_csv):
    try:
        # Read the three CSV files into dataframes
        monthly_df = pd.read_csv(monthly_csv)
        detailed_df = pd.read_csv(detailed_csv)
        meter_reading_df = pd.read_csv(meter_reading_csv)

        # Merge the dataframes side by side (using pd.concat)
        combined_df = pd.concat([monthly_df, detailed_df, meter_reading_df], axis=1)

        # Save the combined dataframe to a new CSV file
        combined_df.to_csv(output_csv, index=False)

        print(f"Combined data saved to {output_csv}")
        return output_csv  # Return the path to the combined CSV
    except Exception as e:
        print(f"Error during combining files: {e}")
        return None
    



# Route for the home page
@app.route('/')
def index():
    return render_template('index.html')

# Route to handle PDF file upload and display all extracted text
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)

    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)

    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        pdf_text = extract_text_from_pdf(file_path)
        return render_template('view_text.html', pdf_text=pdf_text, file_path=filename)






@app.route('/extract/<path:filename>')
def extract_desired_text(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file_path = unquote(file_path)

    if not os.path.exists(file_path):
        return f"File not found: {file_path}", 404

    pdf_text = extract_text_from_pdf(file_path)

    # **Monthly Charges Extraction**
    monthly_charges_text = extract_monthly_charges_block(pdf_text)
    months, charges = extract_months_and_charges(monthly_charges_text)

    monthly_output_file_path = os.path.join(app.config['OUTPUT_FOLDER'], 'monthly_charges.csv')
    with open(monthly_output_file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Month', 'Charge'])
        for month, charge in zip(months, charges):
            writer.writerow([month, charge])

    # **Detailed Charges Extraction**
    preprocessed_text = preprocess_text(pdf_text)
    detailed_charges_text = extract_detailed_charges_block(" ".join(preprocessed_text))

    extracted_detailed_charges_data = extract_detailed_charges_data(detailed_charges_text)

    detailed_output_file_path = os.path.join(app.config['OUTPUT_FOLDER'], 'detailed_charges_data.csv')
    with open(detailed_output_file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(extracted_detailed_charges_data.keys())
        writer.writerow(extracted_detailed_charges_data.values())

    # **Meter Reading Extraction**
    meter_reading_text = extract_meter_reading_block(pdf_text)
    meter_reading_output_file_path = os.path.join(app.config['OUTPUT_FOLDER'], 'meter_reading_data.csv')
    save_meter_reading_to_csv(meter_reading_text, meter_reading_output_file_path)

    # **Combine the CSVs**
    combined_output_file_path = os.path.join(app.config['OUTPUT_FOLDER'], 'combined_output.csv')
    combine_csv_files(
        monthly_csv=monthly_output_file_path,
        detailed_csv=detailed_output_file_path,
        meter_reading_csv=meter_reading_output_file_path,
        output_csv=combined_output_file_path
    )

    # Render the results with links to download the files
    return render_template(
        'result.html',
        monthly_output_file_path=monthly_output_file_path,
        detailed_output_file_path=detailed_output_file_path,
        meter_reading_output_file_path=meter_reading_output_file_path,
        combined_output_file_path=combined_output_file_path,
        months=", ".join(months),
        charges=", ".join(charges),
        detailed_data=extracted_detailed_charges_data
    )


    
    



# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
