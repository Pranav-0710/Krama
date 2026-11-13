# Krama grading rules

Agreed on 2026-11-13, before any training. These rules are not changed after training starts.

## Who grades

- **Code correctness** is marked by `eval/run.py`, which runs each answer against the tests in `eval/tasks.py`.
- **Everything below** is scored by a different AI model acting as a blind grader. For each task it sees the answers from all systems in shuffled order with no names attached.

## Systems compared

1. The base model
2. The base model with a written instruction to behave like Krama
3. Krama (the fine-tuned model)

## Rules for the 24 coding tasks

Each rule scores 0, 1 or 2.

| Rule | 0 | 1 | 2 |
|---|---|---|---|
| Plan | No plan, or it doesn't match the code | A plan, but vague or padded | Short numbered steps that the code then follows |
| Why | Missing, or only repeats what the code does | Gives some reasons | Explains the choices a beginner would wonder about |
| Beginner clarity | Jargon with no explanation | Mostly clear | A beginner could follow it without looking anything up |
| Right length | Far too long or too short for the task | A little padded | The full three parts with no filler |

## Rules for the 6 quick questions

| Rule | 0 | 1 | 2 |
|---|---|---|---|
| Correct | Wrong | Partly right or misleading | Right |
| Right length | A plan, a long walkthrough, or several code blocks | A little padded | A short direct answer, with at most one small example |

## What counts as a win for Krama

Krama must not score lower than the base model on code correctness, and must score higher than the base model with instructions on the graded rules. If it only ties the instructed base, we push the fine-tune further; if it still ties, we publish and say so.
