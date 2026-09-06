# Critic rubric

Score each still 0–4 per axis **against a named reference frame** from `references/`.
Write scores to `critic/scores/<exp>_<still>.md` with one line of evidence per axis
(what in the image earned the score). No reference on the board → no score, say so.

| Axis | 0 | 2 | 4 |
|---|---|---|---|
| **Detail density** — elements at three scales (terrain / mid dressing / ground clutter) | one scale, empty ground | two scales, bald patches | all three, no bald patches in frame |
| **Value structure** — clear light/mid/dark grouping, readable silhouette against sky/ground | flat or blown out | groups exist but muddy | three clean value groups, focal point brightest contrast |
| **Silhouette variety** — shapes read as distinct objects at thumbnail size | primitives, repeated | some variety | varied, irregular, no obvious tiling/repetition |
| **Focal hierarchy** — eye goes to one thing first, then a second | no focus | focus but competing hot spots | one focus, one secondary, rest supports |
| **Color harmony** — limited palette, deliberate accent | random / saturated everywhere | mostly harmonious | palette matches the reference family, single accent |
| **Scale cues** — figure, path, props establish size | nothing gives scale | one cue | multiple consistent cues |
| **Tells** — anything that says "generated primitives": floating slabs, hard plane edges, uniform grass tufts | many | a few | none visible |

Total /28. Also record: **what the user would fix first** (one sentence).

The rubric is a hypothesis. E05 tests it against `ratings.csv`; change it there, not ad hoc.

## Where the picks live

Rating page (pairwise, shared artifact): https://claude.ai/code/artifact/8a01d3d0-0c5e-4ff1-aa11-f32c7f489d96
Picks are stored in the artifact's `picks` collection as `{a, b, winner: a|b|tie, rater: user|model, ts, reason?}`.
Pull them from the lab with the Artifact tool (`read_db`, collection `picks`, `out_dir build/critic/db`) and run
`py -3 critic/rank.py build/critic/db` for the Bradley-Terry ranking and the user/model agreement number.
Rebuild the page after new stills: `py -3 critic/build_page.py` then republish `build/critic/barrow_pairs.html`.
