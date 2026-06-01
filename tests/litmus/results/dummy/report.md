# Summary

- **Run timestamp**: 20260601T120000Z
- **Git SHA**: `abc1234`
- **Total questions**: 8 (1 errors)
- **Hit rate** (≥1 expected URL in top 5): 100.0% (7/7)
- **Partial rate** (≥50% expected URLs in top 5): 71.4% (5/7)
- **Full rate** (all expected URLs in top 5): 42.9% (3/7)
- **Mean recall@5**: 0.651
- **Mean recall@10**: 0.889

> Recall metrics are computed from `debug.reranked_chunks` (full reranker output,
> up to `RAG_RERANK_TOP_K = 15`). recall@5 = top-5 of that list; recall@10 = top-10.

---

# Per Question Results

| Question ID | Category | Hit | Partial | Full | Recall@5 | Recall@10 | Reranked |
|-------------|----------|:---:|:-------:|:----:|:--------:|:---------:|:--------:|
| `cognition_001` | cognition | ✓ | ✓ | ✓ | 1.00 | 1.00 | 7 |
| `productivity_001` | productivity | ✓ | ✗ | ✗ | 0.33 | 1.00 | 10 |
| `memory_001` | memory | ✓ | ✓ | ✓ | 1.00 | 1.00 | 6 |
| `memory_002` | memory | ✓ | ✓ | ✗ | 0.50 | 0.75 | 9 |
| `therapy_001` | mental_health | ✓ | ✓ | ✓ | 1.00 | 1.00 | 5 |
| `digital_wellbeing_001` | digital_wellbeing | ✓ | ✗ | ✗ | 0.40 | 0.80 | 10 |
| `mental_health_001` | mental_health | — | — | — | — | — | ERROR: timeout after 60s |
| `psychology_001` | psychology | ✓ | ✓ | ✗ | 0.33 | 0.67 | 10 |

---

# Failure Analysis

## `productivity_001` — HIT

**Question**: I'm not feeling productive. What can I do?
**Notes**: flag this as high-variance — expect at least 2 of 3 retrieved in most cases.

**Expected URLs**:
- `https://cognitiontoday.com/your-brain-on-productivity-thinking-doing-modes/`
- `https://cognitiontoday.com/productivity-tips-for-gen-z/`
- `https://cognitiontoday.com/losing-focus-at-work-try-distractions-multitasking-music-breaks/`

**Top-5 reranked URLs**:
- [1] `https://cognitiontoday.com/your-brain-on-productivity-thinking-doing-modes/` ✓
- [2] `https://cognitiontoday.com/motivation-science/`
- [3] `https://cognitiontoday.com/deep-work-summary/`
- [4] `https://cognitiontoday.com/habit-formation-guide/`
- [5] `https://cognitiontoday.com/procrastination-causes-solutions/`

**Missing from top 5**:
- `https://cognitiontoday.com/productivity-tips-for-gen-z/` *(present in top 10)*
- `https://cognitiontoday.com/losing-focus-at-work-try-distractions-multitasking-music-breaks/` *(present in top 10)*

## `memory_002` — PARTIAL

**Question**: How do I improve my memory?

**Expected URLs**:
- `https://cognitiontoday.com/mnemonic-techniques-to-slay-at-memorizing-tutorial/`
- `https://cognitiontoday.com/sciency-guide-to-expert-level-memory-skills/`
- `https://cognitiontoday.com/boost-memory-delay-cognitive-decline-memory-loss/`
- `https://cognitiontoday.com/memorization-techniques-to-improve-memory-for-facts/`

**Top-5 reranked URLs**:
- [1] `https://cognitiontoday.com/mnemonic-techniques-to-slay-at-memorizing-tutorial/` ✓
- [2] `https://cognitiontoday.com/sciency-guide-to-expert-level-memory-skills/` ✓
- [3] `https://cognitiontoday.com/spaced-repetition-guide/`
- [4] `https://cognitiontoday.com/sleep-and-memory-consolidation/`
- [5] `https://cognitiontoday.com/retrieval-practice-effect/`

**Missing from top 5**:
- `https://cognitiontoday.com/boost-memory-delay-cognitive-decline-memory-loss/` *(present in top 10)*
- `https://cognitiontoday.com/memorization-techniques-to-improve-memory-for-facts/`

## `digital_wellbeing_001` — HIT

**Question**: I'm spending too much time online and not doing anything.

**Expected URLs**:
- `https://cognitiontoday.com/brainrot-reelationships-and-the-dm-verse/`
- `https://cognitiontoday.com/psychology-of-memes-advanced-emotions-outsourced-thoughts-mental-health/`
- `https://cognitiontoday.com/procrastinating-with-your-phone-reduce-procrastinatory-phone-dependence/`
- `https://cognitiontoday.com/phone-addiction-coping-solutions-research-statistics/`
- `https://cognitiontoday.com/effect-of-social-media-on-mental-health-well-being/`

**Top-5 reranked URLs**:
- [1] `https://cognitiontoday.com/phone-addiction-coping-solutions-research-statistics/` ✓
- [2] `https://cognitiontoday.com/effect-of-social-media-on-mental-health-well-being/` ✓
- [3] `https://cognitiontoday.com/screen-time-effects/`
- [4] `https://cognitiontoday.com/social-media-comparison/`
- [5] `https://cognitiontoday.com/doomscrolling-psychology/`

**Missing from top 5**:
- `https://cognitiontoday.com/brainrot-reelationships-and-the-dm-verse/` *(present in top 10)*
- `https://cognitiontoday.com/psychology-of-memes-advanced-emotions-outsourced-thoughts-mental-health/` *(present in top 10)*
- `https://cognitiontoday.com/procrastinating-with-your-phone-reduce-procrastinatory-phone-dependence/` *(present in top 10)*

## `psychology_001` — PARTIAL

**Question**: How can I use psychology for my sales and marketing?
**Notes**: 6 expected URLs — recall@5 caps at 0.83, use recall@10 as primary metric for this one.

**Expected URLs**:
- `https://cognitiontoday.com/nudge-marketing-and-behavioral-engineering/`
- `https://cognitiontoday.com/how-do-we-humanize-products-brands-science-branding-tips/`
- `https://cognitiontoday.com/consumer-psychology-for-marketers/`
- `https://cognitiontoday.com/how-and-why-looks-matter/`
- `https://cognitiontoday.com/smart-consumers-overcome-the-framing-effect/`
- `https://cognitiontoday.com/effort-heuristic-advertisement-marketing-psychology/`

**Top-5 reranked URLs**:
- [1] `https://cognitiontoday.com/nudge-marketing-and-behavioral-engineering/` ✓
- [2] `https://cognitiontoday.com/consumer-psychology-for-marketers/` ✓
- [3] `https://cognitiontoday.com/persuasion-techniques/`
- [4] `https://cognitiontoday.com/how-and-why-looks-matter/` ✓
- [5] `https://cognitiontoday.com/pricing-psychology/`

**Missing from top 5**:
- `https://cognitiontoday.com/how-do-we-humanize-products-brands-science-branding-tips/` *(present in top 10)*
- `https://cognitiontoday.com/smart-consumers-overcome-the-framing-effect/` *(present in top 10)*
- `https://cognitiontoday.com/effort-heuristic-advertisement-marketing-psychology/` *(present in top 10)*

## `mental_health_001` — API ERROR

**Question**: I've been feeling depressed, and I don't know what to do.
**Error**: `timeout after 60s`

