# Critique log

Running record of what the user says about what they see. Verbatim where possible, dated, with what it
was said about. This is the raw material for any future critic; it is not a scorecard.

Entries marked *(Claude)* are Claude's own observations, kept separate so they never get mistaken for the user's.

| Date | About | Critique | Consequence |
|---|---|---|---|
| 2026-09-02 | AttunementDemo LR1–LR10 stills (before env-lab) | "nothing I did was able to build something beautiful that I was happy with" | env-lab started; diagnosis: empty scene, primitive assets, self-judging model |
| 2026-09-02 | E01/E03 trees and shrubs (procedural kit from `gen_rocks.py`) | "they look terrible, but the rest of the scene they are in looks great" | vegetation is a named gap (E06); whole-frame judgments carry passengers |
| 2026-09-02 | E03 hero assets (TRELLIS.2 dolmen, boulders) | "a couple images look so good they will win against anything else" | the asset factory is the proven leg; hero quality is not the bottleneck |
| 2026-09-02 | Barrow Pairs critic v1 (58 picks) | "I always pick the newer images"; "sample size is far too small"; "not sure this can extend to an entire style for an entire world"; "it carries things I don't like with it" | critic shelved; log + hypotheses kept instead |
| 2026-09-02 | Critic as a tool | "I doubt that tool would ever work" | E04 removed from the plan; the user judges every gate directly |
| 2026-09-02 | Ground material on the new terrain *(Claude)* | reads brick red instead of the baseline green; inherited material depends on the old plane's scale | **resolved E05**: the terrain had no material after run 1 (setup copied it from a plane that no longer existed); every E01–E03 still shows Unreal's default grid material |
| 2026-09-02 | Gate shots *(Claude)* | ward light + auto exposure white out any light stone, hero assets unreadable in situ | look pass; lock exposure in gate shots |
| 2026-09-02 | E03 gate shots *(Claude)* | the generated dolmen rendered as white plaster because the swap left the old stylised-stone override on the actors, not because of exposure alone | world file sets generated parts to mesh-default material; E05 rebuild shows the textures |

| 2026-09-02 | E05 rebuild vs E03 *(Claude)* | the rebuilt map looks different because it is the first render with the real ground material; all light/fog/grade values are identical | Barrow_W is the reference; the E01–E03 stills are not the scene's authored look |
| 2026-09-02 | E06 vegetation, round 4 (`build/snaps/e6/E6_wide.png`, 5 m close-up, E05-vs-E06 sheet) | "It already looks so much better" | E06 gate taken as passed on the side-by-side; distance read not separately called out. Vegetation stays card-based; species count and oak crown are the next tells to fix |
| 2026-09-02 | E07 ground material (`build/snaps/e7/E7_player.png`, grass tile `ground_grass`) | "The ground pattern is especially harsh. It looks like something those people who are afraid of holes would be terrified by. The pattern is too regular as well. If you look at the right angle at the right distance you just start to see lines where elements of the pattern create a larger regular pattern that is noticible." | grass tile regenerated low-contrast without bare patches; normal strength cut; macro variation moved from a re-sampled tile (which made a 7x grid) to world-space noise; stochastic two-sample rotation blend added to hide the repeat |
| 2026-09-02 | E07 ground fix (`build/snaps/e7/E7_player.png`) | "Much better. I think it's enough to pass for now. I hope we can revisit each layer later on, and make even more improvements, but let's continue for now." | E07 passed; a **polish backlog** is kept per layer in PLAN.md so every layer gets revisited |
| 2026-09-02 | E08 hall (`build/snaps/e8/E8_*.png`) vs the E03 gate | "It looks like it worked, but it looks really bad. I think we need to go full science and computer engineering on making things look good. A trained critic is not the solution. ... I think just applying patterns to things is the worst something can look. The gate you built in blender is the best thing this project has made so far." | direction change: geometry over texture; build like the gate (sculpted blocks from the asset factory, assembled procedurally); context-aware weathering; measurable image/geometry metrics instead of a learned critic |

## How to add an entry

When the user reacts to a still, a scene, or an asset, add a row: date, what it was about (file or actor
names where possible), the critique in their words, and what changed because of it. If they say
"this looks out of place" about something specific, record the object or region so the edit loop (E11)
can be tested against real cases later.
