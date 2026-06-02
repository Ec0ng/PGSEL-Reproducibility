# Preprocessing Description

This document describes how the raw crawled comment data were transformed into the processed sample-level data used for model training.

Due to platform terms of service and privacy considerations, the raw Bilibili comments, user identifiers, usernames, user profile information, original comment URLs, and original video URLs are not publicly redistributed. This document only describes the preprocessing pipeline and the construction of the processed training samples.

## Overview

The preprocessing pipeline consists of the following main steps:

1. RoBERTa-based sentiment annotation;
2. Hourly comment-count aggregation;
3. Kleinberg-based burst label generation;
4. Sliding-window sample construction;
5. Comment-word preprocessing;
6. NPMI-based co-occurrence prior construction;
7. Word-frequency calculation and deduplication;
8. Final sample-level training data construction.

## 1. RoBERTa-Based Sentiment Annotation

After the comments were crawled, a RoBERTa-based sentiment classifier was first applied to each comment.

Each comment was assigned a sentiment label. In this study, the sentiment annotation results were used to calculate the positive-comment ratio for each hourly time step.

For each video and each hourly time step, the positive-comment ratio was calculated as:

positive-comment ratio = number of positive comments / total number of comments

The positive-comment ratio was then used as one of the comment time-series features in the final training samples.

## 2. Hourly Comment-Count Aggregation

For each video, the number of comments was counted within the first 24 hours after the video was published.

The 24-hour period was divided into hourly time steps. Therefore, each video was represented by a 24-step comment-count sequence:

[comment_count_1, comment_count_2, ..., comment_count_24]

Each value represents the number of comments received by the video in the corresponding hourly time step.

## 3. Kleinberg-Based Burst Label Generation

Based on the 24-hour comment-count sequence of each video, Kleinberg's burst detection model was used to generate burst labels for each hourly time step.

The model assigns a burst or non-burst state to each time step according to the temporal changes in comment volume.

The default parameters used in this study are:

K = 1  
s = 2.0  
gamma = 1.0

The generated burst label for each time step is binary:

1 = burst  
0 = non-burst

These hourly burst labels were later used as the prediction targets of the constructed samples.

## 4. Sliding-Window Sample Construction

After obtaining the hourly comment-count sequence, positive-comment ratios, and Kleinberg-based burst labels, sample-level data were constructed using a sliding-window strategy.

For each prediction time step, the preceding 8 time steps were used as the observation window.

Specifically, for a prediction time step t, the observation window consists of the previous 8 time steps:

[t-8, t-7, ..., t-1]

The label of the sample is the burst label of the corresponding prediction time step t.

Therefore, each sample contains:

- comment counts over the 8 time steps of the observation window;
- positive-comment ratios over the 8 time steps of the observation window;
- comment collection within the observation window;
- the corresponding video title;
- the burst label of the prediction time step.

The final sample-level structure is as follows:

sample_id  
comment_count_t1, comment_count_t2, ..., comment_count_t8  
pos_comment_ratio_t1, pos_comment_ratio_t2, ..., pos_comment_ratio_t8  
video_title  
comment_words  
label

## 5. Comment-Word Preprocessing

For each sample, all comments within the 8-step observation window were collected to form the comment collection.

The comment collection was then processed through the following steps:

1. Chinese word segmentation;
2. Text cleaning;
3. Stopword removal;
4. Low-frequency word filtering.

The resulting words were used to construct the keyword graph modality.

## 6. NPMI-Based Co-Occurrence Prior Construction

For each sample, an NPMI-based co-occurrence prior was constructed based on the comment-word collection within the observation window.

The co-occurrence relationship between words was calculated from their co-occurrence patterns in comments. The normalized pointwise mutual information value was then used to describe the strength of the co-occurrence relationship between word pairs.

The sample-level NPMI relationship table was saved in the following file:

npmi_by_sample.pt

This file stores the NPMI-based co-occurrence prior used for constructing the keyword graph.

## 7. Word-Frequency Calculation and Deduplication

After word segmentation and cleaning, the frequency of each word was calculated within each sample.

After word-frequency calculation, duplicate words were removed, so that each retained word appeared only once in the final word collection of a sample.

The word-frequency information was used to filter noisy words and retain representative comment words within the observation window.

## 8. Final Training Samples

After the above preprocessing steps, the final sample-level training data were obtained.

Each final sample contains the following fields:

| Field | Description |
|---|---|
| sample_id | An anonymized sample identifier. |
| comment_count_t1 to comment_count_t8 | Comment counts over the 8 time steps of the observation window. |
| pos_comment_ratio_t1 to pos_comment_ratio_t8 | Positive-comment ratios over the 8 time steps of the observation window. |
| video_title | The corresponding video title. |
| comment_words | The processed and deduplicated comment-word collection within the observation window. |
| label | The burst label of the prediction time step. |

These processed sample-level records were used as the final input data for model training and evaluation.

## Privacy Protection

The released reproducibility materials do not contain raw user comments or user-related identifiers.

The following information is not publicly redistributed:

- raw comments;
- user IDs;
- usernames;
- user profile information;
- original comment URLs;
- original video URLs;
- complete crawled dataset;
- crawler scripts.

Only anonymized sample records, data-field descriptions, preprocessing descriptions, and label-generation code are provided to illustrate the data construction process and improve reproducibility.