"""Pipeline stages, each versioned so a result is interpretable ("rejected under
Qualifier v3"): Qualification -> Optimization -> Validation -> Scoring -> Decision.
Validation is the OUTER walk-forward loop; optimization runs only inside each
in-sample fold. Weak candidates are killed at qualification before expensive
search. (M1+.)
"""
