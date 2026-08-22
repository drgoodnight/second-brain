# Known Issues

*A log of non-obvious bugs: what they looked like, what turned out to be wrong (and what we wrongly suspected first), and how they were actually fixed. Purpose is to avoid re-walking the same debugging path twice.*

---

## Template for new entries

```markdown
## [Symptom] — short, searchable title

**Date found:**
**Symptom:** What you actually observed
**False leads ruled out:** Plausible theories that turned out wrong, and why
**Root cause:** What it actually was
**Diagnostic:** The exact command(s) that confirm it
**Fix / mitigation:** What resolved it, and any caveats
**Status:** Resolved / Monitoring / Workaround only
```

---

## Calendar-add requests taking 3+ minutes — GPU memory fragmentation

**Date found:** 2026-08-19 to 2026-08-20

**Symptom:** Calendar-add messages ("add event: ...") were taking 3-5 minutes to get a reply, while calendar queries ("what's on today") stayed fast (sub-1-minute). No errors in n8n — every execution "succeeded," just slowly.

**False leads ruled out** (in the order suspected, cheapest to check first):

1. **Concurrent model residency (two models loaded at once).** Suspected because the router uses `gemma3:12b` for classification + ICS generation and `qwen3.5:9b` for chat. Ruled out by checking the ollama server config: `OLLAMA_MAX_LOADED_MODELS:1` — only one model can ever be resident, so no simultaneous-VRAM scenario exists.
2. **Desktop GPU contention (Xorg/Firefox/VS Code stealing VRAM from Ollama).** Plausible since this box runs a live desktop session on the same GPU, not headless. Ruled out once we captured the scheduler's own logged free-memory figure at the moment of a failed load: `available="15.1 GiB"` — far more than the ~10GB the model needs, so contention wasn't the bottleneck.
3. **Reasoning/thinking tokens in the ICS generator** (the same failure mode already known to affect `qwen3.5:9b` on the chat branch — see design brief). Ruled out because the slow runs showed the model landing on CPU entirely (`ollama ps` → `100% CPU`), which alone accounts for the delay regardless of token count.
4. **Marginal VRAM margin with `OLLAMA_GPU_OVERHEAD:0`.** Suspected once the fit→alloc→commit log sequence was found (scheduler says "fits" then "doesn't fit" ~300ms later). Ruled out by the same free-memory figure as #2 — a 5GB+ margin is too large to be explained by a missing safety buffer.
5. **`nvidia-smi -pm 1` (persistence mode).** Tried as a fix for "GPU dropping to low-power state (P8) between requests, causing a cold-start allocation race." Enabled successfully, but the CPU-fallback recurred immediately afterward on a fresh request — ruled out as the fix, though persistence mode is still worth keeping on generally.

**Root cause:** CUDA memory allocator fragmentation, not scarcity. `nvidia-smi`'s aggregate "free" VRAM figure can look ample (15GB+ free) while no single *contiguous* block large enough for the model (~10GB) actually exists, after a long-running desktop session has interleaved many small GPU allocations/deallocations (window compositing, browser tabs, editor rendering) with Ollama's own memory space. Ollama's scheduler estimates a fit against the aggregate number, then fails at the real `alloc`/`commit` step when it can't find a contiguous span — and falls back to 100% CPU rather than a partial offload.

**Diagnostic:**

```bash
# Check current placement of a loaded model — the decisive check
docker exec ollama ollama ps
# PROCESSOR column: "100% GPU" = healthy, "100% CPU" (or a split) = fragmentation hit

# See the scheduler's own reasoning for a specific incident
docker logs ollama --since <window> 2>&1 | grep -iE "loading model|gpu memory|system memory|GPULayers|offload"
# Look for: "gpu memory" logs a large free figure, then "GPULayers:[]" a few hundred ms later
```

**Fix / mitigation:** A full host reboot resolved it immediately — first request after reboot landed cleanly at `100% GPU`, confirmed via `ollama ps` and `nvidia-smi` showing `ollama` process at ~9.6GB VRAM with 93% GPU-Util.

**Update (2026-08-22):** Symptom recurred. This time, `docker restart ollama` alone (no host reboot) resolved it — first request after the container restart landed cleanly on GPU. This narrows the root cause: since `OLLAMA_MAX_LOADED_MODELS:1` means Ollama constantly loads/evicts `gemma3:12b` and `qwen3.5:9b` on every intent switch, the fragmentation most likely accumulates inside Ollama's own long-lived CUDA context from that repeated churn — not from the wider desktop session (Xorg/Firefox/etc.) as originally suspected. A full host reboot "worked" the first time only because it resets the container too, not because the desktop was the actual source.

**Caveat:** n=1 on the container-only fix so far. Treat as a strong lead, not yet fully confirmed — watch for whether it holds on the next recurrence before relying on it.

**Practical mitigation, pending further confirmation:** a scheduled `docker restart ollama` (e.g. nightly cron) is looking like a viable, low-disruption fix — cheaper than a host reboot cadence since it doesn't touch the desktop session at all.

**Status:** Monitoring. Root cause understood; likely mitigation identified (container restart) but not yet confirmed on repeat occurrence or automated.

---

## ICS DTSTAMP off by one hour — no BST/UTC conversion

**Date found:** 2026-08-22

**Symptom:** Generated ICS events have a `DTSTAMP` value that's numerically identical to the `nowStamp` input field, just with a `Z` appended (e.g. input `nowStamp: 20260822T161929` at 16:19 local time → output `DTSTAMP:20260822T161929Z`). Since Aug 22 is within British Summer Time (UTC+1), the correct UTC value should be `20260822T151929Z` — an hour earlier.

**False leads ruled out:** None — found on first check, not from chasing a reported problem. Surfaced while reviewing the `AI ICS Generator` system prompt ahead of a model-tiering comparison, as a "confirm the baseline is actually correct before comparing a smaller model against it" check.

**Root cause:** The system prompt instructs the model to output `DTSTAMP` as "now in UTC with Z," but `nowStamp` is passed in as local time with no timezone marker, and the model isn't doing the local→UTC conversion — it's just appending `Z` to whatever it's given. This almost certainly went unnoticed because the prompt's worked examples were all authored on 2026-01-26, during GMT (UTC+0) — when local time and UTC are numerically identical, so the bug produces a correct-looking answer all winter. It only became detectable once BST (UTC+1) took effect and the two clocks diverged.

**Diagnostic:** Open any recent `AI ICS Generator` execution and compare the input `nowStamp` field against the output `DTSTAMP:` line. If they're numerically identical (same digits, output just has `Z` added) and the current date is within BST, the conversion isn't happening.

**Fix / mitigation:** Not yet implemented. Planned approach: compute the correct UTC timestamp upstream in code (the same node that already builds `today`/`nowStamp`, e.g. via `new Date().toISOString()` reformatted to match) and pass it in as its own field, rather than asking the model to perform timezone arithmetic at all — same philosophy as moving recurring-event date enumeration into deterministic code (see model-tiering design brief).

**Practical impact:** Low. `DTSTAMP` is bookkeeping metadata (when the entry was created) — it isn't displayed in any calendar view and doesn't affect scheduling. `DTSTART`/`DTEND` are unaffected, since those are built explicitly from `TZID=Europe/London` local time, not from `nowStamp`. Nothing actually scheduled is wrong; this only matters for anything that reads `DTSTAMP` directly, and for not misreading a smaller model's *correct* UTC math as a regression during tiering comparisons.

**Status:** Workaround only (currently just known and worked around by ignoring `DTSTAMP` accuracy) — fix not yet implemented.
