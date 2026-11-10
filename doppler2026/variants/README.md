# Variants

Proposed changes to Doppler that a study compares against the current
version, for example `sparsification_fix.py`. Variants are **ephemeral**:
when the comparison is done, a variant is either promoted into the real
modules or deleted. Keeping one longer is the user's decision, case by case,
and is noted in `CHANGES.md`. Older variants are found in git history, not
here.

A variant changes behaviour, so whether to try it, and whether to promote
it, are scientific decisions for the user (`CLAUDE.md`, "Research
ownership").

## Writing a variant

One module per proposal, `variants/<name>.py`. Its docstring states:

- the problem it addresses (e.g. a driver in `docs/decisions.md`,
  "What drives the sparsification");
- what it changes, and every new assumption or departure from the paper;
- the study that tests it.

The module defines replacement functions and a `REPLACEMENTS` dict
`{module: {name: replacement}}`. A study runs the current and the variant
version side by side:

```python
from doppler2026.variants import applied
from doppler2026.variants import sparsification_fix as fix

baseline = run(config)
with applied(fix.REPLACEMENTS):
    proposed = run(config)
```

`applied` swaps the functions in for the duration of the `with` block and
restores them afterwards, so the real modules are never edited and other
runs are unaffected. Replace the function where it is looked up: if
`controller.py` does `from .filters import operational_check`, replace
`controller.operational_check`, not `filters.operational_check`. The
study's `config.json` should record which variant ran.

If the change is only a new setting, a new optional parameter in the real
module (default = current behaviour) is simpler than a variant.

## Promoting or deleting

- **Promote:** move the change into the real module, normally as an option
  whose default the user chooses; record the decision in
  `docs/decisions.md`, update the docs it affects, and delete the variant.
- **Delete:** remove the module; the study's results and `CHANGES.md` say
  what was tried and why it was dropped.

## Current variants

None.
