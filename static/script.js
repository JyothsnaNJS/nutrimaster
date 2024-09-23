window.onload = function() {
    const resultsDiv = document.getElementById('results');
    
    // Get the stored comparison results from localStorage
    const results = JSON.parse(localStorage.getItem('comparisonResults'));
    
    // Check if results exist and are valid
    if (results && results.length > 0) {
        let output = '<table><tr><th>Parameter</th><th>Status</th><th>Value</th><th>Normal Range</th></tr>';
        
        // Loop through the results and generate the table rows
        results.forEach(param => {
            const statusClass = param.status.toLowerCase();
            output += `<tr class="${statusClass}">
                <td class="parameter-cell" onmouseover="showParameterDetails('${encodeURIComponent(param.parameter)}')">${param.parameter}</td>
                <td>${param.status}</td>
                <td>${param.value}</td>
                <td>${param.normal_range}</td>
            </tr>`;
        });

        output += '</table>';
        resultsDiv.innerHTML = output;  // Inject the table into the resultsDiv
    } else {
        resultsDiv.innerHTML = '<p>No concerning parameters found.</p>';  // Handle case where no data is found
    }
}


function showParameterDetails(parameter) {
    // Set the parameter name heading dynamically
    const parameterNameHeading = document.getElementById('parameter-name-heading');
    parameterNameHeading.textContent = `Details for ${decodeURIComponent(parameter)}`;

    // Fetch parameter details from the server
    fetch(`/parameter_details/${parameter}`)
        .then(response => response.json())
        .then(data => {
            const causesList = document.getElementById('causes-list');
            const effectsList = document.getElementById('effects-list');
            const avoidsList = document.getElementById('avoids-list');

            causesList.innerHTML = '';
            effectsList.innerHTML = '';
            avoidsList.innerHTML = '';

            data.causes.forEach(cause => {
                const li = document.createElement('li');
                li.textContent = cause;
                causesList.appendChild(li);
            });

            data.effects.forEach(effect => {
                const li = document.createElement('li');
                li.textContent = effect;
                effectsList.appendChild(li);
            });

            data.avoids.forEach(avoid => {
                const li = document.createElement('li');
                li.textContent = avoid;
                avoidsList.appendChild(li);
            });
        })
        .catch(error => console.error('Error fetching parameter details:', error));
}

function validateSelection() {
    const compulsoryCheckboxes = document.querySelectorAll('.compulsory');
    const errorMessage = document.getElementById('error-message');
    const nutrientSelection = {};

    // Initialize nutrient selection tracking
    compulsoryCheckboxes.forEach(checkbox => {
        const nutrient = checkbox.getAttribute('data-nutrient');
        if (!nutrientSelection[nutrient]) {
            nutrientSelection[nutrient] = false;
        }

        // If at least one checkbox for the nutrient is checked, mark as selected
        if (checkbox.checked) {
            nutrientSelection[nutrient] = true;
        }
    });

    // Check if all nutrients have at least one vegetable selected
    for (const nutrient in nutrientSelection) {
        if (!nutrientSelection[nutrient]) {
            errorMessage.style.display = 'block';
            return false; // Prevent form submission
        }
    }

    errorMessage.style.display = 'none';
    return true; // Allow form submission
}

