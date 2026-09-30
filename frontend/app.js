/**
 * Public Health Professional Assessment & Learning Platform — Frontend Engine
 * Prometric / CPH / USMLE Standardized Examination Interface & Cockpit
 * Dark-Mode Executive & Authenticated Candidate Experience
 */

(function () {
    "use strict";

    // -------------------------------------------------------------
    // Configuration & API Endpoints
    // -------------------------------------------------------------
    const API_BASE = (function () {
        if (typeof window !== "undefined" && window.location) {
            if (window.location.protocol === "file:") {
                return "http://localhost:8000/api";
            }
            if (window.location.origin && window.location.origin.startsWith("http")) {
                return `${window.location.origin}/api`;
            }
        }
        return "/api";
    })();

    const EXAM_DURATION_SECONDS = 900; // Standard 15:00 minutes countdown

    // -------------------------------------------------------------
    // Application Client-Side State
    // -------------------------------------------------------------
    const state = {
        userRole: "candidate", // "candidate" or "admin"
        candidate: {
            name: "Alex Johnson",
            id: "CPH-2026-8841",
            track: "all",
        },
        isAuthenticated: false,
        sessionId: "",
        activeTab: "practice",
        
        // Examination Cockpit State
        isExamLaunched: false,
        isExamSubmitted: false,
        activeQuestionIndex: 0,
        flaggedQuestions: {}, // { [question_id]: true }
        timeRemainingSec: EXAM_DURATION_SECONDS,
        timerIntervalId: null,

        // Questions & Submissions
        competencies: [],
        questionsData: [],
        selectedObjectiveAnswers: {}, // { [question_id]: selected_option_id }

        // Outbreak Simulation State
        scenariosData: [],
        currentScenarioStage: 1,
        selectedScenarioChoices: [], // [ { scenario_id, stage_id, selected_choice_id } ]
        scenarioStageFeedback: {},

        // Analytics & Remediation
        latestEvaluation: null,
        activeRemediationPillar: null,
    };

    // -------------------------------------------------------------
    // DOM Elements Reference Cache
    // -------------------------------------------------------------
    const dom = {
        // Authentication Gate Modal
        candidateAuthModal: document.getElementById("candidate-auth-modal"),
        authTabCandidate: document.getElementById("auth-tab-candidate"),
        authTabAdmin: document.getElementById("auth-tab-admin"),
        candidateAuthForm: document.getElementById("candidate-auth-form"),
        adminAuthForm: document.getElementById("admin-auth-form"),
        inputCandidateName: document.getElementById("input-candidate-name"),
        inputCandidateId: document.getElementById("input-candidate-id"),
        inputAdminPasskey: document.getElementById("input-admin-passkey"),
        termsAgree: document.getElementById("terms-agree"),
        btnCandidateLogin: document.getElementById("btn-candidate-login"),
        btnAdminLogin: document.getElementById("btn-admin-login"),
        appMainLayout: document.getElementById("app-main-layout"),

        // Header & Utility Bar
        headerNavTabs: document.getElementById("header-nav-tabs"),
        navTabs: document.getElementById("nav-tabs"),
        headerCandidateName: document.getElementById("header-candidate-name"),
        headerCandidateId: document.getElementById("header-candidate-id"),
        sessionIdDisplay: document.getElementById("session-id-display"),
        sessionTimerDisplay: document.getElementById("session-timer-display"),
        sessionTimerBadge: document.getElementById("session-timer-badge"),
        systemHealthText: document.getElementById("system-health-text"),
        systemHealthPill: document.getElementById("system-health-pill"),
        headerProgressBar: document.getElementById("header-progress-bar"),

        // Navigation Tabs
        tabButtons: document.querySelectorAll(".tab-button"),
        tabContents: document.querySelectorAll(".tab-content"),
        practiceCountBadge: document.getElementById("practice-count-badge"),
        simulationStageBadge: document.getElementById("simulation-stage-badge"),
        readinessTabBadge: document.getElementById("readiness-tab-badge"),

        // Tab 1: Pre-Exam Briefing Gate
        candidateBriefingGate: document.getElementById("candidate-briefing-gate"),
        btnStartExam: document.getElementById("btn-start-exam"),

        // Tab 1: Examination Cockpit
        examCockpitContainer: document.getElementById("exam-cockpit-container"),
        examReviewBanner: document.getElementById("exam-review-banner"),
        reviewBannerTitle: document.getElementById("review-banner-title"),
        reviewBannerDesc: document.getElementById("review-banner-desc"),
        btnReviewJumpDashboard: document.getElementById("btn-review-jump-dashboard"),

        // Matrix Navigator
        matrixGrid: document.getElementById("matrix-grid"),
        matrixActiveIndicator: document.getElementById("matrix-active-indicator"),
        matrixAnsweredStat: document.getElementById("matrix-answered-stat"),
        matrixFlaggedStat: document.getElementById("matrix-flagged-stat"),
        examDomainSelect: document.getElementById("exam-domain-select"),
        btnSidebarFinishExam: document.getElementById("btn-sidebar-finish-exam"),

        // Single-Item Viewport Stage & Bottom Dock
        examItemBadge: document.getElementById("exam-item-badge"),
        examPillarBadge: document.getElementById("exam-pillar-badge"),
        btnFlagItem: document.getElementById("btn-flag-item"),
        flagBtnText: document.getElementById("flag-btn-text"),
        btnFlagDock: document.getElementById("btn-flag-dock"),
        flagDockText: document.getElementById("flag-dock-text"),
        stageKeyboardHint: document.getElementById("stage-keyboard-hint"),
        stageReviewPositionBadge: document.getElementById("stage-review-position-badge"),
        stageReviewPositionText: document.getElementById("stage-review-position-text"),
        examQuestionPrompt: document.getElementById("exam-question-prompt"),
        examOptionsGrid: document.getElementById("exam-options-grid"),
        stageItemReviewFeedback: document.getElementById("stage-item-review-feedback"),
        btnExamPrev: document.getElementById("btn-exam-prev"),
        btnExamPrevText: document.getElementById("btn-exam-prev-text"),
        btnExamNext: document.getElementById("btn-exam-next"),
        btnExamNextText: document.getElementById("btn-exam-next-text"),
        btnViewDashboard: document.getElementById("btn-view-dashboard"),

        // Submit Confirmation Modal
        submitConfirmModalOverlay: document.getElementById("submit-confirm-modal-overlay"),
        dialogAnsweredCount: document.getElementById("dialog-answered-count"),
        dialogFlaggedCount: document.getElementById("dialog-flagged-count"),
        dialogTimeRemaining: document.getElementById("dialog-time-remaining"),
        dialogWarningText: document.getElementById("dialog-warning-text"),
        btnCancelSubmit: document.getElementById("btn-cancel-submit"),
        btnConfirmSubmit: document.getElementById("btn-confirm-submit"),

        // Tab 2: Outbreak Simulation
        scenarioBriefingCard: document.getElementById("scenario-briefing-card"),
        scenarioTitle: document.getElementById("scenario-title"),
        scenarioSettingText: document.getElementById("scenario-setting-text"),
        scenarioBackground: document.getElementById("scenario-background"),

        stageCard1: document.getElementById("stage-card-1"),
        stage1StatusTag: document.getElementById("stage-1-status-tag"),
        stage1Prompt: document.getElementById("stage-1-prompt"),
        stage1Choices: document.getElementById("stage-1-choices"),
        btnCommitStage1: document.getElementById("btn-commit-stage-1"),
        stage1Feedback: document.getElementById("stage-1-feedback"),
        stage1DeltaBadge: document.getElementById("stage-1-delta-badge"),
        stage1FeedbackText: document.getElementById("stage-1-feedback-text"),

        stageCard2: document.getElementById("stage-card-2"),
        stage2StatusTag: document.getElementById("stage-2-status-tag"),
        stage2Prompt: document.getElementById("stage-2-prompt"),
        stage2Choices: document.getElementById("stage-2-choices"),
        stage2Actions: document.getElementById("stage-2-actions"),
        btnCommitStage2: document.getElementById("btn-commit-stage-2"),
        stage2Feedback: document.getElementById("stage-2-feedback"),
        stage2DeltaBadge: document.getElementById("stage-2-delta-badge"),
        stage2FeedbackText: document.getElementById("stage-2-feedback-text"),

        scenarioCompleteBanner: document.getElementById("scenario-complete-banner"),
        btnViewSimDashboard: document.getElementById("btn-view-sim-dashboard"),

        // Tab 3: Performance Dashboard
        radialScoreBar: document.getElementById("radial-score-bar"),
        dashReadinessScore: document.getElementById("dash-readiness-score"),
        dashReadinessLabel: document.getElementById("dash-readiness-label"),
        dashObjectiveScore: document.getElementById("dash-objective-score"),
        dashScenarioScore: document.getElementById("dash-scenario-score"),
        weakAreasContent: document.getElementById("weak-areas-content"),
        competencyBarsContainer: document.getElementById("competency-bars-container"),
        btnResetSession: document.getElementById("btn-reset-session"),
        btnExportRecord: document.getElementById("btn-export-record"),

        // Slide-Over Remediation Drawer
        drawerOverlay: document.getElementById("drawer-overlay"),
        remediationDrawer: document.getElementById("remediation-drawer"),
        drawerPillarTag: document.getElementById("drawer-pillar-tag"),
        drawerDomainTitle: document.getElementById("drawer-domain-title"),
        drawerDomainSubtitle: document.getElementById("drawer-domain-subtitle"),
        drawerBody: document.getElementById("drawer-body"),
        btnCloseDrawer: document.getElementById("btn-close-drawer"),
        btnDrawerDismiss: document.getElementById("btn-drawer-dismiss"),
        btnDrawerPracticeNow: document.getElementById("btn-drawer-practice-now"),

        // Institutional Transcript Modal
        transcriptModalOverlay: document.getElementById("transcript-modal-overlay"),
        btnPrintTranscript: document.getElementById("btn-print-transcript"),
        btnCloseTranscriptModal: document.getElementById("btn-close-transcript-modal"),
        transcriptCandidateName: document.getElementById("transcript-candidate-name"),
        transcriptCandidateId: document.getElementById("transcript-candidate-id"),
        transcriptSessionId: document.getElementById("transcript-session-id"),
        transcriptCertId: document.getElementById("transcript-cert-id"),
        transcriptIssuedAt: document.getElementById("transcript-issued-at"),
        transcriptAuditHash: document.getElementById("transcript-audit-hash"),
        transcriptOverallScore: document.getElementById("transcript-overall-score"),
        transcriptStatusBadge: document.getElementById("transcript-status-badge"),
        transcriptMcqScore: document.getElementById("transcript-mcq-score"),
        transcriptScenarioScore: document.getElementById("transcript-scenario-score"),
        transcriptTableBody: document.getElementById("transcript-table-body"),
        transcriptScenarioLog: document.getElementById("transcript-scenario-log"),
        transcriptRemediationList: document.getElementById("transcript-remediation-list"),

        // Admin Management Modal & Console Panel
        btnAdminManage: document.getElementById("btn-admin-manage"),
        adminManageModal: document.getElementById("admin-manage-modal"),
        btnCloseAdminModal: document.getElementById("btn-close-admin-modal"),
        adminConsoleView: document.getElementById("admin-console-view"),
        candidateViewsContainer: document.getElementById("candidate-views-container"),
        facultyPreviewBanner: document.getElementById("faculty-preview-banner"),
        btnReturnAdminConsole: document.getElementById("btn-return-admin-console"),
        btnPreviewExam: document.getElementById("btn-preview-exam"),
        btnAppLogout: document.getElementById("btn-app-logout"),
        adminStatPassages: document.getElementById("admin-stat-passages"),
        adminStatQuestions: document.getElementById("admin-stat-questions"),
        adminStatScenarios: document.getElementById("admin-stat-scenarios"),
        adminStatPath: document.getElementById("admin-stat-path"),
        chipUserLabel: document.getElementById("chip-user-label"),
        chipIdLabel: document.getElementById("chip-id-label"),

        // Modal Dropzone Elements
        curriculumDropzone: document.getElementById("curriculum-dropzone"),
        inputCurriculumFile: document.getElementById("input-curriculum-file"),
        curriculumSelectedFile: document.getElementById("curriculum-selected-file"),
        curriculumFilename: document.getElementById("curriculum-filename"),
        curriculumFilesize: document.getElementById("curriculum-filesize"),
        btnClearCurriculumFile: document.getElementById("btn-clear-curriculum-file"),
        btnUploadCurriculum: document.getElementById("btn-upload-curriculum"),
        btnUploadCurriculumText: document.getElementById("btn-upload-curriculum-text"),
        curriculumUploadStatus: document.getElementById("curriculum-upload-status"),
        curriculumStatusText: document.getElementById("curriculum-status-text"),

        questionsDropzone: document.getElementById("questions-dropzone"),
        inputQuestionsFile: document.getElementById("input-questions-file"),
        questionsSelectedFile: document.getElementById("questions-selected-file"),
        questionsFilename: document.getElementById("questions-filename"),
        questionsFilesize: document.getElementById("questions-filesize"),
        btnClearQuestionsFile: document.getElementById("btn-clear-questions-file"),
        btnUploadQuestions: document.getElementById("btn-upload-questions"),
        btnUploadQuestionsText: document.getElementById("btn-upload-questions-text"),
        questionsUploadStatus: document.getElementById("questions-upload-status"),
        questionsStatusText: document.getElementById("questions-status-text"),

        // Console Panel Dropzone Elements
        panelCurriculumDropzone: document.getElementById("panel-curriculum-dropzone"),
        panelInputCurriculumFile: document.getElementById("panel-input-curriculum-file"),
        panelCurriculumSelectedFile: document.getElementById("panel-curriculum-selected-file"),
        panelCurriculumFilename: document.getElementById("panel-curriculum-filename"),
        panelCurriculumFilesize: document.getElementById("panel-curriculum-filesize"),
        btnClearPanelCurriculumFile: document.getElementById("btn-clear-panel-curriculum-file"),
        btnPanelUploadCurriculum: document.getElementById("btn-panel-upload-curriculum"),
        btnPanelUploadCurriculumText: document.getElementById("btn-panel-upload-curriculum-text"),
        panelCurriculumUploadStatus: document.getElementById("panel-curriculum-upload-status"),
        panelCurriculumStatusText: document.getElementById("panel-curriculum-status-text"),

        panelQuestionsDropzone: document.getElementById("panel-questions-dropzone"),
        panelInputQuestionsFile: document.getElementById("panel-input-questions-file"),
        panelQuestionsSelectedFile: document.getElementById("panel-questions-selected-file"),
        panelQuestionsFilename: document.getElementById("panel-questions-filename"),
        panelQuestionsFilesize: document.getElementById("panel-questions-filesize"),
        btnClearPanelQuestionsFile: document.getElementById("btn-clear-panel-questions-file"),
        btnPanelUploadQuestions: document.getElementById("btn-panel-upload-questions"),
        btnPanelUploadQuestionsText: document.getElementById("btn-panel-upload-questions-text"),
        panelQuestionsUploadStatus: document.getElementById("panel-questions-upload-status"),
        panelQuestionsStatusText: document.getElementById("panel-questions-status-text"),

        // Toast Container
        toastContainer: document.getElementById("toast-container"),
    };

    // -------------------------------------------------------------
    // Helper Utilities
    // -------------------------------------------------------------
    function generateUUID() {
        if (typeof crypto !== "undefined" && crypto.randomUUID) {
            return crypto.randomUUID();
        }
        return "ph-" + Math.random().toString(36).substring(2, 10) + "-" + Date.now().toString(36);
    }

    function showToast(message, type = "info") {
        if (!dom.toastContainer) return;
        const toast = document.createElement("div");
        toast.className = `toast ${type}`;
        const prefix = type === "success" ? "[SUCCESS]" : type === "error" ? "[ERROR]" : "[INFO]";
        toast.innerHTML = `<span class="toast-prefix">${prefix}</span><span class="toast-msg">${message}</span>`;
        dom.toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateX(100%)";
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    }

    function formatTime(seconds) {
        const mins = String(Math.floor(seconds / 60)).padStart(2, "0");
        const secs = String(seconds % 60).padStart(2, "0");
        return `${mins}:${secs}`;
    }

    function getCompetencyAbbr(compName) {
        if (!compName) return "Item";
        const lower = compName.toLowerCase();
        if (lower.includes("epi")) return "Epi";
        if (lower.includes("biostat")) return "Biostat";
        if (lower.includes("research")) return "Research";
        if (lower.includes("env")) return "Env Health";
        if (lower.includes("prog")) return "Prog Mgmt";
        if (lower.includes("comm")) return "Prof Comm";
        return compName.substring(0, 8);
    }

    // -------------------------------------------------------------
    // Dual-Entry Authentication Flow (Candidate & Administrator)
    // -------------------------------------------------------------
    function switchAuthRole(role) {
        if (role === "admin") {
            if (dom.authTabAdmin) dom.authTabAdmin.classList.add("active");
            if (dom.authTabCandidate) dom.authTabCandidate.classList.remove("active");
            if (dom.candidateAuthForm) dom.candidateAuthForm.style.display = "none";
            if (dom.adminAuthForm) dom.adminAuthForm.style.display = "flex";
            if (dom.inputAdminPasskey) {
                dom.inputAdminPasskey.focus();
            }
        } else {
            if (dom.authTabCandidate) dom.authTabCandidate.classList.add("active");
            if (dom.authTabAdmin) dom.authTabAdmin.classList.remove("active");
            if (dom.candidateAuthForm) dom.candidateAuthForm.style.display = "flex";
            if (dom.adminAuthForm) dom.adminAuthForm.style.display = "none";
            updateLoginButtonState();
        }
    }

    function updateLoginButtonState() {
        const name = dom.inputCandidateName ? dom.inputCandidateName.value.trim() : "";
        const id = dom.inputCandidateId ? dom.inputCandidateId.value.trim() : "";
        const agreed = dom.termsAgree ? dom.termsAgree.checked : false;
        if (dom.btnCandidateLogin) {
            dom.btnCandidateLogin.disabled = !(name.length > 0 && id.length > 0 && agreed);
        }
    }

    function handleCandidateLogin(e) {
        if (e && e.preventDefault) e.preventDefault();

        const nameInput = dom.inputCandidateName ? dom.inputCandidateName.value.trim() : "";
        const idInput = dom.inputCandidateId ? dom.inputCandidateId.value.trim() : "";
        const agreed = dom.termsAgree ? dom.termsAgree.checked : false;

        if (!nameInput || !idInput || !agreed) {
            showToast("Please enter your name, ID, and accept the assessment terms.", "error");
            return;
        }

        state.userRole = "candidate";
        state.candidate.name = nameInput;
        state.candidate.id = idInput;
        state.candidate.track = "all";
        state.isAuthenticated = true;

        // Update Header Utility Bar for Candidate
        if (dom.chipUserLabel) dom.chipUserLabel.textContent = "Candidate:";
        if (dom.chipIdLabel) dom.chipIdLabel.textContent = "ID:";
        if (dom.headerCandidateName) dom.headerCandidateName.textContent = state.candidate.name;
        if (dom.headerCandidateId) dom.headerCandidateId.textContent = state.candidate.id;

        // Strictly Hide Faculty Console & Redundant Admin Controls
        if (dom.btnAdminManage) dom.btnAdminManage.style.display = "none";
        if (dom.adminConsoleView) dom.adminConsoleView.style.display = "none";
        if (dom.facultyPreviewBanner) dom.facultyPreviewBanner.style.display = "none";

        // Show Candidate Views, Student Assessment Tabs & Timer HUD
        if (dom.candidateViewsContainer) dom.candidateViewsContainer.style.display = "block";
        if (dom.headerNavTabs) dom.headerNavTabs.style.display = "flex";
        if (dom.sessionTimerBadge) dom.sessionTimerBadge.style.display = "flex";
        if (dom.btnAppLogout) dom.btnAppLogout.style.display = "inline-flex";

        // Hide Auth Gate, Reveal Main Platform
        if (dom.candidateAuthModal) dom.candidateAuthModal.style.display = "none";
        if (dom.appMainLayout) dom.appMainLayout.style.display = "flex";

        showToast(`Candidate authenticated: ${state.candidate.name} (${state.candidate.id})`, "success");
    }

    function handleAdminLogin(e) {
        if (e && e.preventDefault) e.preventDefault();

        const passkey = dom.inputAdminPasskey ? dom.inputAdminPasskey.value.trim() : "";
        if (passkey !== "admin123") {
            showToast("Invalid administrative passkey. Please check passkey and try again.", "error");
            if (dom.inputAdminPasskey) {
                dom.inputAdminPasskey.focus();
                dom.inputAdminPasskey.select();
            }
            return;
        }

        state.userRole = "admin";
        state.candidate.name = "Institutional Administrator";
        state.candidate.id = "Full Curriculum Management";
        state.candidate.track = "all";
        state.isAuthenticated = true;

        // Update Header Utility Bar to: ROLE: Institutional Administrator • ACCESS: Full Curriculum Management
        if (dom.chipUserLabel) dom.chipUserLabel.textContent = "ROLE:";
        if (dom.chipIdLabel) dom.chipIdLabel.textContent = "ACCESS:";
        if (dom.headerCandidateName) dom.headerCandidateName.textContent = "Institutional Administrator";
        if (dom.headerCandidateId) dom.headerCandidateId.textContent = "Full Curriculum Management";

        // Hide Student Assessment Navigation Tabs for Admin
        if (dom.headerNavTabs) dom.headerNavTabs.style.display = "none";

        // Hide Redundant [Manage Curriculum & Banks] Button (Admin Console is already active)
        if (dom.btnAdminManage) dom.btnAdminManage.style.display = "none";

        // Hide Exam Timer HUD for Admin
        if (dom.sessionTimerBadge) dom.sessionTimerBadge.style.display = "none";

        // Keep [Log Out] clearly visible
        if (dom.btnAppLogout) dom.btnAppLogout.style.display = "inline-flex";

        // Switch Main View to Admin Console View & Hide Candidate Exam Cockpit
        if (dom.adminConsoleView) dom.adminConsoleView.style.display = "flex";
        if (dom.candidateViewsContainer) dom.candidateViewsContainer.style.display = "none";
        if (dom.facultyPreviewBanner) dom.facultyPreviewBanner.style.display = "none";

        // Hide Auth Gate, Reveal Main Platform
        if (dom.candidateAuthModal) dom.candidateAuthModal.style.display = "none";
        if (dom.appMainLayout) dom.appMainLayout.style.display = "flex";

        renderAdminTelemetry();
        showToast("Institutional Administrator authenticated. Management console active.", "success");
    }

    function handleFacultyPreviewExam() {
        if (dom.adminConsoleView) dom.adminConsoleView.style.display = "none";
        if (dom.candidateViewsContainer) dom.candidateViewsContainer.style.display = "block";
        if (dom.facultyPreviewBanner) dom.facultyPreviewBanner.style.display = "flex";

        // Show Student Navigation Tabs & Timer HUD for Preview Run
        if (dom.headerNavTabs) dom.headerNavTabs.style.display = "flex";
        if (dom.sessionTimerBadge) dom.sessionTimerBadge.style.display = "flex";

        switchTab("practice");
        showToast("Faculty Assessment Preview active (Non-scoring test run).", "info");
    }

    function handleReturnAdminConsole() {
        if (dom.adminConsoleView) dom.adminConsoleView.style.display = "flex";
        if (dom.candidateViewsContainer) dom.candidateViewsContainer.style.display = "none";
        if (dom.facultyPreviewBanner) dom.facultyPreviewBanner.style.display = "none";

        // Hide Student Tabs & Timer HUD
        if (dom.headerNavTabs) dom.headerNavTabs.style.display = "none";
        if (dom.sessionTimerBadge) dom.sessionTimerBadge.style.display = "none";
        if (dom.btnAdminManage) dom.btnAdminManage.style.display = "none";

        // Reset User Info Bar to Institutional Administrator
        if (dom.chipUserLabel) dom.chipUserLabel.textContent = "ROLE:";
        if (dom.chipIdLabel) dom.chipIdLabel.textContent = "ACCESS:";
        if (dom.headerCandidateName) dom.headerCandidateName.textContent = "Institutional Administrator";
        if (dom.headerCandidateId) dom.headerCandidateId.textContent = "Full Curriculum Management";

        renderAdminTelemetry();
        showToast("Returned to Administrative Management Console.", "info");
    }

    function handleAppLogout() {
        state.isAuthenticated = false;
        state.isExamLaunched = false;
        state.isExamSubmitted = false;
        if (state.timerIntervalId) clearInterval(state.timerIntervalId);

        if (dom.appMainLayout) dom.appMainLayout.style.display = "none";
        if (dom.candidateAuthModal) dom.candidateAuthModal.style.display = "flex";
        if (dom.inputAdminPasskey) dom.inputAdminPasskey.value = "";

        switchAuthRole("candidate");
        showToast("Logged out successfully.", "info");
    }

    async function renderAdminTelemetry() {
        try {
            const res = await fetch(`${API_BASE}/health`);
            if (!res.ok) return;
            const data = await res.json();
            const vecPassages = (data.vector_store && typeof data.vector_store.total_passages === "number")
                ? data.vector_store.total_passages
                : ((data.vector_store && data.vector_store.total_passages != null) ? data.vector_store.total_passages : 16);

            if (dom.adminStatPassages) dom.adminStatPassages.textContent = String(vecPassages);
            if (dom.adminStatQuestions) dom.adminStatQuestions.textContent = String(data.questions_indexed || 6);
            if (dom.adminStatScenarios) dom.adminStatScenarios.textContent = String(data.scenarios_indexed || 1);
            if (dom.adminStatPath && data.vector_store && data.vector_store.storage_path) {
                const parts = data.vector_store.storage_path.split(/[\\/]/);
                dom.adminStatPath.textContent = parts.slice(-2).join("/");
            }
        } catch (e) {
            console.error("Failed to render admin telemetry:", e);
        }
    }

    function navigateToDashboard() {
        switchTab("dashboard");
        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    // -------------------------------------------------------------
    // Application Initialization
    // -------------------------------------------------------------
    async function init() {
        state.sessionId = generateUUID();
        if (dom.sessionIdDisplay) {
            dom.sessionIdDisplay.textContent = state.sessionId;
            dom.sessionIdDisplay.title = state.sessionId;
        }

        // Initialize HUD timer to paused state with clean label
        if (dom.sessionTimerDisplay) {
            dom.sessionTimerDisplay.textContent = "Time Remaining: Paused \u2022 15:00";
        }

        updateLoginButtonState();
        setupEventListeners();
        await checkSystemHealth();
        await Promise.all([
            fetchCompetencies(),
            fetchQuestions(),
            fetchScenarios(),
        ]);
    }

    // -------------------------------------------------------------
    // Event Listeners Setup
    // -------------------------------------------------------------
    function setupEventListeners() {
        // Dual-Entry Role Tabs
        if (dom.authTabCandidate) {
            dom.authTabCandidate.addEventListener("click", () => switchAuthRole("candidate"));
        }
        if (dom.authTabAdmin) {
            dom.authTabAdmin.addEventListener("click", () => switchAuthRole("admin"));
        }

        // Candidate Authentication Form & Inputs
        if (dom.candidateAuthForm) {
            dom.candidateAuthForm.addEventListener("submit", handleCandidateLogin);
        }
        if (dom.btnCandidateLogin) {
            dom.btnCandidateLogin.addEventListener("click", handleCandidateLogin);
        }
        if (dom.inputCandidateName) {
            dom.inputCandidateName.addEventListener("input", updateLoginButtonState);
        }
        if (dom.inputCandidateId) {
            dom.inputCandidateId.addEventListener("input", updateLoginButtonState);
        }
        if (dom.termsAgree) {
            dom.termsAgree.addEventListener("change", updateLoginButtonState);
        }

        // Faculty & Administrator Authentication Form
        if (dom.adminAuthForm) {
            dom.adminAuthForm.addEventListener("submit", handleAdminLogin);
        }
        if (dom.btnAdminLogin) {
            dom.btnAdminLogin.addEventListener("click", handleAdminLogin);
        }

        // Tab switching
        dom.tabButtons.forEach(btn => {
            btn.addEventListener("click", () => {
                const targetTab = btn.getAttribute("data-tab");
                switchTab(targetTab);
            });
        });

        // Launch Exam Button
        if (dom.btnStartExam) {
            dom.btnStartExam.addEventListener("click", launchExamSession);
        }

        // Exam Navigation: Previous & Next / Finish
        if (dom.btnExamPrev) {
            dom.btnExamPrev.addEventListener("click", goToPrevQuestion);
        }
        if (dom.btnExamNext) {
            dom.btnExamNext.addEventListener("click", handleNextOrFinishClick);
        }

        // Flag item for review toggle (Top and Bottom Dock)
        if (dom.btnFlagItem) {
            dom.btnFlagItem.addEventListener("click", toggleFlagCurrentItem);
        }
        if (dom.btnFlagDock) {
            dom.btnFlagDock.addEventListener("click", toggleFlagCurrentItem);
        }

        // Finish Exam Button from Sidebar
        if (dom.btnSidebarFinishExam) {
            dom.btnSidebarFinishExam.addEventListener("click", openSubmitConfirmModal);
        }

        // Jump to Dashboard from Review Banner and Bottom Dock View Button
        if (dom.btnReviewJumpDashboard) {
            dom.btnReviewJumpDashboard.addEventListener("click", navigateToDashboard);
        }
        if (dom.btnViewDashboard) {
            dom.btnViewDashboard.addEventListener("click", navigateToDashboard);
        }

        // Submit Confirmation Modal Actions
        if (dom.btnCancelSubmit) {
            dom.btnCancelSubmit.addEventListener("click", closeSubmitConfirmModal);
        }
        if (dom.btnConfirmSubmit) {
            dom.btnConfirmSubmit.addEventListener("click", confirmAndSubmitExam);
        }
        if (dom.submitConfirmModalOverlay) {
            dom.submitConfirmModalOverlay.addEventListener("click", (e) => {
                if (e.target === dom.submitConfirmModalOverlay) {
                    closeSubmitConfirmModal();
                }
            });
        }

        // Domain Selector within Matrix
        if (dom.examDomainSelect) {
            dom.examDomainSelect.addEventListener("change", (e) => {
                const selectedPillar = e.target.value;
                if (selectedPillar === "all") return;
                const matchIdx = state.questionsData.findIndex(q => q.competency_id === selectedPillar);
                if (matchIdx >= 0) {
                    selectActiveQuestion(matchIdx);
                }
            });
        }

        // Outbreak Scenario Commit Buttons
        if (dom.btnCommitStage1) {
            dom.btnCommitStage1.addEventListener("click", () => handleScenarioStageCommit(1));
        }
        if (dom.btnCommitStage2) {
            dom.btnCommitStage2.addEventListener("click", () => handleScenarioStageCommit(2));
        }
        if (dom.btnViewSimDashboard) {
            dom.btnViewSimDashboard.addEventListener("click", navigateToDashboard);
        }

        // Reset Session Button
        if (dom.btnResetSession) {
            dom.btnResetSession.addEventListener("click", resetSession);
        }

        // Export Official Transcript
        if (dom.btnExportRecord) {
            dom.btnExportRecord.addEventListener("click", handleExportTranscript);
        }
        if (dom.btnPrintTranscript) {
            dom.btnPrintTranscript.addEventListener("click", () => window.print());
        }
        if (dom.btnCloseTranscriptModal) {
            dom.btnCloseTranscriptModal.addEventListener("click", closeTranscriptModal);
        }
        if (dom.transcriptModalOverlay) {
            dom.transcriptModalOverlay.addEventListener("click", (e) => {
                if (e.target === dom.transcriptModalOverlay) {
                    closeTranscriptModal();
                }
            });
        }

        // Remediation Drawer
        if (dom.btnCloseDrawer) dom.btnCloseDrawer.addEventListener("click", closeRemediationDrawer);
        if (dom.btnDrawerDismiss) dom.btnDrawerDismiss.addEventListener("click", closeRemediationDrawer);
        if (dom.drawerOverlay) dom.drawerOverlay.addEventListener("click", closeRemediationDrawer);
        if (dom.btnDrawerPracticeNow) {
            dom.btnDrawerPracticeNow.addEventListener("click", () => {
                if (state.activeRemediationPillar) {
                    closeRemediationDrawer();
                    switchTab("practice");
                    if (dom.examDomainSelect) {
                        dom.examDomainSelect.value = state.activeRemediationPillar;
                        const matchIdx = state.questionsData.findIndex(q => q.competency_id === state.activeRemediationPillar);
                        if (matchIdx >= 0) selectActiveQuestion(matchIdx);
                    }
                }
            });
        }

        // Admin Navigation & Quick Actions
        if (dom.btnPreviewExam) {
            dom.btnPreviewExam.addEventListener("click", handleFacultyPreviewExam);
        }
        if (dom.btnReturnAdminConsole) {
            dom.btnReturnAdminConsole.addEventListener("click", handleReturnAdminConsole);
        }
        if (dom.btnAppLogout) {
            dom.btnAppLogout.addEventListener("click", handleAppLogout);
        }

        // Admin Management Modal Wiring
        if (dom.btnAdminManage) {
            dom.btnAdminManage.addEventListener("click", openAdminModal);
        }
        if (dom.btnCloseAdminModal) {
            dom.btnCloseAdminModal.addEventListener("click", closeAdminModal);
        }
        if (dom.adminManageModal) {
            dom.adminManageModal.addEventListener("click", (e) => {
                if (e.target === dom.adminManageModal) closeAdminModal();
            });
        }

        // Modal Curriculum Dropzone & File Input
        if (dom.inputCurriculumFile) {
            dom.inputCurriculumFile.addEventListener("change", (e) => {
                const file = e.target.files && e.target.files[0];
                handleCurriculumFileSelect(file, false);
            });
        }
        if (dom.curriculumDropzone) {
            ["dragenter", "dragover"].forEach(eventName => {
                dom.curriculumDropzone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    dom.curriculumDropzone.classList.add("dragover");
                });
            });
            ["dragleave", "drop"].forEach(eventName => {
                dom.curriculumDropzone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    dom.curriculumDropzone.classList.remove("dragover");
                });
            });
            dom.curriculumDropzone.addEventListener("drop", (e) => {
                const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
                handleCurriculumFileSelect(file, false);
            });
        }
        if (dom.btnClearCurriculumFile) {
            dom.btnClearCurriculumFile.addEventListener("click", (e) => clearCurriculumFile(e, false));
        }
        if (dom.btnUploadCurriculum) {
            dom.btnUploadCurriculum.addEventListener("click", () => uploadCurriculumFile(false));
        }

        // Modal Questions Dropzone & File Input
        if (dom.inputQuestionsFile) {
            dom.inputQuestionsFile.addEventListener("change", (e) => {
                const file = e.target.files && e.target.files[0];
                handleQuestionsFileSelect(file, false);
            });
        }
        if (dom.questionsDropzone) {
            ["dragenter", "dragover"].forEach(eventName => {
                dom.questionsDropzone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    dom.questionsDropzone.classList.add("dragover");
                });
            });
            ["dragleave", "drop"].forEach(eventName => {
                dom.questionsDropzone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    dom.questionsDropzone.classList.remove("dragover");
                });
            });
            dom.questionsDropzone.addEventListener("drop", (e) => {
                const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
                handleQuestionsFileSelect(file, false);
            });
        }
        if (dom.btnClearQuestionsFile) {
            dom.btnClearQuestionsFile.addEventListener("click", (e) => clearQuestionsFile(e, false));
        }
        if (dom.btnUploadQuestions) {
            dom.btnUploadQuestions.addEventListener("click", () => uploadQuestionsFile(false));
        }

        // Console Panel Curriculum Dropzone & File Input
        if (dom.panelInputCurriculumFile) {
            dom.panelInputCurriculumFile.addEventListener("change", (e) => {
                const file = e.target.files && e.target.files[0];
                handleCurriculumFileSelect(file, true);
            });
        }
        if (dom.panelCurriculumDropzone) {
            ["dragenter", "dragover"].forEach(eventName => {
                dom.panelCurriculumDropzone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    dom.panelCurriculumDropzone.classList.add("dragover");
                });
            });
            ["dragleave", "drop"].forEach(eventName => {
                dom.panelCurriculumDropzone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    dom.panelCurriculumDropzone.classList.remove("dragover");
                });
            });
            dom.panelCurriculumDropzone.addEventListener("drop", (e) => {
                const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
                handleCurriculumFileSelect(file, true);
            });
        }
        if (dom.btnClearPanelCurriculumFile) {
            dom.btnClearPanelCurriculumFile.addEventListener("click", (e) => clearCurriculumFile(e, true));
        }
        if (dom.btnPanelUploadCurriculum) {
            dom.btnPanelUploadCurriculum.addEventListener("click", () => uploadCurriculumFile(true));
        }

        // Console Panel Questions Dropzone & File Input
        if (dom.panelInputQuestionsFile) {
            dom.panelInputQuestionsFile.addEventListener("change", (e) => {
                const file = e.target.files && e.target.files[0];
                handleQuestionsFileSelect(file, true);
            });
        }
        if (dom.panelQuestionsDropzone) {
            ["dragenter", "dragover"].forEach(eventName => {
                dom.panelQuestionsDropzone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    dom.panelQuestionsDropzone.classList.add("dragover");
                });
            });
            ["dragleave", "drop"].forEach(eventName => {
                dom.panelQuestionsDropzone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    dom.panelQuestionsDropzone.classList.remove("dragover");
                });
            });
            dom.panelQuestionsDropzone.addEventListener("drop", (e) => {
                const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
                handleQuestionsFileSelect(file, true);
            });
        }
        if (dom.btnClearPanelQuestionsFile) {
            dom.btnClearPanelQuestionsFile.addEventListener("click", (e) => clearQuestionsFile(e, true));
        }
        if (dom.btnPanelUploadQuestions) {
            dom.btnPanelUploadQuestions.addEventListener("click", () => uploadQuestionsFile(true));
        }

        // Keyboard Shortcuts (ArrowLeft / ArrowRight navigation)
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                closeRemediationDrawer();
                closeTranscriptModal();
                closeSubmitConfirmModal();
                closeAdminModal();
                return;
            }

            if (state.activeTab === "practice" && state.isExamLaunched) {
                const tag = (document.activeElement && document.activeElement.tagName) || "";
                if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;

                if (e.key === "ArrowLeft") {
                    e.preventDefault();
                    goToPrevQuestion();
                } else if (e.key === "ArrowRight") {
                    e.preventDefault();
                    if (state.activeQuestionIndex < state.questionsData.length - 1) {
                        goToNextQuestion();
                    }
                }
            }
        });
    }

    function switchTab(tabKey) {
        state.activeTab = tabKey;
        dom.tabButtons.forEach(btn => {
            const isMatch = btn.getAttribute("data-tab") === tabKey;
            btn.classList.toggle("active", isMatch);
            btn.setAttribute("aria-selected", isMatch ? "true" : "false");
        });
        dom.tabContents.forEach(content => {
            content.classList.toggle("active", content.id === `tab-content-${tabKey}`);
        });

        if (tabKey === "dashboard") {
            renderDashboard();
        }
    }

    // -------------------------------------------------------------
    // API Data Fetchers
    // -------------------------------------------------------------
    async function checkSystemHealth() {
        try {
            const res = await fetch(`${API_BASE}/health`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            const questionsCount = typeof data.questions_indexed === "number" ? data.questions_indexed : 6;
            let vecPassages = 16;
            if (data.vector_store && typeof data.vector_store.total_passages === "number") {
                vecPassages = data.vector_store.total_passages;
            } else if (data.vector_store && data.vector_store.total_passages != null) {
                vecPassages = data.vector_store.total_passages;
            }
            if (dom.systemHealthText) {
                dom.systemHealthText.textContent = `Online \u2022 ${questionsCount} MCQs \u2022 ${vecPassages} Grounded Passages`;
            }
            const dot = dom.systemHealthPill ? dom.systemHealthPill.querySelector(".health-status-dot") : null;
            if (dot) dot.classList.remove("error");
        } catch (err) {
            console.error("Health check failed:", err);
            if (dom.systemHealthText) dom.systemHealthText.textContent = "API Offline / Error";
            const dot = dom.systemHealthPill ? dom.systemHealthPill.querySelector(".health-status-dot") : null;
            if (dot) dot.classList.add("error");
        }
    }

    async function fetchCompetencies() {
        try {
            const res = await fetch(`${API_BASE}/competencies`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            state.competencies = await res.json();
            populateDomainSelect();
            renderInitialDashboardCompetencies();
        } catch (err) {
            console.error("Failed to load competencies:", err);
            showToast("Failed to load core competency domains.", "error");
        }
    }

    async function fetchQuestions() {
        try {
            const res = await fetch(`${API_BASE}/questions`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            state.questionsData = await res.json();

            if (dom.practiceCountBadge) {
                dom.practiceCountBadge.textContent = `${state.questionsData.length} Items`;
            }

            if (state.isExamLaunched) {
                renderItemMatrix();
                renderActiveQuestion();
            }
        } catch (err) {
            console.error("Failed to load questions:", err);
            showToast("Failed to load practice questions from backend API.", "error");
        }
    }

    async function fetchScenarios() {
        try {
            const res = await fetch(`${API_BASE}/scenarios`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            state.scenariosData = await res.json();
            renderScenarioBriefing();
        } catch (err) {
            console.error("Failed to load scenarios:", err);
            showToast("Failed to load outbreak scenarios.", "error");
        }
    }

    function populateDomainSelect() {
        if (!dom.examDomainSelect) return;
        dom.examDomainSelect.innerHTML = `<option value="all">All Domains (${state.questionsData.length || 6} Items)</option>`;
        state.competencies.forEach(c => {
            const opt = document.createElement("option");
            opt.value = c.id;
            opt.textContent = c.name;
            dom.examDomainSelect.appendChild(opt);
        });
    }

    // -------------------------------------------------------------
    // Standardized Examination Cockpit Engine
    // -------------------------------------------------------------
    function launchExamSession() {
        state.isExamLaunched = true;
        state.isExamSubmitted = false;
        state.timeRemainingSec = EXAM_DURATION_SECONDS;
        state.activeQuestionIndex = 0;

        // Hide Briefing Gate, Show Cockpit
        if (dom.candidateBriefingGate) dom.candidateBriefingGate.style.display = "none";
        if (dom.examCockpitContainer) dom.examCockpitContainer.style.display = "block";
        if (dom.examReviewBanner) dom.examReviewBanner.style.display = "none";

        // Reset Sidebar Finish Button visibility
        if (dom.btnSidebarFinishExam) dom.btnSidebarFinishExam.style.display = "block";

        // Start Countdown Timer
        startExamCountdown();

        // Render UI Matrix & Question 1
        renderItemMatrix();
        renderActiveQuestion();
        updateExamTelemetry();

        showToast("Examination session launched. 15:00 countdown active.", "info");
    }

    function startExamCountdown() {
        if (state.timerIntervalId) clearInterval(state.timerIntervalId);

        state.timerIntervalId = setInterval(() => {
            state.timeRemainingSec -= 1;

            if (dom.sessionTimerDisplay) {
                dom.sessionTimerDisplay.textContent = `Time Remaining: ${formatTime(state.timeRemainingSec)}`;
                if (state.timeRemainingSec <= 120) {
                    dom.sessionTimerDisplay.style.color = "var(--danger)";
                } else {
                    dom.sessionTimerDisplay.style.color = "var(--accent-cyan)";
                }
            }

            if (state.timeRemainingSec <= 0) {
                clearInterval(state.timerIntervalId);
                showToast("Time expired! Submitting your examination.", "error");
                confirmAndSubmitExam();
            }
        }, 1000);
    }

    function renderItemMatrix() {
        if (!dom.matrixGrid) return;
        dom.matrixGrid.innerHTML = "";

        const total = state.questionsData.length;

        state.questionsData.forEach((q, idx) => {
            const btn = document.createElement("button");
            btn.className = "matrix-btn";
            btn.id = `matrix-btn-${idx}`;
            btn.title = `Jump to Item ${idx + 1}`;

            const compObj = state.competencies.find(c => c.id === q.competency_id);
            const compAbbr = compObj ? getCompetencyAbbr(compObj.name) : q.competency_id.toUpperCase();

            // Styling States
            const isCurrent = idx === state.activeQuestionIndex;
            const isAnswered = !!state.selectedObjectiveAnswers[q.id];
            const isFlagged = !!state.flaggedQuestions[q.id];

            if (isCurrent) btn.classList.add("current");
            if (isAnswered) btn.classList.add("answered");
            else btn.classList.add("unanswered");
            if (isFlagged) btn.classList.add("flagged");

            let statusClass = isAnswered ? "completed" : "incomplete";
            let statusBadgeText = isAnswered ? "DONE" : "";

            // Review Mode Scoring Highlights
            if (state.isExamSubmitted && state.latestEvaluation) {
                const res = state.latestEvaluation.objective_results.find(r => r.question_id === q.id);
                if (res) {
                    if (res.is_correct) {
                        btn.classList.add("matrix-correct");
                        statusClass = "correct";
                        statusBadgeText = "PASS";
                    } else {
                        btn.classList.add("matrix-incorrect");
                        statusClass = "incorrect";
                        statusBadgeText = "FAIL";
                    }
                }
            }

            btn.innerHTML = `
                <div class="matrix-btn-main">
                    <span class="matrix-btn-num">Q${idx + 1}</span>
                    <span class="matrix-btn-pillar">${compAbbr}</span>
                </div>
                <div class="matrix-btn-status">
                    ${isFlagged ? '<span class="status-flag-tag" title="Flagged for review">FLAG</span>' : ''}
                    <span class="status-indicator-badge ${statusClass}">${statusBadgeText}</span>
                </div>
            `;

            btn.addEventListener("click", () => selectActiveQuestion(idx));
            dom.matrixGrid.appendChild(btn);
        });

        if (dom.matrixActiveIndicator) {
            dom.matrixActiveIndicator.textContent = `Item ${state.activeQuestionIndex + 1} of ${total}`;
        }
    }

    function selectActiveQuestion(index) {
        if (index < 0 || index >= state.questionsData.length) return;
        state.activeQuestionIndex = index;
        renderActiveQuestion();
        renderItemMatrix();
    }

    function renderActiveQuestion() {
        if (!state.questionsData || state.questionsData.length === 0) return;

        const total = state.questionsData.length;
        const q = state.questionsData[state.activeQuestionIndex];
        if (!q) return;

        const compObj = state.competencies.find(c => c.id === q.competency_id);
        const compName = compObj ? compObj.name : q.competency_id.toUpperCase();

        // 1. Header Meta
        if (dom.examItemBadge) {
            dom.examItemBadge.textContent = `ITEM ${String(state.activeQuestionIndex + 1).padStart(2, "0")} OF ${String(total).padStart(2, "0")}`;
        }
        if (dom.examPillarBadge) {
            dom.examPillarBadge.textContent = compName;
        }

        // 2. Flag Button Synchronization
        const isFlagged = !!state.flaggedQuestions[q.id];
        if (dom.btnFlagItem) {
            dom.btnFlagItem.classList.toggle("flagged", isFlagged);
            if (dom.flagBtnText) {
                dom.flagBtnText.textContent = isFlagged ? "Flagged for Review" : "Flag for Review";
            }
        }
        if (dom.btnFlagDock) {
            dom.btnFlagDock.classList.toggle("flagged", isFlagged);
            if (dom.flagDockText) {
                dom.flagDockText.textContent = isFlagged ? "Flagged for Review" : "Flag for Review";
            }
        }

        // 3. Question Prompt
        if (dom.examQuestionPrompt) {
            dom.examQuestionPrompt.textContent = q.text;
        }

        // 4. Options Grid
        if (dom.examOptionsGrid) {
            dom.examOptionsGrid.innerHTML = "";
            const selectedOpt = state.selectedObjectiveAnswers[q.id] || null;

            // Check if submitted for review mode
            let reviewRes = null;
            if (state.isExamSubmitted && state.latestEvaluation) {
                reviewRes = state.latestEvaluation.objective_results.find(r => r.question_id === q.id);
            }

            q.options.forEach(opt => {
                const optEl = document.createElement("div");
                optEl.className = "option-item";

                if (selectedOpt === opt.id) {
                    optEl.classList.add("selected");
                }

                let choiceTagHtml = "";

                if (state.isExamSubmitted && reviewRes) {
                    if (opt.id === reviewRes.correct_option_id) {
                        optEl.style.borderColor = "var(--success)";
                        optEl.style.background = "var(--success-bg)";
                        choiceTagHtml = `<span class="review-choice-tag correct">Correct Answer</span>`;
                    } else if (opt.id === reviewRes.selected_option_id && !reviewRes.is_correct) {
                        optEl.style.borderColor = "var(--danger)";
                        optEl.style.background = "var(--danger-bg)";
                        choiceTagHtml = `<span class="review-choice-tag incorrect">Your Selection</span>`;
                    }
                }

                optEl.innerHTML = `
                    <div class="option-key">${opt.id}</div>
                    <div class="option-content-wrap">
                        <div class="option-text">${opt.text}</div>
                        ${choiceTagHtml}
                    </div>
                `;

                if (!state.isExamSubmitted) {
                    optEl.addEventListener("click", () => {
                        selectObjectiveAnswer(q.id, opt.id);
                    });
                }

                dom.examOptionsGrid.appendChild(optEl);
            });
        }

        // 5. Review Feedback Stage Callout
        if (dom.stageItemReviewFeedback) {
            if (state.isExamSubmitted && state.latestEvaluation) {
                const res = state.latestEvaluation.objective_results.find(r => r.question_id === q.id);
                if (res) {
                    dom.stageItemReviewFeedback.style.display = "flex";
                    dom.stageItemReviewFeedback.className = `stage-item-review-feedback ${res.is_correct ? "correct" : "incorrect"}`;
                    dom.stageItemReviewFeedback.innerHTML = `
                        <div class="feedback-item-header">
                            <div>
                                <span class="feedback-badge" style="background: ${res.is_correct ? 'var(--success)' : 'var(--danger)'}; color: #ffffff;">
                                    ${res.is_correct ? "Correct Response" : "Incorrect Response"}
                                </span>
                                <strong style="margin-left: 10px; font-size: 13px; color: var(--text-primary);">${compName}</strong>
                            </div>
                            <span style="font-family: var(--font-mono); font-size: 12px; color: var(--text-muted);">
                                Your Choice: <strong style="color: ${res.is_correct ? 'var(--success)' : 'var(--danger)'};">${res.selected_option_id.toUpperCase()}</strong> | Correct: <strong style="color: var(--success);">${res.correct_option_id.toUpperCase()}</strong>
                            </span>
                        </div>
                        <div class="feedback-explanation">
                            <strong>Standardized Methodological Rationale:</strong><br>
                            ${res.explanation}
                        </div>
                        <div class="citation-callout">
                            <span class="citation-tag">Authoritative Curriculum Citation</span>
                            <span class="citation-text">${res.citation}</span>
                        </div>
                    `;
                }
            } else {
                dom.stageItemReviewFeedback.style.display = "none";
            }
        }

        // 6. Navigation Buttons & Footer Control
        const isLast = state.activeQuestionIndex === total - 1;

        if (dom.btnExamPrev) {
            dom.btnExamPrev.disabled = state.activeQuestionIndex === 0;
            if (dom.btnExamPrevText) {
                dom.btnExamPrevText.textContent = state.isExamSubmitted ? "Previous Item" : "Previous";
            }
        }

        if (!state.isExamSubmitted) {
            // Testing Mode: Show Flag button and Single Next / Finish button
            if (dom.btnFlagDock) dom.btnFlagDock.style.display = "inline-flex";
            if (dom.btnFlagItem) dom.btnFlagItem.style.display = "inline-flex";
            if (dom.stageKeyboardHint) dom.stageKeyboardHint.style.display = "block";
            if (dom.stageReviewPositionBadge) dom.stageReviewPositionBadge.style.display = "none";
            if (dom.btnViewDashboard) dom.btnViewDashboard.style.display = "none";
            if (dom.btnSidebarFinishExam) dom.btnSidebarFinishExam.style.display = "block";

            if (dom.btnExamNext) {
                dom.btnExamNext.style.display = "inline-flex";
                dom.btnExamNext.disabled = false;
                if (isLast) {
                    if (dom.btnExamNextText) dom.btnExamNextText.textContent = "Finish & Submit Exam";
                    dom.btnExamNext.className = "btn btn-primary";
                } else {
                    if (dom.btnExamNextText) dom.btnExamNextText.textContent = "Next";
                    dom.btnExamNext.className = "btn btn-secondary";
                }
            }
        } else {
            // Review Mode: Hide Flagging and Submit button. Show Item Navigator position & View Dashboard action
            if (dom.btnFlagDock) dom.btnFlagDock.style.display = "none";
            if (dom.btnFlagItem) dom.btnFlagItem.style.display = "none";
            if (dom.stageKeyboardHint) dom.stageKeyboardHint.style.display = "none";
            if (dom.btnSidebarFinishExam) dom.btnSidebarFinishExam.style.display = "none";

            if (dom.stageReviewPositionBadge) {
                dom.stageReviewPositionBadge.style.display = "inline-flex";
            }
            if (dom.stageReviewPositionText) {
                dom.stageReviewPositionText.textContent = `Item ${state.activeQuestionIndex + 1} of ${total} (Review Mode)`;
            }

            if (dom.btnExamNext) {
                dom.btnExamNext.style.display = "inline-flex";
                dom.btnExamNext.disabled = isLast;
                if (dom.btnExamNextText) dom.btnExamNextText.textContent = "Next Item";
                dom.btnExamNext.className = "btn btn-secondary";
            }

            if (dom.btnViewDashboard) {
                dom.btnViewDashboard.style.display = "inline-flex";
            }
        }

        updateExamTelemetry();
    }

    function selectObjectiveAnswer(questionId, optionId) {
        if (state.isExamSubmitted) return;

        state.selectedObjectiveAnswers[questionId] = optionId;
        renderActiveQuestion();
        renderItemMatrix();
        updateExamTelemetry();

        // Automatic advance after 220ms
        if (state.activeQuestionIndex < state.questionsData.length - 1) {
            setTimeout(() => {
                goToNextQuestion();
            }, 220);
        }
    }

    function toggleFlagCurrentItem() {
        if (state.isExamSubmitted) return;
        const q = state.questionsData[state.activeQuestionIndex];
        if (!q) return;

        if (state.flaggedQuestions[q.id]) {
            delete state.flaggedQuestions[q.id];
        } else {
            state.flaggedQuestions[q.id] = true;
        }

        renderActiveQuestion();
        renderItemMatrix();
        updateExamTelemetry();
    }

    function goToPrevQuestion() {
        if (state.activeQuestionIndex > 0) {
            selectActiveQuestion(state.activeQuestionIndex - 1);
        }
    }

    function goToNextQuestion() {
        if (state.activeQuestionIndex < state.questionsData.length - 1) {
            selectActiveQuestion(state.activeQuestionIndex + 1);
        }
    }

    function handleNextOrFinishClick() {
        const isLast = state.activeQuestionIndex === state.questionsData.length - 1;
        if (!state.isExamSubmitted) {
            if (isLast) {
                openSubmitConfirmModal();
            } else {
                goToNextQuestion();
            }
        } else {
            if (!isLast) {
                goToNextQuestion();
            }
        }
    }

    function updateExamTelemetry() {
        const total = state.questionsData.length;
        const answered = Object.keys(state.selectedObjectiveAnswers).length;
        const flaggedCount = Object.keys(state.flaggedQuestions).length;
        const pct = total > 0 ? Math.round((answered / total) * 100) : 0;

        if (dom.matrixAnsweredStat) {
            dom.matrixAnsweredStat.textContent = `Answered: ${answered} / ${total}`;
        }
        if (dom.matrixFlaggedStat) {
            dom.matrixFlaggedStat.textContent = `Flagged: ${flaggedCount}`;
        }

        // Header Progress Bar
        if (dom.headerProgressBar) {
            dom.headerProgressBar.style.width = `${pct}%`;
        }
    }

    // -------------------------------------------------------------
    // Submit Confirmation Modal Logic
    // -------------------------------------------------------------
    function openSubmitConfirmModal() {
        const total = state.questionsData.length;
        const answered = Object.keys(state.selectedObjectiveAnswers).length;
        const flaggedCount = Object.keys(state.flaggedQuestions).length;

        if (dom.dialogAnsweredCount) dom.dialogAnsweredCount.textContent = `${answered} / ${total}`;
        if (dom.dialogFlaggedCount) dom.dialogFlaggedCount.textContent = `${flaggedCount}`;
        if (dom.dialogTimeRemaining) dom.dialogTimeRemaining.textContent = formatTime(state.timeRemainingSec);

        if (dom.submitConfirmModalOverlay) {
            dom.submitConfirmModalOverlay.style.display = "flex";
        }
    }

    function closeSubmitConfirmModal() {
        if (dom.submitConfirmModalOverlay) {
            dom.submitConfirmModalOverlay.style.display = "none";
        }
    }

    async function confirmAndSubmitExam() {
        closeSubmitConfirmModal();

        // Stop Countdown Timer
        if (state.timerIntervalId) clearInterval(state.timerIntervalId);

        try {
            if (dom.btnConfirmSubmit) {
                dom.btnConfirmSubmit.disabled = true;
            }

            const evalPayload = {
                session_id: state.sessionId,
                objective_submissions: Object.entries(state.selectedObjectiveAnswers).map(([qid, opt]) => ({
                    question_id: qid,
                    selected_option_id: opt,
                })),
                scenario_submissions: state.selectedScenarioChoices,
            };

            const res = await fetch(`${API_BASE}/evaluate`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(evalPayload),
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            state.isExamSubmitted = true;
            state.latestEvaluation = data;

            // Reveal Review Banner
            if (dom.examReviewBanner) {
                dom.examReviewBanner.style.display = "flex";
            }
            if (dom.reviewBannerTitle) {
                dom.reviewBannerTitle.textContent = `Examination Completed \u2022 Readiness Score: ${Math.round(data.overall_readiness_score)}%`;
            }

            // Update Tab Badge
            if (dom.readinessTabBadge) {
                dom.readinessTabBadge.textContent = `${Math.round(data.overall_readiness_score)}% Score`;
            }

            // Re-render Cockpit in Review Mode
            renderItemMatrix();
            renderActiveQuestion();

            // Render Dashboard
            renderDashboard();

            showToast("Examination evaluated. Entering review mode with grounded citations.", "success");
        } catch (err) {
            console.error("Exam submission failed:", err);
            showToast("Failed to submit examination to evaluation engine.", "error");
        } finally {
            if (dom.btnConfirmSubmit) dom.btnConfirmSubmit.disabled = false;
        }
    }

    // -------------------------------------------------------------
    // Tab 2: Outbreak Simulation Rendering & Logic
    // -------------------------------------------------------------
    function renderScenarioBriefing() {
        if (!state.scenariosData || state.scenariosData.length === 0) return;
        const scen = state.scenariosData[0];

        if (dom.scenarioTitle) dom.scenarioTitle.textContent = scen.title;
        if (dom.scenarioSettingText) dom.scenarioSettingText.textContent = scen.setting;
        if (dom.scenarioBackground) dom.scenarioBackground.textContent = scen.background;

        // Render Stage 1
        const stage1 = scen.stages.find(s => s.stage_id === 1);
        if (stage1) {
            if (dom.stage1Prompt) dom.stage1Prompt.textContent = stage1.prompt;
            renderStageChoices(1, stage1.choices);
        }

        // Setup Stage 2 placeholder
        const stage2 = scen.stages.find(s => s.stage_id === 2);
        if (stage2) {
            if (dom.stage2Prompt) dom.stage2Prompt.textContent = stage2.prompt;
            renderStageChoices(2, stage2.choices);
        }
    }

    function renderStageChoices(stageNum, choices) {
        const container = stageNum === 1 ? dom.stage1Choices : dom.stage2Choices;
        if (!container) return;
        container.innerHTML = "";

        choices.forEach(choice => {
            const item = document.createElement("div");
            item.className = "stage-choice-item";
            item.setAttribute("data-stage", stageNum);
            item.setAttribute("data-choice-id", choice.id);

            item.innerHTML = `
                <div class="choice-bullet"></div>
                <div class="choice-text">${choice.text}</div>
            `;

            item.addEventListener("click", () => {
                selectScenarioChoice(stageNum, choice.id);
            });

            container.appendChild(item);
        });
    }

    function selectScenarioChoice(stageNum, choiceId) {
        const scenId = state.scenariosData[0].id;
        const container = stageNum === 1 ? dom.stage1Choices : dom.stage2Choices;
        if (!container) return;

        // Update UI selection
        const items = container.querySelectorAll(".stage-choice-item");
        items.forEach(el => {
            el.classList.toggle("selected", el.getAttribute("data-choice-id") === choiceId);
        });

        // Record selection in state
        const existingIdx = state.selectedScenarioChoices.findIndex(
            s => s.scenario_id === scenId && s.stage_id === stageNum
        );
        const entry = { scenario_id: scenId, stage_id: stageNum, selected_choice_id: choiceId };

        if (existingIdx >= 0) {
            state.selectedScenarioChoices[existingIdx] = entry;
        } else {
            state.selectedScenarioChoices.push(entry);
        }

        // Enable action button
        if (stageNum === 1 && dom.btnCommitStage1) {
            dom.btnCommitStage1.disabled = false;
        } else if (stageNum === 2 && dom.btnCommitStage2) {
            dom.btnCommitStage2.disabled = false;
        }
    }

    async function handleScenarioStageCommit(stageNum) {
        const scenId = state.scenariosData[0].id;
        const choiceEntry = state.selectedScenarioChoices.find(s => s.scenario_id === scenId && s.stage_id === stageNum);
        if (!choiceEntry) return;

        try {
            const btn = stageNum === 1 ? dom.btnCommitStage1 : dom.btnCommitStage2;
            btn.disabled = true;
            btn.querySelector(".btn-text").textContent = "Analyzing Directive...";

            const evalPayload = {
                session_id: state.sessionId,
                objective_submissions: Object.entries(state.selectedObjectiveAnswers).map(([qid, opt]) => ({
                    question_id: qid,
                    selected_option_id: opt,
                })),
                scenario_submissions: state.selectedScenarioChoices,
            };

            const res = await fetch(`${API_BASE}/evaluate`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(evalPayload),
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            state.latestEvaluation = data;

            // Find current stage result
            const stgResult = data.scenario_results.find(r => r.stage_id === stageNum);

            if (stageNum === 1) {
                // Render Stage 1 Feedback
                dom.stage1Feedback.style.display = "flex";
                const isPos = (stgResult ? stgResult.score_delta : 0) > 0;
                dom.stage1DeltaBadge.className = `score-delta-badge ${isPos ? "positive" : "negative"}`;
                dom.stage1DeltaBadge.textContent = `${isPos ? "+" : ""}${stgResult ? stgResult.score_delta : 0} pts`;
                dom.stage1FeedbackText.textContent = stgResult ? stgResult.feedback : "Directive evaluated.";

                dom.stage1StatusTag.className = "stage-status-tag completed";
                dom.stage1StatusTag.textContent = "Completed";

                // Unlock Stage 2
                dom.stageCard2.classList.remove("locked");
                dom.stage2StatusTag.className = "stage-status-tag active";
                dom.stage2StatusTag.textContent = "In Progress";
                dom.stage2Actions.style.display = "flex";

                if (dom.simulationStageBadge) {
                    dom.simulationStageBadge.textContent = "Stage 2 Active";
                }

                showToast("Stage 1 Directive evaluated. Stage 2 unlocked.", "success");
                setTimeout(() => {
                    dom.stageCard2.scrollIntoView({ behavior: "smooth" });
                }, 150);
            } else if (stageNum === 2) {
                // Render Stage 2 Feedback
                dom.stage2Feedback.style.display = "flex";
                const isPos = (stgResult ? stgResult.score_delta : 0) > 0;
                dom.stage2DeltaBadge.className = `score-delta-badge ${isPos ? "positive" : "negative"}`;
                dom.stage2DeltaBadge.textContent = `${isPos ? "+" : ""}${stgResult ? stgResult.score_delta : 0} pts`;
                dom.stage2FeedbackText.textContent = stgResult ? stgResult.feedback : "Final directive evaluated.";

                dom.stage2StatusTag.className = "stage-status-tag completed";
                dom.stage2StatusTag.textContent = "Completed";

                // Show Completion Banner
                dom.scenarioCompleteBanner.style.display = "flex";
                if (dom.simulationStageBadge) {
                    dom.simulationStageBadge.textContent = "Resolved (100%)";
                    dom.simulationStageBadge.className = "tab-badge readiness-badge";
                }

                showToast("Outbreak simulation successfully completed!", "success");
                setTimeout(() => {
                    dom.scenarioCompleteBanner.scrollIntoView({ behavior: "smooth" });
                }, 150);
            }

            // Update readiness tab badge
            if (dom.readinessTabBadge) {
                dom.readinessTabBadge.textContent = `${Math.round(data.overall_readiness_score)}% Score`;
            }
        } catch (err) {
            console.error("Scenario commit failed:", err);
            showToast("Failed to process scenario decision.", "error");
        }
    }

    // -------------------------------------------------------------
    // Tab 3: Performance & Readiness Dashboard Rendering
    // -------------------------------------------------------------
    function renderInitialDashboardCompetencies() {
        if (!dom.competencyBarsContainer) return;
        dom.competencyBarsContainer.innerHTML = "";

        state.competencies.forEach(comp => {
            const card = document.createElement("div");
            card.className = "comp-bar-card";
            card.id = `comp-bar-${comp.id}`;
            card.title = `Click to review textbook remediation for ${comp.name}`;

            card.innerHTML = `
                <div class="comp-bar-header">
                    <span class="comp-name">${comp.name}</span>
                    <span class="comp-ratio" id="comp-ratio-${comp.id}">0 / 0</span>
                </div>
                <div class="progress-track">
                    <div class="progress-fill" id="comp-fill-${comp.id}" style="width: 0%;"></div>
                </div>
                <div class="comp-pct-row">
                    <span class="comp-status-text" id="comp-status-${comp.id}">Not Attempted</span>
                    <span class="comp-pct-val" id="comp-val-${comp.id}">0.0%</span>
                </div>
            `;

            card.addEventListener("click", () => openRemediationDrawer(comp.id));
            dom.competencyBarsContainer.appendChild(card);
        });
    }

    function renderDashboard() {
        if (!state.latestEvaluation) {
            animateRadialScore(0);
            if (dom.dashReadinessScore) dom.dashReadinessScore.textContent = "--";
            if (dom.dashReadinessLabel) dom.dashReadinessLabel.textContent = "Not Evaluated";
            if (dom.dashObjectiveScore) dom.dashObjectiveScore.textContent = "--%";
            if (dom.dashScenarioScore) dom.dashScenarioScore.textContent = "--%";
            return;
        }

        const data = state.latestEvaluation;

        // 1. Overall Readiness Radial Gauge
        const score = data.overall_readiness_score;
        animateRadialScore(score);

        if (dom.dashReadinessScore) {
            dom.dashReadinessScore.textContent = Math.round(score);
        }

        if (dom.dashReadinessLabel) {
            if (score >= 80) {
                dom.dashReadinessLabel.textContent = "Board Exam Ready";
                dom.dashReadinessLabel.style.color = "var(--success)";
            } else if (score >= 60) {
                dom.dashReadinessLabel.textContent = "Competent / Review Recommended";
                dom.dashReadinessLabel.style.color = "var(--warning)";
            } else {
                dom.dashReadinessLabel.textContent = "Remediation Required";
                dom.dashReadinessLabel.style.color = "var(--danger)";
            }
        }

        if (dom.dashObjectiveScore) {
            dom.dashObjectiveScore.textContent = `${data.objective_score_percentage.toFixed(1)}%`;
        }

        if (dom.dashScenarioScore) {
            dom.dashScenarioScore.textContent = `${data.scenario_score_percentage.toFixed(1)}%`;
        }

        // 2. Competency Progress Bars
        data.competency_breakdown.forEach(item => {
            const ratioEl = document.getElementById(`comp-ratio-${item.competency_id}`);
            const fillEl = document.getElementById(`comp-fill-${item.competency_id}`);
            const statusEl = document.getElementById(`comp-status-${item.competency_id}`);
            const valEl = document.getElementById(`comp-val-${item.competency_id}`);

            if (ratioEl) ratioEl.textContent = `${item.correct_questions} / ${item.total_questions}`;
            if (fillEl) {
                fillEl.style.width = `${item.accuracy_percentage}%`;
                fillEl.className = `progress-fill ${item.accuracy_percentage < 60 && item.total_questions > 0 ? "warning" : ""}`;
            }
            if (valEl) valEl.textContent = `${item.accuracy_percentage.toFixed(1)}%`;
            if (statusEl) {
                if (item.total_questions === 0) {
                    statusEl.textContent = "Not Attempted";
                    statusEl.style.color = "var(--text-dim)";
                } else if (item.accuracy_percentage >= 80) {
                    statusEl.textContent = "Proficient";
                    statusEl.style.color = "var(--success)";
                } else if (item.accuracy_percentage >= 60) {
                    statusEl.textContent = "Passing";
                    statusEl.style.color = "var(--accent-cyan)";
                } else {
                    statusEl.textContent = "Needs Remediation (Click to Review)";
                    statusEl.style.color = "var(--danger)";
                }
            }
        });

        // 3. Weak Areas Card
        if (dom.weakAreasContent) {
            if (!data.weak_areas || data.weak_areas.length === 0) {
                dom.weakAreasContent.innerHTML = `
                    <div class="empty-state">
                        <p style="color: var(--success); font-weight: 700;">No Critical Weak Areas Detected</p>
                        <p style="font-size: 12.5px;">All attempted competency domains achieved scores at or above the 60% standard proficiency threshold.</p>
                    </div>
                `;
            } else {
                let weakHtml = '<div class="weak-area-pill-list">';
                data.weak_areas.forEach(area => {
                    const match = area.match(/\(([^)]+)\)/);
                    const pillarId = match ? match[1] : area.toLowerCase();

                    weakHtml += `
                        <div class="weak-area-item" data-pillar="${pillarId}" title="Click to open local textbook remediation">
                            <div class="weak-area-info">
                                <span class="weak-area-name">${area}</span>
                                <span class="weak-area-directive">Click to review grounded textbook reference and formulas in slide-over drawer.</span>
                            </div>
                            <span class="weak-area-badge">&lt; 60% Score &bull; Review</span>
                        </div>
                    `;
                });
                weakHtml += '</div>';
                dom.weakAreasContent.innerHTML = weakHtml;

                const weakItems = dom.weakAreasContent.querySelectorAll(".weak-area-item");
                weakItems.forEach(item => {
                    item.addEventListener("click", () => {
                        const pillarId = item.getAttribute("data-pillar");
                        openRemediationDrawer(pillarId);
                    });
                });
            }
        }
    }

    function animateRadialScore(score) {
        if (!dom.radialScoreBar) return;
        const circumference = 427.26;
        const clampedScore = Math.max(0, Math.min(100, score));
        const offset = circumference - (clampedScore / 100) * circumference;
        dom.radialScoreBar.style.strokeDashoffset = offset;

        if (clampedScore >= 80) {
            dom.radialScoreBar.style.stroke = "var(--success)";
        } else if (clampedScore >= 60) {
            dom.radialScoreBar.style.stroke = "var(--accent-cyan)";
        } else {
            dom.radialScoreBar.style.stroke = "var(--danger)";
        }
    }

    // -------------------------------------------------------------
    // Slide-Over Remediation Drawer Logic
    // -------------------------------------------------------------
    async function openRemediationDrawer(pillarId) {
        state.activeRemediationPillar = pillarId;

        const compObj = state.competencies.find(c => c.id === pillarId);
        const domainName = compObj ? compObj.name : pillarId.toUpperCase();

        if (dom.drawerDomainTitle) dom.drawerDomainTitle.textContent = `${domainName} Remediation`;
        if (dom.drawerPillarTag) dom.drawerPillarTag.textContent = pillarId.toUpperCase();
        if (dom.drawerDomainSubtitle) dom.drawerDomainSubtitle.textContent = `Authoritative textbook excerpts retrieved from local ChromaDB for ${domainName}.`;

        if (dom.drawerBody) {
            dom.drawerBody.innerHTML = `
                <div class="loading-state">
                    <div class="spinner"></div>
                    <p>Retrieving textbook passages from ChromaDB...</p>
                </div>
            `;
        }

        // Open Drawer UI
        if (dom.drawerOverlay) dom.drawerOverlay.style.display = "block";
        if (dom.remediationDrawer) {
            dom.remediationDrawer.classList.add("open");
            dom.remediationDrawer.setAttribute("aria-hidden", "false");
        }

        try {
            const res = await fetch(`${API_BASE}/remediation?pillar=${encodeURIComponent(pillarId)}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            if (!dom.drawerBody) return;

            if (!data.citations || data.citations.length === 0) {
                dom.drawerBody.innerHTML = `
                    <div class="empty-state">
                        <p>No specific passages found for this domain.</p>
                        <p style="font-size: 13px; color: var(--text-muted);">${data.context}</p>
                    </div>
                `;
                return;
            }

            let cardsHtml = "";
            data.citations.forEach((cit, idx) => {
                cardsHtml += `
                    <div class="remediation-chunk-card">
                        <div class="chunk-header">
                            <span class="chunk-source-tag">EXCERPT ${idx + 1} &bull; ${cit.title || cit.domain_name}</span>
                            <span class="chunk-score-pill">Match: ${Math.round((cit.score || 0.85) * 100)}%</span>
                        </div>
                        <div class="chunk-content">${cit.text}</div>
                        <div class="citation-callout">
                            <span class="citation-tag">Source Document</span>
                            <span class="citation-text">${cit.source || cit.file_name}</span>
                        </div>
                    </div>
                `;
            });

            dom.drawerBody.innerHTML = cardsHtml;
        } catch (err) {
            console.error("Failed to fetch remediation data:", err);
            if (dom.drawerBody) {
                dom.drawerBody.innerHTML = `
                    <div class="empty-state">
                        <p style="color: var(--danger);">Failed to load textbook remediation passages.</p>
                    </div>
                `;
            }
        }
    }

    function closeRemediationDrawer() {
        if (dom.remediationDrawer) {
            dom.remediationDrawer.classList.remove("open");
            dom.remediationDrawer.setAttribute("aria-hidden", "true");
        }
        if (dom.drawerOverlay) {
            dom.drawerOverlay.style.display = "none";
        }
    }

    // -------------------------------------------------------------
    // Official Accreditation & Transcript Export Logic
    // -------------------------------------------------------------
    async function handleExportTranscript() {
        if (!state.latestEvaluation) {
            showToast("Please complete and submit an assessment before exporting an official record.", "error");
            return;
        }

        try {
            if (dom.btnExportRecord) {
                dom.btnExportRecord.disabled = true;
                dom.btnExportRecord.querySelector(".btn-text").textContent = "Compiling Record...";
            }

            const evalData = state.latestEvaluation;

            const exportPayload = {
                session_id: state.sessionId,
                overall_score: evalData.overall_readiness_score,
                mcq_score: evalData.objective_score_percentage,
                scenario_score: evalData.scenario_score_percentage,
                competency_scores: Object.fromEntries(
                    evalData.competency_breakdown.map(b => [b.competency_id, {
                        name: b.name,
                        total: b.total_questions,
                        correct: b.correct_questions,
                        accuracy: b.accuracy_percentage,
                    }])
                ),
                remediation_areas: evalData.weak_areas.map(a => ({ name: a })),
            };

            const res = await fetch(`${API_BASE}/export-report`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(exportPayload),
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const reportData = await res.json();

            // Populate Candidate Details
            if (dom.transcriptCandidateName) dom.transcriptCandidateName.textContent = state.candidate.name;
            if (dom.transcriptCandidateId) dom.transcriptCandidateId.textContent = state.candidate.id;

            // Populate Modal Fields
            if (dom.transcriptSessionId) dom.transcriptSessionId.textContent = reportData.session_id;
            if (dom.transcriptCertId) dom.transcriptCertId.textContent = reportData.header.certificate_id;
            if (dom.transcriptIssuedAt) dom.transcriptIssuedAt.textContent = new Date(reportData.header.issued_at).toUTCString();
            if (dom.transcriptAuditHash) dom.transcriptAuditHash.textContent = reportData.header.audit_hash;
            if (dom.transcriptOverallScore) dom.transcriptOverallScore.textContent = Math.round(reportData.overall_score);
            if (dom.transcriptStatusBadge) dom.transcriptStatusBadge.textContent = reportData.status;
            if (dom.transcriptMcqScore) dom.transcriptMcqScore.textContent = `${reportData.mcq_score.toFixed(1)}%`;
            if (dom.transcriptScenarioScore) dom.transcriptScenarioScore.textContent = `${reportData.scenario_score.toFixed(1)}%`;

            // Populate 6-Pillar Table
            if (dom.transcriptTableBody) {
                dom.transcriptTableBody.innerHTML = "";
                evalData.competency_breakdown.forEach(b => {
                    const row = document.createElement("tr");
                    const isPass = b.accuracy_percentage >= 60 || b.total_questions === 0;
                    row.innerHTML = `
                        <td><strong>${b.name}</strong></td>
                        <td><code>${b.competency_id}</code></td>
                        <td>${b.total_questions}</td>
                        <td>${b.correct_questions}</td>
                        <td><strong>${b.accuracy_percentage.toFixed(1)}%</strong></td>
                        <td>
                            <span class="status-chip ${isPass ? 'pass' : 'review'}">
                                ${b.total_questions === 0 ? 'NOT ATTEMPTED' : (isPass ? 'COMPETENT (PASS)' : 'REQUIRES REMEDIATION')}
                            </span>
                        </td>
                    `;
                    dom.transcriptTableBody.appendChild(row);
                });
            }

            // Populate Scenario Summary Log
            if (dom.transcriptScenarioLog) {
                if (!evalData.scenario_results || evalData.scenario_results.length === 0) {
                    dom.transcriptScenarioLog.innerHTML = "<p><em>No outbreak incident simulation stages were recorded for this session.</em></p>";
                } else {
                    let scenLogHtml = `
                        <div class="scenario-summary-title">Incident Simulation: Metropolitan Foodborne Salmonellosis Outbreak</div>
                    `;
                    evalData.scenario_results.forEach(sr => {
                        const isPos = sr.score_delta > 0;
                        scenLogHtml += `
                            <div class="scenario-step-entry">
                                <span><strong>Stage ${sr.stage_id} Decision:</strong> ${sr.feedback}</span>
                                <span style="font-family: var(--font-mono); font-weight: 700; color: ${isPos ? 'var(--success)' : 'var(--danger)'};">
                                    ${isPos ? '+' : ''}${sr.score_delta} pts
                                </span>
                            </div>
                        `;
                    });
                    dom.transcriptScenarioLog.innerHTML = scenLogHtml;
                }
            }

            // Populate Remediation Section
            if (dom.transcriptRemediationList) {
                if (!evalData.weak_areas || evalData.weak_areas.length === 0) {
                    dom.transcriptRemediationList.innerHTML = `
                        <div class="doc-remediation-item" style="border-left-color: var(--success);">
                            <span class="doc-remediation-domain" style="color: var(--success);">All Tested Competencies Met Accreditation Standards</span>
                            <span class="doc-remediation-text">The candidate achieved 60% or greater across all active domains. No mandatory curriculum remediation required.</span>
                        </div>
                    `;
                } else {
                    dom.transcriptRemediationList.innerHTML = `
                        <div class="loading-state" style="padding: 10px;">
                            <div class="spinner"></div>
                            <p style="font-size: 12px;">Fetching grounded citations for remediation areas...</p>
                        </div>
                    `;

                    const remediationPromises = evalData.weak_areas.map(async (area) => {
                        const match = area.match(/\(([^)]+)\)/);
                        const pId = match ? match[1] : area.toLowerCase();
                        try {
                            const remRes = await fetch(`${API_BASE}/remediation?pillar=${encodeURIComponent(pId)}`);
                            if (remRes.ok) {
                                const remData = await remRes.json();
                                return { area, data: remData };
                            }
                        } catch (e) {
                            console.error("Remediation fetch error:", e);
                        }
                        return { area, data: null };
                    });

                    const results = await Promise.all(remediationPromises);
                    let remHtml = "";
                    results.forEach(({ area, data }) => {
                        const citText = data && data.citations && data.citations.length > 0
                            ? data.citations[0].text
                            : "Standard curriculum guidelines must be reviewed.";
                        const sourceDoc = data && data.citations && data.citations.length > 0
                            ? data.citations[0].source
                            : "Public Health Core Reference Manual";

                        remHtml += `
                            <div class="doc-remediation-item">
                                <span class="doc-remediation-domain">${area} &bull; Required Study Topic</span>
                                <p class="doc-remediation-text">${citText}</p>
                                <span class="doc-remediation-cit">Source Citation: ${sourceDoc}</span>
                            </div>
                        `;
                    });
                    dom.transcriptRemediationList.innerHTML = remHtml;
                }
            }

            // Open Modal
            if (dom.transcriptModalOverlay) {
                dom.transcriptModalOverlay.style.display = "flex";
            }

            showToast("Official transcript generated and cryptographically signed.", "success");
        } catch (err) {
            console.error("Failed to export official record:", err);
            showToast("Failed to generate official assessment record.", "error");
        } finally {
            if (dom.btnExportRecord) {
                dom.btnExportRecord.disabled = false;
                dom.btnExportRecord.querySelector(".btn-text").textContent = "Export Official Assessment Record";
            }
        }
    }

    function closeTranscriptModal() {
        if (dom.transcriptModalOverlay) {
            dom.transcriptModalOverlay.style.display = "none";
        }
    }

    // -------------------------------------------------------------
    // Administrative Curriculum & Question Bank Management
    // -------------------------------------------------------------
    let selectedCurriculumFile = null;
    let selectedQuestionsFile = null;
    let selectedPanelCurriculumFile = null;
    let selectedPanelQuestionsFile = null;

    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return "0 Bytes";
        const k = 1024;
        const sizes = ["Bytes", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
    }

    function openAdminModal() {
        if (dom.adminManageModal) {
            dom.adminManageModal.style.display = "flex";
        }
    }

    function closeAdminModal() {
        if (dom.adminManageModal) {
            dom.adminManageModal.style.display = "none";
        }
    }

    function handleCurriculumFileSelect(file, isPanel = false) {
        if (!file) return;
        if (isPanel) {
            selectedPanelCurriculumFile = file;
            if (dom.panelCurriculumFilename) dom.panelCurriculumFilename.textContent = file.name;
            if (dom.panelCurriculumFilesize) dom.panelCurriculumFilesize.textContent = formatBytes(file.size);
            if (dom.panelCurriculumSelectedFile) dom.panelCurriculumSelectedFile.style.display = "flex";
            const content = dom.panelCurriculumDropzone ? dom.panelCurriculumDropzone.querySelector(".dropzone-content") : null;
            if (content) content.style.display = "none";
            if (dom.btnPanelUploadCurriculum) dom.btnPanelUploadCurriculum.disabled = false;
        } else {
            selectedCurriculumFile = file;
            if (dom.curriculumFilename) dom.curriculumFilename.textContent = file.name;
            if (dom.curriculumFilesize) dom.curriculumFilesize.textContent = formatBytes(file.size);
            if (dom.curriculumSelectedFile) dom.curriculumSelectedFile.style.display = "flex";
            const content = dom.curriculumDropzone ? dom.curriculumDropzone.querySelector(".dropzone-content") : null;
            if (content) content.style.display = "none";
            if (dom.btnUploadCurriculum) dom.btnUploadCurriculum.disabled = false;
        }
    }

    function clearCurriculumFile(e, isPanel = false) {
        if (e) e.stopPropagation();
        if (isPanel) {
            selectedPanelCurriculumFile = null;
            if (dom.panelInputCurriculumFile) dom.panelInputCurriculumFile.value = "";
            if (dom.panelCurriculumSelectedFile) dom.panelCurriculumSelectedFile.style.display = "none";
            const content = dom.panelCurriculumDropzone ? dom.panelCurriculumDropzone.querySelector(".dropzone-content") : null;
            if (content) content.style.display = "flex";
            if (dom.btnPanelUploadCurriculum) dom.btnPanelUploadCurriculum.disabled = true;
            if (dom.panelCurriculumUploadStatus) dom.panelCurriculumUploadStatus.style.display = "none";
        } else {
            selectedCurriculumFile = null;
            if (dom.inputCurriculumFile) dom.inputCurriculumFile.value = "";
            if (dom.curriculumSelectedFile) dom.curriculumSelectedFile.style.display = "none";
            const content = dom.curriculumDropzone ? dom.curriculumDropzone.querySelector(".dropzone-content") : null;
            if (content) content.style.display = "flex";
            if (dom.btnUploadCurriculum) dom.btnUploadCurriculum.disabled = true;
            if (dom.curriculumUploadStatus) dom.curriculumUploadStatus.style.display = "none";
        }
    }

    function handleQuestionsFileSelect(file, isPanel = false) {
        if (!file) return;
        if (isPanel) {
            selectedPanelQuestionsFile = file;
            if (dom.panelQuestionsFilename) dom.panelQuestionsFilename.textContent = file.name;
            if (dom.panelQuestionsFilesize) dom.panelQuestionsFilesize.textContent = formatBytes(file.size);
            if (dom.panelQuestionsSelectedFile) dom.panelQuestionsSelectedFile.style.display = "flex";
            const content = dom.panelQuestionsDropzone ? dom.panelQuestionsDropzone.querySelector(".dropzone-content") : null;
            if (content) content.style.display = "none";
            if (dom.btnPanelUploadQuestions) dom.btnPanelUploadQuestions.disabled = false;
        } else {
            selectedQuestionsFile = file;
            if (dom.questionsFilename) dom.questionsFilename.textContent = file.name;
            if (dom.questionsFilesize) dom.questionsFilesize.textContent = formatBytes(file.size);
            if (dom.questionsSelectedFile) dom.questionsSelectedFile.style.display = "flex";
            const content = dom.questionsDropzone ? dom.questionsDropzone.querySelector(".dropzone-content") : null;
            if (content) content.style.display = "none";
            if (dom.btnUploadQuestions) dom.btnUploadQuestions.disabled = false;
        }
    }

    function clearQuestionsFile(e, isPanel = false) {
        if (e) e.stopPropagation();
        if (isPanel) {
            selectedPanelQuestionsFile = null;
            if (dom.panelInputQuestionsFile) dom.panelInputQuestionsFile.value = "";
            if (dom.panelQuestionsSelectedFile) dom.panelQuestionsSelectedFile.style.display = "none";
            const content = dom.panelQuestionsDropzone ? dom.panelQuestionsDropzone.querySelector(".dropzone-content") : null;
            if (content) content.style.display = "flex";
            if (dom.btnPanelUploadQuestions) dom.btnPanelUploadQuestions.disabled = true;
            if (dom.panelQuestionsUploadStatus) dom.panelQuestionsUploadStatus.style.display = "none";
        } else {
            selectedQuestionsFile = null;
            if (dom.inputQuestionsFile) dom.inputQuestionsFile.value = "";
            if (dom.questionsSelectedFile) dom.questionsSelectedFile.style.display = "none";
            const content = dom.questionsDropzone ? dom.questionsDropzone.querySelector(".dropzone-content") : null;
            if (content) content.style.display = "flex";
            if (dom.btnUploadQuestions) dom.btnUploadQuestions.disabled = true;
            if (dom.questionsUploadStatus) dom.questionsUploadStatus.style.display = "none";
        }
    }

    async function uploadCurriculumFile(isPanel = false) {
        const fileToUpload = isPanel ? selectedPanelCurriculumFile : selectedCurriculumFile;
        if (!fileToUpload) return;

        const btnUpload = isPanel ? dom.btnPanelUploadCurriculum : dom.btnUploadCurriculum;
        const btnUploadText = isPanel ? dom.btnPanelUploadCurriculumText : dom.btnUploadCurriculumText;
        const uploadStatus = isPanel ? dom.panelCurriculumUploadStatus : dom.curriculumUploadStatus;
        const statusText = isPanel ? dom.panelCurriculumStatusText : dom.curriculumStatusText;

        try {
            if (btnUpload) btnUpload.disabled = true;
            if (btnUploadText) btnUploadText.textContent = "Indexing...";
            if (uploadStatus) uploadStatus.style.display = "flex";
            if (statusText) statusText.textContent = `Parsing & embedding '${fileToUpload.name}' into ChromaDB...`;

            const formData = new FormData();
            formData.append("file", fileToUpload);

            const res = await fetch(`${API_BASE}/admin/upload-curriculum`, {
                method: "POST",
                body: formData,
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || `Upload failed with HTTP ${res.status}`);
            }

            const data = await res.json();
            showToast(`Curriculum indexed: ${data.filename} (${data.total_chunks} passages)`, "success");

            // Refresh health status pill & admin telemetry
            await checkSystemHealth();
            await renderAdminTelemetry();

            // Reset upload UI
            clearCurriculumFile(null, isPanel);
            if (uploadStatus) uploadStatus.style.display = "none";
        } catch (err) {
            console.error("Curriculum upload failed:", err);
            showToast(`Ingestion error: ${err.message}`, "error");
            if (statusText) statusText.textContent = `Error: ${err.message}`;
        } finally {
            if (btnUpload) btnUpload.disabled = !(isPanel ? selectedPanelCurriculumFile : selectedCurriculumFile);
            if (btnUploadText) btnUploadText.textContent = "Index into Knowledge Base";
        }
    }

    async function uploadQuestionsFile(isPanel = false) {
        const fileToUpload = isPanel ? selectedPanelQuestionsFile : selectedQuestionsFile;
        if (!fileToUpload) return;

        const btnUpload = isPanel ? dom.btnPanelUploadQuestions : dom.btnUploadQuestions;
        const btnUploadText = isPanel ? dom.btnPanelUploadQuestionsText : dom.btnUploadQuestionsText;
        const uploadStatus = isPanel ? dom.panelQuestionsUploadStatus : dom.questionsUploadStatus;
        const statusText = isPanel ? dom.panelQuestionsStatusText : dom.questionsStatusText;

        try {
            if (btnUpload) btnUpload.disabled = true;
            if (btnUploadText) btnUploadText.textContent = "Validating...";
            if (uploadStatus) uploadStatus.style.display = "flex";
            if (statusText) statusText.textContent = `Validating question bank schema and reloading...`;

            const formData = new FormData();
            formData.append("file", fileToUpload);

            const res = await fetch(`${API_BASE}/admin/upload-questions`, {
                method: "POST",
                body: formData,
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || `Import failed with HTTP ${res.status}`);
            }

            const data = await res.json();
            showToast(`Question bank reloaded: ${data.new_question_count} MCQs, ${data.total_scenarios || 1} scenarios`, "success");

            // Hot-reload application questions, telemetry, and system stats
            await checkSystemHealth();
            await renderAdminTelemetry();
            await fetchCompetencies();
            await fetchQuestions();
            await fetchScenarios();

            // Reset upload UI
            clearQuestionsFile(null, isPanel);
            if (uploadStatus) uploadStatus.style.display = "none";
        } catch (err) {
            console.error("Questions bank upload failed:", err);
            showToast(`Import error: ${err.message}`, "error");
            if (statusText) statusText.textContent = `Error: ${err.message}`;
        } finally {
            if (btnUpload) btnUpload.disabled = !(isPanel ? selectedPanelQuestionsFile : selectedQuestionsFile);
            if (btnUploadText) btnUploadText.textContent = "Import & Validate Bank";
        }
    }

    // -------------------------------------------------------------
    // Session Reset
    // -------------------------------------------------------------
    function resetSession() {
        state.sessionId = generateUUID();
        state.isExamLaunched = false;
        state.isExamSubmitted = false;
        state.activeQuestionIndex = 0;
        state.flaggedQuestions = {};
        state.timeRemainingSec = EXAM_DURATION_SECONDS;
        if (state.timerIntervalId) clearInterval(state.timerIntervalId);

        state.selectedObjectiveAnswers = {};
        state.selectedScenarioChoices = [];
        state.scenarioStageFeedback = {};
        state.latestEvaluation = null;

        if (dom.sessionIdDisplay) {
            dom.sessionIdDisplay.textContent = state.sessionId;
            dom.sessionIdDisplay.title = state.sessionId;
        }

        if (dom.sessionTimerDisplay) {
            dom.sessionTimerDisplay.textContent = "Time Remaining: Paused \u2022 15:00";
            dom.sessionTimerDisplay.style.color = "var(--text-primary)";
        }

        // Return to Briefing Gate
        if (dom.candidateBriefingGate) dom.candidateBriefingGate.style.display = "block";
        if (dom.examCockpitContainer) dom.examCockpitContainer.style.display = "none";
        if (dom.examReviewBanner) dom.examReviewBanner.style.display = "none";

        // Reset Dock and Sidebar Controls
        if (dom.btnSidebarFinishExam) dom.btnSidebarFinishExam.style.display = "block";
        if (dom.btnFlagDock) dom.btnFlagDock.style.display = "inline-flex";
        if (dom.btnFlagItem) dom.btnFlagItem.style.display = "inline-flex";
        if (dom.btnViewDashboard) dom.btnViewDashboard.style.display = "none";
        if (dom.stageReviewPositionBadge) dom.stageReviewPositionBadge.style.display = "none";
        if (dom.stageKeyboardHint) dom.stageKeyboardHint.style.display = "block";

        // Reset Stage 1 & 2 in Simulation
        if (dom.stage1Feedback) dom.stage1Feedback.style.display = "none";
        if (dom.stage1StatusTag) {
            dom.stage1StatusTag.className = "stage-status-tag active";
            dom.stage1StatusTag.textContent = "In Progress";
        }
        if (dom.btnCommitStage1) dom.btnCommitStage1.disabled = true;

        if (dom.stageCard2) dom.stageCard2.classList.add("locked");
        if (dom.stage2StatusTag) {
            dom.stage2StatusTag.className = "stage-status-tag";
            dom.stage2StatusTag.textContent = "Locked";
        }
        if (dom.stage2Actions) dom.stage2Actions.style.display = "none";
        if (dom.stage2Feedback) dom.stage2Feedback.style.display = "none";
        if (dom.btnCommitStage2) dom.btnCommitStage2.disabled = true;

        if (dom.scenarioCompleteBanner) dom.scenarioCompleteBanner.style.display = "none";
        if (dom.simulationStageBadge) {
            dom.simulationStageBadge.textContent = "Active";
            dom.simulationStageBadge.className = "tab-badge alert-badge";
        }

        if (dom.readinessTabBadge) dom.readinessTabBadge.textContent = "0% Score";

        updateExamTelemetry();
        renderScenarioBriefing();
        renderInitialDashboardCompetencies();
        renderDashboard();

        showToast("New evaluation session initialized.", "info");
        switchTab("practice");
    }

    // Initialize on DOM Ready
    document.addEventListener("DOMContentLoaded", init);
})();
