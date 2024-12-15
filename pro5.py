import re
import os
from flask import Flask, request, render_template, redirect, url_for
from PyPDF2 import PdfReader
from werkzeug.utils import secure_filename
from urllib.parse import unquote

# Flask app setup
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
OUTPUT_FOLDER = os.path.join('static', 'output')  # Save in static for easy serving
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# Ensure the upload and output folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Function to extract the desired block of text from the PDF content
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

    # Updated regex to handle different formats (e.g., charges being on the next line or separated by spaces)
    pattern = r"([A-Z]{3}-\d{2})\s*(?:\(BS\))?\s*([RM0-9,\.]+)"

    matches = re.findall(pattern, charges_text)

    for match in matches:
        month, charge = match
        months.append(month)
        charges.append(charge)
    
    return months, charges






# Function to extract text from the PDF
def extract_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

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

        # Extract text from the PDF
        pdf_text = extract_text_from_pdf(file_path)

        return render_template('view_text.html', pdf_text=pdf_text, file_path=filename)

# Route to extract the desired block of text
@app.route('/extract/<path:filename>')
def extract_desired_text(filename):
    # Construct the file path
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    # Decode the URL-encoded file path
    file_path = unquote(file_path)

    # Check if the file exists
    if not os.path.exists(file_path):
        return f"File not found: {file_path}", 404

    # Extract text from the saved PDF file
    pdf_text = extract_text_from_pdf(file_path)

    # Extract the desired block of text
    extracted_text = extract_monthly_charges_block(pdf_text)

    # Extract months and charges
    months, charges = extract_months_and_charges(extracted_text)

    # Save the extracted months and charges to a file for future use
    output_file_path = os.path.join(app.config['OUTPUT_FOLDER'], 'isolated_text.csv')
    with open(output_file_path, 'w') as f:
        f.write("Months:\n")
        f.write(', '.join(months) + '\n')
        f.write("Charges:\n")
        f.write(', '.join(charges) + '\n')

    return render_template(
        'result.html', 
        months=", ".join(months),  # Display months in a row
        charges=", ".join(charges),  # Display charges in a row
        output_file_path=output_file_path
    )

# Route to show the full extracted text from the PDF
@app.route('/view_text/<path:filename>')
def view_full_text(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file_path = unquote(file_path)

    if not os.path.exists(file_path):
        return f"File not found: {file_path}", 404

    # Extract text from the PDF
    pdf_text = extract_text_from_pdf(file_path)

    return render_template('view_text.html', pdf_text=pdf_text, file_path=filename)

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
