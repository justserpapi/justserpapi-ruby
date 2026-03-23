require "rake/testtask"

Rake::TestTask.new do |task|
  task.libs << "lib"
  task.libs << "generated/ruby-client/lib"
  task.libs << "test"
  task.pattern = "test/**/*_test.rb"
end

task default: :test

