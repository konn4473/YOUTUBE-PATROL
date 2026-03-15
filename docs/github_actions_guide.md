# GitHub Actions Guide

## Overview

This project can run every day at 07:30 JST with GitHub Actions.
The workflow file is `.github/workflows/morning-patrol.yml`.

## Schedule

- GitHub Actions uses UTC.
- `07:30 JST` is `22:30 UTC` on the previous day.
- The workflow uses `30 22 * * *`.

## Required Secrets

Set these repository secrets before enabling the workflow:

- `GOOGLE_API_KEY`
- `GEMINI_API_KEY`
- `DISCORD_WEBHOOK_URL`

If `DISCORD_WEBHOOK_URL` is empty, the jobs still run but no Discord message is sent.

## What the workflow runs

1. Creates `infra/.env` from GitHub Secrets
2. Runs the main patrol job
3. Runs the YouTube patrol job
4. Uploads `data/patrol` and `data/youtube_patrol` as workflow artifacts

## Limitation

GitHub Actions runners are ephemeral.
Local snapshot history is not preserved across runs unless you push it somewhere else.
Current workflow keeps each run's outputs as artifacts, but cross-run diffs are limited.

## Manual run

You can also trigger the workflow manually from the GitHub Actions UI using `workflow_dispatch`.
