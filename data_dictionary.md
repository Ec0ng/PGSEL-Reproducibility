# Data Dictionary

This document describes the processed sample-level data format used in the experiments.

Due to platform terms of service and privacy considerations, the full raw Bilibili comment dataset cannot be publicly redistributed. Therefore, this repository only provides anonymized sample records to illustrate the processed data format used for model training.

## Processed Sample-Level Data

Each row in `examples/anonymized_sample_records.csv` corresponds to one sample constructed from an observation window of a short video.

In this study, each observation window contains 8 hourly time steps. The prediction target is whether a public opinion burst occurs in the subsequent prediction period.

## Field Descriptions

| Field | Type | Description |
|---|---|---|
| `sample_id` | string | An anonymized identifier for each sample. This field is used only to distinguish different samples and does not correspond to the original video ID or user information. |
| `comment_count_t1` to `comment_count_t8` | integer | The number of comments in each of the 8 hourly time steps of the observation window. For example, `comment_count_t1` denotes the comment count in the first time step, and `comment_count_t8` denotes the comment count in the eighth time step. |
| `pos_comment_ratio_t1` to `pos_comment_ratio_t8` | float | The positive-comment ratio in each of the 8 hourly time steps of the observation window. Each value is calculated as the number of positive comments divided by the total number of comments in the corresponding time step. |
| `video_title` | string | The desensitized or anonymized video title used as the title modality. To protect privacy and comply with platform restrictions, original video titles are not publicly redistributed in the sample records. |
| `comment_words` | string | The collection of comment words extracted from comments within the observation window after preprocessing, including word segmentation, stopword removal, and low-frequency word filtering. The words are separated by semicolons in the sample file. |
| `label` | integer | The binary burst label of the sample. `1` denotes a burst sample, and `0` denotes a non-burst sample. The labels were generated using Kleinberg's burst detection model. |

## Notes on Feature Construction

### Comment-count sequence

The fields from `comment_count_t1` to `comment_count_t8` represent the temporal evolution of discussion intensity within the 8-hour observation window. These fields are used as part of the comment time-series modality.

### Positive-comment-ratio sequence

The fields from `pos_comment_ratio_t1` to `pos_comment_ratio_t8` represent the temporal evolution of comment sentiment within the 8-hour observation window. A RoBERTa-based sentiment classifier was used to identify positive comments, and the positive-comment ratio was calculated for each hourly time step.

### Video title

The `video_title` field is used as the title modality. In the released sample records, this field is desensitized or anonymized and is provided only to illustrate the input format.

### Comment-word collection

The `comment_words` field contains the processed word collection extracted from comments within the observation window. This field is used to construct the keyword graph modality. The semantic prior and co-occurrence prior are further constructed based on these comment words.

### Burst label

The `label` field indicates whether a public opinion burst occurs in the subsequent prediction period. The labels were generated using Kleinberg's burst detection model with the following default parameters:

```text
K = 1
s = 2.0
gamma = 1.0