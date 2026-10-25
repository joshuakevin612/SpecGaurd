"""Package the AI implementation and demo evidence, explicitly excluding secrets."""

from zipfile import ZIP_DEFLATED, ZipFile

from dotenv import dotenv_values

from .provider import ROOT


def build_archive():
    output = ROOT / "artifacts" / "specguard-person-a-handoff.zip"
    output.parent.mkdir(exist_ok=True)
    files = [ROOT / name for name in ("README.md", "pyproject.toml", ".env.example", ".gitignore")]
    for name in ("shared", "specguard_ai", "tests", "configs", "docs", "demos"):
        files.extend(path for path in (ROOT / name).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts
                     and path.suffix not in {".pyc", ".pyo"})
    for name in ("mock-nemo-check.json", "nvidia-nemo-check.json", "nvidia-repair-demo.json"):
        path = ROOT / "artifacts" / name
        if path.exists():
            files.append(path)
    bundle_root = ROOT / "artifacts" / "bundles"
    if bundle_root.exists():
        files.extend(path for path in bundle_root.rglob("*") if path.is_file()
                     and path.name != "rejected_test.json" and "__pycache__" not in path.parts)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            relative = path.relative_to(ROOT)
            if path.name == ".env" or ".venv" in relative.parts:
                raise ValueError("Secret/environment files must not be packaged")
            archive.write(path, relative.as_posix())
    contains_secret = False
    with ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("Archive integrity check failed")
        secrets = [value for name, value in dotenv_values(ROOT / ".env").items()
                   if name.endswith("API_KEY") and value]
        for name in archive.namelist():
            contents = archive.read(name)
            if any(secret.encode() in contents for secret in secrets):
                contains_secret = True
                break
        print(f"Handoff archive: {output} ({len(archive.namelist())} files)")
    if contains_secret:
        output.unlink()
        raise ValueError("Handoff contained a credential; archive removed")
    return output


if __name__ == "__main__":
    build_archive()
