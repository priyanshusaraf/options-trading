# Frontend boundary

Frontend implementation is owner-gated. Unless the owner explicitly authorizes frontend work in the active capsule, stop at the API contract and record UI requirements without editing this directory.

When authorized, preserve the centralized REST client, single WebSocket, backend-owned truth, and visible unknown/error states. Verify the actual operator flow, console, network, loading/error/empty states, desktop layout, and 390 by 844 layout. Use mock data or a safely started local backend; never connect the UI to live authority for verification.

Run the capsule's focused checks first. At the frontend slice gate use the applicable tests, typecheck, and build. Screenshots support behavioral evidence but do not replace it.
