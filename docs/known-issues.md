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

**Open question, not yet tested:** whether a full host reboot is actually necessary, or whether `docker restart ollama` alone is enough to clear the fragmentation. This matters for how to automate the mitigation:
- If a **container restart** is sufficient → the fragmentation lives in Ollama's own long-lived CUDA context, and a scheduled `docker restart ollama` (e.g. nightly cron) is a cheap, non-disruptive fix.
- If only a **host reboot** works → the fragmentation comes from the wider desktop session and needs a host-level reboot cadence instead.

Next time the symptom recurs, try `docker restart ollama` first before reaching for a full reboot, and update this entry with the result.

**Status:** Monitoring. Root cause understood and a working (if heavyweight) fix confirmed; permanent/automated mitigation not yet decided or implemented.
