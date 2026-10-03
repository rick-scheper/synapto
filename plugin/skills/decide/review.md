# /decide review

Test the choice the developer made in an open decision lesson, then give your opinion. There is no wrong choice. A good review leaves the developer able to **defend** their choice, or knowingly change it.

## 1. Read the decision

Run `synapto decision show <lesson id>`. It prints JSON: the question, the criteria, the options, your sealed `recommendation`, the developer's `choice` (option and reasoning) and any earlier `review`.

- `choice` is `null`: tell the developer to pick an option and write down why on the lesson's Options tab, then run the review again. Stop.
- `review` is set: the decision was reviewed before. Ask whether they want to review it again; the new verdict replaces the old one.

**Done when** you have their option and their reasoning in front of you.

## 2. Challenge

Find the weakest points in *their reasoning*: a criterion they ignored, a constraint their option strains, an assumption about scale or team that the context contradicts. Ask 2–4 questions, one at a time, and wait for each answer before the next. Each question targets one weak point and is answerable in a few sentences.

Keep your recommendation to yourself while you ask. Name it only after the last answer.

**Done when** each weak point has been asked about and answered, and the developer has said which option they settle on — their original choice or another.

## 3. Verdict

Write the verdict to a file in a temporary directory:

```json
{
  "final_option": "postgis",
  "challenges": [
    { "question": "The question you asked.", "response": "A one-line summary of their answer." }
  ],
  "opinion": "Markdown. Your view of their final choice and their reasoning: where it holds, where it is thin, and how it compares with your recommendation and why."
}
```

`final_option` is an option id from `decision show`. Then run `synapto decision verdict <lesson id> <file>`.

**Done when** the command prints `Stored the verdict`. Tell the developer the hub's Options tab now shows the verdict and your original recommendation.

## 4. Record

Offer to record the decision as an ADR in the project. If the project already keeps ADRs (often `docs/adr/`), follow their format and numbering; otherwise propose `docs/adr/0001-<slug>.md`. The ADR records the developer's final choice, the options considered, and their reasoning, with your opinion as a dissent when you disagreed.

If they accept, write it, then link it: `synapto decision verdict <lesson id> <file> --adr <path relative to the repo>`.

**Done when** the developer has declined, or the ADR exists and the verdict links it.
