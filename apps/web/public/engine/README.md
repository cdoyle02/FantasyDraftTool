# Offline engine asset

Run `pnpm build:engine` from the repository root before a production web build.
It writes `dvs_engine-0.1.0-py3-none-any.whl` here. Wheels are generated release
artifacts and are not committed.
# Offline DVS engine asset

Place the production wheel at `public/engine/dvs_engine.whl`, or set
`VITE_DVS_WHEEL_URL` to its public URL. The wheel must expose:

```python
from dvs_engine import recommend_json
result = recommend_json(request_dict)
```

The return shape must match `RecommendationResponse` in `src/api/client.ts`.
The service worker caches the wheel and Pyodide runtime after first use.
The repository does not currently contain the Python engine artifact.
