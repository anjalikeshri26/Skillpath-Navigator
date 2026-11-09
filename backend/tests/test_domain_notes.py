from app.domain import notes_text as nt


def test_titles_are_compared_case_and_space_insensitively():
    assert nt.title_key("  Binary   Trees ") == nt.title_key("binary trees")
    assert nt.clean_title("a\n\tb") == "a b"


def test_excerpt_is_plain_text_and_cut_on_a_word():
    body = "# Heading\n\n**Bold** text with a [link](https://example.com) and `code`.\n```py\nprint(1)\n```\n" + "word " * 100
    out = nt.excerpt(body, 60)
    assert out.endswith("\u2026") and len(out) <= 61
    assert "#" not in out and "**" not in out and "https" not in out and "print" not in out


def test_short_excerpt_is_not_truncated():
    assert nt.excerpt("## Hi there", 160) == "Hi there"


def test_like_wildcards_are_escaped():
    assert nt.escape_like("50%_off\\") == "50\\%\\_off\\\\"


def test_whole_answer_fence_is_removed_but_inner_code_blocks_survive():
    wrapped = "```markdown\n# T\n\n```py\nx = 1\n```\n\ntext\n```"
    assert nt.unwrap_markdown(wrapped) == "# T\n\n```py\nx = 1\n```\n\ntext"
    plain = "# T\n\n```py\nx = 1\n```"
    assert nt.unwrap_markdown(plain) == plain


def test_study_markdown_gets_a_title_and_collapsed_blank_lines():
    out = nt.normalise_study_markdown("Intro\n\n\n\n\nMore", "Operating  Systems")
    assert out.startswith("# Operating Systems\n\n") and "\n\n\n" not in out
    assert nt.normalise_study_markdown("# Mine\n\ntext", "x").startswith("# Mine")


def test_suggested_title_is_bounded():
    assert nt.suggest_title("A" * 500).__len__() == nt.MAX_TITLE
    assert nt.suggest_title("  SQL  joins ") == "SQL joins: study notes"


def test_every_depth_has_room_for_its_word_target():
    assert nt.DEPTHS["In-depth"].max_tokens > nt.DEPTHS["Standard"].max_tokens > nt.DEPTHS["Quick revision"].max_tokens
