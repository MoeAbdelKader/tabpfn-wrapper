document.addEventListener('DOMContentLoaded', () => {
    const trainForm = document.getElementById('train-form');
    const csvFileInput = document.getElementById('train-csv-file');
    const targetColumnSelect = document.getElementById('target-column');
    const taskTypeSelect = document.getElementById('task-type');
    const submitButton = document.getElementById('train-submit-button');
    
    const progressDiv = document.getElementById('training-progress');
    const resultDiv = document.getElementById('train-result');
    const errorDiv = document.getElementById('train-error');
    const resultModelId = document.getElementById('result-model-id');

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
    };

    // --- Populate Target Column Dropdown ---    
    csvFileInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (!file) {
            targetColumnSelect.innerHTML = '<option value="" selected>-- Select CSV file first --</option>';
            targetColumnSelect.disabled = true;
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            const text = e.target.result;
            const firstLine = text.split('\n')[0].trim();
            // Basic CSV header parsing (commas, handles simple quotes)
            const headers = firstLine.match(/(\"(?:\\"|[^\"])*\"|[^,]+)/g)?.map(h => h.replace(/^"|"$/g, '').replace(/\"\"/g, '"')) || [];

            targetColumnSelect.innerHTML = ''; // Clear previous options
            if (headers.length > 0) {
                headers.forEach(header => {
                    const option = document.createElement('option');
                    option.value = header;
                    option.textContent = header;
                    targetColumnSelect.appendChild(option);
                });
                targetColumnSelect.disabled = false;
            } else {
                targetColumnSelect.innerHTML = '<option value="" selected>-- Could not read headers --</option>';
                targetColumnSelect.disabled = true;
                showError('Could not read headers from the CSV file.');
            }
        };
        reader.onerror = () => {
            targetColumnSelect.innerHTML = '<option value="" selected>-- Error reading file --</option>';
            targetColumnSelect.disabled = true;
            showError('Error reading the CSV file.');
        };
        reader.readAsText(file);
    });

    // --- Form Submission Logic ---    
    trainForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        clearMessages();

        const file = csvFileInput.files[0];
        const targetColumn = targetColumnSelect.value;
        const taskType = taskTypeSelect.value;

        if (!file || !targetColumn) {
            showError('Please select a CSV file and a target column.');
            return;
        }

        submitButton.disabled = true;
        progressDiv.style.display = 'block';

        const formData = new FormData();
        formData.append('file', file);
        // Add target_column and task_type as query parameters or form data parts
        // The API endpoint /api/v1/models/fit/upload expects target_column as a query param
        const apiUrl = `/api/v1/models/fit/upload?target_column=${encodeURIComponent(targetColumn)}&task=${encodeURIComponent(taskType)}`;

        try {
            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${apiKey}`,
                    // 'Content-Type': 'multipart/form-data' is set automatically by fetch for FormData
                    'Accept': 'application/json'
                },
                body: formData,
            });

            const data = await response.json();

            if (response.ok) {
                resultModelId.textContent = data.internal_model_id;
                resultDiv.style.display = 'block';
                trainForm.reset(); // Clear the form
                targetColumnSelect.innerHTML = '<option value="" selected>-- Select CSV file first --</option>';
                targetColumnSelect.disabled = true;
            } else {
                 if (response.status === 401) {
                    sessionStorage.removeItem('tabpfn_api_wrapper_key');
                    window.location.href = '/'; // Redirect if unauthorized
                } else {
                     showError(data.detail || 'An error occurred during training.');
                }
            }
        } catch (error) {
            console.error('Training Error:', error);
            showError('An unexpected error occurred.');
        } finally {
            progressDiv.style.display = 'none';
            submitButton.disabled = false;
        }
    });
}); 