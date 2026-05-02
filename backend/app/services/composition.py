import json
import os
import re
import hashlib
from typing import Dict, Any, Optional, List, Tuple
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
        key = (scope, context_id)
        current_version = self.versions.get(key, 0)
        if version <= current_version:
            return False
        self.contexts[key] = payload
        self.versions[key] = version
        return True

    def get_context(self, scope: str, context_id: str) -> Optional[Dict[str, Any]]:
        return self.contexts.get((scope, context_id))

    def get_version(self, scope: str, context_id: str) -> int:
        return self.versions.get((scope, context_id), 0)

    def get_contexts_count(self) -> Dict[str, int]:
        counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
        for (scope, _), _ in self.contexts.items():
            if scope in counts:
                counts[scope] += 1
        return counts

    def clear(self):
        self.contexts.clear()
        self.versions.clear()


class ConversationManager:
    """Manages active conversations and conversation state."""

    def __init__(self):
        self.conversations: Dict[str, list] = {}
        self.conversation_metadata: Dict[str, Dict[str, Any]] = {}

    def create_conversation(self, conversation_id: str, merchant_id: str, customer_id: Optional[str] = None) -> None:
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
        if conversation_id not in self.conversations:
            return
        self.conversations[conversation_id].append({
            "from_role": from_role,
            "message": message,
            "turn_number": turn_number,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self.conversation_metadata[conversation_id]["turn_count"] = turn_number
        self.conversation_metadata[conversation_id]["last_from_role"] = from_role

    def get_conversation(self, conversation_id: str) -> Optional[list]:
        return self.conversations.get(conversation_id)

    def get_conversation_context(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        return self.conversation_metadata.get(conversation_id)

    def end_conversation(self, conversation_id: str) -> None:
        if conversation_id in self.conversation_metadata:
            self.conversation_metadata[conversation_id]["status"] = "ended"

    def detect_auto_reply(self, conversation_id: str) -> bool:
        conversation = self.get_conversation(conversation_id)
        if not conversation or len(conversation) < 3:
            return False
        merchant_messages = [
            turn["message"] for turn in conversation[-5:] if turn["from_role"] == "merchant"
        ]
        if len(merchant_messages) >= 3:
            return len(set(merchant_messages[-3:])) == 1
        return False

    def get_sent_messages(self, conversation_id: str) -> List[str]:
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return []
        return [turn["message"] for turn in conversation if turn.get("from_role") in ("vera", "bot", "assistant")]

    def get_all_conversations(self) -> Dict[str, list]:
        return self.conversations


# =============================================================================
# CATEGORY-SPECIFIC VOICE PROFILES
# =============================================================================

VOICE_PROFILES: Dict[str, Dict[str, Any]] = {
    "dentists": {
        "tone": "peer_clinical",
        "register": "respectful_collegial",
        "salutation": "Dr. {first_name}",
        "allowed_vocab": ["fluoride varnish", "scaling", "caries", "occlusion", "bruxism", "endodontic", "periodontal", "implant", "aligner", "veneer", "OPG", "IOPA", "RCT", "CAD/CAM", "zirconia", "PFM"],
        "taboos": ["guaranteed", "100% safe", "completely cure", "miracle", "best in city", "doctor approved"],
        "style_notes": "Sound like a colleague dentist, not a salesperson. Cite sources (JIDA, DCI, IDA). Use clinical terms naturally. Focus on patient outcomes and practice efficiency.",
        "cta_style": "Low-friction: 'Want the 2-min abstract?', 'Worth a look?'",
    },
    "salons": {
        "tone": "warm_professional",
        "register": "friendly_expert",
        "salutation": "Hi {first_name}",
        "allowed_vocab": ["haircut", "coloring", "balayage", "keratin", "facial", "bridal", "blowout", "trim", "styling"],
        "taboos": ["guaranteed", "best in city", "miracle", "100%"],
        "style_notes": "Warm, style-savvy tone. Use service+price format (e.g., 'Haircut @ ₹99'). Reference local trends and seasonal demand.",
        "cta_style": "Direct: 'Want me to set it up?', 'Shall I draft a post?'",
    },
    "restaurants": {
        "tone": "energetic_local",
        "register": "friendly_business",
        "salutation": "Hi {first_name}",
        "allowed_vocab": ["menu", "combo", "thali", "delivery", "dine-in", "special", "festival menu", "party order"],
        "taboos": ["guaranteed", "best in city", "finest", "world-class"],
        "style_notes": "Energetic, food-savvy tone. Reference local cuisine and neighborhood. Use combo+price format. Focus on footfall and delivery orders.",
        "cta_style": "Quick: 'Want me to set up a festival special post?', 'Shall I create a combo offer?'",
    },
    "gyms": {
        "tone": "motivational_professional",
        "register": "coach_like",
        "salutation": "Hi {first_name}",
        "allowed_vocab": ["membership", "personal training", "group class", "yoga", "HIIT", "weight loss", "transformation"],
        "taboos": ["guaranteed", "100% results", "miracle", "overnight"],
        "style_notes": "Motivational but professional. Reference fitness trends and seasonal spikes (New Year resolutions, summer prep). Use membership+price format.",
        "cta_style": "Action-oriented: 'Want me to launch the campaign?', 'Shall I set up the offer?'",
    },
    "pharmacies": {
        "tone": "trustworthy_helpful",
        "register": "professional_care",
        "salutation": "Hi {first_name}",
        "allowed_vocab": ["prescription", "refill", "generic", "OTC", "wellness", "consultation", "home delivery", "chronic"],
        "taboos": ["guaranteed", "cure", "miracle", "100% safe", "best prices"],
        "style_notes": "Trustworthy, helpful tone. Focus on patient care and convenience. Reference health awareness days and seasonal needs. Use service+price format.",
        "cta_style": "Gentle: 'Want me to set up a reminder campaign?', 'Shall I create a wellness offer?'",
    },
}


# =============================================================================
# COMPOSITION SERVICE
# =============================================================================

class CompositionService:
    """Service for composing messages using LLM with template fallback."""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.provider = "template"
        self.groq_api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("VITE_GROQ_API_KEY")
        self.groq_model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
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
        """Compose a message using the 4-context framework with LLM."""
        prompt = self._build_composition_prompt(category, merchant, trigger, customer, conversation_history)

        if self.groq_api_key and not force_template:
            response = await self._call_groq(prompt)
            if response:
                message = self._parse_llm_response(response)
                if message.body:
                    validated = self._validate_and_fix(message, category, merchant, trigger, conversation_history)
                    if validated.body:
                        return validated
            return self._template_based_compose(category, merchant, trigger, customer, conversation_history)

        elif self.llm_client and not force_template:
            response = await self._call_llm(prompt)
            if response:
                message = self._parse_llm_response(response)
                if message.body:
                    validated = self._validate_and_fix(message, category, merchant, trigger, conversation_history)
                    if validated.body:
                        return validated
            return self._template_based_compose(category, merchant, trigger, customer, conversation_history)

        else:
            return self._template_based_compose(category, merchant, trigger, customer, conversation_history)

    def _get_voice_profile(self, category: Dict[str, Any]) -> Dict[str, Any]:
        cat_slug = (category.get("slug") or "").lower()
        if cat_slug in VOICE_PROFILES:
            return VOICE_PROFILES[cat_slug]
        cat_voice = category.get("voice", {})
        return {
            "tone": cat_voice.get("tone", "professional"),
            "register": cat_voice.get("register", "professional"),
            "salutation": cat_voice.get("salutation_examples", ["Hi {first_name}"])[0] if isinstance(cat_voice.get("salutation_examples"), list) else "Hi {first_name}",
            "allowed_vocab": cat_voice.get("vocab_allowed", []),
            "taboos": cat_voice.get("vocab_taboo", cat_voice.get("taboos", [])),
            "style_notes": cat_voice.get("style_notes", "Professional, helpful tone."),
            "cta_style": "Clear, single call-to-action.",
        }

    def _build_composition_prompt(
        self,
        category: Dict[str, Any],
        merchant: Dict[str, Any],
        trigger: Dict[str, Any],
        customer: Optional[Dict[str, Any]],
        conversation_history: Optional[list],
    ) -> str:
        """Build a detailed prompt for LLM composition."""
        voice = self._get_voice_profile(category)
        cat_slug = category.get("slug", "N/A")
        identity = merchant.get("identity", {})
        m_name = identity.get("name", "N/A")
        m_first = identity.get("owner_first_name", "")
        m_city = identity.get("city", "")
        m_loc = identity.get("locality", "")
        m_langs = identity.get("languages", ["en"])
        perf = merchant.get("performance", {})
        sub = merchant.get("subscription", {})
        signals = merchant.get("signals", [])
        offers = merchant.get("offers", [])
        peer = category.get("peer_stats", {})
        digest = category.get("digest", [])
        seasonal = category.get("seasonal_beats", [])
        trends = category.get("trend_signals", [])
        offers_catalog = category.get("offer_catalog", [])
        active_titles = [o.get("title") for o in offers if isinstance(o, dict) and o.get("status") == "active"]
        catalog_titles = [o.get("title") for o in offers_catalog if isinstance(o, dict) and o.get("title")]
        t_kind = trigger.get("kind", "update")
        t_scope = trigger.get("scope", "merchant")
        t_payload = trigger.get("payload", {})
        t_urgency = trigger.get("urgency", 3)

        prompt = f"""You are Vera, magicpin's AI merchant assistant. Compose ONE WhatsApp message.

CATEGORY: {cat_slug} | Tone: {voice['tone']} | Style: {voice['style_notes']}
Merchant: {m_name} ({m_first}) | {m_loc}, {m_city} | Languages: {', '.join(m_langs)}
Plan: {sub.get('plan', 'N/A')} ({sub.get('status', 'N/A')}, {sub.get('days_remaining', '?')} days)
Performance (30d): {perf.get('views', 0)} views, {perf.get('calls', 0)} calls, CTR {perf.get('ctr', 0)*100:.1f}%
7d delta: views {perf.get('delta_7d', {}).get('views_pct', 0)*100:.0f}%, calls {perf.get('delta_7d', {}).get('calls_pct', 0)*100:.0f}%
Active offers: {', '.join(active_titles) if active_titles else 'None'}
Signals: {', '.join(signals[:5])}
Peer: {json.dumps(peer, indent=2)}
Trigger: {t_kind} (urgency {t_urgency}/5) | Details: {json.dumps(t_payload, indent=2)}
"""
        if customer:
            c_identity = customer.get("identity", {})
            c_rel = customer.get("relationship", {})
            prompt += f"""Customer: {c_identity.get('name', 'N/A')} | Lang: {c_identity.get('language_pref', 'en')}
Last visit: {c_rel.get('last_visit', 'N/A')} | Visits: {c_rel.get('visits_total', '?')}
Services: {', '.join(c_rel.get('services_received', []))}
"""
        if conversation_history:
            history_summary = []
            for turn in conversation_history[-4:]:
                role = turn.get("from_role", turn.get("from", "?"))
                body = turn.get("message", turn.get("body", ""))
                history_summary.append(f"  {role}: {body[:80]}")
            prompt += f"\nRecent conversation:\n" + "\n".join(history_summary) + "\n"

        prompt += """
RULES:
1. SPECIFICITY: Use concrete numbers, dates, facts from context. NEVER invent data.
2. CATEGORY FIT: Match tone/vocab for this vertical. NEVER use retail-promo tone for clinical categories.
3. MERCHANT PERSONALIZATION: Reference THIS merchant's name, location, performance, offers, signals.
4. TRIGGER RELEVANCE: Clearly communicate WHY NOW.
5. ENGAGEMENT: Use 1-2 levers: social proof, loss aversion, curiosity, effort externalization.
6. CTA: ONE clear call-to-action. Binary (YES/STOP) for action triggers.
7. LENGTH: Concise for WhatsApp (80-200 chars ideal, max 400).
8. NO FABRICATION: Only use data in contexts.
9. SERVICE+PRICE FORMAT: Use "Service @ ₹Price" format.
10. ANTI-REPETITION: Do NOT repeat recent conversation turns.

JSON only:
{"body": "...", "cta": "binary_yes_no"|"open_ended"|"none", "send_as": "vera"|"merchant_on_behalf", "suppression_key": "...", "rationale": "..."}
"""
        return prompt

    async def _call_groq(self, prompt: str) -> str:
        if not self.groq_api_key:
            return ""
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.groq_api_key}", "Content-Type": "application/json"},
                    json={"model": self.groq_model, "messages": [{"role": "user", "content": prompt}], "temperature": 0, "max_tokens": 512},
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Groq call failed: {e}")
            return ""

    async def _call_llm(self, prompt: str) -> str:
        if not self.llm_client:
            return ""
        try:
            message = self.llm_client.messages.create(model="claude-opus-4-7", max_tokens=1024, messages=[{"role": "user", "content": prompt}])
            return message.content[0].text
        except Exception as e:
            print(f"LLM call failed: {e}")
            return ""

    def _parse_llm_response(self, response: str) -> ComposedMessage:
        try:
            data = json.loads(response)
            return ComposedMessage(body=data.get("body", ""), cta=data.get("cta", "open_ended"), send_as=data.get("send_as", "vera"), suppression_key=data.get("suppression_key", ""), rationale=data.get("rationale", ""))
        except json.JSONDecodeError:
            pass
        import re
        for pattern in [r'```(?:json)?\s*(\{.*?\})\s*```', r'(\{[^{}]*\})']:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    return ComposedMessage(body=data.get("body", ""), cta=data.get("cta", "open_ended"), send_as=data.get("send_as", "vera"), suppression_key=data.get("suppression_key", ""), rationale=data.get("rationale", ""))
                except json.JSONDecodeError:
                    pass
        start = response.find('{')
        end = response.rfind('}')
        if start >= 0 and end > start:
            try:
                data = json.loads(response[start:end+1])
                return ComposedMessage(body=data.get("body", ""), cta=data.get("cta", "open_ended"), send_as=data.get("send_as", "vera"), suppression_key=data.get("suppression_key", ""), rationale=data.get("rationale", ""))
            except json.JSONDecodeError:
                pass
        return ComposedMessage(body="", cta="open_ended", send_as="vera", suppression_key="", rationale="LLM response not valid JSON")

    def _validate_and_fix(self, message, category, merchant, trigger, conversation_history):
        body = message.body
        if not body:
            return message
        voice = category.get("voice", {}) if isinstance(category, dict) else {}
        taboos = voice.get("vocab_taboo", voice.get("taboos", []))
        for t in taboos:
            t_lower = t.lower().strip()
            if t_lower and t_lower in body.lower():
                body = re.sub(re.escape(t_lower), "", body, flags=re.IGNORECASE)
                body = re.sub(r"[ \t]{2,}", " ", body).strip()
        cta_count = body.lower().count("reply") + body.lower().count("want me") + body.lower().count("shall i")
        if cta_count > 2:
            last_reply = body.lower().rfind("reply")
            last_want = body.lower().rfind("want")
            cutoff = max(last_reply, last_want)
            if cutoff > 0:
                sentence_start = body.rfind("\n", 0, cutoff)
                if sentence_start < 0:
                    sentence_start = body.rfind(". ", 0, cutoff)
                if sentence_start > 0:
                    body = body[sentence_start+2:]
        return ComposedMessage(body=body, cta=message.cta, send_as=message.send_as, suppression_key=message.suppression_key, rationale=message.rationale)

    def _template_based_compose(
        self,
        category: Dict[str, Any],
        merchant: Dict[str, Any],
        trigger: Dict[str, Any],
        customer: Optional[Dict[str, Any]],
        conversation_history: Optional[list],
    ) -> ComposedMessage:
        """Deterministic, rubric-optimized template composition."""

        def norm(s): return str(s or "").strip()
        def lower(s): return norm(s).lower()
        def first_nonempty(*vals):
            for v in vals:
                if norm(v): return norm(v)
            return ""

        def merchant_identity(): return merchant.get("identity", {}) if isinstance(merchant, dict) else {}
        def customer_identity(): return customer.get("identity", {}) if isinstance(customer, dict) else {}

        def pick_offer_title():
            offers = merchant.get("offers") if isinstance(merchant, dict) else None
            if isinstance(offers, list) and offers:
                for o in offers:
                    if isinstance(o, dict) and o.get("title") and o.get("status", "active") == "active": return o["title"]
                for o in offers:
                    if isinstance(o, dict) and o.get("title"): return o["title"]
            cat_offers = category.get("offer_catalog") if isinstance(category, dict) else None
            if isinstance(cat_offers, list) and cat_offers:
                for o in cat_offers:
                    if isinstance(o, dict) and o.get("title"): return o["title"]
            return None

        def taboo_sanitize(text):
            voice = category.get("voice", {}) if isinstance(category, dict) else {}
            taboos = voice.get("vocab_taboo") or voice.get("taboos") or []
            out = text
            for t in taboos:
                tt = norm(t)
                if tt: out = re.sub(re.escape(tt), "", out, flags=re.IGNORECASE)
            out = re.sub(r"[ \t]{2,}", " ", out).strip()
            return out

        def salutation(name, is_doctor=False):
            if is_doctor:
                if name.lower().startswith("dr"): return name
                return f"Dr. {name}" if name else "Doc"
            if "(parent:" in name:
                parent_name = name.split("(parent:")[-1].strip().rstrip(")")
                return f"Hi {parent_name}" if parent_name else "Hi"
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
        if is_doctor and m_name:
            is_doctor = m_name.lower().startswith("dr.")
        greet_name = first_nonempty(m_first, m_name)
        merchant_salute = salutation(greet_name, is_doctor=is_doctor)
        offer_title = pick_offer_title()
        perf = merchant.get("performance", {}) if isinstance(merchant, dict) else {}
        ctr = perf.get("ctr")
        peer = category.get("peer_stats", {}) if isinstance(category, dict) else {}
        peer_ctr = peer.get("avg_ctr")
        cust_agg = merchant.get("customer_aggregate", {}) if isinstance(merchant, dict) else {}
        signals = merchant.get("signals", []) if isinstance(merchant, dict) else []

        suppression_key = norm(trigger.get("suppression_key") if isinstance(trigger, dict) else "")
        if not suppression_key:
            base = f"{cat_slug}|{m_id}|{trig_id}|{kind}"
            suppression_key = hashlib.sha1(base.encode("utf-8")).hexdigest()[:24]

        body = ""
        cta = "open_ended"
        rationale = ""
        send_as = "vera" if scope == "merchant" else "merchant_on_behalf"

        # ── Helper: peer comparison line ──
        def peer_line_for(metric_name, current_val, peer_key=None):
            pk = peer_key or f"avg_{metric_name}"
            peer_val = peer.get(pk)
            if peer_val is None: return ""
            if isinstance(current_val, (int, float)) and current_val > 0:
                pct_diff = ((current_val - peer_val) / peer_val) * 100
                if pct_diff < -10: return f" ({cat_slug} avg in {m_city}: {peer_val} — you're {abs(int(pct_diff))}% below)"
                elif pct_diff > 10: return f" ({cat_slug} avg in {m_city}: {peer_val} — you're {int(pct_diff)}% above)"
                else: return f" (peer avg: {peer_val})"
            return f" (peer avg: {peer_val})"

        def recovery_estimate(base_pct=None):
            if isinstance(peer, dict):
                adoption = peer.get("campaign_adoption_rate")
                if adoption: return f"{int(round(adoption * 100))}% of {cat_slug} in {m_city or 'your area'} are already acting on this"
                ret = peer.get("retention_6mo_pct")
                if ret and base_pct: return f"Peers with similar profiles recover ~{max(10, base_pct // 2)}% within 2 weeks"
            return f"Peers who act on this see measurable recovery within 7-14 days"

        # ── Customer-facing messages ──
        if scope == "customer":
            c_name = norm(customer_identity().get("name"))
            if not c_name:
                return ComposedMessage(body="", cta="none", send_as="merchant_on_behalf", suppression_key=suppression_key, rationale="Customer scope trigger but customer context missing.")

            hi = salutation(c_name, is_doctor=False)
            price_hint = offer_title or ""
            price_line = f" Offer: {price_hint}." if price_hint else ""
            rel = customer.get("relationship", {}) if isinstance(customer, dict) else {}
            services = rel.get("services_received", [])
            svc_line = f" (last: {', '.join(services[-2:])})" if services else ""

            if kind == "appointment_tomorrow":
                loc_hint = f" ({m_loc})" if m_loc else ""
                body = f"{hi} — {m_name}{loc_hint} here. Reminder for your appointment tomorrow.{price_line}\nReply YES to confirm, or tell us a better time."
                cta = "binary_yes_no"
                rationale = "Appointment reminder to reduce no-shows."
            elif kind == "recall_due":
                last_visit = norm(rel.get("last_visit"))
                months_ago = ""
                if last_visit:
                    try:
                        lv = datetime.fromisoformat(last_visit.replace("Z", "+00:00"))
                        months = max(1, int((datetime.now(timezone.utc) - lv).days / 30))
                        months_ago = f" ({months} months ago)"
                    except: pass
                loc_hint = f" ({m_loc})" if m_loc else ""
                body = f"{hi} — {m_name}{loc_hint} here.\nIt's been {months_ago or 'a while'} since your last visit{f' on {last_visit[:10]}' if last_visit else ''}. Want to book your next recall/cleaning?{price_line}\nReply YES and we'll share slots. (Reply STOP to opt out.)"
                cta = "binary_yes_no"
                rationale = "Recall trigger; warm reminder + grounded offer + opt-out."
            elif kind == "chronic_refill_due":
                loc_hint = f" ({m_loc})" if m_loc else ""
                body = f"{hi} — {m_name}{loc_hint} here.\nRefill reminder: want us to keep your regular meds ready for pickup/delivery?{price_line}\nReply YES (or STOP to opt out)."
                cta = "binary_yes_no"
                rationale = "Chronic refill due."
            elif kind in ["customer_lapsed_hard", "winback_eligible"]:
                visits = rel.get("visits_total", 0)
                visits_line = f" You've been with us for {visits} visits." if visits > 2 else ""
                clean_services = []
                for s in services[-2:]:
                    clean = s.replace("_", " ").replace("x4", "").replace("x12", "").strip()
                    if clean: clean_services.append(clean)
                svc_display = f" (last: {', '.join(clean_services)})" if clean_services else ""
                loc_hint = f" ({m_loc})" if m_loc else ""
                body = f"{hi} — {m_name}{loc_hint} here.{svc_display}{visits_line}\nWe'd love to have you back!{price_line}\nReply YES for current options, or STOP to opt out."
                cta = "binary_yes_no"
                rationale = "Winback; warm re-engagement."
            elif kind == "trial_followup":
                trial_date = trig_payload.get("trial_date")
                next_options = trig_payload.get("next_session_options", [])
                date_note = f" Your trial session was on {trial_date[:10]}." if trial_date else ""
                slot_line = ""
                if isinstance(next_options, list) and len(next_options) > 0:
                    first_slot = next_options[0].get("label", "") if isinstance(next_options[0], dict) else ""
                    if first_slot: slot_line = f" Next available: {first_slot}."
                clean_services = []
                for s in services[-1:]:
                    clean = s.replace("_", " ").strip()
                    if clean: clean_services.append(clean)
                svc_display = f" Thanks for trying our {clean_services[0]}!" if clean_services else ""
                loc_hint = f" ({m_loc})" if m_loc else ""
                body = f"{hi} — {m_name}{loc_hint} here.{svc_display}{date_note}{slot_line}\nWant to continue? Reply YES for available slots. (Reply STOP to opt out.)"
                cta = "binary_yes_no"
                rationale = "Trial followup; feedback + next booking."
            elif kind == "wedding_package_followup":
                days_to_wedding = trig_payload.get("days_to_wedding")
                trial_completed = trig_payload.get("trial_completed")
                timing = ""
                if days_to_wedding: timing = f"{days_to_wedding} days to your big day — "
                trial_note = ""
                if trial_completed: trial_note = f"Your bridal trial is complete — "
                loc_hint = f" ({m_loc})" if m_loc else ""
                body = f"{hi} — {m_name}{loc_hint} here. {timing}{trial_note}Ready to finalize your bridal package?{price_line}\nReply YES to book your consultation, or STOP to opt out."
                cta = "binary_yes_no"
                rationale = "Wedding followup; timing-aware CTA."
            else:
                last_visit = norm(rel.get("last_visit"))
                visits = rel.get("visits_total")
                visit_line = f"Last visit: {last_visit}." if last_visit else ""
                visits_line = f"Total visits: {visits}." if visits else ""
                svc_line2 = f"Recent: {', '.join(services[-2:])}." if services else ""
                context_lines = " ".join(x for x in [visit_line, visits_line, svc_line2] if x)
                loc_hint = f" ({m_loc})" if m_loc else ""
                if context_lines:
                    body = f"{hi} — {m_name}{loc_hint} here.\n{context_lines}{price_line}\nWant to book? Reply YES for options. (Reply STOP to opt out.)"
                else:
                    body = f"{hi} — {m_name}{loc_hint} here.{price_line}\nReply YES for details, or STOP to opt out."
                cta = "binary_yes_no"
                rationale = f"Customer {kind} trigger."

            return ComposedMessage(body=taboo_sanitize(body), cta=cta, send_as="merchant_on_behalf", suppression_key=suppression_key, rationale=rationale)

        # ── Merchant-facing rules ──
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
            effect = item.get("effect_size") if item else None
            patient_segment = item.get("patient_segment") if item else None
            summary = item.get("summary") if item else None
            actionable = item.get("actionable") if item else None
            bits = []
            if title: bits.append(title)
            if trial_n: bits.append(f"{trial_n}-patient trial")
            if effect: bits.append(f"effect: {effect}")
            fact = " — ".join(bits) if bits else "New research available"
            segment_line = ""
            if patient_segment:
                seg_display = patient_segment.replace("_", " ")
                high_risk = cust_agg.get("high_risk_adult_count")
                if high_risk and ("high_risk" in patient_segment or ("high" in patient_segment and "risk" in patient_segment)):
                    segment_line = f" You have {high_risk} high-risk patients who could benefit."
                else:
                    segment_line = f" Relevant to your {seg_display} segment."
            social_proof = ""
            if peer.get("avg_views_30d") and perf.get("views"):
                views = perf.get("views", 0)
                avg_views = peer.get("avg_views_30d", 0)
                if views >= avg_views:
                    loc_ref = f" in {m_city}" if m_city else ""
                    social_proof = f" With {views} profile views/month{loc_ref}, your patients are already looking — this positions you ahead of peers."
            loc_ref = f", {m_loc}" if m_loc else ""
            body = f"{merchant_salute}{loc_ref} — {fact}.{segment_line}{social_proof}"
            if source: body += f"\n— {source}"
            if actionable: body += f"\nAction: {actionable}"
            body += "\nWant the 2-min abstract + a ready-to-forward patient message?"
            cta = "binary_yes_no"
            rationale = f"Research digest; grounded facts + merchant-specific segment match + low-friction CTA."

        elif kind == "perf_dip":
            metric = trig_payload.get("metric") or "calls"
            delta = trig_payload.get("delta_pct")
            window = trig_payload.get("window") or "7d"
            pct = int(round(float(delta) * 100)) if delta is not None else None
            current_val = perf.get(metric) if metric in perf else None
            vs_baseline = trig_payload.get("vs_baseline")
            clinic_name = m_name if m_name else "your listing"
            loc_line = f", {m_loc}" if m_loc else ""
            if pct is not None:
                curr = current_val if current_val is not None else "your baseline"
                dip_line = f"{metric} at {clinic_name}{loc_line} dropped to {curr} — down {abs(pct)}% vs last {window}"
            else:
                dip_line = f"{metric} at {clinic_name}{loc_line} dipped ({window})"
            loss_line = ""
            if vs_baseline and pct:
                lost_per_week = max(1, int(abs(pct) / 100 * vs_baseline))
                loss_line = f" That's ~{lost_per_week} fewer {metric}/week — roughly {lost_per_week * 4} lost this month if unaddressed."
            elif current_val and pct:
                prev_val = int(current_val / (1 + delta)) if delta else current_val
                loss_line = f" That's ~{prev_val - current_val} fewer {metric}/week."
            peer_line = ""
            if metric == "ctr" and peer_ctr and ctr is not None:
                peer_line = f" ({cat_slug} avg in {m_city}: {peer_ctr*100:.1f}% CTR)"
            elif pct is not None and abs(pct) >= 20:
                peer_line = f" — {cat_slug} across {m_city or 'the city'} held steady"
            elif m_city:
                peer_line = f" — {cat_slug} across {m_city} held steady"
            recovery_line = ""
            target = clinic_name or "your listing"
            if offer_title and pct:
                recovery = max(5, abs(pct) // 3)
                recovery_line = f"\n{recovery_estimate(abs(pct))}.\nLaunching '{offer_title}' at {target} typically recovers ~{recovery}%.\nShall I draft a recovery WhatsApp + Google post for you to review?"
            else:
                cat_offers = category.get("offer_catalog", []) if isinstance(category, dict) else []
                cat_offer = None
                for o in cat_offers:
                    if isinstance(o, dict) and o.get("title"):
                        cat_offer = o["title"]
                        break
                if cat_offer:
                    recovery_line = f"\n{recovery_estimate(abs(pct) if pct else 20)}.\nSetting up '{cat_offer}' at {target} could recover ~{max(10, abs(pct)//2 if pct else 15)}%.\nWant me to activate it + draft a recovery post?"
                else:
                    recovery_line = f"\n{recovery_estimate(abs(pct) if pct else 20)}.\nA quick GBP refresh for {target} can recover ~{max(10, abs(pct)//2 if pct else 15)}%.\nWant me to draft a recovery post?"
            body = f"{merchant_salute} — heads up: {dip_line}.{loss_line}{peer_line}{recovery_line}"
            cta = "binary_yes_no"
            rationale = f"Perf dip; urgency + quantified loss + merchant-specific recovery path + social proof."

        elif kind == "perf_spike":
            metric = trig_payload.get("metric") or "calls"
            delta = trig_payload.get("delta_pct")
            window = trig_payload.get("window") or "7d"
            pct = int(round(float(delta) * 100)) if delta is not None else None
            driver = trig_payload.get("likely_driver")
            vs_baseline = trig_payload.get("vs_baseline")
            clinic_name = m_name or "your listing"
            loc_line = f", {m_loc}" if m_loc else ""
            spike_line = f"{metric} at {clinic_name}{loc_line} up {pct}% ({window})" if pct is not None else f"{metric} trending up ({window})"
            driver_display = driver.replace("_", " ") if driver else ""
            driver_line = f" Likely driven by: {driver_display}." if driver_display else ""
            opp_line = ""
            if vs_baseline and pct:
                extra_per_week = int(pct / 100 * vs_baseline)
                opp_line = f" That's ~{extra_per_week} extra {metric}/week — capitalize before this cools off."
            elif pct and pct >= 15:
                opp_line = f" Momentum like this usually lasts 1-2 weeks — act now while interest is peaking."
            offer_line = ""
            if offer_title:
                offer_line = f"\nPin '{offer_title}' while the momentum lasts — want me to set it up?"
            else:
                offer_line = "\nWant me to draft a follow-up post + pin your best offer to convert this surge?"
            body = f"{merchant_salute} — good news: {spike_line}{driver_line}{opp_line}{offer_line}"
            cta = "binary_yes_no"
            rationale = f"Perf spike; capitalize on momentum + urgency window + concrete next step."

        elif kind == "competitor_opened":
            cn = trig_payload.get("competitor_name") or "A new competitor"
            dist = trig_payload.get("distance_km")
            their_offer = trig_payload.get("their_offer")
            opened = trig_payload.get("opened_date")
            dist_line = f"~{dist} km away" if dist else "in your area"
            their_line = f" They're promoting: '{their_offer}'." if their_offer else ""
            our_offer = offer_title or "your top service"
            diff_line = ""
            if their_offer and our_offer:
                diff_line = f"\nYour '{our_offer}' is differentiated — let's make that visible before they capture search mindshare."
            loc_ref = f", {m_loc}" if m_loc else ""
            body = f"{merchant_salute}{loc_ref} — heads up: {cn} just opened {dist_line}{f' on {opened}' if opened else ''}.{their_line}{diff_line}\nWant me to draft a 1-line hook highlighting what sets you apart — ready to post today?"
            cta = "binary_yes_no"
            rationale = f"Competitor alert; urgency + differentiation + immediate action."

        elif kind == "review_theme_emerged":
            theme = trig_payload.get("theme")
            sentiment = trig_payload.get("sentiment", "mixed")
            count = trig_payload.get("review_count") or trig_payload.get("occurrences_30d")
            trend = trig_payload.get("trend")
            common_quote = trig_payload.get("common_quote")
            theme_line = f" Theme: '{theme}'" if theme else ""
            count_line = f" ({count} reviews this week)" if count else ""
            sentiment_note = " positive feedback you can leverage." if sentiment == "positive" else " worth addressing."
            trend_note = f" Trend is {trend} — acting now prevents more damage." if trend == "rising" else ""
            quote_line = f" One customer said: \"{common_quote}\"" if common_quote else ""
            action_line = ""
            if sentiment == "negative" or trend == "rising":
                action_line = "\nWant me to pull the full theme + draft response templates + 1 listing tweak you can implement today?"
            else:
                action_line = "\nWant me to pull the full theme + draft 2 response templates you can reuse for similar reviews?"
            loc_ref = f", {m_loc}" if m_loc else ""
            body = f"{merchant_salute}{loc_ref} — a pattern is emerging in your reviews{count_line}.{theme_line}{sentiment_note}{quote_line}{trend_note}{action_line}"
            cta = "binary_yes_no"
            rationale = f"Review theme; curiosity + concrete deliverables + urgency when trend is rising."

        elif kind == "active_planning_intent":
            intent_topic = trig_payload.get("intent_topic") or trig_payload.get("plan_type") or "package"
            merchant_last_msg = trig_payload.get("merchant_last_message")
            topic_display = intent_topic.replace("_", " ").replace("corp", "corporate")
            loc_ref = f", {m_loc}" if m_loc else ""
            if merchant_last_msg:
                body = f"{merchant_salute}{loc_ref} — re: \"{merchant_last_msg}\"\n"
            else:
                body = f"{merchant_salute}{loc_ref} — regarding your {topic_display} plan.\n"
            body += f"I've got a draft ready. Share: (1) target price band, (2) weekday vs weekend preference.\nI'll send the final version within 2 minutes."
            cta = "open_ended"
            rationale = f"Planning intent; context-aware with merchant's own words + low-friction ask."

        elif kind in ["ipl_match_today", "festival_upcoming", "category_seasonal"]:
            search_n = trig_payload.get("search_volume")
            search_line = f" {search_n}+ local searches this week{f' in {m_city}' if m_city else ''}." if search_n else ""
            if kind == "category_seasonal":
                season = trig_payload.get("season", "").replace("_", " ").title()
                trends = trig_payload.get("trends", [])
                top_trend_name = ""
                if isinstance(trends, list) and len(trends) > 0:
                    top_t = trends[0]
                    if isinstance(top_t, str):
                        clean = top_t.split("_+")[0].split("_-")[0]
                        parts = clean.replace("_", " ").split()
                        cleaned_parts = []
                        for p in parts:
                            if p.lower() in ("ors", "otc", "bp", "spf", "rx", "uv"):
                                cleaned_parts.append(p.upper())
                            else:
                                cleaned_parts.append(p.capitalize())
                        top_trend_name = " ".join(cleaned_parts)
                if top_trend_name:
                    event_name = f"{season}: {top_trend_name} trending"
                else:
                    event_name = f"{season} season"
                search_line = ""
            elif kind == "festival_upcoming":
                festival = trig_payload.get("festival") or trig_payload.get("festival_name") or "Festival"
                event_name = f"{festival}"
            else:
                match_info = trig_payload.get("match", "")
                event_name = f"Today's IPL match: {match_info}" if match_info else "Today's IPL match"
            peer_line = ""
            if isinstance(peer, dict):
                adoption = peer.get("campaign_adoption_rate")
                if adoption:
                    pct_val = int(round(adoption * 100))
                    peer_line = f" {pct_val}% of {cat_slug} in {m_city or 'your area'} are already running offers."
                elif m_city:
                    peer_line = f" {cat_slug} in {m_city} are already preparing."
            days_until = trig_payload.get("days_until")
            urgency_line = ""
            if days_until and days_until < 60:
                urgency_line = f"Only {days_until} days left — early launchers capture 2x more bookings."
            elif days_until:
                urgency_line = f"{days_until} days out — merchants who prep now see 1.8x higher conversion."
            else:
                urgency_line = "Merchants who launch early capture 2x more bookings."
            opening_line = f"{merchant_salute} — {event_name}."
            body = f"{opening_line}{search_line}{peer_line}\n{urgency_line}\nWant me to set up a seasonal offer + WhatsApp blast?"
            cta = "binary_yes_no"
            rationale = f"Event/seasonal; proof + urgency + concrete action."

        elif kind == "seasonal_perf_dip":
            delta7 = perf.get("delta_7d", {}) if isinstance(perf, dict) else {}
            views_pct = delta7.get("views_pct")
            calls_pct = delta7.get("calls_pct")
            dip_parts = []
            if isinstance(views_pct, (int, float)):
                dip_parts.append(f"{abs(int(round(views_pct*100)))}% views")
            if isinstance(calls_pct, (int, float)):
                dip_parts.append(f"{abs(int(round(calls_pct*100)))}% calls")
            dip = f"{' and '.join(dip_parts)} down (7d)" if dip_parts else "seasonal dip"
            season_note = trig_payload.get("season_note", "")
            if season_note:
                raw = season_note.replace("_", " ")
                parts = raw.split()
                cleaned = []
                for p in parts:
                    if p.lower() in ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"):
                        cleaned.append(p.upper())
                    else:
                        cleaned.append(p.capitalize())
                peer_note = f" {' '.join(cleaned)}."
            else:
                peer_note = " Peers see the same pattern this time of year."
            churn = cust_agg.get("monthly_churn_pct")
            lapsed = cust_agg.get("lapsed_180d_plus") or cust_agg.get("lapsed_90d_plus")
            retention_line = ""
            if churn:
                retention_line = f"\nYour monthly churn is {int(churn*100)}% — a retention WhatsApp now can save ~{max(5, int(churn * cust_agg.get('total_active_members', cust_agg.get('total_unique_ytd', 100)) / 2))} customers this month."
            elif lapsed:
                retention_line = f"\nYou have {lapsed} lapsed customers — a re-engagement message now can bring back 10-15%."
            else:
                retention_line = "\nShifting focus to retention typically offsets 60-70% of seasonal acquisition dips."
            loc_ref = f", {m_loc}" if m_loc else ""
            body = f"{merchant_salute}{loc_ref} — {dip}.{peer_note}{retention_line}\nWant a retention WhatsApp draft you can send today?"
            cta = "binary_yes_no"
            rationale = f"Seasonal dip; peer-normalized + merchant-specific retention angle + concrete action."

        elif kind in ["milestone_reached", "curious_ask_due"]:
            topic = norm(trig_payload.get("question_topic") or trig_payload.get("milestone"))
            topic_display = topic.replace("_", " ").capitalize() if topic else ""
            milestone_val = trig_payload.get("value_now") or trig_payload.get("value")
            metric_name = trig_payload.get("metric")
            if kind == "milestone_reached":
                metric_display = metric_name.replace("_", " ") if metric_name else ""
                if metric_display == "review count":
                    metric_display = "reviews"
                if milestone_val and metric_display:
                    views = perf.get("views", 0)
                    calls = perf.get("calls", 0)
                    loc_ref = f" at {m_name}" if m_name else ""
                    loc_greet = f", {m_loc}" if m_loc else ""
                    perf_line = f" You're at {views} views and {calls} calls this month{loc_ref} — momentum is strong." if views or calls else ""
                    body = f"{merchant_salute}{loc_greet} — you're about to hit {milestone_val} {metric_display}!{perf_line}\nWant me to draft a celebration post + a customer-facing thank-you message?"
                elif milestone_val:
                    loc_greet = f", {m_loc}" if m_loc else ""
                    body = f"{merchant_salute}{loc_greet} — {milestone_val} and counting!\nWant me to draft a celebration post to capitalize on this?"
                else:
                    loc_greet = f", {m_loc}" if m_loc else ""
                    body = f"{merchant_salute}{loc_greet} — quick milestone alert!\nWant me to draft a customer-facing post?"
                cta = "binary_yes_no"
                rationale = f"Milestone; celebration + social proof + capitalize on momentum."
            else:
                ask_template = trig_payload.get("ask_template", "")
                if "demand" in ask_template.lower() or "service" in ask_template.lower():
                    trends = category.get("trend_signals", []) if isinstance(category, dict) else []
                    trend_line = ""
                    if trends:
                        top_trend = trends[0] if isinstance(trends, list) and len(trends) > 0 else {}
                        query = top_trend.get("query", "")
                        delta = top_trend.get("delta_yoy")
                        if query and delta:
                            trend_line = f" \"{query.replace('_', ' ')}\" is up {int(delta*100)}% YoY."
                    loc_greet = f", {m_loc}" if m_loc else ""
                    body = f"{merchant_salute}{loc_greet} — quick pulse check: which service is getting the most walk-in requests this week?{trend_line}\nReply and I'll optimize your GBP posts for max visibility."
                else:
                    loc_greet = f", {m_loc}" if m_loc else ""
                    body = f"{merchant_salute}{loc_greet} — quick question:"
                    if topic_display:
                        body += f" {topic_display}."
                    offer_line = f" Want to promote '{offer_title}'?" if offer_title else ""
                    body += offer_line + "\nReply and I'll use your input to refine this week's recommendations."
                cta = "open_ended"
                rationale = f"Curiosity; engaging question + trend data to prompt merchant response."

        elif kind in ["renewal_due", "trial_followup"]:
            sub = merchant.get("subscription", {}) if isinstance(merchant, dict) else {}
            status = sub.get("status") or "due for renewal"
            days = sub.get("days_remaining")
            plan = sub.get("plan_name") or sub.get("plan") or "your plan"
            renewal_amount = sub.get("renewal_amount") or trig_payload.get("renewal_amount")
            views = perf.get("views", 0)
            calls = perf.get("calls", 0)
            ctr_val = perf.get("ctr")
            value_parts = []
            if views: value_parts.append(f"{views} views")
            if calls: value_parts.append(f"{calls} calls")
            if ctr_val is not None: value_parts.append(f"{ctr_val*100:.1f}% CTR")
            value_summary = ", ".join(value_parts[:3]) if value_parts else "steady activity"
            at_line = f" at {m_name}" if m_name else ""
            loc_ref = f", {m_loc}" if m_loc else ""
            if status == "trial":
                trial_line = f"Your trial period is ending. This period: {value_summary} — your profile is actively converting."
                urgency_line = f" After trial ends, your posts and offers go invisible — {max(5, int(views * 0.3))} monthly views at risk."
                action_line = f"Upgrade to {plan} at ₹{renewal_amount:,} and I'll auto-set up: weekly posts + offer refresh + reply templates."
                body = f"{merchant_salute}{at_line}{loc_ref} — {trial_line}\n{urgency_line}\n{action_line}\nWant me to proceed?"
            elif days is not None:
                days_urgency = ""
                urgency_line = ""
                if days <= 7:
                    days_urgency = f" ({days} days left)"
                    urgency_line = f" If it lapses, your profile visibility drops ~30% — that's ~{max(5, int(views * 0.3))} views/month at risk."
                elif days <= 30:
                    days_urgency = f" ({days} days remaining)"
                else:
                    days_urgency = f" ({days} days remaining)"
                trial_line = f"{plan} at {m_name}{loc_ref} is {status}{days_urgency}.\nThis period: {value_summary} from your listing."
                action_line = f"Renew {plan} and I'll auto-set up: weekly post + offer refresh + reply templates."
                if urgency_line:
                    body = f"{merchant_salute}{loc_ref} — {trial_line}\n{urgency_line}\n{action_line}\nWant me to proceed?"
                else:
                    body = f"{merchant_salute}{loc_ref} — {trial_line}\n{action_line}\nWant me to proceed?"
            else:
                body = f"{merchant_salute}{at_line}{loc_ref} — {plan} is {status}.\nThis period: {value_summary} from your listing.\nRenew {plan} and I'll auto-set up: weekly post + offer refresh + reply templates.\nWant me to proceed?"
            cta = "binary_yes_no"
            rationale = f"Renewal/trial; value proof + quantified loss aversion + binary CTA."

        elif kind == "gbp_unverified":
            est_uplift = trig_payload.get("estimated_uplift_pct")
            views = perf.get("views", 0)
            calls = perf.get("calls", 0)
            impact_line = ""
            if est_uplift:
                uplift_pct = int(est_uplift * 100)
                extra_views = int(views * est_uplift) if views else 0
                impact_line = f" That's ~{extra_views} extra views and ~{max(1, int(calls * est_uplift))} more calls per month for {m_name}." if calls else f" That could mean ~{extra_views}+ extra monthly views."
            else:
                impact_line = " Verified profiles show up 2.7x more in local search results."
            path_line = ""
            path = trig_payload.get("verification_path")
            if path:
                path_display = path.replace("_", " ")
                path_line = f" Path: {path_display}. Takes under 5 minutes to start."
            loc_ref = f", {m_loc}" if m_loc else ""
            body = f"{merchant_salute}{loc_ref} — your Google Business Profile is unverified.{impact_line}\nUnverified profiles lose ~30% visibility in local search — competitors with verified profiles capture those searches.{path_line}\nWant me to walk you through it step by step?"
            cta = "binary_yes_no"
            rationale = f"GBP unverified; quantified impact + merchant-specific numbers + low-friction action."

        elif kind == "cde_opportunity":
            boost_type = trig_payload.get("boost_type") or "local discovery boost"
            requirement = trig_payload.get("requirement") or "1 fresh post + 3 photos this week"
            digest_item_id = trig_payload.get("digest_item_id")
            credits = trig_payload.get("credits")
            fee = trig_payload.get("fee")
            digest = category.get("digest", []) if isinstance(category, dict) else []
            item = None
            if digest_item_id and isinstance(digest, list):
                for d in digest:
                    if isinstance(d, dict) and d.get("id") == digest_item_id:
                        item = d
                        break
            item_line = ""
            if item:
                item_title = item.get("title", "")
                item_date = item.get("date", "")
                date_display = f" on {item_date[:10]}" if item_date else ""
                fee_display = fee.replace("_", " ") if fee else ""
                credits_line = f" ({credits} CDE credits, {fee_display})" if credits else ""
                item_line = f"\nUpcoming: {item_title}{date_display}{credits_line}."
            urgency_line = ""
            if item and item.get("date"):
from datetime import datetime, timezone
                try:
                    evt_date = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
                    days_left = (evt_date - datetime.now(timezone.utc)).days
                    if 0 <= days_left <= 7:
                        urgency_line = f" Only {days_left} days left — spots fill fast."
                    elif days_left > 0:
                        urgency_line = f" {days_left} days out — early sign-up recommended."
                except: pass
            loc_ref = f", {m_loc}" if m_loc else ""
            body = f"{merchant_salute}{loc_ref} — you qualify for a {boost_type}.{item_line}{urgency_line}\nActivate it with: {requirement}.\nWant me to draft the post + suggest which photos to upload?"
            cta = "binary_yes_no"
            rationale = f"CDE opportunity; specific event context + urgency + concrete checklist."

        elif kind in ["regulation_change", "supply_alert"]:
            top_id = trig_payload.get("top_item_id") or trig_payload.get("alert_id")
            digest = category.get("digest", []) if isinstance(category, dict) else []
            item = None
            if top_id and isinstance(digest, list):
                for d in digest:
                    if isinstance(d, dict) and d.get("id") == top_id:
                        item = d
                        break
            if item:
                reg_title = item.get("title", kind.replace("_", " ").capitalize())
                reg_source = item.get("source", "")
                actionable = item.get("actionable", "")
                deadline = trig_payload.get("deadline_iso") or item.get("date")
                if kind == "supply_alert":
                    molecule = trig_payload.get("molecule")
                    batches = trig_payload.get("affected_batches", [])
                    mfr = trig_payload.get("manufacturer")
                    if molecule:
                        reg_title = f"Supply alert: {molecule} — {item.get('title', '').split(':')[0] if ':' in item.get('title', '') else item.get('title', '')}"
                    if mfr and "manufacturer X" in reg_title.lower():
                        reg_title = reg_title.replace("manufacturer X", mfr)
                    elif mfr:
                        reg_title = f"{reg_title} (Manufacturer: {mfr})"
                    if batches:
                        reg_title = f"{reg_title} — batches {', '.join(batches)}"
                loc_ref = f", {m_loc}" if m_loc else ""
                body = f"{merchant_salute}{loc_ref} — {reg_title}."
                if deadline:
                    body += f" Effective: {deadline[:10]}."
                    try:
                        dl = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
                        days_left = (dl - datetime.now(timezone.utc)).days
                        if days_left > 0:
                            body += f" You have {days_left} days to comply."
                        elif days_left <= 0:
                            body += " Deadline has passed — immediate action needed."
                    except: pass
                if actionable:
                    body += f"\nAction: {actionable}"
                body += "\nWant the full 3-bullet summary + a patient/customer messaging update?"
            else:
                reg_name = trig_payload.get("regulation_name") or trig_payload.get("alert_type") or trig_payload.get("molecule")
                reg_display = reg_name.replace("_", " ").capitalize() if reg_name else kind.replace("_", " ").capitalize()
                deadline = trig_payload.get("compliance_deadline") or trig_payload.get("deadline_iso")
                deadline_line = f" Deadline: {deadline[:10] if deadline else deadline}." if deadline else ""
                impact = trig_payload.get("impact_summary")
                impact_line = f" {impact}" if impact else ""
                alert_detail = ""
                if kind == "supply_alert":
                    batches = trig_payload.get("affected_batches", [])
                    mfr = trig_payload.get("manufacturer")
                    if batches:
                        alert_detail = f" Affected batches: {', '.join(batches[:2])}."
                    if mfr:
                        alert_detail += f" Manufacturer: {mfr}."
                loc_ref = f", {m_loc}" if m_loc else ""
                body = f"{merchant_salute}{loc_ref} — {reg_display} alert.{deadline_line}{impact_line}{alert_detail}\nI'll summarize in 3 bullets + what to change in customer messaging.\nWant the summary?"
            cta = "binary_yes_no"
            rationale = f"Compliance/supply alert; urgency + actionable summary + deadline awareness."

        elif kind == "wedding_package_followup":
            season = trig_payload.get("season") or "wedding"
            wedding_date = trig_payload.get("wedding_date")
            trial_completed = trig_payload.get("trial_completed")
            days_to_wedding = trig_payload.get("days_to_wedding")
            timing_line = ""
            if days_to_wedding:
                if days_to_wedding <= 60:
                    timing_line = f" Only {days_to_wedding} days to your wedding — the next 2 weeks are critical for skin prep and trial adjustments."
                elif days_to_wedding <= 180:
                    timing_line = f" {days_to_wedding} days to go — now is the ideal window to lock in your bridal package and start the prep timeline."
                else:
                    timing_line = f" {days_to_wedding} days to go — early planning gives you the best options and pricing."
            trial_line = ""
            if trial_completed:
                trial_line = f" Your trial on {trial_completed[:10]} went well — let's build on that momentum."
            loc_ref = f", {m_loc}" if m_loc else ""
            body = f"{merchant_salute}{loc_ref} — {season} season planning.{timing_line}{trial_line}\nWant a ready-to-send 3-tier package (basic/standard/premium) with clear pricing?\nReply YES and I'll draft it in 2 minutes."
            cta = "binary_yes_no"
            rationale = f"Wedding season; timing-aware + trial context + ready-to-send package."

        elif kind == "dormant_with_vera":
            days_dormant = trig_payload.get("days_since_last_merchant_message") or trig_payload.get("days_since_last_interaction", 30)
            last_topic = trig_payload.get("last_topic")
            last_topic_display = last_topic.replace("_", " ") if last_topic else "your last conversation"
            views = perf.get("views", 0)
            calls = perf.get("calls", 0)
            loc_ref = f", {m_loc}" if m_loc else ""
            value_line = ""
            if views or calls:
                value_line = f" Since we last spoke{loc_ref}: {views} profile views and {calls} calls — your profile is still active."
            signal_line = ""
            actionable_signals = [s for s in signals if "dip" in s.lower() or "below" in s.lower() or "unverified" in s.lower()]
            if actionable_signals:
                sig_display = actionable_signals[0].replace("_", " ")
                signal_line = f"\nI noticed: {sig_display} — want me to help you address this?"
            if signal_line:
                body = f"{merchant_salute}{loc_ref} — it's been {days_dormant} days since we chatted about {last_topic_display}.{value_line}{signal_line}"
            elif views:
                body = f"{merchant_salute}{loc_ref} — it's been {days_dormant} days.{value_line}\nWant a quick snapshot of what's changed + 1 action you can take this week?"
            else:
                body = f"{merchant_salute}{loc_ref} — it's been {days_dormant} days since we last talked about {last_topic_display}.\nWant a fresh profile audit + 2 quick wins?"
            cta = "binary_yes_no"
            rationale = f"Dormant re-engagement; value reminder + specific hook from signals."

        elif kind == "winback_eligible" and scope == "merchant":
            days_since = trig_payload.get("days_since_expiry") or trig_payload.get("days_inactive", 30)
            perf_dip_pct = trig_payload.get("perf_dip_pct")
            lapsed_added = trig_payload.get("lapsed_customers_added_since_expiry")
            loc_ref = f", {m_loc}" if m_loc else ""
            dip_line = ""
            if perf_dip_pct:
                dip_line = f" Since then, your profile metrics{f' at {m_name}' if m_name else ''}{loc_ref} have dropped {int(abs(perf_dip_pct)*100)}%."
            competitor_line = ""
            if lapsed_added:
                competitor_line = f" {lapsed_added} of your past customers have found alternatives in the meantime — each week you wait, more drift away."
            body = f"{merchant_salute}{loc_ref} — it's been {days_since} days.{dip_line}{competitor_line}\nLet's get you back on track. I can reactivate your profile setup in 1 session — weekly posts, offer refresh, and reply templates.\nWant me to restart everything?"
            cta = "binary_yes_no"
            rationale = f"Merchant winback; loss aversion + competitive pressure + clear reactivation path."

        else:
            city = f"{m_loc}, {m_city}".strip(", ")
            payload_bits = []
            if isinstance(trig_payload, dict):
                for k, v in trig_payload.items():
                    if v is not None and k not in ("category",):
                        payload_bits.append(f"{k}: {v}")
            perf_lines = []
            if perf.get("views"): perf_lines.append(f"{perf['views']} views (30d)")
            if perf.get("calls"): perf_lines.append(f"{perf['calls']} calls")
            if perf.get("ctr") is not None: perf_lines.append(f"CTR {perf['ctr']*100:.1f}%")
            if peer_ctr and ctr is not None:
                if ctr < peer_ctr:
                    perf_lines.append(f"CTR below peer avg ({peer_ctr*100:.1f}%)")
                else:
                    perf_lines.append(f"CTR above peer avg ({peer_ctr*100:.1f}%)")
            offer_line = f"Active offer: '{offer_title}'." if offer_title else ""
            peer_proof = ""
            if isinstance(peer, dict):
                avg_views = peer.get("avg_views_30d")
                avg_calls = peer.get("avg_calls_30d")
                if avg_views and perf.get("views"):
                    views_ratio = perf["views"] / avg_views
                    if views_ratio > 1.2:
                        peer_proof = f" You're in the top tier for {cat_slug} in {m_city}."
                    elif views_ratio < 0.8:
                        peer_proof = f" There's headroom vs {cat_slug} peers in {m_city}."
            fact_lines = payload_bits + perf_lines
            if fact_lines:
                facts = "; ".join(fact_lines[:3])
                body = f"{merchant_salute}{f', {m_loc}' if m_loc else ''} — here's your current snapshot: {facts}.{peer_proof} {offer_line}\nWant me to take a specific action? Reply YES for next steps."
            else:
                body = f"{merchant_salute}{f', {m_loc}' if m_loc else ''} — {kind.replace('_', ' ')} update{f' for {city}' if city else ''}.{peer_proof} {offer_line}\nWant me to draft a focused message with your best offer + one clear CTA?"
            cta = "binary_yes_no"
            rationale = f"Generic {kind} trigger; grounded in available facts + peer comparison."

        return ComposedMessage(body=taboo_sanitize(body), cta=cta, send_as=send_as, suppression_key=suppression_key, rationale=rationale)
