#!/usr/bin/env python
import sys
from time import gmtime, strftime
import logging
import re
import json
import getopt
import asyncio
from aiohttp import ClientSession

logging.basicConfig(
    format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
    level=logging.DEBUG,
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger("areq")
logging.getLogger("chardet.charsetprober").disabled = True


# Create Test Data START
def parse_json_to_dict(path):
    with open(path) as file:
        raw_config = json.load(file)
        return raw_config


def extract_did_method(did):
    return re.findall("(?<=:)(.*?)(?=:)", did)[0]


def create_test_data(drivers_config, host):
    test_data = []
    for driver in drivers_config:
        did: str = driver["testIdentifiers"][0]
        if did.startswith("did:"):
            driver_test_data = {
                "method": extract_did_method(driver["testIdentifiers"][0]),
                "url": host + driver["testIdentifiers"][0]
            }
            test_data.append(driver_test_data)

    return test_data


# Create Test Data END

# Run tests START
async def fetch_html(url: str, session: ClientSession):
    resp = await session.request(method="GET", url=url)
    html = await resp.text()
    logger.info("Got response [%s] for URL: %s", resp.status, url)
    logger.info("With body:\n %s", html)
    return {"status": resp.status, "body": html}


async def write_one(results, data, session):
    url = data['url']
    try:
        res = await fetch_html(url=url, session=session)
        results.update({url: res})
    except asyncio.TimeoutError:
        results.update({
            url: {
                "status": 504,
                "body": "Gateway Timeout error"
            }
        })
        logger.info("Gateway Timeout error for %s", url)
    print("\n-----------------------------------------------------------------------------------------------\n")


async def run_tests(test_data):
    async with ClientSession() as session:
        tasks = []
        results = {}
        for data in test_data:
            tasks.append(
                write_one(results, data=data, session=session)
            )
        await asyncio.gather(*tasks)
        return results


# Run tests END

def main(argv):
    help_text = './smoke-test.py -i <ingress-file> -c <uni-resolver-config> -o <out-folder>'
    host = 'https://dev.uniresolver.io'
    config = '/github/workspace/config.json'
    out_folder = './'
    try:
        opts, args = getopt.getopt(argv, "h:c:o", ["host=", "config=", "out="])
    except getopt.GetoptError:
        print(help_text)
        sys.exit(2)
    for opt, arg in opts:
        if opt == '--help':
            print(help_text)
            sys.exit()
        elif opt in ("-h", "--host"):
            host = arg
        elif opt in ("-c", "--config"):
            config = arg
        elif opt in ("-o", "--out"):
            print("ARG:" + arg)
            out_folder = arg + '/'

    uni_resolver_path = host + "/1.0/identifiers/"
    print('Resolving for: ' + uni_resolver_path)

    # build test data
    config_dict = parse_json_to_dict(config)
    test_data = create_test_data(config_dict["drivers"], uni_resolver_path)

    # run tests
    results = asyncio.run(run_tests(test_data=test_data))

    timestr = strftime("%d-%m-%Y_%H-%M-%S-UTC", gmtime())
    filename = "smoke-tests-result-" + timestr + ".json"
    print('Out folder: ' + out_folder)
    out_path = out_folder + filename
    print('Writing to path: ' + out_path)
    with open(out_path, "a") as f:
        f.write(json.dumps(results, indent=4, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1:])
    print('Script finished')
