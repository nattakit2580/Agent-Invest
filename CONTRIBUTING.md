# Contributing

## Development setup

1. Fork or clone the repository.
2. Install Python 3.11+, Node.js 20 LTS, and Git.
3. On Windows, run `./setup.ps1`. On any platform, follow the manual setup in
   `README.md` or use Docker Compose.
4. Copy only example environment files. Never commit `.env`, local databases,
   logs, virtual environments, `node_modules`, or build output.
5. Run the validation commands below before opening a pull request.

## Validation

```powershell
cd backend
python -m compileall -q .
python -m unittest discover -s tests -v

cd ../frontend
npm run audit:prod
npm run build
```

## Pull requests

- Keep changes focused and explain user-visible behavior.
- Add or update tests when changing shared backend behavior.
- Include setup or environment changes in `.env.example` and the README.
- Do not include credentials or customer data in screenshots, logs, fixtures,
  commits, or pull-request descriptions.
