"""Prompt role and variant registry for built-in templates."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class PromptVariant:
    """A single prompt variant for a role."""

    filename: str
    label: str
    description: str
    is_default: bool = False


@dataclass(frozen=True)
class PromptRole:
    """A role that can be placed in a workflow DAG."""

    name: str
    category: str
    phase: str  # "input" | "process" | "review" | "output"
    pairs_with: list[str] = field(default_factory=list)
    variants: list[PromptVariant] = field(default_factory=list)

    @property
    def default_variant(self) -> PromptVariant:
        for v in self.variants:
            if v.is_default:
                return v
        return self.variants[0]


@dataclass(frozen=True)
class TemplateConfig:
    """A workflow template within a category."""

    name: str
    label: str
    description: str
    dsl: str
    icon: str
    default_name: str
    node_roles: dict[str, str] = field(default_factory=dict)


def get_roles_by_category(category: str) -> list[PromptRole]:
    return [r for r in ROLES if r.category == category]


def get_role(name: str) -> PromptRole | None:
    for r in ROLES:
        if r.name == name:
            return r
    return None


# ---------------------------------------------------------------------------
# Category display configuration
# ---------------------------------------------------------------------------

CATEGORY_ORDER: list[str] = [
    "general",
    "development",
    "business",
    "content",
    "education",
    "legal",
    "data",
    "support",
]

CATEGORY_ICONS: dict[str, str] = {
    "general": "\U0001f50d",
    "development": "\U0001f6e0\ufe0f",
    "business": "\U0001f4ca",
    "content": "\u270f\ufe0f",
    "education": "\U0001f393",
    "legal": "\u2696\ufe0f",
    "data": "\U0001f52c",
    "support": "\U0001f4ac",
}

# ---------------------------------------------------------------------------
# Template registry — 24 pipelines across 8 categories
# ---------------------------------------------------------------------------

TEMPLATE_CATEGORIES: dict[str, list[TemplateConfig]] = {
    "general": [
        TemplateConfig(
            name="research",
            label="Research",
            description="plan, research, validate, summarize",
            dsl="planner -> researcher1, researcher2 -> validator -> summarizer",
            icon="\U0001f50d",
            default_name="my-research-pipeline",
            node_roles={
                "planner": "research-planner",
                "researcher1": "researcher",
                "researcher2": "researcher",
                "validator": "research-validator",
                "summarizer": "research-synthesizer",
            },
        ),
        TemplateConfig(
            name="content-review",
            label="Content Review",
            description="draft, review, revise, finalize",
            dsl="draft -> review -> revise -> finalize",
            icon="\U0001f4dd",
            default_name="my-content-review",
            node_roles={
                "draft": "draft-writer",
                "review": "content-reviewer",
                "revise": "content-reviser",
                "finalize": "content-editor",
            },
        ),
        TemplateConfig(
            name="data-processing",
            label="Data Processing",
            description="split, process in parallel, merge",
            dsl="splitter -> processor1, processor2, processor3 -> merger",
            icon="\u2699\ufe0f",
            default_name="my-data-pipeline",
            node_roles={
                "splitter": "chunk-splitter",
                "processor1": "chunk-processor",
                "processor2": "chunk-processor",
                "processor3": "chunk-processor",
                "merger": "chunk-merger",
            },
        ),
        TemplateConfig(
            name="map-reduce",
            label="Map-Reduce",
            description="process, aggregate, refine",
            dsl="mapper -> reducer -> analyzer",
            icon="\U0001f5c2\ufe0f",
            default_name="my-map-reduce",
            node_roles={
                "mapper": "data-processor",
                "reducer": "data-aggregator",
                "analyzer": "data-refiner",
            },
        ),
    ],
    "development": [
        TemplateConfig(
            "qa-testing",
            "QA Testing",
            "plan tests, write cases, find edge cases, review",
            "test-planner -> test-writer, edge-case-finder -> test-reviewer",
            "\U0001f9ea",
            "my-qa-testing",
            {
                "test-planner": "test-planner",
                "test-writer": "test-writer",
                "edge-case-finder": "edge-case-finder",
                "test-reviewer": "test-reviewer",
            },
        ),
        TemplateConfig(
            "code-generation",
            "Code Generation",
            "plan, code, review, refactor",
            "task-planner -> coder -> code-reviewer -> refactorer",
            "\U0001f4bb",
            "my-code-generation",
            {
                "task-planner": "task-planner",
                "coder": "coder",
                "code-reviewer": "code-reviewer",
                "refactorer": "refactorer",
            },
        ),
        TemplateConfig(
            "code-review",
            "Code Review",
            "analyze, security + performance audit, verdict",
            "analyzer -> security-auditor, performance-checker -> verdict-writer",
            "\U0001f50e",
            "my-code-review",
            {
                "analyzer": "code-analyzer",
                "security-auditor": "security-auditor",
                "performance-checker": "performance-checker",
                "verdict-writer": "verdict-writer",
            },
        ),
        TemplateConfig(
            "bug-triage",
            "Bug Triage",
            "reproduce, root cause, fix, assess impact",
            "reproducer -> root-cause -> fix-suggester -> impact-assessor",
            "\U0001f41b",
            "my-bug-triage",
            {
                "reproducer": "bug-reproducer",
                "root-cause": "root-cause-analyzer",
                "fix-suggester": "fix-suggester",
                "impact-assessor": "impact-assessor",
            },
        ),
        TemplateConfig(
            "api-design",
            "API Design",
            "requirements, schema, review, docs",
            "requirements -> schema-drafter -> schema-reviewer -> docs-generator",
            "\U0001f310",
            "my-api-design",
            {
                "requirements": "requirements-extractor",
                "schema-drafter": "schema-drafter",
                "schema-reviewer": "schema-reviewer",
                "docs-generator": "docs-generator",
            },
        ),
    ],
    "business": [
        TemplateConfig(
            "competitive-analysis",
            "Competitive Analysis",
            "collect, analyze competitors, SWOT, recommend",
            "collector -> analyst1, analyst2 -> swot-writer -> recommender",
            "\U0001f4c8",
            "my-competitive-analysis",
            {
                "collector": "data-collector",
                "analyst1": "competitor-analyzer",
                "analyst2": "competitor-analyzer",
                "swot-writer": "swot-writer",
                "recommender": "recommender",
            },
        ),
        TemplateConfig(
            "report-generation",
            "Report Generation",
            "collect metrics, visualize + narrate, summarize",
            "metrics-collector -> visualizer, narrative-writer -> executive-summarizer",
            "\U0001f4c4",
            "my-report-generation",
            {
                "metrics-collector": "metrics-collector",
                "visualizer": "visualizer",
                "narrative-writer": "narrative-writer",
                "executive-summarizer": "executive-summarizer",
            },
        ),
        TemplateConfig(
            "proposal-writing",
            "Proposal Writing",
            "analyze brief, draft, estimate pricing, finalize",
            "brief-analyzer -> draft-writer -> pricing-estimator -> proposal-finalizer",
            "\U0001f4b0",
            "my-proposal",
            {
                "brief-analyzer": "brief-analyzer",
                "draft-writer": "proposal-draft-writer",
                "pricing-estimator": "pricing-estimator",
                "proposal-finalizer": "proposal-finalizer",
            },
        ),
    ],
    "content": [
        TemplateConfig(
            "seo-content",
            "SEO Content",
            "keywords, outline, draft, optimize",
            "keyword-researcher -> outline-writer -> content-drafter -> seo-optimizer",
            "\U0001f50d",
            "my-seo-content",
            {
                "keyword-researcher": "keyword-researcher",
                "outline-writer": "outline-writer",
                "content-drafter": "content-drafter",
                "seo-optimizer": "seo-optimizer",
            },
        ),
        TemplateConfig(
            "social-media",
            "Social Media",
            "analyze topic, adapt per platform, check tone",
            "topic-analyzer -> platform-adapter1, platform-adapter2 -> tone-checker",
            "\U0001f4f1",
            "my-social-media",
            {
                "topic-analyzer": "topic-analyzer",
                "platform-adapter1": "platform-adapter",
                "platform-adapter2": "platform-adapter",
                "tone-checker": "tone-checker",
            },
        ),
        TemplateConfig(
            "email-campaign",
            "Email Campaign",
            "segment, personalize, A/B variants, finalize",
            "segmenter -> personalizer -> variant-a, variant-b -> campaign-finalizer",
            "\U0001f4e7",
            "my-email-campaign",
            {
                "segmenter": "audience-segmenter",
                "personalizer": "personalizer",
                "variant-a": "variant-writer",
                "variant-b": "variant-writer",
                "campaign-finalizer": "campaign-finalizer",
            },
        ),
    ],
    "education": [
        TemplateConfig(
            "lesson-planning",
            "Lesson Planning",
            "analyze topic, structure, materials, quiz",
            "topic-analyzer -> lesson-structurer -> materials-creator -> quiz-generator",
            "\U0001f4da",
            "my-lesson-plan",
            {
                "topic-analyzer": "edu-topic-analyzer",
                "lesson-structurer": "lesson-structurer",
                "materials-creator": "materials-creator",
                "quiz-generator": "quiz-generator",
            },
        ),
        TemplateConfig(
            "essay-grading",
            "Essay Grading",
            "extract criteria, evaluate, feedback, suggest improvements",
            "criteria-extractor -> evaluator -> feedback-writer -> improvement-suggester",
            "\U0001f4dd",
            "my-essay-grading",
            {
                "criteria-extractor": "criteria-extractor",
                "evaluator": "essay-evaluator",
                "feedback-writer": "feedback-writer",
                "improvement-suggester": "improvement-suggester",
            },
        ),
    ],
    "legal": [
        TemplateConfig(
            "contract-review",
            "Contract Review",
            "extract clauses, analyze risk, check compliance, summarize",
            "clause-extractor -> risk-analyzer -> compliance-checker -> contract-summarizer",
            "\U0001f4dc",
            "my-contract-review",
            {
                "clause-extractor": "clause-extractor",
                "risk-analyzer": "risk-analyzer",
                "compliance-checker": "compliance-checker",
                "contract-summarizer": "contract-summarizer",
            },
        ),
        TemplateConfig(
            "policy-analysis",
            "Policy Analysis",
            "parse policy, assess impact, recommend",
            "policy-parser -> impact-assessor -> recommendation-writer",
            "\U0001f3db\ufe0f",
            "my-policy-analysis",
            {
                "policy-parser": "policy-parser",
                "impact-assessor": "policy-impact-assessor",
                "recommendation-writer": "recommendation-writer",
            },
        ),
    ],
    "data": [
        TemplateConfig(
            "data-cleaning",
            "Data Cleaning",
            "validate, normalize, deduplicate, quality report",
            "validator -> normalizer -> deduplicator -> quality-reporter",
            "\U0001f9f9",
            "my-data-cleaning",
            {
                "validator": "data-validator",
                "normalizer": "data-normalizer",
                "deduplicator": "data-deduplicator",
                "quality-reporter": "quality-reporter",
            },
        ),
        TemplateConfig(
            "prompt-optimization",
            "Prompt Optimization",
            "write baseline, variations in parallel, evaluate, pick best",
            "baseline-writer -> variation1, variation2 -> evaluator -> best-picker",
            "\u2728",
            "my-prompt-optimization",
            {
                "baseline-writer": "baseline-writer",
                "variation1": "variation-writer",
                "variation2": "variation-writer",
                "evaluator": "prompt-evaluator",
                "best-picker": "best-picker",
            },
        ),
    ],
    "support": [
        TemplateConfig(
            "customer-support",
            "Customer Support",
            "classify query, generate response, check tone",
            "classifier -> response-generator -> tone-checker",
            "\U0001f4de",
            "my-customer-support",
            {
                "classifier": "query-classifier",
                "response-generator": "response-generator",
                "tone-checker": "support-tone-checker",
            },
        ),
        TemplateConfig(
            "translation",
            "Translation",
            "translate, check accuracy + cultural fit, finalize",
            "translator -> accuracy-checker, cultural-adapter -> finalizer",
            "\U0001f30d",
            "my-translation",
            {
                "translator": "translator",
                "accuracy-checker": "accuracy-checker",
                "cultural-adapter": "cultural-adapter",
                "finalizer": "translation-finalizer",
            },
        ),
        TemplateConfig(
            "summarization",
            "Summarization",
            "extract key facts, parallel summaries, synthesize",
            "extractor -> summarizer1, summarizer2 -> synthesizer",
            "\U0001f4cb",
            "my-summarization",
            {
                "extractor": "key-fact-extractor",
                "summarizer1": "summarizer",
                "summarizer2": "summarizer",
                "synthesizer": "summary-synthesizer",
            },
        ),
    ],
}


# ---------------------------------------------------------------------------
# Role registry — loaded from YAML data file
# ---------------------------------------------------------------------------

_ROLES_YAML = Path(__file__).parent.parent / "prompts" / "roles" / "roles.yaml"


def _load_roles() -> list[PromptRole]:
    """Load roles from the YAML data file."""
    with open(_ROLES_YAML) as f:
        raw: list[dict[str, Any]] = yaml.safe_load(f)
    roles: list[PromptRole] = []
    for entry in raw:
        variants = [
            PromptVariant(
                filename=v["filename"],
                label=v["label"],
                description=v["description"],
                is_default=v.get("is_default", False),
            )
            for v in entry.get("variants", [])
        ]
        roles.append(
            PromptRole(
                name=entry["name"],
                category=entry["category"],
                phase=entry["phase"],
                pairs_with=entry.get("pairs_with", []),
                variants=variants,
            )
        )
    return roles


ROLES: list[PromptRole] = _load_roles()
