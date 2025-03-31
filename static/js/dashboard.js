document.addEventListener('DOMContentLoaded', async () => {
    const modelsListDiv = document.getElementById('models-list');
    const modelsErrorDiv = document.getElementById('models-error');

    const apiKey = sessionStorage.getItem('tabpfn_api_wrapper_key');

    if (!apiKey) {
        // If no API key, redirect back to landing page
        window.location.href = '/'; 
        return;
    }

    const showError = (message) => {
        modelsErrorDiv.textContent = message;
        modelsErrorDiv.style.display = 'block';
        modelsListDiv.innerHTML = ''; // Clear loading message
    };

    try {
        const response = await fetch('/api/v1/models', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${apiKey}`,
                'Accept': 'application/json' // Ensure we expect JSON
            }
        });

        if (response.status === 401) {
            // Unauthorized - likely bad key, redirect to landing
            sessionStorage.removeItem('tabpfn_api_wrapper_key');
            window.location.href = '/?error=invalid_key'; // Optional: add query param
            return;
        }

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch models. Server returned an error.' }));
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        // Check if models are inside a 'models' property or directly in the response
        const models = data.models || data;

        modelsListDiv.innerHTML = ''; // Clear loading message

        if (models && models.length > 0) {
            const ul = document.createElement('ul');
            models.forEach(model => {
                const li = document.createElement('li');
                // Display relevant info - adapt based on actual API response structure
                // Assuming the response is a list of objects like: 
                // { internal_model_id: "...", train_set_uid: "...", created_at: "...", metadata: {...} }
                li.textContent = `Model ID: ${model.internal_model_id} (Created: ${new Date(model.created_at).toLocaleString()})`;
                // Add delete button later if needed
                ul.appendChild(li);
            });
            modelsListDiv.appendChild(ul);
        } else {
            modelsListDiv.innerHTML = '<p>You haven't trained any models yet.</p>';
        }

    } catch (error) {
        console.error('Error fetching models:', error);
        showError(error.message || 'An unexpected error occurred while fetching models.');
    }
}); 