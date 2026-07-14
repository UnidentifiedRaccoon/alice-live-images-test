# Wan 2.7 × Veo 3.1 Lite — 5-second comparison

Static, dependency-free demo for `PROMOPAGES-9681`.

## Local preview

From this directory, move one level up and start the server at the repository root:

```sh
cd ..
python3 -m http.server 4173 --bind 127.0.0.1
```

Then open `http://127.0.0.1:4173/model-comparison-5s/`.

The root server is required because the shared navigation and styles live one
level above this demo. `comparison-data.js` is a deliberate allowlist extracted
from the local generation manifest. The full manifest, raw provider files, API
metadata, and generation scripts are excluded from publication.
