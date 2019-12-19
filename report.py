import sys
import os
import re
import json
import getopt
import random
import subprocess

def get_sample_data(foundations):
    sample_data = {}
    for f in foundations:
        sample_data[f] = [{
            "type": "cf",
            "product_version": "2.4.1"
        }, {
            "type": "apm",
            "product_version": "1.5.3"
        }, {
            "type": "p-bosh",
            "product_version": "2.4-build.152"
        }, {
            "type": "aws-service-broker",
            "product_version": "1.0.0-beta.1"
        }]

        if (random.randrange(1, 255) % 2) == 1:
            sample_data[f].append({
                "type": "pivotal-mysql",
                "product_version": "2.3.4"
            })
        else:
            sample_data[f].append({
                "type": "p-redis",
                "product_version": "1.14.1"
            })

    return sample_data

def run_cmd(args):
    omproc = subprocess.Popen(args, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = omproc.communicate()

    result = dict()
    result["stdout"] = stdout
    result["stderr"] = stderr

    return omproc.returncode, result

def om(target, username, password, cmd):
    args = [
        "om",
        "--target", "%s" % target,
        "--skip-ssl-validation",
        "--username", "%s" % username,
        "--password", "%s" % password
    ]

    args.extend(cmd.split())

    returncode, result = run_cmd(args)

    if returncode != 0:
        sys.stderr.write("ERROR encountered when running command: {}\n".format(" ".join(args)))
        sys.stderr.write(result["stderr"])
        sys.exit(1)

    return result["stdout"]

def get_product_slug(product_type):
    product_table = {
      "apm": "pcf-metrics",
      "apmPostgres": "pcf-metrics",
      "cf": "elastic-runtime",
      "p-bosh": "ops-manager",
      "scanner": "p-compliance-scanner"
    }

    if product_table.has_key(product_type):
        product_slug = product_table[product_type]
    else:
        product_slug = product_type

    return product_slug

def add_foundation(foundations, definition):
    try:
        name, target, username, password = definition.split(",")
    except:
        sys.stderr.write("ERROR: Invalid foundation format: \"%s\"\n" % definition)
        print
        usage()
        sys.exit(1)

    if foundations.has_key(name):
        sys.stderr.write("ERROR: Duplicate foundation name: %s" % name)
        sys.exit(1)

    foundations[name] = {
        "target": target,
        "username": username,
        "password": password
    }

def get_deployed_products(foundations):
    deployed_products = {}

    for foundation_name in foundations:
        f = foundations[foundation_name]

        # Logout any existing sessions
        om(f["target"], f["username"], f["password"], "curl -s -x DELETE -p /api/v0/sessions")

        # Query deployed products
        json_response = om(f["target"], f["username"], f["password"], "curl -s -x GET -p /api/v0/deployed/products")

        # Logout our session
        om(f["target"], f["username"], f["password"], "curl -s -x DELETE -p /api/v0/sessions")

        deployed_products[foundation_name] = json.loads(json_response)

    return deployed_products

def get_pivnet_version(pivnet_token, product_slug, use_file_version=False):
    file_version_lookup = {
        "ops-manager": ".*onAWS\.yml",
        "elastic-runtime": ".*cf-.*\.pivotal"
    }

    args = [
        "curl",
        "-s",
        "-f",
        "-H", "Accept: application/json",
        "-H", "Content-Type: application/json"
    ]

    if len(pivnet_token) > 0:
        args.extend([ "-H", "Authorization: Token {}".format(pivnet_token) ])

    args.append("https://network.pivotal.io/api/v2/products/{}/releases/latest".format(product_slug))

    returncode, result = run_cmd(args)

    version = "-"
    if returncode == 0:
        pivnet_response = json.loads(result["stdout"])
        if pivnet_response.has_key("version"):
            version = pivnet_response["version"]

        if use_file_version:
            if file_version_lookup.has_key(product_slug):
                regex = re.compile(file_version_lookup[product_slug])
            else:
                regex = re.compile(".*\.pivotal")

            for f in pivnet_response.get("product_files", []):
                if regex.match(f["aws_object_key"]):
                    version = f["file_version"]
                    break

    return version

def print_header(num_foundations):
    # 42 dashes
    sys.stdout.write("------------------------------------------")
    i = 0;
    while i < num_foundations:
      sys.stdout.write("----------------")
      i += 1
    sys.stdout.write("\n")

def usage():
    print "Usage: report.py [options]"
    print "  Options:"
    print "    -f, --foundation=             Foundation definition (may be used multiple times) formatted as follows:"
    print "                                  \"<foundation name>,<opsman target>,<opsman username>,<opsman password\""
    print "                                  Example: --foundation \"MY_PCF,my_opsman.example.org,admin,admin\""
    print
    print "    -p, --pivnet-token=           Token used to fetch latest releases from PivNet ($PIVNET_TOKEN)"
    print "                                  Note: Not required, however certain products may not be resolved without a valid token"
    print
    print "    -v, --file-versions           Use file version of products in report (if applicable)"
    print "    -s, --product-slugs           Use product slugs in report"
    print "    --sample                      Prints a report with sample data instead of reading from real foundations"
    print ""

def main(argv):
    pivnet_token = os.getenv("PIVNET_TOKEN", "")
    use_file_versions = False
    use_product_slug = False
    use_sample_data = False
    foundations = {}
    deployments = {}
    products = {}

    try:
        opts, args = getopt.getopt(argv,"hf:p:vs",["help", "foundation=", "pivnet-token=", "file-versions", "product-slugs", "sample"])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-f", "--foundation"):
            add_foundation(foundations, arg)
        elif opt in ("-p", "--pivnet-token"):
            pivnet_token = arg
        elif opt in ("-v", "--file-versions"):
            use_file_versions = True
        elif opt in ("-s", "--product-slugs"):
            use_product_slug = True
        elif opt == "--sample":
            use_sample_data = True

    foundations_env_value = os.getenv("FOUNDATIONS", "")
    if (len(foundations) == 0 and len(foundations_env_value) > 0):
        for definition in foundations_env_value.split("\n"):
            add_foundation(foundations, definition)

    if len(foundations) == 0:
        sys.stderr.write("ERROR: No foundations to process")
        usage()
        sys.exit(2)

    if use_sample_data:
        deployed_products = get_sample_data(foundations)
    else:
        deployed_products = get_deployed_products(foundations)

    for foundation_name in deployed_products:
        deployments[foundation_name] = {}

        # Keep track of all products seen across deployments and fetch their latest
        # release version from Pivotal
        for product in deployed_products[foundation_name]:
            product_slug = get_product_slug(product["type"])

            if use_product_slug:
                product_id = product_slug
            else:
                product_id = product["type"]

            deployments[foundation_name][product_id] = product["product_version"]
            if not products.has_key(product_id):
                products[product_id] = get_pivnet_version(pivnet_token, product_slug, use_file_versions)

    # Output Results
    # Print header
    print_header(len(deployments))
    sys.stdout.write("%-42s" % "Product (latest version)")
    # Output foundation name
    for foundation_name in deployments:
      sys.stdout.write("%-16s" % foundation_name)
    sys.stdout.write("\n")
    print_header(len(deployments))

    # Print deployed products and versions
    for p in sorted(products.iterkeys()):
        product_info = "{} ({})".format(p, products[p])
        sys.stdout.write("%-42s" % product_info)

        for foundation_name in deployments.keys():
            foundation_products = deployments[foundation_name]

            if foundation_products.has_key(p):
                sys.stdout.write("%-16s" % foundation_products[p])
            else:
                sys.stdout.write("%-16s" % "-")

        sys.stdout.write("\n")

    # Print footer
    print_header(len(deployments))
    sys.stdout.flush()

if __name__== "__main__":
  main(sys.argv[1:])
