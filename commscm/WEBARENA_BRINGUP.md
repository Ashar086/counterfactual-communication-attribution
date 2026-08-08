# WebArena official environment bring-up (Part VI.C)

**Prereg:** `commscm/PART_VI_C_PREREGISTRATION.md` (frozen).  
**Rule:** No CommSCM changes. Official Success only from live evaluators.

## Capacity reality (this machine, 2026-08-04)

| Image | Compressed size |
|-------|-----------------|
| shopping | ~63 GB |
| shopping_admin | ~9 GB |
| forum (reddit) | ~50 GB |
| gitlab | ~72 GB |
| wikipedia zim | ~89 GB |
| **Total** | **~283 GB compressed** (+ load expansion) |

Local free disk at assessment: **~41 GB** on C: and D:. **Full local stack does not fit.**

Locked n=100 site mix: gitlab 24 · shopping 25 · reddit 18 · map 16 · shopping_admin 18 · wikipedia 3.

## Recommended path (upstream)

Use the public AMI (us-east-2):

- Name: `webarena-with-configurable-map-backend`
- ID: `ami-08a862bf98e3bd7aa`
- Instance: ≥ `t3a.xlarge`, ~1000 GB EBS

Then point this repo at that host:

```powershell
$env:WEBARENA_ROOT = "D:\WebArena\webarena"   # or clone on the AMI
$env:SHOPPING = "http://<host>:7770"
$env:SHOPPING_ADMIN = "http://<host>:7780/admin"
$env:REDDIT = "http://<host>:9999"
$env:GITLAB = "http://<host>:8023"
$env:MAP = "http://<host>:3000"
$env:WIKIPEDIA = "http://<host>:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
$env:HOMEPAGE = "http://<host>:4399"

python -m commscm.experiments.part_vi_c_env_status
python -m commscm.experiments.part_vi_c_official_runner --out results/part_vi_c_official.json
```

## Local partial path (wire proof only)

If only `shopping_admin` is loaded (~9 GB), that can validate Docker↔adapter wiring for **18/100** locked tasks.  
**It does not replace the preregistered n=100 primary result.**

```powershell
# after docker load + run shopping_admin on :7780
docker load -i D:\WebArena\images\shopping_admin_final_0719.tar
docker run --name shopping_admin -p 7780:80 -d shopping_admin_final_0719
# configure base-url per upstream README using hostname localhost / host.docker.internal
```

## Gate

`part_vi_c_official_runner` refuses to write official Success claims unless `assess_environment().ready_for_official` is true.
