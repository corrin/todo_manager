// tasks.js - JavaScript functionality for the tasks page

document.addEventListener('DOMContentLoaded', function() {
    // Initialize components
    initializeFilter();
    initializeSortableLists();
    initializeTaskDetails();
    initializeTaskCompletionForms();
});

/**
 * Initialize task completion forms to use AJAX submission
 */
function initializeTaskCompletionForms() {
    const taskForms = document.querySelectorAll('form[action*="/tasks/"][action*="/status"]');
    
    taskForms.forEach(form => {
        form.addEventListener('submit', function(event) {
            event.preventDefault();
            
            // Show a subtle loading indicator on the button
            const button = form.querySelector('button');
            const originalButtonHtml = button.innerHTML;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            button.disabled = true;
            
            // Hide any previous errors
            hideErrorMessage();
            
            // Submit form via AJAX
            const formData = new FormData(form);
            
            // Get the form's action URL directly from the form element
            const actionUrl = form.getAttribute('action');
            
            // Submit the form via AJAX to the exact URL specified in the form
            fetch(actionUrl, {
                method: 'POST',
                body: formData,
                credentials: 'same-origin'
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Server returned ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                // Update UI to show task completion
                const taskItem = form.closest('.task-item');
                if (taskItem) {
                    taskItem.classList.add('completed');
                }
                // Restore button
                button.innerHTML = originalButtonHtml;
                button.disabled = false;
            })
            .catch(error => {
                console.error('Error updating task status:', error);
                // Show error and restore button
                button.innerHTML = originalButtonHtml;
                button.disabled = false;
                showErrorMessage('Failed to update task. Please try again.');
            });
            const taskId = form.action.split('/').pop().split('?')[0];
            
            // Use the new route instead of the old one
            const updateUrl = `/tasks/${taskId}/update_status`;
            
            fetch(updateUrl, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => {
                // Reset button state
                button.innerHTML = originalButtonHtml;
                button.disabled = false;
                
                if (!response.ok) {
                    // For error responses, try to get error details as JSON
                    return response.json()
                        .then(errorData => {
                            // Use error message from JSON if available
                            throw new Error(errorData.message || 'Failed to update task status');
                        })
                        .catch(jsonError => {
                            // If JSON parsing fails, use a generic error message
                            throw new Error('Failed to update task status');
                        });
                }
                
                // For successful responses, parse as JSON
                return response.json();
            })
            .then(data => {
                // If we got here, the request was successful and we have data
                // Show success by reloading the page
                window.location.reload();
            })
            .catch(error => {
                // Show error message to user
                showErrorMessage(error.message || 'Failed to update task status. Please try again.');
                console.error('Task update error:', error);
            });
        });
    });
}

/**
 * Show error message in the error container
 */
function showErrorMessage(message) {
    const errorContainer = document.getElementById('error-container');
    const errorMessage = document.getElementById('error-message');
    
    if (errorContainer && errorMessage) {
        errorMessage.textContent = message;
        errorContainer.style.display = 'block';
        
        // Scroll to the error message
        errorContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

/**
 * Hide the error message container
 */
function hideErrorMessage() {
    const errorContainer = document.getElementById('error-container');
    
    if (errorContainer) {
        errorContainer.style.display = 'none';
    }
}

/**
 * Initialize the filter functionality
 * As the user types in the filter input, only matching tasks will be shown
 */
function initializeFilter() {
    // Create filter input element
    const filterContainer = document.createElement('div');
    filterContainer.className = 'mb-3';
    filterContainer.innerHTML = `
        <div class="input-group">
            <span class="input-group-text"><i class="fas fa-search"></i></span>
            <input type="text" id="taskFilter" class="form-control" placeholder="Filter tasks...">
            <button class="btn btn-outline-secondary" type="button" id="clearFilter">Clear</button>
        </div>
    `;
    
    // Insert filter at the top of both task list containers
    const containers = [
        document.getElementById('prioritized-container'),
        document.getElementById('unprioritized-container'),
        document.getElementById('completed-container')
    ];
    
    containers.forEach(container => {
        if (container) {
            const filterClone = filterContainer.cloneNode(true);
            container.insertBefore(filterClone, container.firstChild);
            
            // Add event listener for filter input
            const filterInput = filterClone.querySelector('#taskFilter');
            filterInput.addEventListener('input', function() {
                filterTasks(container, this.value);
            });
            
            // Add event listener for clear button
            const clearButton = filterClone.querySelector('#clearFilter');
            clearButton.addEventListener('click', function() {
                filterInput.value = '';
                filterTasks(container, '');
            });
        }
    });
}

/**
 * Filter tasks based on input text
 */
function filterTasks(container, filterText) {
    const lowercaseFilter = filterText.toLowerCase();
    const taskItems = container.querySelectorAll('.list-group-item');
    
    taskItems.forEach(item => {
        // Get all text content from the item to search through
        const taskContent = item.textContent.toLowerCase();
        if (taskContent.includes(lowercaseFilter)) {
            item.style.display = '';
        } else {
            item.style.display = 'none';
        }
    });
}

/**
 * Initialize Sortable.js for both task lists
 */
function initializeSortableLists() {
    // Load Sortable.js from CDN if not already loaded
    if (typeof Sortable === 'undefined') {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js';
        script.onload = function() {
            createSortableLists();
        };
        document.head.appendChild(script);
    } else {
        createSortableLists();
    }
}

/**
 * Create Sortable instances for both task lists
 */
/**
 * Create Sortable instances for all task lists
 */
function createSortableLists() {
    const prioritizedList = document.getElementById('prioritized-tasks');
    const unprioritizedList = document.getElementById('unprioritized-tasks');
    const completedList = document.getElementById('completed-tasks');
    
    if (!prioritizedList || !unprioritizedList || !completedList) {
        return;
    }
    
    // Helper function to determine destination list type
    function getDestinationFromId(id) {
        if (id === 'prioritized-tasks') return 'prioritized';
        if (id === 'unprioritized-tasks') return 'unprioritized';
        if (id === 'completed-tasks') return 'completed';
        return 'unprioritized'; // default
    }
    
    // Create sortable for prioritized tasks
    Sortable.create(prioritizedList, {
        animation: 150,
        ghostClass: 'sortable-ghost',
        chosenClass: 'sortable-chosen',
        dragClass: 'sortable-drag',
        group: 'tasks', // Shared group allows dragging between lists
        onEnd: function(evt) {
            // Check if the task was moved to a different list
            if (evt.from !== evt.to) {
                const taskId = evt.item.getAttribute('data-task-id');
                const destination = getDestinationFromId(evt.to.id);
                
                // Move task between lists
                moveTaskBetweenLists(taskId, destination, evt.newIndex);
            } else {
                // Task was reordered within the same list
                updateTaskOrder(prioritizedList, 'prioritized');
            }
        }
    });
    
    // Create sortable for unprioritized tasks
    Sortable.create(unprioritizedList, {
        animation: 150,
        ghostClass: 'sortable-ghost',
        chosenClass: 'sortable-chosen',
        dragClass: 'sortable-drag',
        group: 'tasks', // Shared group allows dragging between lists
        onEnd: function(evt) {
            // Check if the task was moved to a different list
            if (evt.from !== evt.to) {
                const taskId = evt.item.getAttribute('data-task-id');
                const destination = getDestinationFromId(evt.to.id);
                
                // Move task between lists
                moveTaskBetweenLists(taskId, destination, evt.newIndex);
            } else {
                // Task was reordered within the same list
                updateTaskOrder(unprioritizedList, 'unprioritized');
            }
        }
    });
    
    // Create sortable for completed tasks
    Sortable.create(completedList, {
        animation: 150,
        ghostClass: 'sortable-ghost',
        chosenClass: 'sortable-chosen',
        dragClass: 'sortable-drag',
        group: 'tasks', // Shared group allows dragging between lists
        onEnd: function(evt) {
            // Check if the task was moved to a different list
            if (evt.from !== evt.to) {
                const taskId = evt.item.getAttribute('data-task-id');
                const destination = getDestinationFromId(evt.to.id);
                
                // Move task between lists
                moveTaskBetweenLists(taskId, destination, evt.newIndex);
            } else {
                // Task was reordered within the same list
                updateTaskOrder(completedList, 'completed');
            }
        }
    });
}

/**
 * Move a task between prioritized, unprioritized, and completed lists
 */
function moveTaskBetweenLists(taskId, destination, position) {
    // Create a FormData object to send the task movement data
    const formData = new FormData();
    formData.append('task_id', taskId);
    formData.append('destination', destination);
    formData.append('position', position);
    
    // Send the movement data to the server
    fetch('/tasks/move_task', {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to move task');
        }
        return response.json();
    })
    .then(data => {
        console.log('Task moved successfully:', data);
    })
    .catch(error => {
        console.error('Error moving task:', error);
        // Consider showing a user-friendly error message
    });
}

/**
 * Update task order within a list
 */
function updateTaskOrder(taskList, listType) {
    // Save the new task order
    const taskItems = Array.from(taskList.querySelectorAll('.list-group-item'));
    const taskOrder = taskItems.map((item, index) => {
        return {
            id: item.getAttribute('data-task-id'),
            position: index
        };
    });

    // Create a FormData object to send the task order
    const formData = new FormData();
    formData.append('order', JSON.stringify(taskOrder));
    formData.append('list_type', listType);
    
    // Send the order data to the server
    fetch('/tasks/update_order', {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to update task order');
        }
        return response.json();
    })
    .then(data => {
        console.log(`${listType} task order updated:`, data);
    })
    .catch(error => {
        console.error(`Error updating ${listType} task order:`, error);
        // Consider showing a user-friendly error message
    });
}

/**
 * Initialize task details popup functionality
 */
function initializeTaskDetails() {
    // Create modal element for task details
    const modalElement = document.createElement('div');
    modalElement.className = 'modal fade';
    modalElement.id = 'taskDetailsModal';
    modalElement.tabIndex = '-1';
    modalElement.setAttribute('aria-labelledby', 'taskDetailsModalLabel');
    modalElement.setAttribute('aria-hidden', 'true');
    
    modalElement.innerHTML = `
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="taskDetailsModalLabel">Task Details</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <div id="taskDetailsContent">
                        <p><strong>Title:</strong> <span id="taskTitle"></span></p>
                        <p><strong>Project:</strong> <span id="taskProject"></span></p>
                        <p><strong>Status:</strong> <span id="taskStatus"></span></p>
                        <p><strong>Due Date:</strong> <span id="taskDueDate"></span></p>
                        <p><strong>Description:</strong> <span id="taskDescription"></span></p>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    <button type="button" class="btn btn-primary" id="toggleTaskStatus">Toggle Status</button>
                </div>
            </div>
        </div>
    `;
    
    // Add modal to the document
    document.body.appendChild(modalElement);
    
    // Add click event listeners to task items in all lists
    const taskItems = document.querySelectorAll('#prioritized-tasks .list-group-item, #unprioritized-tasks .list-group-item, #completed-tasks .list-group-item');
    taskItems.forEach(item => {
        // Add click event listener
        item.addEventListener('click', function(event) {
            // Don't show modal if clicking on the status button
            if (event.target.closest('button') || event.target.closest('form')) {
                return;
            }
            
            showTaskDetails(item);
        });
    });
}

/**
 * Show task details in the modal
 */
function showTaskDetails(taskItem) {
    // Get task ID
    const taskId = taskItem.getAttribute('data-task-id');
    
    // First, populate with basic information from the DOM
    const taskTitle = taskItem.querySelector('span:not(.text-muted)') ? 
                     taskItem.querySelector('span:not(.text-muted)').textContent.trim() : 
                     'Unknown';
    const taskProject = taskItem.querySelector('.text-muted.small') ? 
                       taskItem.querySelector('.text-muted.small').textContent.trim() : 
                       'None';
    const taskStatus = taskItem.querySelector('.btn-success') ? 'Completed' : 'Active';
    const taskDueDate = taskItem.querySelector('small.text-muted') ? 
                       taskItem.querySelector('small.text-muted').textContent.trim() : 
                       'None';
    
    // Show loading state in the modal
    document.getElementById('taskTitle').textContent = taskTitle;
    document.getElementById('taskProject').textContent = taskProject;
    document.getElementById('taskStatus').textContent = taskStatus;
    document.getElementById('taskDueDate').textContent = taskDueDate;
    
    // Show the modal
    const modal = new bootstrap.Modal(document.getElementById('taskDetailsModal'));
    modal.show();
    
    // Set up toggle status button
    const toggleButton = document.getElementById('toggleTaskStatus');
    toggleButton.onclick = function() {
        const form = taskItem.querySelector('form');
        if (form) {
            form.submit();
        }
    };
    
    // Fetch detailed task information from the API
    fetch(`/tasks/${taskId}/details`, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to fetch task details');
        }
        return response.json();
    })
    .then(taskDetails => {
        // Store task details for editing
        window.currentTaskDetails = taskDetails;
        
        // Update modal with detailed information
        const titleElement = document.getElementById('taskTitle');
        titleElement.innerHTML = `<input type="text" class="form-control" id="editTaskTitle" value="${taskDetails.title}">`;
        
        // Update project name if available
        const projectElement = document.getElementById('taskProject');
        if (taskDetails.project_name) {
            projectElement.textContent = taskDetails.project_name;
        }
        
        // Update status
        document.getElementById('taskStatus').textContent = 
            taskDetails.status === 'completed' ? 'Completed' : 'Active';
        
        // Update due date with editable date picker
        const dueDateElement = document.getElementById('taskDueDate');
        if (taskDetails.due_date) {
            const dueDate = new Date(taskDetails.due_date);
            const formattedDate = dueDate.toISOString().split('T')[0]; // Format as YYYY-MM-DD
            dueDateElement.innerHTML = `<input type="date" class="form-control" id="editTaskDueDate" value="${formattedDate}">`;
        } else {
            dueDateElement.innerHTML = `<input type="date" class="form-control" id="editTaskDueDate">`;
        }
        
        // Update description with editable textarea
        const descriptionElement = document.getElementById('taskDescription');
        if (descriptionElement) {
            const descriptionValue = taskDetails.description || '';
            descriptionElement.innerHTML = `<textarea class="form-control" id="editTaskDescription" rows="3">${descriptionValue}</textarea>`;
        }
        
        // Create or update the additional details section
        let detailsDiv = document.getElementById('additionalTaskDetails');
        if (!detailsDiv) {
            detailsDiv = document.createElement('div');
            detailsDiv.id = 'additionalTaskDetails';
            document.getElementById('taskDetailsContent').appendChild(detailsDiv);
        }
        
        // Add additional details with editable fields
        let additionalHTML = '';
        
        // Add priority dropdown
        let priorityValue = 2; // Default to Normal
        if (taskDetails.priority) {
            priorityValue = taskDetails.priority;
        }
        
        additionalHTML += `<div class="mb-3">
            <label for="editTaskPriority"><strong>Priority:</strong></label>
            <select class="form-select" id="editTaskPriority">
                <option value="1" ${priorityValue === 1 ? 'selected' : ''}>Low</option>
                <option value="2" ${priorityValue === 2 ? 'selected' : ''}>Normal</option>
                <option value="3" ${priorityValue === 3 ? 'selected' : ''}>High</option>
                <option value="4" ${priorityValue === 4 ? 'selected' : ''}>Urgent</option>
            </select>
        </div>`;
        
        // Add provider (read-only)
        if (taskDetails.provider) {
            additionalHTML += `<p><strong>Provider:</strong> ${taskDetails.provider}</p>`;
            // Store provider for use in update
            window.currentTaskProvider = taskDetails.provider;
        }
        
        // Add save button
        additionalHTML += `<div class="mt-3 text-end">
            <button class="btn btn-primary" id="saveTaskChanges">Save Changes</button>
        </div>`;
        
        // Set the HTML
        detailsDiv.innerHTML = additionalHTML;
        
        // Add event listener to save button
        document.getElementById('saveTaskChanges').addEventListener('click', function() {
            saveTaskChanges(taskId);
        });
    })
    .catch(error => {
        console.error('Error fetching task details:', error);
        // Don't show error to user, we already have basic information displayed
    });
}

/**
 * Save the edited task changes
 */
function saveTaskChanges(taskId) {


    // Get values from form fields
    const title = document.getElementById('editTaskTitle').value;
    const dueDate = document.getElementById('editTaskDueDate').value;
    const priority = parseInt(document.getElementById('editTaskPriority').value);
    const description = document.getElementById('editTaskDescription') ?
                      document.getElementById('editTaskDescription').value : '';
    
    // Create updated task object
    const updatedTask = {
        title: title,
        due_date: dueDate,
        priority: priority,
        description: description,
        provider: window.currentTaskProvider
    };
    
    // Hide any previous errors
    hideErrorMessage();
    
    // Show a loading indicator
    const saveButton = document.getElementById('saveTaskChanges');
    const originalButtonText = saveButton.textContent;
    saveButton.textContent = 'Saving...';
    saveButton.disabled = true;
    
    // Send update to server
    fetch(`/tasks/${taskId}/update`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify(updatedTask)
    })
    .then(response => {
        // Reset button state
        saveButton.textContent = originalButtonText;
        saveButton.disabled = false;
        
        if (!response.ok) {
            // For error responses, try to get error details as JSON
            return response.json()
                .then(errorData => {
                    // Use error message from JSON if available
                    throw new Error(errorData.error || 'Failed to update task');
                })
                .catch(jsonError => {
                    // If JSON parsing fails, use a generic error message
                    throw new Error('Failed to update task');
                });
        }
        
        return response.json();
    })
    .then(data => {
        // Show success message
        const messageDiv = document.createElement('div');
        messageDiv.className = 'alert alert-success';
        messageDiv.textContent = 'Task updated successfully!';
        
        // Insert message at top of modal
        const modalContent = document.getElementById('taskDetailsContent');
        modalContent.insertBefore(messageDiv, modalContent.firstChild);
        
        // Remove message after 2 seconds
        setTimeout(() => {
            messageDiv.remove();
            
            // Close modal and refresh task list
            bootstrap.Modal.getInstance(document.getElementById('taskDetailsModal')).hide();
            location.reload(); // Refresh the page to show updated task
        }, 2000);
    })
    .catch(error => {
        console.error('Error updating task:', error);
        
        // Show error message
        const messageDiv = document.createElement('div');
        messageDiv.className = 'alert alert-danger';
        messageDiv.textContent = error.message || 'Failed to update task. Please try again.';
        
        // Insert message at top of modal
        const modalContent = document.getElementById('taskDetailsContent');
        modalContent.insertBefore(messageDiv, modalContent.firstChild);
        
        // Remove message after 3 seconds
        setTimeout(() => {
            messageDiv.remove();
        }, 3000);
    });
}