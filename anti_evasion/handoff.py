# -*- coding: utf-8 -*-
"""anti_evasion/handoff.py — HandoffEvaluator.

W6 Module 2 (part 2): interceptor handoff with hysteresis and active-lock protection.

Rule:
  handoff allowed iff
    1. candidate B ETA < current A ETA * (1 - HANDOFF_MIN_BENEFIT)   (hysteresis)
    2. A does NOT hold an active lock in a mature kill chain          (lock protection)
    3. cooldown since last handoff of this target passed
  benefit = (old_eta - new_eta) / old_eta  (recorded; only counts as SUCCESS if it holds
    in follow-up — see w6 metrics / regression).

No opponent / count / seed dependence.
"""
from . import config as cfg


class HandoffDecision:
    __slots__ = ("target", "from_interceptor", "to_interceptor", "handoff",
                 "reason", "old_eta", "new_eta", "benefit_margin", "blocked_reason")

    def __init__(self, target, frm, to, handoff, reason, old_eta, new_eta, benefit,
                 blocked_reason="NONE"):
        self.target = target
        self.from_interceptor = frm
        self.to_interceptor = to
        self.handoff = handoff
        self.reason = reason
        self.old_eta = old_eta
        self.new_eta = new_eta
        self.benefit_margin = benefit
        self.blocked_reason = blocked_reason

    def to_dict(self):
        return {"target": self.target, "from": self.from_interceptor,
                "to": self.to_interceptor, "handoff": self.handoff,
                "reason": self.reason, "old_eta": self.old_eta,
                "new_eta": self.new_eta, "benefit_margin": round(self.benefit_margin, 4),
                "blocked_reason": self.blocked_reason}


class HandoffEvaluator:
    """Compares the CURRENT COMMITTED interceptor vs the BEST alternative.

    Correct object: `current` is the interceptor already committed to the target (from the
    existing commitment state), `alternative` is the best non-committed candidate.
    Self-compare is impossible (we skip current == alternative)."""

    def __init__(self, min_benefit=cfg.HANDOFF_MIN_BENEFIT,
                 cooldown=cfg.HANDOFF_COOLDOWN_S,
                 lock_protect=cfg.LOCK_PROTECT_K,
                 active_lock_age=cfg.ACTIVE_LOCK_AGE_S):
        self.min_benefit = min_benefit
        self.cooldown = cooldown
        self.lock_protect = lock_protect
        self.active_lock_age = active_lock_age
        self._last_handoff = {}   # target -> sim_time
        self.evaluations = 0
        self.blocked_counts = {}

    def _protected(self, current_interceptor, now):
        st = current_interceptor or {}
        if not st.get("is_locking"):
            return False
        locked_since = st.get("locked_since")
        if locked_since is None:
            return False
        return now - locked_since >= self.active_lock_age

    def evaluate(self, target, current, alternative, current_eta, alternative_eta,
                 current_interceptor_state, now):
        """current / alternative: interceptor names; current_eta / alternative_eta: their
        predicted ETA to the target's corridor."""
        self.evaluations += 1
        if current is None or alternative is None or current == alternative:
            return HandoffDecision(target, current, alternative, False,
                                   "self_or_none", current_eta, alternative_eta, 0.0,
                                   "NO_ALTERNATIVE")
        if current_eta is None or alternative_eta is None or current_eta <= 0:
            return HandoffDecision(target, current, alternative, False, "no_eta",
                                   current_eta, alternative_eta, 0.0, "OTHER")
        benefit = (current_eta - alternative_eta) / current_eta
        blocked = "NONE"
        if benefit < self.min_benefit:
            blocked = "INSUFFICIENT_BENEFIT"
        elif self._protected(current_interceptor_state, now):
            blocked = "ACTIVE_LOCK_PROTECTED"
        elif self._last_handoff.get(target) is not None and \
                now - self._last_handoff[target] < self.cooldown:
            blocked = "COOLDOWN"
        else:
            self.blocked_counts["ACCEPT"] = self.blocked_counts.get("ACCEPT", 0) + 1
            self._last_handoff[target] = now
            return HandoffDecision(target, current, alternative, True, "eta_advantage",
                                   current_eta, alternative_eta, benefit)
        self.blocked_counts[blocked] = self.blocked_counts.get(blocked, 0) + 1
        return HandoffDecision(target, current, alternative, False, blocked,
                               current_eta, alternative_eta, benefit, blocked)
