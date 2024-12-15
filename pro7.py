import re 
import os
from flask import Flask, request, render_template, redirect, url_for
from PyPDF2 import PdfReader
from werkzeug.utils import secure_filename

# Flask app setup
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
OUTPUT_FOLDER = 'output'
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# Ensure the upload and output folders exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# Function to extract the desired block of text for monthly charges
def extract_monthly_charges_block(text):
    start_marker = r"Caj Elektrik Anda Bagi Tempoh 6 Bulan"
    end_marker = r"\d+\s?kWh"
    pattern = f"{start_marker}.*?{end_marker}"

    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group()
    return None

# Function to extract the specific bill details block
def extract_bill_details_block(text):
    """
    Extracts the section from the text starting with "Keterangan Tanpa ST Dengan ST Jumlah"
    and ending with "kVARh".
    """
    start_marker = r"Keterangan Tanpa ST Dengan ST Jumlah"
    end_marker = r"kVARh"
    pattern = f"{start_marker}.*?{end_marker}"

    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group()
    return None

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
        
        return render_template('view_text.html', pdf_text=pdf_text, file_path=file_path)

# Route to display the extracted text and save both blocks to files
@app.route('/extract/<path:file_path>')
def extract_desired_text(file_path):
    # Extract text again from the saved PDF file
    pdf_text = extract_text_from_pdf(file_path)
    
    # Extract the desired block of text
    monthly_charges_text = extract_monthly_charges_block(pdf_text)
    bill_details_text = extract_bill_details_block(pdf_text)

    if not monthly_charges_text:
        monthly_charges_text = "No matching monthly charges text found."
    if not bill_details_text:
        bill_details_text = "No matching bill details text found."

    # Save the extracted text to files
    output_file_path_1 = os.path.join(app.config['OUTPUT_FOLDER'], 'monthly_charges.txt')
    with open(output_file_path_1, 'w') as f:
        f.write(monthly_charges_text)

    output_file_path_2 = os.path.join(app.config['OUTPUT_FOLDER'], 'bill_details.txt')
    with open(output_file_path_2, 'w') as f:
        f.write(bill_details_text)

    return render_template(
        'result.html',
        monthly_charges_text=monthly_charges_text,
        bill_details_text=bill_details_text,
        output_file_path_1=output_file_path_1,
        output_file_path_2=output_file_path_2
    )

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
