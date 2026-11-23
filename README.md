# Road to 2030: website

Interactive overview of Team 14's Datathon analysis: knockout brackets 2006–2026 with squad value ranks, sources, pipeline, the four analysis steps and the board's likely questions.

- `index.html`: the page (no build step; fonts from Google Fonts)
- `data.js`: all numbers, generated from `../03 Daten und Analyse/data/clean`
- `build_data.py`: rebuilds `data.js` (`python3 -I build_data.py`) after the analysis changes

Preview locally: `python3 -m http.server` in this folder, then open http://localhost:8000.

Host on GitHub Pages: put `index.html` and `data.js` in a repository (root or `/docs`), then Settings → Pages → deploy from that branch and folder.
