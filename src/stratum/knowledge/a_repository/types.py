"""A Repository — domain types and enums."""

from __future__ import annotations

from enum import Enum


class ReadingRunStatus(str, Enum):
    CREATED = "CREATED"
    READING = "READING"
    EXTRACTING = "EXTRACTING"
    CANDIDATING = "CANDIDATING"
    VERIFYING = "VERIFYING"
    REVIEWING = "REVIEWING"
    FROZEN = "FROZEN"
    FAILED = "FAILED"


class EvidenceType(str, Enum):
    QUOTE = "QUOTE"
    STRUCTURE = "STRUCTURE"
    SUMMARY = "SUMMARY"
    OBSERVATION = "OBSERVATION"


class CandidateType(str, Enum):
    DEFINITION = "DEFINITION"
    CLAIM = "CLAIM"
    FACT = "FACT"
    CONCEPT = "CONCEPT"
    ARGUMENT = "ARGUMENT"
    MECHANISM = "MECHANISM"


class KUCandidateStatus(str, Enum):
    EXTRACTED = "EXTRACTED"
    REVIEWED = "REVIEWED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class PipelineStage(str, Enum):
    REGISTER = "register"
    SNAPSHOT = "snapshot"
    READ = "read"
    EXTRACT = "extract"
    CANDIDATE = "candidate"
    VERIFY = "verify"
    FREEZE = "freeze"
