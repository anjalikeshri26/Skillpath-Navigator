from app.domain.skills import load_taxonomy

tax = load_taxonomy()


def found(text):
    return set(tax.find_skills(text))


def test_substring_collisions_do_not_match():
    assert "sql" not in found("Worked with digital marketing and a mythical creature")
    assert "java" not in found("Built UIs in JavaScript")
    assert "git" not in found("Improved digital signatures")


def test_c_family_languages_are_distinguished():
    assert found("Languages: C, C++") >= {"c_lang", "cpp"}
    assert "c_lang" not in found("Wrote C++ and C# services")
    assert "c_lang" not in found("Rich in vitamin c")


def test_vendor_names_map_to_skill():
    assert "sql" in found("Designed a PostgreSQL schema")
    assert "web_frameworks" in found("Backend in Flask")


def test_every_role_references_known_skills():
    for role, weights in tax.roles.items():
        assert set(weights) <= set(tax.skills), role


def test_prerequisite_graph_has_no_cycles():
    state = {}

    def visit(sid):
        if state.get(sid) == "done":
            return
        assert state.get(sid) != "open", f"cycle through {sid}"
        state[sid] = "open"
        for pre in tax.skills[sid].prerequisites:
            visit(pre)
        state[sid] = "done"

    for sid in tax.skills:
        visit(sid)
