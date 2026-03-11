"""Tests for prompt role registry."""

from binex.cli.prompt_roles import (
    CATEGORY_ICONS,
    CATEGORY_ORDER,
    ROLES,
    TEMPLATE_CATEGORIES,
    PromptRole,
    PromptVariant,
    TemplateConfig,
    get_role,
    get_roles_by_category,
)


def test_prompt_variant_fields():
    v = PromptVariant(
        filename="dev-code-reviewer-strict.md",
        label="Strict",
        description="Focus on bugs, security, hard verdict",
        is_default=True,
    )
    assert v.filename == "dev-code-reviewer-strict.md"
    assert v.is_default is True


def test_prompt_role_fields():
    r = PromptRole(
        name="code-reviewer",
        category="development",
        phase="review",
        pairs_with=["coder", "analyzer"],
        variants=[
            PromptVariant(
                "dev-code-reviewer-strict.md", "Strict", "Hard verdict", True
            ),
        ],
    )
    assert r.name == "code-reviewer"
    assert r.category == "development"
    assert r.phase == "review"
    assert len(r.variants) == 1
    assert r.default_variant.filename == "dev-code-reviewer-strict.md"


def test_prompt_role_no_default_falls_back_to_first():
    r = PromptRole(
        name="test",
        category="general",
        phase="process",
        pairs_with=[],
        variants=[
            PromptVariant("a.md", "A", "desc", False),
            PromptVariant("b.md", "B", "desc", False),
        ],
    )
    assert r.default_variant.filename == "a.md"


def test_roles_registry_not_empty():
    assert len(ROLES) > 0


def test_get_roles_by_category():
    dev_roles = get_roles_by_category("development")
    assert len(dev_roles) > 0
    assert all(r.category == "development" for r in dev_roles)


def test_get_roles_by_category_unknown():
    assert get_roles_by_category("nonexistent") == []


def test_get_role_by_name():
    role = get_role("code-reviewer")
    assert role is not None
    assert role.name == "code-reviewer"


def test_get_role_unknown():
    assert get_role("nonexistent") is None


def test_all_categories_present():
    categories = {r.category for r in ROLES}
    expected = {
        "general", "development", "business", "content",
        "education", "legal", "data", "support",
    }
    assert categories == expected


def test_all_phases_valid():
    valid_phases = {"input", "process", "review", "output"}
    for role in ROLES:
        assert role.phase in valid_phases, (
            f"{role.name} has invalid phase {role.phase}"
        )


def test_all_variant_filenames_unique():
    filenames = [v.filename for r in ROLES for v in r.variants]
    assert len(filenames) == len(set(filenames))


# -- Template registry tests --


def test_template_config_fields():
    t = TemplateConfig(
        name="code-review",
        label="Code Review",
        description="analyzer, security, performance, verdict",
        dsl="analyzer -> security-auditor, performance-checker -> verdict-writer",
        icon="\U0001f6e0",
        default_name="my-code-review",
        node_roles={
            "analyzer": "code-analyzer",
            "security-auditor": "security-auditor",
        },
    )
    assert t.name == "code-review"
    assert "analyzer" in t.node_roles


def test_template_categories_has_all_categories():
    assert set(TEMPLATE_CATEGORIES.keys()) == set(CATEGORY_ORDER)


def test_category_order_length():
    assert len(CATEGORY_ORDER) == 8


def test_each_category_has_templates():
    for cat in CATEGORY_ORDER:
        assert len(TEMPLATE_CATEGORIES[cat]) > 0, (
            f"Category {cat} is empty"
        )


def test_category_icons_match():
    for cat in CATEGORY_ORDER:
        assert cat in CATEGORY_ICONS


def test_all_template_dsls_are_parseable():
    from binex.cli.dsl_parser import parse_dsl
    for cat, templates in TEMPLATE_CATEGORIES.items():
        for t in templates:
            parsed = parse_dsl([t.dsl])
            assert len(parsed.nodes) >= 2, (
                f"{cat}/{t.name} has <2 nodes"
            )


def test_total_templates_count():
    total = sum(len(ts) for ts in TEMPLATE_CATEGORIES.values())
    assert total == 24


def test_all_variant_files_exist():
    """Every filename referenced in ROLES must exist in prompts dir."""
    from pathlib import Path
    prompts_dir = Path(__file__).resolve().parents[2] / "src" / "binex" / "prompts"
    missing = []
    for role in ROLES:
        for v in role.variants:
            if not (prompts_dir / v.filename).is_file():
                missing.append(v.filename)
    assert missing == [], f"Missing prompt files: {missing}"
