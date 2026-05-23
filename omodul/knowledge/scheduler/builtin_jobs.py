"""Builtin scheduled jobs for knowledge module."""

BUILTIN_JOBS = {
    "nightly_audio_gen": {
        "enabled": False,  # v1.0 unavailable, upstream image broken
        "schedule": "0 3 * * *",
        "agent": "audio_generator",
    },
}
