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

function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];
    const fileStatus = document.getElementById('fileStatus');

    if (!file) {
        alert('Please select a file to upload.');
        return;
    }

    if (file.size > 5 * 1024 * 1024) {
        alert('File size exceeds 5MB limit. Please upload a smaller file.');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    // Display file name and upload status
    fileStatus.innerHTML = `<p>Uploading: ${file.name}</p>`;

    fetch('/upload', {
        method: 'POST',
        body: formData,
    })
    .then(response => {
        // Check if the response is in JSON format
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.indexOf('application/json') !== -1) {
            return response.json();
        } else {
            return response.text().then(text => {
                throw new Error(`Unexpected response: ${text}`);
            });
        }
    })
    .then(data => {
        localStorage.setItem('comparisonResults', JSON.stringify(data));
        window.location.href = '/response';
    })
    .catch(error => {
        console.error('Error:', error);
        fileStatus.innerHTML = `<p style="color: red;">An error occurred: ${error.message}</p>`;
    });
}
