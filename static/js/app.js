document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const globalSettingsForm = document.getElementById('globalSettingsForm');
    const sheetList = document.getElementById('sheetList');
    const emptyState = document.getElementById('emptyState');
    const addSheetBtn = document.getElementById('addSheetBtn');
    const sheetFormSection = document.getElementById('sheetFormSection');
    const sheetConfigForm = document.getElementById('sheetConfigForm');
    const cancelBtn = document.getElementById('cancelBtn');
    const formTitle = document.getElementById('formTitle');
    const submitBtnText = document.getElementById('submitBtnText');
    const statusMessage = document.getElementById('statusMessage');
    const loadingIndicator = document.getElementById('loadingIndicator');
    
    // Current sheet configurations
    let sheetConfigs = [];
    let globalSettings = {};
    let currentEditingId = null;
    let eventSource = null;
    
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
    
    function showNotification(message) {
        const notificationArea = document.getElementById('notificationArea');
        const notificationMessage = document.getElementById('notificationMessage');
        
        // Set message
        notificationMessage.textContent = message;
        
        // Show notification
        notificationArea.classList.remove('hidden');
        
        // Hide notification after animation completes
        setTimeout(() => {
            notificationArea.classList.add('hidden');
        }, 3000); // Match fadeOut animation + delay
    }
    
    // Function to toggle form visibility
    function toggleForm(show = true, isEdit = false) {
        if (show) {
            sheetFormSection.classList.remove('hidden');
            formTitle.textContent = isEdit ? 'Edit Sheet Configuration' : 'Add Sheet Configuration';
            submitBtnText.textContent = isEdit ? 'Update Configuration' : 'Add Configuration';
        } else {
            sheetFormSection.classList.add('hidden');
            // Reset form fields
            sheetConfigForm.reset();
            document.getElementById('sheet_id').value = '';
            currentEditingId = null;
        }
    }
    
    // Function to check if the sheet list is empty
    function checkEmptyState() {
        if (sheetConfigs.length === 0) {
            emptyState.classList.remove('hidden');
        } else {
            emptyState.classList.add('hidden');
        }
    }
    
    // Function to populate sheet list
    function populateSheetList() {
        // Clear current list
        const items = sheetList.querySelectorAll('.sheet-item');
        items.forEach(item => item.remove());
        
        // Add new items
        sheetConfigs.forEach(config => {
            const template = document.getElementById('sheetItemTemplate');
            const clone = document.importNode(template.content, true);
            
            const sheetItem = clone.querySelector('.sheet-item');
            sheetItem.dataset.id = config.sheet_id;
            
            const sheetName = clone.querySelector('.sheet-name');
            sheetName.textContent = config.sheet_name;
            
            const sheetDetails = clone.querySelector('.sheet-details');
            sheetDetails.textContent = `Dana: ${config.dana_used} • SpreadsheetID: ${config.spreadsheet_ids.substring(0, 15)}...`;
            
            const editBtn = clone.querySelector('.edit-btn');
            editBtn.addEventListener('click', () => editSheetConfig(config.sheet_id));
            
            const deleteBtn = clone.querySelector('.delete-btn');
            deleteBtn.addEventListener('click', () => confirmDeleteSheetConfig(config.sheet_id, config.sheet_name));
            
            sheetList.insertBefore(clone, emptyState);
        });
        
        checkEmptyState();
    }
    
    // Function to load all configurations
    async function loadConfigurations() {
        try {
            showLoading();
            const response = await fetch('/get_config', {
                headers: {
                    'X-UI-Request': 'true'  // Add this custom header to identify UI requests
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            hideLoading();
            
            // Update global variables
            globalSettings = data.global_settings || {};
            sheetConfigs = data.sheet_configs || [];
            
            // Populate the UI
            document.getElementById('transfer_destination').value = globalSettings.transfer_destination || 'LAYER 1';
            populateSheetList();
            
            showStatus('Configurations loaded successfully');
        } catch (error) {
            hideLoading();
            console.error('Error loading configurations:', error);
            showStatus('Failed to load configurations: ' + error.message, true);
        }
    }    
    
    // Function to edit a sheet configuration
    function editSheetConfig(sheetId) {
        const config = sheetConfigs.find(c => c.sheet_id === sheetId);
        if (!config) return;
        
        // Populate form fields
        document.getElementById('sheet_id').value = config.sheet_id;
        document.getElementById('dana_used').value = config.dana_used || '';
        document.getElementById('sheet_name').value = config.sheet_name || '';
        document.getElementById('spreadsheet_ids').value = config.spreadsheet_ids || '';
        document.getElementById('bank_destination').value = config.bank_destination || '';
        document.getElementById('bank_name_destination').value = config.bank_name_destination || '';
        
        // Show form in edit mode
        currentEditingId = sheetId;
        toggleForm(true, true);
    }
    
    // Function to confirm deletion of a sheet configuration
    function confirmDeleteSheetConfig(sheetId, sheetName) {
        const confirmDelete = confirm(`Are you sure you want to delete the configuration for "${sheetName}"?`);
        if (confirmDelete) {
            deleteSheetConfig(sheetId);
        }
    }
    
    // Function to delete a sheet configuration
    async function deleteSheetConfig(sheetId) {
        try {
            showLoading();
            const response = await fetch(`/delete_sheet_config/${sheetId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            hideLoading();
            
            // Remove from the list
            sheetConfigs = sheetConfigs.filter(c => c.sheet_id !== sheetId);
            populateSheetList();
            
            showStatus('Sheet configuration deleted successfully');
        } catch (error) {
            hideLoading();
            console.error('Error deleting sheet configuration:', error);
            showStatus('Failed to delete configuration: ' + error.message, true);
        }
    }
    
    // Function to submit global settings
    async function submitGlobalSettings(event) {
        event.preventDefault();
        
        // Get form data
        const formData = new FormData(globalSettingsForm);
        const formDataObj = {};
        formData.forEach((value, key) => {
            formDataObj[key] = value;
        });
        
        try {
            showLoading();
            
            // Send the update request
            const response = await fetch('/update_global_settings', {
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
            
            // Update global settings
            globalSettings = data.current_settings;
            
            showStatus('Global settings updated successfully');
        } catch (error) {
            hideLoading();
            console.error('Error updating global settings:', error);
            showStatus('Failed to update global settings: ' + error.message, true);
        }
    }
    
    // Function to submit sheet configuration
    async function submitSheetConfig(event) {
        event.preventDefault();
        
        // Get form data
        const formData = new FormData(sheetConfigForm);
        const formDataObj = {};
        formData.forEach((value, key) => {
            formDataObj[key] = value;
        });
        
        const isEdit = !!formDataObj.sheet_id;
        const url = isEdit 
            ? `/update_sheet_config/${formDataObj.sheet_id}` 
            : '/add_sheet_config';
        const method = isEdit ? 'PUT' : 'POST';
        
        try {
            showLoading();
            
            // Send the request
            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formDataObj)
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            hideLoading();
            
            // Update the list
            if (isEdit) {
                sheetConfigs = sheetConfigs.map(c => 
                    c.sheet_id === formDataObj.sheet_id ? data.current_config : c
                );
            } else {
                sheetConfigs.push(data.config);
            }
            
            populateSheetList();
            toggleForm(false);
            
            showStatus(`Sheet configuration ${isEdit ? 'updated' : 'added'} successfully`);
        } catch (error) {
            hideLoading();
            console.error(`Error ${isEdit ? 'updating' : 'adding'} sheet configuration:`, error);
            showStatus(`Failed to ${isEdit ? 'update' : 'add'} configuration: ${error.message}`, true);
        }
    }

    // Function to setup Server-Sent Events connection
    function setupSSEConnection() {
        // Close any existing connection
        if (eventSource) {
            eventSource.close();
        }

        // Create a new connection
        eventSource = new EventSource('/sse');

        // Connection opened
        eventSource.addEventListener('open', function(e) {
            console.log('SSE connection established');
        });

        // Listen for messages
        eventSource.addEventListener('message', function(e) {
            try {
                const data = JSON.parse(e.data);
                
                // Handle different event types
                if (data.type === 'config_updated') {
                    console.log('Configuration updated, refreshing data...');
                    loadConfigurations();
                    showNotification('Configuration updated automatically');
                } else if (data.type === 'data_processed') {
                    console.log('Data processed for sheet:', data.sheet_name);
                    showNotification(`Data processed for sheet: ${data.sheet_name}`);
                } else if (data.type === 'connected') {
                    console.log('Connected to update stream');
                }
            } catch (error) {
                console.error('Error processing SSE message:', error);
            }
        });        

        // Error handling
        eventSource.addEventListener('error', function(e) {
            console.error('SSE connection error:', e);
            
            // Try to reconnect after a delay
            setTimeout(() => {
                if (eventSource.readyState === EventSource.CLOSED) {
                    setupSSEConnection();
                }
            }, 5000);
        });
    }
    
    // Event listeners
    globalSettingsForm.addEventListener('submit', submitGlobalSettings);
    sheetConfigForm.addEventListener('submit', submitSheetConfig);
    addSheetBtn.addEventListener('click', () => toggleForm(true, false));
    cancelBtn.addEventListener('click', () => toggleForm(false));
    
    // Load configurations when the page loads
    loadConfigurations();
    
    // Setup SSE connection
    setupSSEConnection();
    
    // Reconnect if the page becomes visible again after being in background
    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'visible' && (!eventSource || eventSource.readyState === EventSource.CLOSED)) {
            setupSSEConnection();
        }
    });
});