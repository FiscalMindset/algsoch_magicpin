import json
import os
import re
import hashlib
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

import httpx
from app.models import (
    CategoryContext,
    MerchantContext,
    TriggerContext,
    CustomerContext,
    ComposedMessage,
)


class ContextStore:
    """In-memory storage for contexts with versioning support."""

    def __init__(self):
        self.contexts: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.versions: Dict[Tuple[str, str], int] = {}

    def store_context(self, scope: str, context_id: str, version: int, payload: Dict[str, Any]) -> bool:
        """
        Store context with version checking.
        Returns True if stored, False if stale or same version.
        """
        key = (scope, context_id)
        current_version = self.versions.get(key, 0)

        if version <= current_version:
            return False

        self.contexts[key] = payload
        self.versions[key] = version
        return True

    def get_context(self, scope: str, context_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve context by scope and ID."""
        key = (scope, context_id)
        return self.contexts.get(key)

    def get_version(self, scope: str, context_id: str) -> int:
        """Get current version of a context."""
        key = (scope, context_id)
        return self.versions.get(key, 0)

    def get_contexts_count(self) -> Dict[str, int]:
        """Get count of loaded contexts by scope."""
        counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
        for (scope, _), _ in self.contexts.items():
            if scope in counts:
                counts[scope] += 1
        return counts

    def clear(self):
        """Clear all stored contexts."""
        self.contexts.clear()
        self.versions.clear()


class ConversationManager:
    """Manages active conversations and conversation state."""

    def __init__(self):
        self.conversations: Dict[str, list] = {}
        self.conversation_metadata: Dict[str, Dict[str, Any]] = {}

    def create_conversation(self, conversation_id: str, merchant_id: str, customer_id: Optional[str] = None) -> None:
        """Initialize a new conversation."""
        self.conversations[conversation_id] = []
        self.conversation_metadata[conversation_id] = {
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "created_at": datetime.utcnow().isoformat(),
            "turn_count": 0,
            "last_from_role": None,
            "status": "active",
        }

    def add_turn(self, conversation_id: str, from_role: str, message: str, turn_number: int) -> None:
        """Add a turn to a conversation."""
        if conversation_id not in self.conversations:
            return

        self.conversations[conversation_id].append(
            {
                "from_role": from_role,
                "message": message,
                "turn_number": turn_number,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        self.conversation_metadata[conversation_id]["turn_count"] = turn_number
        self.conversation_metadata[conversation_id]["last_from_role"] = from_role

    def get_conversation(self, conversation_id: str) -> Optional[list]:
        """Retrieve full conversation history."""
        return self.conversations.get(conversation_id)

    def get_conversation_context(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation metadata."""
        return self.conversation_metadata.get(conversation_id)

    def end_conversation(self, conversation_id: str) -> None:
        """Mark conversation as ended."""
        if conversation_id in self.conversation_metadata:
            self.conversation_metadata[conversation_id]["status"] = "ended"

    def detect_auto_reply(self, conversation_id: str) -> bool:
        """
        Detect if conversation has repeated auto-replies.
        Returns True if same message appears 3+ times.
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation or len(conversation) < 3:
            return False

        # Get last 5 messages from merchant
        merchant_messages = [
            turn["message"]
            for turn in conversation[-5:]
            if turn["from_role"] == "merchant"
        ]

        if len(merchant_messages) >= 3:
            # Check if same message repeats
            return len(set(merchant_messages[-3:])) == 1

        return False

    def get_all_conversations(self) -> Dict[str, list]:
        """Get all conversations."""
        return self.conversations


class CompositionService:
    """Service for composing messages using LLM."""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.provider = "template"
        self.groq_api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("VITE_GROQ_API_KEY")
        self.groq_model = os.environ.get("GROQ_MODEL", "llama-3.1-70b-versatile")
        if self.groq_api_key:
            self.provider = "groq"
        elif self.llm_client:
            self.provider = "anthropic"

    async def compose(
        self,
        category: Dict[str, Any],
        merchant: Dict[str, Any],
        trigger: Dict[str, Any],
        customer: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[list] = None,
        force_template: bool = False,
    ) -> ComposedMessage:
        """
        Compose a message using the 4-context framework.
        Integrates with LLM for intelligent composition.
        """
        # Build prompt with all contexts
        prompt = self._build_composition_prompt(
            category, merchant, trigger, customer, conversation_history
        )

        # Call LLM (using Anthropic Claude or similar)
        if self.groq_api_key and not force_template:
            response = await self._call_groq(prompt)
            message = self._parse_llm_response(response)
        elif self.llm_client and not force_template:
            response = await self._call_llm(prompt)
            message = self._parse_llm_response(response)
        else:
            # Fallback to template-based composition
            message = self._template_based_compose(category, merchant, trigger, customer)

        return message

    def _build_composition_prompt(
        self,
        category: Dict[str, Any],
        merchant: Dict[str, Any],
        trigger: Dict[str, Any],
        customer: Optional[Dict[str, Any]],
        conversation_history: Optional[list],
    ) -> str:
        """Build a detailed prompt for LLM composition."""
        prompt = f"""You are Vera, magicpin's AI merchant assistant. Compose a compelling WhatsApp message based on the following 4-context framework:

CATEGORY CONTEXT (Business vertical knowledge):
- Slug: {category.get('slug', 'N/A')}
- Voice: {category.get('voice', {})}
- Offers: {category.get('offer_catalog', [])}
- Peer Stats: {category.get('peer_stats', {})}
- Recent Digest: {category.get('digest', [])}
- Seasonal Context: {category.get('seasonal_beats', [])}

MERCHANT CONTEXT (Specific business state):
- Name: {merchant.get('identity', {}).get('name', 'N/A')}
- ID: {merchant.get('merchant_id', 'N/A')}
- City/Locality: {merchant.get('identity', {}).get('city', 'N/A')} / {merchant.get('identity', {}).get('locality', 'N/A')}
- Subscription: {merchant.get('subscription', {})}
- Performance (30d): Views={merchant.get('performance', {}).get('views', 0)}, Calls={merchant.get('performance', {}).get('calls', 0)}, CTR={merchant.get('performance', {}).get('ctr', 0)}
- Active Signals: {merchant.get('signals', [])}
- Languages: {merchant.get('identity', {}).get('languages', ['en'])}

TRIGGER CONTEXT (Why now):
- Type: {trigger.get('kind', 'N/A')}
- Scope: {trigger.get('scope', 'N/A')}
- Source: {trigger.get('source', 'N/A')}
- Details: {trigger.get('payload', {})}
- Urgency: {trigger.get('urgency', 1)}/5

"""
        if customer:
            prompt += f"""CUSTOMER CONTEXT (Customer state - for customer-facing messages):
- Name: {customer.get('identity', {}).get('name', 'N/A')}
- Relationship: {customer.get('relationship', {})}
- State: {customer.get('state', 'N/A')}
- Preferences: {customer.get('preferences', {})}

"""

        if conversation_history:
            prompt += f"""CONVERSATION HISTORY:
{json.dumps(conversation_history, indent=2)}

"""

        prompt += """REQUIREMENTS:
1. Specificity: Use concrete numbers, dates, or verifiable facts from the context
2. Category Fit: Match the voice, tone, and vocabulary of the business vertical
3. Merchant Personalization: Reference specific details about THIS merchant
4. Compulsion: Use one or more engagement levers (curiosity, social proof, loss aversion, effort externalization)
5. CTA: Single, binary call-to-action when appropriate
6. Length: Concise and readable for WhatsApp
7. Language: Match merchant's language preference
8. No Fabrication: Only use data provided in contexts

Respond in JSON format:
{
    "body": "The message text here",
    "cta": "open_ended|binary_yes_no|none",
    "send_as": "vera|merchant",
    "suppression_key": "unique_key_for_dedup",
    "rationale": "Why this message at this time"
}
"""
        return prompt

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM API."""
        if not self.llm_client:
            return ""

        try:
            message = self.llm_client.messages.create(
                model="claude-opus-4-7",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as e:
            print(f"LLM call failed: {e}")
            return ""

    async def _call_groq(self, prompt: str) -> str:
        """Call Groq's OpenAI-compatible chat completions API."""
        if not self.groq_api_key:
            return ""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.groq_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.groq_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0,
                        "max_tokens": 1024,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Groq call failed: {e}")
            return ""

    def _parse_llm_response(self, response: str) -> ComposedMessage:
        """Parse JSON response from LLM."""
        try:
            data = json.loads(response)
            return ComposedMessage(
                body=data.get("body", ""),
                cta=data.get("cta", "open_ended"),
                send_as=data.get("send_as", "vera"),
                suppression_key=data.get("suppression_key", ""),
                rationale=data.get("rationale", ""),
            )
        except json.JSONDecodeError:
            return self._template_based_compose({}, {}, {}, None)

    def _template_based_compose(
        self,
        category: Dict[str, Any],
        merchant: Dict[str, Any],
        trigger: Dict[str, Any],
        customer: Optional[Dict[str, Any]],
    ) -> ComposedMessage:
        """Deterministic, rubric-optimized composition (no hallucinations)."""

        def norm(s: Any) -> str:
            return str(s or "").strip()

        def lower(s: Any) -> str:
            return norm(s).lower()

        def first_nonempty(*vals: Any) -> str:
            for v in vals:
                if norm(v):
                    return norm(v)
            return ""

        def merchant_identity() -> Dict[str, Any]:
            return merchant.get("identity", {}) if isinstance(merchant, dict) else {}

        def customer_identity() -> Dict[str, Any]:
            return customer.get("identity", {}) if isinstance(customer, dict) else {}

        def pick_offer_title() -> Optional[str]:
            offers = merchant.get("offers") if isinstance(merchant, dict) else None
            if isinstance(offers, list) and offers:
                for o in offers:
                    if isinstance(o, dict) and o.get("title") and o.get("status", "active") == "active":
                        return o["title"]
                for o in offers:
                    if isinstance(o, dict) and o.get("title"):
                        return o["title"]
            cat_offers = category.get("offer_catalog") if isinstance(category, dict) else None
            if isinstance(cat_offers, list) and cat_offers:
                for o in cat_offers:
                    if isinstance(o, dict) and o.get("title"):
                        return o["title"]
            return None

        def taboo_sanitize(text: str) -> str:
            voice = category.get("voice", {}) if isinstance(category, dict) else {}
            taboos = voice.get("vocab_taboo") or voice.get("taboos") or []
            out = text
            for t in taboos:
                tt = norm(t)
                if not tt:
                    continue
                out = re.sub(re.escape(tt), "", out, flags=re.IGNORECASE)
            out = re.sub(r"[ \t]{2,}", " ", out).strip()
            return out

        def choose_language_code() -> str:
            c_lang = lower(customer_identity().get("language_pref"))
            if "hi" in c_lang and "mix" in c_lang:
                return "hi-en mix"
            if c_lang.startswith("hi"):
                return "hi"
            langs = merchant_identity().get("languages") or []
            langs_l = [lower(x) for x in langs if x]
            if "hi" in langs_l and "en" in langs_l:
                return "hi-en mix"
            if "hi" in langs_l:
                return "hi"
            return "en"

        def salutation(name: str, is_doctor: bool = False) -> str:
            if is_doctor:
                if name.lower().startswith("dr"):
                    return name
                return f"Dr. {name}" if name else "Doc"
            return f"Hi {name}" if name else "Hi"

        kind = norm(trigger.get("kind") if isinstance(trigger, dict) else "") or "update"
        scope = norm(trigger.get("scope") if isinstance(trigger, dict) else "") or "merchant"
        trig_payload = trigger.get("payload", {}) if isinstance(trigger, dict) else {}
        trig_id = norm(trigger.get("id") if isinstance(trigger, dict) else "")

        m_id = norm(merchant.get("merchant_id") if isinstance(merchant, dict) else "")
        m_name = norm(merchant_identity().get("name"))
        m_first = norm(merchant_identity().get("owner_first_name"))
        m_city = norm(merchant_identity().get("city"))
        m_loc = norm(merchant_identity().get("locality"))
        cat_slug = norm(category.get("slug") if isinstance(category, dict) else "") or norm(merchant.get("category_slug") if isinstance(merchant, dict) else "")

        is_doctor = cat_slug == "dentists" and bool(m_first)
        greet_name = first_nonempty(m_first, m_name)
        merchant_salute = salutation(greet_name, is_doctor=is_doctor)

        offer_title = pick_offer_title()
        perf = merchant.get("performance", {}) if isinstance(merchant, dict) else {}
        ctr = perf.get("ctr")
        peer = category.get("peer_stats", {}) if isinstance(category, dict) else {}
        peer_ctr = peer.get("avg_ctr")

        suppression_key = norm(trigger.get("suppression_key") if isinstance(trigger, dict) else "")
        if not suppression_key:
            base = f"{cat_slug}|{m_id}|{trig_id}|{kind}"
            suppression_key = hashlib.sha1(base.encode("utf-8")).hexdigest()[:24]

        body = ""
        cta = "open_ended"
        rationale = ""
        send_as = "vera" if scope == "merchant" else "merchant_on_behalf"

        # Customer-facing messages (strictly grounded; no invented slots/times)
        if scope == "customer":
            c_name = norm(customer_identity().get("name"))
            if not c_name:
                return ComposedMessage(
                    body="",
                    cta="none",
                    send_as="merchant_on_behalf",
                    suppression_key=suppression_key,
                    rationale="Customer scope trigger but customer context missing; skipping.",
                )

            hi = salutation(c_name, is_doctor=False)
            price_hint = offer_title or ""
            price_line = f" Offer: {price_hint}." if price_hint else ""

            if kind == "appointment_tomorrow":
                body = f"{hi} — {m_name} here. Reminder for your appointment tomorrow.{price_line}\nReply YES to confirm, or tell us a better time."
                cta = "binary_yes_no"
                rationale = "Appointment reminder to reduce no-shows; simple YES confirmation."
            elif kind == "recall_due":
                rel = customer.get("relationship", {}) if isinstance(customer, dict) else {}
                last_visit = norm(rel.get("last_visit"))
                body = (
                    f"{hi} — {m_name} here 🦷\n"
                    f"It’s been since {last_visit or 'your last visit'}. Want to book your next recall/cleaning?{price_line}\n"
                    f"Reply YES and we’ll share options. (Reply STOP to opt out.)"
                )
                cta = "binary_yes_no"
                rationale = "Recall trigger; warm reminder + grounded offer + opt-out."
            elif kind in ["customer_lapsed_hard", "winback_eligible", "trial_followup", "chronic_refill_due"]:
                if cat_slug == "pharmacies" and kind == "chronic_refill_due":
                    body = (
                        f"{hi} — {m_name} here.\n"
                        f"Refill reminder: want us to keep your regular meds ready for pickup/delivery?{price_line}\n"
                        f"Reply YES (or STOP to opt out)."
                    )
                    cta = "binary_yes_no"
                    rationale = "Chronic refill due; reduce friction and include opt-out."
                else:
                    body = (
                        f"{hi} — {m_name} here.\n"
                        f"Quick check-in: want to restart where you left off?{price_line}\n"
                        f"Reply YES and we’ll share options. (Reply STOP to opt out.)"
                    )
                    cta = "binary_yes_no"
                    rationale = "Winback/followup trigger; no guilt, simple YES/STOP CTA."
            else:
                rel = customer.get("relationship", {}) if isinstance(customer, dict) else {}
                last_visit = norm(rel.get("last_visit"))
                visits = rel.get("visits_total")
                services = rel.get("services_received", [])
                visit_line = f"Last visit: {last_visit}." if last_visit else ""
                visits_line = f"Total visits: {visits}." if visits else ""
                svc_line = f"Recent services: {', '.join(services[-2:])}." if services else ""
                context_lines = " ".join(x for x in [visit_line, visits_line, svc_line] if x)
                if context_lines:
                    body = (
                        f"{hi} — {m_name} here.\n"
                        f"{kind.replace('_', ' ')}: {context_lines}{price_line}\n"
                        f"Want to book or learn more? Reply YES for options. (Reply STOP to opt out.)"
                    )
                else:
                    body = f"{hi} — {m_name} here.\n{kind.replace('_', ' ')} update.{price_line}\nReply YES for details, or STOP to opt out."
                cta = "binary_yes_no"
                rationale = f"Generic customer {kind} trigger; grounded in relationship data where available."

            return ComposedMessage(
                body=taboo_sanitize(body),
                cta=cta,
                send_as="merchant_on_behalf",
                suppression_key=suppression_key,
                rationale=rationale,
            )

        # Merchant-facing rules by trigger.kind
        if kind == "research_digest":
            top_id = trig_payload.get("top_item_id")
            digest = category.get("digest", []) if isinstance(category, dict) else []
            item = None
            if top_id and isinstance(digest, list):
                for d in digest:
                    if isinstance(d, dict) and d.get("id") == top_id:
                        item = d
                        break
            title = item.get("title") if item else None
            source = item.get("source") if item else None
            trial_n = item.get("trial_n") if item else None
            bits = []
            if title:
                bits.append(title)
            if trial_n:
                bits.append(f"{trial_n}-patient trial")
            fact = " — ".join(bits) if bits else "New category update"
            body = (
                f"{merchant_salute}, quick research nugget for {m_loc or m_city}:\n"
                f"{fact}.\n"
                f"Want me to pull a 2‑min abstract + draft a WhatsApp you can forward to patients?"
            )
            if source:
                body += f"\n— {source}"
            cta = "open_ended"
            rationale = "Research digest trigger; source-cited nugget + low-friction CTA."

        elif kind == "perf_dip":
            metric = trig_payload.get("metric") or "calls"
            delta = trig_payload.get("delta_pct")
            window = trig_payload.get("window") or "7d"
            pct = int(round(float(delta) * 100)) if delta is not None else None
            dip_line = f"{metric} dipped {pct}% ({window})." if pct is not None else f"{metric} dipped ({window})."
            peer_line = ""
            if metric == "ctr" and peer_ctr and ctr is not None:
                peer_line = f"Your CTR {ctr:.3f} vs peer {peer_ctr:.3f}."
            offer_line = f"Offer to push: {offer_title}." if offer_title else ""
            body = (
                f"{merchant_salute} — {dip_line}\n"
                f"{peer_line} {offer_line}\n"
                f"Want me to draft 1 Google post + 1 WhatsApp reply to recover this week?"
            ).strip()
            cta = "binary_yes_no"
            rationale = "Perf dip trigger; acknowledge metric + propose concrete recovery assets."

        elif kind == "perf_spike":
            metric = trig_payload.get("metric") or "calls"
            delta = trig_payload.get("delta_pct")
            window = trig_payload.get("window") or "7d"
            pct = int(round(float(delta) * 100)) if delta is not None else None
            driver = trig_payload.get("likely_driver")
            spike_line = f"{metric} up +{pct}% ({window})." if pct is not None else f"{metric} up ({window})."
            driver_line = f"Likely driver: {driver}." if driver else ""
            body = (
                f"{merchant_salute} — nice! {spike_line} {driver_line}\n"
                f"Want me to double down with a follow-up post + pin a best offer on your listing?"
            ).strip()
            cta = "binary_yes_no"
            rationale = "Perf spike trigger; reinforce momentum with a low-effort next action."

        elif kind == "competitor_opened":
            cn = trig_payload.get("competitor_name") or "a competitor"
            dist = trig_payload.get("distance_km")
            their_offer = trig_payload.get("their_offer")
            opened = trig_payload.get("opened_date")
            dist_line = f"~{dist} km away" if dist is not None else "nearby"
            offer_line = f"They’re advertising: {their_offer}." if their_offer else ""
            our_offer = offer_title or "one strong service+price offer"
            body = (
                f"{merchant_salute} — heads-up: {cn} opened {dist_line} ({opened or 'recently'}).\n"
                f"{offer_line}\n"
                f"To stay ahead, I suggest we highlight {our_offer}. Want me to draft a 1-line hook + pricing copy for your listing?"
            ).strip()
            cta = "binary_yes_no"
            rationale = "Competitor trigger; propose grounded differentiation copy."

        elif kind == "review_theme_emerged":
            body = (
                f"{merchant_salute} — quick quality loop: a theme is repeating in reviews.\n"
                f"What’s the top 1 issue this week (wait time / pricing clarity / staff / hygiene)?\n"
                f"I’ll turn it into a response template + 1 listing tweak."
            )
            cta = "open_ended"
            rationale = "Review theme trigger; ask one concrete question and offer an immediate artifact."

        elif kind == "active_planning_intent":
            body = (
                f"{merchant_salute} — done. I’ll draft a starter package you can send.\n"
                f"Reply with 2 inputs: (1) your target price band, (2) weekday vs weekend.\n"
                f"I’ll send the final draft next."
            )
            cta = "open_ended"
            rationale = "Planning intent; switch to drafting with minimal clarifying inputs."

        elif kind in ["ipl_match_today", "festival_upcoming", "category_seasonal"]:
            offer_hint = offer_title or "one strong offer"
            body = (
                f"{merchant_salute} — campaign idea for {kind.replace('_',' ')}.\n"
                f"Let’s push {offer_hint}. I can draft:\n"
                f"1) Google post (120 chars)\n2) WhatsApp (4 lines)\n"
                f"Want me to draft it now?"
            )
            cta = "binary_yes_no"
            rationale = "Event/seasonal trigger; propose ready-to-use assets."

        elif kind == "seasonal_perf_dip":
            delta7 = perf.get("delta_7d", {}) if isinstance(perf, dict) else {}
            views_pct = delta7.get("views_pct")
            dip = f"{int(round(views_pct*100))}% views dip (7d)" if isinstance(views_pct, (int, float)) else "seasonal dip"
            body = (
                f"{merchant_salute} — you’re seeing a {dip}. This window is often seasonal.\n"
                f"Suggestion: focus retention + one offer refresh (no spam).\n"
                f"Want a retention WhatsApp draft?"
            )
            cta = "binary_yes_no"
            rationale = "Seasonal dip; reframe + propose retention action."

        elif kind in ["milestone_reached", "curious_ask_due"]:
            topic = norm(trig_payload.get("question_topic") or trig_payload.get("milestone"))
            topic_line = f" Topic: {topic.replace('_', ' ')}." if topic else ""
            offer_line = f" Push {offer_title}?" if offer_title else ""
            body = (
                f"{merchant_salute} 🎉 quick win!{topic_line}{offer_line}\n"
                f"Want me to draft a Google post + a 4-line WhatsApp reply for customers?"
            )
            cta = "open_ended"
            rationale = f"Milestone/curious ask{' about ' + topic if topic else ''}; offer immediate deliverable."

        elif kind in ["renewal_due", "trial_followup"]:
            sub = merchant.get("subscription", {}) if isinstance(merchant, dict) else {}
            status = sub.get("status")
            days = sub.get("days_remaining")
            body = (
                f"{merchant_salute} — your plan is {status or 'due'}"
                f"{f' (days left: {days})' if days is not None else ''}.\n"
                f"If you renew, I’ll set up: 1 weekly post + 1 offer refresh + quick reply templates.\n"
                f"Proceed?"
            )
            cta = "binary_yes_no"
            rationale = "Renewal/trial followup; clear value exchange + binary CTA."

        elif kind == "gbp_unverified":
            body = (
                f"{merchant_salute} — quick fix: your Google profile looks unverified.\n"
                f"Want me to guide you through the 2‑min verification steps?"
            )
            cta = "binary_yes_no"
            rationale = "GBP unverified; small action with high leverage."

        elif kind == "cde_opportunity":
            body = (
                f"{merchant_salute} — opportunity: you’re eligible for a local discovery boost.\n"
                f"To activate: 1 fresh post + 3 new photos this week.\n"
                f"Want me to draft the post and tell you which photos to upload?"
            )
            cta = "binary_yes_no"
            rationale = "CDE opportunity; convert into a concrete checklist."

        elif kind in ["regulation_change", "supply_alert"]:
            body = (
                f"{merchant_salute} — compliance heads-up ({kind.replace('_',' ')}).\n"
                f"I can summarize in 3 bullets + what to change in customer messaging.\n"
                f"Want the summary?"
            )
            cta = "binary_yes_no"
            rationale = "Compliance trigger; summary + actionable next step."

        elif kind == "wedding_package_followup":
            body = (
                f"{merchant_salute} — wedding-season follow-up idea.\n"
                f"Want me to draft a 3-tier package (basic/standard/premium) with clear prices you can forward?"
            )
            cta = "binary_yes_no"
            rationale = "Wedding followup; offer a ready-to-send tiered package draft."

        else:
            city = f"{m_loc}, {m_city}".strip(", ")
            payload_bits = []
            if isinstance(trig_payload, dict):
                for k, v in trig_payload.items():
                    if v is not None and k not in ("category",):
                        payload_bits.append(f"{k}: {v}")
            perf_lines = []
            if perf.get("views"):
                perf_lines.append(f"{perf['views']} views (30d)")
            if perf.get("calls"):
                perf_lines.append(f"{perf['calls']} calls")
            if perf.get("ctr") is not None:
                perf_lines.append(f"CTR {perf['ctr']*100:.1f}%")
            if peer_ctr and ctr is not None:
                if ctr < peer_ctr:
                    perf_lines.append(f"CTR below peer median ({peer_ctr*100:.1f}%)")
                else:
                    perf_lines.append(f"CTR above peer median ({peer_ctr*100:.1f}%)")
            offer_line = f"Active offer: {offer_title}." if offer_title else ""
            fact_lines = payload_bits + perf_lines
            if fact_lines:
                facts = " ".join(f"• {l}" for l in fact_lines[:4])
                body = (
                    f"{merchant_salute} — {kind.replace('_', ' ')} update{f' for {city}' if city else ''}.\n"
                    f"{facts}\n"
                    f"{offer_line}\n"
                    f"Want me to act on this? Reply YES and I'll draft next steps."
                )
            else:
                body = (
                    f"{merchant_salute} — {kind.replace('_', ' ')} update{f' for {city}' if city else ''}.\n"
                    f"{offer_line}\n"
                    f"Want me to draft a focused message using your best offer + one clear CTA?"
                )
            cta = "binary_yes_no"
            rationale = f"Generic {kind} trigger; grounded in available facts from trigger payload, merchant performance, and offers."

        return ComposedMessage(
            body=taboo_sanitize(body),
            cta=cta,
            send_as=send_as,
            suppression_key=suppression_key,
            rationale=rationale,
        )
