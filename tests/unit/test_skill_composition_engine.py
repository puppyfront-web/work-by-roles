import pytest
from work_by_roles.core.skill_composition_engine import SkillCompositionEngine
from work_by_roles.core.models import Skill

def test_validate_composition():
    s1 = Skill(id="s1", name="S1", description="D", category="C")
    s2 = Skill(id="s2", name="S2", description="D", category="C")
    library = {"s1": s1, "s2": s2}
    
    engine = SkillCompositionEngine(library)
    res = engine.validate_composition(["s1", "s2"])
    assert res.is_valid
    
    res2 = engine.validate_composition(["s1", "nonexistent"])
    assert not res2.is_valid
    assert "nonexistent" in res2.errors[0]

def test_create_compound_skill():
    s1 = Skill(id="s1", name="S1", description="D1", category="C", tools=["t1"], constraints=["c1"])
    s2 = Skill(id="s2", name="S2", description="D2", category="C", tools=["t2"], constraints=["c2"])
    library = {"s1": s1, "s2": s2}
    
    engine = SkillCompositionEngine(library)
    compound = engine.create_compound_skill(["s1", "s2"], "Combined", "New Description")
    
    assert compound.name == "Combined"
    assert "t1" in compound.tools
    assert "t2" in compound.tools
    assert len(compound.dependencies) == 2
    assert compound.metadata["is_compound"]
