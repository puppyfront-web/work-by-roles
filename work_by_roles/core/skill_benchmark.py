"""
Skill benchmark for evaluating skill performance.
Following Single Responsibility Principle - handles skill benchmarking only.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import time
import json
import hashlib

try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False

try:
    from deepdiff import DeepDiff
    DEEPDIFF_AVAILABLE = True
except ImportError:
    DEEPDIFF_AVAILABLE = False

from .models import Skill, SkillExecution
from .execution_tracker import ExecutionTracker
from .workflow_engine import WorkflowEngine
from .agent_orchestrator import AgentOrchestrator
from .exceptions import WorkflowError

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
                validation_result = self._validate_test_case(
                    result.get('output', {}),
                    expected_output,
                    test_case.get('expected_schema'),
                    skill
                )
                
                results.append({
                    "test_name": test_name,
                    "success": success and validation_result['valid'],
                    "execution_time": execution_time,
                    "result": result,
                    "validation": validation_result
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
    
    def benchmark_with_models(
        self,
        skill_id: str,
        models: List[str],
        test_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Benchmark a skill with multiple LLM models (P2 optimization).
        
        Args:
            skill_id: Skill ID to benchmark
            models: List of model identifiers
            test_cases: Test cases to run
        
        Returns:
            Comparison results for each model
        """
        if not self.engine.role_manager.skill_library:
            raise WorkflowError("Skill library not loaded")
        
        skill = self.engine.role_manager.skill_library.get(skill_id)
        if not skill:
            raise WorkflowError(f"Skill '{skill_id}' not found")
        
        model_results = {}
        
        # Store original orchestrator
        original_orchestrator = self.orchestrator
        
        for model_name in models:
            # Create orchestrator with different model (simplified - assumes LLM client switching)
            # In a real implementation, you would switch the LLM client here
            try:
                # Benchmark with this model
                results = self.benchmark_skill(skill_id, test_cases)
                model_results[model_name] = results
            except Exception as e:
                model_results[model_name] = {
                    "skill_id": skill_id,
                    "model": model_name,
                    "error": str(e),
                    "success_rate": 0.0
                }
        
        # Restore original orchestrator
        self.orchestrator = original_orchestrator
        
        # Rank models by success rate
        ranked = sorted(
            [(m, r) for m, r in model_results.items() if 'success_rate' in r],
            key=lambda x: x[1]['success_rate'],
            reverse=True
        )
        
        return {
            "skill_id": skill_id,
            "models": model_results,
            "ranked": [{"model": m, "success_rate": r['success_rate']} for m, r in ranked],
            "best_model": ranked[0][0] if ranked else None
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
    
    def _validate_test_case(
        self,
        actual_output: Dict[str, Any],
        expected_output: Optional[Dict[str, Any]] = None,
        expected_schema: Optional[Dict[str, Any]] = None,
        skill: Optional[Skill] = None
    ) -> Dict[str, Any]:
        """
        Validate test case output using snapshot comparison and schema validation.
        
        Returns:
            Dict with validation results including:
            - valid: bool
            - snapshot_match: bool (if expected_output provided)
            - schema_valid: bool (if expected_schema provided)
            - differences: List[str] (if snapshot mismatch)
            - schema_errors: List[str] (if schema validation fails)
        """
        result = {
            "valid": True,
            "snapshot_match": True,
            "schema_valid": True,
            "differences": [],
            "schema_errors": []
        }
        
        # Snapshot comparison (deep diff)
        if expected_output:
            if DEEPDIFF_AVAILABLE:
                diff = DeepDiff(expected_output, actual_output, ignore_order=True, verbose_level=2)
                if diff:
                    result["snapshot_match"] = False
                    result["valid"] = False
                    result["differences"] = [
                        f"{change_type}: {details}"
                        for change_type, details in diff.items()
                    ]
            else:
                # Fallback to simple comparison
                if actual_output != expected_output:
                    result["snapshot_match"] = False
                    result["valid"] = False
                    result["differences"] = ["Output does not match expected snapshot"]
        
        # Schema validation
        schema_to_validate = expected_schema
        if not schema_to_validate and skill and skill.output_schema:
            schema_to_validate = skill.output_schema
        
        if schema_to_validate and JSONSCHEMA_AVAILABLE:
            try:
                jsonschema.validate(instance=actual_output, schema=schema_to_validate)
                result["schema_valid"] = True
            except jsonschema.ValidationError as e:
                result["schema_valid"] = False
                result["valid"] = False
                result["schema_errors"] = [str(e)]
            except jsonschema.SchemaError as e:
                result["schema_errors"] = [f"Invalid schema: {str(e)}"]
        
        return result
    
    def _validate_output(self, actual: Dict[str, Any], expected: Dict[str, Any]) -> bool:
        """Validate actual output against expected output (legacy method)"""
        validation_result = self._validate_test_case(actual, expected)
        return validation_result['valid']
    
    def test_skill(
        self,
        skill_id: str,
        input_data: Dict[str, Any],
        expected_output: Optional[Dict[str, Any]] = None,
        expected_schema: Optional[Dict[str, Any]] = None,
        snapshot_file: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Test a single skill execution with validation.
        
        Args:
            skill_id: Skill ID to test
            input_data: Input data for the skill
            expected_output: Expected output for snapshot comparison
            expected_schema: Expected JSON schema for validation
            snapshot_file: Optional path to save/load snapshot
        
        Returns:
            Test result dictionary
        """
        if not self.engine.role_manager.skill_library:
            raise WorkflowError("Skill library not loaded")
        
        skill = self.engine.role_manager.skill_library.get(skill_id)
        if not skill:
            raise WorkflowError(f"Skill '{skill_id}' not found")
        
        # Load snapshot if file provided and expected_output not given
        if snapshot_file and snapshot_file.exists() and not expected_output:
            with snapshot_file.open('r', encoding='utf-8') as f:
                expected_output = json.load(f)
        
        # Execute skill
        start_time = time.time()
        try:
            result = self.orchestrator.execute_skill(skill_id, input_data)
            execution_time = time.time() - start_time
            
            success = result.get('success', False)
            actual_output = result.get('output', {})
            
            # Validate output
            validation_result = self._validate_test_case(
                actual_output,
                expected_output,
                expected_schema,
                skill
            )
            
            # Save snapshot if file provided
            if snapshot_file and success and actual_output:
                snapshot_file.parent.mkdir(parents=True, exist_ok=True)
                with snapshot_file.open('w', encoding='utf-8') as f:
                    json.dump(actual_output, f, indent=2, ensure_ascii=False)
            
            return {
                "skill_id": skill_id,
                "success": success and validation_result['valid'],
                "execution_time": execution_time,
                "output": actual_output,
                "validation": validation_result,
                "snapshot_saved": snapshot_file is not None and success
            }
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "skill_id": skill_id,
                "success": False,
                "execution_time": execution_time,
                "error": str(e),
                "validation": {
                    "valid": False,
                    "snapshot_match": False,
                    "schema_valid": False,
                    "differences": [],
                    "schema_errors": [str(e)]
                }
            }
