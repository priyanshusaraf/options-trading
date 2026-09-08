# Legacy frontend work

- This directory contains the legacy bot UI. The V0 product UI is in `../strategy-frontend`.
- Use the existing REST client and WebSocket. Readiness comes from the backend.
- Keep loading, empty, unavailable and error states distinct. Never present missing data as zero or success.
- Preserve accepted design choices. Check affected controls, keyboard access, focus, browser errors and relevant screen sizes.
- Verify the actual preview URL and route. Label example data.
- Run affected tests, type checks and the build for integrated UI changes.
