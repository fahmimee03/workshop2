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

# Function to extract text from the PDF
def extract_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

# Function to extract detailed charges data
def extract_detailed_charges_data(detailed_charges_text):
    # Initialize values for each column
    total_usage_no_st = ""
    total_usage_st = ""
    icpt_no_st = ""
    icpt_st = ""
    kwtbb = ""
    current_charge = ""

    # Process the block line by line
    lines = detailed_charges_text.splitlines()
    for line in lines:
        if "Jumlah Penggunaan Anda" in line:
            values = re.findall(r"RM\s*([\d.,]+)", line)
            if len(values) >= 2:
                total_usage_no_st = values[0]
                total_usage_st = values[1]
        elif "ICPT" in line:
            values = re.findall(r"RM\s*([\d.,]+)", line)
            if len(values) >= 2:
                icpt_no_st = values[0]
                icpt_st = values[1]
        elif "Kumpulan Wang Tenaga Boleh Baharu" in line:
            match = re.search(r"RM\s*([\d.,]+)", line)
            if match:
                kwtbb = match.group(1)
        elif "Caj Semasa" in line:
            match = re.search(r"RM\s*([\d.,]+)", line)
            if match:
                current_charge = match.group(1)

    return {
        "Total Usage (No ST)": total_usage_no_st,
        "Total Usage (ST)": total_usage_st,
        "ICPT (No ST)": icpt_no_st,
        "ICPT (ST)": icpt_st,
        "KWTBB (1.6%)": kwtbb,
        "Current Charge": current_charge,
    }

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

    # Extract the Detailed Charges block
    detailed_charges_text = extract_detailed_charges_block(pdf_text)

    # Parse specific details
    extracted_data = extract_detailed_charges_data(detailed_charges_text)

    # Save extracted details to a CSV file
    output_file_path = os.path.join(app.config['OUTPUT_FOLDER'], 'extracted_data.csv')
    with open(output_file_path, 'w') as f:
        # Write header
        f.write(
            "Total Usage (No ST),Total Usage (ST),ICPT (No ST),ICPT (ST),KWTBB (1.6%),Current Charge\n"
        )
        # Write extracted data
        f.write(
            f"{extracted_data['Total Usage (No ST)']},{extracted_data['Total Usage (ST)']},"
            f"{extracted_data['ICPT (No ST)']},{extracted_data['ICPT (ST)']},"
            f"{extracted_data['KWTBB (1.6%)']},{extracted_data['Current Charge']}\n"
        )

    # Render result page
    return render_template(
        'result.html',
        extracted_data=extracted_data,
        output_file_path=output_file_path,
    )

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
