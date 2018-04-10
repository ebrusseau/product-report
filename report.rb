#!/usr/bin/ruby

# Report installed product versions
# 20170519 - Mike Jacobi <michael.jacobi@altoros.com>

# This script parses Pivotal Ops Mgr installed products (API) JSON output
# and displays a table of installed product versions as well as the latest
# available versions for easy comparison between deployments.

# Environment variable SITES is a multi-line and pipe-separated list.
# For example:
#   PCFPRE-PHX|https://opsmgr.pcfpre-phx.....com|pcfautomation|superstrongsecret
#   PCF-PHX|https://opsmgr.pcf-phx.....com|pcfautomation|superstrongsecret
#   PCF-EWD|https://opsmgr.pcf-ewd.....com|pcfautomation|superstrongsecret

# Pass this in via Concourse vars.yml like this:
# sites: |-
#   PCFPRE-PHX|https://opsmgr.pcfpre-phx.....com|pcfautomation|superstrongsecret
#   PCF-PHX|https://opsmgr.pcf-phx.....com|pcfautomation|superstrongsecret
#   PCF-EWD|https://opsmgr.pcf-ewd.....com|pcfautomation|superstrongsecret

# And in the pipeline like this:
#   TODO

require 'json'

# OpsMgr Type <=> PivNet Slug conversion since Pivotal is not consistent with naming
product_table = {
  "apm" => "pcf-metrics",
  "apigee-cf-service-broker" => "apigee-edge-for-pcf-service-broker",
  "cf" => "elastic-runtime",
  "p-bosh" => "ops-manager",
  "p-rabbitmq" => "pivotal-rabbitmq-service",
  "p-mysql" => "p-mysql",
  "p-spring-cloud-services" => "p-spring-cloud-services",
  "Pivotal_Single_Sign-On_Service" => "p-identity",
  "p-windows-runtime" => "runtime-for-windows",
  "p-redis" => "p-redis"
}

# TODO rename sites to foundations

sites = ENV['SITES'].split(/\n/)

# product_list is an array of hashes that contain the "type" and "version".
# For example: [{"type"=>"cf", "version"=>"1.10.1-build.7"}, {"type"=>"p-rabbitmq", "version"=>"1.23"}]
product_list = Array.new

# deployments is an array of hashes that contains the json list of deployed products
# per site
deployments = Array.new

sites.each do |f|
  site,url,client,secret = f.split('|')

  # Logout any existing sessions
  `om-linux \
    --target #{url} \
    --skip-ssl-validation \
    --client-id #{client} \
    --client-secret #{secret} \
    curl -s -x DELETE -p /api/v0/sessions`

  # Query installed products
  installed_products = `om-linux \
    --target #{url} \
    --skip-ssl-validation \
    --client-id #{client} \
    --client-secret #{secret} \
    curl -s -x GET -p /api/v0/deployed/products`

  # Logout our session
  `om-linux \
    --target #{url} \
    --skip-ssl-validation \
    --client-id #{client} \
    --client-secret #{secret} \
    curl -s -x DELETE -p /api/v0/sessions`

  deployment = p = JSON.parse(installed_products)
  deployments << deployment
  p.each do |x|
    found = false
    # If product previously unseen...
    product_list.each do |y|
      found = true if y.has_value?(x['type'])
    end
    if !found
      v = `curl \
             -s \
             -H \"Accept: application/json\" \
             -H \"Content-Type: application/json\" \
             -H \"Authorization: Token #{ENV['API_TOKEN']}\" \
             -X GET https://network.pivotal.io/api/v2/products/#{product_table[x['type']]}/releases`

      r = JSON.parse(v)

      if r.has_key?("releases")
        vers = r["releases"][0]["version"]
      else
        vers = "-"
      end

      product_list << { :type => x["type"], :product_version => vers }

    end
  end
end

#  `sort!': comparison of Hash with Hash failed (ArgumentError)
# product_list.sort!

# 42 dashes
print "------------------------------------------"

# Add more border for each site
sites.each do
  print "----------------"
end
puts

# Print deployment name
printf "%-42s", "Product (latest version)"
sites.each do |f|
  site,url,client,secret = f.split('|')
  printf "%-17s", site
end
puts

# 42 dashes
print "------------------------------------------"

# Add more border for each site
sites.each do
  print "----------------"
end
puts

# Find each product
product_list.each do |p| 
  printf "%-42s", sprintf("%s (%s)", p[:type], p[:product_version])
  deployments.each do |a|
    found = false
    a.each do |d|
      if d["type"].eql?p[:type]
        printf "%-16s ", d.fetch('product_version')
        found = true
      end
    end
    printf "%-16s ", "-" if !found
  end
  puts
end

# 42 dashes
print "------------------------------------------"

# Add more border for each site
sites.each do
  print "----------------"
end
puts

#eof
