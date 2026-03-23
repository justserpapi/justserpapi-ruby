generated_lib = File.expand_path("../generated/ruby-client/lib", __dir__)
$LOAD_PATH.unshift(generated_lib) unless $LOAD_PATH.include?(generated_lib)

require_relative "justserpapi/version"
require_relative "../generated/ruby-client/lib/justserpapi"
require_relative "justserpapi/client"

JustSerpAPI = JustSerpApi::Client unless defined?(JustSerpAPI)
