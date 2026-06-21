/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, onMounted, onPatched, onWillUnmount, useState, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Unified Dashboard Component - Configurable for all dashboard types
 * 
 * CONFIGURATION GUIDE:
 * To add a new dashboard type, add it to DASHBOARD_CONFIG below:
 * 
 * DASHBOARD_CONFIG = {
 *     'dashboard_type_name': {
 *         template: 'bhukhadan_core.TemplateName',
 *         registryKey: 'bhukhadan_core.registry_key',
 *         pageTitle: 'Dashboard Title',
 *         localStoragePrefix: 'local_storage_prefix',
 *         showDepartmentFilter: true/false,
 *         showProjectFilter: true/false,
 *         showVillageFilter: true/false,
 *         initialDataMethod: 'method_name', // Optional: custom method for initial data
 *         statsMapping: { // Map backend stats keys to frontend state keys
 *             'survey_total': 'survey_total',
 *             ...
 *         }
 *     }
 * }
 */

// ========== CONFIGURATION: Dashboard Types ==========
const DASHBOARD_CONFIG = {
    'sdm': {
        template: 'bhukhadan_core.SDMTemplate',
        registryKey: 'bhukhadan_core.sdm_dashboard_tag',
        pageTitle: 'SDM Dashboard',
        localStoragePrefix: 'sdm_dashboard',
        showDepartmentFilter: true,
        showProjectFilter: true,
        showVillageFilter: true,
        statsMapping: {
            // Maps backend response keys to frontend state keys
            'survey_total': 'survey_total',
            'survey_draft': 'survey_draft',
            'survey_submitted': 'survey_submitted',
            'survey_approved': 'survey_approved',
            'survey_rejected': 'survey_rejected',
            'section4_total': 'section4_total',
            'section4_draft': 'section4_draft',
            'section4_submitted': 'section4_submitted',
            'section4_approved': 'section4_approved',
            'section4_send_back': 'section4_send_back',
            'section11_total': 'section11_total',
            'section11_draft': 'section11_draft',
            'section11_submitted': 'section11_submitted',
            'section11_approved': 'section11_approved',
            'section11_send_back': 'section11_send_back',
            'section15_total': 'section15_total',
            'section15_draft': 'section15_draft',
            'section15_submitted': 'section15_submitted',
            'section15_approved': 'section15_approved',
            'section15_send_back': 'section15_send_back',
            'section19_total': 'section19_total',
            'section19_draft': 'section19_draft',
            'section19_submitted': 'section19_submitted',
            'section19_approved': 'section19_approved',
            'section19_send_back': 'section19_send_back',
            'expert_total': 'expert_total',
            'expert_draft': 'expert_draft',
            'expert_submitted': 'expert_submitted',
            'expert_approved': 'expert_approved',
            'expert_send_back': 'expert_send_back',
            'sia_total': 'sia_total',
            'sia_draft': 'sia_draft',
            'sia_submitted': 'sia_submitted',
            'sia_approved': 'sia_approved',
            'sia_send_back': 'sia_send_back',
            'section8_total': 'section8_total',
            'section8_draft': 'section8_draft',
            'section8_approved': 'section8_approved',
            'section8_rejected': 'section8_rejected',
            'section23_award_total': 'section23_award_total',
            'section23_award_draft': 'section23_award_draft',
            'section23_award_submitted': 'section23_award_submitted',
            'section23_award_approved': 'section23_award_approved',
            'section23_award_send_back': 'section23_award_send_back',
            'section23_award_completion_percent': 'section23_award_completion_percent',
            'payment_voucher_total': 'payment_voucher_total',
            'payment_voucher_draft': 'payment_voucher_draft',
            'payment_voucher_generated': 'payment_voucher_generated',
            'payment_voucher_completion_percent': 'payment_voucher_completion_percent',
            'payment_voucher_info': 'payment_voucher_info',
            'payment_file_total': 'payment_file_total',
            'payment_file_draft': 'payment_file_draft',
            'payment_file_generated': 'payment_file_generated',
            'payment_file_completion_percent': 'payment_file_completion_percent',
            'payment_file_info': 'payment_file_info',
            'reconciliation_total': 'reconciliation_total',
            'reconciliation_draft': 'reconciliation_draft',
            'reconciliation_processed': 'reconciliation_processed',
            'reconciliation_completed': 'reconciliation_completed',
            'reconciliation_completion_percent': 'reconciliation_completion_percent',
            'reconciliation_info': 'reconciliation_info',
            'section247_1_cglrc_total': 'section247_1_cglrc_total',
            'section247_1_cglrc_draft': 'section247_1_cglrc_draft',
            'section247_1_cglrc_approved': 'section247_1_cglrc_approved',
            'section247_1_cglrc_info': 'section247_1_cglrc_info',
            'section247_1_cglrc_completion_percent': 'section247_1_cglrc_completion_percent',
            'section247_2_cglrc_total': 'section247_2_cglrc_total',
            'section247_2_cglrc_draft': 'section247_2_cglrc_draft',
            'section247_2_cglrc_approved': 'section247_2_cglrc_approved',
            'section247_2_cglrc_info': 'section247_2_cglrc_info',
            'section247_2_cglrc_completion_percent': 'section247_2_cglrc_completion_percent',
            'section247_3_cglrc_total': 'section247_3_cglrc_total',
            'section247_3_cglrc_draft': 'section247_3_cglrc_draft',
            'section247_3_cglrc_approved': 'section247_3_cglrc_approved',
            'section247_3_cglrc_info': 'section247_3_cglrc_info',
            'section247_3_cglrc_completion_percent': 'section247_3_cglrc_completion_percent',
        }
    },
    'collector': {
        template: 'bhukhadan_core.CollectorDashboardTemplate',
        registryKey: 'bhukhadan_core.collector_dashboard',
        pageTitle: 'Collector Dashboard',
        localStoragePrefix: 'collector_dashboard',
        showDepartmentFilter: true,
        showProjectFilter: true,
        showVillageFilter: true,
        statsMapping: {
            // Same as SDM
            'survey_total': 'survey_total',
            'survey_draft': 'survey_draft',
            'survey_submitted': 'survey_submitted',
            'survey_approved': 'survey_approved',
            'survey_rejected': 'survey_rejected',
            'section4_total': 'section4_total',
            'section4_draft': 'section4_draft',
            'section4_submitted': 'section4_submitted',
            'section4_approved': 'section4_approved',
            'section4_send_back': 'section4_send_back',
            'section11_total': 'section11_total',
            'section11_draft': 'section11_draft',
            'section11_submitted': 'section11_submitted',
            'section11_approved': 'section11_approved',
            'section11_send_back': 'section11_send_back',
            'section15_total': 'section15_total',
            'section15_draft': 'section15_draft',
            'section15_submitted': 'section15_submitted',
            'section15_approved': 'section15_approved',
            'section15_send_back': 'section15_send_back',
            'section19_total': 'section19_total',
            'section19_draft': 'section19_draft',
            'section19_submitted': 'section19_submitted',
            'section19_approved': 'section19_approved',
            'section19_send_back': 'section19_send_back',
            'expert_total': 'expert_total',
            'expert_draft': 'expert_draft',
            'expert_submitted': 'expert_submitted',
            'expert_approved': 'expert_approved',
            'expert_send_back': 'expert_send_back',
            'sia_total': 'sia_total',
            'sia_draft': 'sia_draft',
            'sia_submitted': 'sia_submitted',
            'sia_approved': 'sia_approved',
            'sia_send_back': 'sia_send_back',
            'section8_total': 'section8_total',
            'section8_draft': 'section8_draft',
            'section8_approved': 'section8_approved',
            'section8_rejected': 'section8_rejected',
            'section23_award_total': 'section23_award_total',
            'section23_award_draft': 'section23_award_draft',
            'section23_award_submitted': 'section23_award_submitted',
            'section23_award_approved': 'section23_award_approved',
            'section23_award_send_back': 'section23_award_send_back',
            'section23_award_completion_percent': 'section23_award_completion_percent',
            'payment_voucher_total': 'payment_voucher_total',
            'payment_voucher_draft': 'payment_voucher_draft',
            'payment_voucher_generated': 'payment_voucher_generated',
            'payment_voucher_completion_percent': 'payment_voucher_completion_percent',
            'payment_voucher_info': 'payment_voucher_info',
            'payment_file_total': 'payment_file_total',
            'payment_file_draft': 'payment_file_draft',
            'payment_file_generated': 'payment_file_generated',
            'payment_file_completion_percent': 'payment_file_completion_percent',
            'payment_file_info': 'payment_file_info',
            'reconciliation_total': 'reconciliation_total',
            'reconciliation_draft': 'reconciliation_draft',
            'reconciliation_processed': 'reconciliation_processed',
            'reconciliation_completed': 'reconciliation_completed',
            'reconciliation_completion_percent': 'reconciliation_completion_percent',
            'reconciliation_info': 'reconciliation_info',
            'section247_1_cglrc_total': 'section247_1_cglrc_total',
            'section247_1_cglrc_draft': 'section247_1_cglrc_draft',
            'section247_1_cglrc_approved': 'section247_1_cglrc_approved',
            'section247_1_cglrc_info': 'section247_1_cglrc_info',
            'section247_1_cglrc_completion_percent': 'section247_1_cglrc_completion_percent',
            'section247_2_cglrc_total': 'section247_2_cglrc_total',
            'section247_2_cglrc_draft': 'section247_2_cglrc_draft',
            'section247_2_cglrc_approved': 'section247_2_cglrc_approved',
            'section247_2_cglrc_info': 'section247_2_cglrc_info',
            'section247_2_cglrc_completion_percent': 'section247_2_cglrc_completion_percent',
            'section247_3_cglrc_total': 'section247_3_cglrc_total',
            'section247_3_cglrc_draft': 'section247_3_cglrc_draft',
            'section247_3_cglrc_approved': 'section247_3_cglrc_approved',
            'section247_3_cglrc_info': 'section247_3_cglrc_info',
            'section247_3_cglrc_completion_percent': 'section247_3_cglrc_completion_percent',
        }
    },
    'admin': {
        template: 'bhukhadan_core.AdminDashboardTemplate',
        registryKey: 'bhukhadan_core.admin_dashboard',
        pageTitle: 'Admin Dashboard',
        localStoragePrefix: 'admin_dashboard',
        showDepartmentFilter: true,
        showProjectFilter: true,
        showVillageFilter: true,
        statsMapping: {
            'survey_total': 'survey_total',
            'survey_draft': 'survey_draft',
            'survey_submitted': 'survey_submitted',
            'survey_approved': 'survey_approved',
            'survey_rejected': 'survey_rejected',
            'section4_total': 'section4_total',
            'section4_draft': 'section4_draft',
            'section4_submitted': 'section4_submitted',
            'section4_approved': 'section4_approved',
            'section4_send_back': 'section4_send_back',
            'section11_total': 'section11_total',
            'section11_draft': 'section11_draft',
            'section11_submitted': 'section11_submitted',
            'section11_approved': 'section11_approved',
            'section11_send_back': 'section11_send_back',
            'section15_total': 'section15_total',
            'section15_draft': 'section15_draft',
            'section15_submitted': 'section15_submitted',
            'section15_approved': 'section15_approved',
            'section15_send_back': 'section15_send_back',
            'section19_total': 'section19_total',
            'section19_draft': 'section19_draft',
            'section19_submitted': 'section19_submitted',
            'section19_approved': 'section19_approved',
            'section19_send_back': 'section19_send_back',
            'expert_total': 'expert_total',
            'expert_draft': 'expert_draft',
            'expert_submitted': 'expert_submitted',
            'expert_approved': 'expert_approved',
            'expert_send_back': 'expert_send_back',
            'sia_total': 'sia_total',
            'sia_draft': 'sia_draft',
            'sia_submitted': 'sia_submitted',
            'sia_approved': 'sia_approved',
            'sia_send_back': 'sia_send_back',
            'section8_total': 'section8_total',
            'section8_draft': 'section8_draft',
            'section8_approved': 'section8_approved',
            'section8_rejected': 'section8_rejected',
            'section23_award_total': 'section23_award_total',
            'section23_award_draft': 'section23_award_draft',
            'section23_award_submitted': 'section23_award_submitted',
            'section23_award_approved': 'section23_award_approved',
            'section23_award_send_back': 'section23_award_send_back',
            'section23_award_completion_percent': 'section23_award_completion_percent',
            'payment_voucher_total': 'payment_voucher_total',
            'payment_voucher_draft': 'payment_voucher_draft',
            'payment_voucher_generated': 'payment_voucher_generated',
            'payment_voucher_completion_percent': 'payment_voucher_completion_percent',
            'payment_voucher_info': 'payment_voucher_info',
            'payment_file_total': 'payment_file_total',
            'payment_file_draft': 'payment_file_draft',
            'payment_file_generated': 'payment_file_generated',
            'payment_file_completion_percent': 'payment_file_completion_percent',
            'payment_file_info': 'payment_file_info',
            'reconciliation_total': 'reconciliation_total',
            'reconciliation_draft': 'reconciliation_draft',
            'reconciliation_processed': 'reconciliation_processed',
            'reconciliation_completed': 'reconciliation_completed',
            'reconciliation_completion_percent': 'reconciliation_completion_percent',
            'reconciliation_info': 'reconciliation_info',
            'section247_1_cglrc_total': 'section247_1_cglrc_total',
            'section247_1_cglrc_draft': 'section247_1_cglrc_draft',
            'section247_1_cglrc_approved': 'section247_1_cglrc_approved',
            'section247_1_cglrc_info': 'section247_1_cglrc_info',
            'section247_1_cglrc_completion_percent': 'section247_1_cglrc_completion_percent',
            'section247_2_cglrc_total': 'section247_2_cglrc_total',
            'section247_2_cglrc_draft': 'section247_2_cglrc_draft',
            'section247_2_cglrc_approved': 'section247_2_cglrc_approved',
            'section247_2_cglrc_info': 'section247_2_cglrc_info',
            'section247_2_cglrc_completion_percent': 'section247_2_cglrc_completion_percent',
            'section247_3_cglrc_total': 'section247_3_cglrc_total',
            'section247_3_cglrc_draft': 'section247_3_cglrc_draft',
            'section247_3_cglrc_approved': 'section247_3_cglrc_approved',
            'section247_3_cglrc_info': 'section247_3_cglrc_info',
            'section247_3_cglrc_completion_percent': 'section247_3_cglrc_completion_percent',
        }
    },
    'department': {
        template: 'bhukhadan_core.DepartmentDashboardTemplate',
        registryKey: 'bhukhadan_core.department_dashboard',
        pageTitle: 'Department User Dashboard',
        localStoragePrefix: 'department_dashboard',
        showDepartmentFilter: false, // Department users have only one department - no dropdown needed
        showProjectFilter: true,
        showVillageFilter: true,
        statsMapping: {
            'survey_total': 'survey_total',
            'survey_draft': 'survey_draft',
            'survey_submitted': 'survey_submitted',
            'survey_approved': 'survey_approved',
            'survey_rejected': 'survey_rejected',
            'survey_completion_percent': 'survey_completion_percent',
            'section8_total': 'section8_total',
            'section8_draft': 'section8_draft',
            'section8_approved': 'section8_approved',
            'section8_rejected': 'section8_rejected',
            'section23_award_total': 'section23_award_total',
            'section23_award_draft': 'section23_award_draft',
            'section23_award_submitted': 'section23_award_submitted',
            'section23_award_approved': 'section23_award_approved',
            'section23_award_send_back': 'section23_award_send_back',
            'section23_award_completion_percent': 'section23_award_completion_percent',
            'payment_voucher_total': 'payment_voucher_total',
            'payment_voucher_draft': 'payment_voucher_draft',
            'payment_voucher_generated': 'payment_voucher_generated',
            'payment_voucher_completion_percent': 'payment_voucher_completion_percent',
            'payment_voucher_info': 'payment_voucher_info',
            'payment_file_total': 'payment_file_total',
            'payment_file_draft': 'payment_file_draft',
            'payment_file_generated': 'payment_file_generated',
            'payment_file_completion_percent': 'payment_file_completion_percent',
            'payment_file_info': 'payment_file_info',
            'reconciliation_total': 'reconciliation_total',
            'reconciliation_draft': 'reconciliation_draft',
            'reconciliation_processed': 'reconciliation_processed',
            'reconciliation_completed': 'reconciliation_completed',
            'reconciliation_completion_percent': 'reconciliation_completion_percent',
            'reconciliation_info': 'reconciliation_info',
        }
    },
    'district': {
        template: 'bhukhadan_core.DistrictDashboardTemplate',
        registryKey: 'bhukhadan_core.district_dashboard',
        pageTitle: 'District Admin Dashboard',
        localStoragePrefix: 'district_dashboard',
        showDepartmentFilter: true,
        showProjectFilter: true,
        showVillageFilter: true,
        isReadOnly: true, // District admin can only view, not create
        statsMapping: {
            'survey_total': 'survey_total',
            'survey_draft': 'survey_draft',
            'survey_submitted': 'survey_submitted',
            'survey_approved': 'survey_approved',
            'survey_rejected': 'survey_rejected',
            'section4_total': 'section4_total',
            'section4_draft': 'section4_draft',
            'section4_submitted': 'section4_submitted',
            'section4_approved': 'section4_approved',
            'section4_send_back': 'section4_send_back',
            'section11_total': 'section11_total',
            'section11_draft': 'section11_draft',
            'section11_submitted': 'section11_submitted',
            'section11_approved': 'section11_approved',
            'section11_send_back': 'section11_send_back',
            'section15_total': 'section15_total',
            'section15_draft': 'section15_draft',
            'section15_submitted': 'section15_submitted',
            'section15_approved': 'section15_approved',
            'section15_send_back': 'section15_send_back',
            'section19_total': 'section19_total',
            'section19_draft': 'section19_draft',
            'section19_submitted': 'section19_submitted',
            'section19_approved': 'section19_approved',
            'section19_send_back': 'section19_send_back',
            'expert_total': 'expert_total',
            'expert_draft': 'expert_draft',
            'expert_submitted': 'expert_submitted',
            'expert_approved': 'expert_approved',
            'expert_send_back': 'expert_send_back',
            'sia_total': 'sia_total',
            'sia_draft': 'sia_draft',
            'sia_submitted': 'sia_submitted',
            'sia_approved': 'sia_approved',
            'sia_send_back': 'sia_send_back',
            'section8_total': 'section8_total',
            'section8_draft': 'section8_draft',
            'section8_approved': 'section8_approved',
            'section8_rejected': 'section8_rejected',
            'section23_award_total': 'section23_award_total',
            'section23_award_draft': 'section23_award_draft',
            'section23_award_submitted': 'section23_award_submitted',
            'section23_award_approved': 'section23_award_approved',
            'section23_award_send_back': 'section23_award_send_back',
            'section23_award_completion_percent': 'section23_award_completion_percent',
            'payment_voucher_total': 'payment_voucher_total',
            'payment_voucher_draft': 'payment_voucher_draft',
            'payment_voucher_generated': 'payment_voucher_generated',
            'payment_voucher_completion_percent': 'payment_voucher_completion_percent',
            'payment_voucher_info': 'payment_voucher_info',
            'payment_file_total': 'payment_file_total',
            'payment_file_draft': 'payment_file_draft',
            'payment_file_generated': 'payment_file_generated',
            'payment_file_completion_percent': 'payment_file_completion_percent',
            'payment_file_info': 'payment_file_info',
            'reconciliation_total': 'reconciliation_total',
            'reconciliation_draft': 'reconciliation_draft',
            'reconciliation_processed': 'reconciliation_processed',
            'reconciliation_completed': 'reconciliation_completed',
            'reconciliation_completion_percent': 'reconciliation_completion_percent',
            'reconciliation_info': 'reconciliation_info',
            'section247_1_cglrc_total': 'section247_1_cglrc_total',
            'section247_1_cglrc_draft': 'section247_1_cglrc_draft',
            'section247_1_cglrc_approved': 'section247_1_cglrc_approved',
            'section247_1_cglrc_info': 'section247_1_cglrc_info',
            'section247_1_cglrc_completion_percent': 'section247_1_cglrc_completion_percent',
            'section247_2_cglrc_total': 'section247_2_cglrc_total',
            'section247_2_cglrc_draft': 'section247_2_cglrc_draft',
            'section247_2_cglrc_approved': 'section247_2_cglrc_approved',
            'section247_2_cglrc_info': 'section247_2_cglrc_info',
            'section247_2_cglrc_completion_percent': 'section247_2_cglrc_completion_percent',
            'section247_3_cglrc_total': 'section247_3_cglrc_total',
            'section247_3_cglrc_draft': 'section247_3_cglrc_draft',
            'section247_3_cglrc_approved': 'section247_3_cglrc_approved',
            'section247_3_cglrc_info': 'section247_3_cglrc_info',
            'section247_3_cglrc_completion_percent': 'section247_3_cglrc_completion_percent',
        }
    },

};

export class UnifiedDashboard extends Component {
    // Template will be set dynamically based on dashboard type
    static template = "bhukhadan_core.SDMTemplate"; // Default, will be overridden

    setup() {
        // Determine dashboard type from props or context
        // Only set dashboardType if not already set by child class
        if (!this.dashboardType) {
            this.dashboardType = this.props.dashboardType || 'sdm';
        }
        this.config = DASHBOARD_CONFIG[this.dashboardType] || DASHBOARD_CONFIG['sdm'];

        // Set template dynamically
        this.constructor.template = this.config.template;

        this.pageTitle = this.config.pageTitle;
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        // Bind methods to this instance for use in templates
        this.openSection8ForRecommend = this.openSection8ForRecommend.bind(this);
        this.openFirstPending = this.openFirstPending.bind(this);
        this.openSectionList = this.openSectionList.bind(this);
        this.openFirstDocument = this.openFirstDocument.bind(this);
        this.createSectionRecord = this.createSectionRecord.bind(this);
        this.createPaymentVoucherFromDashboard = this.createPaymentVoucherFromDashboard.bind(this);
        this.viewPaymentVoucherFromDashboard = this.viewPaymentVoucherFromDashboard.bind(this);
        this.openPaymentVoucherFromDashboard = this.openPaymentVoucherFromDashboard.bind(this);

        const localStoragePrefix = this.config.localStoragePrefix;

        // Load persisted selections from localStorage
        const savedDepartment = localStorage.getItem(`${localStoragePrefix}_department`);
        const savedProject = localStorage.getItem(`${localStoragePrefix}_project`);
        const savedProjectName = localStorage.getItem(`${localStoragePrefix}_project_name`);
        const savedProjectCode = localStorage.getItem(`${localStoragePrefix}_project_code`);
        const savedVillage = localStorage.getItem(`${localStoragePrefix}_village`);
        const savedVillageName = localStorage.getItem(`${localStoragePrefix}_village_name`);

        // Initialize state based on configuration
        const initialState = {
            loading: true,
            selectedDepartment: savedDepartment ? parseInt(savedDepartment, 10) : null,
            selectedProject: savedProject ? parseInt(savedProject, 10) : null,
            selectedProjectName: savedProjectName || null,
            selectedProjectCode: savedProjectCode || null,
            selectedVillage: savedVillage ? parseInt(savedVillage, 10) : null,
            selectedVillageName: savedVillageName || null,
            departments: [],
            projects: [],
            villages: [],
            isCollector: false,
            isAdmin: false,
            isSDM: false,
            isProjectExempt: false,
            isDisplacement: false,
            isReadOnly: this.config.isReadOnly || false, // District admin is read-only
            allowedSectionNames: [], // Sections mapped to project'
            stats: this._getInitialStats(),
            showTimeline: true,
            departmentDropdownOpen: false,
        };

        this.state = useState(initialState);
        this.dashboardRoot = useRef("dashboardRoot");
        this.departmentDropdownRef = useRef("departmentDropdown");

        onWillStart(async () => {
            this._showBodyLoader();
            try {
                await this.loadInitialData();
                await this.loadDashboardData();
            } catch (error) {
                console.error("Error in onWillStart:", error);
                this.state.loading = false;
            }
            this._hideBodyLoader();
        });

        onMounted(() => {
            this._applySectionActivityHighlights();
            this._departmentDropdownOutsideClick = (ev) => {
                if (!this.state.departmentDropdownOpen) {
                    return;
                }
                const el = this.departmentDropdownRef.el;
                if (el && !el.contains(ev.target)) {
                    this.closeDepartmentDropdown();
                }
            };
            document.addEventListener("click", this._departmentDropdownOutsideClick);
        });

        onWillUnmount(() => {
            if (this._departmentDropdownOutsideClick) {
                document.removeEventListener("click", this._departmentDropdownOutsideClick);
            }
        });

        this.toggleTimeline = () => {
            this.state.showTimeline = !this.state.showTimeline;
        };

        onPatched(() => {
            this._applySectionActivityHighlights();
        });
    }

    _getInitialStats() {
        // Initialize stats based on dashboard type configuration
        const stats = {};
        const mapping = this.config.statsMapping || {};

        // Initialize all mapped stats to 0
        for (const [backendKey, frontendKey] of Object.entries(mapping)) {
            stats[frontendKey] = 0;
        }

        // Add info objects for sections that need them
        if (this.dashboardType === 'sdm' || this.dashboardType === 'collector' || this.dashboardType === 'district' || this.dashboardType === 'admin') {
            stats.section4_info = null;
            stats.section11_info = null;
            stats.section15_info = null;
            stats.section19_info = null;
            stats.expert_info = null;
            stats.sia_info = null;
            stats.section8_info = null;
            stats.survey_info = null;
            stats.draft_award_info = null;
            stats.section23_award_info = null;
        }

        return stats;
    }

    _formatProjectCode(project) {
        if (!project) {
            return null;
        }
        const code = (project.code || "").trim();
        return code ? `[${code}]` : null;
    }

    /**
     * Department label for dropdown / header (with optional code prefix).
     * @param {{ id: number, name?: string, code?: string, dropdown_label?: string }|null|undefined} department
     */
    _formatDepartmentTitle(department) {
        if (!department) {
            return null;
        }
        const preset = (department.dropdown_label || "").trim();
        if (preset) {
            return preset;
        }
        const code = (department.code || "").trim();
        const name = (department.name || "").trim();
        if (code && name) {
            return `[${code}] ${name}`;
        }
        if (name) {
            return name;
        }
        if (code) {
            return `[${code}]`;
        }
        return null;
    }

    /** Normalize department rows from RPC for consistent dropdown labels. */
    _normalizeDepartmentRow(row) {
        if (!row || !row.id) {
            return row;
        }
        const code = String(row.code || "").trim();
        const name = String(row.name || "").trim();
        let dropdown_label = String(row.dropdown_label || "").trim();
        if (!dropdown_label) {
            if (code && name) {
                dropdown_label = `[${code}] ${name}`;
            } else if (name) {
                dropdown_label = name;
            } else if (code) {
                dropdown_label = `[${code}]`;
            }
        }
        row.code = code;
        row.name = name;
        row.dropdown_label = dropdown_label;
        row.icon = String(row.icon || "").trim();
        row.department_has_logo = !!row.department_has_logo;
        return row;
    }

    departmentLogoSrc(deptId) {
        return deptId ? `/web/image/bhu.department/${deptId}/department_logo` : "";
    }

    departmentPlaceholderIcon(department) {
        const ic = ((department && department.icon) || "").trim();
        return ic || "fa fa-building text-secondary";
    }

    departmentRowClass(department) {
        return (department.survey_count || 0) > 0 ? "o_bhu_dd_row_active" : "o_bhu_dd_row_inactive";
    }

    toggleDepartmentDropdown(ev) {
        ev.stopPropagation();
        this.state.departmentDropdownOpen = !this.state.departmentDropdownOpen;
    }

    closeDepartmentDropdown() {
        this.state.departmentDropdownOpen = false;
    }

    /**
     * Project label for header / persistence (no survey count).
     * @param {{ id: number, name?: string, code?: string }|null|undefined} project
     */
    _formatProjectTitle(project) {
        if (!project) {
            return null;
        }
        const code = (project.code || "").trim();
        const name = (project.name || "").trim();
        if (code && name) {
            return `[${code}] ${name}`;
        }
        if (name) {
            return name;
        }
        if (code) {
            return `[${code}]`;
        }
        return null;
    }

    /** Full project label for tooltips (includes survey count). */
    getProjectOptionTitle(project) {
        if (!project) {
            return "";
        }
        const base = this._formatProjectTitle(project) || (project.name || "").trim();
        const count = project.survey_count || 0;
        return base ? `${base} (${count})` : "";
    }

    getDepartmentOptionTitle(department) {
        if (!department) {
            return "";
        }
        const base = this._formatDepartmentTitle(department) || (department.name || "").trim();
        const count = department.survey_count || 0;
        return base ? `${base} (${count})` : "";
    }

    getSelectedDepartment() {
        if (!this.state.selectedDepartment) {
            return null;
        }
        return this.state.departments.find((d) => d.id === this.state.selectedDepartment) || null;
    }

    getSelectedProject() {
        if (!this.state.selectedProject) {
            return null;
        }
        return this.state.projects.find((p) => p.id === this.state.selectedProject) || null;
    }

    _getStepCardProjectName() {
        const project = this.getSelectedProject();
        if (project && project.name) {
            return project.name.trim();
        }
        const stored = (this.state.selectedProjectName || '').trim();
        return stored.replace(/^\[[^\]]+\]\s*/, '').trim() || stored;
    }

    getVillageOptionTitle(village) {
        if (!village) {
            return "";
        }
        const label = (village.dropdown_label || this._formatVillageTitle(village) || "").trim();
        const count = village.survey_count || 0;
        const type = ((village.village_type || "").toLowerCase() === "urban") ? "U" : "R";
        return label ? `${label} (${count}) (${type})` : "";
    }

    getSelectedVillage() {
        if (!this.state.selectedVillage) {
            return null;
        }
        return this.state.villages.find((v) => v.id === this.state.selectedVillage) || null;
    }

    getVillageDisplayCode(village) {
        if (!village) {
            return "—";
        }
        const code = String(village.display_code || village.village_code || "").trim();
        return code || "—";
    }

    /**
     * Village label for header / persistence (no survey count / type suffix).
     * Uses ``dropdown_label`` / ``display_code`` from dashboard RPC when present.
     * @param {{ id: number, name?: string, village_code?: string, display_code?: string, dropdown_label?: string }|null|undefined} village
     */
    _formatVillageTitle(village) {
        if (!village) {
            return null;
        }
        const label = (village.dropdown_label || "").trim();
        if (label) {
            return label;
        }
        const code = (village.display_code || village.village_code || "").trim();
        const name = (village.name || "").trim();
        if (code && name) {
            return `[${code}] ${name}`;
        }
        if (name) {
            return name;
        }
        if (code) {
            return `[${code}]`;
        }
        return null;
    }

    /**
     * Normalize village rows from ``get_villages_by_project`` so dropdown/header always get ``dropdown_label``.
     * @param {Record<string, unknown>} raw
     * @param {number} [fallbackIndex] stable V1, V2, … when master has no village_code
     */
    _normalizeVillageRow(raw, fallbackIndex) {
        const row = { ...raw };
        let code = String(row.display_code || row.village_code || "").trim();
        if (!code && fallbackIndex) {
            code = `V${fallbackIndex}`;
        }
        const name = String(row.name || "").trim();
        let dropdown_label = String(row.dropdown_label || "").trim();
        if (code && name) {
            dropdown_label = `[${code}] ${name}`;
        } else if (code) {
            dropdown_label = `[${code}]`;
        } else if (!dropdown_label) {
            dropdown_label = name;
        }
        row.display_code = code;
        row.village_code = String(row.village_code || code || "").trim();
        row.dropdown_label = dropdown_label;
        return row;
    }

    async loadInitialData() {
        const localStoragePrefix = this.config.localStoragePrefix;

        // For department dashboard, always load department (even if filter is hidden)
        if (this.dashboardType === 'department') {
            await this.loadDepartments();
            // Department should now be auto-selected and projects loaded
        } else if (this.config.showDepartmentFilter) {
            // For other dashboards, load departments if filter is shown
            await this.loadDepartments();
        } else if (this.config.initialDataMethod) {
            // Custom data loading method
            await this.loadUserDepartment();
        }

        // Load projects (if not already loaded by loadDepartments for department dashboard)
        // For department dashboard, projects are already loaded in loadDepartments()
        // For collector dashboards, allow all projects without department selection
        // For others, only load if department is selected
        if (this.dashboardType === 'collector') {
            await this.loadProjects();
        } else if (this.dashboardType !== 'department' && (this.state.selectedDepartment || !this.config.showDepartmentFilter)) {
            await this.loadProjects();
        }

        // Load villages if project is selected
        if (this.state.selectedProject) {
            await this.loadVillages();

            // Restore village title from loaded list (includes village_code when present)
            if (this.state.selectedVillage && this.state.villages.length > 0) {
                const village = this.state.villages.find(v => v.id === this.state.selectedVillage);
                if (village) {
                    const title = this._formatVillageTitle(village);
                    this.state.selectedVillageName = title;
                    localStorage.setItem(`${localStoragePrefix}_village_name`, title || "");
                } else {
                    this.state.selectedVillageName = null;
                }
            } else {
                this.state.selectedVillageName = null;
            }
        }
    }

    async loadUserDepartment() {
        try {
            const userDepartment = await this.orm.call(
                "bhuarjan.dashboard",
                this.config.initialDataMethod,
                []
            );

            if (userDepartment) {
                const deptId = userDepartment.id || (Array.isArray(userDepartment) && userDepartment[0]?.id);
                const deptName = userDepartment.name || (Array.isArray(userDepartment) && userDepartment[0]?.name);
                const deptCode = userDepartment.code || (Array.isArray(userDepartment) && userDepartment[0]?.code) || "";

                if (deptId) {
                    const deptRow = this._normalizeDepartmentRow({
                        id: deptId,
                        name: deptName || `Department ${deptId}`,
                        code: deptCode,
                    });
                    this.state.selectedDepartment = deptId;
                    this.state.departments = [deptRow];
                }
            }
        } catch (error) {
            console.error("Error loading user department:", error);
        }
    }

    async loadDepartments() {
        try {
            const departments = await this.orm.call("bhuarjan.dashboard", "get_all_departments", []);
            const departmentsArray = Array.isArray(departments) ? departments : [];
            const departmentsWithSurveyCount = await Promise.all(
                departmentsArray.map(async (department) => {
                    let surveyCount = 0;
                    try {
                        surveyCount = await this.orm.searchCount("bhu.survey", [
                            ["project_id.department_id", "=", department.id],
                        ]);
                    } catch (error) {
                        console.warn(`Could not load survey count for department ${department.id}`, error);
                    }
                    return this._normalizeDepartmentRow({
                        ...department,
                        survey_count: surveyCount,
                    });
                })
            );
            this.state.departments = departmentsWithSurveyCount.sort((a, b) => (b.survey_count || 0) - (a.survey_count || 0));
            // Auto-select department for department users (they only have one department)
            if (this.dashboardType === 'department' && this.state.departments.length === 1) {
                this.state.selectedDepartment = this.state.departments[0].id;
                this.state.selectedDepartmentName = this._formatDepartmentTitle(this.state.departments[0]);
                // Save to localStorage
                const prefix = this.config.localStoragePrefix;
                localStorage.setItem(`${prefix}_department`, String(this.state.selectedDepartment));
                // Auto-load projects after department selection
                await this.loadProjects();
            }
        } catch (error) {
            console.error("Error loading departments:", error);
            this.state.departments = [];
        }
    }

    async loadProjects() {
        // Get department ID from state
        // For department dashboard, use selectedDepartment even if filter is hidden
        const departmentId = this.state.selectedDepartment || null;

        // For most dashboards, if department filter is shown and no department is selected, clear projects
        // When the department filter is shown, wait for a selection so the project dropdown
        // only lists projects of that department (see get_user_projects(..., department_id)).
        // Collector / department dashboards use different flows.
        if (departmentId === null && this.config.showDepartmentFilter && !['department', 'collector'].includes(this.dashboardType)) {
            this.state.projects = [];
            return;
        }

        try {
            // Pass departmentId to get_user_projects to filter projects by department
            const projects = await this.orm.call(
                "bhuarjan.dashboard",
                "get_user_projects",
                [departmentId]
            );

            // Ensure we have an array
            const projectsArray = Array.isArray(projects) ? projects : [];
            const projectsWithSurveyCount = await Promise.all(
                projectsArray.map(async (project) => {
                    let surveyCount = 0;
                    try {
                        surveyCount = await this.orm.searchCount("bhu.survey", [
                            ["project_id", "=", project.id]
                        ]);
                    } catch (error) {
                        console.warn(`Could not load survey count for project ${project.id}`, error);
                    }
                    return {
                        ...project,
                        survey_count: surveyCount,
                    };
                })
            );
            this.state.projects = projectsWithSurveyCount.sort((a, b) => (b.survey_count || 0) - (a.survey_count || 0));
            if (this.state.selectedProject) {
                const sel = this.state.projects.find((p) => p.id === this.state.selectedProject);
                if (sel) {
                    const title = this._formatProjectTitle(sel);
                    const code = this._formatProjectCode(sel);
                    this.state.selectedProjectName = title;
                    this.state.selectedProjectCode = code;
                    localStorage.setItem(`${this.config.localStoragePrefix}_project_name`, title || "");
                    localStorage.setItem(`${this.config.localStoragePrefix}_project_code`, code || "");
                }
            }
        } catch (error) {
            console.error("Error loading projects:", error);
            this.state.projects = [];
        }
    }

    async loadVillages() {
        if (!this.state.selectedProject) {
            this.state.villages = [];
            return;
        }

        try {
            const villages = await this.orm.call(
                "bhuarjan.dashboard",
                "get_villages_by_project",
                [this.state.selectedProject]
            );
            const villagesArray = Array.isArray(villages) ? villages : [];
            const sortedByName = [...villagesArray].sort((a, b) => {
                const an = String(a.name || "").toLowerCase();
                const bn = String(b.name || "").toLowerCase();
                return an.localeCompare(bn) || (Number(a.id) - Number(b.id));
            });
            const villagesWithSurveyCount = await Promise.all(
                sortedByName.map(async (raw, idx) => {
                    const village = this._normalizeVillageRow(raw, idx + 1);
                    let surveyCount = 0;
                    try {
                        surveyCount = await this.orm.searchCount("bhu.survey", [
                            ["project_id", "=", this.state.selectedProject],
                            ["village_id", "=", village.id],
                        ]);
                    } catch (error) {
                        console.warn(`Could not load survey count for village ${village.id}`, error);
                    }
                    return {
                        ...village,
                        survey_count: surveyCount,
                    };
                })
            );
            this.state.villages = villagesWithSurveyCount.sort((a, b) => (b.survey_count || 0) - (a.survey_count || 0));
            if (this.state.selectedVillage) {
                const sel = this.state.villages.find((v) => v.id === this.state.selectedVillage);
                if (sel) {
                    const title = this._formatVillageTitle(sel);
                    this.state.selectedVillageName = title;
                    localStorage.setItem(`${this.config.localStoragePrefix}_village_name`, title || "");
                }
            }
        } catch (error) {
            console.error("Error loading villages:", error);
            this.state.villages = [];
        }
    }

    async loadDashboardData() {
        try {
            this.state.loading = true;

            const stats = await this.orm.call(
                "bhuarjan.dashboard",
                "get_dashboard_stats",
                [
                    this.state.selectedDepartment || null,
                    this.state.selectedProject || null,
                    this.state.selectedVillage || null
                ]
            );

            if (stats) {
                // Map backend stats to frontend state using configuration
                this._mapStatsToState(stats);

                // Set additional flags
                if (stats.is_collector !== undefined) {
                    this.state.isCollector = stats.is_collector;
                }
                if (stats.is_sdm !== undefined) {
                    this.state.isSDM = stats.is_sdm;
                }
                if (stats.is_admin !== undefined) {
                    this.state.isAdmin = stats.is_admin;
                }
                if (stats.is_project_exempt !== undefined) {
                    this.state.isProjectExempt = stats.is_project_exempt;
                }
                if (stats.is_displacement !== undefined) {
                    this.state.isDisplacement = stats.is_displacement;
                }
                if (stats.user_type !== undefined) {
                    this.state.isAdmin = (stats.user_type === 'admin');
                }
                // Store allowed section names from project's law
                if (stats.allowed_section_names !== undefined) {
                    this.state.allowedSectionNames = stats.allowed_section_names || [];
                }
            }

        } catch (error) {
            console.error("Error loading dashboard stats:", error);
            this.notification.add(_t("Error loading dashboard data"), { type: "danger" });
        } finally {
            this.state.loading = false;
            // Ensure highlights are re-applied after async data refresh and rerender.
            setTimeout(() => this._applySectionActivityHighlights(), 0);
        }
    }

    _mapStatsToState(backendStats) {
        // Map backend stats to frontend state using configuration mapping
        const mapping = this.config.statsMapping || {};

        for (const [backendKey, frontendKey] of Object.entries(mapping)) {
            if (backendKey in backendStats) {
                this.state.stats[frontendKey] = backendStats[backendKey] || 0;
            }
        }

        // Handle info objects separately (they're not in the mapping)
        if (backendStats.survey_info) {
            this.state.stats.survey_info = backendStats.survey_info;
        }
        if (backendStats.section4_info) {
            this.state.stats.section4_info = backendStats.section4_info;
        }
        if (backendStats.section11_info) {
            this.state.stats.section11_info = backendStats.section11_info;
        }
        if (backendStats.section15_info) {
            this.state.stats.section15_info = backendStats.section15_info;
        }
        if (backendStats.section19_info) {
            this.state.stats.section19_info = backendStats.section19_info;
        }
        if (backendStats.expert_info) {
            this.state.stats.expert_info = backendStats.expert_info;
        }
        if (backendStats.sia_info) {
            this.state.stats.sia_info = backendStats.sia_info;
        }
        if (backendStats.section8_info) {
            this.state.stats.section8_info = backendStats.section8_info;
        }
        if (backendStats.draft_award_info) {
            this.state.stats.draft_award_info = backendStats.draft_award_info;
        }
        if (backendStats.section23_award_info) {
            this.state.stats.section23_award_info = backendStats.section23_award_info;
        }
    }

    async onDepartmentChange(ev) {
        if (!this.config.showDepartmentFilter) return;
        const value = ev.target.value;
        const departmentId = value && value !== '' ? parseInt(value, 10) : null;
        await this.applyDepartmentSelection(departmentId);
    }

    async onDepartmentPick(departmentId) {
        if (!this.config.showDepartmentFilter) {
            return;
        }
        this.closeDepartmentDropdown();
        await this.applyDepartmentSelection(departmentId);
    }

    async applyDepartmentSelection(departmentId) {
        this.state.selectedDepartment = departmentId;

        // Save to localStorage
        const prefix = this.config.localStoragePrefix;
        if (departmentId) {
            localStorage.setItem(`${prefix}_department`, String(departmentId));
        } else {
            localStorage.removeItem(`${prefix}_department`);
        }

        // Reset project and village when department changes
        this.state.selectedProject = null;
        this.state.selectedProjectName = null;
        this.state.selectedProjectCode = null;
        this.state.selectedVillage = null;
        this.state.selectedVillageName = null;
        this.state.projects = [];
        this.state.villages = [];
        localStorage.removeItem(`${prefix}_project`);
        localStorage.removeItem(`${prefix}_project_name`);
        localStorage.removeItem(`${prefix}_project_code`);
        localStorage.removeItem(`${prefix}_village`);
        localStorage.removeItem(`${prefix}_village_name`);

        // Load projects for the selected department
        if (departmentId) {
            try {
                await this.loadProjects();
            } catch (error) {
                console.error("Error in loadProjects after department change:", error);
            }
        }

        await this.loadDashboardData();
    }

    async onProjectChange(ev) {
        if (!this.config.showProjectFilter) return;
        const value = ev.target.value;
        const projectId = value ? parseInt(value, 10) : null;
        await this.applyProjectSelection(projectId);
    }

    async onProjectPick(projectId) {
        if (!this.config.showProjectFilter) {
            return;
        }
        await this.applyProjectSelection(projectId);
    }

    async applyProjectSelection(projectId) {
        this.state.selectedProject = projectId;

        // Save to localStorage
        const prefix = this.config.localStoragePrefix;
        if (projectId) {
            localStorage.setItem(`${prefix}_project`, String(projectId));
            const project = this.state.projects.find(p => p.id === projectId);
            this.state.selectedProjectName = project ? this._formatProjectTitle(project) : null;
            this.state.selectedProjectCode = project ? this._formatProjectCode(project) : null;
            if (this.state.selectedProjectName) {
                localStorage.setItem(`${prefix}_project_name`, this.state.selectedProjectName);
            }
            if (this.state.selectedProjectCode) {
                localStorage.setItem(`${prefix}_project_code`, this.state.selectedProjectCode);
            }
        } else {
            localStorage.removeItem(`${prefix}_project`);
            localStorage.removeItem(`${prefix}_project_name`);
            localStorage.removeItem(`${prefix}_project_code`);
            this.state.selectedProjectName = null;
            this.state.selectedProjectCode = null;
        }

        // Check if current village belongs to new project
        if (projectId) {
            await this.loadVillages();
            const currentVillage = this.state.villages.find(v => v.id === this.state.selectedVillage);
            if (!currentVillage) {
                this.state.selectedVillage = null;
                this.state.selectedVillageName = null;
                localStorage.removeItem(`${prefix}_village`);
                localStorage.removeItem(`${prefix}_village_name`);
            } else {
                // Update village title if village still exists in new project
                this.state.selectedVillageName = this._formatVillageTitle(currentVillage);
                localStorage.setItem(`${prefix}_village_name`, this.state.selectedVillageName || "");
            }
        } else {
            this.state.selectedVillage = null;
            this.state.selectedVillageName = null;
            this.state.villages = [];
            localStorage.removeItem(`${prefix}_village`);
            localStorage.removeItem(`${prefix}_village_name`);
        }

        // Save selection to server for bulk approval
        await this.saveDashboardSelection();

        await this.loadDashboardData();
    }

    async onVillageChange(ev) {
        if (!this.config.showVillageFilter) return;
        const value = ev.target.value;
        const villageId = value ? parseInt(value, 10) : null;
        await this.applyVillageSelection(villageId);
    }

    async onVillagePick(villageId) {
        if (!this.config.showVillageFilter) {
            return;
        }
        await this.applyVillageSelection(villageId);
    }

    async applyVillageSelection(villageId) {
        this.state.selectedVillage = villageId;

        // Get and save village name
        const prefix = this.config.localStoragePrefix;
        if (villageId) {
            localStorage.setItem(`${prefix}_village`, String(villageId));
            const village = this.state.villages.find(v => v.id === villageId);
            if (village) {
                const title = this._formatVillageTitle(village);
                this.state.selectedVillageName = title;
                localStorage.setItem(`${prefix}_village_name`, title || "");
            }
        } else {
            localStorage.removeItem(`${prefix}_village`);
            localStorage.removeItem(`${prefix}_village_name`);
            this.state.selectedVillageName = null;
        }

        // Save selection to server for bulk approval
        await this.saveDashboardSelection();

        await this.loadDashboardData();
    }

    async onSubmitFilters() {
        await this.loadDashboardData();
    }

    async saveDashboardSelection() {
        /**
         * Save the current dashboard selection (project and village) to the server
         * This allows the bulk approval wizard to retrieve these values
         */
        try {
            await this.orm.call(
                "bhuarjan.dashboard",
                "save_dashboard_selection",
                [this.state.selectedProject || false, this.state.selectedVillage || false]
            );
        } catch (error) {
            console.error("Error saving dashboard selection:", error);
        }
    }

    async downloadForm10() {
        /**
         * Open Form 10 download wizard with pre-filled project and village
         */
        if (!this.state.selectedProject) {
            this.notification.add(_t("Please select a project first"), { type: "warning" });
            return;
        }

        if (!this.state.selectedVillage) {
            this.notification.add(_t("Please select a village first"), { type: "warning" });
            return;
        }

        try {
            await this.action.doAction({
                type: 'ir.actions.act_window',
                name: 'Download Form 10',
                res_model: 'report.wizard',
                view_mode: 'form',
                views: [[false, 'form']],
                target: 'new',
                context: {
                    'default_project_id': this.state.selectedProject,
                    'default_village_id': this.state.selectedVillage,
                    'default_export_type': 'excel',  // Default to Excel export
                },
            });
        } catch (error) {
            console.error("Error opening Form 10 download wizard:", error);
        }
    }

    async downloadGanttChart() {
        if (!this.state.selectedProject) {
            this.notification.add(_t("Please select a project first"), { type: "warning" });
            return;
        }

        try {
            // Create wizard record
            const wizardId = await this.orm.create("bhuarjan.gantt.report.wizard", [{
                project_id: parseInt(this.state.selectedProject)
            }]);

            // Call method to get download action
            const action = await this.orm.call("bhuarjan.gantt.report.wizard", "action_download_report", [wizardId]);

            // Execute action
            await this.action.doAction(this._normalizeRpcActWindow(action));

        } catch (error) {
            console.error("Error generating Gantt report:", error);
            this.notification.add(_t("Error generating report"), { type: "danger" });
        }
    }

    // Helper methods for domain building
    getDomain(model = null) {
        const domain = [];

        // Models that have department_id field
        const modelsWithDepartment = [
            'bhu.project',
            'bhu.section4.notification',
            'bhu.survey',
            'bhu.section23.award',
            'bhu.draft.award',  // Legacy, keeping for compatibility
            'bhu.payment.file',
            'bhu.payment.reconciliation.bank',
            'bhu.payment.reconciliation.bank.line',
            'bhu.section8',
        ];

        // Only add department_id if model has this field
        const deptId = parseInt(this.state.selectedDepartment);
        if (!isNaN(deptId) && this.state.selectedDepartment && (!model || modelsWithDepartment.includes(model))) {
            domain.push(['department_id', '=', deptId]);
        }

        const projectId = parseInt(this.state.selectedProject);
        if (!isNaN(projectId) && this.state.selectedProject) {
            domain.push(['project_id', '=', projectId]);
        }

        // Models that have village_id field and should be filtered by village selection
        const modelsWithVillage = [
            'bhu.survey',
            'bhu.section4.notification',
            'bhu.section11.preliminary.report',
            'bhu.section15.objection',
            'bhu.section19.notification',
            'bhu.section21.notification',
            'bhu.section23.award',
            'bhu.payment.voucher',
            'bhu.payment.voucher.export',
            'bhu.section20a.railways',
            'bhu.section20d.railways',
            'bhu.section20e.railways',
            'bhu.section3a.nh',
            'bhu.section3c.nh',
            'bhu.section3d.nh',
            'bhu.payment.file',
            'bhu.payment.voucher',
            'bhu.payment.reconciliation.bank',
            'bhu.payment.reconciliation.bank.line',
            'bhu.section8',
        ];

        const villageId = parseInt(this.state.selectedVillage);
        if (!isNaN(villageId) && this.state.selectedVillage && (!model || modelsWithVillage.includes(model))) {
            domain.push(['village_id', '=', villageId]);
        }
        return domain;
    }

    checkProjectSelected() {
        if (!this.state.selectedProject) {
            this.notification.add(_t("Please select a project first"), { type: "warning" });
            return false;
        }
        return true;
    }

    // Action methods (can be overridden by specific dashboard types)
    /** Odoo 18 doAction expects ir.actions.act_window.views; RPC payloads skip server generate_views. */
    _normalizeRpcActWindow(action) {
        if (!action || action.type !== "ir.actions.act_window") {
            return action;
        }
        let views = action.views;
        if (!Array.isArray(views) || views.length === 0) {
            const rawVm = action.view_mode || "list,form";
            const modes = String(rawVm)
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean);
            views = modes.length ? modes.map((m) => [false, m]) : [
                [false, "list"],
                [false, "form"],
            ];
            return { ...action, views };
        }
        return action;
    }

    async openAction(actionName) {
        try {
            const action = await this.orm.call("bhuarjan.dashboard", actionName, []);
            if (action && action.type) {
                await this.action.doAction(this._normalizeRpcActWindow(action));
            }
        } catch (error) {
            console.error(`Error opening ${actionName}:`, error);
            this.notification.add(_t("Error: " + (error.message || actionName)), { type: "danger" });
        }
    }

    async openDocumentVaultNavigator() {
        try {
            const action = await this.orm.call(
                "bhuarjan.dashboard",
                "action_open_document_vault_navigator",
                [],
                {
                    context: {
                        active_department_id: this.state.selectedDepartment || false,
                        active_project_id: this.state.selectedProject || false,
                        active_village_id: this.state.selectedVillage || false,
                    },
                }
            );
            if (action && action.type) {
                await this.action.doAction(this._normalizeRpcActWindow(action));
            }
        } catch (error) {
            console.error("Error opening Doc Vault Viewer:", error);
            this.notification.add(_t("Error opening Doc Vault Viewer: ") + (error.message || ""), {
                type: "danger",
            });
        }
    }

    async openSectionList(model) {
        if (!this.checkProjectSelected()) {
            return;
        }

        // Special handling for R and R Scheme - open form directly (one per project)
        if (model === 'bhu.section18.rr.scheme') {
            await this.openRRSchemeForm();
            return;
        }

        // Payment File — bank exports (multiple per voucher; one voucher per award)
        if (model === 'bhu.payment.file') {
            if (!this.state.selectedVillage) {
                this.notification.add(_t("Please select a village first before viewing Payment File."), {
                    type: "warning",
                    sticky: true,
                });
                return;
            }
            const domain = this.getDomain('bhu.payment.voucher.export');
            await this.action.doAction({
                type: 'ir.actions.act_window',
                name: _t('Generated Payment Files'),
                res_model: 'bhu.payment.voucher.export',
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                domain,
                target: 'current',
                context: {
                    create: false,
                },
            });
            return;
        }

        // Payment Voucher — open voucher if it exists; do not show empty list when only award exists
        if (model === "bhu.payment.voucher") {
            await this.viewPaymentVoucherFromDashboard();
            return;
        }

        const domain = this.getDomain(model);
        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: this.getSectionName(model),
            res_model: model,
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                'default_project_id': this.state.selectedProject || false,
                'default_village_id': this.state.selectedVillage || false,
            },
        });
    }

    // Open first document in form view with pagination (for View button)
    async openFirstDocument(sectionModel, sectionInfo) {
        if (!this.checkProjectSelected()) {
            return;
        }

        if (sectionModel === "bhu.payment.file") {
            await this.openSectionList("bhu.payment.file");
            return;
        }

        const domain = this.getDomain(sectionModel);

        // Try to get first pending, otherwise first document
        let recordId = false;
        if (sectionInfo) {
            if (sectionInfo.first_pending_id) {
                recordId = sectionInfo.first_pending_id;
            } else if (sectionInfo.first_document_id) {
                recordId = sectionInfo.first_document_id;
            }
        }

        const sectionName = this.getSectionName(sectionModel);

        if (recordId) {
            // If only 1 document, open directly in form view, otherwise use list,form for pagination
            const totalCount = sectionInfo ? (sectionInfo.total || 0) : 0;
            const viewMode = totalCount === 1 ? "form" : "list,form";
            const views = totalCount === 1 ? [[false, "form"]] : [[false, "list"], [false, "form"]];

            await this.action.doAction({
                type: "ir.actions.act_window",
                name: sectionName,
                res_model: sectionModel,
                res_id: recordId,
                view_mode: viewMode,
                views: views,
                domain: domain,
                target: "current",
                context: {
                    'default_project_id': this.state.selectedProject || false,
                    'default_village_id': this.state.selectedVillage || false,
                    'active_project_id': this.state.selectedProject || false,
                    'active_village_id': this.state.selectedVillage || false,
                },
            });
        } else {
            // No documents, open list view
            await this.openSectionList(sectionModel);
        }
    }

    /** Extract readable text from Odoo RPC / UserError (not the generic "Odoo Server Error" title). */
    _rpcErrorMessage(error, fallback) {
        const data = error?.data || error?.cause?.data;
        const fromArgs = Array.isArray(data?.arguments) && data.arguments[0];
        if (typeof fromArgs === "string" && fromArgs.trim()) {
            return fromArgs;
        }
        if (typeof data?.message === "string" && data.message.trim() && data.message !== "Odoo Server Error") {
            return data.message;
        }
        if (typeof error?.message === "string" && error.message.trim() && error.message !== "Odoo Server Error") {
            return error.message;
        }
        return fallback || _t("Something went wrong. Please try again.");
    }

    _notifyPaymentVoucherBlocked(message) {
        this.notification.add(message, {
            title: _t("Payment Voucher"),
            type: "danger",
            sticky: true,
        });
    }

    async _validatePaymentVoucherPrerequisites(projectId, villageId) {
        const awards = await this.orm.searchRead(
            "bhu.section23.award",
            [
                ["project_id", "=", projectId],
                ["village_id", "=", villageId],
            ],
            ["id", "name", "rr_generated"],
            { limit: 1 }
        );
        if (!awards.length) {
            this._notifyPaymentVoucherBlocked(
                _t(
                    "Cannot create a Payment Voucher yet.\n\n" +
                        "Complete Step 11 — Section 23 Award for the selected project and village first.\n" +
                        "After the award is saved, generate the R&R award on that form, then return here and click Create.\n\n" +
                        "अभी भुगतान वाउचर नहीं बनाया जा सकता। कृपया पहले चरण 11 — धारा 23 अवार्ड बनाएं, फिर R&R जेनरेट करें।"
                )
            );
            return false;
        }
        if (!awards[0].rr_generated) {
            this._notifyPaymentVoucherBlocked(
                _t(
                    "Cannot create a Payment Voucher yet.\n\n" +
                        "Step 11 — Section 23 Award exists, but R&R has not been generated.\n" +
                        "Open that award, generate the R&R award, then click Create on Payment Voucher again.\n\n" +
                        "धारा 23 अवार्ड मौजूद है, पर R&R अभी जेनरेट नहीं हुआ है। कृपया अवार्ड खोलकर R&R जेनरेट करें।"
                )
            );
            return false;
        }
        return true;
    }

    /** Create or reopen the single payment voucher for this award (dashboard Step 12 → Create). */
    async createPaymentVoucherFromDashboard() {
        if (!this.checkProjectSelected()) {
            return;
        }
        if (!this.state.selectedVillage) {
            this.notification.add(_t("Please select a village first before creating a Payment Voucher."), {
                title: _t("Payment Voucher"),
                type: "warning",
                sticky: true,
            });
            return;
        }
        const projectId = parseInt(this.state.selectedProject, 10);
        const villageId = parseInt(this.state.selectedVillage, 10);
        if (isNaN(projectId) || isNaN(villageId)) {
            this.notification.add(_t("Please select a project and village."), { type: "warning" });
            return;
        }
        if (!(await this._validatePaymentVoucherPrerequisites(projectId, villageId))) {
            return;
        }
        try {
            const action = await this.orm.call(
                "bhuarjan.dashboard",
                "action_create_payment_voucher_from_dashboard",
                [projectId, villageId]
            );
            await this.action.doAction(this._normalizeRpcActWindow(action));
        } catch (error) {
            this._notifyPaymentVoucherBlocked(
                this._rpcErrorMessage(
                    error,
                    _t(
                        "Could not create the payment voucher. Complete Section 23 Award and generate R&R first."
                    )
                )
            );
        }
    }

    /** View/Edit — open voucher form/list, or explain when only the award exists. */
    async viewPaymentVoucherFromDashboard() {
        if (!this.checkProjectSelected()) {
            return;
        }
        if (!this.state.selectedVillage) {
            this.notification.add(_t("Please select a village first."), {
                title: _t("Payment Voucher"),
                type: "warning",
                sticky: true,
            });
            return;
        }
        const projectId = parseInt(this.state.selectedProject, 10);
        const villageId = parseInt(this.state.selectedVillage, 10);
        if (isNaN(projectId) || isNaN(villageId)) {
            return;
        }

        const vouchers = await this.orm.searchRead(
            "bhu.payment.voucher",
            [
                ["project_id", "=", projectId],
                ["village_id", "=", villageId],
            ],
            ["id", "name"],
            { limit: 2, order: "id desc" }
        );

        if (vouchers.length === 1) {
            await this.action.doAction({
                type: "ir.actions.act_window",
                name: _t("Payment Voucher"),
                res_model: "bhu.payment.voucher",
                res_id: vouchers[0].id,
                view_mode: "form",
                views: [[false, "form"]],
                target: "current",
            });
            return;
        }
        if (vouchers.length > 1) {
            await this.action.doAction({
                type: "ir.actions.act_window",
                name: _t("Payment Vouchers"),
                res_model: "bhu.payment.voucher",
                view_mode: "list,form",
                views: [[false, "list"], [false, "form"]],
                domain: [
                    ["project_id", "=", projectId],
                    ["village_id", "=", villageId],
                ],
                target: "current",
                context: { create: false },
            });
            return;
        }

        const awards = await this.orm.searchRead(
            "bhu.section23.award",
            [
                ["project_id", "=", projectId],
                ["village_id", "=", villageId],
            ],
            ["id", "name", "rr_generated"],
            { limit: 1 }
        );
        if (!awards.length) {
            this._notifyPaymentVoucherBlocked(
                _t(
                    "No Payment Voucher to view.\n\n" +
                        "Create Step 11 — Section 23 Award for this village first, then generate R&R, then click Create here."
                )
            );
            return;
        }
        if (!awards[0].rr_generated) {
            this.notification.add(
                _t(
                    "No Payment Voucher yet. Open the Section 23 award and generate R&R first, then click Create on Payment Voucher."
                ),
                { title: _t("Payment Voucher"), type: "warning", sticky: true }
            );
            await this.action.doAction({
                type: "ir.actions.act_window",
                name: _t("Section 23 Award"),
                res_model: "bhu.section23.award",
                res_id: awards[0].id,
                view_mode: "form",
                views: [[false, "form"]],
                target: "current",
            });
            return;
        }

        this.notification.add(
            _t(
                "No Payment Voucher has been created yet for this village.\n\n" +
                    "Click Create on Payment Voucher to generate it from the Section 23 award."
            ),
            { title: _t("Payment Voucher"), type: "info", sticky: true }
        );
    }

    /** Open existing payment voucher form (when already created). */
    async openPaymentVoucherFromDashboard() {
        if (!this.checkProjectSelected()) {
            return;
        }
        if (!this.state.selectedVillage) {
            this.notification.add(_t("Please select a village first."), {
                title: _t("Payment Voucher"),
                type: "warning",
                sticky: true,
            });
            return;
        }
        const projectId = parseInt(this.state.selectedProject, 10);
        const villageId = parseInt(this.state.selectedVillage, 10);
        if (isNaN(projectId) || isNaN(villageId)) {
            this.notification.add(_t("Please select a project and village."), { type: "warning" });
            return;
        }
        try {
            const action = await this.orm.call(
                "bhuarjan.dashboard",
                "action_open_payment_voucher_from_dashboard",
                [projectId, villageId]
            );
            await this.action.doAction(this._normalizeRpcActWindow(action));
        } catch (error) {
            this._notifyPaymentVoucherBlocked(
                this._rpcErrorMessage(error, _t("No payment voucher is available for this village yet."))
            );
        }
    }

    // Create new record for a section
    async createSectionRecord(sectionModel) {
        if (!this.checkProjectSelected()) {
            return;
        }

        // District admin cannot create records - read-only mode
        if (this.config.isReadOnly) {
            this.notification.add(_t("District Admin can only view data. Cannot create records."), {
                type: "warning",
                sticky: false
            });
            return;
        }

        // Payment Voucher → create draft R&R voucher from Section 23 award
        if (sectionModel === "bhu.payment.voucher") {
            await this.createPaymentVoucherFromDashboard();
            return;
        }

        // Payment File — multiple bank files per voucher; generate from voucher form
        if (sectionModel === "bhu.payment.file") {
            this.notification.add(
                _t(
                    "One voucher per award. Open Payment Voucher, then use Generate payment file on the voucher — you can create several files for the same voucher."
                ),
                { type: "info", sticky: true }
            );
            return;
        }

        // Special handling for R and R Scheme - open form directly (one per project)
        if (sectionModel === 'bhu.section18.rr.scheme') {
            await this.openRRSchemeForm();
            return;
        }

        // Village-specific sections that require village selection
        const villageSpecificSections = {
            'bhu.section4.notification': 'Section 4 Notification',
            'bhu.section11.preliminary.report': 'Section 11 Preliminary Report',
            'bhu.section19.notification': 'Section 19 Notification',
            'bhu.section21.notification': 'Section 21 Notification',
            'bhu.section23.award': 'Award',
            'bhu.section20a.railways': 'Section 20 A (Railways)',
            'bhu.section20e.railways': 'Section 20 E (Railways)',
            'bhu.section3a.nh': 'Section 3A (NH)',
            'bhu.section3d.nh': 'Section 3D (NH)',
            'bhu.payment.reconciliation.bank': 'Bank Recon',
        };

        if (villageSpecificSections[sectionModel]) {
            if (!this.state.selectedVillage) {
                this.notification.add(_t(`Please select a village first before creating ${villageSpecificSections[sectionModel]}.`), {
                    type: "warning",
                    sticky: true
                });
                return;
            }
        }

        // Section 23: one award per project+village. Open existing with message, or create on server
        // so land (survey) lines are stored immediately; tree data lives on bhu.survey and shows here.
        if (sectionModel === "bhu.section23.award") {
            const projectId = parseInt(this.state.selectedProject, 10);
            const villageId = parseInt(this.state.selectedVillage, 10);
            if (isNaN(projectId) || isNaN(villageId)) {
                this.notification.add(_t("Please select a project and village."), { type: "warning" });
                return;
            }

            // LARR only: Section 4 approval required before award (not Railway, NHAI, or CGLRC).
            if (this.requiresSection4BeforeAward()) {
                const section4Records = await this.orm.searchRead(
                    "bhu.section4.notification",
                    [
                        ["project_id", "=", projectId],
                        ["village_id", "=", villageId],
                    ],
                    ["approved_date", "signed_date", "public_hearing_date"],
                    { limit: 10 }
                );
                const hasSection4Approval = section4Records.some(r =>
                    r.approved_date || r.signed_date || r.public_hearing_date
                );
                if (!hasSection4Approval) {
                    this.notification.add(
                        _t(
                            "Section 4 notification is not approved yet for this project and village.\n" +
                            "Please get the Section 4 approved before creating the award.\n\n" +
                            "इस प्रोजेक्ट और गाँव के लिए धारा 4 की अधिसूचना अभी स्वीकृत नहीं हुई है। " +
                            "अवार्ड बनाने से पहले कृपया धारा 4 की स्वीकृति प्राप्त करें।"
                        ),
                        { type: "danger", sticky: true }
                    );
                    return;
                }
            }

            const existing = await this.orm.searchRead(
                "bhu.section23.award",
                [
                    ["project_id", "=", projectId],
                    ["village_id", "=", villageId],
                ],
                ["id", "name"],
                { limit: 1 }
            );
            if (existing.length) {
                this.notification.add(
                    _t(
                        "A Section 23 award for this project and village already exists. " +
                        "You cannot create another; opening the existing record."
                    ),
                    { type: "warning", sticky: true }
                );
                await this.action.doAction({
                    type: "ir.actions.act_window",
                    name: _t("Award"),
                    res_model: "bhu.section23.award",
                    res_id: existing[0].id,
                    view_mode: "form",
                    views: [[false, "form"]],
                    target: "current",
                });
                return;
            }
            let awardId;
            try {
                const created = await this.orm.create("bhu.section23.award", [
                    { project_id: projectId, village_id: villageId },
                ]);
                awardId = Array.isArray(created) ? created[0] : created;
            } catch (e) {
                const again = await this.orm.search("bhu.section23.award", [
                    ["project_id", "=", projectId],
                    ["village_id", "=", villageId],
                ], { limit: 1 });
                if (again.length) {
                    awardId = again[0];
                    this.notification.add(
                        _t("A Section 23 award for this project and village already exists. Opened the existing record."),
                        { type: "info" }
                    );
                } else {
                    this.notification.add(e.message || String(e), { type: "danger" });
                    return;
                }
            }
            await this.action.doAction({
                type: "ir.actions.act_window",
                name: _t("Award"),
                res_model: "bhu.section23.award",
                res_id: awardId,
                view_mode: "form",
                views: [[false, "form"]],
                target: "current",
            });
            this.notification.add(
                _t(
                    "Section 23 award is saved. Land lines are built from village surveys. " +
                    "Tree amounts follow the tree lines entered on each survey for this village."
                ),
                { type: "success", sticky: false }
            );
            return;
        }

        let context = {};
        if (this.state.selectedProject) {
            context.default_project_id = this.state.selectedProject;
        }
        if (this.state.selectedVillage) {
            context.default_village_id = this.state.selectedVillage;
        }
        if (sectionModel === "bhu.payment.voucher") {
            await this.createPaymentVoucherFromDashboard();
            return;
        }
        if (sectionModel === "bhu.payment.file") {
            this.notification.add(
                _t(
                    "One voucher per award. Open Payment Voucher, then use Generate payment file on the voucher — you can create several files for the same voucher."
                ),
                { type: "info", sticky: true }
            );
            return;
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("New Record"),
            res_model: sectionModel,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
            context: context,
        });
    }

    // Open first pending document in form view for approval/rejection
    async openFirstPending(sectionModel, pendingId, sectionInfo) {
        if (!this.checkProjectSelected()) {
            return;
        }

        if (!pendingId) {
            // No pending documents, just open list view
            await this.openSectionList(sectionModel);
            return;
        }

        const domain = this.getDomain(sectionModel);
        // Filter to only submitted records for pagination
        domain.push(["state", "=", "submitted"]);

        const sectionName = this.getSectionName(sectionModel);

        // If only 1 submitted document, open directly in form view, otherwise use list,form for pagination
        const submittedCount = sectionInfo ? (sectionInfo.submitted_count || 0) : 0;
        const viewMode = submittedCount === 1 ? "form" : "list,form";
        const views = submittedCount === 1 ? [[false, "form"]] : [[false, "list"], [false, "form"]];

        await this.action.doAction({
            type: "ir.actions.act_window",
            name: sectionName,
            res_model: sectionModel,
            res_id: pendingId,
            view_mode: viewMode,
            views: views,
            domain: domain,
            target: "current",
            context: {
                'default_project_id': this.state.selectedProject || false,
                'default_village_id': this.state.selectedVillage || false,
            },
        });
    }

    // Handle Section 8 Recommend/Not Recommend actions (for Collector)
    async openSection8ForRecommend(actionType) {
        if (!this.checkProjectSelected()) {
            return;
        }

        // Section 8 uses 'draft' as pending state
        // Find first draft record
        const domain = this.getDomain('bhu.section8');
        domain.push(['state', '=', 'draft']);

        try {
            // Find the first draft record
            const records = await this.orm.searchRead(
                'bhu.section8',
                domain,
                ['id'],
                { limit: 1, order: 'create_date asc' }
            );

            if (records && records.length > 0) {
                const recordId = records[0].id;
                console.log(`Processing Section 8 record ${recordId} with action ${actionType}`);

                const method = actionType === 'recommend' ? 'action_approve' : 'action_reject';

                try {
                    // Call the model method which returns an action (wizard)
                    const action = await this.orm.call('bhu.section8', method, [recordId]);

                    if (action && action.type) {
                        await this.action.doAction(this._normalizeRpcActWindow(action));
                    } else {
                        console.error("Method did not return a valid action:", action);
                        this.notification.add(_t("The action could not be started. Please try again."), { type: "danger" });
                    }
                } catch (callError) {
                    console.error(`Odoo call error for ${method}:`, callError);
                    const msg = callError.message || (callError.data && callError.data.message) || _t("Server error while processing action");
                    this.notification.add(msg, { type: "danger" });
                }
            } else {
                this.notification.add(_t("No draft Section 8 records found to process for the selected filters."), { type: "warning" });
            }
        } catch (error) {
            console.error(`General error in openSection8ForRecommend:`, error);
            this.notification.add(_t("Error accessing Section 8 data"), { type: "danger" });
        }
    }

    // Open R and R Scheme form directly (one per project)
    async openRRSchemeForm() {
        if (!this.checkProjectSelected()) {
            return;
        }

        try {
            const action = await this.orm.call(
                'bhu.section18.rr.scheme',
                'action_open_rr_scheme_form',
                [this.state.selectedProject]
            );
            if (action && action.type) {
                await this.action.doAction(this._normalizeRpcActWindow(action));
            }
        } catch (error) {
            console.error('Error opening R and R Scheme:', error);
            // Fallback to list view
            await this.action.doAction({
                type: "ir.actions.act_window",
                name: "Section 18 R and R Scheme",
                res_model: 'bhu.section18.rr.scheme',
                view_mode: "list,form",
                views: [[false, "list"], [false, "form"]],
                target: "current",
            });
        }
    }

    // Check if all items in a section are approved
    isAllApproved(sectionInfo) {
        if (!sectionInfo) {
            return true;
        }
        // Check if all are approved (no submitted or draft)
        return sectionInfo.submitted_count === 0 && sectionInfo.draft_count === 0;
    }

    // Open surveys filtered by state (for department dashboard)
    async openSurveysByState(state) {
        let domain = this.getDomain('bhu.survey');  // Survey has department_id

        // Add state filter if provided
        if (state === 'draft') {
            domain.push(['state', '=', 'draft']);
        } else if (state === 'submitted') {
            domain.push(['state', '=', 'submitted']);
        } else if (state === 'approved') {
            domain.push(['state', '=', 'approved']);
        } else if (state === 'rejected') {
            domain.push(['state', '=', 'rejected']);
        }
        // If state is null, show all surveys (no additional filter)

        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: state ? `${state.charAt(0).toUpperCase() + state.slice(1)} Surveys` : 'All Surveys',
            res_model: 'bhu.survey',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                'default_project_id': this.state.selectedProject || false,
                'default_village_id': this.state.selectedVillage || false,
                'active_project_id': this.state.selectedProject || false,
                'active_village_id': this.state.selectedVillage || false,
            },
        });
    }

    // Get section name from model
    getSectionName(model) {
        const names = {
            'bhu.survey': 'Surveys',
            'bhu.section4.notification': 'Section 4 Notifications',
            'bhu.section11.preliminary.report': 'Section 11 Reports',
            'bhu.section15.objection': 'Section 15 Objections',
            'bhu.section19.notification': 'Section 19 Notifications',
            'bhu.expert.committee.report': 'Expert Committee Reports',
            'bhu.sia.team': 'SIA Teams',
            'bhu.section18.rr.scheme': 'Section 18 R and R Scheme',
            'bhu.section21.notification': 'Section 21 Notifications',
            'bhu.section23.award': 'Award',
            'bhu.section20a.railways': 'Section 20 A (Railways)',
            'bhu.section20e.railways': 'Section 20 E (Railways)',
            'bhu.section3a.nh': 'Section 3A (NH)',
            'bhu.section3d.nh': 'Section 3D (NH)',
            'bhu.payment.voucher': 'Payment Voucher',
            'bhu.payment.file': 'Payment File',
            'bhu.payment.reconciliation.bank': 'Bank Recon',
            'bhu.payment.reconciliation.bank.line': 'Payment Lines',
        };
        return names[model] || model;
    }

    // Mapping between dashboard section display names and section master names
    getSectionMasterName(dashboardSectionName) {
        const mapping = {
            'Surveys': 'Surveys',
            'Create SIA Team': '(Sec 4) Create SIA Team',  // Map to backend name (with Sec 4 prefix)
            '(Sec 4) Create SIA Team': '(Sec 4) Create SIA Team',
            '(Sec 4) Section 4 Notifications': '(Sec 4) Section 4 Notifications',
            'Expert Group': 'Expert Group',
            'Section 8': 'Section 8',
            'Section 11 Notifications': 'Section 11 Notifications',
            '(Sec 15) Objections': '(Sec 15) Objections',
            'Section 18 R and R Scheme': 'Section 18 R and R Scheme',
            '(Sec 19) Section 19 Notifications': '(Sec 19) Section 19 Notifications',
            'Award': 'Section 23 Award',
            'Sec 21 notice': 'Sec 21 notice',
            'Section 23 Award': 'Section 23 Award',
            'Sec 20 A (Railways)': 'Sec 20 A (Railways)',
            'Sec 20 E (Railways)': 'Sec 20 E (Railways)',
            'Sec 3A (NH)': 'Sec 3A (NH)',
            'Sec 3D (NH)': 'Sec 3D (NH)',
            'Mutual Consent': 'आपसी सहमति की क्रय नीति (Only in रायगढ़ and पसौर)',
            'Payment Voucher': 'Payment Voucher',
            'Payment File': 'Payment File',
            'Payment Reconciliation': 'Payment Reconciliation',
            'Bank Recon': 'Payment Reconciliation',
            'Personal Notice generation (247.1)': 'Personal Notice generation (247.1)',
            'Istehar प्रकाशन (247.2)': 'Istehar प्रकाशन (247.2)',
            'Award (247.3)': 'Award (247.3)',
        };
        return mapping[dashboardSectionName] || dashboardSectionName;
    }

    /** Workflow scope shown on step cards: project-wide vs village-specific. */
    sectionScopeLevel(sectionName) {
        const key = this.getSectionMasterName(sectionName || '');
        const scopes = {
            'Surveys': 'village',
            '(Sec 4) Create SIA Team': 'project',
            'Create SIA Team': 'project',
            '(Sec 4) Section 4 Notifications': 'project',
            'Expert Group': 'project',
            'Section 8': 'project',
            'Section 11 Notifications': 'project',
            '(Sec 15) Objections': 'village',
            'Section 18 R and R Scheme': 'project',
            '(Sec 19) Section 19 Notifications': 'village',
            'Sec 21 notice': 'village',
            'Section 23 Award': 'village',
            'Award': 'village',
            'Payment Voucher': 'village',
            'Payment File': 'project',
            'Payment Reconciliation': 'project',
            'Bank Recon': 'project',
            'Sec 20 A (Railways)': 'project',
            'Sec 20 E (Railways)': 'project',
            'Sec 3A (NH)': 'project',
            'Sec 3D (NH)': 'project',
            'Personal Notice generation (247.1)': 'village',
            'Istehar प्रकाशन (247.2)': 'village',
            'Award (247.3)': 'village',
            'Mutual Consent': 'village',
            'आपसी सहमति की क्रय नीति (Only in रायगढ़ and पसौर)': 'village',
        };
        return scopes[key] || scopes[sectionName] || 'project';
    }

    _extractCardSectionName(card) {
        if (card.dataset.section) {
            return card.dataset.section;
        }
        const titleEl = card.querySelector('.o_section_list_title');
        if (!titleEl) {
            return null;
        }
        const clone = titleEl.cloneNode(true);
        clone.querySelectorAll(
            '.o_section_list_context, .o_completion_tick, .o_step_scope_badge, .o_step_card_project_name, .o_section_list_title_step, .o_section_list_title_village, i, style'
        ).forEach((el) => el.remove());
        const text = clone.textContent.replace(/\s+/g, ' ').trim();
        return text || null;
    }

    isRailwayLaw() {
        const names = this.state.allowedSectionNames;
        return !!(names && names.includes('Sec 20 A (Railways)'));
    }

    isNHLaw() {
        const names = this.state.allowedSectionNames;
        return !!(names && names.includes('Sec 3A (NH)'));
    }

    /** True only for LARR: Sec 4 must exist in the project workflow and this is not Railway, NHAI, or CGLRC. */
    requiresSection4BeforeAward() {
        const names = this.state.allowedSectionNames || [];
        if (this.isRailwayLaw() || this.isNHLaw()) {
            return false;
        }
        if (names.includes('Personal Notice generation (247.1)')) {
            return false;
        }
        return names.includes('(Sec 4) Section 4 Notifications');
    }

    // Check if a section should be visible based on project's law
    getStepNumber(sectionName, defaultText) {
        if (!this.state.allowedSectionNames) {
            return defaultText;
        }

        // Check for Railways
        const isRailways = this.state.allowedSectionNames.includes('Sec 20 A (Railways)');
        if (isRailways) {
            const steps = {
                'Surveys': 'Step 1',
                'Section 23 Award': 'Step 2',
                'Payment Voucher': 'Step 3',
                'Sec 20 A (Railways)': 'Step 4',
                'Sec 20 E (Railways)': 'Step 5',
                'Payment File': 'Step 6',
                'Payment Reconciliation': 'Step 7',
                'Bank Recon': 'Step 7',
            };
            const masterName = this.getSectionMasterName(sectionName);
            if (steps[masterName]) return steps[masterName];
        }

        // Check for NH
        const isNH = this.state.allowedSectionNames.includes('Sec 3A (NH)');
        if (isNH) {
            const steps = {
                'Surveys': 'Step 1',
                'Section 23 Award': 'Step 2',
                'Payment Voucher': 'Step 3',
                'Sec 3A (NH)': 'Step 4',
                'Sec 3D (NH)': 'Step 5',
                'Payment File': 'Step 6',
                'Payment Reconciliation': 'Step 7',
                'Bank Recon': 'Step 7',
            };
            const masterName = this.getSectionMasterName(sectionName);
            if (steps[masterName]) return steps[masterName];
        }

        // Check for CGLRC 247
        const isCGLRC = this.state.allowedSectionNames.includes('Personal Notice generation (247.1)');
        if (isCGLRC) {
            const steps = {
                'Surveys': 'Step 1',
                'Personal Notice generation (247.1)': 'Step 2',
                'Istehar प्रकाशन (247.2)': 'Step 3',
                'Award (247.3)': 'Step 4',
                'Payment Voucher': 'Step 5',
                'Payment File': 'Step 6',
                'Payment Reconciliation': 'Step 7',
                'Bank Recon': 'Step 7',
            };
            const masterName = this.getSectionMasterName(sectionName);
            if (steps[masterName]) return steps[masterName];
        }

        return defaultText;
    }

    isSectionVisible(dashboardSectionName) {
        try {
            // Railway and NH sections require department to be selected
            // Check both dashboard names and mapped names
            const railwayNhSections = [
                'Sec 20 A (Railways)',
                'Sec 20 E (Railways)',
                'Sec 3A (NH)',
                'Sec 3D (NH)'
            ];

            // Check if this is a Railway or NH section
            const isRailwayNh = railwayNhSections.includes(dashboardSectionName) ||
                dashboardSectionName.includes('Railways') ||
                dashboardSectionName.includes('(NH)');

            if (isRailwayNh) {
                // For Railway and NH sections, require department to be selected
                if (!this.state || !this.state.selectedDepartment) {
                    return false;
                }
            }

            // If no project is selected, show all sections (except Railway/NH which need department)
            if (!this.state || !this.state.selectedProject) {
                return true;
            }

            // Always show payment steps and reconciliation when a project is selected
            if (
                dashboardSectionName === 'Payment Voucher' ||
                dashboardSectionName === 'Payment File' ||
                dashboardSectionName === 'Payment Reconciliation' ||
                dashboardSectionName === 'Bank Recon'
            ) {
                return true;
            }

            // If project is selected but no allowed sections configured, hide all sections
            // This prevents showing all sections when law master is not configured
            if (!this.state.allowedSectionNames || this.state.allowedSectionNames.length === 0) {
                console.warn(`Project ${this.state.selectedProject} has no law master sections configured. Hiding all sections.`);
                return false;
            }

            // Get the section master name for this dashboard section
            const sectionMasterName = this.getSectionMasterName(dashboardSectionName);

            // Check if this section is in the allowed list
            const isVisible = this.state.allowedSectionNames.includes(sectionMasterName);

            return isVisible;
        } catch (error) {
            console.error('Error in isSectionVisible:', error);
            // On error, show the section to avoid breaking the UI
            return true;
        }
    }

    toString(value) {
        return value ? String(value) : '';
    }

    _applySectionActivityHighlights() {
        const root = this.dashboardRoot.el;
        if (!root) {
            return;
        }
        const cards = root.querySelectorAll('.o_section_list_item');
        cards.forEach((card) => {
            const isCompleted = !!card.querySelector('.o_completion_tick');
            card.classList.toggle('o_has_done_ribbon', isCompleted);
            let ribbon = card.querySelector('.o_status_ribbon');
            if (!isCompleted) {
                if (ribbon) {
                    ribbon.remove();
                }
                return;
            }
            if (!ribbon) {
                ribbon = document.createElement('span');
                ribbon.className = 'o_status_ribbon o_status_ribbon_done';
                ribbon.setAttribute('aria-label', 'Completed');
                ribbon.setAttribute('title', 'Completed');
                card.appendChild(ribbon);
            }
            ribbon.textContent = '';
            ribbon.classList.add('o_status_ribbon_done');
            ribbon.classList.remove('o_status_ribbon_progress');
        });
        this._applyStepCardChrome();
        this._applyStatHighlights();
    }

    _parseStatDisplayValue(el) {
        const text = (el.textContent || '').replace(/[^\d.]/g, '');
        const num = parseFloat(text);
        return Number.isFinite(num) ? num : 0;
    }

    _applyStatHighlights() {
        const root = this.dashboardRoot.el;
        if (!root) {
            return;
        }
        root.querySelectorAll('.o_completion_percent_list, .o_count_badge').forEach((el) => {
            const hasValue = this._parseStatDisplayValue(el) > 0;
            el.classList.toggle('o_stat_has_value', hasValue);
        });
    }

    _applyStepCardChrome() {
        const root = this.dashboardRoot.el;
        if (!root) {
            return;
        }
        const projectName = this._getStepCardProjectName();
        const villageName = (this.state.selectedVillageName || '').trim();
        root.querySelectorAll('.o_section_list_item').forEach((card) => {
            this._cleanupLegacyTitleMutations(card);

            const titleEl = card.querySelector('.o_section_list_title');
            if (!titleEl) {
                return;
            }

            const sectionName = this._extractCardSectionName(card);
            const scope = this.sectionScopeLevel(sectionName);
            const hasProjectName = !!projectName;

            titleEl.classList.toggle('o_has_project_name_row', hasProjectName);
            titleEl.classList.toggle('o_step_scope_village', scope === 'village');
            titleEl.classList.toggle('o_step_scope_project', scope === 'project');
            card.classList.toggle('o_has_title_header', hasProjectName);

            if (hasProjectName) {
                titleEl.dataset.projectName = projectName;
                titleEl.dataset.villageName = villageName;
            } else {
                delete titleEl.dataset.projectName;
                delete titleEl.dataset.villageName;
            }

            const ctx = titleEl.querySelector('.o_section_list_context');
            this._configureContextDisplay(titleEl, scope, villageName, hasProjectName, ctx);
        });
    }

    _configureContextDisplay(titleEl, scope, villageName, hasProjectName, ctx) {
        if (!ctx) {
            return;
        }
        ctx.classList.remove('o_ctx_hidden_for_project', 'o_ctx_village_only');
        const home = ctx.querySelector('i.fa-home');
        if (home) {
            delete home.dataset.villageLabel;
        }
        if (!hasProjectName) {
            return;
        }
        if (scope === 'village' && villageName) {
            ctx.classList.add('o_ctx_village_only');
            if (home) {
                home.dataset.villageLabel = villageName;
            }
            return;
        }
        ctx.classList.add('o_ctx_hidden_for_project');
    }

    _cleanupLegacyTitleMutations(card) {
        try {
            const content = card.querySelector('.o_section_list_content');
            const header = card.querySelector('.o_step_card_title_row');
            if (header && content) {
                const titleInHeader = header.querySelector('.o_section_list_title');
                if (titleInHeader) {
                    content.insertBefore(titleInHeader, content.firstChild);
                }
                header.remove();
            }
            card.querySelector('.o_step_card_project_header')?.remove();

            const titleEl = card.querySelector('.o_section_list_title');
            if (!titleEl) {
                return;
            }

            titleEl.querySelector('.o_step_scope_badge')?.remove();
            titleEl.querySelector('.o_step_card_project_name')?.remove();

            const lead = titleEl.querySelector('.o_section_list_title_lead');
            if (lead && lead.parentNode === titleEl) {
                while (lead.firstChild) {
                    titleEl.insertBefore(lead.firstChild, lead);
                }
                lead.remove();
            }

            const stepWrap = titleEl.querySelector('.o_section_list_title_step');
            if (stepWrap && stepWrap.parentNode === titleEl) {
                while (stepWrap.firstChild) {
                    titleEl.insertBefore(stepWrap.firstChild, stepWrap);
                }
                stepWrap.remove();
            }

            const villageSlot = titleEl.querySelector('.o_section_list_title_village');
            if (villageSlot && villageSlot.parentNode === titleEl) {
                const ctx = villageSlot.querySelector('.o_section_list_context');
                if (ctx) {
                    titleEl.appendChild(ctx);
                }
                villageSlot.remove();
            }

            titleEl.querySelector('.o_ctx_project_code')?.remove();
            const ctx = titleEl.querySelector('.o_section_list_context');
            if (ctx) {
                ctx.hidden = false;
                ctx.classList.remove('o_ctx_hidden_for_project', 'o_ctx_village_only');
                const home = ctx.querySelector('i.fa-home');
                if (home) {
                    delete home.dataset.villageLabel;
                }
                delete ctx.dataset.projectCodeStripped;
            }
        } catch (error) {
            console.warn('BhuKhadan dashboard: skipped legacy title cleanup', error);
        }
    }

    // ── Body-level loader (works with any Odoo theme including Spiffy) ──────
    _showBodyLoader() {
        if (document.getElementById('bhu_dash_loader')) return;
        const el = document.createElement('div');
        el.id = 'bhu_dash_loader';
        el.style.cssText = 'position:fixed!important;inset:0!important;z-index:99999!important;display:flex!important;align-items:center!important;justify-content:center!important;flex-direction:column!important;background:linear-gradient(135deg,#3b1a0e 0%,#6b2f0f 40%,#8B4513 70%,#c47c3e 100%)!important;';
        el.innerHTML = `
            <style>
                #bhu_dash_loader {
                    position: fixed !important;
                    inset: 0 !important;
                    z-index: 99999 !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    flex-direction: column !important;
                    background: linear-gradient(135deg, #3b1a0e 0%, #6b2f0f 40%, #8B4513 70%, #c47c3e 100%) !important;
                }
                #bhu_dash_loader .bdl-ring {
                    width: 96px; height: 96px;
                    border-radius: 50%;
                    background: rgba(255,255,255,0.15);
                    border: 3px solid rgba(255,255,255,0.4);
                    display: flex; align-items: center; justify-content: center;
                    margin-bottom: 18px;
                    box-shadow: 0 4px 24px rgba(0,0,0,0.25);
                    overflow: hidden;
                    padding: 6px;
                }
                #bhu_dash_loader .bdl-ring img {
                    width: 100%; height: 100%;
                    object-fit: contain;
                    border-radius: 50%;
                }
                #bhu_dash_loader .bdl-spinner {
                    width: 60px; height: 60px;
                    border: 5px solid rgba(255,255,255,0.15);
                    border-top-color: #ffd88a;
                    border-radius: 50%;
                    animation: bdl-spin 0.85s linear infinite;
                    margin-bottom: 26px;
                }
                #bhu_dash_loader .bdl-title {
                    color: #fff; font-size: 1.5rem; font-weight: 700;
                    margin: 0 0 6px 0; font-family: inherit;
                }
                #bhu_dash_loader .bdl-sub {
                    color: rgba(255,255,255,0.70); font-size: 0.95rem;
                    margin: 0 0 26px 0; font-style: italic; font-family: inherit;
                }
                #bhu_dash_loader .bdl-dots {
                    display: flex; gap: 9px; margin-bottom: 30px;
                }
                #bhu_dash_loader .bdl-dots span {
                    width: 10px; height: 10px; border-radius: 50%;
                    background: #ffd88a;
                    animation: bdl-bounce 1.2s ease-in-out infinite;
                }
                #bhu_dash_loader .bdl-dots span:nth-child(2) { animation-delay: 0.18s; }
                #bhu_dash_loader .bdl-dots span:nth-child(3) { animation-delay: 0.36s; }
                #bhu_dash_loader .bdl-dots span:nth-child(4) { animation-delay: 0.54s; }
                #bhu_dash_loader .bdl-dots span:nth-child(5) { animation-delay: 0.72s; }
                #bhu_dash_loader .bdl-brand {
                    color: rgba(255,255,255,0.35); font-size: 0.75rem;
                    letter-spacing: 1.2px; text-transform: uppercase; font-family: inherit;
                }
                @keyframes bdl-spin {
                    to { transform: rotate(360deg); }
                }
                @keyframes bdl-bounce {
                    0%, 80%, 100% { transform: scale(0.55); opacity: 0.4; }
                    40%           { transform: scale(1.2);  opacity: 1;   }
                }
            </style>
            <div class="bdl-ring"><img src="/bhukhadan_core/static/img/icon.png" alt="BhuKhadan"/></div>
            <div class="bdl-spinner"></div>
            <div class="bdl-title">Please wait…</div>
            <div class="bdl-sub">We are loading your dashboard</div>
            <div class="bdl-dots">
                <span></span><span></span><span></span><span></span><span></span>
            </div>
            <div class="bdl-brand">BhuKhadan · Land Acquisition System</div>
        `;
        document.body.appendChild(el);
    }

    _hideBodyLoader() {
        const el = document.getElementById('bhu_dash_loader');
        if (el) {
            el.style.transition = 'opacity 0.35s ease';
            el.style.opacity = '0';
            setTimeout(() => el.remove(), 380);
        }
    }
}

// ========== Register Dashboard Types ==========
// Register each dashboard type from configuration
for (const [dashboardType, config] of Object.entries(DASHBOARD_CONFIG)) {
    // Create a class for this dashboard type
    const DashboardClass = class extends UnifiedDashboard {
        static template = config.template;

        setup() {
            this.dashboardType = dashboardType;
            super.setup();
        }
    };

    // Register with Odoo
    registry.category("actions").add(config.registryKey, DashboardClass);
}

