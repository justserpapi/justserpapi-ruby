# JustSerpAPI Ruby SDK

OpenAPI-first Ruby SDK for the JustSerpAPI HTTP interface. The repository commits the fetched upstream spec, a deterministic normalized spec, and the generated low-level Ruby runtime so endpoint additions and changes flow through code generation instead of manual SDK edits.

## Install

```bash
gem install justserpapi
```

Or add it to your Gemfile:

```ruby
gem "justserpapi"
```

## Quick Start

```ruby
require "justserpapi"

client = JustSerpApi::Client.new(api_key: ENV.fetch("JUSTSERPAPI_API_KEY"))

search = client.google.search(query: "coffee shops in New York", language: "en")
maps = client.google.maps.search(query: "espresso bars", location: "Shanghai")
news = client.google.news.search(query: "OpenAI", language: "en")
images = client.google.images.search(query: "espresso machine")
shopping = client.google.shopping.search(query: "espresso tamper")
overview = client.google.ai.overview(url: "https://example.com/ai-overview")

puts search["code"]
puts search["data"]
```

The high-level client returns the standard JustSerpAPI response envelope as a Ruby `Hash`. Low-level generated classes stay public for full endpoint coverage.

## Public API

- `JustSerpApi::Client`
- `client.google.search(query:, **opts)`
- `client.google.autocomplete(query:, **opts)`
- `client.google.maps.search(query:, **opts)`
- `client.google.news.search(query:, **opts)`
- `client.google.images.search(query:, **opts)`
- `client.google.shopping.search(query:, **opts)`
- `client.google.ai.overview(url:, **opts)`
- `client.google.ai.mode(query:, **opts)`
- `JustSerpApi::GoogleApi` for advanced low-level access to all generated operations

## Configuration

```ruby
client = JustSerpApi::Client.new(
  api_key: ENV.fetch("JUSTSERPAPI_API_KEY"),
  base_url: "https://api.justserpapi.com",
  timeout: 20,
  user_agent: "my-app/1.2.3"
)
```

`api_key` is injected into both `X-API-Key` and `api_key` for compatibility with the generated low-level client.

## Regenerate the SDK

Fetch the live OpenAPI document, normalize it, regenerate the SDK, and sync the committed generated runtime:

```bash
JUSTSERPAPI_OPENAPI_API_KEY=... python3 scripts/sdkctl.py sync
```

Rebuild from the checked-in raw spec without hitting the network:

```bash
python3 scripts/sdkctl.py sync --skip-fetch
```

Verify the committed generated runtime is already up to date:

```bash
python3 scripts/sdkctl.py sync --skip-fetch --check
```

Run the control-plane unit tests:

```bash
python3 -m unittest discover -s scripts/tests -v
```

Run the Ruby tests:

```bash
bundle exec rake test
```

## Spec Artifacts

- `openapi/raw/justserpapi.openapi.json`: exact fetched upstream document
- `openapi/normalized/justserpapi.openapi.json`: deterministic codegen input
- `openapi/baseline/justserpapi.openapi.json`: last released normalized spec for breaking-change checks

The upstream spec currently lacks rich per-endpoint response schemas, so the normalized spec injects a shared `JustSerpApiResponse` envelope with `data` as a generic object/Hash.

## Release Flow

1. Run `python3 scripts/sdkctl.py sync --skip-fetch --check`.
2. Run `python3 scripts/sdkctl.py verify-release --tag vX.Y.Z`.
3. Update `lib/justserpapi/version.rb` to the intended gem version.
4. Push a matching `vX.Y.Z` tag.
5. GitHub Actions publishes the gem to RubyGems.org and creates a GitHub Release.

RubyGems Trusted Publishing setup is documented in `docs/publishing.md`.

