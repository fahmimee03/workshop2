from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient
from werkzeug.utils import secure_filename
import os
import re
import csv
from urllib.parse import unquote
from PyPDF2 import PdfReader
import json

app = Flask(__name__)

# Set the secret key for sessions
app.secret_key = 'your_secret_key'

# MongoDB connection setup
client = MongoClient('mongodb://localhost:27017/')  # Replace with your MongoDB URI
db = client['Workshop2']  # Replace with your database name
user_collection = db['user']  # User collection
bill_collection = db['electric_bills']  # New collection for electric bills
train_collection = db['electric_consumption']



# Configure file upload folder
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = os.path.join('static', 'output')  # Save in static for easy serving
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# Ensure the upload and output folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Function to extract the desired block of text for Monthly Charges
def extract_monthly_charges_block(text):
    start_marker = r"Caj Elektrik Anda Bagi Tempoh 6 Bulan"
    end_marker = r"\d+\s?Purata Caj Bulanan &"  # Looks for a number followed by kWh
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

# Function to extract the Detailed Charges block
def extract_detailed_charges_block(text):
    start_marker = r"Keterangan Tanpa ST Dengan ST Jumlah"
    end_marker = r"Caj Semasa RM \d+\.\d{2}"
    pattern = f"{start_marker}.*?{end_marker}"

    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group()
    return "No matching detailed charges section found."

# Function to extract text from the PDF
def extract_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

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

    return render_template('index.html', username=session['username'], electric_bills=formatted_bills, months=months, charges=charges)

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
    
    return render_template('index-new.html',  username=session['username'])



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
                print("Electric bill data uploaded successfully!, success")
            else:
                flash('Failed to extract monthly charges. Ensure the PDF is valid.', 'danger')
                print("Failed to extract monthly charges. Ensure the PDF is valid., danger")

            return redirect(url_for('electric'))

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

    
    
    return render_template('electric_bills.html', username=session['username'], electric_bills=formatted_bills, months=months, charges=charges)


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
        password = request.form.get('password')
        email = request.form.get('email')

        # Check if user already exists
        if user_collection.find_one({"username": username}):
            flash("Username already exists.", "danger")
            return redirect(request.url)

        # Add user to MongoDB
        user_data = {"username": username, "password": password, "email": email}
        user_collection.insert_one(user_data)

        flash("Signup successful. Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('auth-boxed-register.html')

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


# Route for signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')

        # Check if user already exists
        if user_collection.find_one({"username": username}):
            flash("Username already exists.", "danger")
            return redirect(request.url)

        # Add user to MongoDB
        user_data = {"username": username, "password": password, "email": email}
        user_collection.insert_one(user_data)

        flash("Signup successful. Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('signup.html')

# Route for logout
@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("Logged out successfully.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
