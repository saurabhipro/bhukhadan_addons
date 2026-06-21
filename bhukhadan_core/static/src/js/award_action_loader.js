/** @odoo-module **/

/**
 * Award Action Loader
 * Shows a full-screen loading overlay when heavy award actions (generate / download)
 * are triggered from any Odoo form view button.
 */

const LOADER_ID = 'bhu_award_action_loader';
const LOADING_BODY_CLASS = 'bhu_award_loading_state';
const POPUP_DISABLE_STYLE_ID = 'bhu_award_popup_disable_style';

function _ensurePopupDisableStyles() {
    if (document.getElementById(POPUP_DISABLE_STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = POPUP_DISABLE_STYLE_ID;
    style.textContent = `
        body.${LOADING_BODY_CLASS} .modal.show .modal-footer button,
        body.${LOADING_BODY_CLASS} .o_dialog .modal-footer button,
        body.${LOADING_BODY_CLASS} [role="dialog"] .modal-footer button,
        body.${LOADING_BODY_CLASS} .modal.show .btn-close,
        body.${LOADING_BODY_CLASS} .o_dialog .btn-close,
        body.${LOADING_BODY_CLASS} [role="dialog"] .btn-close {
            pointer-events: none !important;
            opacity: 0.55 !important;
            filter: grayscale(0.2);
        }
    `;
    document.head.appendChild(style);
}

function _setPopupButtonsDisabled(disabled) {
    _ensurePopupDisableStyles();
    document.body.classList.toggle(LOADING_BODY_CLASS, !!disabled);
    const buttons = document.querySelectorAll(
        '.modal.show .modal-footer button, .o_dialog .modal-footer button, [role="dialog"] .modal-footer button, .modal.show .btn-close, .o_dialog .btn-close, [role="dialog"] .btn-close'
    );
    buttons.forEach((btn) => {
        if (disabled) { 
            if (!btn.dataset.bhuPrevDisabled) {
                btn.dataset.bhuPrevDisabled = btn.disabled ? '1' : '0';
            }
            btn.disabled = true;
            btn.setAttribute('aria-disabled', 'true');
        } else {
            const prev = btn.dataset.bhuPrevDisabled;
            if (prev !== undefined) {
                btn.disabled = prev === '1';
                delete btn.dataset.bhuPrevDisabled;
            } else {
                btn.disabled = false;
            }
            btn.removeAttribute('aria-disabled');
        }
    });
}

// Button method names that warrant a loading overlay.
// NOTE: 'action_download_award' is intentionally EXCLUDED because it opens
// a wizard popup — showing a loader would cover the dialog.
// The loader is only for actions that do heavy server-side work (PDF/Excel generation).
const HEAVY_ACTIONS = new Set([
    'action_generate_award',
    'action_generate_land_award',
    'action_generate_tree_award',
    'action_generate_asset_award',
    'action_regenerate_land_award',
    'action_regenerate_tree_award',
    'action_regenerate_asset_award',
    'action_generate_consolidated_award',
    'action_generate_rr_award',
    // 'action_download_award' — opens a wizard, NOT a heavy action (wizard covers loader)
    'action_download',          // inside the download wizard — actual PDF/Excel generation
    'action_download_excel_components',
    'apply_generate_from_download_wizard',
    'action_generate_award_notification',
    'action_download_award_notification',
    'action_download_consolidated_excel',
    'action_consolidated_report',
]);

const PRECHECK_GENERATE_ACTIONS = new Set([
    'action_generate_award',
    'action_generate_land_award',
    'action_generate_tree_award',
    'action_generate_asset_award',
    'action_regenerate_land_award',
    'action_regenerate_tree_award',
    'action_regenerate_asset_award',
]);

// Payment voucher actions — file already exists or quick UI; skip Section 23 award overlay.
const PAYMENT_VOUCHER_SKIP_LOADER = new Set([
    'action_download',
    'action_generate_payment_files',
    'action_download_payment_file',
    'action_open_line_editor',
    'action_sync_col_amounts_from_rr',
]);

function _isPaymentVoucherContext(btn) {
    return !!(btn && btn.closest('.bhu_payment_voucher_premium'));
}

function _isPaymentVoucherExportPage() {
    const loc = `${window.location.pathname}${window.location.hash}${window.location.search}`.toLowerCase();
    if (loc.includes('bhu.payment.voucher.export')) {
        return true;
    }
    const cp = document.querySelector('.o_control_panel .o_breadcrumb, .o_control_panel_breadcrumbs');
    const txt = ((cp && cp.textContent) || '').toLowerCase();
    return txt.includes('generated payment files');
}

function _fieldWidget(fieldName) {
    return document.querySelector(`.o_form_view .o_field_widget[name="${fieldName}"]`);
}

function _fieldRawValue(fieldName) {
    const widget = _fieldWidget(fieldName);
    if (!widget) return '';
    const input = widget.querySelector('input, textarea, select');
    if (input) return (input.value || '').trim();
    return (widget.textContent || '').trim();
}

function _toNumber(raw) {
    const cleaned = String(raw || '')
        .replace(/[,₹\s]/g, '')
        .replace(/[^\d.\-]/g, '');
    const num = parseFloat(cleaned);
    return Number.isFinite(num) ? num : 0.0;
}

function _section23GeneratePrecheckError() {
    const caseNumber = _fieldRawValue('case_number');
    if (!caseNumber) {
        return 'Please enter Case Number before generating the award.';
    }
    const vikarDar = _toNumber(_fieldRawValue('avg_three_year_sales_sort_rate'));
    if (vikarDar <= 0) {
        return 'Please enter Vikray/Vikar Dar (3-year average sales rate) greater than zero before generating.';
    }
    const mrHa = _toNumber(_fieldRawValue('rate_master_main_road_ha'));
    const bmrHa = _toNumber(_fieldRawValue('rate_master_other_road_ha'));
    if (mrHa <= 0 || bmrHa <= 0) {
        return 'Please enter MR Rate and BMR Rate (per hectare) greater than zero before generating.';
    }
    return '';
}

const ACTION_ICONS = {
    action_generate_land_award: '🧾',
    action_regenerate_land_award: '🧾',
    action_generate_tree_award: '🌳',
    action_regenerate_tree_award: '🌳',
    action_generate_asset_award: '🏠',
    action_regenerate_asset_award: '🏠',
    action_generate_consolidated_award: '📘',
    action_generate_rr_award: '📗',
    action_generate_award: '✅',
};

let LOADER_PROGRESS_TIMER = null;

function _extractSection23AwardId() {
    const hash = window.location.hash || '';
    const modelMatch = hash.match(/(?:^|[?#&])model=([^&]+)/);
    const idMatch = hash.match(/(?:^|[?#&])id=(\d+)/);
    const activeIdMatch = hash.match(/(?:^|[?#&])active_id=(\d+)/);
    const model = modelMatch ? decodeURIComponent(modelMatch[1] || '') : '';
    if (model === 'bhu.section23.award' && idMatch) {
        return parseInt(idMatch[1], 10) || 0;
    }
    if (model === 'bhu.section23.award' && activeIdMatch) {
        return parseInt(activeIdMatch[1], 10) || 0;
    }
    const form = document.querySelector('.o_form_view');
    const fromDataset = parseInt(
        (form && (form.dataset.resId || form.getAttribute('data-res-id'))) || '0',
        10
    ) || 0;
    return fromDataset;
}

function _loaderEl(selector) {
    const host = document.getElementById(LOADER_ID);
    return host ? host.querySelector(selector) : null;
}

function _setLoaderText(selector, value, fallback = '-') {
    const el = _loaderEl(selector);
    if (el) el.textContent = value || fallback;
}

function _updateLoaderProgressUI(payload) {
    if (!payload) return;
    const total = Math.max(0, parseInt(payload.total || 0, 10));
    const done = Math.max(0, parseInt(payload.done || 0, 10));
    const pct = total > 0 ? Math.min(100, Math.max(0, (done * 100.0) / total)) : (parseFloat(payload.pct || 0) || 0);
    const pctFixed = `${pct.toFixed(1)}%`;

    _setLoaderText('.aal-project-name', payload.project || _fieldRawValue('project_id'));
    _setLoaderText('.aal-village-name', payload.village || _fieldRawValue('village_id'));
    _setLoaderText('.aal-village-type', payload.village_type || _fieldRawValue('village_type') || '-');
    _setLoaderText('.aal-urban-body', payload.urban_body || _fieldRawValue('urban_body_type') || '-');
    _setLoaderText('.aal-progress-stat', total > 0 ? `${done} / ${total} rows` : 'Preparing rows...');
    _setLoaderText('.aal-progress-pct', pctFixed, '0.0%');
    _setLoaderText('.aal-progress-label', payload.label || 'Processing...');

    const bar = _loaderEl('.aal-progress-fill');
    if (bar) bar.style.width = `${Math.max(0, Math.min(100, pct))}%`;
}

function _startLoaderProgressPolling() {
    if (LOADER_PROGRESS_TIMER) {
        clearInterval(LOADER_PROGRESS_TIMER);
        LOADER_PROGRESS_TIMER = null;
    }
    _setLoaderText('.aal-project-name', _fieldRawValue('project_id'));
    _setLoaderText('.aal-village-name', _fieldRawValue('village_id'));
    _setLoaderText('.aal-village-type', _fieldRawValue('village_type') || '-');
    _setLoaderText('.aal-urban-body', _fieldRawValue('urban_body_type') || '-');

    const poll = () => {
        if (!document.getElementById(LOADER_ID)) return;
        const awardId = _extractSection23AwardId();
        // Avoid RPCs with no record id (e.g. transient "new" form while overlay is up).
        if (!awardId || awardId <= 0) {
            return;
        }
        fetch('/web/dataset/call_kw/bhu.section23.award/get_loader_progress', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: {
                    model: 'bhu.section23.award',
                    method: 'get_loader_progress',
                    args: [awardId],
                    kwargs: {},
                },
                id: Date.now(),
            }),
        })
            .then((r) => r.json())
            .then((res) => {
                if (!res || res.error) {
                    return;
                }
                const payload = res.result || {};
                _updateLoaderProgressUI(payload || {});
            })
            .catch(() => { /* keep loader alive even when polling fails */ });
    };

    poll();
    LOADER_PROGRESS_TIMER = setInterval(poll, 350);
}

function _showLoader(label, actionName = '') {
    if (document.getElementById(LOADER_ID)) return;
    _setPopupButtonsDisabled(true);
    const el = document.createElement('div');
    el.id = LOADER_ID;
    el.style.cssText = [
        'position:fixed!important', 'inset:0!important', 'z-index:999999!important',
        'display:flex!important', 'align-items:center!important',
        'justify-content:center!important', 'flex-direction:column!important',
        'background:linear-gradient(135deg,#3b1a0e 0%,#6b2f0f 40%,#8B4513 70%,#c47c3e 100%)!important',
    ].join(';');

    el.innerHTML = `
        <style>
            #${LOADER_ID} .aal-ring {
                width: 96px; height: 96px; border-radius: 50%;
                background: rgba(255,255,255,0.15);
                border: 3px solid rgba(255,255,255,0.4);
                display: flex; align-items: center; justify-content: center;
                margin-bottom: 18px;
                box-shadow: 0 4px 24px rgba(0,0,0,0.25);
                overflow: hidden; padding: 6px;
            }
            #${LOADER_ID} .aal-ring img { width:100%; height:100%; object-fit:contain; border-radius:50%; }
            #${LOADER_ID} .aal-spinner {
                width: 64px; height: 64px;
                border: 5px solid rgba(255,255,255,0.15);
                border-top-color: #ffd88a; border-radius: 50%;
                animation: aal-spin 0.85s linear infinite; margin-bottom: 26px;
            }
            #${LOADER_ID} .aal-title {
                color:#fff; font-size:2rem; font-weight:800;
                margin:0 0 10px 0; font-family:inherit; text-align:center;
            }
            #${LOADER_ID} .aal-action-icon {
                width:48px; height:48px; border-radius:14px;
                display:flex; align-items:center; justify-content:center;
                background:rgba(255,255,255,0.2);
                color:#fff; font-size:1.7rem; line-height:1;
                margin:0 0 12px 0;
                box-shadow: inset 0 0 0 1px rgba(255,255,255,0.35), 0 4px 10px rgba(0,0,0,0.2);
            }
            #${LOADER_ID} .aal-sub {
                color:rgba(255,255,255,0.9); font-size:1.18rem;
                margin:0 0 28px 0; font-style:italic; font-family:inherit; text-align:center;
                max-width: 520px; line-height: 1.6;
            }
            #${LOADER_ID} .aal-sub small {
                display:block;
                font-size:0.98rem;
                line-height:1.5;
                margin-top:6px;
                color:rgba(255,255,255,0.88);
            }
            #${LOADER_ID} .aal-meta {
                width: min(620px, 90vw);
                margin: 0 0 14px 0;
                padding: 10px 14px;
                border-radius: 12px;
                background: rgba(255, 255, 255, 0.12);
                box-shadow: inset 0 0 0 1px rgba(255,255,255,0.25);
                color: #fff;
                font-size: 0.96rem;
            }
            #${LOADER_ID} .aal-meta-row {
                display: flex;
                justify-content: space-between;
                gap: 12px;
                margin-bottom: 4px;
            }
            #${LOADER_ID} .aal-meta-row:last-child { margin-bottom: 0; }
            #${LOADER_ID} .aal-progress-wrap {
                width: min(620px, 90vw);
                margin: 0 0 10px 0;
            }
            #${LOADER_ID} .aal-progress-head {
                display: flex;
                justify-content: space-between;
                align-items: center;
                color: rgba(255,255,255,0.95);
                font-size: 0.95rem;
                margin-bottom: 6px;
            }
            #${LOADER_ID} .aal-progress-track {
                width: 100%;
                height: 10px;
                border-radius: 999px;
                background: rgba(255,255,255,0.18);
                overflow: hidden;
                box-shadow: inset 0 1px 2px rgba(0,0,0,0.25);
            }
            #${LOADER_ID} .aal-progress-fill {
                width: 0%;
                height: 100%;
                border-radius: inherit;
                transition: width 0.35s ease;
                background: linear-gradient(90deg, #ffe49f, #ffd066);
            }
            #${LOADER_ID} .aal-progress-label {
                color: rgba(255,255,255,0.9);
                font-size: 0.9rem;
                margin-top: 6px;
                text-align: left;
            }
            #${LOADER_ID} .aal-dots { display:flex; gap:9px; margin-bottom:30px; }
            #${LOADER_ID} .aal-dots span {
                width:10px; height:10px; border-radius:50%;
                background:#ffd88a; animation:aal-bounce 1.2s ease-in-out infinite;
            }
            #${LOADER_ID} .aal-dots span:nth-child(2){animation-delay:0.18s;}
            #${LOADER_ID} .aal-dots span:nth-child(3){animation-delay:0.36s;}
            #${LOADER_ID} .aal-dots span:nth-child(4){animation-delay:0.54s;}
            #${LOADER_ID} .aal-dots span:nth-child(5){animation-delay:0.72s;}
            #${LOADER_ID} .aal-brand {
                color:rgba(255,255,255,0.35); font-size:0.75rem;
                letter-spacing:1.2px; text-transform:uppercase; font-family:inherit;
            }
            @keyframes aal-spin  { to { transform: rotate(360deg); } }
            @keyframes aal-bounce {
                0%,80%,100% { transform:scale(0.55); opacity:0.4; }
                40%         { transform:scale(1.2);  opacity:1;   }
            }
        </style>
        <div class="aal-ring"><img src="/bhukhadan_core/static/img/icon.png" alt="BhuKhadan"/></div>
        <div class="aal-spinner"></div>
        <div class="aal-action-icon">${ACTION_ICONS[actionName] || '📄'}</div>
        <div class="aal-title">Please wait…</div>
        <div class="aal-sub">${label || 'Processing your request. This may take a few moments.'}</div>
        <div class="aal-meta">
            <div class="aal-meta-row"><span>Project</span><strong class="aal-project-name">-</strong></div>
            <div class="aal-meta-row"><span>Village</span><strong class="aal-village-name">-</strong></div>
            <div class="aal-meta-row"><span>Village Type</span><strong class="aal-village-type">-</strong></div>
            <div class="aal-meta-row"><span>Urban Body Type</span><strong class="aal-urban-body">-</strong></div>
        </div>
        <div class="aal-progress-wrap">
            <div class="aal-progress-head">
                <span class="aal-progress-stat">Preparing rows...</span>
                <strong class="aal-progress-pct">0.0%</strong>
            </div>
            <div class="aal-progress-track"><div class="aal-progress-fill"></div></div>
            <div class="aal-progress-label">Initializing generation...</div>
        </div>
        <div class="aal-dots"><span></span><span></span><span></span><span></span><span></span></div>
        <div class="aal-brand">BhuKhadan · Land Acquisition System</div>
    `;
    document.body.appendChild(el);
    _startLoaderProgressPolling();
}

function _hideLoader() {
    const el = document.getElementById(LOADER_ID);
    if (LOADER_PROGRESS_TIMER) {
        clearInterval(LOADER_PROGRESS_TIMER);
        LOADER_PROGRESS_TIMER = null;
    }
    _setPopupButtonsDisabled(false);
    if (!el) return;
    el.style.transition = 'opacity 0.35s ease';
    el.style.opacity = '0';
    setTimeout(() => el && el.remove(), 380);
}

// Label map for each action
const ACTION_LABELS = {
    'action_generate_award':            'Generating the Section 23 Award document…<br><small>Building PDF from survey data. Please do not close this page.</small>',
    'action_generate_land_award':       'Generating Land Award…<br><small>Files will be stored in BhuKhadan for download. Please wait.</small>',
    'action_generate_tree_award':       'Generating Tree Award…<br><small>Files will be stored in BhuKhadan for download. Please wait.</small>',
    'action_generate_asset_award':      'Generating Asset Award…<br><small>Files will be stored in BhuKhadan for download. Please wait.</small>',
    'action_regenerate_land_award':     'Regenerating Land Award…<br><small>Files will be stored in BhuKhadan for download.</small>',
    'action_regenerate_tree_award':     'Regenerating Tree Award…<br><small>Files will be stored in BhuKhadan for download.</small>',
    'action_regenerate_asset_award':    'Regenerating Asset Award…<br><small>Files will be stored in BhuKhadan for download.</small>',
    'action_generate_consolidated_award': 'Generating Consolidated Award…<br><small>Files will be stored in BhuKhadan for download.</small>',
    'action_generate_rr_award':         'Generating R&amp;R Award…<br><small>Files will be stored in BhuKhadan for download.</small>',
    'action_download':                  'Generating &amp; downloading your document…<br><small>Building PDF / Excel. This may take a moment.</small>',
    'action_download_excel_components': 'Generating Excel report…<br><small>Building Excel workbook from survey data.</small>',
    'apply_generate_from_download_wizard': 'Generating &amp; downloading Award…<br><small>Building the document. Download will start automatically.</small>',
    'action_generate_award_notification': 'Generating notification document…',
    'action_download_award_notification': 'Preparing notification for download…',
    'action_download_consolidated_excel': 'Generating Consolidated Excel…',
    'action_consolidated_report':        'Generating Consolidated PDF report…',
};

function _showLoaderAfterConfirmDialogClose(confirmDialog, label, actionName = '') {
    let shown = false;
    const showOnce = () => {
        if (shown) return;
        shown = true;
        _showLoader(label, actionName);
    };
    if (!confirmDialog || !document.body.contains(confirmDialog)) {
        showOnce();
        return;
    }
    const obs = new MutationObserver(() => {
        if (
            !document.body.contains(confirmDialog) ||
            confirmDialog.style.display === 'none' ||
            !confirmDialog.offsetParent
        ) {
            obs.disconnect();
            showOnce();
        }
    });
    obs.observe(document.body, { childList: true, subtree: true });
    // Hard fallback in case MutationObserver misses the close.
    setTimeout(() => { obs.disconnect(); showOnce(); }, 400);
}

function _attachConfirmDialogListener(label, actionName = '') {
    // Called after a heavy form button click; waits for confirm dialog to appear,
    // then attaches a one-time listener to its footer to detect OK vs Cancel.
    let attached = false;
    let cancelled = false;
    const tryAttach = () => {
        if (attached || cancelled) return;
        const dialog = document.querySelector('.o_dialog:not([style*="display:none"]):not([style*="display: none"])');
        if (!dialog) return;
        const footer = dialog.querySelector('.o_dialog_footer, .modal-footer');
        if (!footer) return;
        attached = true;
        footer.addEventListener('click', function onFooterClick(e) {
            footer.removeEventListener('click', onFooterClick);
            let b = e.target;
            while (b && b.tagName !== 'BUTTON') b = b.parentElement;
            if (!b) return;
            const cls = b.className || '';
            const txt = (b.textContent || '').trim().toLowerCase();
            const isOk = cls.includes('btn-primary') || cls.includes('btn-success') ||
                txt === 'ok' || txt === 'yes' || txt === 'confirm';
            if (isOk) {
                _showLoaderAfterConfirmDialogClose(dialog, label, actionName);
            }
            // Cancel: do nothing — no loader.
        }, true);
    };
    // Poll briefly for dialog to appear (Odoo renders it async via OWL).
    let polls = 0;
    const poll = setInterval(() => {
        polls++;
        tryAttach();
        if (attached || polls > 30) {  // 30 × 50ms = 1.5s max wait
            clearInterval(poll);
            if (!attached) {
                // No confirm dialog appeared — action ran directly, show loader now.
                if (!document.getElementById(LOADER_ID)) {
                    _showLoader(label, actionName);
                }
            }
        }
    }, 50);
    // Allow cancellation if a Cancel/Close click detected within 1.5s.
    return { cancel: () => { cancelled = true; clearInterval(poll); } };
}

function _isSection23Context() {
    const hash = (window.location.hash || '').toLowerCase();
    if (hash.includes('bhu.section23.award') || hash.includes('section23')) {
        return true;
    }
    const cp = document.querySelector('.o_control_panel_breadcrumbs, .o_breadcrumb, .breadcrumb');
    const txt = ((cp && cp.textContent) || '').toLowerCase();
    return txt.includes('section 23 award') || txt.includes('धारा 23');
}

function _isCreateButton(btn) {
    if (!btn) return false;
    return (
        btn.classList.contains('o_list_button_add') ||
        btn.classList.contains('o-kanban-button-new') ||
        btn.classList.contains('o_form_button_create')
    );
}

function _isSection23Hash(hashValue) {
    const hash = (hashValue || '').toLowerCase();
    return hash.includes('model=bhu.section23.award') || hash.includes('section23');
}

function _isAwardMenuTarget(node) {
    const target = node && node.closest('a, button, [role="menuitem"]');
    if (!target) return false;
    const haystack = [
        target.getAttribute('data-menu-xmlid') || '',
        target.getAttribute('data-action-xmlid') || '',
        target.getAttribute('data-action-id') || '',
        target.getAttribute('name') || '',
        target.getAttribute('href') || '',
        target.getAttribute('title') || '',
        target.textContent || '',
    ].join(' ').toLowerCase();
    return (
        haystack.includes('menu_sec23_award') ||
        haystack.includes('menu_payment_view_awards') ||
        haystack.includes('action_section23_award') ||
        haystack.includes('bhu.section23.award') ||
        haystack.includes('section 23 awards') ||
        haystack.includes('section 23 award') ||
        haystack.includes('view awards')
    );
}

function _showSection23OpenLoader() {
    _showLoader('Opening Section 23 Award…<br><small>Loading award data. Please wait.</small>', 'action_generate_award');

    const startedAt = Date.now();
    const MAX_WAIT = 25000;
    const MIN_VISIBLE_MS = 550;
    let done = false;
    let pollTimer = null;
    let observer = null;

    const isViewReady = () => {
        if (!_isSection23Context() && !_isSection23Hash(window.location.hash)) return false;
        const hasList = !!document.querySelector('.o_content .o_list_view .o_list_table');
        const hasForm = !!document.querySelector('.o_content .o_form_view .o_form_sheet');
        const hasBreadcrumb = !!document.querySelector(
            '.o_control_panel_breadcrumbs, .o_breadcrumb, .breadcrumb'
        );
        return hasList || hasForm || hasBreadcrumb;
    };

    const finish = () => {
        if (done) return;
        done = true;
        if (observer) observer.disconnect();
        if (pollTimer) clearInterval(pollTimer);
        const elapsed = Date.now() - startedAt;
        const waitMore = Math.max(0, MIN_VISIBLE_MS - elapsed);
        setTimeout(_hideLoader, waitMore);
    };

    if (isViewReady()) {
        finish();
        return;
    }

    pollTimer = setInterval(() => {
        if (isViewReady() || (Date.now() - startedAt) > MAX_WAIT) {
            finish();
        }
    }, 220);

    observer = new MutationObserver(() => {
        if (isViewReady()) {
            finish();
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
}

// Show loader when user opens the Section 23 Award action from menu.
document.addEventListener('click', (e) => {
    if (!_isAwardMenuTarget(e.target)) return;
    if (_isSection23Context()) return;
    _showSection23OpenLoader();
}, true);

// Also catch hash-based navigation into Section 23 (dashboard shortcuts etc.).
let _lastHash = window.location.hash;
window.addEventListener('hashchange', () => {
    const previous = (_lastHash || '').toLowerCase();
    const current = (window.location.hash || '').toLowerCase();
    _lastHash = window.location.hash;
    if (_isSection23Hash(current) && !_isSection23Hash(previous)) {
        _showSection23OpenLoader();
    } else if (_isSection23Hash(current) && !document.getElementById(LOADER_ID)) {
        // Fallback for SPA transitions where previous/current hash values are noisy.
        _showSection23OpenLoader();
    }
});

// Attach click listener using event delegation on document body (capture phase).
document.addEventListener('click', (e) => {
    // Walk up the DOM to find the actual <button> element.
    let btn = e.target;
    while (btn && btn.tagName !== 'BUTTON') {
        btn = btn.parentElement;
    }
    if (!btn || btn.disabled) return;

    const name = btn.getAttribute('name') || btn.dataset.name || '';
    if (
        PAYMENT_VOUCHER_SKIP_LOADER.has(name)
        && (_isPaymentVoucherContext(btn) || _isPaymentVoucherExportPage())
    ) {
        return;
    }
    // Pre-generated bank Excel — direct download, no PDF/Excel build overlay.
    if (name === 'action_download' && _isPaymentVoucherExportPage()) {
        return;
    }
    const isHeavy = HEAVY_ACTIONS.has(name);
    const isCreateInS23 = _isCreateButton(btn) && _isSection23Context();
    if (!isHeavy && !isCreateInS23) return;

    // For Section 23 generate/regenerate, validate mandatory rates first
    // and block confirm popup until data is valid.
    if (PRECHECK_GENERATE_ACTIONS.has(name)) {
        const precheckError = _section23GeneratePrecheckError();
        if (precheckError) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            window.alert(precheckError);
            return;
        }
    }

    const label = isCreateInS23
        ? 'Opening Section 23 Award form…<br><small>Preparing the next screen.</small>'
        : (ACTION_LABELS[name] || 'Processing your request…');

    // If button is INSIDE a wizard/download dialog: show loader immediately.
    const insideDialog = !!btn.closest('.o_dialog, .modal, [role="dialog"]');
    if (insideDialog) {
        _showLoader(label, name);
        _setupLoaderDone(btn.closest('.o_dialog, .modal, [role="dialog"]'));
        return;
    }

    // For form-level buttons: Odoo may render a confirm dialog first (OWL async).
    // Wait and attach to dialog's footer, then show loader only after user clicks OK.
    _attachConfirmDialogListener(label, name);

}, true); // capture phase

function _setupLoaderDone(wizardDialog) {
    const MAX_WAIT = 120000;
    const safetyTimer = setTimeout(_hideLoader, MAX_WAIT);

    function done() {
        clearTimeout(safetyTimer);
        dialogObs && dialogObs.disconnect();
        notifObs && notifObs.disconnect();
        setTimeout(_hideLoader, 500);
    }

    // 1. Hide when wizard dialog is removed.
    let dialogObs = null;
    if (wizardDialog) {
        dialogObs = new MutationObserver(() => {
            if (!document.body.contains(wizardDialog) ||
                wizardDialog.style.display === 'none' ||
                !wizardDialog.offsetParent) {
                done();
            }
        });
        dialogObs.observe(document.body, { childList: true, subtree: true });
    }

    // 2. Hide when Odoo shows a notification.
    let notifObs = new MutationObserver(() => {
        const notif = document.querySelector('.o_notification_manager .o_notification');
        if (notif) { done(); }
    });
    notifObs.observe(document.body, { childList: true, subtree: true });

    // 3. Hide on focus return (file download finished).
    window.addEventListener('focus', () => done(), { once: true });
}

// Watch notifications and close loader after success/error.
// Important: guard against early module load when `document.body` is not ready yet.
function _startLoaderHideWatcher() {
    const target = document.body || document.documentElement;
    if (!target) return;
    const obs = new MutationObserver(() => {
        if (!document.getElementById(LOADER_ID)) return;
        const notif = document.querySelector('.o_notification_manager .o_notification');
        if (notif) {
            setTimeout(_hideLoader, 600);
        }
    });
    obs.observe(target, { childList: true, subtree: true });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _startLoaderHideWatcher, { once: true });
} else {
    _startLoaderHideWatcher();
}
