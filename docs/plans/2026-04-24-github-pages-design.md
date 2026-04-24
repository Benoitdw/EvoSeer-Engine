# GitHub Pages Site — Design Document
_2026-04-24_

## Stack

| Besoin | Techno |
|--------|--------|
| Site | Astro + Starlight |
| Notebooks | nbconvert → HTML iframe (semi-interactif, widget state) |
| Visualiseur | île React (lib phylogénétique TBD) |
| CLI UI | placeholder React |
| Deploy | GitHub Pages |
| JS tooling | pnpm + TypeScript |

## Structure repo

```
EvoSeerEngine/
├── evoseer/
├── notebooks/            # sources .ipynb
├── docs/
└── site/
    ├── src/
    │   ├── content/docs/ # MDX docs + tutoriels
    │   └── components/   # îles React
    └── public/
        └── notebooks/    # HTML générés par nbconvert
```

## Build pipeline (GitHub Actions)

1. `nbconvert` → `public/notebooks/*.html`
2. `astro build` → site statique
3. Deploy → branche `gh-pages`

## Routine nocturne — Audit doc

- **Cron** : 2h du matin
- **Condition** : skip si aucun commit dans les 24h précédentes
- **LLM** : Gemini Flash (clé gratuite — `GEMINI_API_KEY` dans les secrets GitHub)
- **Scope** : cohérence doc/code, liens cassés, notebooks sans output, TODOs
- **Output** : GitHub Issue si findings. Pas de PR automatique.

## Ce qui reste à définir

- Design visuel → Claude Design (prompt fourni)
- Lib phylogénétique → quand on attaque le visualiseur
- Prompt exact audit Gemini → à affiner à l'usage
