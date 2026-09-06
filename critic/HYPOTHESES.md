# What a critic that worked would look like

Shelved 2026-09-02 at the user's call after v1 (pairwise, whole frame, 21 uncontrolled stills) only
recovered "which experiment made it". These are hypotheses, not a plan. Revisit if the log in
`CRITIQUES.md` grows long enough to test any of them.

## Why v1 failed

1. The stills varied on one confounded axis (experiment number), so preference could only learn that axis.
2. A whole-frame pick has no way to say "wins despite the trees". Passengers ride along.
3. Nothing in v1 was tied to a *region's* style; a single ranking across the world is the wrong shape.
4. 21 stills, 58 picks. A few dominant frames make Bradley-Terry degenerate (top five at 5.0, rest at 0).

## Hypotheses

- **H1 Elements, not frames.** Judgments on single-factor pairs (same scene, one thing changed) turn
  preference into a measurement of that thing. Test: per-factor win rates separate ≥70/30.
- **H2 Attribution is cheap and necessary.** One tap after a pick ("what decided it", "never ship this")
  is enough to attribute a frame-level pick to an element. Test: attributed elements predict later picks.
- **H3 Quality and style are separate judgments.** A universal quality rubric (density at three scales,
  value structure, focal hierarchy, tells) plus a per-region style board. Test: the rubric's scores
  transfer across regions; style boards do not, and should not.
- **H4 A model can be a second rater on quality, not on style.** Agreement on single-factor quality pairs
  could reach 70%+; agreement on "does this belong to my world" probably cannot without boards.
  Test: run the model on the same pairs, blind; the number is the whole result.
- **H5 The critique log beats the rating page.** Specific, worded reactions about named objects
  ("the bushes are terrible", "this stone is too pink") carry more information per second of the
  user's time than a pick. Test: after 50 log entries, can Claude predict the next 10 reactions?
- **H6 The right unit of judgment at world scale is a walk, not a still.** Stills flatten what a
  player experiences. Test: does the user's reaction to a 60-second fly-through match their still ratings?

## What would make it worth reopening

- The log has 50+ entries and the same complaints recur (a pattern a tool could catch earlier).
- The search loop (fifty lighting rigs, a hundred kit variants) produces more candidates than the user
  is willing to look at, and something has to pre-filter.
- Scale (E12) makes sampling unavoidable.
