# Publishing Setup

The release workflow publishes this SDK to RubyGems.org through Trusted Publishing and creates a GitHub Release for the pushed tag.

## One-Time RubyGems Setup

1. Create or log into the RubyGems.org account that will own `justserpapi`.
2. Configure a pending Trusted Publisher for:
   - gem name: `justserpapi`
   - repository owner: `justserpapi`
   - repository name: `justserpapi-ruby`
   - workflow filename: `release.yml`
   - environment: `release`
3. After the first successful publish, RubyGems will convert the pending publisher into a normal trusted publisher for the gem.

## GitHub Repository Setup

- The release workflow uses the `release` GitHub Actions environment.
- No long-lived RubyGems API key is required.
- The workflow needs `contents: write` and `id-token: write`.
- For the scheduled OpenAPI sync workflow, configure:
  - `JUSTSERPAPI_OPENAPI_USERNAME`
  - `JUSTSERPAPI_OPENAPI_PASSWORD`
  - `JUSTSERPAPI_OPENAPI_URL` only if the docs URL itself changed

## Release Procedure

1. Merge any pending OpenAPI sync PR.
2. Update `lib/justserpapi/version.rb` to the intended release version.
3. Run:

   ```bash
   python3 scripts/sdkctl.py sync --skip-fetch --check
   python3 scripts/sdkctl.py verify-release --tag vX.Y.Z
   ```

4. Create and push a matching Git tag, for example `v0.1.0`.
5. The `release.yml` workflow will build the gem, publish it to RubyGems.org, and create the GitHub Release.
