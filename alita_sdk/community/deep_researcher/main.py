import asyncio
import argparse
from .iterative_research import IterativeResearcher
from .deep_research import DeepResearcher
from typing import Literal
from dotenv import load_dotenv

load_dotenv(override=True)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Deep Research Assistant")
    parser.add_argument("--query", type=str, help="Research query")
    parser.add_argument("--model", type=str, choices=["deep", "simple"], 
                        help="Mode of research (deep or simple)", default="deep")
    parser.add_argument("--max-iterations", type=int, default=5,
                       help="Maximum number of iterations for deep research")
    parser.add_argument("--max-time", type=int, default=10,
                       help="Maximum time in minutes for deep research")
    parser.add_argument("--output-length", type=str, default="5 pages",
                       help="Desired output length for the report")
    parser.add_argument("--output-instructions", type=str, default="",
                       help="Additional instructions for the report")
    parser.add_argument("--verbose", action="store_true",
                       help="Print status updates to the console")
    parser.add_argument("--tracing", action="store_true",
                       help="Enable tracing for the research (only valid for OpenAI models)")
    
    args = parser.parse_args()
    
    # If no query is provided via command line, prompt the user
    query = args.query if args.query else input("What would you like to research? ")
    
    print(f"Starting deep research on: {query}")
    print(f"Max iterations: {args.max_iterations}, Max time: {args.max_time} minutes")
    
    if args.model == "deep":
        manager = DeepResearcher(
            max_iterations=args.max_iterations,
            max_time_minutes=args.max_time,
            verbose=args.verbose,
            tracing=args.tracing
        )
        report = await manager.run(query)
    else:
        manager = IterativeResearcher(
            max_iterations=args.max_iterations,
            max_time_minutes=args.max_time,
            verbose=args.verbose,
            tracing=args.tracing
        )
        report = await manager.run(
            query, 
            output_length=args.output_length, 
            output_instructions=args.output_instructions
        )

    print("\n=== Final Report ===")
    print(report)

# Command line entry point
def cli_entry():
    """Entry point for the command-line interface."""
    asyncio.run(main())

if __name__ == "__main__":
    cli_entry()
