# Data policy

Published datasets should contain transaction IDs, block hashes/heights, sampling provenance, numeric measurements, and reproducible retrieval instructions. Do not commit bulk raw transactions or decoded witness payloads.

Each dataset manifest must state:

- chain;
- Bitcoin Core version/commit;
- acquisition time in UTC;
- block range and sampling seed;
- inclusion/exclusion rules;
- label provenance and confidence, if external protocol cohorts are used;
- missing transaction/prevout counts;
- checksum of the ordered transaction-ID manifest.

RPC cookie files, usernames, passwords, and local node paths must never be committed.

