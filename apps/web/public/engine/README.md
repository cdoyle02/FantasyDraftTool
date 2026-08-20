# Offline engine asset

Run `pnpm build:engine` from the repository root before a production web build.
It writes `dvs_engine-0.2.0-py3-none-any.whl` here. Wheels are generated release
artifacts and are not committed.

Set `VITE_DVS_WHEEL_URL` to override the generated wheel's public URL. The wheel
must expose:

```python
from dvs_engine import recommendation_json
result_json = recommendation_json(request_json)
```
