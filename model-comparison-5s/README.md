# Wan 2.7 × Veo 3.1 Lite — 5-second comparison

Static, dependency-free demo for `PROMOPAGES-9681`.

## Local preview

From this directory:

```sh
python3 -m http.server 4173 --bind 127.0.0.1
```

Then open `http://127.0.0.1:4173/`.

The page uses only relative asset paths and can also be opened directly from
`index.html`. `comparison-data.js` is a deliberate allowlist extracted from the
local generation manifest. The full manifest, raw provider files, API metadata,
and generation scripts are excluded from publication.
