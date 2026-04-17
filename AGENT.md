# OpenMontage Local Notes

- Responding agents must read `AGENT_GUIDE.md` before acting.
- This working copy uses `origin` for the personal fork and `upstream` for `calesthio/OpenMontage`.
- Keep `main` as the upstream-sync branch. Fast-forward it from `upstream/main`; do not use it for feature work.
- Do long-lived customization work on `product-main`, and branch short-lived feature branches from `product-main`.
- Prefer additive customization (`providers/`, new tools, new UI, new pipelines) over hard edits to core orchestration when possible.
- For MiniMax integration, prefer official direct APIs over fal.ai proxy paths. Use `MINIMAX_API_KEY` plus `MINIMAX_API_HOST` (`https://api.minimaxi.com` for CN, `https://api.minimax.io` for Global).
- Treat MiniMax Token Plan limits as live metadata, not hardcoded constants. Current docs indicate text uses a 5-hour rolling window, while non-text quotas reset daily and should be surfaced from the provider or quota endpoint when possible.
