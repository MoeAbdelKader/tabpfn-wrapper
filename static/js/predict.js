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
            const data = await response.json(); 

            if (response.ok) {
                resultDiv.style.display = 'block';
                
                // Display a preview (e.g., first 10 predictions)
                let previewHtml = '<h4>Preview:</h4><pre>';
                previewHtml += JSON.stringify(data.slice(0, 10), null, 2);
                 if (data.length > 10) previewHtml += '\n... (more results truncated)';
                previewHtml += '</pre>';
                resultPreviewDiv.innerHTML = previewHtml;

                // Create a Blob and URL for downloading full results as CSV
                // Assuming `data` is an array of predictions/probabilities
                let csvContent = "data:text/csv;charset=utf-8,";
                // Simple conversion: each item on a new line. Adapt if data structure is complex.
                // For probabilities, you might want headers like 'prob_class_0,prob_class_1,...'
                csvContent += data.map(row => JSON.stringify(row)).join("\r\n"); 
                
                const blob = new Blob([csvContent.substring(csvContent.indexOf(',') + 1)], { type: 'text/csv' });
                downloadLink.href = URL.createObjectURL(blob);
                downloadLink.download = `predictions_${modelId}_${new Date().toISOString()}.csv`;
                downloadLink.style.display = 'inline-block';

            } else {
                 if (response.status === 401) {
                    sessionStorage.removeItem('tabpfn_api_wrapper_key');
                    window.location.href = '/'; // Redirect if unauthorized
                } else {
                     showError(data.detail || 'An error occurred during prediction.');
                }
            }
        } catch (error) {
            console.error('Prediction Error:', error);
            showError('An unexpected error occurred.');
        } finally {
            progressDiv.style.display = 'none';
            submitButton.disabled = false;
        }
    });
}); 