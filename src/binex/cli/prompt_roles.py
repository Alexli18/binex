"""Prompt role and variant registry for built-in templates."""

from __future__ import annotations

from dataclasses import dataclass, field


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
# Role registry — stub roles (one per category) for initial tests.
# Will be fully populated in Phase 6 (US4).
# ---------------------------------------------------------------------------

_V = PromptVariant
_R = PromptRole

ROLES: list[PromptRole] = [
    # -- General --
    _R("research-planner", "general", "input", ["researcher"],
       [_V("gen-research-planner.md", "Default", "Plan research goals and approach", True)]),
    _R("researcher", "general", "process", ["research-planner", "research-validator"],
       [_V("gen-researcher.md", "Default", "Conduct deep research on assigned topic", True)]),
    _R("research-validator", "general", "review", ["researcher"],
       [_V("gen-research-validator.md", "Default", "Validate research quality", True)]),
    _R("research-synthesizer", "general", "output", ["research-validator"],
       [_V("gen-research-synthesizer.md", "Default", "Synthesize findings into summary", True)]),
    _R("draft-writer", "general", "process", ["content-reviewer"],
       [_V("gen-draft-writer.md", "Default", "Write initial content draft", True)]),
    _R("content-reviewer", "general", "review", ["draft-writer", "content-reviser"],
       [_V("gen-content-reviewer.md", "Default", "Review content for quality", True)]),
    _R("content-reviser", "general", "process", ["content-reviewer"],
       [_V("gen-content-reviser.md", "Default", "Revise content based on review", True)]),
    _R("content-editor", "general", "output", ["content-reviser"],
       [_V("gen-content-editor.md", "Default", "Final editing and polish", True)]),
    _R("chunk-splitter", "general", "input", ["chunk-processor"],
       [_V("gen-chunk-splitter.md", "Default", "Split data into chunks", True)]),
    _R("chunk-processor", "general", "process", ["chunk-splitter", "chunk-merger"],
       [_V("gen-chunk-processor.md", "Default", "Process individual chunks", True)]),
    _R("chunk-merger", "general", "output", ["chunk-processor"],
       [_V("gen-chunk-merger.md", "Default", "Merge processed chunks", True)]),
    _R("data-processor", "general", "process", ["data-aggregator"],
       [_V("gen-data-processor.md", "Default", "Process data records", True)]),
    _R("data-aggregator", "general", "process", ["data-processor", "data-refiner"],
       [_V("gen-data-aggregator.md", "Default", "Aggregate processed data", True)]),
    _R("data-refiner", "general", "output", ["data-aggregator"],
       [_V("gen-data-refiner.md", "Default", "Refine and polish aggregated data", True)]),

    # -- Development --
    _R("test-planner", "development", "input", ["test-writer"],
       [_V("dev-test-planner.md", "Default", "Plan test strategy and cases", True)]),
    _R("test-writer", "development", "process", ["test-planner", "test-reviewer"],
       [_V("dev-test-writer.md", "Default", "Write test cases from plan", True)]),
    _R("edge-case-finder", "development", "process", ["test-planner", "test-reviewer"],
       [_V("dev-edge-case-finder.md", "Default", "Find boundary and edge cases", True)]),
    _R("test-reviewer", "development", "review", ["test-writer", "edge-case-finder"],
       [_V("dev-test-reviewer-strict.md", "Strict", "Hard pass/fail verdict", True),
        _V("dev-test-reviewer-balanced.md", "Balanced", "Pragmatic review with priorities"),
        _V("dev-test-reviewer-mentor.md", "Mentor", "Educational tone, explain why")]),
    _R("task-planner", "development", "input", ["coder"],
       [_V("dev-task-planner.md", "Default", "Break task into implementation steps", True)]),
    _R("coder", "development", "process", ["task-planner", "code-reviewer"],
       [_V("dev-coder.md", "Default", "Write production code from plan", True)]),
    _R("code-reviewer", "development", "review", ["coder", "refactorer"],
       [_V("dev-code-reviewer-strict.md", "Strict", "Focus on bugs, security, hard verdict", True),
        _V("dev-code-reviewer-mentor.md", "Mentor", "Educational tone, explain why"),
        _V("dev-code-reviewer-security.md", "Security", "OWASP-focused, vulnerability hunting")]),
    _R("refactorer", "development", "process", ["code-reviewer"],
       [_V("dev-refactorer.md", "Default", "Refactor code for clarity", True)]),
    _R("code-analyzer", "development", "input", ["security-auditor", "performance-checker"],
       [_V("dev-code-analyzer.md", "Default", "Static analysis and code structure review", True)]),
    _R("security-auditor", "development", "review", ["code-analyzer", "verdict-writer"],
       [_V("dev-security-auditor-strict.md", "Strict", "Zero-tolerance security review", True),
        _V("dev-security-auditor-balanced.md", "Balanced", "Risk-weighted security assessment"),
        _V("dev-security-auditor-pentest.md", "Pentest", "Offensive security perspective")]),
    _R("performance-checker", "development", "review", ["code-analyzer", "verdict-writer"],
       [_V("dev-performance-checker.md", "Default", "Performance and efficiency analysis", True)]),
    _R("verdict-writer", "development", "output", ["security-auditor", "performance-checker"],
       [_V("dev-verdict-writer.md", "Default", "Synthesize review into final verdict", True)]),
    _R("bug-reproducer", "development", "input", ["root-cause-analyzer"],
       [_V("dev-bug-reproducer.md", "Default", "Reproduce and isolate bug", True)]),
    _R("root-cause-analyzer", "development", "process", ["bug-reproducer", "fix-suggester"],
       [_V("dev-root-cause-analyzer.md", "Default", "Identify root cause of bug", True)]),
    _R("fix-suggester", "development", "process", ["root-cause-analyzer", "impact-assessor"],
       [_V("dev-fix-suggester.md", "Default", "Suggest fix approaches", True)]),
    _R("impact-assessor", "development", "output", ["fix-suggester"],
       [_V("dev-impact-assessor.md", "Default", "Assess fix impact and risk", True)]),
    _R("requirements-extractor", "development", "input", ["schema-drafter"],
       [_V("dev-requirements-extractor.md", "Default", "Extract API requirements", True)]),
    _R("schema-drafter", "development", "process", ["requirements-extractor", "schema-reviewer"],
       [_V("dev-schema-drafter.md", "Default", "Draft API schema from requirements", True)]),
    _R("schema-reviewer", "development", "review", ["schema-drafter", "docs-generator"],
       [_V("dev-schema-reviewer.md", "Default", "Review schema for correctness", True)]),
    _R("docs-generator", "development", "output", ["schema-reviewer"],
       [_V("dev-docs-generator.md", "Default", "Generate API documentation", True)]),

    # -- Business --
    _R("data-collector", "business", "input", ["competitor-analyzer"],
       [_V("biz-data-collector.md", "Default", "Collect business data from sources", True)]),
    _R("competitor-analyzer", "business", "process", ["data-collector", "swot-writer"],
       [_V("biz-competitor-analyzer.md", "Default", "Analyze competitor strengths", True)]),
    _R("swot-writer", "business", "process", ["competitor-analyzer", "recommender"],
       [_V("biz-swot-writer.md", "Default", "Write SWOT analysis", True)]),
    _R("recommender", "business", "output", ["swot-writer"],
       [_V("biz-recommender.md", "Default", "Generate strategic recommendations", True)]),
    _R("metrics-collector", "business", "input", ["visualizer", "narrative-writer"],
       [_V("biz-metrics-collector.md", "Default", "Collect and organize business metrics", True)]),
    _R("visualizer", "business", "process", ["metrics-collector", "executive-summarizer"],
       [_V("biz-visualizer.md", "Default", "Create data visualizations", True)]),
    _R("narrative-writer", "business", "process", ["metrics-collector", "executive-summarizer"],
       [_V("biz-narrative-writer-formal.md", "Formal", "Business-formal narrative style", True),
        _V("biz-narrative-writer-casual.md", "Casual", "Conversational narrative style")]),
    _R("executive-summarizer", "business", "output", ["visualizer", "narrative-writer"],
       [_V("biz-executive-summarizer-brief.md", "Brief", "One-page executive summary", True),
        _V("biz-executive-summarizer-detailed.md", "Detailed", "Full executive report")]),
    _R("brief-analyzer", "business", "input", ["proposal-draft-writer"],
       [_V("biz-brief-analyzer.md", "Default", "Analyze client brief and requirements", True)]),
    _R("proposal-draft-writer", "business", "process", ["brief-analyzer", "pricing-estimator"],
       [_V("biz-proposal-draft-writer.md", "Default", "Draft proposal from brief", True)]),
    _R("pricing-estimator", "business", "process", ["proposal-draft-writer", "proposal-finalizer"],
       [_V("biz-pricing-estimator.md", "Default", "Estimate project pricing", True)]),
    _R("proposal-finalizer", "business", "output", ["pricing-estimator"],
       [_V("biz-proposal-finalizer.md", "Default", "Finalize and format proposal", True)]),

    # -- Content --
    _R("keyword-researcher", "content", "input", ["outline-writer"],
       [_V("cnt-keyword-researcher.md", "Default", "Research SEO keywords and trends", True)]),
    _R("outline-writer", "content", "process", ["keyword-researcher", "content-drafter"],
       [_V("cnt-outline-writer.md", "Default", "Create content outline from keywords", True)]),
    _R("content-drafter", "content", "process", ["outline-writer", "seo-optimizer"],
       [_V("cnt-content-drafter-formal.md", "Formal", "Professional tone content", True),
        _V("cnt-content-drafter-casual.md", "Casual", "Conversational and engaging tone")]),
    _R("seo-optimizer", "content", "output", ["content-drafter"],
       [_V("cnt-seo-optimizer.md", "Default", "Optimize content for search engines", True)]),
    _R("topic-analyzer", "content", "input", ["platform-adapter"],
       [_V("cnt-topic-analyzer.md", "Default", "Analyze topic for social media angles", True)]),
    _R("platform-adapter", "content", "process", ["topic-analyzer", "tone-checker"],
       [_V("cnt-platform-adapter.md", "Default", "Adapt content per social platform", True)]),
    _R("tone-checker", "content", "review", ["platform-adapter"],
       [_V("cnt-tone-checker-brand.md", "Brand", "Check brand voice consistency", True),
        _V("cnt-tone-checker-professional.md", "Professional", "Professional tone verification")]),
    _R("audience-segmenter", "content", "input", ["personalizer"],
       [_V("cnt-audience-segmenter.md", "Default", "Segment audience for targeting", True)]),
    _R("personalizer", "content", "process", ["audience-segmenter", "variant-writer"],
       [_V("cnt-personalizer.md", "Default", "Personalize content per segment", True)]),
    _R("variant-writer", "content", "process", ["personalizer", "campaign-finalizer"],
       [_V("cnt-variant-writer.md", "Default", "Write A/B test variants", True)]),
    _R("campaign-finalizer", "content", "output", ["variant-writer"],
       [_V("cnt-campaign-finalizer.md", "Default", "Finalize email campaign", True)]),

    # -- Education --
    _R("edu-topic-analyzer", "education", "input", ["lesson-structurer"],
       [_V("edu-topic-analyzer.md", "Default", "Analyze educational topic and objectives", True)]),
    _R("lesson-structurer", "education", "process", ["edu-topic-analyzer", "materials-creator"],
       [_V("edu-lesson-structurer.md", "Default", "Structure lesson plan", True)]),
    _R("materials-creator", "education", "process", ["lesson-structurer", "quiz-generator"],
       [_V("edu-materials-creator.md", "Default", "Create learning materials", True)]),
    _R("quiz-generator", "education", "output", ["materials-creator"],
       [_V("edu-quiz-generator.md", "Default", "Generate assessment questions", True)]),
    _R("criteria-extractor", "education", "input", ["essay-evaluator"],
       [_V("edu-criteria-extractor.md", "Default", "Extract grading criteria", True)]),
    _R("essay-evaluator", "education", "process", ["criteria-extractor", "feedback-writer"],
       [_V("edu-essay-evaluator-strict.md", "Strict", "Rigorous academic evaluation", True),
        _V("edu-essay-evaluator-encouraging.md", "Encouraging", "Growth-focused evaluation"),
        _V("edu-essay-evaluator-rubric.md", "Rubric", "Rubric-based systematic evaluation")]),
    _R("feedback-writer", "education", "process", ["essay-evaluator", "improvement-suggester"],
       [_V("edu-feedback-writer.md", "Default", "Write constructive feedback", True)]),
    _R("improvement-suggester", "education", "output", ["feedback-writer"],
       [_V("edu-improvement-suggester.md", "Default", "Suggest specific improvements", True)]),

    # -- Legal --
    _R("clause-extractor", "legal", "input", ["risk-analyzer"],
       [_V("leg-clause-extractor.md", "Default", "Extract key clauses from contracts", True)]),
    _R("risk-analyzer", "legal", "process", ["clause-extractor", "compliance-checker"],
       [_V("leg-risk-analyzer-risk.md", "Risk", "Focus on financial and legal risk", True),
        _V("leg-risk-analyzer-compliance.md", "Compliance", "Regulatory compliance focus"),
        _V("leg-risk-analyzer-full.md", "Full", "Comprehensive risk assessment")]),
    _R("compliance-checker", "legal", "review", ["risk-analyzer", "contract-summarizer"],
       [_V("leg-compliance-checker.md", "Default", "Check regulatory compliance", True)]),
    _R("contract-summarizer", "legal", "output", ["compliance-checker"],
       [_V("leg-contract-summarizer.md", "Default", "Summarize contract terms", True)]),
    _R("policy-parser", "legal", "input", ["policy-impact-assessor"],
       [_V("leg-policy-parser.md", "Default", "Parse policy document structure", True)]),
    _R("policy-impact-assessor", "legal", "process", ["policy-parser", "recommendation-writer"],
       [_V("leg-policy-impact-assessor.md", "Default", "Assess policy impact", True)]),
    _R("recommendation-writer", "legal", "output", ["policy-impact-assessor"],
       [_V("leg-recommendation-writer.md", "Default", "Write policy recommendations", True)]),

    # -- Data --
    _R("data-validator", "data", "input", ["data-normalizer"],
       [_V("dat-data-validator.md", "Default", "Validate data integrity and format", True)]),
    _R("data-normalizer", "data", "process", ["data-validator", "data-deduplicator"],
       [_V("dat-data-normalizer.md", "Default", "Normalize data formats", True)]),
    _R("data-deduplicator", "data", "process", ["data-normalizer", "quality-reporter"],
       [_V("dat-data-deduplicator.md", "Default", "Deduplicate data records", True)]),
    _R("quality-reporter", "data", "output", ["data-deduplicator"],
       [_V("dat-quality-reporter.md", "Default", "Generate data quality report", True)]),
    _R("baseline-writer", "data", "input", ["variation-writer"],
       [_V("dat-baseline-writer.md", "Default", "Write baseline prompt version", True)]),
    _R("variation-writer", "data", "process", ["baseline-writer", "prompt-evaluator"],
       [_V("dat-variation-writer.md", "Default", "Write prompt variations", True)]),
    _R("prompt-evaluator", "data", "review", ["variation-writer", "best-picker"],
       [_V("dat-prompt-evaluator.md", "Default", "Evaluate prompt quality metrics", True)]),
    _R("best-picker", "data", "output", ["prompt-evaluator"],
       [_V("dat-best-picker.md", "Default", "Select best performing prompt", True)]),

    # -- Support --
    _R("query-classifier", "support", "input", ["response-generator"],
       [_V("sup-query-classifier.md", "Default", "Classify customer query type", True)]),
    _R("response-generator", "support", "process", ["query-classifier", "support-tone-checker"],
       [_V("sup-response-generator.md", "Default", "Generate support response", True)]),
    _R("support-tone-checker", "support", "review", ["response-generator"],
       [_V("sup-support-tone-checker-brand.md", "Brand", "Check brand voice in responses", True),
        _V("sup-support-tone-checker-friendly.md", "Friendly", "Ensure warm, friendly tone")]),
    _R("translator", "support", "process", ["accuracy-checker"],
       [_V("sup-translator-literal.md", "Literal", "Word-for-word accurate translation", True),
        _V("sup-translator-adaptive.md", "Adaptive", "Context-adapted natural translation"),
        _V("sup-translator-creative.md", "Creative", "Creative localization translation")]),
    _R("accuracy-checker", "support", "review", ["translator", "cultural-adapter"],
       [_V("sup-accuracy-checker.md", "Default", "Verify translation accuracy", True)]),
    _R("cultural-adapter", "support", "process", ["translator", "translation-finalizer"],
       [_V("sup-cultural-adapter.md", "Default", "Adapt content for cultural context", True)]),
    _R("translation-finalizer", "support", "output", ["accuracy-checker", "cultural-adapter"],
       [_V("sup-translation-finalizer.md", "Default", "Finalize translated content", True)]),
    _R("key-fact-extractor", "support", "input", ["summarizer"],
       [_V("sup-key-fact-extractor.md", "Default", "Extract key facts from documents", True)]),
    _R("summarizer", "support", "process", ["key-fact-extractor", "summary-synthesizer"],
       [_V("sup-summarizer-brief.md", "Brief", "Short executive summary", True),
        _V("sup-summarizer-detailed.md", "Detailed", "Comprehensive detailed summary"),
        _V("sup-summarizer-executive.md", "Executive", "C-level focused summary")]),
    _R("summary-synthesizer", "support", "output", ["summarizer"],
       [_V("sup-summary-synthesizer.md", "Default", "Synthesize multiple summaries", True)]),
]
