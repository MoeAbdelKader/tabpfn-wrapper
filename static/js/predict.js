document.addEventListener('DOMContentLoaded', async () => {
    const predictForm = document.getElementById('predict-form');
    const modelSelect = document.getElementById('model-id');
    const csvFileInput = document.getElementById('predict-csv-file');
    const outputTypeSelect = document.getElementById('output-type');
    const submitButton = document.getElementById('predict-submit-button');

    const progressDiv = document.getElementById('predicting-progress');
    const resultDiv = document.getElementById('predict-result');
    const errorDiv = document.getElementById('predict-error');
    const resultPreviewDiv = document.getElementById('result-preview');
    const downloadLink = document.getElementById('download-results-link');

    // Store CSV data for combining with predictions later
    let csvHeaders = [];
    let csvData = [];

    const apiKey = sessionStorage.getItem('tabpfn_api_wrapper_key');
    if (!apiKey) {
        window.location.href = '/'; // Redirect if not logged in
        return;
    }

    const showError = (message) => {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        progressDiv.style.display = 'none';
        submitButton.disabled = false;
    };

    const clearMessages = () => {
        errorDiv.style.display = 'none';
        resultDiv.style.display = 'none';
        progressDiv.style.display = 'none';
        resultPreviewDiv.innerHTML = ''; // Clear previous preview
        downloadLink.style.display = 'none'; // Hide download link
        if (downloadLink.href.startsWith('blob:')) {
             URL.revokeObjectURL(downloadLink.href); // Clean up old blob URLs
        }
    };

    // Parse CSV function
    const parseCSV = (text) => {
        // Simple CSV parser - for more complex cases, consider using a library
        const rows = text.split('\n').filter(row => row.trim());
        const headers = rows[0].split(',').map(h => h.trim());
        
        const data = rows.slice(1).map(row => {
            const values = row.split(',').map(val => val.trim());
            return values;
        });
        
        return { headers, data };
    };

    // Handle CSV file selection to store data
    csvFileInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const { headers, data } = parseCSV(e.target.result);
                csvHeaders = headers;
                csvData = data;
                console.log('CSV parsed successfully:', { headers, rowCount: data.length });
            } catch (err) {
                console.error('Error parsing CSV:', err);
                showError('Error parsing CSV file. Please check the format.');
            }
        };
        reader.onerror = () => {
            showError('Error reading the CSV file.');
        };
        reader.readAsText(file);
    });

    // --- Load Models into Dropdown ---    
    try {
        const response = await fetch('/api/v1/models', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${apiKey}`,
                'Accept': 'application/json'
            }
        });

        if (response.status === 401) {
            sessionStorage.removeItem('tabpfn_api_wrapper_key');
            window.location.href = '/?error=invalid_key';
            return;
        }
        if (!response.ok) {
             const errorData = await response.json().catch(() => ({ detail: 'Failed to load models for selection.' }));
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        // Check if models are inside a 'models' property or directly in the response
        const models = data.models || data;
        
        modelSelect.innerHTML = ''; // Clear "Loading..."
        if (models && models.length > 0) {
            const defaultOption = document.createElement('option');
            defaultOption.value = "";
            defaultOption.textContent = "-- Select a Model --";
            defaultOption.disabled = true;
            defaultOption.selected = true;
            modelSelect.appendChild(defaultOption);

            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.internal_model_id;
                // Include more details if helpful
                option.textContent = `ID: ${model.internal_model_id} (Created: ${new Date(model.created_at).toLocaleDateString()})`;
                // Store task type if available in metadata (assuming classification for now)
                option.dataset.task = model.metadata?.task_type || 'classification'; 
                modelSelect.appendChild(option);
            });
        } else {
            const option = document.createElement('option');
            option.value = "";
            option.textContent = "-- No models trained yet --";
            modelSelect.appendChild(option);
            modelSelect.disabled = true;
            submitButton.disabled = true; // Disable submission if no models
        }

    } catch (error) {
        console.error('Error loading models:', error);
        showError(`Failed to load models: ${error.message}`);
        modelSelect.innerHTML = '<option value="">-- Error loading models --</option>';
        modelSelect.disabled = true;
        submitButton.disabled = true;
    }
    
    // Create HTML table from data and predictions
    const createTable = (headers, data, predictions, outputType) => {
        const table = document.createElement('table');
        table.className = 'prediction-table';
        
        // Create header row
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        
        // Add original headers
        headers.forEach(header => {
            const th = document.createElement('th');
            th.textContent = header;
            headerRow.appendChild(th);
        });
        
        // Add prediction header
        const predHeader = document.createElement('th');
        predHeader.textContent = outputType === 'probabilities' ? 'Probabilities' : 'Prediction';
        predHeader.className = 'prediction-column';
        headerRow.appendChild(predHeader);
        
        thead.appendChild(headerRow);
        table.appendChild(thead);
        
        // Create table body
        const tbody = document.createElement('tbody');
        
        // Add data rows
        data.forEach((row, index) => {
            if (index >= predictions.length) return; // Skip if no prediction
            
            const tr = document.createElement('tr');
            
            // Add original data cells
            row.forEach(cell => {
                const td = document.createElement('td');
                td.textContent = cell;
                tr.appendChild(td);
            });
            
            // Add prediction cell
            const predCell = document.createElement('td');
            predCell.className = 'prediction-column';
            
            // Format prediction based on type
            if (outputType === 'probabilities' && Array.isArray(predictions[index])) {
                // For probabilities, show formatted percentages
                const probs = predictions[index]
                    .map((p, i) => `Class ${i}: ${(p * 100).toFixed(2)}%`)
                    .join('<br>');
                predCell.innerHTML = probs;
            } else {
                // For standard predictions, show the value
                predCell.textContent = JSON.stringify(predictions[index]);
            }
            
            tr.appendChild(predCell);
            tbody.appendChild(tr);
        });
        
        table.appendChild(tbody);
        return table;
    };

    // Format CSV for download
    const formatCSVForDownload = (headers, data, predictions, outputType) => {
        // Create header row with original headers + prediction
        const headerRow = [...headers, outputType === 'probabilities' ? 'Probabilities' : 'Prediction'];
        
        // Create data rows with original data + prediction
        const rows = data.map((row, index) => {
            if (index >= predictions.length) return row; // Skip if no prediction
            
            // For probabilities, we need to handle the array format
            let predictionValue;
            if (outputType === 'probabilities' && Array.isArray(predictions[index])) {
                predictionValue = JSON.stringify(predictions[index]);
            } else {
                predictionValue = JSON.stringify(predictions[index]);
            }
            
            return [...row, predictionValue];
        });
        
        // Combine into CSV string
        const csvRows = [headerRow, ...rows];
        return csvRows.map(row => row.join(',')).join('\n');
    };

    // --- Form Submission Logic ---    
    predictForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        clearMessages();

        const selectedModelOption = modelSelect.options[modelSelect.selectedIndex];
        const modelId = selectedModelOption.value;
        const taskType = selectedModelOption.dataset.task || 'classification'; // Get task from data-* attribute
        const file = csvFileInput.files[0];
        const outputType = outputTypeSelect.value;

        if (!modelId || !file) {
            showError('Please select a model and a prediction CSV file.');
            return;
        }

        // Check if CSV was successfully parsed
        if (csvHeaders.length === 0 || csvData.length === 0) {
            showError('Could not parse the CSV file or CSV is empty.');
            return;
        }

        submitButton.disabled = true;
        progressDiv.style.display = 'block';

        const formData = new FormData();
        formData.append('file', file);
        
        // API expects task and output_type as query params
        const apiUrl = `/api/v1/models/${modelId}/predict/upload?task=${encodeURIComponent(taskType)}&output_type=${encodeURIComponent(outputType)}`;

        try {
            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${apiKey}`,
                    'Accept': 'application/json' // Expect JSON response containing predictions
                },
                body: formData,
            });

            // Predictions might be returned directly as JSON array
            const responseData = await response.json(); 

            if (response.ok) {
                resultDiv.style.display = 'block';
                
                // Check all possible locations where predictions might be in the response
                const predictions = Array.isArray(responseData) ? responseData : 
                                   responseData.predictions || 
                                   responseData.data || 
                                   responseData.results || 
                                   [];

                // Log for debugging
                console.log('API Response:', responseData);
                console.log('Extracted predictions:', predictions);

                if (!Array.isArray(predictions)) {
                    throw new Error('Unexpected response format. Could not extract predictions array.');
                }
                
                // Generate the table with results
                resultPreviewDiv.innerHTML = '<h4>Results:</h4>';
                const table = createTable(csvHeaders, csvData, predictions, outputType);
                resultPreviewDiv.appendChild(table);

                // Create a Blob and URL for downloading combined results as CSV
                const csvContent = formatCSVForDownload(csvHeaders, csvData, predictions, outputType);
                const blob = new Blob([csvContent], { type: 'text/csv' });
                downloadLink.href = URL.createObjectURL(blob);
                downloadLink.download = `predictions_${modelId}_${new Date().toISOString()}.csv`;
                downloadLink.style.display = 'inline-block';

            } else {
                 if (response.status === 401) {
                    sessionStorage.removeItem('tabpfn_api_wrapper_key');
                    window.location.href = '/'; // Redirect if unauthorized
                } else {
                     showError(responseData.detail || 'An error occurred during prediction.');
                }
            }
        } catch (error) {
            console.error('Prediction Error:', error);
            showError(error.message || 'An unexpected error occurred.');
        } finally {
            progressDiv.style.display = 'none';
            submitButton.disabled = false;
        }
    });
}); 