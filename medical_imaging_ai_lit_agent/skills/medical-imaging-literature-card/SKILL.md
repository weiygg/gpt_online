---
name: medical-imaging-literature-card
description: "Generate daily medical imaging AI literature cards from PubMed/arXiv/Crossref search results, with source links, deduplication notes, priority ranking, and human review checks."
---

# Medical Imaging Literature Card

Use this skill when turning raw literature search results into a daily Feishu/Obsidian card for medical imaging AI research.

## Inputs

- Search date.
- Topic name and exact query string.
- Deduplicated records with title, authors, source, date, DOI/PMID/arXiv ID, URL, and abstract when available.
- User's current research resources if known: disease, modality, sample size, labels, outcomes, external validation, ethics status.

## Required Output

1. Top 3-8 papers worth reading today.
2. For each paper:
   - Why it matters.
   - What evidence supports that judgment.
   - Landing potential: high / medium / watch / low.
   - Manual review checklist.
3. Hotspot summary across topics.
4. Next action list.

## Rules

- Never invent DOI, PMID, arXiv ID, venue, authors, or sample size.
- Mark preprints clearly.
- Do not claim clinical usefulness unless there is external validation, reader study, prospective testing, or workflow evidence.
- Prefer fewer high-signal papers over a long unreadable list.
- Preserve original links so the user can verify.

## Manual Review Checklist

- Is the population close to the user's intended clinical population?
- Is the imaging modality and protocol comparable?
- Are labels clinically credible?
- Is there external validation or only internal splitting?
- Are code, model weights, or data available?
- Are claims aligned with actual evidence?
