"""
Script that uploads compose files to applications on BigBoat instances.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import argparse
import configparser
import itertools
import logging
from bigboat import Client_v1, Client_v2

def parse_args():
    """
    Parse command line arguments.
    """

    log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

    parser = argparse.ArgumentParser(description='Upload compose files')
    parser.add_argument('sites', nargs='*',
                        help='URLs to update to, or default to settings.cfg')
    parser.add_argument('--keys', nargs='*', default=[],
                        help='API keys to use, or default to settings.cfg')
    parser.add_argument('--name', default='gros-data-gathering-agent',
                        help='Name of the application')
    parser.add_argument('--version', default='1',
                        help='Version number of the application')
    parser.add_argument('--log', choices=log_levels, default='INFO',
                        help='log level (info by default)')

    return parser.parse_args()

def get_api(site, key=None, config=None):
    """
    Retrieve an API instance for the given `site` URL. If possible, the API is
    instantiated as a v2 Client with the given `key` or one from the `config`
    ConfigParser. If the key and the configuration object/section/option is not
    available, or the section is marked as v1, then a Client_v1 object is given.
    """

    client = Client_v2
    if key is None:
        if config is None or not config.has_section(site) or \
            not config.has_option(site, 'key') or config.has_option(site, 'v1'):
            client = Client_v1
        else:
            key = config.get(site, 'key')

    logging.info('Setting up API for %s: %s', site, repr(client))

    return client(site, api_key=key)

def upload_site(site, name, version, key=None, config=None):
    """
    Upload the compose files to a specific site.
    """

    api = get_api(site, key=key, config=config)
    if isinstance(api, Client_v1):
        raise RuntimeError('API must use v2 to upload compose files for {}'.format(site))

    for filename in ['docker-compose.yml', 'bigboat-compose.yml']:
        with open(filename) as compose_file:
            application = api.get_app(name, version)
            if application is None:
                raise RuntimeError('Application does not yet exist on {}'.format(site))
            api.update_compose(name, version, filename, compose_file.read())

def main():
    """
    Main entry point.
    """

    args = parse_args()
    logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s',
                        level=getattr(logging, args.log.upper(), None))

    config = configparser.RawConfigParser()
    config.read('settings.cfg')

    if args.sites:
        logging.info('Sites: %s', ', '.join(args.sites))
        # pylint: disable=no-member
        for site, key in itertools.zip_longest(args.sites, args.keys):
            upload_site(site, args.name, args.version, key=key, config=config)
    else:
        logging.info('Default sites: %s', ', '.join(config.sections()))
        for site in config.sections():
            upload_site(site, args.name, args.version, config=config)

if __name__ == '__main__':
    main()
