require "minitest/autorun"
require "justserpapi"

class JustSerpApiClientTest < Minitest::Test
  FakeResponse = Struct.new(:payload) do
    def to_hash
      payload
    end
  end

  class FakeGoogleApi
    attr_reader :calls

    def initialize
      @calls = []
    end

    def search(query, opts = {})
      @calls << [:search, query, opts]
      FakeResponse.new({ "code" => 200, "data" => { "query" => query, "opts" => opts } })
    end

    def maps_search(query, opts = {})
      @calls << [:maps_search, query, opts]
      FakeResponse.new({ "code" => 200, "data" => { "query" => query } })
    end

    def news_search(query, opts = {})
      @calls << [:news_search, query, opts]
      FakeResponse.new({ "code" => 200, "data" => { "query" => query } })
    end

    def images_search(query, opts = {})
      @calls << [:images_search, query, opts]
      FakeResponse.new({ "code" => 200, "data" => { "query" => query } })
    end

    def shopping_search(query, opts = {})
      @calls << [:shopping_search, query, opts]
      FakeResponse.new({ "code" => 200, "data" => { "query" => query } })
    end

    def autocomplete(query, opts = {})
      @calls << [:autocomplete, query, opts]
      FakeResponse.new({ "code" => 200, "data" => { "query" => query } })
    end

    def ai_overview(url, opts = {})
      @calls << [:ai_overview, url, opts]
      FakeResponse.new({ "code" => 200, "data" => { "url" => url } })
    end

    def ai_mode(query, opts = {})
      @calls << [:ai_mode, query, opts]
      FakeResponse.new({ "code" => 200, "data" => { "query" => query } })
    end
  end

  def test_client_applies_configuration
    client = JustSerpApi::Client.new(
      api_key: "test-key",
      base_url: "https://alt.example.com/v1",
      timeout: 12,
      user_agent: "custom-agent/1.0"
    )

    assert_equal "https", client.configuration.scheme
    assert_equal "alt.example.com", client.configuration.host
    assert_equal "/v1", client.configuration.base_path
    assert_equal 12, client.configuration.timeout
    assert_equal "test-key", client.configuration.api_key["X-API-Key"]
    assert_equal "test-key", client.configuration.api_key["api_key"]
    assert_equal "custom-agent/1.0", client.api_client.default_headers["User-Agent"]
  end

  def test_google_resource_returns_hash_payloads
    fake_api = FakeGoogleApi.new
    google = JustSerpApi::GoogleResource.new(fake_api)

    response = google.search(query: "coffee", language: "en")

    assert_equal 200, response["code"]
    assert_equal "coffee", response["data"]["query"]
    assert_equal [:search, "coffee", { language: "en" }], fake_api.calls.last
  end

  def test_nested_resources_delegate_to_generated_methods
    fake_api = FakeGoogleApi.new
    google = JustSerpApi::GoogleResource.new(fake_api)

    maps = google.maps.search(query: "espresso", location: "Shanghai")
    ai = google.ai.overview(url: "https://example.com/overview")

    assert_equal "espresso", maps["data"]["query"]
    assert_equal "https://example.com/overview", ai["data"]["url"]
    assert_equal [:maps_search, "espresso", { location: "Shanghai" }], fake_api.calls[0]
    assert_equal [:ai_overview, "https://example.com/overview", {}], fake_api.calls[1]
  end
end

