document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const configForm = document.getElementById('configForm');
    const loadBtn = document.getElementById('loadBtn');
    const statusMessage = document.getElementById('statusMessage');
    const currentConfig = document.getElementById('currentConfig');
    const loadingIndicator = document.getElementById('loadingIndicator');
    
    // Function to show loading state
    function showLoading() {
        loadingIndicator.classList.remove('hidden');
    }
    
    // Function to hide loading state
    function hideLoading() {
        loadingIndicator.classList.add('hidden');
    }
    
    // Function to show status message
    function showStatus(message, isError = false) {
        statusMessage.textContent = message;
        statusMessage.className = 'status-message';
        if (isError) {
            statusMessage.classList.add('error');
        } else {
            statusMessage.classList.add('success');
        }
    }
    
    // Function to display configuration
    function displayConfig(config) {
        // Format the JSON with indentation for better readability
        const formattedConfig = JSON.stringify(config, null, 2);
        currentConfig.textContent = formattedConfig;
    }
    
    // Function to load current configuration
    async function loadCurrentConfig() {
        try {
            showLoading();
            // Send a request to get current config (assuming we add this endpoint)
            const response = await fetch('/get_config');
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            hideLoading();
            
            // Display the configuration
            displayConfig(data.config);
            showStatus('Current configuration loaded successfully');
            
            // Fill the form with current values
            document.getElementById('dana_used').value = data.config.dana_used || '';
            document.getElementById('sheet_name').value = data.config.sheet_name || '';
            document.getElementById('spreadsheet_ids').value = data.config.spreadsheet_ids || '';
            document.getElementById('bank_destination').value = data.config.bank_destination || '';
            document.getElementById('bank_name_destination').value = data.config.bank_name_destination || '';
            
        } catch (error) {
            hideLoading();
            console.error('Error loading configuration:', error);
            showStatus('Failed to load configuration: ' + error.message, true);
        }
    }
    
    // Function to submit the form
    async function submitForm(event) {
        event.preventDefault();
        
        // Get form data
        const formData = new FormData(configForm);
        const formDataObj = {};
        formData.forEach((value, key) => {
            formDataObj[key] = value;
        });
        
        try {
            showLoading();
            
            // Send the update request
            const response = await fetch('/update_config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formDataObj)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            hideLoading();
            
            // Display success message and updated config
            showStatus('Configuration updated successfully!');
            displayConfig(data.current_config);
            
        } catch (error) {
            hideLoading();
            console.error('Error updating configuration:', error);
            showStatus('Failed to update configuration: ' + error.message, true);
        }
    }
    
    // Event listeners
    configForm.addEventListener('submit', submitForm);
    loadBtn.addEventListener('click', loadCurrentConfig);
    
    // Load the current configuration when the page loads
    loadCurrentConfig();
});