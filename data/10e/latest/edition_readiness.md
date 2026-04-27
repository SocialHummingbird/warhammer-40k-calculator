# Edition Readiness Report

## Summary
- Edition: `10e`
- Status: `ready`
- Calculations enabled: yes
- Ruleset available: yes
- Supported rulesets: `10e`
- Data directory: `data/10e/latest`
- Source commit: `32b4525d9f69f062f3458d517c6cf82512ef6fef`

## Data Counts

| Table | Rows |
| --- | ---: |
| units | 1464 |
| weapons | 8628 |
| abilities | 3124 |
| keywords | 1407 |
| unit_keywords | 9523 |

## Audit Summary

| Severity | Rows |
| --- | ---: |
| Errors | 0 |
| Warnings | 0 |
| Info | 0 |
| Total | 0 |

## Ruleset Capability Coverage

| Capability | Status | Notes |
| --- | --- | --- |
| Hit rolls, hit modifiers, and critical hits | implemented |  |
| Hit rerolls | implemented |  |
| Lethal Hits | implemented |  |
| Sustained Hits | implemented |  |
| Torrent and automatic hits | implemented |  |
| Advance firing restrictions and Assault handling | implemented |  |
| Heavy stationary hit bonus | implemented |  |
| Rapid Fire attack bonuses | implemented |  |
| Blast attack bonuses | implemented |  |
| Wound roll thresholds and wound modifiers | implemented |  |
| Wound rerolls and Twin-linked | implemented |  |
| Anti keyword critical wounds | implemented |  |
| Devastating Wounds pool splitting | implemented |  |
| Armour, invulnerable, AP, cover, and Ignores Cover | implemented |  |
| Feel No Pain damage prevention | implemented |  |
| Melta range damage bonuses | implemented |  |
| Flat damage reduction | implemented |  |
| Defender damage caps | implemented |  |
| Expected model removal with overkill capping | implemented |  |

## Blockers
- None

## Migration Checklist
- [x] Ruleset module exists and is registered in `warhammer.rules`.
- [x] Edition-specific hit, wound, save, damage, and model-removal behavior is implemented.
- [x] Edition-specific contextual mechanics are behind the ruleset interface.
- [x] Generated data has no audit error samples.
- [x] Web/API calculations are enabled for this edition.
