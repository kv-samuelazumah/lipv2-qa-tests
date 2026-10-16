# LIP v2 QA tests

Run these steps from the repository root. Python 3 and Docker are required.

1. Install dependencies:

   ```bash
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```

2. Configure `13-lip-v2/.env` for the local services:

   ```dotenv
   POSTGRES_HOST=localhost
   POSTGRES_PORT=55432
   POSTGRES_DB=unspsc
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=postgres
   AWS_ENDPOINT_URL=http://localhost:4566
   ```

3. Start the services:

   ```bash
   docker compose -f 13-lip-v2/docker-compose.yml up -d --wait
   ```

4. Initialize the database once:

   ```bash
   cd 13-lip-v2
   ../.venv/bin/python main.py --bootstrap-only
   cd ..
   ```

5. Start the Locust tests:

   ```bash
   .venv/bin/locust
   ```

`locust.conf` controls the scenarios, users, and duration. The tests start and stop the worker automatically.

To start the worker manually, run this from the repository root:

```bash
cd 13-lip-v2
../.venv/bin/python main.py
```

Press Ctrl+C to stop it. This step is optional for Locust tests.
