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

class Uploader(object):
    """
    BigBoat dashboard application compose file uploader using the BigBoat API.
    """

    def __init__(self, site, key=None, config=None):
        self._site = site
        self._key = key
        self._config = config

        self._api = None

    @property
    def api(self):
        """
        Retrieve an API instance for the given site URL. If possible, the API
        is instantiated as a v2 Client with the API key or one from the provided
        configuration. If the key and the configuration object/section/option
        is not available, or the section is marked as v1, then a Client_v1
        object is given.
        """

        if self._api is not None:
            return self._api

        client = Client_v2
        if self._key is not None:
            key = self._key
        else:
            if self._config is None or \
                not self._config.has_section(self._site) or \
                not self._config.has_option(self._site, 'key') or \
                self._config.has_option(self._site, 'v1'):
                client = Client_v1
                key = None
            else:
                key = self._config.get(self._site, 'key')

        logging.info('Setting up API for %s: %s', self._site, repr(client))

        self._api = client(self._site, api_key=key)
        return self._api

    def upload(self, name, version):
        """
        Upload the compose files to a specific site.
        """

        if isinstance(self.api, Client_v1):
            raise RuntimeError('API must use v2 to upload compose files for {}'.format(self._site))

        application = self.api.get_app(name, version)
        if application is None:
            logging.warning('Application %s version %s is not on %s, creating.',
                            name, version, self._site)

        for filename in ['docker-compose.yml', 'bigboat-compose.yml']:
            with open(filename) as compose_file:
                self.api.update_compose(name, version, filename,
                                        compose_file.read())

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
            uploader = Uploader(site, key=key, config=config)
            uploader.upload(args.name, args.version)
    else:
        logging.info('Default sites: %s', ', '.join(config.sections()))
        for site in config.sections():
            uploader = Uploader(site, config=config)
            uploader.upload(args.name, args.version)

if __name__ == '__main__':
    main()
