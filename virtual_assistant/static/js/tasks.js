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
            
            // Get the task ID from the form action URL
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
        document.getElementById('unprioritized-container')
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
function createSortableLists() {
    const prioritizedList = document.getElementById('prioritized-tasks');
    const unprioritizedList = document.getElementById('unprioritized-tasks');
    
    if (!prioritizedList || !unprioritizedList) {
        return;
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
                const destination = evt.to.id === 'prioritized-tasks' ? 'prioritized' : 'unprioritized';
                
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
                const destination = evt.to.id === 'prioritized-tasks' ? 'prioritized' : 'unprioritized';
                
                // Move task between lists
                moveTaskBetweenLists(taskId, destination, evt.newIndex);
            } else {
                // Task was reordered within the same list
                updateTaskOrder(unprioritizedList, 'unprioritized');
            }
        }
    });
}

/**
 * Move a task between prioritized and unprioritized lists
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
    
    // Add click event listeners to task items in both lists
    const taskItems = document.querySelectorAll('#prioritized-tasks .list-group-item, #unprioritized-tasks .list-group-item');
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
        // Update modal with detailed information
        document.getElementById('taskTitle').textContent = taskDetails.title;
        
        // Update project name if available
        if (taskDetails.project_name) {
            document.getElementById('taskProject').textContent = taskDetails.project_name;
        }
        
        // Update status
        document.getElementById('taskStatus').textContent = 
            taskDetails.status === 'completed' ? 'Completed' : 'Active';
        
        // Update due date
        if (taskDetails.due_date) {
            const dueDate = new Date(taskDetails.due_date);
            document.getElementById('taskDueDate').textContent = dueDate.toLocaleDateString();
        } else {
            document.getElementById('taskDueDate').textContent = 'None';
        }
        
        // Create or update the additional details section
        let detailsDiv = document.getElementById('additionalTaskDetails');
        if (!detailsDiv) {
            detailsDiv = document.createElement('div');
            detailsDiv.id = 'additionalTaskDetails';
            document.getElementById('taskDetailsContent').appendChild(detailsDiv);
        }
        
        // Add additional details
        let additionalHTML = '';
        
        // Add priority
        if (taskDetails.priority) {
            // Convert priority number to text
            let priorityText = 'Normal';
            switch(taskDetails.priority) {
                case 1: priorityText = 'Low'; break;
                case 3: priorityText = 'High'; break;
                case 4: priorityText = 'Urgent'; break;
            }
            additionalHTML += `<p><strong>Priority:</strong> ${priorityText}</p>`;
        }
        
        // Add provider
        if (taskDetails.provider) {
            additionalHTML += `<p><strong>Provider:</strong> ${taskDetails.provider}</p>`;
        }
        
        // Set the HTML
        detailsDiv.innerHTML = additionalHTML;
    })
    .catch(error => {
        console.error('Error fetching task details:', error);
        // Don't show error to user, we already have basic information displayed
    });
}