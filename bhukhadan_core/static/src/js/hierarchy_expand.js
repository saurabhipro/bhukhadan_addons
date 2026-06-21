// Expand All Nodes Functionality for Horizontal Hierarchy View
function expandAllNodes() {
    console.log('Expand All Nodes clicked!');
    
    // Find all hierarchy nodes that can be expanded
    const nodes = document.querySelectorAll('.o_hierarchy_node');
    let expandedCount = 0;
    
    nodes.forEach(node => {
        // Check if node has children (subordinate count > 0)
        const subordinateCount = node.querySelector('.subordinate-count span');
        if (subordinateCount && parseInt(subordinateCount.textContent) > 0) {
            // Try to find and click the expand button
            const expandBtn = node.querySelector('.expand-all-btn');
            if (expandBtn) {
                expandBtn.click();
                expandedCount++;
            }
            
            // Also try to trigger the hierarchy's built-in expand functionality
            const hierarchyBtn = node.querySelector('[name="hierarchy_search_subsidiaries"]');
            if (hierarchyBtn) {
                hierarchyBtn.click();
                expandedCount++;
            }
        }
    });
    
    // Show success message
    if (expandedCount > 0) {
        console.log(`Successfully expanded ${expandedCount} nodes!`);
        // You could add a toast notification here if needed
    } else {
        console.log('No expandable nodes found or all nodes are already expanded.');
    }
}

// Add click handler for expand all buttons
document.addEventListener('DOMContentLoaded', function() {
    console.log('Hierarchy expand script loaded');
    
    // Add global expand all button if it doesn't exist
    const hierarchyView = document.querySelector('.o_hierarchy_view');
    if (hierarchyView && !document.querySelector('.btn-expand-all-global')) {
        const toolbar = document.createElement('div');
        toolbar.className = 'o_hierarchy_toolbar';
        toolbar.innerHTML = `
            <button class="btn-expand-all-global" onclick="expandAllNodes()">
                <i class="fa fa-expand"></i> Expand All Nodes
            </button>
        `;
        hierarchyView.insertBefore(toolbar, hierarchyView.firstChild);
    }
    
    // Add click handlers for individual expand buttons
    const expandButtons = document.querySelectorAll('.expand-all-btn');
    expandButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Individual expand button clicked');
            expandAllNodes();
        });
    });
    
    // Add click handler for global expand button
    const globalExpandBtn = document.querySelector('.btn-expand-all-global');
    if (globalExpandBtn) {
        globalExpandBtn.addEventListener('click', function(e) {
            e.preventDefault();
            expandAllNodes();
        });
    }
});

// Make function globally available
window.expandAllNodes = expandAllNodes;
