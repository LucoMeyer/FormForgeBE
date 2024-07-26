import cv2
import logging
import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from PyPDF2 import PdfReader

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
UPLOAD_FOLDER = tempfile.gettempdir()
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

logging.basicConfig(level=logging.DEBUG)

def extract_pdf_fields(pdf_path):
    reader = PdfReader(pdf_path)
    fields = []
    signatures = []

    for page_num, page in enumerate(reader.pages):
        if "/Annots" in page:
            for annot in page["/Annots"]:
                annot_obj = annot.get_object()
                if annot_obj:
                    field_name = annot_obj.get("/T")
                    field_value = annot_obj.get("/V")
                    field_type = annot_obj.get("/FT")
                    logging.debug(f"Annot Object: {annot_obj}")
                    fields.append({"name": field_name, "value": field_value, "type": field_type})
                    logging.debug(f"Extracted field: {{'name': {field_name}, 'value': {field_value}, 'type': {field_type}}}")

                    if field_type == "/Sig":
                        signatures.append({"name": field_name, "signed": bool(field_value)})
                        logging.debug(f"Extracted signature: {{'name': {field_name}, 'signed': {bool(field_value)}}}")
    return fields, signatures

def identify_and_validate_form(fields, signatures):
    form_type = "RiskProfile"
    
    field_groups = {
        "Your investment term is": ['Investment Term', 'Investment Term2', 'Investment Term3', 'Investment Term4', 'Investment Term5'],
        "Required risk": ['Required Risk 1', 'Required Risk 2', 'Required Risk 3'],
        "Risk tolerance": ['Risk Tolerance 1', 'Risk Tolerance 2', 'Risk Tolerance 3'],
        "Risk capacity": ['Risk Category 1', 'Risk Category 2', 'Risk Category 3'],
        "Score outcome": ['Risk outcome 1', 'Risk outcome 2', 'Risk outcome 3', 'Risk outcome 4', 'Risk outcome 5']
    }

    required_fields = [
        'Prepared for', 'Identity number', 'Financial Adviser', 'Prepared on', 'TOTAL SCORE',
        'Your derived profile according to this Risk Questionnaire is', 'Date', 'If you disagree please state the chosen risk profile and the reason for this risk profile' 
        #, 'Signature of client'
    ]

    missing_fields = []

    for group_name, group_fields in field_groups.items():
        if not any(field['value'] for field in fields if field['name'] in group_fields):
            missing_fields.append(group_name)

    for field in required_fields:
        matched_field = next((f for f in fields if f['name'] == field), None)
        if matched_field is None or matched_field['value'] is None:
            missing_fields.append(field)

    logging.debug(f"All extracted fields: {fields}")
    logging.debug(f"Missing fields: {missing_fields}")

    return form_type, list(set(missing_fields))

def extract_signature_image(pdf_path, page_num, signature_coords):
    reader = PdfReader(pdf_path)
    page = reader.pages[page_num]
    x, y, width, height = signature_coords

    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_img:
        temp_img_name = temp_img.name
        # Placeholder: Use correct method to extract image from PDF
        # pdf2image.convert_from_path(pdf_path)[page_num].crop((x, y, x + width, y + height)).save(temp_img_name)
        logging.debug(f"Extracted signature image to: {temp_img_name}")

    return temp_img_name

def detect_handwritten_signature(image_path):
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    _, thresh = cv2.threshold(image, 150, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    has_signature = bool(contours)
    logging.debug(f"Handwritten signature detected: {has_signature}")

    return has_signature

@app.route('/api/v1/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected for uploading"}), 400

    temp_file = tempfile.NamedTemporaryFile(delete=False, dir=app.config['UPLOAD_FOLDER'])
    file.save(temp_file.name)
    temp_file.close()

    try:
        fields, signatures = extract_pdf_fields(temp_file.name)
        form_type, missing_fields = identify_and_validate_form(fields, signatures)

        if 'Signature of client' in missing_fields:
            signature_image_path = extract_signature_image(temp_file.name, page_num=0, signature_coords=(100, 100, 200, 50))  # Example coordinates
            if detect_handwritten_signature(signature_image_path):
                missing_fields.remove('Signature of client')
    except Exception as e:
        logging.error(f"Error processing file: {e}")
        return jsonify({"error": f"Internal server error: {e}"}), 500
    finally:
        os.remove(temp_file.name)

    return jsonify({
        "message": "File successfully uploaded",
        "form_type": form_type,
        "missing_fields": missing_fields,
        "fields": fields,
        "signatures": signatures
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=12345, debug=True)
