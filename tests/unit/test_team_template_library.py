import pytest
from work_by_roles.core.team_template_library import TeamTemplateLibrary, TeamTemplate

def test_builtin_templates():
    library = TeamTemplateLibrary()
    templates = library.list_all()
    assert len(templates) >= 4
    
    ids = [t.id for t in templates]
    assert "agile_scrum" in ids
    assert "devops_pipeline" in ids
    assert "startup_mvp" in ids

def test_search_templates():
    library = TeamTemplateLibrary()
    
    # Search by name
    results = library.search("敏捷")
    assert len(results) > 0
    assert results[0].id == "agile_scrum"
    
    # Search by industry
    results = library.list_by_industry("devops")
    assert len(results) > 0
    assert results[0].id == "devops_pipeline"

def test_match_sop_keywords():
    library = TeamTemplateLibrary()
    sop_content = "We need a sprint-based iteration process with a backlog."
    
    matches = library.match_sop_keywords(sop_content)
    assert len(matches) > 0
    assert matches[0].industry == "agile"

def test_generate_team_config():
    library = TeamTemplateLibrary()
    template = library.get_by_id("startup_mvp")
    
    config = library.generate_team_config(template)
    assert config["team_id"] == "startup_mvp"
    assert "role_schema" in config
    assert "workflow_schema" in config
    assert len(config["role_schema"]["roles"]) == len(template.roles)
