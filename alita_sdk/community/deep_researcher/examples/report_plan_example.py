import asyncio
from deep_researcher.agents.planner_agent import planner_agent, ReportPlan
from agents import gen_trace_id, trace
from deep_researcher import ResearchRunner


async def run_report_planner(query):
    trace_id = gen_trace_id()

    with trace("Deep Research trace", trace_id=trace_id):
        print(f"View trace: https://platform.openai.com/traces/{trace_id}")
        result = await ResearchRunner.run(planner_agent, query)
        plan = result.final_output_as(ReportPlan)
        return plan


user_query = "Provide a detailed overview of the company Quantera (quantera.io) from an investor's perspective"

plan = asyncio.run(run_report_planner(user_query))

print(f"BACKGROUND CONTEXT:\n{plan.background_context if plan.background_context else 'No background context'}")

print("\nREPORT OUTLINE:\n")
for section in plan.report_outline:
    print(f"Section: {section.title}")
    print(f"Key question: {section.key_question}\n")
    