from pathlib import Path

from work_by_roles.core.config_loader import ConfigLoader


def test_standard_delivery_learning_module_loads():
    root = Path(__file__).resolve().parents[3]
    skills_dir = root / "teams" / "standard-delivery" / "skills"
    roles_file = root / "teams" / "standard-delivery" / "role_schema.yaml"
    workflow_file = root / "teams" / "standard-delivery" / "workflow_schema.yaml"

    loader = ConfigLoader(root)
    skill_data, roles_data, workflow_data, _ = loader.load_all(
        skill_file=skills_dir,
        roles_file=roles_file,
        workflow_file=workflow_file
    )

    skill_ids = {skill["id"] for skill in skill_data["skills"]}
    assert "knowledge_distillation" in skill_ids

    role_ids = {role["id"] for role in roles_data["roles"]}
    assert "knowledge_curator" in role_ids

    stage_ids = {stage["id"] for stage in workflow_data["workflow"]["stages"]}
    assert "learning" in stage_ids

    # Verify Knowledge Curator instructions reflect the new skill evolution focus
    curator = next(r for r in roles_data["roles"] if r["id"] == "knowledge_curator")
    assert "evolve specific Team Skills" in curator["description"]
    assert "deduplicate_knowledge" in curator["constraints"]["allowed_actions"]
