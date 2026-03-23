require "uri"

module JustSerpApi
  DEFAULT_BASE_URL = "https://api.justserpapi.com".freeze
  DEFAULT_TIMEOUT = 30

  class ResourceBase
    def initialize(api)
      @api = api
    end

    private

    def invoke(method_name, *args, **opts)
      response = @api.public_send(method_name, *args, opts)
      response.respond_to?(:to_hash) ? response.to_hash : response
    end
  end

  class GoogleMapsResource < ResourceBase
    def search(query:, **opts)
      invoke(:maps_search, query, **opts)
    end
  end

  class GoogleNewsResource < ResourceBase
    def search(query:, **opts)
      invoke(:news_search, query, **opts)
    end
  end

  class GoogleImagesResource < ResourceBase
    def search(query:, **opts)
      invoke(:images_search, query, **opts)
    end
  end

  class GoogleShoppingResource < ResourceBase
    def search(query:, **opts)
      invoke(:shopping_search, query, **opts)
    end
  end

  class GoogleAiResource < ResourceBase
    def overview(url:, **opts)
      invoke(:ai_overview, url, **opts)
    end

    def mode(query:, **opts)
      invoke(:ai_mode, query, **opts)
    end
  end

  class GoogleResource < ResourceBase
    attr_reader :maps, :news, :images, :shopping, :ai

    def initialize(api)
      super(api)
      @maps = GoogleMapsResource.new(api)
      @news = GoogleNewsResource.new(api)
      @images = GoogleImagesResource.new(api)
      @shopping = GoogleShoppingResource.new(api)
      @ai = GoogleAiResource.new(api)
    end

    def search(query:, **opts)
      invoke(:search, query, **opts)
    end

    def autocomplete(query:, **opts)
      invoke(:autocomplete, query, **opts)
    end
  end

  class Client
    attr_reader :api_client, :configuration, :google, :google_api

    def self.open(**kwargs)
      client = new(**kwargs)
      return client unless block_given?

      begin
        yield(client)
      ensure
        client.close
      end
    end

    def initialize(api_key: nil, base_url: DEFAULT_BASE_URL, timeout: DEFAULT_TIMEOUT, user_agent: nil, configuration: nil)
      @configuration = configuration || Configuration.new
      apply_base_url(@configuration, base_url)
      @configuration.timeout = timeout unless timeout.nil?
      apply_api_key(@configuration, api_key) unless api_key.nil?

      @api_client = ApiClient.new(@configuration)
      @api_client.default_headers["User-Agent"] = user_agent || default_user_agent

      @google_api = GoogleApi.new(@api_client)
      @google = GoogleResource.new(@google_api)
    end

    def close
      nil
    end

    private

    def apply_api_key(config, api_key)
      config.api_key["X-API-Key"] = api_key
      config.api_key["api_key"] = api_key
    end

    def apply_base_url(config, base_url)
      uri = URI.parse(base_url)
      config.scheme = uri.scheme
      config.host = if uri.port && uri.port != uri.default_port
                      "#{uri.host}:#{uri.port}"
                    else
                      uri.host
                    end
      config.base_path = uri.path.to_s.empty? ? "" : uri.path
    end

    def default_user_agent
      "justserpapi/#{VERSION}/ruby"
    end
  end
end

