# Suicidality Detection Corpus (multilingual)

> ⚠️ **Content warning.** This dataset contains sentences that express or describe suicidal
> ideation, self-harm intent, hopelessness, and coded farewells, in five languages. It exists for
> research on text-classification data handling. It is **not** a clinical instrument and must never
> be used to screen, triage, diagnose, or make any decision about a real person.

## What this is

A labelled, multilingual corpus for the binary task *"does this sentence carry a suicidality
signal?"*. Each row is a short first-person message labelled `suicidality` or `neutral`.

This corpus was the **suicidality class** of an internal Input-Risk-Scorer training set at Silicon
Psyche Labs. On 2026-08-19 the company **removed user-suicidality from its product entirely**: the
production reader was retrained without this class, and no runtime path scores, stores, or alarms on
a user's suicidality any more. Reading a user's suicidal state is special-category health data and
sits outside what the product measures (the machine's behaviour, read from its output). The corpus
is published here, on its own, as a data-handling and transparency artifact, and is **not** part of
any production model.

## Schema

Newline-delimited JSON (`suicidality_detection_corpus.jsonl`); one object per line:

| field  | type            | meaning |
|--------|-----------------|---------|
| `text`  | string          | the message |
| `label` | `"suicidality"` \| `"neutral"` | class |
| `lang`  | string \| null  | `en`/`it`/`fr`/`es`/`de`, or `null` where the source left it untagged |
| `split` | `"train"` \| `"test"` | the split the row was drawn from |
| `id`    | string          | stable row id |

## Composition

- **3,511 rows**: 422 `suicidality`, 3,089 `neutral`.
- Languages: en, it, fr, es, de (plus untagged rows).
- The neutral rows include benign, technical, and *near-miss* text (bereavement, resignation,
  academic references to death) so a classifier is forced to separate a real signal from surface
  vocabulary rather than keyword-match.

## Intended use

Research and teaching on multilingual crisis-text classification, data documentation, and the
false-positive / false-negative trade-off on a high-stakes construct. Nothing here is validated for,
or licensed for, any operational or clinical use.

## Explicitly out of scope

- Any real-time screening, triage, or intervention for a real person.
- Any claim of clinical validity. Labels are text annotations, not clinical judgements, and there is
  no clinician ground truth or subject history behind them.
- Training a product that reads a user's suicidality. The originating company removed that feature by
  decision; this dataset is a record, not a starting point for reinstating it.

## If you or someone you know is in crisis

Please reach a local crisis line. In the US you can call or text **988** (Suicide & Crisis
Lifeline). International directories: <https://findahelpline.com>.

## License

Released under **CC BY-NC-SA 4.0**. You may share and adapt for non-commercial research with
attribution and share-alike, subject to the out-of-scope limits above.
