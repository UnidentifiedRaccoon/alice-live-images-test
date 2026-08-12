# Tune approved S3 export

This directory freezes the two reviewer exports and the exact 45-video
selection used for the PROMOPAGES-10060 Tune follow-up:

- 37 Helped rows from the v4 evaluation;
- 6 Helped rows from the v6 evaluation;
- the explicitly requested latest Wan 2.2 videos for 17#11 and 18#06.

The selection contract binds the exact evaluation files, current Tune
manifest, media commit, S3 routing config, evaluation IDs, counts, and
selection policy. The exporter fails if any bound input, current video,
local byte count, or SHA-256 changes.

Local workflow:

```bash
python3 scripts/promopages_10060_tune_s3_export.py validate-selection
python3 scripts/promopages_10060_tune_s3_export.py build --materialize hardlink
python3 scripts/promopages_10060_tune_s3_export.py verify
python3 scripts/promopages_10060_tune_s3_export.py upload
```

The last command is a dry-run: it performs no network calls or writes.

External execution:

```bash
python3 scripts/promopages_10060_tune_s3_export.py upload \
  --yc-profile promopages-internal \
  --execute
```

Execute mode performs HEAD-before-PUT, skips exact existing objects, refuses
immutable-key conflicts, verifies every object through yastatic, and only then
writes:

```text
clipmaker-lite-test/promopages-10060-tune-approved-s3-overlay.json
```

The overlay must not be created or committed from a planned or partial upload.
