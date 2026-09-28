# Theory Test Drill

Practice app for the Singapore driving theory tests: 800 questions from 6 BTT and 10 FTT practice papers.

## To study

- **Easiest:** open `dist/theory-test-drill.html` in any browser. It is one file with everything inside, so it works offline and can be copied to a phone.
- **Website:** https://handsomejj12.github.io/btt-ftt-quiz/ (GitHub Pages, updates on every push to `main`).
- **Claude link:** https://claude.ai/artifact/8zDggKiNu35nXNCDHHxN2d (private, needs your Claude login).
- **With links to the original screenshots:** open `index.html`. It needs the `img/` folder next to it.

Practice mode shows the answer after each question. Mock test is timed (50 minutes for 50 questions) and marked at the end. Pass mark is 45 of 50.

## To rebuild after changing questions

```
python tools/build.py
```

It reads `data/verified/`, applies any hand fixes in `data/fixes.json`, and writes `index.html`, `questions.js` and `dist/theory-test-drill.html`. The correct answer always comes from the blue row in each screenshot (`data/layout.json`), and the build prints any question where the transcript disagrees. Source typos are kept as printed and listed in `data/notes.txt`.
