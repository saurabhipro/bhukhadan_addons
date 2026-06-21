/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class BhuKhadanHierarchyTree extends Component {
    static template = "bhukhadan_core.HierarchyTree";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.canvas = useRef("canvas");
        
        this.state = useState({
            rawData: {},      // Full district tree from server
            displayData: {},  // The part of the tree being rendered (root or focused subtree)
            loading: true,
            collapsed: {},
            fullscreen: false,
            error: false,
            districts: [],
            selectedDistrictId: null,
            orientation: 'vertical',
            breadcrumb: [],   // History of focused nodes
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData(districtId = null) {
        this.state.loading = true;
        this.state.error = false;
        try {
            const context = {};
            if (districtId) {
                context.district_id = districtId;
            }
            
            const result = await this.orm.call(
                "bhu.district",
                "get_detailed_hierarchy",
                [],
                { ...context }
            );
            
            if (result && !result.error) {
                this.state.rawData = result.tree;
                this.state.displayData = result.tree;
                this.state.districts = result.available_districts || [];
                this.state.breadcrumb = [{ id: result.tree.id, name: result.tree.name, type: 'district' }];
                
                if (!this.state.selectedDistrictId && result.tree) {
                    this.state.selectedDistrictId = parseInt(result.tree.id.split('_')[1]);
                }
                
                // Collapse all by default to start clean
                this.initializeCollapsedState(result.tree);
            } else {
                this.state.error = result ? result.error : "No data received";
            }
        } catch (error) {
            console.error("Failed to load hierarchy data", error);
            this.state.error = "Failed to fetch data from server";
        } finally {
            this.state.loading = false;
        }
    }

    initializeCollapsedState(node) {
        if (node.children && node.children.length > 0) {
            // Keep the root expanded, collapse others
            if (node.type !== 'district') {
                this.state.collapsed[node.id] = true;
            }
            node.children.forEach(child => this.initializeCollapsedState(child));
        }
    }

    findNodeById(node, id) {
        if (node.id === id) return node;
        if (node.children) {
            for (let child of node.children) {
                const found = this.findNodeById(child, id);
                if (found) return found;
            }
        }
        return null;
    }

    focusOnNode(node) {
        if (node.type === 'user') return;
        
        // Build breadcrumb
        const index = this.state.breadcrumb.findIndex(b => b.id === node.id);
        if (index !== -1) {
            this.state.breadcrumb = this.state.breadcrumb.slice(0, index + 1);
        } else {
            this.state.breadcrumb.push({ id: node.id, name: node.name, type: node.type });
        }

        this.state.displayData = this.findNodeById(this.state.rawData, node.id);
        // Expand the focused node if it was collapsed
        this.state.collapsed[node.id] = false;
    }

    resetView() {
        this.state.displayData = this.state.rawData;
        this.state.breadcrumb = [{ id: this.state.rawData.id, name: this.state.rawData.name, type: 'district' }];
    }

    async onDistrictChange(ev) {
        const districtId = parseInt(ev.target.value);
        this.state.selectedDistrictId = districtId;
        await this.loadData(districtId);
    }

    toggleOrientation(type) {
        this.state.orientation = type;
    }

    getRoleIcon(role) {
        const icons = {
            'collector': 'fa-university',
            'additional_collector': 'fa-balance-scale',
            'sdm': 'fa-briefcase',
            'tehsildar': 'fa-shield',
            'naib_tehsildar': 'fa-bookmark',
            'revenue_inspector': 'fa-search',
            'patwari': 'fa-pencil-square',
            'district_administrator': 'fa-cogs',
            'administrator': 'fa-user-secret'
        };
        return icons[role] || 'fa-user';
    }

    getRoleLabel(role) {
        const labels = {
            'collector': 'District Collector',
            'additional_collector': 'Add. Collector',
            'sdm': 'SDM',
            'tehsildar': 'Tehsildar',
            'naib_tehsildar': 'Naib Tehsildar',
            'revenue_inspector': 'RI',
            'patwari': 'Patwari',
            'district_administrator': 'Admin',
            'administrator': 'Super Admin'
        };
        return labels[role] || role;
    }

    toggleNode(nodeId) {
        this.state.collapsed[nodeId] = !this.state.collapsed[nodeId];
    }

    onNodeClick(node) {
        if (node.type === 'user') {
            const userId = parseInt(node.id.split('_')[1]);
            this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'res.users',
                res_id: userId,
                views: [[false, 'form']],
                target: 'current',
            });
        }
    }

    toggleFull() {
        this.state.fullscreen = !this.state.fullscreen;
        const el = this.canvas.el;
        if (el && this.state.fullscreen) {
            if (el.requestFullscreen) el.requestFullscreen();
        } else {
            if (document.exitFullscreen) document.exitFullscreen();
        }
    }
}

registry.category("actions").add("bhuarjan_hierarchy_tree_action", BhuKhadanHierarchyTree);
