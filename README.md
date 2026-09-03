# Resume Claim Verification Skill

A portable Agent Skill for Claude and Codex that reviews resume claims individually and produces a neutral, evidence-based PDF report for human review.

It does **not** label a resume or candidate as fake, rank candidates, infer intent, or make hiring recommendations. Missing online evidence is never treated as proof of deception. Reports show a beginner-friendly five-category percentage profile with raw counts and plain-language definitions rather than a misleading single “fake percentage.”

## Install

Copy this repository folder into the skills directory used by your agent. The package follows the standard `SKILL.md` layout used by Claude Agent Skills and Codex skills.

```bash
# Claude Code (user-level)
cp -R resume-claim-verification ~/.claude/skills/resume-claim-verification

# Codex (user-level)
cp -R resume-claim-verification ~/.codex/skills/resume-claim-verification
```

## Use

Invoke the skill with a resume and any candidate-provided evidence:

```text
Use $resume-claim-verification to review this resume claim by claim.
Do not search public sources unless I explicitly authorize it.
Produce the final PDF report.
```

For authorized public research:

```text
Use $resume-claim-verification to review this resume and its supplied links.
You may search public, job-relevant professional sources. Produce the final PDF report.
```

The skill first creates validated report JSON, then uses `scripts/generate_report.py` to produce the PDF. Optional normalized JSON is available for later ATS integration.

The tracked sample report is available at `output/pdf/sample-resume-claim-verification-report.pdf`.

## Local validation

Install the small PDF dependency set and run the tests:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Generate the included mixed-evidence example:

```bash
python scripts/generate_report.py \
  tests/fixtures/mixed-evidence.json \
  output/pdf/sample-resume-claim-verification-report.pdf
```

Render it for visual inspection:

```bash
pdftoppm -png output/pdf/sample-resume-claim-verification-report.pdf tmp/pdfs/sample
```
