"""CrewAI objects for Binex example workflows.

Prerequisites:
    pip install binex[crewai]
    export OPENAI_API_KEY=sk-...

Objects defined here:
    - research_crew:   Multi-agent research crew (researcher + writer)
    - synthesis_crew:  Synthesizes research into a design document

Usage in workflow YAML:
    agent: "crewai://myproject.crews.research_crew"
"""

from crewai import Agent, Crew, Task

# --- Research Crew ---
# Used by: crewai-research-crew.yaml

_researcher = Agent(
    role="Senior Researcher",
    goal="Find comprehensive, accurate information on the given topic",
    backstory=(
        "You are an expert researcher with 15 years of experience in "
        "academic and industry research. You excel at finding reliable "
        "sources and synthesizing complex information."
    ),
    verbose=False,
)

_writer = Agent(
    role="Technical Writer",
    goal="Write a clear, well-structured report from research findings",
    backstory=(
        "You are a skilled technical writer who can take complex research "
        "and turn it into accessible, engaging reports for a broad audience."
    ),
    verbose=False,
)

research_crew = Crew(
    agents=[_researcher, _writer],
    tasks=[
        Task(
            description="Research the topic thoroughly: {input}",
            agent=_researcher,
            expected_output="Detailed research findings with key data points",
        ),
        Task(
            description="Write a polished report based on the research findings",
            agent=_writer,
            expected_output="A well-structured report with introduction, findings, and conclusion",
        ),
    ],
    verbose=False,
)

# --- Synthesis Crew ---
# Used by: mixed-framework-pipeline.yaml

_analyst = Agent(
    role="Systems Analyst",
    goal="Analyze research and facts to produce a coherent design document",
    backstory=(
        "You are a systems analyst who bridges research and implementation. "
        "You create clear design documents from disparate information sources."
    ),
    verbose=False,
)

synthesis_crew = Crew(
    agents=[_analyst],
    tasks=[
        Task(
            description=(
                "Synthesize the following research and facts into a design document "
                "with requirements, architecture, and implementation steps:\n{input}"
            ),
            agent=_analyst,
            expected_output="A design document with clear requirements and architecture",
        ),
    ],
    verbose=False,
)
