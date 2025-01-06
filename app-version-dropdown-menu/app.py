from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient
from werkzeug.utils import secure_filename
import os
import re
import csv
from urllib.parse import unquote
from PyPDF2 import PdfReader
import json
import pandas as pd
import plotly

app = Flask(__name__)

# Set the secret key for sessions
app.secret_key = 'your_secret_key'

# MongoDB connection setup
client = MongoClient('mongodb://localhost:27017/')  # Replace with your MongoDB URI
db = client['Workshop2']  # Replace with your database name
user_collection = db['user']  # User collection
bill_collection = db['electric_bills']  # New collection for electric bills
train_collection = db['electric_consumption']


### Function for Uploading electric Bills#######
# Configure file upload folder
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = os.path.join('static', 'output')  # Save in static for easy serving
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
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
    pattern = r"([A-Z]{3}-\d{2})(?:\s*\(BS\))?\s*([RM0-9,\.]+)|(?:\(BS\))?\s*([RM0-9,\.]+)\s*([A-Z]{3}-\d{2})"
    matches = re.findall(pattern, charges_text)

    for match in matches:
        # Match groups for either case
        if match[0]:  # Case where the month appears first
            months.append(match[0])
            charges.append(match[1])
        else:  # Case where the charge appears first
            charges.append(match[2])
            months.append(match[3])


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



#Train & Prediction Module 
@app.route('/prediction', methods=['GET', 'POST'])
def prediction():
    if request.method == 'POST':  # Check if the user clicked the Predict button
        print("SUCeess")

        # Run Debug_.py (forecasting)
        subprocess.run(["python", "Debug_.py"], check=True)

        # Return a success message or redirect to a results page
        return jsonify({"message": "Training and prediction completed successfully."})

    # Render the prediction page for GET request
    return render_template('prediction_model.html')




@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'username' not in session:
        return redirect(url_for('log'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part in the request', 'danger')
            return redirect(url_for('dashboard'))

        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(url_for('dashboard'))

        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Extract text from the PDF
            pdf_text = extract_text_from_pdf(file_path)

            # Extract the Monthly Charges block
            extracted_text = extract_monthly_charges_block(pdf_text)

            # Extract months and charges
            months, charges = extract_months_and_charges(extracted_text)

            # Save the data into MongoDB
            if months and charges:
                electric_bill_data = {
                    "username": session['username'],
                    "months": months,
                    "charges": charges
                }
                db['electric_bills'].insert_one(electric_bill_data)
                flash('Electric bill data uploaded successfully!', 'success')
            else:
                flash('Failed to extract monthly charges. Ensure the PDF is valid.', 'danger')

            return redirect(url_for('dashboard'))

    # Retrieve user's electric bills from MongoDB
    electric_bills = db['electric_bills'].find({"username": session['username']})

    # Pre-zip months and charges for each bill
    formatted_bills = []

    for bill in electric_bills:
        months = bill.get("months", [])
        charges = bill.get("charges", [])

        # Validate that months and charges are not empty
        if months and charges:
            formatted_bills.append({
                "data": list(zip(months, charges))
            })

    # Pass empty lists if no data found
    months = months if months else []
    charges = charges if charges else []

    return render_template('index-new.html', username=session['username'], electric_bills=formatted_bills, months=months, charges=charges)

# Route for new login
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        print(f"Email: {email}, Password: {password}")

        # Authenticate user
        user = user_collection.find_one({"email": email, "password": password})
        if user:
            session['email'] = email
            session['username'] = user.get('username', 'Guest')  # Default to 'Guest' if username is not found
            print("Success")
            return redirect(url_for('test'))
        else:
            flash("Invalid credentials.", "danger")
            print("GAGAL")

    return render_template('auth-boxed-login.html')


# Route for new dashboard
@app.route('/test', methods=['GET', 'POST'])
def test():
    if 'email' not in session:
        return redirect(url_for('login'))
    
    # Query the database for all bills of the current user
    user_bills_data = db['electric_bills'].find({"username": session['username']})

    # List to store the last months of each bill
    last_months = []  # Initialize as an empty list
    bill_data = []  # This will store all the bills
    all_charges = []  # To calculate the average monthly charge

    # Iterate through the user's bills
    for bill in user_bills_data:
        months = bill.get('Months', [])
        charges = bill.get('Charges', [])

        if months and charges:
            last_month = months[-1]  # Get the last month from the 'Months' array
            last_months.append(last_month)  # Add it to the list of last months
            bill_data.append(bill)  # Save the bill data for later use
            
            # Add the charge to the all_charges list for calculating the average
            all_charges.append(float(charges[-1].replace("RM", "").replace(",", "")))  # Convert charge to float

    # Calculate the average monthly charge
    avg_monthly_charge = sum(all_charges) / len(all_charges) if all_charges else 0

    # Find the maximum charge
    max_charge = max(all_charges) if all_charges else 0

    # Handle form submission to select a specific bill based on last month index
    selected_bill = None
    selected_month = None
    selected_charge = None
    if request.method == 'POST':
        selected_month_index = int(request.form['month_index'])  # Get the selected month index from the form
        selected_bill = bill_data[selected_month_index]  # Select the corresponding bill data
        
        # Get the months and charges for the selected bill
        months = selected_bill.get('Months', [])
        charges = selected_bill.get('Charges', [])

        # Calculate the average monthly charge for the selected bill
        charges_float = [float(charge.replace("RM", "").replace(",", "")) for charge in charges]
        selected_month = months[-1]  # The last month is the selected month
        selected_charge = charges[-1]  # The charge for the selected month
        
        avg_monthly_charge = sum(charges_float) / len(charges_float) if charges_float else 0
        max_charge = max(charges_float) if charges_float else 0

    # Pass the last months, selected bill, average charge, and max charge to the template
    return render_template('index-new.html', 
                           username=session['username'],
                           last_months=last_months or [],
                           charges=charges or [],  
                           selected_bill=selected_bill, 
                           selected_month=selected_month, 
                           selected_charge=selected_charge, 
                           avg_monthly_charge=avg_monthly_charge, 
                           max_charge=max_charge)
#return render_template('index-new.html',    username=session['username'], last_months=last_months or [], selected_bill=selected_bill, selected_month=selected_month, selected_charge=selected_charge, avg_monthly_charge=avg_monthly_charge, max_charge=max_charge)



#Electric Bills Module 
@app.route('/electric', methods=['GET', 'POST'])
def electric():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part in the request', 'danger')
            return redirect(url_for('electric'))

        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'danger')
            print("No file selected, danger")
            return redirect(url_for('electric'))

        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Extract text from the PDF
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
            detailed_charges_text = extract_detailed_charges_block(pdf_text)
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
                # Step 1: Read the CSV file that contains the meter readings

                meter_reading_df = pd.read_csv(meter_reading_output_file_path)
                # Step 2: Check if the data in the CSV is correct
                print(meter_reading_df.head())  # This will print the first few rows of the DataFrame

                # Step 3: Extract the data into lists (ensure column names match exactly)
                meter_numbers = meter_reading_df['Meter Number'].tolist()
                previous_meter_reading = meter_reading_df['Previous Meter Reading'].tolist()
                current_meter_reading = meter_reading_df['Current Meter Reading'].tolist()
                usage = meter_reading_df['Usage'].tolist()
                unit = meter_reading_df['Unit'].tolist()

                # Step 4: Check for missing or NaN values and replace with defaults
                meter_numbers = [x if pd.notna(x) else "N/A" for x in meter_numbers]
                previous_meter_reading = [x if pd.notna(x) else 0 for x in previous_meter_reading]
                current_meter_reading = [x if pd.notna(x) else 0 for x in current_meter_reading]
                usage = [x if pd.notna(x) else 0 for x in usage]
                unit = [x if pd.notna(x) else "kWh" for x in unit]  # Default to 'kWh' if missing

            # **Combine the CSVs**
            combined_output_file_path = os.path.join(app.config['OUTPUT_FOLDER'], 'combined_output.csv')
            combine_csv_files(
                monthly_csv=monthly_output_file_path,
                detailed_csv=detailed_output_file_path,
                meter_reading_csv=meter_reading_output_file_path,
                output_csv=combined_output_file_path
            )

            # Save the months and charges to MongoDB
            if months and charges and extracted_detailed_charges_data:
            # Create a single document with all fields grouped into arrays
                electric_bill_data = {
                "username": session['username'],
                "Months": months,
                "Charges": charges,
                "Total Usage (No ST)": extracted_detailed_charges_data.get('Total Usage (No ST)', []),
                "Total Usage (ST)": extracted_detailed_charges_data.get('Total Usage (ST)', []),
                "ICPT (No ST)": extracted_detailed_charges_data.get('ICPT (No ST)', []),
                "ICPT (ST)": extracted_detailed_charges_data.get('ICPT (ST)', []),
                "KWTBB (1.6%)": extracted_detailed_charges_data.get('KWTBB (1.6%)', []),
                "Current Charge": extracted_detailed_charges_data.get('Current Charge', []),
                "Meter Numbers": meter_numbers,
                "Previous Meter Reading": previous_meter_reading,
                "Current Meter Reading": current_meter_reading,
                "Usage": usage,
                "Unit": unit
            }
                db['electric_bills'].insert_one(electric_bill_data)
                flash('Electric bill data uploaded and extracted successfully!', 'success')
                print("Electric bill data uploaded and extracted successfully!, success")
            else:
                flash('Failed to extract monthly charges. Ensure the PDF is valid.', 'danger')
                print("Failed to extract monthly charges. Ensure the PDF is valid., danger")

            return redirect(url_for('electric'))

    # Retrieve user's electric bills from MongoDB
    electric_bills = db['electric_bills'].find({"username": session['username']})

    # Pre-zip months and charges for each bill
    formatted_bills = []
    for bill in electric_bills:
        months = bill.get("Month", [])
        charges = bill.get("Charge", [])
        if months and charges:
            formatted_bills.append({
                "data": list(zip(months, charges))
            })

    return render_template('electric_bills.html', username=session['username'], electric_bills=formatted_bills)



#Suggestion Module
@app.route('/suggestion', methods=['GET', 'POST'])
def suggestion():
    
    
    return render_template('suggestion.html')

@app.route('/icon', methods=['GET', 'POST'])
def icon():
    
    
    return render_template('icons-line-icons.html')



# Route for register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        phone_number = request.form.get('phone_number')
        appliances = request.form.getlist('appliances')  # Get list of selected appliances
        custom_appliance = request.form.get('custom_appliance')
        hours_per_day = request.form.get('hours_per_day')
        work_hours = request.form.get('work_hours')
        weekend_home = request.form.get('weekend_home')
        work_from_home = request.form.get('work_from_home')
        household_size = request.form.get('household_size')

        # Check if username or email already exists
        if user_collection.find_one({"username": username}):
            error = {"field": "username", "message": "Username already exists!"}
            return render_template('auth-boxed-register.html', error=error, form_data=request.form)
        if user_collection.find_one({"email": email}):
            error = {"field": "email", "message": "Email already exists!"}
            return render_template('auth-boxed-register.html', error=error, form_data=request.form)

        # Add user to MongoDB
        user_data = {"username": username,"email": email,"password": password,"phone_number": phone_number,"appliances": appliances,"hours_per_day": hours_per_day,"work_hours": work_hours,"weekend_home": weekend_home,"work_from_home": work_from_home,"household_size": household_size}
        user_collection.insert_one(user_data)

        flash("Signup successful. Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('auth-boxed-register.html', error=None, form_data={})

# Route for login
@app.route('/log', methods=['GET', 'POST'])
def log():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Authenticate user
        user = user_collection.find_one({"username": username, "password": password})
        if user:
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials.", "danger")

    return render_template('login.html')



# Route for logout
@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("Logged out successfully.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
