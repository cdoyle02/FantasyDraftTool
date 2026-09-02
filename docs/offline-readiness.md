# Offline draft readiness

Complete this check on the device and browser that will be used for the draft.

1. Open the app while online and install it when the browser offers the option.
2. Import projections and confirm the expected player count.
3. Configure the league, draft position, and user adjustments.
4. Wait for the app's **Offline ready** indicator. This confirms that the app
   shell, Pyodide runtime, and DVS engine package are cached.
5. Click **Export draft log** in the header and confirm that a dated
   `fantasy-draft-evaluation-YYYY-MM-DD.json` file downloads.
6. Disable networking and enter several mock picks. Confirm that the board,
   rosters, and recommendations continue to update.
7. Re-enable networking and confirm that the connection indicator returns to
   online without losing picks.

The active draft and adjustments are stored in this browser profile. Clearing
site data or using a private window removes them. Keep the tab or installed app
open during a draft and retain the exported backup until cloud accounts are
available.

## Exporting a completed draft for analysis

1. After the final pick is recorded, click **Export draft log** in the app
   header.
2. Confirm that `fantasy-draft-evaluation-YYYY-MM-DD.json` is present in your
   browser's Downloads folder and is not an empty file.
3. Keep the original JSON unchanged. Do not open and re-save it in a spreadsheet
   or text editor.
4. Send or attach that JSON file for V4.1 analysis. It contains the final board
   plus the pre-pick roster, available pool, ranked recommendations, score
   breakdowns, effective simulation configuration, and actual selection for
   each of your picks.

## Supported browsers

Current Chrome, Edge, and Firefox desktop releases are supported. Chromium-based
browsers provide the best install experience. Safari is not a release target
until its service-worker, storage, and Pyodide behavior is covered by automated
and manual tests.
