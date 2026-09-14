# ASD prospecting discovery sources

Scope: public, attributable discovery only. No outreach, private data, guessed
emails, data brokers, or private-profile scraping. Reviewed 2026-09-14.

## Source 1

- SOURCE: GitHub topic search
- URL: https://github.com/topics/ai-agents
- TYPE: GitHub topic
- WHY_USEFUL: Finds active agent projects and maintainers across stacks.
- WHAT_TO_SEARCH: ai-agents, agentic-ai, multi-agent, orchestration, reliability, retries, loops, observability.
- SIGNALS_OF_FIT: Recent commits, issues about stuck runs/tool calls, small or mid-sized teams, public maintainer identity.
- CONTACT_PATHS: Public repository issues, discussions, contribution history, linked profiles.
- LIMITATIONS: Topic labels are noisy; stars and recency are discovery signals, not product validation.
- PRIORITY: HIGH

## Source 2

- SOURCE: GitHub contributor graphs and issue trackers
- URL: https://github.com/langchain-ai/langgraph/graphs/contributors
- TYPE: GitHub repository activity
- WHY_USEFUL: Identifies active maintainers and contributors operating real agent frameworks.
- WHAT_TO_SEARCH: langgraph, langchain, pydantic-ai, crewAI, llama_index, langfuse, letta, mastra, ag2, braintrust.
- SIGNALS_OF_FIT: Repeated workflow/tool/state issues, recent technical contributions, public project ownership.
- CONTACT_PATHS: Repository issues/discussions and verified GitHub profiles.
- LIMITATIONS: Contributor activity does not prove buyer intent or ASD pain.
- PRIORITY: HIGH

## Source 3

- SOURCE: Official agent framework repositories
- URL: https://github.com/langchain-ai/langgraph; https://github.com/pydantic/pydantic-ai; https://github.com/CrewAIInc/crewAI; https://github.com/run-llama/llama_index
- TYPE: OSS project source
- WHY_USEFUL: Public evidence of teams building multi-step, stateful, tool-using agents.
- WHAT_TO_SEARCH: runtime behavior, retries, checkpoints, tool errors, task success, production, cost.
- SIGNALS_OF_FIT: Active maintainers, production documentation, reproducible examples, operational issue threads.
- CONTACT_PATHS: Issues, discussions where enabled, contributor profiles, official communities.
- LIMITATIONS: Project scale can make individual outreach difficult; framework interest is not customer qualification.
- PRIORITY: HIGH

## Source 4

- SOURCE: Official observability and evaluation projects
- URL: https://github.com/langfuse/langfuse; https://github.com/braintrustdata/braintrust-sdk-python
- TYPE: OSS observability/evals source
- WHY_USEFUL: Finds builders already measuring traces, failures, evaluations, and token economics.
- WHAT_TO_SEARCH: agent traces, eval gaps, failure modes, cost, quality, debugging, production reliability.
- SIGNALS_OF_FIT: Public evidence of real agent monitoring or evaluation work and a reachable technical team.
- CONTACT_PATHS: Public issues/discussions, community pages, contributor profiles.
- LIMITATIONS: Observability practitioners may be partners or competitors rather than ASD users.
- PRIORITY: HIGH

## Source 5

- SOURCE: CrewAI community
- URL: https://community.crewai.com/about
- TYPE: Public project community
- WHY_USEFUL: Concentrated community of people building multi-agent workflows and tools.
- WHAT_TO_SEARCH: loops, repeated calls, stuck agents, retries, orchestration, debugging, production.
- SIGNALS_OF_FIT: Named builders with public projects and concrete execution problems.
- CONTACT_PATHS: Public community discussions and linked public profiles.
- LIMITATIONS: Self-reported discussion; usernames require identity verification elsewhere.
- PRIORITY: HIGH

## Source 6

- SOURCE: Reddit agent communities
- URL: https://www.reddit.com/r/LocalLLaMA/; https://www.reddit.com/r/LangChain/; https://www.reddit.com/r/AI_Agents/
- TYPE: Public discussion communities
- WHY_USEFUL: Surfaces recurring operator pain before it becomes a formal issue or product request.
- WHAT_TO_SEARCH: stuck agent, infinite loop, repeated tool calls, retry, orchestration, observability, token cost.
- SIGNALS_OF_FIT: Detailed reproducible pain plus a linked public project or profile.
- CONTACT_PATHS: Public thread replies only after identity and relevance are verified.
- LIMITATIONS: Anonymous handles are not targets; anecdotes are weak evidence and can be noisy.
- PRIORITY: MEDIUM

## Source 7

- SOURCE: Hacker News AI agent discussions
- URL: https://hn.algolia.com/?q=AI%20agents
- TYPE: Public technical discussion index
- WHY_USEFUL: Reaches founders and builders discussing reliability, workflow execution, and infrastructure trade-offs.
- WHAT_TO_SEARCH: Show HN agent, durable execution, tool calling, workflow reliability, observability, cost.
- SIGNALS_OF_FIT: Technical launch with a public repository or company page and an attributable maker.
- CONTACT_PATHS: Public HN profile, linked GitHub, project page.
- LIMITATIONS: HN comments are contextual leads, not validated pain; no target counted without identity evidence.
- PRIORITY: MEDIUM

## Source 8

- SOURCE: Product Hunt AI workflow and infrastructure pages
- URL: https://www.producthunt.com/categories/ai-workflow-automation/all
- TYPE: Public product discovery page
- WHY_USEFUL: Finds current products whose teams run agent workflows, automation, and observability.
- WHAT_TO_SEARCH: AI agents, coding agents, workflow automation, agent monitoring, reliability, self-hosted.
- SIGNALS_OF_FIT: Recent launch, technical maker, public GitHub/company page, concrete multi-step execution.
- CONTACT_PATHS: Public maker profile, launch discussion, linked website or repository.
- LIMITATIONS: Launch copy and reviews are marketing-weighted; no target counted without attribution and fit evidence.
- PRIORITY: MEDIUM

## Source 9

- SOURCE: Official technical documentation and team pages
- URL: https://www.langchain.com/about; https://pydantic.dev/about; https://langfuse.com/about; https://mastra.ai/about
- TYPE: Public company/project page
- WHY_USEFUL: Verifies roles, project ownership, technical focus, and public contact routes.
- WHAT_TO_SEARCH: founders, maintainers, production agents, evaluation, observability, communities.
- SIGNALS_OF_FIT: Named technical decision-makers connected to active public projects.
- CONTACT_PATHS: Linked GitHub, public community, official contact page; no guessed personal addresses.
- LIMITATIONS: Marketing pages prove identity and positioning, not operational pain.
- PRIORITY: HIGH

## Source 10

- SOURCE: Public reliability-oriented demos and talks
- URL: https://news.ycombinator.com/item?id=48192383; https://news.ycombinator.com/item?id=41984257
- TYPE: Public demo/discussion
- WHY_USEFUL: Provides concrete language around guardrails, durable execution, recovery, and failure compounding.
- WHAT_TO_SEARCH: retry recovery, step enforcement, durable state, stuck workflows, cost of failure.
- SIGNALS_OF_FIT: Attributable builder plus public code and a directly described reliability problem.
- CONTACT_PATHS: Linked repository, HN profile, public project page.
- LIMITATIONS: One launch is a lead, not a representative market sample; avoid inferring willingness to pay.
- PRIORITY: MEDIUM
