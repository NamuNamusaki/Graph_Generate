"""
Helper functions for web_api/app_frontend.py.

All function in this files:
  1. FASTA validation      -- validate_fasta_content()
  2. Job ID formatting     -- format_job_id()
  3. Result file reading   -- group_label_from_filename(), 
                              read_stat_files(),
                              resolve_sequence_file()

Nothing here touches the database; app_frontend.py handles that via db.py.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from fastapi import HTTPException

# -----------------------------------------------------------------------------------------
# 1. FASTA VALIDATION
# -----------------------------------------------------------------------------------------
MAX_FASTA_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB -- matches the web_ui limit

# Standard 20 canonical amino acids + common IUPAC ambiguity codes:
# B=Asp/Asn, Z=Glu/Gln, X=any, J=Leu/Ile, U=selenocysteine, O=pyrrolysine.
VALID_AA_CHARS = set("ACDEFGHIKLMNPQRSTVWYBZXJUO")

def _parse_fasta_records(lines: List[str]) -> List[tuple]:
    #Groups raw FASTA lines into [(header, [sequence_line, ...]), ...].
    records: List[tuple] = []
    current_header: Optional[str] = None
    current_seq_lines: List[str] = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current_header is not None:
                records.append((current_header, current_seq_lines))
            current_header = line
            current_seq_lines = []
        else:
            current_seq_lines.append(line)

    if current_header is not None:
        records.append((current_header, current_seq_lines))

    return records

def validate_fasta_content(fasta_content: str) -> List[str]:
    """
    Checks fasta_content against the project's upload rules:
      - total size is within MAX_FASTA_SIZE_BYTES
      - content starts with a '>' header (i.e. it really is FASTA)
      - every record has at least one sequence line
      - every sequence uses only recognized amino acid letters

    Returns a list of human-readable problems -- an EMPTY list means the input
    is valid.
    """
    errors: List[str] = []

    size_bytes = len(fasta_content.encode("utf-8"))
    if size_bytes > MAX_FASTA_SIZE_BYTES:
        errors.append(
            f"FASTA content is {size_bytes / (1024 * 1024):.1f} MB, over the "
            f"{MAX_FASTA_SIZE_BYTES // (1024 * 1024)} MB limit."
        )

    lines = fasta_content.splitlines()
    if not lines or not lines[0].strip().startswith(">"):
        errors.append("Content doesn't start with a FASTA header ('>...') -- not a valid FASTA file.")
        return errors  # nothing structurally useful left to check

    records = _parse_fasta_records(lines)
    if not records:
        errors.append("No sequence records found.")
        return errors

    for idx, (header, seq_lines) in enumerate(records, start=1):
        if not seq_lines:
            errors.append(f"Record {idx} ({header[:40]}) has a header but no sequence.")
            continue
        seq = "".join(seq_lines).upper()
        bad_chars = sorted(set(seq) - VALID_AA_CHARS)
        if bad_chars:
            errors.append(
                f"Record {idx} ({header[:40]}) has invalid character(s) "
                f"for a protein sequence: {', '.join(bad_chars)}"
            )
    return errors

# -----------------------------------------------------------------------------------------
# 2. JOB ID FORMATTING
# -----------------------------------------------------------------------------------------
def format_job_id(db_id: int) -> str:
    """
    Turns a job row's real MySQL auto-increment id into the display-friendly
    'JOB000001' label the API returns.
    """
    return f"JOB{db_id:06d}"

# -----------------------------------------------------------------------------------------
# 3. RESULT FILE READING
# -----------------------------------------------------------------------------------------
# Matches "RankBioactivity_G1_2Enz", "RankBioactivity_G3a_2Enz", etc.
STAT_FILE_PATTERN = re.compile(r"^RankBioactivity_G(\d+)([a-z]?)(?:_\d+Enz)?$")

def group_label_from_filename(stem: str) -> Optional[str]:
    """'RankBioactivity_G3a_2Enz' -> 'Group 3a'; returns None if it doesn't match."""
    match = STAT_FILE_PATTERN.match(stem)
    if not match:
        return None
    num, letter = match.groups()
    return f"Group {num}{letter}"

def read_stat_files(output_path: Optional[str]) -> Dict[str, list]:
    """
    Reads this job's RankBioactivity_G*.csv statistics files into
    {group_label: [{"Bioactivity": ..., "nPepSeq": ...}, ...]}.

    Returns an empty dict when output_path is None/empty -- that means the
    job hasn't finished yet, which is a normal state.
    """
    if not output_path:
        return {}

    job_output_dir = Path(output_path).resolve()
    if not job_output_dir.is_dir():
        raise HTTPException(
            status_code=500,
            detail=f"output_result_path does not exist on disk: {output_path}",
        )

    stat_files: Dict[str, list] = {}
    for path in sorted(job_output_dir.glob("RankBioactivity_*.csv")):
        group_label = group_label_from_filename(path.stem)
        if group_label is None:
            continue  # skip anything not matching the expected naming pattern

        # encoding="utf-8-sig" strips the leading BOM these files were saved
        # with (otherwise the first column reads as "﻿Bioactivity").
        df = pd.read_csv(path, encoding="utf-8-sig")
        missing = {"Bioactivity", "nPepSeq"} - set(df.columns)
        if missing:
            raise HTTPException(
                status_code=500,
                detail=f"{path.name} is missing columns: {sorted(missing)}",
            )
        stat_files[group_label] = df.to_dict(orient="records")

    return stat_files

def resolve_sequence_file(output_path: Optional[str], group: str, bioactivity: str) -> Path:
    """
    Resolves one bioactivity's peptide-sequence CSV inside this job's output
    directory, e.g. group="Group 1", bioactivity="ACE_inhibitor" ->
    <output_path>/ResultG1/ACE_inhibitor.csv
    """
    if not output_path:
        raise HTTPException(
            status_code=409,
            detail="Job results are not ready yet. Wait for status to reach COMPLETED before requesting a download.",
        )
    job_output_dir = Path(output_path).resolve()
    if not job_output_dir.is_dir():
        raise HTTPException(
            status_code=500,
            detail=f"output_result_path does not exist on disk: {output_path}",
        )
    # "Group 1" -> "G1" -> the ResultG1/ subfolder the sequence files live under.
    group_id = group.replace("Group ", "G")
    candidate = (job_output_dir / f"Result{group_id}" / f"{bioactivity}.csv").resolve()

    # Defend against path traversal (e.g. bioactivity="../../etc/passwd") --
    # reject anything resolving outside job_output_dir before touching disk.
    if job_output_dir not in candidate.parents:
        raise HTTPException(status_code=400, detail="Invalid group or bioactivity value")

    if not candidate.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"No sequence file for group={group}, bioactivity={bioactivity}",
        )

    return candidate
