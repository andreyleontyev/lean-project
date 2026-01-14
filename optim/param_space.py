from itertools import product

STOP_PROFILES = [
    ("tight",   3.0, 2.0, 1.5),
    ("normal",  3.5, 2.5, 2.0),
    ("wide",    4.0, 3.0, 2.5),
    ("extreme", 4.5, 3.0, 2.25),
]

breakeven_r_values = [0.8, 1.0, 1.2]
# trail_gap_r_values = [0.8, 1.2, 1.6]
trail_gap_r_values = [0.8]
# soft_exit_gap_r_values = [1.0, 1.5, 2.0]
soft_exit_gap_r_values = [1.0]

def generate_param_space():
    for profile, a_neg, a_neu, a_pos in STOP_PROFILES:
        for be, trail_gap, soft_gap in product(
            breakeven_r_values,
            trail_gap_r_values,
            soft_exit_gap_r_values
        ):
            trail_start_r = be + trail_gap
            soft_exit_r = trail_start_r + soft_gap

            # profile-aware constraints
            if profile == "tight" and soft_gap > 1.5:
                continue
            if profile in ("wide", "extreme") and be < 1.0:
                continue

            yield {
                "atr_stop_negative": a_neg,
                "atr_stop_neutral": a_neu,
                "atr_stop_positive": a_pos,
                "breakeven_r": be,
                "trail_start_r": trail_start_r,
                "soft_exit_r": soft_exit_r,
                "stop_profile": profile,
            }
