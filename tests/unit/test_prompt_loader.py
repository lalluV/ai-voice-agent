from app.prompts.loader import PromptLoader


def test_build_system_instruction_includes_hospital() -> None:
    loader = PromptLoader()
    text = loader.build_system_instruction(
        "v1", hospital_name="Sri Chakra", hospital_blurb="Multispecialty hospital"
    )
    assert "Sri Chakra" in text
    assert "Multispecialty hospital" in text
    assert "Telugu" in text
    assert "patientSearch" in text


def test_prompt_cache_reload() -> None:
    loader = PromptLoader()
    a = loader.load("v1", "language_policy.md")
    b = loader.load("v1", "language_policy.md")
    assert a == b
    assert "Tenglish" in a
