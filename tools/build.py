"""Run tests, build the background helper, and package the Windows app."""

import hashlib
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(*command, env=None):
    print("\n> " + " ".join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), cwd=ROOT, env=env, check=True)


def main():
    if sys.platform != "win32":
        raise SystemExit("Build this application on Windows.")
    if shutil.which("dotnet") is None:
        raise SystemExit("A .NET SDK is required to build injector/.")

    run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v")
    env = os.environ.copy()
    env["DOTNET_CLI_HOME"] = str(ROOT / ".dotnet-home")
    env["NUGET_PACKAGES"] = str(ROOT / ".nuget" / "packages")
    run("dotnet", "build", "injector/TerrariaAutoFisher.Injector.csproj",
        "--configuration", "Release", "--nologo", env=env)
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "TerrariaAutoFisher.spec")

    version = runpy.run_path(str(ROOT / "autofisher" / "__init__.py"))["__version__"]
    executable = ROOT / "dist" / f"TerrariaAutoFisher-v{version}.exe"
    with executable.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    checksum = executable.with_suffix(".exe.sha256")
    checksum.write_text(f"{digest}  {executable.name}\n", encoding="ascii")
    print(f"\nBuilt: {executable}\nSHA-256: {digest}", flush=True)


if __name__ == "__main__":
    main()
