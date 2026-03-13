"""LangChain objects for Binex example workflows.

Prerequisites:
    pip install binex[langchain] langchain-openai

Objects defined here:
    - summarizer:   Summarizes research text
    - researcher:   Researches a topic in depth
    - fact_checker: Verifies facts and claims

Usage in workflow YAML:
    agent: "langchain://myproject.chains.summarizer"
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# --- Summarizer chain ---
# Used by: langchain-summarizer.yaml, mixed-framework-pipeline.yaml

summarizer = (
    ChatPromptTemplate.from_template(
        "You are an expert summarizer. Read the following research and produce "
        "a concise summary with key takeaways.\n\n"
        "Research:\n{input}"
    )
    | ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
)

# --- Researcher chain ---
# Used by: mixed-framework-pipeline.yaml

researcher = (
    ChatPromptTemplate.from_template(
        "You are a thorough researcher. Given the following plan, investigate "
        "each point and produce detailed findings with sources.\n\n"
        "Plan:\n{input}"
    )
    | ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
)

# --- Fact-checker chain ---
# Used by: mixed-framework-pipeline.yaml

fact_checker = (
    ChatPromptTemplate.from_template(
        "You are a fact-checker. Verify the claims in the following plan. "
        "For each claim, state whether it is supported, unsupported, or "
        "needs more evidence.\n\n"
        "Plan:\n{input}"
    )
    | ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
)
