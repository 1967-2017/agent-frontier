from __future__ import annotations

from demo3_browser_agent.schemas import AgentDecision, AgentObservation, TaskValidationResult
from demo3_browser_agent.tasks.base import TaskContext


POPUP_TERMS = {
    "cookie",
    "cookies",
    "consent",
    "privacy",
    "preferences",
    "necessary",
    "statistics",
    "marketing",
    "personalisation",
    "personalization",
}
REJECT_TERMS = {
    "reject",
    "reject all",
    "deny",
    "decline",
    "necessary only",
    "only necessary",
    "use necessary",
}
ACCEPT_TERMS = {
    "accept all",
    "allow all",
    "accept cookies",
    "allow cookies",
    "agree to all",
}
VISIBLE_POPUP_REJECT_TERMS = {
    "reject",
    "reject all",
    "deny",
    "decline",
}
VISIBLE_POPUP_ACCEPT_TERMS = {
    "accept all",
    "allow all",
    "agree to all",
}
VISIBLE_POPUP_SETTINGS_TERMS = {
    "customize",
    "customise",
    "manage options",
    "manage consent",
}
SETTINGS_TERMS = {
    "customize",
    "customise",
    "preferences",
    "settings",
    "manage options",
    "manage consent",
}


class ModalWallTask:
    id = "modal-wall"
    name = "Cookiebot cookie consent rejection"
    start_url = "https://www.cookiebot.com/en/cookie-consent/"
    artifact_name = None
    max_retries = 1

    def __init__(self) -> None:
        self.saw_cookie_popup = False
        self.saw_reject_control = False
        self.last_popup_visible = False
        self.last_reject_labels: list[str] = []
        self.last_visible_text_excerpt = ""

    def instruction(self) -> str:
        return """
Your goal is to handle the cookie consent popup on the Cookiebot page by rejecting non-essential cookies.

Open the page and look for a cookie consent banner, popup, or modal. Click a reject-style option such as "Reject", "Reject all", "Deny", "Decline", "Necessary only", or "Use necessary cookies only". Do not click "Accept all", "Allow all", or any equivalent accept-all option.

If the reject option is hidden behind "Settings", "Preferences", "Customize", or "Manage consent", open that panel and choose the option that rejects or disables non-essential cookies. After clicking reject/decline/necessary-only, observe the page again. Finish only when the cookie popup is no longer visible.

When finished, return action_type=finish with a summary explaining which reject-style control you used, and include one row with: status="rejected", control=<button/control used>, popup_dismissed="true".
""".strip()

    def instruction_for_observation(self, observation: AgentObservation) -> str:
        self._remember_observation(observation)
        status = []
        if self.saw_cookie_popup:
            status.append("A cookie consent popup/banner has been observed.")
        else:
            status.append("No cookie consent popup/banner has been confirmed yet; inspect the page and visible controls.")
        if self.last_popup_visible:
            status.append("The latest observation still appears to show cookie consent UI, so do not finish yet.")
        else:
            status.append("The latest observation does not appear to show cookie consent UI. If you already rejected cookies, finish now.")
        if self.last_reject_labels:
            status.append("Reject-like controls seen in the latest observation: " + ", ".join(self.last_reject_labels[:5]) + ".")
        elif self.saw_reject_control:
            status.append("A reject-like control was seen earlier; if you clicked it and the popup is gone, finish.")
        else:
            status.append("No direct reject-like control has been seen yet; use settings/preferences if needed, and avoid accept-all controls.")
        return self.instruction() + "\n\nCurrent validation context:\n- " + "\n- ".join(status)

    async def prepare(self, context: TaskContext) -> None:
        self.saw_cookie_popup = False
        self.saw_reject_control = False
        self.last_popup_visible = False
        self.last_reject_labels = []
        self.last_visible_text_excerpt = ""

    async def validate_finish(self, decision: AgentDecision, context: TaskContext) -> TaskValidationResult:
        evidence = _decision_evidence(decision)
        evidence_lower = evidence.lower()
        if not self.saw_cookie_popup:
            return TaskValidationResult(passed=False, message="cookie consent popup was not observed")
        if self.last_popup_visible:
            return TaskValidationResult(passed=False, message="cookie consent popup still appears visible; reject/dismiss it before finishing")
        if any(term in evidence_lower for term in ACCEPT_TERMS):
            return TaskValidationResult(passed=False, message="finish evidence suggests cookies may have been accepted instead of rejected")
        if not _contains_any(evidence_lower, REJECT_TERMS | {"rejected", "declined", "denied", "non-essential", "non essential"}):
            return TaskValidationResult(passed=False, message="finish summary/rows must state that cookies were rejected or limited to necessary cookies")
        if decision.rows:
            row = decision.rows[0]
            status = str(row.get("status", "")).lower()
            dismissed = str(row.get("popup_dismissed", "")).lower()
            if "reject" not in status and "declin" not in status and "den" not in status and "necessary" not in status:
                return TaskValidationResult(passed=False, message="finish row status must indicate rejected/declined/necessary-only")
            if dismissed not in {"true", "yes", "1", "dismissed", "gone"}:
                return TaskValidationResult(passed=False, message="finish row must set popup_dismissed=true")
        return TaskValidationResult(passed=True, message="Cookiebot cookie consent popup rejected and dismissed")

    def _remember_observation(self, observation: AgentObservation) -> None:
        text = observation.visible_text or ""
        mark_texts = [mark.text or "" for mark in observation.marks]
        reject_labels = [label.strip() for label in mark_texts if _contains_any(label.lower(), REJECT_TERMS)]
        popup_labels = [
            label.strip()
            for label in mark_texts
            if _contains_any(label.lower(), VISIBLE_POPUP_REJECT_TERMS | VISIBLE_POPUP_ACCEPT_TERMS | VISIBLE_POPUP_SETTINGS_TERMS)
        ]
        popup_visible = _looks_like_cookie_popup(text.lower(), popup_labels)
        self.last_popup_visible = popup_visible
        self.last_reject_labels = reject_labels
        self.last_visible_text_excerpt = text[:1200]
        if popup_visible:
            self.saw_cookie_popup = True
        if reject_labels:
            self.saw_reject_control = True


def _looks_like_cookie_popup(visible_text: str, popup_action_labels: list[str]) -> bool:
    """Return true only for actionable consent UI, not ordinary page copy.

    Cookiebot's page still contains lots of words like "cookie", "consent",
    and "privacy" after the banner is dismissed. Treat the popup as visible
    only when visible interactive controls still expose reject/accept/manage
    consent actions.
    """
    return bool(popup_action_labels) and _contains_any(visible_text, {"cookie", "cookies", "consent", "privacy"})


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def _decision_evidence(decision: AgentDecision) -> str:
    parts = [decision.summary or "", decision.thought or ""]
    for row in decision.rows:
        parts.extend(str(value) for value in row.values())
    return "\n".join(parts)
