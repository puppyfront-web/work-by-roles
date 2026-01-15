"""
Skill benchmark for evaluating skill performance.
Following Single Responsibility Principle - handles skill benchmarking only.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import time

from .models import Skill, SkillExecution
from .execution_tracker import ExecutionTracker
from .workflow_engine import WorkflowEngine
from .agent_orchestrator import AgentOrchestrator

class SkillBenchmark:
    """Benchmark system for evaluating skill performance"""
    
    def __init__(self, engine: 'WorkflowEngine', orchestrator: Optional[AgentOrchestrator] = None):
        self.engine = engine
        self.orchestrator = orchestrator or AgentOrchestrator(engine)
    
    def benchmark_skill(
        self,
        skill_id: str,
        test_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Benchmark a single skill with test cases"""
        if not self.engine.role_manager.skill_library:
            raise WorkflowError("Skill library not loaded")
        
        skill = self.engine.role_manager.skill_library.get(skill_id)
        if not skill:
            raise WorkflowError(f"Skill '{skill_id}' not found")
        
        results = []
        total_time = 0.0
        successes = 0
        
        for test_case in test_cases:
            test_name = test_case.get('name', 'unnamed_test')
            input_data = test_case.get('input', {})
            expected_output = test_case.get('expected_output', {})
            
            start_time = time.time()
            try:
                result = self.orchestrator.execute_skill(skill_id, input_data)
                execution_time = time.time() - start_time
                total_time += execution_time
                
                success = result.get('success', False)
                if success:
                    successes += 1
                
                # Validate output if expected_output provided
                output_valid = True
                if expected_output and result.get('output'):
                    output_valid = self._validate_output(result['output'], expected_output)
                
                results.append({
                    "test_name": test_name,
                    "success": success and output_valid,
                    "execution_time": execution_time,
                    "result": result,
                    "output_valid": output_valid
                })
            except Exception as e:
                execution_time = time.time() - start_time
                total_time += execution_time
                results.append({
                    "test_name": test_name,
                    "success": False,
                    "execution_time": execution_time,
                    "error": str(e)
                })
        
        return {
            "skill_id": skill_id,
            "total_tests": len(test_cases),
            "successful_tests": successes,
            "success_rate": successes / len(test_cases) if test_cases else 0.0,
            "avg_execution_time": total_time / len(test_cases) if test_cases else 0.0,
            "total_execution_time": total_time,
            "results": results
        }
    
    def benchmark_skill_pair(
        self,
        skill_a_id: str,
        skill_b_id: str,
        test_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Benchmark two skills in sequence (e.g., generate -> review)"""
        results_a = self.benchmark_skill(skill_a_id, test_cases)
        results_b = self.benchmark_skill(skill_b_id, test_cases)
        
        # Check if skills complement each other
        complementary = True
        if results_a['success_rate'] > 0.8 and results_b['success_rate'] > 0.8:
            # Both skills perform well individually
            complementary = True
        
        return {
            "skill_a": results_a,
            "skill_b": results_b,
            "complementary": complementary,
            "combined_success_rate": (results_a['success_rate'] + results_b['success_rate']) / 2
        }
    
    def compare_skills(
        self,
        skill_ids: List[str],
        test_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compare multiple skills on the same test cases"""
        comparisons = {}
        
        for skill_id in skill_ids:
            comparisons[skill_id] = self.benchmark_skill(skill_id, test_cases)
        
        # Rank skills by success rate
        ranked = sorted(
            comparisons.items(),
            key=lambda x: x[1]['success_rate'],
            reverse=True
        )
        
        return {
            "comparisons": comparisons,
            "ranked": [{"skill_id": skill_id, **stats} for skill_id, stats in ranked],
            "best_skill": ranked[0][0] if ranked else None
        }
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """Generate a human-readable benchmark report"""
        lines = []
        lines.append("=" * 60)
        lines.append("Skill Benchmark Report")
        lines.append("=" * 60)
        lines.append("")
        
        if 'skill_id' in results:
            # Single skill benchmark
            lines.append(f"Skill: {results['skill_id']}")
            lines.append(f"Total Tests: {results['total_tests']}")
            lines.append(f"Successful: {results['successful_tests']}")
            lines.append(f"Success Rate: {results['success_rate']:.2%}")
            lines.append(f"Avg Execution Time: {results['avg_execution_time']:.2f}s")
            lines.append("")
            lines.append("Test Results:")
            for result in results['results']:
                status = "✅" if result['success'] else "❌"
                lines.append(f"  {status} {result['test_name']}: {result.get('execution_time', 0):.2f}s")
        
        elif 'comparisons' in results:
            # Comparison report
            lines.append("Skill Comparison")
            lines.append("")
            for skill_id, stats in results['comparisons'].items():
                lines.append(f"{skill_id}:")
                lines.append(f"  Success Rate: {stats['success_rate']:.2%}")
                lines.append(f"  Avg Time: {stats['avg_execution_time']:.2f}s")
                lines.append("")
            lines.append(f"Best Skill: {results['best_skill']}")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def _validate_output(self, actual: Dict[str, Any], expected: Dict[str, Any]) -> bool:
        """Validate actual output against expected output"""
        for key, expected_value in expected.items():
            if key not in actual:
                return False
            # Simple equality check - could be enhanced with schema validation
            if actual[key] != expected_value:
                return False
        return True
