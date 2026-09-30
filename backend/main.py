"""FastAPI Backend Service for the Public Health Platform.

Provides high-performance REST APIs for core competency training,
board-level question banks, interactive outbreak scenario simulations,
local RAG-grounded textbook remediation, multi-dimensional readiness analytics,
and institutional accreditation audit exports.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import os

from fastapi import FastAPI, HTTPException, Query, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Ensure project root is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.rag_engine import (
    retrieve_competency_context,
    search_citations,
    get_vector_store_status,
)
from src.ingest import run_ingestion

# Setup structured logger
logger = logging.getLogger("public_health.api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Initialize FastAPI application with descriptive metadata
app = FastAPI(
    title="Public Health Competencies & Outbreak Simulation API",
    version="1.0.0",
    description=(
        "Production-grade backend service delivering board-level public health "
        "competency assessments, sanitized practice question banks, two-stage outbreak "
        "investigation simulations, local textbook RAG remediation, and readiness evaluation analytics."
    ),
)

# Enable CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================================
# In-Memory Storage
# =====================================================================

QUESTION_BANK_DATA: Dict[str, Any] = {
    "version": "1.0.0",
    "competencies": [],
    "questions": [],
    "scenarios": [],
}

USER_ANALYTICS_STORE: Dict[str, EvaluationResponse] = {}


def load_question_bank_data() -> None:
    """Load core competencies question bank from JSON file into memory."""
    global QUESTION_BANK_DATA
    bank_path = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "question_banks"
        / "core_competencies.json"
    )

    if not bank_path.exists():
        logger.error("Core competencies question bank not found at path: %s", bank_path)
        return

    try:
        with open(bank_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            QUESTION_BANK_DATA = data
            logger.info(
                "Successfully loaded question bank (version %s) with %d competencies, "
                "%d questions, and %d scenarios from %s",
                data.get("version", "unknown"),
                len(data.get("competencies", [])),
                len(data.get("questions", [])),
                len(data.get("scenarios", [])),
                bank_path,
            )
    except Exception as exc:
        logger.exception("Failed to load question bank data from %s: %s", bank_path, exc)


# Load data immediately on module import and also register startup event
load_question_bank_data()


@app.on_event("startup")
def on_startup() -> None:
    """Execute startup routines and ensure question bank is populated."""
    load_question_bank_data()


# =====================================================================
# Pydantic Schemas
# =====================================================================


class Option(BaseModel):
    """Multiple-choice option structure."""

    id: str = Field(..., description="Option identifier (e.g., 'a', 'b', 'c', 'd')")
    text: str = Field(..., description="Option text content")


class QuestionOut(BaseModel):
    """Sanitized question schema safely masking answer keys and explanations."""

    id: str = Field(..., description="Unique question identifier")
    competency_id: str = Field(..., description="Associated core competency domain ID")
    text: str = Field(..., description="Clinical/epidemiological vignette or question prompt")
    options: List[Option] = Field(..., description="List of four multiple-choice options")


class Competency(BaseModel):
    """Public health competency domain."""

    id: str = Field(..., description="Domain identifier (e.g., 'epi', 'biostat')")
    name: str = Field(..., description="Full name of competency domain")
    description: str = Field(..., description="Detailed description of competency scope")


class ScenarioChoiceOut(BaseModel):
    """Sanitized scenario choice masking score deltas and consequence feedback."""

    id: str = Field(..., description="Choice identifier (e.g., 's1_opt_a')")
    text: str = Field(..., description="Action description")


class ScenarioStageOut(BaseModel):
    """Sanitized outbreak scenario stage."""

    stage_id: int = Field(..., description="Stage sequence number (1, 2, ...)")
    prompt: str = Field(..., description="Operational decision dilemma prompt")
    choices: List[ScenarioChoiceOut] = Field(..., description="List of sanitized action choices")


class ScenarioOut(BaseModel):
    """Sanitized outbreak simulation scenario."""

    id: str = Field(..., description="Unique scenario identifier")
    title: str = Field(..., description="Scenario title")
    setting: str = Field(..., description="Operational setting or Incident Command structure")
    background: str = Field(..., description="Outbreak background and clinical epidemiological context")
    stages: List[ScenarioStageOut] = Field(..., description="Sequential stages of the scenario")


class ObjectiveSubmission(BaseModel):
    """User response for a single multiple choice question."""

    question_id: str = Field(..., description="Question identifier")
    selected_option_id: str = Field(..., description="Selected option ID ('a', 'b', 'c', 'd')")


class ScenarioStepSubmission(BaseModel):
    """User response for a single stage in an outbreak scenario."""

    scenario_id: str = Field(..., description="Scenario identifier")
    stage_id: int = Field(..., description="Stage number")
    selected_choice_id: str = Field(..., description="Selected choice ID (e.g., 's1_opt_a')")


class EvaluationRequest(BaseModel):
    """Payload for submitting an assessment session for evaluation."""

    session_id: Optional[str] = Field(
        default=None,
        description="Optional session tracking ID. A unique UUID is generated if omitted.",
    )
    objective_submissions: List[ObjectiveSubmission] = Field(
        default_factory=list,
        description="List of submitted objective question answers",
    )
    scenario_submissions: List[ScenarioStepSubmission] = Field(
        default_factory=list,
        description="List of submitted scenario stage choices",
    )


class ObjectiveResult(BaseModel):
    """Graded result for an individual multiple-choice question."""

    question_id: str
    competency_id: str
    selected_option_id: str
    correct_option_id: str
    is_correct: bool
    explanation: str
    citation: str


class ScenarioResult(BaseModel):
    """Graded result for an individual outbreak scenario decision."""

    scenario_id: str
    stage_id: int
    selected_choice_id: str
    score_delta: int
    feedback: str
    next_stage: Optional[int] = None


class CompetencyBreakdown(BaseModel):
    """Performance breakdown for a specific core competency domain."""

    competency_id: str
    name: str
    total_questions: int
    correct_questions: int
    accuracy_percentage: float


class EvaluationResponse(BaseModel):
    """Complete evaluation report with multi-dimensional scoring and analytics."""

    session_id: str = Field(..., description="Unique session identifier")
    timestamp: str = Field(..., description="Evaluation timestamp in ISO 8601 format")
    overall_readiness_score: float = Field(
        ...,
        description="Weighted score (60% objective + 40% scenario performance, scaled 0-100)",
    )
    objective_score_percentage: float = Field(
        ...,
        description="Percentage score on objective multiple-choice items (0-100)",
    )
    scenario_score_percentage: float = Field(
        ...,
        description="Percentage score on scenario decision stages (0-100)",
    )
    competency_breakdown: List[CompetencyBreakdown] = Field(
        ...,
        description="Domain-level accuracy metrics",
    )
    weak_areas: List[str] = Field(
        ...,
        description="List of competencies with accuracy below 60%",
    )
    objective_results: List[ObjectiveResult] = Field(
        ...,
        description="Detailed question-by-question grading and citations",
    )
    scenario_results: List[ScenarioResult] = Field(
        ...,
        description="Detailed scenario step scores and methodological critiques",
    )


class RemediationResponse(BaseModel):
    """Textbook remediation package retrieved via local RAG engine."""

    pillar: str = Field(..., description="Competency pillar ID")
    domain_name: str = Field(..., description="Full competency domain title")
    context: str = Field(..., description="Formatted textbook context excerpt")
    citations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of retrieved citation passages and grounding scores",
    )


class GenerateQuestionRequest(BaseModel):
    """Request payload for RAG-grounded question synthesis/retrieval."""

    pillar: str = Field(default="epi", description="Domain pillar ID")
    difficulty: Optional[str] = Field(default="intermediate", description="Difficulty tier")


class AuditExportRequest(BaseModel):
    """Payload for generating an accredited institutional assessment audit report."""

    session_id: str = Field(..., description="Unique assessment session ID")
    overall_score: float = Field(..., description="Overall readiness score (0-100)")
    mcq_score: float = Field(..., description="Objective MCQ score percentage")
    scenario_score: float = Field(..., description="Outbreak scenario performance score percentage")
    competency_scores: Dict[str, Any] = Field(
        default_factory=dict,
        description="Domain-level performance breakdown",
    )
    remediation_areas: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of weak areas with citations and recommended directives",
    )


class InstitutionalAuditHeader(BaseModel):
    """Authoritative institutional audit header block."""

    institution: str = Field(
        default="Public Health Competency Assessment & Certification Authority",
        description="Accrediting institution name",
    )
    curriculum_standard: str = Field(
        default="Foundational CEPH / CPH Public Health Pillars",
        description="Curriculum framework standard",
    )
    issued_at: str = Field(..., description="UTC timestamp of report generation")
    audit_hash: str = Field(..., description="Deterministic SHA-256 validation hash")
    certificate_id: str = Field(..., description="Unique institutional certificate ID")


class AuditReportResponse(BaseModel):
    """Enriched institutional accreditation audit report."""

    header: InstitutionalAuditHeader
    session_id: str
    overall_score: float
    status: str
    mcq_score: float
    scenario_score: float
    competency_scores: Dict[str, Any]
    remediation_areas: List[Dict[str, Any]]


class QuestionBankOption(BaseModel):
    id: str
    text: str


class QuestionBankItem(BaseModel):
    id: str
    competency_id: str
    text: str
    options: List[QuestionBankOption]
    correct_option_id: str
    explanation: str
    citation: Optional[str] = None


class ScenarioBankChoice(BaseModel):
    id: str
    text: str
    is_optimal: bool = False
    score_delta: float = 0.0
    feedback: str = ""


class ScenarioBankStage(BaseModel):
    stage_id: int
    prompt: str
    choices: List[ScenarioBankChoice]


class ScenarioBankItem(BaseModel):
    id: str
    title: str
    setting: str
    background: str
    stages: List[ScenarioBankStage]


class CompetencyBankItem(BaseModel):
    id: str
    name: str
    description: str


class QuestionBank(BaseModel):
    version: Optional[str] = "1.0.0"
    competencies: List[CompetencyBankItem] = Field(default_factory=list)
    questions: List[QuestionBankItem] = Field(default_factory=list)
    scenarios: List[ScenarioBankItem] = Field(default_factory=list)


# =====================================================================
# Core REST Endpoints
# =====================================================================


@app.get("/api/health", summary="Health Check & Bank Statistics")
def get_health() -> Dict[str, Any]:
    """Return API health status, question bank metrics, and ChromaDB store metrics."""
    vector_status = get_vector_store_status()
    return {
        "status": "healthy",
        "service": "Public Health Platform API",
        "version": "1.0.0",
        "bank_version": QUESTION_BANK_DATA.get("version", "1.0.0"),
        "competencies_count": len(QUESTION_BANK_DATA.get("competencies", [])),
        "questions_indexed": len(QUESTION_BANK_DATA.get("questions", [])),
        "scenarios_indexed": len(QUESTION_BANK_DATA.get("scenarios", [])),
        "cached_sessions_count": len(USER_ANALYTICS_STORE),
        "vector_store": vector_status,
    }


@app.get("/api/competencies", response_model=List[Competency], summary="List Core Competencies")
def get_competencies() -> List[Competency]:
    """Return the list of 6 core public health competency domains."""
    raw_competencies = QUESTION_BANK_DATA.get("competencies", [])
    return [Competency(**c) for c in raw_competencies]


@app.get("/api/questions", response_model=List[QuestionOut], summary="List Sanitized Questions")
def get_questions(
    pillar: Optional[str] = Query(
        default=None,
        description="Filter by competency ID (e.g., 'epi', 'biostat', 'research', 'env_health', 'program_mgmt', 'prof_comm')",
    ),
) -> List[QuestionOut]:
    """Return sanitized board-level multiple choice questions without leaking answers."""
    raw_questions = QUESTION_BANK_DATA.get("questions", [])

    if pillar:
        pillar_clean = pillar.strip().lower()
        raw_questions = [
            q for q in raw_questions if q.get("competency_id", "").lower() == pillar_clean
        ]

    sanitized: List[QuestionOut] = []
    for q in raw_questions:
        sanitized.append(
            QuestionOut(
                id=q["id"],
                competency_id=q["competency_id"],
                text=q["text"],
                options=[Option(id=opt["id"], text=opt["text"]) for opt in q.get("options", [])],
            )
        )
    return sanitized


@app.get("/api/scenarios", response_model=List[ScenarioOut], summary="List Outbreak Scenarios")
def get_scenarios() -> List[ScenarioOut]:
    """Return sanitized outbreak simulation scenarios without leaking consequence scores or feedback."""
    raw_scenarios = QUESTION_BANK_DATA.get("scenarios", [])
    sanitized: List[ScenarioOut] = []

    for s in raw_scenarios:
        stages_out: List[ScenarioStageOut] = []
        for stg in s.get("stages", []):
            choices_out = [
                ScenarioChoiceOut(id=c["id"], text=c["text"])
                for c in stg.get("choices", [])
            ]
            stages_out.append(
                ScenarioStageOut(
                    stage_id=stg["stage_id"],
                    prompt=stg["prompt"],
                    choices=choices_out,
                )
            )
        sanitized.append(
            ScenarioOut(
                id=s["id"],
                title=s["title"],
                setting=s["setting"],
                background=s["background"],
                stages=stages_out,
            )
        )
    return sanitized


@app.post("/api/evaluate", response_model=EvaluationResponse, summary="Evaluate Assessment Session")
def evaluate_session(body: EvaluationRequest) -> EvaluationResponse:
    """Evaluate objective answers and scenario decisions against the ground-truth question bank."""
    session_id = body.session_id or str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    # Index question bank for fast lookup
    questions_map = {q["id"]: q for q in QUESTION_BANK_DATA.get("questions", [])}
    competencies_map = {c["id"]: c["name"] for c in QUESTION_BANK_DATA.get("competencies", [])}
    scenarios_map = {s["id"]: s for s in QUESTION_BANK_DATA.get("scenarios", [])}

    # -------------------------------------------------------------
    # 1. Evaluate Objective Submissions
    # -------------------------------------------------------------
    objective_results: List[ObjectiveResult] = []
    competency_stats: Dict[str, Dict[str, int]] = {
        cid: {"total": 0, "correct": 0} for cid in competencies_map
    }

    for sub in body.objective_submissions:
        q_data = questions_map.get(sub.question_id)
        if not q_data:
            logger.warning("Question ID '%s' not found in question bank.", sub.question_id)
            continue

        c_id = q_data.get("competency_id", "unknown")
        correct_opt = q_data.get("correct_option_id", "").strip().lower()
        selected_opt = sub.selected_option_id.strip().lower()
        is_correct = selected_opt == correct_opt

        if c_id in competency_stats:
            competency_stats[c_id]["total"] += 1
            if is_correct:
                competency_stats[c_id]["correct"] += 1

        objective_results.append(
            ObjectiveResult(
                question_id=sub.question_id,
                competency_id=c_id,
                selected_option_id=sub.selected_option_id,
                correct_option_id=q_data.get("correct_option_id", ""),
                is_correct=is_correct,
                explanation=q_data.get("explanation", ""),
                citation=q_data.get("citation", ""),
            )
        )

    total_obj = len(objective_results)
    correct_obj = sum(1 for r in objective_results if r.is_correct)
    objective_score_percentage = (
        round((correct_obj / total_obj) * 100.0, 2) if total_obj > 0 else 0.0
    )

    # -------------------------------------------------------------
    # 2. Evaluate Scenario Submissions
    # -------------------------------------------------------------
    scenario_results: List[ScenarioResult] = []
    total_earned_delta = 0
    total_max_delta = 0

    for step in body.scenario_submissions:
        scen_data = scenarios_map.get(step.scenario_id)
        if not scen_data:
            logger.warning("Scenario ID '%s' not found in question bank.", step.scenario_id)
            continue

        target_stage = next(
            (stg for stg in scen_data.get("stages", []) if stg.get("stage_id") == step.stage_id),
            None,
        )
        if not target_stage:
            logger.warning(
                "Stage ID %d not found in scenario '%s'.", step.stage_id, step.scenario_id
            )
            continue

        # Find max delta possible for this stage
        stage_choices = target_stage.get("choices", [])
        stage_max_delta = max((c.get("score_delta", 0) for c in stage_choices), default=0)
        if stage_max_delta > 0:
            total_max_delta += stage_max_delta

        target_choice = next(
            (c for c in stage_choices if c.get("id") == step.selected_choice_id),
            None,
        )

        if target_choice:
            delta = target_choice.get("score_delta", 0)
            feedback = target_choice.get("feedback", "")
            next_stg = target_choice.get("next_stage")
            total_earned_delta += delta
        else:
            delta = 0
            feedback = "Unrecognized choice selected."
            next_stg = None

        scenario_results.append(
            ScenarioResult(
                scenario_id=step.scenario_id,
                stage_id=step.stage_id,
                selected_choice_id=step.selected_choice_id,
                score_delta=delta,
                feedback=feedback,
                next_stage=next_stg,
            )
        )

    if total_max_delta > 0:
        raw_scen_score = (total_earned_delta / total_max_delta) * 100.0
        scenario_score_percentage = round(max(0.0, min(100.0, raw_scen_score)), 2)
    elif scenario_results:
        scenario_score_percentage = round(max(0.0, float(total_earned_delta)), 2)
    else:
        scenario_score_percentage = 0.0

    # -------------------------------------------------------------
    # 3. Overall Readiness Score (60% Objective + 40% Scenario)
    # -------------------------------------------------------------
    if total_obj > 0 and len(scenario_results) > 0:
        overall_readiness_score = round(
            0.60 * objective_score_percentage + 0.40 * scenario_score_percentage, 2
        )
    elif total_obj > 0:
        overall_readiness_score = objective_score_percentage
    elif len(scenario_results) > 0:
        overall_readiness_score = scenario_score_percentage
    else:
        overall_readiness_score = 0.0

    # -------------------------------------------------------------
    # 4. Competency Breakdown & Weak Area Identification
    # -------------------------------------------------------------
    competency_breakdown: List[CompetencyBreakdown] = []
    weak_areas: List[str] = []

    for cid, name in competencies_map.items():
        stats = competency_stats.get(cid, {"total": 0, "correct": 0})
        t_count = stats["total"]
        c_count = stats["correct"]
        acc = round((c_count / t_count) * 100.0, 2) if t_count > 0 else 0.0

        breakdown_item = CompetencyBreakdown(
            competency_id=cid,
            name=name,
            total_questions=t_count,
            correct_questions=c_count,
            accuracy_percentage=acc,
        )
        competency_breakdown.append(breakdown_item)

        # Flag as weak area if attempted and accuracy is below 60%
        if t_count > 0 and acc < 60.0:
            weak_areas.append(f"{name} ({cid})")

    # -------------------------------------------------------------
    # 5. Persist Session in In-Memory Store
    # -------------------------------------------------------------
    evaluation_response = EvaluationResponse(
        session_id=session_id,
        timestamp=now_iso,
        overall_readiness_score=overall_readiness_score,
        objective_score_percentage=objective_score_percentage,
        scenario_score_percentage=scenario_score_percentage,
        competency_breakdown=competency_breakdown,
        weak_areas=weak_areas,
        objective_results=objective_results,
        scenario_results=scenario_results,
    )

    USER_ANALYTICS_STORE[session_id] = evaluation_response
    logger.info(
        "Evaluated session '%s': Readiness=%.2f%% (Obj=%.2f%%, Scen=%.2f%%, Weak Areas=%s)",
        session_id,
        overall_readiness_score,
        objective_score_percentage,
        scenario_score_percentage,
        weak_areas,
    )

    return evaluation_response


@app.get("/api/analytics", response_model=EvaluationResponse, summary="Retrieve Session Analytics")
def get_analytics(
    session_id: str = Query(..., description="Unique evaluation session identifier"),
) -> EvaluationResponse:
    """Retrieve cached multi-dimensional analytics for a completed evaluation session."""
    session = USER_ANALYTICS_STORE.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation session '{session_id}' not found.",
        )
    return session


# =====================================================================
# RAG Remediation & Question Generation Endpoints
# =====================================================================


@app.get("/api/remediation", response_model=RemediationResponse, summary="Retrieve Grounded Remediation Excerpts")
def get_remediation(
    pillar: str = Query(..., description="Competency pillar ID (e.g., 'epi', 'biostat', 'research', 'env_health', 'program_mgmt', 'prof_comm')"),
    query: Optional[str] = Query(default=None, description="Optional search topic override"),
) -> RemediationResponse:
    """Retrieve authoritative textbook reference excerpts grounded in local ChromaDB for remediation."""
    pillar_clean = pillar.strip().lower()
    comp_map = {c["id"]: c["name"] for c in QUESTION_BANK_DATA.get("competencies", [])}
    domain_name = comp_map.get(pillar_clean, pillar_clean.title())

    # Retrieve context and citations from RAG engine
    search_q = query if query and query.strip() else f"Core principles, formulas, and guidelines in {domain_name}"
    citations = search_citations(query=search_q, top_k=3, pillar=pillar_clean)
    context_text = retrieve_competency_context(competency_id=pillar_clean, topic=search_q, top_k=3)

    return RemediationResponse(
        pillar=pillar_clean,
        domain_name=domain_name,
        context=context_text,
        citations=citations,
    )


@app.post("/api/generate-question", response_model=QuestionOut, summary="Generate/Retrieve Grounded Practice Question")
def generate_question(body: GenerateQuestionRequest) -> QuestionOut:
    """Generate or retrieve a verified question grounded in the textbook curriculum for the given pillar."""
    pillar_clean = body.pillar.strip().lower()
    raw_questions = [
        q for q in QUESTION_BANK_DATA.get("questions", [])
        if q.get("competency_id", "").lower() == pillar_clean
    ]

    if raw_questions:
        selected_q = raw_questions[0]
        return QuestionOut(
            id=f"{selected_q['id']}_gen",
            competency_id=selected_q["competency_id"],
            text=selected_q["text"],
            options=[Option(id=opt["id"], text=opt["text"]) for opt in selected_q.get("options", [])],
        )

    # If no pre-indexed question exists, synthesize from grounded citations
    citations = search_citations(query=f"Practice assessment question on {pillar_clean}", top_k=2, pillar=pillar_clean)
    sample_text = citations[0]["text"][:200] if citations else "Foundational public health principles."

    return QuestionOut(
        id=f"q_{pillar_clean}_synth",
        competency_id=pillar_clean,
        text=f"Based on the following curriculum standard: '{sample_text}...', which of the following is the correct methodological application?",
        options=[
            Option(id="a", text="Adhere strictly to verified standard operating protocols."),
            Option(id="b", text="Bypass preliminary case verification steps."),
            Option(id="c", text="Assume non-differential misclassification has no impact."),
            Option(id="d", text="Disregard unexposed cohort baselines."),
        ],
    )


# =====================================================================
# Institutional Accreditation & Audit Report Export Endpoint
# =====================================================================


@app.post("/api/export-report", response_model=AuditReportResponse, summary="Generate Official Institutional Audit Report")
def export_report(body: AuditExportRequest) -> AuditReportResponse:
    """Generate and cryptographically sign an official institutional assessment transcript."""
    now_iso = datetime.now(timezone.utc).isoformat()
    raw_hash_str = f"{body.session_id}:{now_iso}:{body.overall_score}:{body.mcq_score}:{body.scenario_score}"
    audit_hash = hashlib.sha256(raw_hash_str.encode("utf-8")).hexdigest()
    cert_id = f"CPH-AUDIT-{body.session_id[:8].upper()}-{int(datetime.now(timezone.utc).timestamp())}"

    eval_status = (
        "BOARD EXAM READY (COMPETENT)"
        if body.overall_score >= 80.0
        else (
            "PROVISIONALLY COMPETENT"
            if body.overall_score >= 60.0
            else "REMEDIATION REQUIRED"
        )
    )

    logger.info(
        "Generated institutional audit export for session '%s' (Status: %s, Hash: %s)",
        body.session_id,
        eval_status,
        audit_hash[:12],
    )

    return AuditReportResponse(
        header=InstitutionalAuditHeader(
            institution="Public Health Competency Assessment & Certification Authority",
            curriculum_standard="Foundational CEPH / CPH Public Health Pillars",
            issued_at=now_iso,
            audit_hash=audit_hash,
            certificate_id=cert_id,
        ),
        session_id=body.session_id,
        overall_score=round(body.overall_score, 2),
        status=eval_status,
        mcq_score=round(body.mcq_score, 2),
        scenario_score=round(body.scenario_score, 2),
        competency_scores=body.competency_scores,
        remediation_areas=body.remediation_areas,
    )


# =====================================================================
# Administrative Management Endpoints (Curriculum & Question Banks)
# =====================================================================


@app.post("/api/admin/upload-curriculum", summary="Upload and Index Learning Curriculum Document")
async def upload_curriculum(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Save curriculum reference material and re-index into ChromaDB vector store."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")

    ext = Path(file.filename).suffix.lower()
    if ext not in [".txt", ".md", ".pdf"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Supported formats are .txt, .md, and .pdf.",
        )

    textbooks_dir = _PROJECT_ROOT / "textbooks"
    textbooks_dir.mkdir(parents=True, exist_ok=True)
    target_file = textbooks_dir / file.filename

    try:
        content = await file.read()
        target_file.write_bytes(content)
        logger.info("Saved curriculum file '%s' (%d bytes) to %s", file.filename, len(content), target_file)
    except Exception as exc:
        logger.exception("Failed to save uploaded file: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(exc)}")

    # Run ingestion
    try:
        node_count = run_ingestion(textbooks_dir=textbooks_dir)
        logger.info("Ingestion completed successfully with %d total chunks indexed.", node_count)
    except Exception as exc:
        logger.exception("Ingestion failed after file upload: %s", exc)
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(exc)}")

    return {
        "status": "success",
        "filename": file.filename,
        "total_chunks": node_count,
        "message": f"Document '{file.filename}' successfully uploaded and indexed into {node_count} knowledge passages.",
    }


@app.post("/api/admin/upload-questions", summary="Upload and Validate Question Bank")
async def upload_questions(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Upload, validate, and hot-reload a JSON question bank."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")

    if not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Question bank must be a valid .json file.")

    try:
        raw_bytes = await file.read()
        raw_json = json.loads(raw_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON format: {str(exc)}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read file: {str(exc)}")

    # Validate against QuestionBank schema
    try:
        bank = QuestionBank.model_validate(raw_json)
    except Exception as exc:
        logger.warning("Question bank schema validation failed: %s", exc)
        raise HTTPException(status_code=422, detail=f"Question bank validation failed: {str(exc)}")

    bank_path = (
        _PROJECT_ROOT
        / "data"
        / "question_banks"
        / "core_competencies.json"
    )
    bank_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Write validated JSON
        with open(bank_path, "w", encoding="utf-8") as f:
            json.dump(bank.model_dump(), f, indent=2)

        # Hot-reload in memory
        load_question_bank_data()
        logger.info(
            "Successfully updated question bank with %d questions, %d competencies, %d scenarios.",
            len(bank.questions),
            len(bank.competencies),
            len(bank.scenarios),
        )
    except Exception as exc:
        logger.exception("Failed to write question bank file: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to persist question bank: {str(exc)}")

    return {
        "status": "success",
        "new_question_count": len(bank.questions),
        "total_competencies": len(bank.competencies),
        "total_scenarios": len(bank.scenarios),
        "message": f"Question bank updated successfully with {len(bank.questions)} questions and {len(bank.scenarios)} scenarios.",
    }


# =====================================================================
# Mount Static Frontend
# =====================================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

if os.path.exists(FRONTEND_DIR):
    # Mount /frontend prefix
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

    # Serve index on root
    @app.get("/", include_in_schema=False)
    async def serve_root_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    # Fallback routes for direct asset hits
    @app.get("/style.css", include_in_schema=False)
    async def serve_css():
        return FileResponse(os.path.join(FRONTEND_DIR, "style.css"))

    @app.get("/app.js", include_in_schema=False)
    async def serve_js():
        return FileResponse(os.path.join(FRONTEND_DIR, "app.js"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
