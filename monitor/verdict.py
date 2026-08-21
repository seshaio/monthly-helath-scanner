"""
Score to verdict.

One scale for both instrument types, so a table of equities and a table of
funds end in the same five words. Equities score health + valuation + trend;
ETFs score structure + underlying valuation + trend. The middle term differs
because the instruments differ, the arithmetic does not.

The band alone cannot express "sound but expensive" — a 6 built from intact
health and a stretched multiple means something different from a 6 built from
a wobbling business at fair value, and they call for different actions. So
TRIM sits over the band as an override rather than occupying a band of its
own.
"""

import config

BUY, KEEP, TRIM, SELL, WAIT = "BUY", "KEEP", "TRIM", "SELL", "WAIT"
INCOMPLETE = "—"


def total(*components):
    """Sum the score, or None if any component is missing."""
    if any(c is None for c in components):
        return None
    return sum(components)


def band(score):
    """The plain score band, before any override."""
    if score is None:
        return INCOMPLETE
    for ceiling, verdict in config.VERDICT_BANDS:
        if score <= ceiling:
            return verdict
    return KEEP


def decide(score, *, soundness=None, expensive_anchors=0, broken=False,
           days_to_earnings=None):
    """
    The verdict, with every override applied in priority order.

    `soundness` is health for an equity and structural score for a fund — the
    0-4 term that says whether the thing itself is in good order, as opposed
    to whether its price is attractive.
    """
    # Reporting imminently: reviewing on figures about to be superseded
    # produces noise dressed as a verdict.
    if (days_to_earnings is not None
            and 0 <= days_to_earnings <= config.DEFER_DAYS_BEFORE_EARNINGS):
        return WAIT

    # A broken business is a sell however cheap it looks. Cheapness is the
    # symptom here, not the opportunity.
    if broken:
        return SELL

    result = band(score)
    if result is INCOMPLETE:
        return INCOMPLETE

    # Sound but dear: reduce, do not exit. Valuation alone never reaches SELL
    # by score, because soundness scores 4 on its own and 4 is the KEEP floor.
    if (result == KEEP
            and soundness is not None
            and soundness >= config.TRIM_SOUNDNESS_FLOOR
            and expensive_anchors >= config.TRIM_MIN_ANCHORS_EXPENSIVE):
        return TRIM

    return result


def explain(verdict_word):
    """One line, for the report footer."""
    return {
        BUY: "sound and cheap against its own history",
        KEEP: "nothing to do",
        TRIM: "sound, but the price is at an extreme — reduce, do not exit",
        SELL: "the thing itself has deteriorated",
        WAIT: "reports within days; not scored on figures about to change",
        INCOMPLETE: "not enough computed to say",
    }[verdict_word]
