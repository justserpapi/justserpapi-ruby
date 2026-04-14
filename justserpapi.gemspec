# frozen_string_literal: true

require_relative "lib/justserpapi/version"

Gem::Specification.new do |spec|
  spec.name = "justserpapi"
  spec.version = JustSerpApi::VERSION
  spec.platform = Gem::Platform::RUBY
  spec.authors = ["JustSerpAPI"]
  spec.email = ["support@justserpapi.com"]
  spec.summary = "OpenAPI-first Ruby SDK for JustSerpAPI"
  spec.description = "Generated Ruby client and stable high-level wrapper for the JustSerpAPI HTTP API."
  spec.homepage = "https://github.com/justserpapi/justserpapi-ruby"
  spec.license = "MIT"
  spec.required_ruby_version = ">= 3.1"

  spec.metadata = {
    "homepage_uri" => spec.homepage,
    "source_code_uri" => spec.homepage,
    "changelog_uri" => "#{spec.homepage}/releases",
    "rubygems_mfa_required" => "true"
  }

  spec.files = Dir.chdir(__dir__) do
    Dir.glob([
      "lib/**/*",
      "generated/ruby-client/lib/**/*",
      "README.md",
      "LICENSE"
    ]).select { |path| File.file?(path) }
  end

  spec.require_paths = ["lib", "generated/ruby-client/lib"]

  spec.add_runtime_dependency "faraday", ">= 1.0.1", "< 3.0"
  spec.add_runtime_dependency "faraday-multipart", "~> 1.0"
  spec.add_runtime_dependency "marcel", "~> 1.0"

  spec.add_development_dependency "minitest", "~> 5.22"
  spec.add_development_dependency "rake", "~> 13.0"
end
