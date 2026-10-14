ANALYSIS_PROMPT = """You are assisting an insurance property assessor. You are given photos of ONE building, \
labelled by view (front, left, right, rear, damage_closeup). Report only what is visible. Do not guess.

Return JSON with:
- construction_type: what the visible materials suggest (masonry, wood, rcc, steel, mixed, or unknown). \
Policy record says: {recorded_type}. If the photos disagree, report what you see.
- ornateness_score: 0 to 1. 0 = plain, simple box-like structure. 1 = highly ornamented, complex rebuild \
(carved facades, domes, decorative columns, intricate roofing). Score architectural complexity and ornamentation only.
- ornateness_evidence: short list of the visible features behind the score.
- damage: one item per damaged element. element is one of roof, facade, windows, walls, other. \
severity is 0 to 1 (0.1 cosmetic, 0.4 repairable structural or partial, 0.7 major, 1.0 collapse or total loss). \
view is the view where you saw it. evidence is one short sentence describing what is visible. \
Return an empty list if you see no damage.
- views_consistent: true only if all views plausibly show the SAME building (same materials, proportions, features). \
- consistency_notes: one sentence explaining your answer.
- confidence: 0 to 1, how reliable your assessment is given image quality and coverage.
"""

FORENSICS_PROMPT = """You are examining photos submitted with an insurance claim for signs they were \
AI-generated, digitally edited, or composited. You may see several views of one building.

Look for: inconsistent lighting or shadow directions, warped or unreadable text and signage, repeated or \
smeared textures, impossible geometry, architectural details that change between views, blurred or \
mismatched edges around damaged areas, unnatural debris or fire/water effects.

Return JSON with:
- suspicion: 0 to 1. Low if you see nothing unusual. Be conservative: ordinary phone photos can look odd.
- findings: short list of specific observations (empty if none). Describe what you see; do not claim certainty.
- confidence: 0 to 1, how well you could judge given image quality.
This is a screening signal for a human reviewer, not a verdict.
"""