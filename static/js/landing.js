document.addEventListener('DOMContentLoaded', () => {
    const setupForm = document.getElementById('setup-form');
    const accessForm = document.getElementById('access-form');
    const tabpfnTokenInput = document.getElementById('tabpfn-token');
    const apiWrapperKeyInput = document.getElementById('api-wrapper-key');

    const setupResultDiv = document.getElementById('setup-result');
    const generatedApiKeyInput = document.getElementById('generated-api-key');
    const copyKeyButton = document.getElementById('copy-key-button');
    const proceedAfterSetupButton = document.getElementById('proceed-after-setup');

    const setupErrorDiv = document.getElementById('setup-error');
    const accessErrorDiv = document.getElementById('access-error');

    // Function to display errors
    const showError = (element, message) => {
        element.textContent = message;
        element.style.display = 'block';
    };

    // Function to clear errors
    const clearError = (element) => {
        element.textContent = '';
        element.style.display = 'none';
    };

    // --- Setup Form Logic ---    
    if (setupForm) {
        setupForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            clearError(setupErrorDiv);
            setupResultDiv.style.display = 'none'; // Hide previous result

            const tabpfnToken = tabpfnTokenInput.value.trim();
            if (!tabpfnToken) {
                showError(setupErrorDiv, 'Please enter your TabPFN Token.');
                return;
            }

            try {
                const response = await fetch('/api/v1/auth/setup', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ tabpfn_token: tabpfnToken }),
                });

                const data = await response.json();

                if (response.ok) {
                    const apiKey = data.api_key;
                    generatedApiKeyInput.value = apiKey;
                    sessionStorage.setItem('tabpfn_api_wrapper_key', apiKey); // Store key
                    setupResultDiv.style.display = 'block'; // Show result section
                    tabpfnTokenInput.value = ''; // Clear the input
                } else {
                    showError(setupErrorDiv, data.detail || 'Failed to generate API key. Please check your TabPFN Token.');
                }
            } catch (error) {
                console.error('Setup Error:', error);
                showError(setupErrorDiv, 'An error occurred while contacting the server.');
            }
        });
    }

    // --- Copy API Key Button Logic ---
    if (copyKeyButton) {
        copyKeyButton.addEventListener('click', () => {
            generatedApiKeyInput.select();
            generatedApiKeyInput.setSelectionRange(0, 99999); // For mobile devices
            try {
                navigator.clipboard.writeText(generatedApiKeyInput.value);
                // Optional: Give user feedback (e.g., change button text)
                copyKeyButton.textContent = 'Copied!';
                setTimeout(() => { copyKeyButton.textContent = 'Copy'; }, 2000);
            } catch (err) {
                console.error('Failed to copy API key: ', err);
                // Maybe show a small error message near the button
            }
        });
    }

    // --- Proceed After Setup Button Logic ---
    if (proceedAfterSetupButton) {
        proceedAfterSetupButton.addEventListener('click', () => {
            const apiKey = generatedApiKeyInput.value;
            if (apiKey) {
                sessionStorage.setItem('tabpfn_api_wrapper_key', apiKey);
                window.location.href = '/dashboard'; // Redirect to dashboard (needs route)
            } else {
                // Should not happen if button is only visible when key is generated
                console.error('API Key missing when trying to proceed.'); 
            }
        });
    }

    // --- Access Form Logic ---    
    if (accessForm) {
        accessForm.addEventListener('submit', (event) => {
            event.preventDefault();
            clearError(accessErrorDiv);

            const apiWrapperKey = apiWrapperKeyInput.value.trim();
            if (!apiWrapperKey) {
                showError(accessErrorDiv, 'Please enter your API Wrapper Key.');
                return;
            }

            // Store the key and redirect
            // TODO: Add validation step later? Call a simple authenticated endpoint?
            sessionStorage.setItem('tabpfn_api_wrapper_key', apiWrapperKey);
            window.location.href = '/dashboard'; // Redirect to dashboard (needs route)
        });
    }

}); 