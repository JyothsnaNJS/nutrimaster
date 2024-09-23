from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import pandas as pd
import pdfplumber
import os
import re

app = Flask(__name__)

# Set secret key for session management
app.secret_key = 'hakunamatata'

# Load Excel data into DataFrames
names_units_df = pd.read_excel('parameters.xlsx', sheet_name='main_table')
alt_names_df = pd.read_excel('parameters.xlsx', sheet_name='alt_name_table')
ranges_df = pd.read_excel('parameters.xlsx', sheet_name='param_table')
master_cea_df = pd.read_excel('parameters.xlsx', sheet_name='master_cea')
nutrients_table_df = pd.read_excel('nutrients.xlsx', sheet_name='nutrients_def_mapping')

# Load food-nutrient mapping from the Excel sheet
food_nutrient_mapping_df = pd.read_excel('nutrients.xlsx', sheet_name='food_nutrients_mapping')

# Ensure uploads folder exists
if not os.path.exists('uploads'):
    os.makedirs('uploads')

# PDF parsing and parameter extraction
def parse_pdf(pdf_path):
    extracted_data = {}
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    lines = text.split('\n')
                    for line in lines:
                        # Use regex to match parameter name and value
                        match = re.search(r'([A-Za-z\s]+)\s+([\d.]+)\s*(\w+)?', line)
                        if match:
                            param_name = match.group(1).strip()
                            param_value = match.group(2).strip()

                            try:
                                param_value = float(param_value)
                            except ValueError:
                                continue

                            main_name = names_units_df[names_units_df['general_name'].str.lower() == param_name.lower()]['general_name'].values
                            alt_name_matches = alt_names_df[alt_names_df['alt_name'].str.lower() == param_name.lower()]['general_name'].values

                            if len(main_name) > 0:
                                extracted_data[main_name[0]] = param_value
                            elif len(alt_name_matches) > 0:
                                extracted_data[alt_name_matches[0]] = param_value
    
    except Exception as e:
        print(f"Error processing the PDF file: {e}")
    
    return extracted_data

# Upload route and parameter extraction
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'pdfFile' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['pdfFile']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        file_path = os.path.join('uploads', file.filename)
        file.save(file_path)

        # Parse the PDF
        extracted_data = parse_pdf(file_path)
        comparison_results, deficiencies = check_parameters(extracted_data)

        # Save extracted data and deficiencies to session
        session['extracted_data'] = extracted_data
        session['deficiencies'] = deficiencies

        return jsonify(comparison_results)
    except Exception as e:
        print(f"Error processing file upload: {e}")
        return jsonify({'error': f'An error occurred during file processing: {str(e)}'}), 500

# Compare extracted data with Excel data
def check_parameters(extracted_data):
    flagged_params = []
    deficiencies = []  # Track nutrient deficiencies
    
    for param, value in extracted_data.items():
        param_data = ranges_df[ranges_df['general_name'].str.lower() == param.lower()]

        if not param_data.empty:
            try:
                min_normal = float(param_data.iloc[0]['min_normal_range'])
                max_normal = float(param_data.iloc[0]['max_normal_range'])
                status = 'Normal'

                if value < min_normal or value > max_normal:
                    status = 'Risk' if (value < min_normal) else 'Concern'

                    # Look up the nutrients required for this parameter
                    nutrients_needed = nutrients_table_df[nutrients_table_df['general_name'].str.lower() == param.lower()]['nutrient'].tolist()

                    # If the status is 'Risk' or 'Concern', add the nutrients to the deficiencies
                    if status in ['Risk', 'Concern']:
                        deficiencies.extend(nutrients_needed)
                        print(f"Parameter: {param}, Status: {status}, Nutrients Needed: {nutrients_needed}")

                flagged_params.append({
                    'parameter': param,
                    'value': value,
                    'status': status,
                    'normal_range': f"{min_normal} - {max_normal}"
                })
            except ValueError:
                continue

    print("Final Deficiencies List:", deficiencies)
    return flagged_params, deficiencies


# Vegetable selection route
@app.route('/vegetable_selection')
def vegetable_selection():
    # Get deficiencies from session
    deficiencies = session.get('deficiencies')
    
    if not deficiencies:
        return redirect(url_for('index'))  # Redirect if deficiencies are not found

    print("Deficiencies from session:", deficiencies)  # Debugging print to check if deficiencies are passed correctly

    # Get recommended foods based on deficiencies from food-nutrient mapping
    recommended_foods = food_nutrient_mapping_df[food_nutrient_mapping_df['nutrient'].isin(deficiencies)]

    # Categorize compulsory and normal vegetables
    compulsory_vegetables = {}
    normal_vegetables = []

    for nutrient in deficiencies:
        nutrient_foods = recommended_foods[recommended_foods['nutrient'] == nutrient]['food_name'].tolist()
        compulsory_vegetables[nutrient] = nutrient_foods
    
    print("Compulsory Vegetables:", compulsory_vegetables)

    return render_template('vegetable_selection.html', 
                           compulsory_vegetables=compulsory_vegetables, 
                           normal_vegetables=normal_vegetables, 
                           deficiencies=deficiencies)


# Route for food plan generation and session clearing
@app.route('/submit_food_plan', methods=['POST'])
def submit_food_plan():
    selected_vegetables = request.form.getlist('vegetables')

    # Generate the food plan as a dictionary with days and corresponding foods
    food_plan = {f"Day {i+1}": food for i, food in enumerate(selected_vegetables)}

    # Clear session after food plan submission
    session.clear()

    # Render the food plan page with the generated food plan
    return render_template('weekly_food_plan.html', food_plan=food_plan)


@app.route('/parameter_details/<general_name>')
def get_parameter_details(general_name):
    parameter_data = master_cea_df[master_cea_df['general_name'].str.lower() == general_name.lower()]

    causes = parameter_data[parameter_data['type'] == 'cause']['what_how'].tolist()
    effects = parameter_data[parameter_data['type'] == 'effect']['what_how'].tolist()
    avoids = parameter_data[parameter_data['type'] == 'avoid']['what_how'].tolist()

    return jsonify({
        'causes': causes,
        'effects': effects,
        'avoids': avoids
    })


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/response')
def response_page():
    return render_template('response.html')

if __name__ == '__main__':
    app.run(debug=True)
