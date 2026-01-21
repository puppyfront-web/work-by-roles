import pytest
from unittest.mock import MagicMock
from pathlib import Path
from work_by_roles.core.sop_importer import SOPImporter, SOPAnalysis

def test_sop_analysis_to_dict():
    analysis = SOPAnalysis(
        document_type="process",
        industry="agile",
        roles=[{"id": "dev"}]
    )
    data = analysis.to_dict()
    assert data["document_type"] == "process"
    assert data["industry"] == "agile"
    assert data["roles"][0]["id"] == "dev"

def test_infer_industry():
    importer = SOPImporter()
    
    agile_sop = "This is a sprint process for scrum teams."
    assert importer._infer_industry(agile_sop) == "agile"
    
    devops_sop = "The pipeline deploys to kubernetes."
    assert importer._infer_industry(devops_sop) == "devops"

def test_infer_document_type():
    importer = SOPImporter()
    
    sop = "这是操作规程说明。"
    assert importer._infer_document_type(sop) == "procedure"
    
    sop2 = "开发流程定义。"
    assert importer._infer_document_type(sop2) == "process"

def test_generate_team_from_analysis():
    importer = SOPImporter()
    analysis = SOPAnalysis(
        document_type="process",
        roles=[{"id": "dev", "name": "Developer"}],
        workflow_stages=[{"id": "impl", "name": "Implementation", "role": "dev"}]
    )
    
    config = importer.generate_team_from_analysis(analysis)
    assert config["team_id"] == "sop_generated_team"
    assert len(config["role_schema"]["roles"]) == 1
    assert len(config["workflow_schema"]["workflow"]["stages"]) == 1
    assert config["workflow_schema"]["workflow"]["stages"][0]["role"] == "dev"
