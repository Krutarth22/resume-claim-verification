---
name: resume-claim-verification
description: Evaluate factual claims in resumes and portfolios, distinguish supported, unresolved, and contradictory evidence, and produce a neutral PDF report with follow-up questions. Use for resume due diligence or project/authorship verification; do not use to make autonomous hiring or fraud decisions.
---

# Resume Claim Verification

Assess claims, not people. The deliverable is an evidence dossier for human review, never a binary authenticity verdict, candidate score, fraud determination, or hiring recommendation.

## Inputs and authorization

1. Accept a resume in PDF, DOCX, image, or text form plus any candidate-provided portfolio, repository, publication, or credential links.
2. Ask before searching public sources unless the user already requested public research. Private employment, education, reference, or background checks require candidate consent and an authorized service.
3. Use only job-relevant evidence. Do not seek, infer, record, or use protected or sensitive personal traits.
4. If a source cannot be accessed or identity cannot be matched reliably, record the claim as `Not assessable`; do not treat missing evidence as adverse evidence.

## Workflow

1. Extract atomic, checkable claims. Separate employer, title, dates, education, project authorship, technologies, responsibilities, and quantified impact instead of judging a whole paragraph at once.
2. Normalize dates only enough to compare them. Treat ordinary month/year rounding as benign unless it changes a material conclusion.
3. Check internal consistency across the resume before using external sources.
4. When authorized, inspect candidate-provided and public professional evidence. Prefer primary evidence such as an employer page, repository history, release notes, publication record, credential issuer, or deployed artifact. A search-result snippet alone is not evidence.
5. Record observations separately from inferences. For every conflict, include reasonable alternative explanations and a question that could resolve it.
6. Apply the assessment and confidence rules in [references/assessment-rubric.md](references/assessment-rubric.md).
7. Create a report JSON that conforms to [references/report-schema.md](references/report-schema.md).
8. Validate and generate the PDF:

   ```bash
   python scripts/validate_report.py report.json
   python scripts/generate_report.py report.json output/pdf/resume-claim-verification-report.pdf
   ```

9. Render every final PDF with `pdftoppm`, inspect every page, and fix clipping, overflow, unreadable tables, or broken links before delivery.
10. Return a brief plain-text summary and the PDF. Generate normalized JSON only when the user requests an integration-ready secondary output.

## Required report behavior

- Use only these claim assessments: `Supported`, `Plausible but unverified`, `Needs clarification`, `Material inconsistency`, and `Not assessable`.
- Use only these overall conclusions: `No material issues found`, `Clarification recommended`, `Human review recommended`, and `Insufficient evidence`.
- A `Material inconsistency` requires credible evidence that directly conflicts with a material claim. Weak signals, stylistic impressions, or absence of evidence never qualify.
- Confidence describes confidence in the assessment, not confidence in the candidate's honesty.
- Show the percentage of assessed claims in each assessment category as an evidence profile. Do not combine those percentages into an “X% fake,” deception-probability, authenticity, or candidate-risk score.
- Cite a retrievable source or identify the supplied artifact for each supporting observation.
- Include the standard limitations and human-review disclaimer from the report schema.
- Do not rank candidates, recommend hire/no-hire, infer intent, or use terms such as “fake resume” as a conclusion.

## Failure handling

- If the resume cannot be parsed reliably, stop and request a clearer source rather than guessing.
- If evidence conflicts across sources, preserve both observations and reduce confidence unless one source is demonstrably authoritative.
- If the PDF toolchain is unavailable, return the plain-text summary and validated JSON, explain the missing dependency, and do not substitute Markdown as the final report.
