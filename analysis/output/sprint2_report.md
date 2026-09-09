# Sprint 2 Report

This report evaluates the pre-registered Sprint 2 hypotheses literally.
It does not choose the paper narrative.

## Hypothesis Verdicts

| hypothesis | criterion | passed |
| --- | --- | --- |
| H1 | best(rf+fo, rf+mip) < cold MIP in >=4/6 instances at both 300s and 600s | false |
| H2 | best(rf+fo, rf+mip) < cold MIP in >=3/5 10X instances at 3600s | true |
| H3 | rf+fo < truncated ILS v2 in every short-budget cell | false |
| H4 | no rf+fo run has Z_final greater than its RF reference | false |

## Updated BKS Accounting

BKS is recomputed after adding matheuristic outputs from tuning, pilot, short-budget, and 8X/10X runs.

| dataset | instance | BKS | matheuristic_best | matheuristic_method | matheuristic_budget | updated_BKS | updated_source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10X | IncT10x_2 | 142834.183 | 165438.755 | rf+mip | 3600.000 | 142834.183 | analysis_table |
| 10X | IncT10x_3 | 80690.614 | 102151.544 | rf+mip | 3600.000 | 80690.614 | analysis_table |
| 10X | IncT10x_4 | 168985.520 | 185779.606 | mip | 3600.000 | 168985.520 | analysis_table |
| 10X | IncT10x_5 | 66696.973 | 68914.120 | mip | 3600.000 | 66696.973 | analysis_table |
| 10X | IncT10x_6 | 109047.046 | 127960.821 | rf+mip | 3600.000 | 109047.046 | analysis_table |
| 3X | IncT3x_1 | 43424.391 |  |  |  | 43424.391 | analysis_table |
| 3X | IncT3x_10 | 10914.378 |  |  |  | 10914.378 | analysis_table |
| 3X | IncT3x_2 | 108645.892 |  |  |  | 108645.892 | analysis_table |
| 3X | IncT3x_3 | 46154.492 | 46175.567 | rf+fo | 3600.000 | 46154.492 | analysis_table |
| 3X | IncT3x_4 | 134477.501 |  |  |  | 134477.501 | analysis_table |
| 3X | IncT3x_5 | 40735.322 |  |  |  | 40735.322 | analysis_table |
| 3X | IncT3x_6 | 73458.775 |  |  |  | 73458.775 | analysis_table |
| 3X | IncT3x_7 | 16441.491 | 16441.491 | rf+mip | 600.000 | 16441.491 | rf+mip |
| 3X | IncT3x_8 | 171942.718 |  |  |  | 171942.718 | analysis_table |
| 3X | IncT3x_9 | 21779.420 |  |  |  | 21779.420 | analysis_table |
| 4X | IncT4x_1 | 46880.699 |  |  |  | 46880.699 | analysis_table |
| 4X | IncT4x_10 | 13375.333 |  |  |  | 13375.333 | analysis_table |
| 4X | IncT4x_2 | 111902.298 |  |  |  | 111902.298 | analysis_table |
| 4X | IncT4x_3 | 49468.889 | 49521.664 | mip | 600.000 | 49468.889 | analysis_table |
| 4X | IncT4x_4 | 137435.102 |  |  |  | 137435.102 | analysis_table |
| 4X | IncT4x_5 | 43396.022 |  |  |  | 43396.022 | analysis_table |
| 4X | IncT4x_6 | 76811.290 |  |  |  | 76811.290 | analysis_table |
| 4X | IncT4x_7 | 19282.326 | 19873.039 | rf+fo | 3600.000 | 19282.326 | analysis_table |
| 4X | IncT4x_8 | 174700.915 |  |  |  | 174700.915 | analysis_table |
| 4X | IncT4x_9 | 24689.228 |  |  |  | 24689.228 | analysis_table |
| 5X | IncT5x_1 | 50351.243 |  |  |  | 50351.243 | analysis_table |
| 5X | IncT5x_10 | 16115.811 | 16188.998 | rf+fo | 3600.000 | 16115.811 | analysis_table |
| 5X | IncT5x_2 | 116353.298 |  |  |  | 116353.298 | analysis_table |
| 5X | IncT5x_3 | 53570.461 | 54844.669 | rf+fo | 3600.000 | 53570.461 | analysis_table |
| 5X | IncT5x_4 | 141043.753 |  |  |  | 141043.753 | analysis_table |
| 5X | IncT5x_5 | 46138.191 |  |  |  | 46138.191 | analysis_table |
| 5X | IncT5x_6 | 80612.087 |  |  |  | 80612.087 | analysis_table |
| 5X | IncT5x_7 | 22166.183 |  |  |  | 22166.183 | analysis_table |
| 5X | IncT5x_8 | 177536.272 |  |  |  | 177536.272 | analysis_table |
| 5X | IncT5x_9 | 28381.253 |  |  |  | 28381.253 | analysis_table |
| 8X | IncT8x_2 | 128054.148 | 131839.464 | mip | 3600.000 | 128054.148 | analysis_table |
| 8X | IncT8x_3 | 67597.088 | 68783.650 | rf+mip | 3600.000 | 67597.088 | analysis_table |
| 8X | IncT8x_4 | 158113.714 | 158113.714 | rf+mip | 3600.000 | 158113.714 | rf+mip |
| 8X | IncT8x_5 | 58152.349 | 59924.391 | mip | 3600.000 | 58152.349 | analysis_table |
| 8X | IncT8x_6 | 95679.146 | 98744.057 | rf+mip | 3600.000 | 95679.146 | analysis_table |

## Tuning Grid

| instance | omega | tl_fo | step_fo | Z_final | fo_accepts | fo_sweeps_completed |
| --- | --- | --- | --- | --- | --- | --- |
| IncT5x_10 | 12.000 | 30.000 | 6.000 | 18303.079 | 43.000 | 24.000 |
| IncT5x_10 | 12.000 | 60.000 | 6.000 | 18303.079 | 43.000 | 23.000 |
| IncT5x_10 | 20.000 | 30.000 | 10.000 | 16188.998 | 43.000 | 37.000 |
| IncT5x_10 | 20.000 | 60.000 | 10.000 | 16538.664 | 38.000 | 37.000 |
| IncT5x_10 | 28.000 | 30.000 | 14.000 | 16859.777 | 20.000 | 32.000 |
| IncT5x_10 | 28.000 | 60.000 | 14.000 | 16841.977 | 19.000 | 31.000 |
| IncT5x_3 | 12.000 | 30.000 | 6.000 | 57006.921 | 2.000 | 29.000 |
| IncT5x_3 | 12.000 | 60.000 | 6.000 | 57006.921 | 2.000 | 29.000 |
| IncT5x_3 | 20.000 | 30.000 | 10.000 | 54879.119 | 0.000 | 45.000 |
| IncT5x_3 | 20.000 | 60.000 | 10.000 | 54879.119 | 0.000 | 43.000 |
| IncT5x_3 | 28.000 | 30.000 | 14.000 | 54859.144 | 1.000 | 45.000 |
| IncT5x_3 | 28.000 | 60.000 | 14.000 | 54859.144 | 1.000 | 45.000 |

## Short-Budget Experiment

| dataset | instance | budget_s | Z_rf_fo | Z_rf_mip | Z_mip | Z_ils_v2_best_until_budget | best_method | best_Z |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3X | IncT3x_3 | 300.000 | 47769.556 | 46239.367 | 48147.231 | 53728.903 | rf+mip | 46239.367 |
| 3X | IncT3x_3 | 600.000 | 48237.316 | 46190.017 | 46210.117 | 53728.903 | rf+mip | 46190.017 |
| 3X | IncT3x_7 | 300.000 | 16702.607 | 16603.182 | 16664.600 | 23026.037 | rf+mip | 16603.182 |
| 3X | IncT3x_7 | 600.000 | 16532.257 | 16441.491 | 16651.675 | 23026.037 | rf+mip | 16441.491 |
| 4X | IncT4x_3 | 300.000 | 51437.320 | 53449.044 | 50288.764 | 63255.293 | mip | 50288.764 |
| 4X | IncT4x_3 | 600.000 | 51777.217 | 49578.045 | 49521.664 | 62926.853 | mip | 49521.664 |
| 4X | IncT4x_7 | 300.000 | 23259.550 | 23534.720 | 22685.483 | 38851.599 | mip | 22685.483 |
| 4X | IncT4x_7 | 600.000 | 20675.807 | 21389.233 | 21657.453 | 26897.394 | rf+fo | 20675.807 |
| 5X | IncT5x_3 | 300.000 | 93627.594 | 380937.341 | 56023.127 | 69520.774 | mip | 56023.127 |
| 5X | IncT5x_3 | 600.000 | 64791.163 | 56597.058 | 55824.522 | 68096.090 | mip | 55824.522 |
| 5X | IncT5x_10 | 300.000 | 999420.861 | 283461.421 | 18657.518 | 26440.814 | mip | 18657.518 |
| 5X | IncT5x_10 | 600.000 | 18776.770 | 18536.715 | 17880.240 | 26440.814 | mip | 17880.240 |

## 8X/10X Scale Experiment

| dataset | instance | Z_rf_fo | Z_rf_mip | Z_mip | best_method | best_Z |
| --- | --- | --- | --- | --- | --- | --- |
| 8X | IncT8x_2 | 141146.399 | 134500.543 | 131839.464 | mip | 131839.464 |
| 8X | IncT8x_3 | 79473.057 | 68783.650 | 71839.478 | rf+mip | 68783.650 |
| 8X | IncT8x_4 | 159958.731 | 158113.714 | 166073.216 | rf+mip | 158113.714 |
| 8X | IncT8x_5 | 71855.978 | 61371.845 | 59924.391 | mip | 59924.391 |
| 8X | IncT8x_6 | 100008.734 | 98744.057 | 103833.803 | rf+mip | 98744.057 |
| 10X | IncT10x_2 | 209676.831 | 165438.755 | 185344.308 | rf+mip | 165438.755 |
| 10X | IncT10x_3 | 128314.728 | 102151.544 | 102753.138 | rf+mip | 102151.544 |
| 10X | IncT10x_4 | 216208.276 | 188575.590 | 185779.606 | mip | 185779.606 |
| 10X | IncT10x_5 | 154102.825 | 165170.737 | 68914.120 | mip | 68914.120 |
| 10X | IncT10x_6 | 161011.652 | 127960.821 | 130545.565 | rf+mip | 127960.821 |

## H1 Evidence

| budget_s | wins | required | passed |
| --- | --- | --- | --- |
| 300.000 | 2.000 | 4.000 | false |
| 600.000 | 3.000 | 4.000 | false |

| instance | budget_s | best_decomp | cplex_mip | decomp_beats_mip |
| --- | --- | --- | --- | --- |
| IncT3x_3 | 300.000 | 46239.367 | 48147.231 | true |
| IncT3x_7 | 300.000 | 16603.182 | 16664.600 | true |
| IncT4x_3 | 300.000 | 51437.320 | 50288.764 | false |
| IncT4x_7 | 300.000 | 23259.550 | 22685.483 | false |
| IncT5x_10 | 300.000 | 283461.421 | 18657.518 | false |
| IncT5x_3 | 300.000 | 93627.594 | 56023.127 | false |
| IncT3x_3 | 600.000 | 46190.017 | 46210.117 | true |
| IncT3x_7 | 600.000 | 16441.491 | 16651.675 | true |
| IncT4x_3 | 600.000 | 49578.045 | 49521.664 | false |
| IncT4x_7 | 600.000 | 20675.807 | 21657.453 | true |
| IncT5x_10 | 600.000 | 18536.715 | 17880.240 | false |
| IncT5x_3 | 600.000 | 56597.058 | 55824.522 | false |

## H2 Evidence

| instance | best_decomp | cplex_mip | decomp_beats_mip |
| --- | --- | --- | --- |
| IncT10x_2 | 165438.755 | 185344.308 | true |
| IncT10x_3 | 102151.544 | 102753.138 | true |
| IncT10x_4 | 188575.590 | 185779.606 | false |
| IncT10x_5 | 154102.825 | 68914.120 | false |
| IncT10x_6 | 127960.821 | 130545.565 | true |

## H3 Evidence

| instance | budget_s | Z_rf_fo | Z_ils_v2_best_until_budget | rf_fo_beats_ils_v2 |
| --- | --- | --- | --- | --- |
| IncT3x_3 | 300.000 | 47769.556 | 53728.903 | true |
| IncT3x_7 | 300.000 | 16702.607 | 23026.037 | true |
| IncT4x_3 | 300.000 | 51437.320 | 63255.293 | true |
| IncT4x_7 | 300.000 | 23259.550 | 38851.599 | true |
| IncT5x_10 | 300.000 | 999420.861 | 26440.814 | false |
| IncT5x_3 | 300.000 | 93627.594 | 69520.774 | false |
| IncT3x_3 | 600.000 | 48237.316 | 53728.903 | true |
| IncT3x_7 | 600.000 | 16532.257 | 23026.037 | true |
| IncT4x_3 | 600.000 | 51777.217 | 62926.853 | true |
| IncT4x_7 | 600.000 | 20675.807 | 26897.394 | true |
| IncT5x_10 | 600.000 | 18776.770 | 26440.814 | true |
| IncT5x_3 | 600.000 | 64791.163 | 68096.090 | true |

## H4 Evidence

RF reference includes the RF phase inside each rf+fo JSON and any standalone rf JSON with the same instance, seed, and budget.

Checked comparisons: 66. Violations: 3.

| instance | dataset | seed | budget | Z_final | Z_rf_reference | comparison | source_file |
| --- | --- | --- | --- | --- | --- | --- | --- |
| IncT5x_3 | 5X | 1.000 | 3600.000 | 56880.968 | 54879.119 | standalone_rf_json | experiments\matheuristics\results_pilot\IncT5x_3_rf_fo_seed1.json |
| IncT5x_3 | 5X | 1.000 | 3600.000 | 57006.921 | 54879.119 | standalone_rf_json | experiments\matheuristics\results_tuning\IncT5x_3_rf_fo_seed1_omega12_tlfo30.json |
| IncT5x_3 | 5X | 1.000 | 3600.000 | 57006.921 | 54879.119 | standalone_rf_json | experiments\matheuristics\results_tuning\IncT5x_3_rf_fo_seed1_omega12_tlfo60.json |

