# ML Model Audit

## Summary
- Model: `nearest_centroid_classifier`
- Feature set: `pre_match`
- Model file: `C:\Users\ap010\OneDrive\Documents\dev\Warhammer 40K Calculator\250916 0942 Warhammer 40k damage calculator\models\10e\matchup_centroid_model.json`
- Feature file: `C:\Users\ap010\OneDrive\Documents\dev\Warhammer 40K Calculator\250916 0942 Warhammer 40k damage calculator\data\ml\10e\matchup_training_rows.csv`
- Saved feature rows: 10000
- Saved feature SHA-256: `0b84aae91010141e89adb91ccaa69bb4a0ba873a364bba5991f3b17af2b46d35`
- Created at: `2026-04-26T15:56:19.585925Z`
- Label source: `deterministic_calculator`
- Labels: `attacker`, `close`, `defender`
- Training rows: 8000
- Validation rows: 2000
- Validation accuracy: 0.688
- Feature CSV completeness: ok

## Interpretation
- This is an advisory model, not the rules engine.
- Labels are generated from deterministic calculator outputs, not real tabletop results.
- Validation accuracy measures agreement with the calculator-derived labels.

## Class Balance
### Feature CSV labels

| Label | Rows | Share |
| --- | ---: | ---: |
| `attacker` | 5100 | 51.0% |
| `close` | 510 | 5.1% |
| `defender` | 4390 | 43.9% |
| **Total** | **10000** | **100.0%** |
### Training labels

| Label | Rows | Share |
| --- | ---: | ---: |
| `attacker` | 4080 | 51.0% |
| `close` | 417 | 5.2% |
| `defender` | 3503 | 43.8% |
| **Total** | **8000** | **100.0%** |

## Validation Confusion Matrix
| Expected \ Predicted | `attacker` | `close` | `defender` |
| --- | ---: | ---: | ---: |
| `attacker` | 687 | 300 | 33 |
| `close` | 14 | 56 | 23 |
| `defender` | 21 | 233 | 633 |

## Feature Columns
- Total columns: 42
- Calculator output columns: none

- `attacker_points`
- `attacker_models`
- `attacker_toughness`
- `attacker_save`
- `attacker_invulnerable_save`
- `attacker_wounds`
- `attacker_keywords_count`
- `attacker_weapon_count`
- `attacker_mode_weapon_count`
- `attacker_points_per_model`
- `attacker_mode_avg_attacks`
- `attacker_mode_max_attacks`
- `attacker_mode_avg_skill`
- `attacker_mode_avg_strength`
- `attacker_mode_max_strength`
- `attacker_mode_avg_ap`
- `attacker_mode_best_ap`
- `attacker_mode_avg_damage`
- `attacker_mode_max_damage`
- `attacker_mode_keyword_count`
- `attacker_mode_special_rule_count`
- `defender_points`
- `defender_models`
- `defender_toughness`
- `defender_save`
- `defender_invulnerable_save`
- `defender_wounds`
- `defender_keywords_count`
- `defender_weapon_count`
- `defender_mode_weapon_count`
- `defender_points_per_model`
- `defender_mode_avg_attacks`
- `defender_mode_max_attacks`
- `defender_mode_avg_skill`
- `defender_mode_avg_strength`
- `defender_mode_max_strength`
- `defender_mode_avg_ap`
- `defender_mode_best_ap`
- `defender_mode_avg_damage`
- `defender_mode_max_damage`
- `defender_mode_keyword_count`
- `defender_mode_special_rule_count`
