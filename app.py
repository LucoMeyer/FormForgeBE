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
                    fields.append({
                        "name": field_name,
                        "value": field_value,
                        "type": field_type,
                        "page": page_num + 1  # Add page number here
                    })
                    logging.debug(f"Extracted field: {{'name': {field_name}, 'value': {field_value}, 'type': {field_type}, 'page': {page_num + 1}}}")

                    if field_type == "/Sig":
                        signatures.append({
                            "name": field_name,
                            "signed": bool(field_value),
                            "page": page_num + 1  # Add page number here
                        })
                        logging.debug(f"Extracted signature: {{'name': {field_name}, 'signed': {bool(field_value)}, 'page': {page_num + 1}}}")
    return fields, signatures

def identify_form(fields):
    # Check for unique fields in each form to identify the form type
    fais_keywords = ["@FA Full name", "@CD Full name Not permitted", "@CD Full name Appoint"]
    risk_profile_keywords = ["TOTAL SCORE", "Risk Tolerance", "Investment Term"]

    fais_match = any(field['name'] in fais_keywords for field in fields)
    risk_profile_match = any(field['name'] in risk_profile_keywords for field in fields)

    if fais_match:
        return "FAIS Letter"
    elif risk_profile_match:
        return "Risk Profile Questionnaire"
    else:
        logging.debug(f"Unrecognized form fields: {fields}")
        return "Unknown"

def validate_fais(fields):
    required_fields = ['Signature1', 'Signature2', 'Signature3', '@Date1', '@Date2', '@Date3']
    missing_fields = []

    for field in required_fields:
        matched_field = next((f for f in fields if f['name'] == field), None)
        if matched_field is None or matched_field['value'] is None:
            # Include page number in the output and format name
            page_num = next((f['page'] for f in fields if f['name'] == field), None)
            formatted_name = field.replace('Signature', 'Signature ').replace('@Date', 'Date ') + (f" (page {page_num})" if page_num else "")
            missing_fields.append(formatted_name)

    return list(set(missing_fields))

def validate_risk_profile(fields):
    field_groups = {
        "Investment Term": ['Investment Term', 'Investment Term2', 'Investment Term3', 'Investment Term4', 'Investment Term5'],
        "Required Risk": ['Required Risk 1', 'Required Risk 2', 'Required Risk 3'],
        "Risk Tolerance": ['Risk Tolerance 1', 'Risk Tolerance 2', 'Risk Tolerance 3'],
        "Risk Capacity": ['Risk Category 1', 'Risk Category 2', 'Risk Category 3'],
        "Score Outcome": ['Risk outcome 1', 'Risk outcome 2', 'Risk outcome 3', 'Risk outcome 4', 'Risk outcome 5']
    }

    required_fields = [
        'Prepared for', 'Identity number', 'Financial Adviser', 'Prepared on', 'TOTAL SCORE',
        'Your derived profile according to this Risk Questionnaire is', 'Date', 'If you disagree please state the chosen risk profile and the reason for this risk profile'
    ]

    missing_fields = []

    for group_name, group_fields in field_groups.items():
        if not any(field['value'] for field in fields if field['name'] in group_fields):
            missing_fields.append(group_name)

    for field in required_fields:
        matched_field = next((f for f in fields if f['name'] == field), None)
        if matched_field is None or matched_field['value'] is None:
            missing_fields.append(field)

    return list(set(missing_fields))

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
        form_type = identify_form(fields)

        if form_type == "FAIS Letter":
            missing_fields = validate_fais(fields)
        elif form_type == "Risk Profile Questionnaire":
            missing_fields = validate_risk_profile(fields)
        else:
            missing_fields = ["Unknown form type"]

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
