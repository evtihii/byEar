# Recipes for the setup agent

A recipe is what someone learned while getting the voice-over out of one kind of game and back in.
The setup agent reads this list first and opens the recipe that matches the game it is looking at.

| Recipe | Engine / audio | Tried on |
|---|---|---|
| [unreal_wwise.md](unreal_wwise.md) | Unreal Engine 4/5 `.pak` + Audiokinetic Wwise (`.bnk`, `.wem`) | SILENT HILL f (UE5, pak v11, Oodle) |

No recipe fits? Work it out, and at the end write what you learned as a new recipe draft in the workspace
(`.holosii/recipe_draft.md`) — the user can add it here.

## Rules for every recipe

- The game folder is read-only. Everything you make goes into the workspace.
- Only the user's own copy, for a personal mod. Do not look for encryption keys, do not bypass DRM, anti-cheat
  or protection. If the archives are encrypted, say so and stop.
- `extract` must be re-runnable (skips what is already there) and never touches the game.
- `pack` builds the mod into `<workspace>/build/` only. Installing into the game is a separate, explicit step.
