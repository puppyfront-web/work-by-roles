import pytest
from work_by_roles.core.skill_version_manager import SkillVersionManager
from work_by_roles.core.models import Skill, SkillDependency

def test_version_compatibility():
    skill = Skill(id="s1", name="S1", description="D", category="C", version="1.2.3")
    library = {"s1": skill}
    manager = SkillVersionManager(library)
    
    # Matching version
    res = manager.check_compatibility("s1", "1.2.3")
    assert res.compatible
    
    # Caret compatible
    res = manager.check_compatibility("s1", "^1.0.0")
    assert res.compatible
    
    # Incompatible major
    res = manager.check_compatibility("s1", "^2.0.0")
    assert not res.compatible
    
    # Greater than
    res = manager.check_compatibility("s1", ">=1.0.0")
    assert res.compatible

def test_resolve_dependencies():
    s1 = Skill(id="s1", name="S1", description="D", category="C", version="1.0.0",
               dependencies=[SkillDependency(skill_id="s2")])
    s2 = Skill(id="s2", name="S2", description="D", category="C", version="2.1.0")
    
    library = {"s1": s1, "s2": s2}
    manager = SkillVersionManager(library)
    
    resolved = manager.resolve_dependencies(["s1"])
    assert "s1" in resolved
    assert "s2" in resolved
    assert resolved["s1"] == "1.0.0"
    assert resolved["s2"] == "2.1.0"

def test_upgrade_skill():
    s1 = Skill(id="s1", name="S1", description="D", category="C", version="1.0.0", changelog=["Initial"])
    library = {"s1": s1}
    manager = SkillVersionManager(library)
    
    # Normal upgrade
    res = manager.upgrade_skill("s1", "1.1.0")
    assert res.success
    assert not res.breaking_changes
    
    # Breaking upgrade
    res = manager.upgrade_skill("s1", "2.0.0")
    assert res.success
    assert res.breaking_changes
    
    # Invalid upgrade
    res = manager.upgrade_skill("s1", "0.9.0")
    assert not res.success
