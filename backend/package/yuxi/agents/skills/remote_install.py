from __future__ import annotations

import asyncio
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.agents.skills.service import import_skill_dir, is_valid_skill_slug

if TYPE_CHECKING:
    from yuxi.storage.postgres.models_business import Skill

ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
CONTROL_SEQUENCE_RE = re.compile(r"\x1B\][^\x07]*(?:\x07|\x1B\\)|\x1B[\(\)][A-Za-z0-9]")
CLI_TIMEOUT_SECONDS = 300


@dataclass(slots=True)
class RemoteSkillsBatchPreparation:
    temp_home: str | None
    results: list[dict]

    async def cleanup(self) -> None:
        if self.temp_home:
            await asyncio.to_thread(shutil.rmtree, self.temp_home, ignore_errors=True)


def _normalize_source(source: str) -> str:
    value = str(source or "").strip()
    if not value:
        raise ValueError("source không được để trống")
    if any(ch in value for ch in ("\n", "\r", "\x00")):
        raise ValueError("source chứa ký tự không hợp lệ")
    return value


def _normalize_skill_name(skill: str) -> str:
    value = str(skill or "").strip()
    if not is_valid_skill_slug(value):
        raise ValueError("Tên skill không hợp lệ")
    return value


def _clean_cli_output(output: str) -> list[str]:
    cleaned = ANSI_ESCAPE_RE.sub("", output or "")
    cleaned = CONTROL_SEQUENCE_RE.sub("", cleaned)
    cleaned = cleaned.replace("\r", "\n")
    normalized_lines: list[str] = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        stripped = re.sub(r"^[│┌└◇◒◐◓◑■●]+\s*", "", stripped)
        normalized_lines.append(stripped.strip())
    return normalized_lines


def _parse_available_skills(output: str) -> list[dict[str, str]]:
    lines = _clean_cli_output(output)
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    collecting = False

    for idx, line in enumerate(lines):
        if not collecting:
            if "Available Skills" in line:
                collecting = True
            continue

        if not line:
            continue
        if "Use --skill " in line:
            break
        if not is_valid_skill_slug(line):
            continue
        if line in seen:
            continue

        description = ""
        next_index = idx + 1
        while next_index < len(lines):
            next_line = lines[next_index]
            next_index += 1
            if not next_line:
                continue
            if "Use --skill " in next_line:
                break
            if is_valid_skill_slug(next_line):
                break
            if next_line and next_line[0].isalpha():
                description = next_line
            else:
                continue
            break

        seen.add(line)
        items.append({"name": line, "description": description})

    return items


async def _run_skills_cli(
    args: list[str],
    *,
    env: dict[str, str],
    cwd: str,
) -> str:
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=CLI_TIMEOUT_SECONDS)
    except TimeoutError:
        process.kill()
        await process.communicate()
        raise ValueError("skills CLI thực thi quá thời gian") from None

    output = (stdout or b"").decode("utf-8", errors="replace")
    error_output = (stderr or b"").decode("utf-8", errors="replace")
    combined = "\n".join(part for part in [output.strip(), error_output.strip()] if part)
    if process.returncode != 0:
        cleaned_lines = _clean_cli_output(combined)
        error_msg = "\n".join(line for line in cleaned_lines if line)[:500]
        raise ValueError(error_msg or "skills CLI thực thi thất bại")
    return combined


def _create_isolated_workdir() -> tuple[str, dict[str, str], str]:
    temp_home = tempfile.mkdtemp(prefix=".remote-skills-")
    env = os.environ.copy()
    env["HOME"] = temp_home
    workdir = str(Path(temp_home) / "workspace")
    Path(workdir).mkdir(parents=True, exist_ok=True)
    return temp_home, env, workdir


async def list_remote_skills(source: str) -> list[dict[str, str]]:
    normalized_source = _normalize_source(source)

    temp_home, env, workdir = _create_isolated_workdir()
    try:
        output = await _run_skills_cli(
            ["npx", "-y", "skills", "add", normalized_source, "--list"],
            env=env,
            cwd=workdir,
        )
    finally:
        await asyncio.to_thread(shutil.rmtree, temp_home, ignore_errors=True)

    skills = _parse_available_skills(output)
    if not skills:
        raise ValueError("Không tìm thấy bất kỳ skill nào có thể cài đặt")
    return skills


async def install_remote_skill(
    db: AsyncSession,
    *,
    source: str,
    skill: str,
    created_by: str | None,
) -> Skill:
    normalized_source = _normalize_source(source)
    normalized_skill = _normalize_skill_name(skill)

    temp_home, env, workdir = _create_isolated_workdir()
    try:
        available_skills = _parse_available_skills(
            await _run_skills_cli(
                ["npx", "-y", "skills", "add", normalized_source, "--list"],
                env=env,
                cwd=workdir,
            )
        )
        available_names = {item["name"] for item in available_skills}
        if normalized_skill not in available_names:
            raise ValueError(f"Skill không tồn tại trong kho lưu trữ từ xa: {normalized_skill}")

        await _run_skills_cli(
            [
                "npx",
                "-y",
                "skills",
                "add",
                normalized_source,
                "--skill",
                normalized_skill,
                "-g",
                "-y",
                "--copy",
            ],
            env=env,
            cwd=workdir,
        )

        skills_dir = Path(temp_home).resolve() / ".agents" / "skills"
        installed_dir = _find_skill_dir(skills_dir, normalized_skill)
        if installed_dir is None:
            raise ValueError("skills CLI không tạo ra thư mục skill như mong đợi")

        return await import_skill_dir(
            db,
            source_dir=installed_dir,
            created_by=created_by,
        )
    finally:
        await asyncio.to_thread(shutil.rmtree, temp_home, ignore_errors=True)


async def install_remote_skills_batch(
    db: AsyncSession,
    *,
    source: str,
    skills: list[str],
    created_by: str | None,
) -> list[dict]:
    """Batch install multiple individual skills from the same individual remote repository (only one clone).

    Args:
        db: database session.
        source: Remote warehouse source, such as ``owner/repo`` or GitHub URL。
        skills: Need to install the skill name column surface.
        created_by: operator ID.

    Returns:
        List of installation results for each skill, in the same order as requested: ``[{slug, success, error?}, ...]``
    """
    preparation = await prepare_remote_skills_batch(source=source, skills=skills)
    try:
        results = preparation.results
        for index, result in enumerate(results):
            if not result.get("success"):
                continue

            source_dir = result.get("source_dir")
            try:
                item = await import_skill_dir(
                    db,
                    source_dir=source_dir,
                    created_by=created_by,
                )
                results[index] = {"slug": item.slug, "success": True}
            except Exception as e:
                if hasattr(db, "rollback"):
                    await db.rollback()
                results[index] = {"slug": result["slug"], "success": False, "error": str(e)}

        return results
    finally:
        await preparation.cleanup()


async def prepare_remote_skills_batch(
    *,
    source: str,
    skills: list[str],
) -> RemoteSkillsBatchPreparation:
    """Pull skill directories in batches from the remote warehouse, but do not write to the database."""
    normalized_source = _normalize_source(source)
    if not skills:
        raise ValueError("Danh sách skill không được để trống")

    # Pre-allocate the result array (in request order), verify illegal names and log failures
    results: list[dict] = [{"slug": "", "success": False, "error": "unset"} for _ in range(len(skills))]
    normalized_skills: list[str] = []
    valid_indices: list[int] = []
    for i, skill in enumerate(skills):
        try:
            normalized_skills.append(_normalize_skill_name(skill))
            valid_indices.append(i)
        except ValueError as e:
            results[i] = {"slug": skill, "success": False, "error": str(e)}

    if not normalized_skills:
        return RemoteSkillsBatchPreparation(temp_home=None, results=results)

    temp_home, env, workdir = _create_isolated_workdir()
    try:
        skill_args: list[str] = []
        for name in normalized_skills:
            skill_args.extend(["--skill", name])

        cli_failed = False
        try:
            await _run_skills_cli(
                [
                    "npx",
                    "-y",
                    "skills",
                    "add",
                    normalized_source,
                    *skill_args,
                    "-g",
                    "-y",
                    "--copy",
                ],
                env=env,
                cwd=workdir,
            )
        except ValueError:
            # The CLI will exit with a non-zero code for unmatched skills, but the installed directory remains
            cli_failed = True

        skills_dir = Path(temp_home).resolve() / ".agents" / "skills"
        for original_index, name in zip(valid_indices, normalized_skills):
            installed_dir = _find_skill_dir(skills_dir, name)
            if installed_dir is None:
                error_msg = (
                    "CLI Installation failed" if cli_failed else "skills CLI Expected skills catalog not generated"
                )
                results[original_index] = {"slug": name, "success": False, "error": error_msg}
            else:
                results[original_index] = {"slug": name, "success": True, "source_dir": installed_dir}

        return RemoteSkillsBatchPreparation(temp_home=temp_home, results=results)
    except Exception:
        await asyncio.to_thread(shutil.rmtree, temp_home, ignore_errors=True)
        raise


def _find_skill_dir(skills_dir: Path, name: str) -> Path | None:
    """Find the skill subdirectory by name in the skills installation directory."""
    if not skills_dir.is_dir():
        return None
    for candidate in skills_dir.iterdir():
        if candidate.name == name and candidate.is_dir():
            return candidate
    return None


def _parse_search_skills(output: str) -> list[dict[str, str]]:
    """Parse the output of the npx skills find command."""
    lines = _clean_cli_output(output)
    results: list[dict[str, str]] = []
    # Matches the form "owner/repo@skill-name [installs]"
    # For example: vercel-labs/agent-skills@web-design-guidelines 339.3K installs
    pattern = re.compile(r"^([a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+)\@([a-zA-Z0-9_\-\.]+)(?:\s+(.*))?$")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = pattern.match(line)
        if match:
            source, name, extra = match.groups()
            installs = extra.strip() if extra else ""
            results.append(
                {
                    "source": source,
                    "name": name,
                    "installs": installs,
                }
            )
    return results


async def search_remote_skills(query: str) -> list[dict[str, str]]:
    """Use npx skills find <query> Search for remote skills."""
    query_val = str(query or "").strip()
    if not query_val:
        return []
    if any(ch in query_val for ch in ("\n", "\r", "\x00")):
        raise ValueError("Từ khóa tìm kiếm chứa ký tự không hợp lệ")

    temp_home, env, workdir = _create_isolated_workdir()
    try:
        output = await _run_skills_cli(
            ["npx", "-y", "skills", "find", query_val],
            env=env,
            cwd=workdir,
        )
    finally:
        await asyncio.to_thread(shutil.rmtree, temp_home, ignore_errors=True)

    return _parse_search_skills(output)
