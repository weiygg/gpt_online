---
name: hotspot-feasibility-analyst
description: "Analyze whether a medical imaging AI hotspot can become a real project, considering clinical need, data access, technical maturity, competition, publication space, and translation potential."
---

# Hotspot Feasibility Analyst

Use this skill after daily or weekly literature cards identify emerging topics in medical imaging AI.

## Inputs

- Candidate hotspot.
- Supporting papers and links.
- User's available data and collaborators.
- Target output: paper, grant, patent, product, or teaching material.

## Scoring Dimensions

Score each dimension from 0 to 2.

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Clinical need | Unclear | Useful but not urgent | Clear decision/workflow pain point |
| Data access | No data | Small/internal data | Enough data plus labels or validation path |
| Technical maturity | Vague method | Reproducible baseline | Code/model/data or clear implementation route |
| Competition | Saturated | Competitive but room remains | Clear gap in population/task/validation |
| Publication space | Hard to publish | Needs careful positioning | Strong novelty or validation value |
| Translation potential | Purely conceptual | Indirect use | Fits clinical workflow or decision point |

## Output

- Overall grade:
  - A: start project now.
  - B: run 1-week evidence and data feasibility check.
  - C: keep as review/background topic.
  - D: do not invest now.
- Main opportunity.
- Main risk.
- Required evidence before proceeding.
- 7-day next actions.

## Safety Rules

- Do not overstate clinical value from retrospective internal validation.
- Identify regulatory, ethics, privacy, and data license barriers.
- Separate published evidence, preprint evidence, and speculation.
