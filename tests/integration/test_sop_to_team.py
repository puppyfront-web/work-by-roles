import pytest
from pathlib import Path
from work_by_roles.core.sop_importer import SOPImporter
from work_by_roles.core.team_template_library import TeamTemplateLibrary

def test_sop_to_team_integration(tmp_path):
    # Setup template library
    library = TeamTemplateLibrary()
    importer = SOPImporter(template_library=library)
    
    # Create dummy SOP file with clear agile keywords
    sop_file = tmp_path / "test_sop.md"
    sop_file.write_text("""
# Sprint Development Process
This is a scrum agile process for agile teams.

## Roles
- Scrum Master: Facilitates the sprint and scrum process.
- Developer: Writes code and tests in each sprint.

## Workflow
1. Sprint Planning: Define backlog tasks.
2. Development: Implement backlog features.
3. Review: Demo to stakeholders at end of sprint.
""", encoding='utf-8')
    
    # Import and auto-match
    config, analysis = importer.import_sop_enhanced(sop_file, auto_match_template=True)
    
    # Verify results
    assert analysis.industry == "agile"
    assert "agile_scrum" in analysis.warnings[0] # Should have matched template
    
    assert config["team_name"] == "SOP Generated Team"
    assert len(config["role_schema"]["roles"]) >= 2
    assert "workflow_schema" in config
    assert len(config["workflow_schema"]["workflow"]["stages"]) >= 3
