from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import pdfplumber
import os
import re
import io
from io import BytesIO
import base64
import matplotlib
matplotlib.use('Agg')



app = Flask(__name__)

# Set secret key for session management
app.secret_key = 'hakunamatata'

# Load Excel data into DataFrames
names_units_df = pd.read_excel('parameters.xlsx', sheet_name='main_table')
alt_names_df = pd.read_excel('parameters.xlsx', sheet_name='alt_name_table')
ranges_df = pd.read_excel('parameters.xlsx', sheet_name='param_table')
master_cea_df = pd.read_excel('parameters.xlsx', sheet_name='master_cea')

# Load food-nutrient mapping from the Excel sheet
nutrients_table_df = pd.read_excel('nutrients.xlsx', sheet_name='nutrients_def_mapping')
food_nutrient_mapping_df = pd.read_excel('nutrients.xlsx', sheet_name='food_nutrients_mapping')
nutri_tree_df = pd.read_excel('nutrients.xlsx', sheet_name='nutri_tree_dependencies')
rda_df = pd.read_excel('nutrients.xlsx', sheet_name='RDA')

# Ensure uploads folder exists
if not os.path.exists('uploads'):
    os.makedirs('uploads')

def analyze_uploaded_report(filepath):
    extracted_data = parse_pdf(filepath)  # Use the file path

    flagged_params, deficiencies = check_parameters(extracted_data)

    # Dynamically build parameter_deficiencies
    parameter_deficiencies = {}
    for param_data in flagged_params:
        param_name = param_data['parameter']
        param_status = param_data['status']
        if param_status in ['Risk', 'Concern']:
            nutrients_needed = nutrients_table_df[nutrients_table_df['general_name'].str.lower() == param_name.lower()]['nutrient'].tolist()
            parameter_deficiencies[param_name] = nutrients_needed

    return flagged_params, parameter_deficiencies

    
@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']  # Ensure 'file' matches the frontend name

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        filename = file.filename
        filepath = os.path.join('uploads', filename)
        file.save(filepath)

        # Analyze the uploaded report
        analyzed_parameters, deficiencies = analyze_uploaded_report(filepath)

        session['parameters_data'] = analyzed_parameters
        session['parameter_deficiencies'] = deficiencies

        return jsonify({'message': 'File processed successfully', 'redirect_url': url_for('response_page')}), 200

    return jsonify({'error': 'File upload failed'}), 400


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






def generate_tree_graph(parameter_deficiencies):
    G = nx.DiGraph()

    for param, nutrients in parameter_deficiencies.items():
        # Add the parameter itself as a root node
        G.add_node(param, layer=0)
        
        for nutrient in nutrients:
            # Add nutrients as children of the parameter
            G.add_edge(param, nutrient)
            
            # Add deeper nutrient dependencies from nutri_tree_df
            dependency_tree = nutri_tree_df[nutri_tree_df['child_nutrient'].str.lower() == nutrient.lower()].to_dict('records')

            for item in dependency_tree:
                parent = item['parent_nutrient']
                child = item['child_nutrient']

                # Connect the nutrients to their deeper dependencies
                if parent and parent != 'None':
                    G.add_edge(nutrient, parent)
                else:
                    G.add_edge(nutrient, child)

    # Use shell layout for better hierarchical representation
    pos = nx.spring_layout(G, k=0.5, iterations=50)

    # Draw the graph with non-overlapping nodes and labels
    plt.figure(figsize=(10, 8))
    nx.draw(G, pos, with_labels=True, node_size=3000, node_color="lightblue", font_size=10, font_weight="bold", arrows=True)
    plt.title("Nutrient Deficiency Dependency Tree")

    # Save the image in a buffer and encode it to base64
    img_buffer = BytesIO()
    plt.savefig(img_buffer, format='png')
    img_buffer.seek(0)
    graph_img = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
    img_buffer.close()
    plt.close()

    return graph_img


# Example usage:
# Pass the dependency_tree as a list of dictionaries as done in previous code
# dependency_tree = [
#     {'parent_nutrient': 'Iron', 'child_nutrient': 'Hemoglobin', ...},
#     {'parent_nutrient': 'Folate', 'child_nutrient': 'Hemoglobin', ...},
# ]
# graph_img = generate_tree_graph(dependency_tree)


# Vegetable selection route
@app.route('/vegetable_selection', methods=['POST'])
def vegetable_selection():
    print("Session Data:", session)  # Debug session dat
    # Retrieve user info from form submission
    age = int(request.form.get('age'))
    gender = request.form.get('gender')
    weight = float(request.form.get('weight'))
    activity_level = request.form.get('activity-level')

    # Store user info in session for future use
    session['user_info'] = {
        'age': age,
        'gender': gender,
        'weight': weight,
        'activity_level': activity_level
    }

    # Get deficiencies from session
    deficiencies = session.get('deficiencies')
    #added by jyothsna
    parameters_data = session.get('parameters_data')
    parameter_deficiencies = session.get('parameter_deficiencies')
    #### end of code added by jyothsna
    if not deficiencies:
        return redirect(url_for('index'))  # Redirect if deficiencies are not found

    print("Deficiencies from session:", deficiencies)

    # Find deeper nutrient dependencies from nutri_tree_df
    # Load dependencies using parent_nutrient and child_nutrient
    dependency_tree = nutri_tree_df[nutri_tree_df['parent_nutrient'].isin(deficiencies)].to_dict('records')

    # Get recommended foods based on deficiencies from food-nutrient mapping
    recommended_foods = food_nutrient_mapping_df[food_nutrient_mapping_df['nutrient'].isin(deficiencies)]

    # Calculate RDA values for each nutrient based on user info
    rda_values = {}
    for nutrient in deficiencies:
        rda_values[nutrient] = get_rda_value(nutrient, age, gender, activity_level)

    # Categorize compulsory and normal vegetables
    compulsory_vegetables = {}
    for nutrient in deficiencies:
        nutrient_foods = recommended_foods[recommended_foods['nutrient'] == nutrient][['food_name', 'nutrient_value', 'nutrient_unit']].to_dict(orient='records')
        compulsory_vegetables[nutrient] = nutrient_foods
        
    # Generate Text Representation for Nutrient Deficiencies
    text_representation = "Nutrient Deficiency Dependencies:\n\n"
    for parameter, nutrients in parameter_deficiencies.items():
        text_representation += f"\nParameter: {parameter}\n"
        for nutrient in nutrients:
            text_representation += f"  → {nutrient}\n"
            deeper_nutrients = get_deeper_nutrients(nutrient)
            for deeper in deeper_nutrients:
                text_representation += f"    → {deeper['nutrient']}\n"

    # Generate Deficiency Graph Image
    graph_img = generate_tree_graph(parameter_deficiencies)

    return render_template('vegetable_selection.html', 
                           compulsory_vegetables=compulsory_vegetables, 
                           rda_values=rda_values,
                           user_info=session['user_info'],
                           dependency_tree=dependency_tree,
                           text_representation=text_representation,  # Pass the text representation
                           graph_img=graph_img)  # Pass the dependency tree




def get_rda_value(nutrient, age, gender, activity_level):
    rda_filtered = rda_df[
        (rda_df['nutrient'].str.lower() == nutrient.lower()) &
        (rda_df['min_age'] <= int(age)) & 
        (rda_df['max_age'] >= int(age)) &
        (rda_df['gender'].str.lower() == gender.lower()) &
        (rda_df['activity_level'].str.lower() == activity_level.lower())
    ]
    
    if not rda_filtered.empty:
        return rda_filtered.iloc[0]['rda_value']
    else:
        return "RDA not available"


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
    
# Function to retrieve deeper nutrient dependencies from the nutri_tree_df
def get_deeper_nutrients(nutrient):
    dependencies = nutri_tree_df[nutri_tree_df['parent_nutrient'].str.lower() == nutrient.lower()]
    deeper_nutrients = []
    
    for _, row in dependencies.iterrows():
        deeper_nutrients.append({
            'nutrient': row['child_nutrient'],
            'relation_type': row['relation_type'],
            'comments': row['comments'],
            'body_signs': row['body_signs']
        })
    return deeper_nutrients

@app.route('/response', methods=['GET'])
def response_page():
    parameters_data = session.get('parameters_data')
    parameter_deficiencies = session.get('parameter_deficiencies')

    if not parameters_data or not parameter_deficiencies:
        return render_template('response.html', text_representation="No deficiencies found.")
    
    # Add debug to check what is passed to the page
    print(f"parameters_data: {parameters_data}")
    print(f"parameter_deficiencies: {parameter_deficiencies}")
    
    text_representation = "Nutrient Deficiency Dependencies:\n\n"

    # Process each parameter and its deficiencies
    for parameter, nutrients in parameter_deficiencies.items():
        text_representation += f"\nParameter: {parameter}\n"
        if nutrients:
            for nutrient in nutrients:
                text_representation += f"  → {nutrient}\n"
                deeper_nutrients = get_deeper_nutrients(nutrient)
                for deeper in deeper_nutrients:
                    text_representation += f"    → {deeper['nutrient']}\n"
        else:
            text_representation += "  No deeper dependencies.\n"

    # Generate tree graph image for deficiencies
    graph_img = generate_tree_graph(parameter_deficiencies)

    return render_template('response.html', text_representation=text_representation, graph_img=graph_img)


# Ensure generate_graph function is defined and works properly
def generate_text_representation(deficiencies, parameter_name):
    text_representation = f"{parameter_name}\n"
    
    for nutrient in deficiencies:
        text_representation += f"  → {nutrient}\n"
        deeper_nutrients = get_deeper_nutrients(nutrient)
        for deeper in deeper_nutrients:
            text_representation += f"    → {deeper['nutrient']}\n"
    print(f"Deficiencies List: {deficiencies}")


    return text_representation



#if __name__ == '__main__':
#    app.run(debug=True)
    
# Other imports and code...



if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Get the port from environment, default to 5000
    app.run(host='0.0.0.0', port=port)        # Bind to 0.0.0.0 and the port number
