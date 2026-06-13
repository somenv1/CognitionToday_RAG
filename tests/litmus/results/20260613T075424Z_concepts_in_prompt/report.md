# Summary

- **Run timestamp**: 20260613T075424Z
- **Git SHA**: `d46ded5`
- **Total questions**: 8
- **Hit rate** (≥1 expected URL in top 5): 62.5% (5/8)
- **Partial rate** (≥50% expected URLs in top 5): 37.5% (3/8)
- **Full rate** (all expected URLs in top 5): 0.0% (0/8)
- **Mean recall@5**: 0.300
- **Mean recall@10**: 0.429
- **Mean concept recall@5**: 0.254
- **Mean union recall@5**: 0.367

> Chunk recall is computed from `debug.reranked_chunks` (full reranker output,
> up to `RAG_RERANK_TOP_K = 15`). recall@5 = top-5 of that list; recall@10 = top-10.
>
> Concept recall is computed from `debug.concepts` (up to `RAG_CONCEPT_TOP_K = 8`,
> de-duped to source-article URLs, ordered by RRF-style rank).
>
> Union recall counts an expected URL as retrieved if it appears in the chunk
> top-K OR anywhere in the concept URLs — the headline Phase 2 retrieval metric.

---

# Per Question Results

| Question ID | Category | Hit | Partial | Full | Recall@5 | Recall@10 | Concept@5 | Union@5 | Union@10 | Reranked |
|-------------|----------|:---:|:-------:|:----:|:--------:|:---------:|:---------:|:-------:|:--------:|:--------:|
| `cognition_001` | cognition | ✓ | ✓ | ✗ | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 | 14 |
| `productivity_001` | productivity | ✗ | ✗ | ✗ | 0.00 | 0.33 | 0.00 | 0.33 | 0.67 | 13 |
| `memory_001` | memory | ✓ | ✓ | ✗ | 0.67 | 0.67 | 0.67 | 0.67 | 0.67 | 9 |
| `memory_002` | memory | ✗ | ✗ | ✗ | 0.00 | 0.25 | 0.00 | 0.00 | 0.25 | 8 |
| `therapy_001` | mental_health | ✓ | ✓ | ✗ | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 | 15 |
| `digital_wellbeing_001` | digital_wellbeing | ✓ | ✗ | ✗ | 0.40 | 0.60 | 0.20 | 0.60 | 0.60 | 15 |
| `mental_health_001` | mental_health | ✗ | ✗ | ✗ | 0.00 | 0.25 | 0.00 | 0.00 | 0.25 | 13 |
| `psychology_001` | psychology | ✓ | ✗ | ✗ | 0.33 | 0.33 | 0.17 | 0.33 | 0.33 | 13 |

---

# Failure Analysis

## `cognition_001` — PARTIAL

**Question**: What is cognition?

**Expected URLs**:
- `https://cognitiontoday.com/category/cognition/`
- `https://cognitiontoday.com/what-is-cognition-executive-functions-and-cognitive-processes/`

**Top-5 reranked URLs**:
- [1] `https://cognitiontoday.com/metacognition-metamemory-meta-skills/`
- [2] `https://cognitiontoday.com/why-does-caffeine-alter-mood-focus-cognition/`
- [3] `https://cognitiontoday.com/what-is-cognition-executive-functions-and-cognitive-processes/` ✓
- [4] `https://cognitiontoday.com/big-changes-break-our-perception-blame-our-words/`
- [5] `https://cognitiontoday.com/portion-size-effect-eating-habits-portion-control/`

**Concept-derived URLs**:
- [1] `https://cognitiontoday.com/easy-explanations-definitions-glossary-psychology-neuroscience/`
- [2] `https://cognitiontoday.com/the-heart-mind-relationship-is-more-than-a-metaphor/`
- [3] `https://cognitiontoday.com/what-is-cognition-executive-functions-and-cognitive-processes/` ✓
- [4] `https://cognitiontoday.com/chewing-gum-affects-mood-cognition-in-surprising-ways/`
- [5] `https://cognitiontoday.com/study-tips-for-psychology-students/`
- [6] `https://cognitiontoday.com/psychology-definition-nature-and-scope-types/`
- [7] `https://cognitiontoday.com/boost-memory-delay-cognitive-decline-memory-loss/`
- [8] `https://cognitiontoday.com/psychology-myth-vs-fact-quiz/`

**Missing from top 5**:
- `https://cognitiontoday.com/category/cognition/`

## `productivity_001` — MISS

**Question**: I'm not feeling productive. What can I do?
**Notes**: flag this as high-variance — expect at least 2 of 3 retrieved in most cases.

**Expected URLs**:
- `https://cognitiontoday.com/your-brain-on-productivity-thinking-doing-modes/`
- `https://cognitiontoday.com/productivity-tips-for-gen-z/`
- `https://cognitiontoday.com/losing-focus-at-work-try-distractions-multitasking-music-breaks/`

**Top-5 reranked URLs**:
- [1] `https://cognitiontoday.com/you-procrastinate-because-of-emotions-not-laziness-regulate-them-to-stop-procrastinating/`
- [2] `https://cognitiontoday.com/productivity-tips-for-early-career-employees/`
- [3] `https://cognitiontoday.com/ai-forked-us/`
- [4] `https://cognitiontoday.com/prospective-memory-explanation-and-how-to-build-it/`
- [5] `https://cognitiontoday.com/how-to-increase-productivity-the-ultimate-psychological-guide/`

**Concept-derived URLs**:
- [1] `https://cognitiontoday.com/9-reasons-why-you-should-learn-a-new-skill-even-if-you-dont-need-it/`
- [2] `https://cognitiontoday.com/productivity-tips-for-early-career-employees/`
- [3] `https://cognitiontoday.com/examples-of-everyday-procrastination-mindsets-and-beliefs/`
- [4] `https://cognitiontoday.com/active-or-passive-procrastinating-on-purpose-may-boost-creativity-productivity/`
- [5] `https://cognitiontoday.com/ways-to-reduce-stress-during-the-covid-19-pandemic/`
- [6] `https://cognitiontoday.com/your-brain-on-productivity-thinking-doing-modes/` ✓
- [7] `https://cognitiontoday.com/skills-for-self-improvement-self-development-and-independence/`

**Missing from top 5**:
- `https://cognitiontoday.com/your-brain-on-productivity-thinking-doing-modes/`
- `https://cognitiontoday.com/productivity-tips-for-gen-z/` *(present in top 10)*
- `https://cognitiontoday.com/losing-focus-at-work-try-distractions-multitasking-music-breaks/`

## `memory_001` — PARTIAL

**Question**: How is memory stored?

**Expected URLs**:
- `https://cognitiontoday.com/memory-models-in-psychology-understanding-human-memory/`
- `https://cognitiontoday.com/in-what-form-is-memory-stored-in-the-brain-mind-an-introduction/`
- `https://cognitiontoday.com/metacognition-metamemory-meta-skills/`

**Top-5 reranked URLs**:
- [1] `https://cognitiontoday.com/in-what-form-is-memory-stored-in-the-brain-mind-an-introduction/` ✓
- [2] `https://cognitiontoday.com/prospective-memory-explanation-and-how-to-build-it/`
- [3] `https://cognitiontoday.com/memory-models-in-psychology-understanding-human-memory/` ✓
- [4] `https://cognitiontoday.com/learning-vs-memory-in-school-education/`
- [5] `https://cognitiontoday.com/ai-forked-us/`

**Concept-derived URLs**:
- [1] `https://cognitiontoday.com/in-what-form-is-memory-stored-in-the-brain-mind-an-introduction/` ✓
- [2] `https://cognitiontoday.com/sciency-guide-to-expert-level-memory-skills/`
- [3] `https://cognitiontoday.com/daily-memory-habits-to-improve-confidence-in-memory/`
- [4] `https://cognitiontoday.com/memory-models-in-psychology-understanding-human-memory/` ✓
- [5] `https://cognitiontoday.com/learning-vs-memory-in-school-education/`
- [6] `https://cognitiontoday.com/why-fun-improves-learning-mood-senses-neurons-arousal-cognition/`

**Missing from top 5**:
- `https://cognitiontoday.com/metacognition-metamemory-meta-skills/`

## `memory_002` — MISS

**Question**: How do I improve my memory?

**Expected URLs**:
- `https://cognitiontoday.com/mnemonic-techniques-to-slay-at-memorizing-tutorial/`
- `https://cognitiontoday.com/sciency-guide-to-expert-level-memory-skills/`
- `https://cognitiontoday.com/boost-memory-delay-cognitive-decline-memory-loss/`
- `https://cognitiontoday.com/memorization-techniques-to-improve-memory-for-facts/`

**Top-5 reranked URLs**:
- [1] `https://cognitiontoday.com/prospective-memory-explanation-and-how-to-build-it/`
- [2] `https://cognitiontoday.com/how-to-improve-your-memory-and-remembering-capacity/`
- [3] `https://cognitiontoday.com/ai-forked-us/`
- [4] `https://cognitiontoday.com/daily-memory-habits-to-improve-confidence-in-memory/`
- [5] `https://cognitiontoday.com/improve-your-observation-power/`

**Concept-derived URLs**:
- [1] `https://cognitiontoday.com/brain-benefits-from-exercise-mechanisms/`
- [2] `https://cognitiontoday.com/psychology-facts-neuroscience-trivia/`
- [3] `https://cognitiontoday.com/daily-memory-habits-to-improve-confidence-in-memory/`
- [4] `https://cognitiontoday.com/brain-hacking-tricks/`
- [5] `https://cognitiontoday.com/how-to-be-smarter-50-actionable-tips-to-have-a-sharp-mind-and-increase-intelligence/`
- [6] `https://cognitiontoday.com/how-to-improve-your-memory-and-remembering-capacity/`

**Missing from top 5**:
- `https://cognitiontoday.com/mnemonic-techniques-to-slay-at-memorizing-tutorial/`
- `https://cognitiontoday.com/sciency-guide-to-expert-level-memory-skills/`
- `https://cognitiontoday.com/boost-memory-delay-cognitive-decline-memory-loss/`
- `https://cognitiontoday.com/memorization-techniques-to-improve-memory-for-facts/` *(present in top 10)*

## `therapy_001` — PARTIAL

**Question**: Therapy isn't working. What should I do?

**Expected URLs**:
- `https://cognitiontoday.com/7-reasons-why-psychotherapy-fails-for-many-people/`
- `https://cognitiontoday.com/mental-health-recovery-toolkit-diy-edition/`

**Top-5 reranked URLs**:
- [1] `https://cognitiontoday.com/ai-alignment-should-be-our-prime-concern/`
- [2] `https://cognitiontoday.com/7-reasons-why-psychotherapy-fails-for-many-people/` ✓
- [3] `https://cognitiontoday.com/nunchi-%eb%88%88%ec%b9%98-a-silent-skill-of-reading-the-room/`
- [4] `https://cognitiontoday.com/we-are-in-the-speed-economy-now-what/`
- [5] `https://cognitiontoday.com/the-value-of-productivity-will-be-its-beauty/`

**Concept-derived URLs**:
- [1] `https://cognitiontoday.com/7-reasons-why-psychotherapy-fails-for-many-people/` ✓
- [2] `https://cognitiontoday.com/psychology-career-options-in-india/`

**Missing from top 5**:
- `https://cognitiontoday.com/mental-health-recovery-toolkit-diy-edition/`

## `digital_wellbeing_001` — HIT

**Question**: I'm spending too much time online and not doing anything.

**Expected URLs**:
- `https://cognitiontoday.com/brainrot-reelationships-and-the-dm-verse/`
- `https://cognitiontoday.com/psychology-of-memes-advanced-emotions-outsourced-thoughts-mental-health/`
- `https://cognitiontoday.com/procrastinating-with-your-phone-reduce-procrastinatory-phone-dependence/`
- `https://cognitiontoday.com/phone-addiction-coping-solutions-research-statistics/`
- `https://cognitiontoday.com/effect-of-social-media-on-mental-health-well-being/`

**Top-5 reranked URLs**:
- [1] `https://cognitiontoday.com/examples-of-everyday-procrastination-mindsets-and-beliefs/`
- [2] `https://cognitiontoday.com/pros-and-cons-of-online-education-and-learning/`
- [3] `https://cognitiontoday.com/prospective-memory-explanation-and-how-to-build-it/`
- [4] `https://cognitiontoday.com/phone-addiction-coping-solutions-research-statistics/` ✓
- [5] `https://cognitiontoday.com/psychology-of-memes-advanced-emotions-outsourced-thoughts-mental-health/` ✓

**Concept-derived URLs**:
- [1] `https://cognitiontoday.com/pros-and-cons-of-online-education-and-learning/`
- [2] `https://cognitiontoday.com/how-you-use-social-media-mindfully-during-covid-19-lockdowns/`
- [3] `https://cognitiontoday.com/productivity-tips-for-early-career-employees/`
- [4] `https://cognitiontoday.com/procrastinating-with-your-phone-reduce-procrastinatory-phone-dependence/` ✓
- [5] `https://cognitiontoday.com/impulse-control-disorders-many-itches/`
- [6] `https://cognitiontoday.com/examples-of-everyday-procrastination-mindsets-and-beliefs/`

**Missing from top 5**:
- `https://cognitiontoday.com/brainrot-reelationships-and-the-dm-verse/`
- `https://cognitiontoday.com/procrastinating-with-your-phone-reduce-procrastinatory-phone-dependence/` *(present in top 10)*
- `https://cognitiontoday.com/effect-of-social-media-on-mental-health-well-being/`

## `mental_health_001` — MISS

**Question**: I've been feeling depressed, and I don't know what to do.
**Notes**: Sensitive topic — qualitative flag the answer for appropriate handling, not just retrieval accuracy.

**Expected URLs**:
- `https://cognitiontoday.com/why-you-are-consistently-unhappy/`
- `https://cognitiontoday.com/biophilia-sensory-contact-with-nature-can-improve-your-overall-well-being-mental-health/`
- `https://cognitiontoday.com/habits-patterns-that-degrade-mental-health/`
- `https://cognitiontoday.com/mental-health-recovery-toolkit-diy-edition/`

**Top-5 reranked URLs**:
- [1] `https://cognitiontoday.com/prospective-memory-explanation-and-how-to-build-it/`
- [2] `https://cognitiontoday.com/how-to-help-a-friend-with-depression-guide-and-examples/`
- [3] `https://cognitiontoday.com/15-things-to-not-say-to-depressed-people-and-why-you-shouldnt-say-them/`
- [4] `https://cognitiontoday.com/anatomy-of-human-skill/`
- [5] `https://cognitiontoday.com/chatgpt-answers-mental-health-questions/`

**Concept-derived URLs**:
- [1] `https://cognitiontoday.com/how-to-help-a-friend-with-depression-guide-and-examples/`
- [2] `https://cognitiontoday.com/simplifying-depression-a-serious-mental-health-issue/`
- [3] `https://cognitiontoday.com/how-i-broke-out-of-the-cycle-of-depression-guest-post/`
- [4] `https://cognitiontoday.com/15-things-to-not-say-to-depressed-people-and-why-you-shouldnt-say-them/`
- [5] `https://cognitiontoday.com/how-poor-mental-health-destroys-productivity/`

**Missing from top 5**:
- `https://cognitiontoday.com/why-you-are-consistently-unhappy/`
- `https://cognitiontoday.com/biophilia-sensory-contact-with-nature-can-improve-your-overall-well-being-mental-health/`
- `https://cognitiontoday.com/habits-patterns-that-degrade-mental-health/` *(present in top 10)*
- `https://cognitiontoday.com/mental-health-recovery-toolkit-diy-edition/`

## `psychology_001` — HIT

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
- [1] `https://cognitiontoday.com/consumer-psychology-for-marketers/` ✓
- [2] `https://cognitiontoday.com/tech-industry-careers-for-psychologists/`
- [3] `https://cognitiontoday.com/prospective-memory-explanation-and-how-to-build-it/`
- [4] `https://cognitiontoday.com/how-do-we-humanize-products-brands-science-branding-tips/` ✓
- [5] `https://cognitiontoday.com/psychology-career-options-in-india/`

**Concept-derived URLs**:
- [1] `https://cognitiontoday.com/consumer-psychology-for-marketers/` ✓
- [2] `https://cognitiontoday.com/14-career-skills-school-students-must-have-before-16/`
- [3] `https://cognitiontoday.com/psychology-career-options-in-india/`
- [4] `https://cognitiontoday.com/study-tips-for-psychology-students/`
- [5] `https://cognitiontoday.com/introduction/`
- [6] `https://cognitiontoday.com/top-future-proof-job-skills-psychology-students-need/`

**Missing from top 5**:
- `https://cognitiontoday.com/nudge-marketing-and-behavioral-engineering/`
- `https://cognitiontoday.com/how-and-why-looks-matter/`
- `https://cognitiontoday.com/smart-consumers-overcome-the-framing-effect/`
- `https://cognitiontoday.com/effort-heuristic-advertisement-marketing-psychology/`

