export const PATTERN_DEFAULT_PROMPTS: Record<string, Record<string, string>> = {
  critic: {
    draft: 'Based on the input, produce a thorough draft.',
    critique: 'Review the draft. List specific weaknesses, gaps, and errors.',
    refine: 'Revise the draft addressing each critique point.',
  },
  debate: {
    collector: 'Collect all arguments.',
    judge: 'Evaluate arguments and render a verdict.',
    agent: 'Argue your position on the topic.',
  },
  best_of_n: {
    judge: 'Compare all variants and select the best one.',
    variant: 'Generate a solution.',
  },
  reflexion: {
    actor: 'Attempt the task.',
    reflector: 'Reflect on the attempt. List what failed and what to improve. Output DONE if satisfactory.',
  },
  scatter: {
    mapper: 'Split the input into independent sub-tasks.',
    reducer: 'Combine all worker results into a single coherent output.',
  },
  constitutional: {
    generate: 'Generate initial response.',
    critique_principles: 'Evaluate the response against constitutional principles. List violations.',
    revise: 'Revise the response to address all principle violations.',
  },
  chain_of_verification: {
    generate: 'Generate initial response.',
    extract_claims: 'Extract all verifiable factual claims from the response.',
    verify_each: 'Verify each claim for accuracy. Mark as Accurate, Inaccurate, or Uncertain.',
    revise: 'Revise the response correcting all inaccurate claims.',
  },
  plan_execute: {
    planner: 'Create a step-by-step plan with clear success criteria for each step.',
    executor: 'Execute the plan step by step and produce the final result.',
    verifier: 'Verify execution results against the plan. Output DONE if satisfactory.',
  },
};
