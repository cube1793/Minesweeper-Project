# Stage 3 Replay Validation — Replacement Selection Record

> **Project:** Minesweeper graduation project  
> **Scope:** Final 30 Replay Validation V1.1 corpus replacement provenance  
> **Status:** Final replacement record for the canonical replay-validation corpus  
> **Purpose:** Preserve why each original target was retained, recaptured, replaced, or excluded without using replay-validation performance outcomes to choose records.

---

## 1. Canonical corpus

The Final 30 replay-validation corpus was defined by logical slots, not by whatever rank ultimately supplied a usable replay.

### STANDARD

Original target ranks:

```text
1–10
21–30
```

Total: 20 logical slots.

### NO_FLAG

Original target ranks:

```text
1–5
26–30
```

Total: 10 logical slots.

The logical slot filename remains unchanged even when its final selected replay comes from a replacement rank.

Example:

```text
logical slot: STD_R006
final selected rank: 13
metadata filename: STD_R006.metadata.json
validation filename: STD_R006.validation.json
```

---

## 2. Frozen replacement rule

The replacement procedure used for the corpus was:

```text
unavailable / corrupt / unreconstructable original rank
    -> nearest unused rank in the same category
    -> if equally near, choose the lower rank
```

Additional constraints used during corpus repair:

- Rank 15 is pilot-only and is never eligible for the Final corpus.
- A same-rank recapture is preferred when the failure appears capture-sensitive.
- For a same-rank recapture, the first new take that returns `RECONSTRUCTED` is adopted immediately.
- Recaptures are not compared by P/H, modeled physical time, displayed time, or any other performance measure.
- Rejected attempts remain preserved under `final/superseded/`.
- Final canonical folders contain only the adopted 30 logical slots.

### 2.1 Exact metadata replacement-reason value

The five adopted replacement metadata files and their final validation JSONs store this exact text:

```text
Unreconstructable under frozen V1.1 fixed counter ROI
```

This stored field must not be treated as a precise per-case diagnosis. In particular, the actual reconstruction failures for `STD_R024` and `NF_R002` were repeated event omissions rather than fixed-ROI unreadability.

The detailed technical cause for each replacement is therefore recorded separately in this document.

---

## 3. Final replacement mapping

| Logical slot | Original rank | Final selected rank | Category | Final status |
|---|---:|---:|---|---|
| `STD_R006` | 6 | 13 | STANDARD | RECONSTRUCTED |
| `STD_R022` | 22 | 20 | STANDARD | RECONSTRUCTED |
| `STD_R023` | 23 | 19 | STANDARD | RECONSTRUCTED |
| `STD_R024` | 24 | 17 | STANDARD | RECONSTRUCTED |
| `NF_R002` | 2 | 6 | NO_FLAG | RECONSTRUCTED |

All other logical slots retain their original selected rank.

---

## 4. Replacement histories

### 4.1 `STD_R006` — original rank 6 -> final rank 13

#### Original rank 6

The original replay could not be reconstructed under the frozen V1.1 production validator.

Observed failure:

- click counter could not be read in the frozen fixed ROI;
- reconstruction produced `0/167` events;
- the board geometry itself was normal;
- the observed validator failure was therefore a fixed click-counter ROI incompatibility for this replay capture.

No claim is made here about why the source site rendered the sidebar differently. The cause of that layout difference is unknown.

Disposition:

```text
original rank 6 -> unreconstructable
```

#### Replacement candidate rank 11

The first replacement candidate was Standard rank 11.

Observed failure:

- click counter was unreadable throughout the capture;
- reconstruction produced `0/182` events;
- behavior was consistent with another frozen fixed-ROI incompatibility.

Disposition:

```text
rank 11 -> rejected as unreconstructable
```

#### Replacement candidate rank 12

The next candidate was Standard rank 12.

Observed failure:

```text
REVIEW_REQUIRED
164/166 events reconstructed
```

Disposition:

```text
rank 12 -> rejected as unreconstructable
```

#### Replacement candidate rank 13

The next candidate was Standard rank 13.

Final production result:

```text
RECONSTRUCTED
152/152 events
P_us = 26090347
```

Disposition:

```text
rank 13 -> adopted
```

The preserved artifacts support the failure history and final adoption. They do not by themselves independently prove every historical operator action after adoption, so no stronger claim is made here about whether later candidates were or were not inspected.

Final mapping:

```text
STD_R006: original 6 -> selected 13
```

---

### 4.2 `STD_R022` — original rank 22 -> final rank 20

The original Standard rank 22 replay could not be reconstructed under the frozen validator.

Observed failure:

- click counter was unreadable in the frozen fixed ROI;
- reconstruction produced `0/149` events;
- the board geometry itself was normal;
- the observed validator failure was fixed click-counter ROI incompatibility.

The nearest eligible unused replacement selected under the corpus rule was Standard rank 20.

Final production result:

```text
RECONSTRUCTED
175/175 events
P_us = 29463594
```

Final mapping:

```text
STD_R022: original 22 -> selected 20
```

The preserved evidence supports technical reconstruction incompatibility as the reason for replacement. No performance-based selection rule is documented.

---

### 4.3 `STD_R023` — original rank 23 -> final rank 19

The original Standard rank 23 replay could not be reconstructed under the frozen validator.

Observed failure:

- click counter was unreadable in the frozen fixed ROI;
- reconstruction produced `0/168` events;
- the board geometry itself was normal;
- the observed validator failure was fixed click-counter ROI incompatibility.

The next eligible unused replacement under the replacement sequence was Standard rank 19.

Final production result:

```text
RECONSTRUCTED
150/150 events
P_us = 24418243
```

Final mapping:

```text
STD_R023: original 23 -> selected 19
```

The preserved evidence supports technical reconstruction incompatibility as the reason for replacement. No performance-based selection rule is documented.

---

### 4.4 `STD_R024` — original rank 24 -> final rank 17

The original Standard rank 24 replay initially reconstructed only:

```text
153/154 events
```

A same-rank recapture was performed because the failure could have been capture-sensitive.

The same-rank retry reproduced the same failure:

```text
153/154 events
```

The repeated deterministic failure occurred at the same event boundary: reconstructed counter progression skipped expected event 117 and advanced from 116 to 118.

After this repeated same-rank failure, the logical slot was treated as unreconstructable and moved to replacement selection.

#### Rank 18 exclusion

Standard rank 18 was not separately recorded as a Standard replacement candidate.

The leaderboard record was identified as mobile-origin. Because this validation targets mouse-based physical execution and cursor-movement physics, the record was excluded as source/input-device incompatible with this validation target.

Important methodological note:

> The original frozen replacement wording did not explicitly define a mobile-origin exclusion rule.

Therefore this exclusion is recorded transparently here as a later eligibility clarification / limitation rather than being presented as if it had been written into the original protocol from the start.

A further provenance nuance must also be preserved:

- the Standard rank 18 leaderboard entry corresponds to the same underlying game as the original `NF_R002` game;
- that game was captured twice in the `NF_R002` failed-attempt history;
- those failed captures produced partial transition diagnostics and resolved-transition subtotals;
- because both attempts were incomplete reconstructions, their authoritative `modeled_physical_time_us` and authoritative P/H are null;
- therefore those partial diagnostics must not be treated as valid whole-game Model-C validation results for Standard rank 18.

The exclusion basis remained the mobile-origin input-device incompatibility, not an authoritative P/H result.

#### Rank 17 adoption

The next compatible eligible candidate was Standard rank 17.

Final production result:

```text
RECONSTRUCTED
156/156 events
P_us = 27074357
```

Final mapping:

```text
STD_R024: original 24 -> selected 17
```

---

### 4.5 `NF_R002` — original rank 2 -> final rank 6

The original No Flag rank 2 replay initially reconstructed:

```text
189/190 events
```

The first reconstructed visible click-counter value was 2 rather than 1, leaving one event unreconstructed.

A same-rank recapture was performed.

The retry reproduced the same failure:

```text
189/190 events
```

Because the same event-reconstruction defect repeated, the logical slot was treated as unreconstructable.

The replacement selected under the same-category nearest-unused procedure was No Flag rank 6.

Final production result:

```text
RECONSTRUCTED
169/169 events
P_us = 30390473
```

Final mapping:

```text
NF_R002: original 2 -> selected 6
```

The preserved evidence supports repeated reconstruction failure as the reason for replacement. The two failed attempts retain partial diagnostics, but authoritative P and P/H are null and must not be interpreted as whole-game validation results.

---

## 5. Same-rank recaptures that remained in the corpus

The following logical slots had capture-sensitive failures and were recaptured at the same leaderboard rank.

When a recapture returned `RECONSTRUCTED`, that take became the canonical same-rank artifact:

```text
STD_R003 -> same-rank recapture adopted
STD_R009 -> same-rank recapture adopted
STD_R010 -> later same-rank recapture adopted
STD_R030 -> same-rank recapture adopted
NF_R028  -> same-rank recapture adopted
```

The following same-rank recaptures repeated the original reconstruction defect and therefore proceeded to replacement:

```text
STD_R024 -> replacement required
NF_R002  -> replacement required
```

The preserved superseded validations do not show a discarded authoritative `RECONSTRUCTED` take among the retained failed/superseded attempts.

---

## 6. Superseded evidence retention

Failed and superseded evidence is intentionally retained.

Expected organization:

```text
results/stage3_replay_validation/final/superseded/
    <logical-slot>/
        original/
        attempt1/
        attempt2/
        replacement_R011/
        replacement_R012/
        ...
```

Each stored attempt should preserve its associated evidence set when available:

```text
video
metadata JSON
game PNG
OBS stats PNG
validation JSON
```

Common leaderboard provenance remains under `final/provenance/` rather than being duplicated into every superseded attempt directory.

The canonical `final/videos/`, `final/metadata/`, and final validation folders contain only the adopted logical-slot artifacts.

---

## 7. Performance-outcome independence

The preserved corpus history supports replacement and recapture decisions being driven by technical reconstructability / source compatibility.

The following authoritative whole-game values were not valid for failed incomplete attempts:

```text
modeled physical time P
P/H
```

Failed attempts may still contain non-authoritative partial diagnostics such as resolved-transition subtotals and transition comparison counts. Those diagnostics must not be reinterpreted as authoritative whole-game outcomes.

No evidence in the preserved artifacts demonstrates selection of a replacement because its authoritative P/H or Model-C validation result was more favorable.

This is a provenance claim bounded by the preserved evidence; the document does not claim to independently prove every historical operator action not captured by artifacts.

---

## 8. Final corpus state

After all recaptures and replacements, the canonical Final 30 corpus was rerun from the beginning through the frozen V1.1 production validator.

Final audit result:

```text
Records        : 30
Reconstructed  : 30
Non-authority  : 0
Event mismatch : 0
Unresolved     : 0
Null P         : 0
```

The Final 30 replacement mapping is therefore closed unless a later audit demonstrates a correctness or provenance defect.

This document records corpus-selection provenance only. It does not itself decide whether Physical Model C passes replay validation or whether model parameters should be changed.
