# Strategy OS frontend

This is the repository-owned V0 candidate UI. It contains the connected account, preset, builder and research workflows. Use Node.js 24 and the npm lockfile:

```sh
npm ci --ignore-scripts
npm test
npm run typecheck
npm run build
```

The production bundle is `dist/`. Tests inspect its module graph to exclude development prototypes and keep one authenticated, same-origin `/api/v1` transport. Local HTTPS certificate paths are used only by `npm run dev`, through `STRATEGY_OS_DEV_TLS_CERT` and `STRATEGY_OS_DEV_TLS_KEY`; production builds do not read them.

The existing `../frontend` package and the separate design checkout are preserved. Future product UI changes belong here. There is no automatic sync from another checkout.

After approval of a concrete V0 candidate and destination, `../scripts/deploy.sh --strategy-os-v0` builds this package and uses the established remote `frontend/dist` serving path. That mode requires explicit `PT_VPS_HOST`, `PT_VPS_PATH`, `PT_SERVICE` and `PT_VPS_KEY`. The command without that mode retains the existing bot frontend. Do not infer deployment approval from a local build or this README.

Dependency inventory, notices and actual built-artifact checks belong in the candidate evidence. A package copy or passing component test is not a deployed journey check.
