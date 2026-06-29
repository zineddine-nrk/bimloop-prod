/**
 * UI label maps for English display.
 * Backend keeps French canonical values in DB; we only translate at render time.
 */
(function () {
    "use strict";

    const STATUS_LABELS = {
        "in_building":  "In building",
        "démonté":      "Dismantled",
        "transporté":   "In transit",
        "stocké":       "Stored",
        "réutilisé":    "Reused",
        "à réutiliser": "To reuse",
        "à recycler":   "To recycle",
    };

    const CONDITION_LABELS = {
        "Neuf":    "New",
        "Bon":     "Good",
        "Moyen":   "Fair",
        "Mauvais": "Poor",
    };

    const AGE_LABELS = {
        "Inférieur à 2 ans":  "Under 2 years",
        "Entre 2 et 10 ans":  "2–10 years",
        "Entre 10 et 50 ans": "10–50 years",
        "Supérieur à 50 ans": "Over 50 years",
    };

    function statusLabel(s)    { return STATUS_LABELS[s]    || s || "—"; }
    function conditionLabel(c) { return CONDITION_LABELS[c] || c || "—"; }
    function ageLabel(a)       { return AGE_LABELS[a]       || a || "—"; }

    window.I18N = {
        STATUS_LABELS, CONDITION_LABELS, AGE_LABELS,
        statusLabel, conditionLabel, ageLabel,
    };
})();
