from flask import Flask, request, jsonify
from flask_cors import CORS
import tempfile
from PyPDF2 import PdfReader
import os
import logging

#   Jou Toets URL vanaf Angular is : http://192.168.88.136:12345/upload


app = Flask(__name__)
CORS(app)
UPLOAD_FOLDER = 'uploads'
CONTROLLER = '/api/v1'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route(CONTROLLER + '/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected for uploading"}), 400
    
    # filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    # file.save(filepath)
    # return jsonify({"message": "File successfully uploaded", "filepath": filepath}), 200

    # Create a unique temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, dir=app.config['UPLOAD_FOLDER'])
    file.save(temp_file.name)
    temp_file.close()

    return jsonify({"message": "File successfully uploaded", "filepath": temp_file.name}), 200


@app.route(CONTROLLER + '/uploadRiskProfile', methods=['POST'])
def upload_RiskProfile():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected for uploading"}), 400

    # Create a unique temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, dir=app.config['UPLOAD_FOLDER'])
    file.save(temp_file.name)
    temp_file.close()

    try:
        # Extract fields from the PDF
        fields, signatures = extract_pdf_fields(temp_file.name)
    finally:
        # Remove the temporary file
        os.remove(temp_file.name)
    
    return jsonify({"message": "File successfully uploaded", "fields": fields, "signatures": signatures}), 200

def extract_pdf_fields(pdf_path):
    fields = []
    signatures = []
    with open(pdf_path, "rb") as pdf_file:
        reader = PdfReader(pdf_file)
        
        if reader.is_encrypted:
            reader.decrypt("")
        
        if '/AcroForm' in reader.trailer['/Root']:
            form = reader.trailer['/Root']['/AcroForm']
            form_fields = form['/Fields']
            for field in form_fields:
                field_object = field.get_object()
                field_name = field_object.get('/T')
                field_value = field_object.get('/V')
                if field_name:
                    fields.append({
                        "name": field_name,
                        "value": field_value
                    })
                    logging.debug(f"Extracted field: {{'name': {field_name}, 'value': {field_value}}}")
                
                # Check if the field is a signature field
                if field_object.get('/FT') == '/Sig':
                    signature = {
                        "name": field_name,
                        "value": field_value,
                        "signed": True if field_value else False
                    }
                    signatures.append(signature)
                    logging.debug(f"Found signature field: {signature}")
                else:
                    signatures.append({
                        "name": field_name,
                        "signed": False
                    })
        else:
            logging.debug("No form fields found in the PDF.")
    logging.debug(f"Total fields extracted: {fields}")
    logging.debug(f"Total signatures extracted: {signatures}")
    return fields, signatures


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=12345)
