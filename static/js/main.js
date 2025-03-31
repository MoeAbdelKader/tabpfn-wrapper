// TabPFN API Wrapper - Common JS Utilities

// Check if user is authenticated (has an API key in sessionStorage)
function isAuthenticated() {
    return !!sessionStorage.getItem('tabpfn_api_wrapper_key');
}

// Redirect to landing page if user is not authenticated
function requireAuth() {
    if (!isAuthenticated()) {
        window.location.href = '/';
        return false;
    }
    return true;
}

// Get the API key from sessionStorage
function getApiKey() {
    return sessionStorage.getItem('tabpfn_api_wrapper_key');
}

// Logout function - clear sessionStorage and redirect to landing
function logout() {
    sessionStorage.removeItem('tabpfn_api_wrapper_key');
    window.location.href = '/';
}

// Add a logout button to the header if user is authenticated
document.addEventListener('DOMContentLoaded', () => {
    // Check auth on every page load
    if (window.location.pathname !== '/' && !isAuthenticated()) {
        window.location.href = '/';
        return;
    }
    
    // Add logout button to header
    const header = document.querySelector('header');
    if (header && isAuthenticated()) {
        // Only add logout if on a page other than landing
        if (window.location.pathname !== '/') {
            const logoutBtn = document.createElement('button');
            logoutBtn.textContent = 'Logout';
            logoutBtn.className = 'logout-btn';
            
            // Add a subtle animation on hover
            logoutBtn.onmouseenter = function() {
                this.style.transform = 'translateY(-1px)';
            };
            logoutBtn.onmouseleave = function() {
                this.style.transform = 'translateY(0)';
            };
            
            logoutBtn.onclick = function() {
                // Simple fade-out animation before logout
                this.style.opacity = '0';
                this.style.transform = 'translateY(-5px)';
                
                // Small delay for animation to complete
                setTimeout(logout, 200);
            };
            
            header.appendChild(logoutBtn);
        }
    }
    
    // Apply subtle fade-in to all containers on page load
    const containers = document.querySelectorAll('.container');
    containers.forEach((container, index) => {
        // Stagger the animations slightly
        container.style.animation = `fadeIn 0.3s ease-out ${index * 0.1}s both`;
    });
}); 