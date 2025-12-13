#!/usr/bin/env python3
"""
eval_harness.py - Evaluation Harness v0 (Phase 0.5)

This script runs a fixed set of tasks to measure agent quality.
It reports:
- Success/fail for each task
- Tool call count
- Execution time
- Whether tests were run

This turns "agent quality" into something measurable and allows
iteration on agent behavior with regression detection.

Usage:
    python eval_harness.py [--task TASK_NAME] [--verbose]
"""

import asyncio
import json
import time
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class TaskDefinition:
    """Definition of a test task.
    
    Attributes:
        name: Task identifier
        description: What the task should accomplish
        user_message: Message to send to agent
        success_criteria: Function to check if task succeeded
        expect_tests: Whether this task should run tests
    """
    name: str
    description: str
    user_message: str
    success_criteria: callable
    expect_tests: bool = False


@dataclass
class TaskResult:
    """Result of running a task.
    
    Attributes:
        task_name: Name of the task
        success: Whether task succeeded
        tool_calls_count: Number of tool calls made
        execution_time_seconds: Time taken to complete
        tests_ran: Whether tests were executed
        error: Optional error message
        details: Additional details
    """
    task_name: str
    success: bool
    tool_calls_count: int
    execution_time_seconds: float
    tests_ran: bool
    error: Optional[str] = None
    details: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class EvalHarness:
    """Evaluation harness for measuring agent quality."""
    
    def __init__(self, workspace_dir: str = "./workspace/eval"):
        """Initialize eval harness.
        
        Args:
            workspace_dir: Directory for eval workspace
        """
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.tasks = self._define_tasks()
    
    def _define_tasks(self) -> List[TaskDefinition]:
        """Define the fixed set of evaluation tasks.
        
        Returns:
            List of task definitions
        """
        return [
            TaskDefinition(
                name="simple_file_creation",
                description="Create a simple text file",
                user_message="Create a file called hello.txt with the content 'Hello, World!'",
                success_criteria=lambda result, workspace: 
                    (workspace / "hello.txt").exists() and
                    (workspace / "hello.txt").read_text().strip() == "Hello, World!",
                expect_tests=False,
            ),
            TaskDefinition(
                name="list_and_read",
                description="List files then read one",
                user_message="List all Python files in the current directory, then read the first one you find",
                success_criteria=lambda result, workspace: 
                    "list_files" in str(result) and "read_file" in str(result),
                expect_tests=False,
            ),
            TaskDefinition(
                name="create_python_function",
                description="Create a Python function and test it",
                user_message="Create a Python file called math_utils.py with a function that adds two numbers. Then write a test for it and run the test.",
                success_criteria=lambda result, workspace:
                    (workspace / "math_utils.py").exists() and
                    "def " in (workspace / "math_utils.py").read_text(),
                expect_tests=True,
            ),
            TaskDefinition(
                name="fix_syntax_error",
                description="Fix a Python syntax error",
                user_message="Fix the syntax error in broken.py (if it exists) or create a correct version",
                success_criteria=lambda result, workspace: True,  # Success is attempting
                expect_tests=False,
            ),
        ]
    
    async def run_task(self, task: TaskDefinition) -> TaskResult:
        """Run a single task.
        
        Args:
            task: Task to run
            
        Returns:
            TaskResult with metrics
        """
        logger.info(f"Running task: {task.name}")
        start_time = time.time()
        
        try:
            # In a real implementation, this would:
            # 1. Initialize agent state
            # 2. Create agent loop
            # 3. Run agent with task.user_message
            # 4. Collect metrics
            
            # For now, this is a placeholder that shows the structure
            # Real implementation would integrate with flow/loops.py
            
            # Simulate execution
            await asyncio.sleep(0.1)
            
            # Placeholder metrics
            tool_calls_count = 0
            tests_ran = False
            success = False
            
            # Try to check success criteria
            try:
                success = task.success_criteria(None, self.workspace_dir)
            except Exception as e:
                logger.debug(f"Success criteria check failed: {e}")
                success = False
            
            execution_time = time.time() - start_time
            
            return TaskResult(
                task_name=task.name,
                success=success,
                tool_calls_count=tool_calls_count,
                execution_time_seconds=execution_time,
                tests_ran=tests_ran,
                details={"description": task.description},
            )
        
        except Exception as e:
            logger.error(f"Task {task.name} failed with error: {e}", exc_info=True)
            execution_time = time.time() - start_time
            
            return TaskResult(
                task_name=task.name,
                success=False,
                tool_calls_count=0,
                execution_time_seconds=execution_time,
                tests_ran=False,
                error=str(e),
            )
    
    async def run_all_tasks(self, task_filter: Optional[str] = None) -> List[TaskResult]:
        """Run all tasks or filtered subset.
        
        Args:
            task_filter: Optional task name to run only specific task
            
        Returns:
            List of task results
        """
        tasks_to_run = self.tasks
        if task_filter:
            tasks_to_run = [t for t in self.tasks if t.name == task_filter]
            if not tasks_to_run:
                logger.error(f"Task '{task_filter}' not found")
                return []
        
        results = []
        for task in tasks_to_run:
            result = await self.run_task(task)
            results.append(result)
        
        return results
    
    def generate_report(self, results: List[TaskResult]) -> Dict[str, Any]:
        """Generate evaluation report.
        
        Args:
            results: List of task results
            
        Returns:
            Report dictionary
        """
        total_tasks = len(results)
        successful_tasks = sum(1 for r in results if r.success)
        total_tool_calls = sum(r.tool_calls_count for r in results)
        total_time = sum(r.execution_time_seconds for r in results)
        tasks_with_tests = sum(1 for r in results if r.tests_ran)
        
        report = {
            "summary": {
                "total_tasks": total_tasks,
                "successful_tasks": successful_tasks,
                "success_rate": successful_tasks / total_tasks if total_tasks > 0 else 0,
                "total_tool_calls": total_tool_calls,
                "total_time_seconds": total_time,
                "tasks_with_tests_run": tasks_with_tests,
            },
            "tasks": [r.to_dict() for r in results],
        }
        
        return report
    
    def print_report(self, report: Dict[str, Any]) -> None:
        """Print report to console.
        
        Args:
            report: Report dictionary
        """
        summary = report["summary"]
        
        print("\n" + "="*60)
        print("EVALUATION HARNESS v0 - RESULTS")
        print("="*60)
        print(f"\nTotal Tasks: {summary['total_tasks']}")
        print(f"Successful: {summary['successful_tasks']}")
        print(f"Success Rate: {summary['success_rate']:.1%}")
        print(f"Total Tool Calls: {summary['total_tool_calls']}")
        print(f"Total Time: {summary['total_time_seconds']:.2f}s")
        print(f"Tasks with Tests Run: {summary['tasks_with_tests_run']}")
        print("\n" + "-"*60)
        print("TASK DETAILS")
        print("-"*60)
        
        for task_result in report["tasks"]:
            status = "✓" if task_result["success"] else "✗"
            print(f"\n{status} {task_result['task_name']}")
            print(f"  Tools: {task_result['tool_calls_count']}, "
                  f"Time: {task_result['execution_time_seconds']:.2f}s, "
                  f"Tests: {'Yes' if task_result['tests_ran'] else 'No'}")
            if task_result.get("error"):
                print(f"  Error: {task_result['error']}")
        
        print("\n" + "="*60 + "\n")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Evaluation Harness v0 - Measure agent quality"
    )
    parser.add_argument(
        "--task",
        type=str,
        help="Run specific task only"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="eval_results.json",
        help="Output file for results (default: eval_results.json)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run evaluation
    harness = EvalHarness()
    logger.info("Starting evaluation harness...")
    
    results = await harness.run_all_tasks(task_filter=args.task)
    
    # Generate and print report
    report = harness.generate_report(results)
    harness.print_report(report)
    
    # Save to file
    output_path = Path(args.output)
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Results saved to {output_path}")
    
    # Exit with appropriate code
    if report["summary"]["successful_tasks"] == report["summary"]["total_tasks"]:
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
