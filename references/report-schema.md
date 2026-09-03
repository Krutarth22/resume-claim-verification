# Report JSON schema

The PDF generator consumes UTF-8 JSON with this shape. Unknown fields are rejected so prohibited decision fields cannot silently enter the report.

```json
{
  "report_version": "1.0",
  "candidate_label": "Candidate A",
  "review_date": "2026-09-02",
  "reviewed_inputs": ["Resume", "Candidate-provided GitHub profile"],
  "overall_conclusion": "Clarification recommended",
  "summary": "Most claims are coherent; two require focused follow-up.",
  "claims": [
    {
      "id": "C1",
      "category": "Project authorship",
      "claim": "Created the linked inventory application",
      "assessment": "Needs clarification",
      "confidence": "Medium",
      "observations": [
        "The candidate appears in three commits after the repository was created."
      ],
      "inference": "The available history supports contribution but not sole creation.",
      "evidence": [
        {
          "source": "Repository commit history",
          "finding": "Another account authored the initial commit.",
          "url": "https://example.com/repository/commits"
        }
      ],
      "alternative_explanations": [
        "Earlier work may have been migrated from a private repository."
      ],
      "follow_up_questions": [
        "Which components did you personally design and implement?"
      ],
      "next_step": "Ask the candidate to walk through one representative contribution."
    }
  ],
  "sources": [
    {
      "label": "Candidate-provided repository",
      "url": "https://example.com/repository",
      "accessed": "2026-09-02"
    }
  ],
  "limitations": [
    "Missing public evidence is not evidence of deception.",
    "Identity matching between profiles may be uncertain."
  ]
}
```

## Required fields

- Top level: `report_version`, `candidate_label`, `review_date`, `reviewed_inputs`, `overall_conclusion`, `summary`, `claims`, `sources`, `limitations`.
- Claim: `id`, `category`, `claim`, `assessment`, `confidence`, `observations`, `inference`, `evidence`, `alternative_explanations`, `follow_up_questions`, `next_step`.
- Evidence: `source`, `finding`; `url` is optional.
- Source: `label`; `url` and `accessed` are optional.

## Prohibited fields and conclusions

Do not add fields representing `fake`, `fraud`, `score`, `risk_score`, `candidate_score`, `hire`, `hiring_recommendation`, `ranking`, protected traits, or inferred intent. Do not state that a candidate lied, committed fraud, should be hired, or should be rejected.

## Standard limitations

The generator always appends these statements even if they are absent from the input:

- Missing public evidence is not evidence of deception.
- Confidential or private work may not be independently verifiable.
- Identity matching between records may be uncertain.
- This report does not establish fraud and must not be used as an autonomous hiring decision.

The validator derives `counts` and `percentages` from `claims`; they are not accepted as input. The PDF presents the percentages as a five-category evidence profile and never combines them into a single authenticity or deception score.
