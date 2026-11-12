from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FORBIDDEN_NAMES = ("PAYPAL_CLIENT_SECRET", "AI_API_KEY", "DATABASE_URL", "SESSION_SECRET")


def test_env_example_values_are_empty() -> None:
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        _key, value = stripped.split("=", 1)
        assert value.strip() == ""


def test_web_source_does_not_name_server_secrets() -> None:
    web_root = ROOT / "apps" / "web"
    offenders: list[str] = []
    for path in web_root.rglob("*"):
        if not path.is_file():
            continue
        if "node_modules" in path.parts or ".next" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name in FORBIDDEN_NAMES:
            if name in text:
                offenders.append(f"{path.relative_to(ROOT)}:{name}")
    assert offenders == []
