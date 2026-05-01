# MAGICPIN_FIX_ANALYSIS.md

**Date**: 2026-05-01  
**Author**: Algsoch AI  
**Status**: PHASE 1 — Analysis Complete

---

## 1. Architecture Overview

```
┌───────────────────────────────────────────────────────────────┐
│                     magicpin Judge Harness                     │
│   Pushes context → Calls /v1/tick → Plays merchant replies     │
└──────────────────────┬────────────────────────────────────────┘
                       │ HTTP/JSON
                       ▼
┌───────────────────────────────────────────────────────────────┐
│                    Candidate Bot (FastAPI)                     │
│                                                                │
│  POST /v1/context ──► ContextStore (in-memory, versioned)     │
│  POST /v1/tick    ──► TickResolver ──► CompositionService     │
│  POST /v1/reply   ──► ReplyRouter ──► IntentDispatcher        │
│  GET  /v1/healthz ──► BotState (uptime, context counts)       │
│  GET  /v1/metadata ──► Static identity response               │
└───────────────────────────────────────────────────────────────┘
```

### Core Components

| Component | File | Role |
|---|---|---|
| `ContextStore` | `backend/app/services/composition.py:18-61` | In-memory KV store with `(scope, context_id)` keys and version locking |
| `ConversationManager` | `backend/app/services/composition.py:64-137` | Tracks conversations, turns, auto-repetition detection |
| `CompositionService` | `backend/app/services/composition.py:139-670` | Message composition: LLM (Groq/Anthropic) or template fallback |
| `TickResolver` | `backend/app/routes/tick.py:37-153` | Decides which triggers to act on each tick |
| `ReplyRouter` | `backend/app/routes/reply.py:232-439` | Keyword/intent routing for merchant replies |
| `BotState` | `backend/app/services/state.py:5-27` | Global singleton holding all services + suppression keys |

### Data Flow

```
1. Judge POST /v1/context → ContextStore.store_context(scope, id, version, payload)
2. Judge POST /v1/tick → TickResolver iterates available_triggers
   → Loads trigger_ctx, merchant_ctx, category_ctx, customer_ctx
   → Calls CompositionService.compose(category, merchant, trigger, customer, force_template=True)
   → Returns actions[]
3. Judge POST /v1/reply → ReplyRouter routes by keyword matching
   → Falls back to CompositionService.compose(conversation_history=...)
   → Returns {action, body, cta, rationale}
```

---

## 2. Critical Architectural Flaws (Judge-Fatal)

### FLAW 1: `force_template=True` hardcoded — LLM never runs

**Files**: `tick.py:103`, `reply.py:428`

```python
# tick.py:103
composed = await bot_state.composition_service.compose(
    ...
    force_template=True,  # ← ALWAYS template, LLM bypassed
)
```

**Impact**: The `CompositionService` has Groq/Anthropic LLM support but `force_template=True` ensures it's never used. The template composer only handles ~15 hardcoded `trigger.kind` values. Any fresh/unseen trigger from the judge falls through to the generic `else` block (line 654-662), producing a bland, non-specific message.

**Fix**: Set `force_template=False` and let LLM run at `temperature=0`. Keep template as fallback only if LLM fails.

---

### FLAW 2: Template composer hardcodes `trigger.kind` — brittle pattern matching

**File**: `composition.py:388-662`

The `_template_based_compose` method uses a massive `if/elif` chain on `trigger.kind`:

```python
if kind == "research_digest": ...        # line 481
elif kind == "perf_dip": ...             # line 509
elif kind == "perf_spike": ...           # line 527
elif kind == "competitor_opened": ...    # line 541
elif kind == "review_theme_emerged": ... # line 558
elif kind == "active_planning_intent": ... # line 567
elif kind in ["ipl_match_today", "festival_upcoming", "category_seasonal"]: ... # line 576
elif kind == "seasonal_perf_dip": ...    # line 587
elif kind in ["milestone_reached", "curious_ask_due"]: ... # line 599
elif kind in ["renewal_due", "trial_followup"]: ... # line 607
elif kind == "gbp_unverified": ...       # line 620
elif kind == "cde_opportunity": ...      # line 628
elif kind in ["regulation_change", "supply_alert"]: ... # line 637
elif kind == "wedding_package_followup": ... # line 644
else: ...  # ← generic fallback for ALL unseen triggers
```

**Impact**: The judge injects **15 new triggers** mid-test (Phase 3). Any trigger kind not in this list gets the generic fallback: `"quick update for {city}. Trigger: {kind}. Want me to draft a focused message..."` — this is useless and scores 0 on specificity, groundedness, and category fit.

**Fix**: Replace pattern matching with a **generic 4-context grounding algorithm**:
1. Extract all factual slots from trigger.payload, merchant, category, customer
2. Apply safety gates (taboo words, consent, expiry)
3. Build message from actual context data, not trigger.kind
4. Use LLM only for polishing wording

---

### FLAW 3: Non-deterministic `conversation_id`

**File**: `tick.py:108`

```python
conversation_id = f"conv_{trigger_id}_{uuid.uuid4().hex[:8]}"
```

**Impact**: UUID changes every tick. Same input → different `conversation_id`. Judge expects deterministic behavior — same `/v1/tick` input must yield same action. UUID causes:
- Duplicate conversations for the same trigger
- Reply continuity breaks (judge can't find the conversation)
- Suppression key dedup may fail

**Fix**: Use deterministic ID: `f"conv:{merchant_id}:{trigger_id}"` (add `:{customer_id}` if customer scope).

---

### FLAW 4: `TickRequest` ignores `merchant_id` and `customer_id`

**File**: `tick.py:12-14`

```python
class TickRequest(BaseModel):
    now: datetime
    available_triggers: List[str] = []
    # ← Missing: merchant_id, customer_id (if judge sends them)
```

**Impact**: The tick resolver only uses `available_triggers`. If the judge sends merchant_id or customer_id in the tick request (as the testing brief allows), they're ignored. This means:
- No cross-scope linking from the tick request itself
- Relies entirely on trigger_ctx having correct merchant_id/customer_id
- If a trigger is missing merchant_id, it's silently skipped (line 72-73)

**Fix**: The testing brief's tick request only has `now` and `available_triggers`, so this is actually correct per spec. But the resolver should still validate and load linked contexts properly.

---

### FLAW 5: Suppression key uses SHA1 hash — non-deterministic across restarts

**File**: `composition.py:410-413`

```python
suppression_key = norm(trigger.get("suppression_key") if isinstance(trigger, dict) else "")
if not suppression_key:
    base = f"{cat_slug}|{m_id}|{trig_id}|{kind}"
    suppression_key = hashlib.sha1(base.encode("utf-8")).hexdigest()[:24]
```

**Impact**: SHA1 of the same string IS deterministic, so this is actually fine. But the `bot_state.sent_suppression_keys` set is in-memory and lost on restart. If the bot restarts between context push and tick, it will resend messages.

**Fix**: This is acceptable for the judge (no restarts during test). No change needed.

---

### FLAW 6: Customer-facing scope messages are hardcoded to dentist/pharmacy

**File**: `composition.py:421-478`

The `scope == "customer"` branch only handles specific trigger kinds:
- `appointment_tomorrow`
- `recall_due`
- `customer_lapsed_hard`, `winback_eligible`, `trial_followup`, `chronic_refill_due`

For any other customer-scope trigger, it falls to the generic:
```python
body = f"{hi} — {m_name} here.\nQuick update from us. Reply YES for details, or STOP to opt out."
```

**Impact**: Judge pushes **5 new customer contexts** mid-test with `recall_due` triggers. If the trigger kind is anything else (e.g., `appointment_cancelled`, `feedback_request`), the message is useless.

**Fix**: Generic customer-scope composer that extracts: customer name, merchant name, relationship context, any offer, and builds a grounded message regardless of trigger kind.

---

### FLAW 7: Metadata uses placeholder identity

**Expected**: Truthful team name, model, contact email.  
**Current**: Likely uses placeholder values (needs verification).

**Fix**: Update `metadata` endpoint with real `Algsoch AI` identity.

---

## 3. Failure Points (Judge Scoring Impact)

### 3.1 Zero-Action Ticks

**Trigger**: When all triggers are expired, missing merchant_id, or have been suppressed.

**Current behavior**: Returns `{"actions": []}` — this is **correct** per the testing brief ("Restraint is rewarded; spam is penalized").

**Risk**: If the template composer returns empty body (line 105-106: `if not composed.body: continue`), the action is dropped. With `force_template=True` and unseen trigger kinds, the generic fallback DOES produce a body, so this shouldn't cause zero actions — but the body quality will be terrible.

### 3.2 Expired Trigger Handling

**File**: `tick.py:58-65`

```python
exp = trigger_ctx.get("expires_at")
if exp and isinstance(exp, str) and request.now:
    exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
    if exp_dt <= request.now:
        continue
```

**Status**: ✅ **Correct**. Properly filters expired triggers.

### 3.3 Version Conflict Handling

**File**: `backend/app/routes/context.py` (not yet inspected)

**Expected**: `POST /v1/context` should reject stale versions with 409. Need to verify the implementation handles this correctly.

### 3.4 Auto-Reply Detection

**File**: `composition.py:112-132`

```python
def detect_auto_reply(self, conversation_id: str) -> bool:
    # Check if last 3 merchant messages are identical
    merchant_messages = [turn["message"] for turn in conversation[-5:] if turn["from_role"] == "merchant"]
    return len(set(merchant_messages[-3:])) == 1
```

**Status**: ⚠️ **Partial**. Detects exact repetition but doesn't handle WA Business auto-replies that vary slightly (e.g., "Thanks for your message" vs "Thank you for reaching out").

### 3.5 Repetition Detection in Reply

**File**: `reply.py:29-65`

```python
_last_response_bodies: Dict[str, str] = {}
def _check_repetition(conv_id: str, body: str) -> bool:
    return prev.strip() == body.strip()
```

**Status**: ⚠️ **Partial**. Only detects exact repetition. Judge Phase 4 tests for "same canned text 4 times in a row" — exact match works for that scenario. But slight variations would slip through.

---

## 4. Randomness Sources (Violate Determinism Requirement)

| Source | Location | Type | Impact |
|---|---|---|---|
| `uuid.uuid4()` | `tick.py:108` | UUID | Different `conversation_id` every tick |
| `datetime.utcnow()` | `composition.py:77,93` | Timestamp | `created_at` and `timestamp` in conversation metadata (not in API response, so OK) |
| LLM temperature | `composition.py:287` | `temperature=0.3` | Non-zero → non-deterministic output (only if `force_template=False`) |

**Verdict**: Only the UUID in `conversation_id` is a real problem. The timestamps are internal metadata (not part of the API response). LLM temperature needs to be set to `0` when enabled.

---

## 5. Context Store Analysis

### 5.1 Storage Mechanism

```python
self.contexts: Dict[Tuple[str, str], Dict[str, Any]] = {}  # (scope, context_id) -> payload
self.versions: Dict[Tuple[str, str], int] = {}             # (scope, context_id) -> version
```

### 5.2 Version Locking

```python
def store_context(self, scope, context_id, version, payload):
    current_version = self.versions.get(key, 0)
    if version <= current_version:
        return False  # Stale or duplicate
    self.contexts[key] = payload
    self.versions[key] = version
    return True
```

**Status**: ✅ **Correct**. Idempotent on `(context_id, version)`, higher versions replace atomically.

### 5.3 Cross-Scope Linking

The tick resolver loads linked contexts:

```python
merchant_ctx = bot_state.context_store.get_context("merchant", merchant_id) or {}
category_slug = merchant_ctx.get("category_slug")
category_ctx = bot_state.context_store.get_context("category", category_slug) if category_slug else {}
customer_ctx = bot_state.context_store.get_context("customer", customer_id) if customer_id else None
```

**Status**: ⚠️ **Partial**. Works when trigger has `merchant_id` and `customer_id`. But:
- No validation that merchant exists before proceeding
- No fallback if category_slug is missing
- Customer context only loaded if `trigger_ctx.get("customer_id")` exists (misses cases where customer context exists but trigger doesn't reference it)

### 5.4 Context Counting (for `/v1/healthz`)

```python
def get_contexts_count(self):
    counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
    for (scope, _), _ in self.contexts.items():
        if scope in counts:
            counts[scope] += 1
    return counts
```

**Status**: ✅ **Correct**. Matches the judge's warmup check.

---

## 6. Reply Engine Analysis

### 6.1 Intent Routing

The reply engine uses **keyword matching** on the incoming message:

```python
if any(k in msg_lower for k in ["offer", "my offer", ...]): ...
elif any(k in msg_lower for k in ["performance", "how am i doing", ...]): ...
elif any(k in msg_lower for k in ["hi", "hello", "hey", ...]): ...
elif any(k in msg_lower for k in ["gst", "tax", ...]): ...
elif any(k in msg_lower for k in ["profile", "google profile", ...]): ...
elif any(k in msg_lower for k in ["review", "rating", ...]): ...
elif any(m in msg_lower for m in commitment_markers): ...
elif msg_clean in ["yes", "sure", "ok", ...]: ...
elif msg_clean in ["no", "nope", "nah", ...]: ...
else: fallback to CompositionService.compose()
```

**Status**: ⚠️ **Partial**. Works for explicit keywords but fails on:
- Implicit intent ("What are my numbers?" → not matched by "performance" keywords)
- Multi-intent messages ("Show offers and how I'm doing")
- Objections that aren't hostile ("I don't have budget right now" → not caught)
- Questions requiring grounding ("Why is my CTR low?" → falls to generic composer)

### 6.2 Hostile/Stop Detection

```python
hostile_markers = ["stop", "unsubscribe", "useless", "spam", "don't message", ...]
if any(m in msg_lower for m in hostile_markers):
    return ReplyAction(action="end", ...)
```

**Status**: ✅ **Good coverage**. Includes common opt-out phrases.

### 6.3 Hindi/Hinglish Detection

```python
def _is_hindi(text: str) -> bool:
    return any('\u0900' <= c <= '\u097F' for c in text)

def _is_hinglish(text: str) -> bool:
    hi_markers = ["kya", "kaise", "kaisa", "kahan", "kab", "kyun", ...]
    return any(word in text_lower for word in hi_markers)
```

**Status**: ✅ **Reasonable**. Devanagari range + Hinglish keyword list. Could miss edge cases but good enough.

---

## 7. Exact Files Needing Changes

### PRIORITY 1 (Judge-Fatal)

| File | Lines | Change |
|---|---|---|
| `backend/app/routes/tick.py` | 12-14, 103, 108 | Add `merchant_id`/`customer_id` to request schema; set `force_template=False`; deterministic `conversation_id` |
| `backend/app/services/composition.py` | 152-181, 271-296, 312-670 | Enable LLM at temp=0; replace `_template_based_compose` with generic 4-context composer |
| `backend/app/routes/reply.py` | 412-430 | Set `force_template=False` for reply composition |

### PRIORITY 2 (Judge-Significant)

| File | Lines | Change |
|---|---|---|
| `backend/app/routes/reply.py` | 244-253 | Expand hostile/disinterest markers to include objections |
| `backend/app/routes/reply.py` | 382-395 | Handle objection repositioning ("not now" → "come back later") |
| `backend/app/services/composition.py` | 112-132 | Improve auto-reply detection to handle near-duplicates |
| `backend/app/routes/metadata.py` | All | Update with truthful Algsoch AI identity |

### PRIORITY 3 (Nice-to-Have)

| File | Lines | Change |
|---|---|---|
| `backend/app/services/composition.py` | 271-296 | Reduce Groq timeout from 30s to 10s |
| `backend/app/routes/tick.py` | 79-80 | Increase from 3 to 5 actions per tick (judge allows 20) |
| `backend/app/routes/context.py` | All | Add validation for malformed context payloads |

---

## 8. Proposed Fix Architecture

### 8.1 Generic 4-Context Composer (replaces `_template_based_compose`)

```
┌─────────────────────────────────────────────────────────────┐
│                  GenericComposer                            │
│                                                              │
│  1. FACT EXTRACTION                                          │
│     - Extract all factual slots from 4 contexts              │
│     - trigger.payload → facts about WHY NOW                  │
│     - merchant.identity → name, city, locality, languages    │
│     - merchant.performance → views, calls, CTR, delta        │
│     - category.peer_stats → benchmarks                       │
│     - category.offer_catalog → available offers              │
│     - customer.relationship → last_visit, services           │
│                                                              │
│  2. SAFETY GATES                                             │
│     - Taboo word filtering (category.voice.taboos)           │
│     - Consent check (customer.conent.scope)                  │
│     - Expiry check (trigger.expires_at)                      │
│     - Opt-out detection (customer.state == "opted_out")      │
│                                                              │
│  3. MESSAGE BUILDING                                         │
│     - Salutation: match language preference                  │
│     - Hook: trigger-specific (from payload facts)            │
│     - Body: grounded in merchant/customer data               │
│     - CTA: binary_yes_no for offers, open_ended for info     │
│     - Sign-off: category-appropriate                         │
│                                                              │
│  4. LLM POLISH (optional, temp=0)                            │
│     - Only polish wording, never invent facts               │
│     - Fallback to deterministic if LLM fails                │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Deterministic Tick Resolver

```
1. Load all triggers from available_triggers
2. For each trigger:
   a. Check expiry → skip if expired
   b. Check suppression_key → skip if already sent
   c. Load merchant_ctx → skip if missing
   d. Load category_ctx via merchant.category_slug
   e. Load customer_ctx if trigger.customer_id exists
3. Priority scoring:
   - urgency (desc) × recency (version) × engagement_potential
4. Sort by priority, take top 5
5. For each:
   a. Compose with GenericComposer
   b. Generate deterministic conversation_id
   c. Add to actions[]
6. Return actions[]
```

### 8.3 Improved Reply Engine

```
1. Safety checks: hostile → end, disinterest → end, later → wait
2. Auto-reply detection: near-duplicate → end
3. Intent classification (expanded keyword + pattern matching):
   - offers, performance, greeting, profile, reviews, commitment, yes, no
   - objection: "no budget", "not interested in this", "too expensive"
   - question: "why", "how", "what does" → ground in context
4. Objection repositioning:
   - "no budget" → reframe with free/low-cost option
   - "not now" → suggest timeline, set wait
   - "too expensive" → highlight ROI, peer comparison
5. Fallback: LLM composition with conversation history (temp=0)
```

---

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LLM timeout (>30s) | Medium | High | Reduce timeout to 10s, fallback to deterministic |
| LLM hallucination | Low | High | Temp=0, strict grounding, fact validation |
| Context store memory leak | Low | Medium | Not an issue for 60-min test window |
| Race condition on suppression_keys | Low | Medium | Single-threaded FastAPI, no concurrency |
| Judge sends malformed context | Medium | Low | Add validation, return 400 with reason |
| Bot restart during test | Low | Critical | Not expected; judge doesn't restart bots |

---

## 10. Test Strategy

### 10.1 Adversarial Probe Tests (15 tests)

1. **Fresh trigger kind** — send trigger with unknown `kind`, verify grounded message
2. **Expired trigger** — verify filtered out
3. **Missing merchant context** — verify no action sent
4. **Duplicate context push** — verify idempotent (409)
5. **Higher version update** — verify context updated
6. **Customer scope without customer context** — verify skipped
7. **Taboo word in output** — verify sanitized
8. **No triggers available** — verify empty actions
9. **Multiple triggers, priority ordering** — verify highest urgency first
10. **Conversation ID determinism** — same input → same conversation_id
11. **Auto-reply hell** — 4 identical replies → end conversation
12. **Hostile message** → end conversation
13. **Objection repositioning** — "no budget" → reframed offer
14. **Commitment transition** — "let's do it" → action plan, not more questions
15. **Metadata truthfulness** — verify Algsoch AI identity

### 10.2 Judge Simulator Tests

Run `judge_simulator.py` with `TEST_SCENARIO="all"` after fixes. Target: non-zero scores on all 5 dimensions.

---

## 11. Implementation Order

1. ✅ **This document** (PHASE 1)
2. **PHASE 2**: Rewrite `/v1/tick` resolver + deterministic IDs
3. **PHASE 3**: Replace `_template_based_compose` with generic 4-context composer
4. **PHASE 4**: Fix `/v1/reply` intent routing + objection handling
5. **PHASE 5**: Update metadata + healthz
6. **PHASE 6**: Create and run adversarial probe tests
7. **PHASE 7**: Run judge simulator, verify scores
8. **PHASE 8**: Write fix report + deployment checklist
