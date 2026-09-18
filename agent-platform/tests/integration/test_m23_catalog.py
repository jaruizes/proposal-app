from agent_platform.bootstrap import load_bootstrap_catalog
from agent_platform.full_test import EXPECTED_AGENTS, EXPECTED_SKILLS


def test_m23_expected_catalog_matches_git_bootstrap():
    skills, agents = load_bootstrap_catalog()
    assert {item.key for item in skills} == EXPECTED_SKILLS
    assert {item.key for item in agents} == EXPECTED_AGENTS
    skill_keys = {item.key for item in skills}
    for agent in agents:
        assert set(agent.skills) <= skill_keys
