"""
Script that uploads compose files to applications on BigBoat instances.
"""

try:
    from future import standard_library
    standard_library.install_aliases()
except ImportError:
    raise

import argparse
import copy
import itertools
import logging
import time
import yaml
from bigboat import Client_v1, Client_v2

def parse_args():
    """
    Parse command line arguments.
    """

    log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

    parser = argparse.ArgumentParser(description='Upload compose files')
    parser.add_argument('sites', nargs='*',
                        help='URLs to update to, or default to settings.yml')
    parser.add_argument('--keys', nargs='*', default=[],
                        help='API keys to use, or default to settings.yml')
    parser.add_argument('--name', default='gros-data-gathering-agent',
                        help='Name of the application')
    parser.add_argument('--version', default='1',
                        help='Version number of the application')
    parser.add_argument('--log', choices=log_levels, default='INFO',
                        help='Log level (info by default)')
    parser.add_argument('--start', action='store_true', default=False,
                        help='(Re)start an instance after updating the app')
    parser.add_argument('--no-stop', action='store_false', dest='stop', default=True,
                        help='Skip stopping an existing instance')

    return parser.parse_args()

class Uploader(object):
    """
    BigBoat dashboard application compose file uploader using the BigBoat API.
    """

    # Local file names and BigBoat API endpoints to upload compose files to
    FILES = [
        ('docker-compose.yml', 'dockerCompose'),
        ('bigboat-compose.yml', 'bigboatCompose')
    ]

    # Number of seconds to wait to check if the instance has been stopped
    RESTART_POLL = 2

    def __init__(self, site, **options):
        self._site = site
        self._options = options

        self._api = None

    def _get_key(self, default=None):
        if 'key' in self._options and 'v1' not in self._options:
            return self._options['key']

        return default

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
        key = self._get_key()

        if key is None:
            client = Client_v1

        logging.info('Setting up API for %s', self._site)

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
            if self.api.update_app(name, version) is None:
                raise RuntimeError('Cannot register application on {}'.format(self._site))

        for filename, api_filename in self.FILES:
            with open(filename) as compose_file:
                if not self.api.update_compose(name, version, api_filename,
                                               compose_file.read()):
                    raise RuntimeError('Cannot update compose file on {}'.format(self._site))

    def start(self, name, version, stop=True):
        """
        Request that the default instance for the application is (re)started.
        """

        parameters = {
            "BIGBOAT_HOST": self._site,
            "BIGBOAT_KEY": self._get_key('-')
        }
        parameters.update(self._options.get('params', {}))

        if stop:
            first = True
            while self.api.get_instance(name):
                if first:
                    self.api.delete_instance(name)
                    logging.info('Waiting for old instance to be removed...')

                time.sleep(self.RESTART_POLL)
                first = False

        instance = self.api.update_instance(name, name, version,
                                            parameters=parameters)
        if instance is None:
            raise RuntimeError('Could not start instance on {}'.format(self._site))

        logging.info('Started application %s version %s on %s', name, version,
                     self._site)

def run(args, site, options):
    """
    Perform the upload for a single site.
    """

    uploader = Uploader(site, **options)
    uploader.upload(args.name, args.version)
    if args.start:
        uploader.start(args.name, args.version, stop=args.stop)

DEFAULT_SITE = 'default'

def get_options(config, site):
    """
    Create an options dictionary based on configuration for a site as well as
    a default configuration.

    The two configurations are merged such that the site-specific values
    override default values if they are simple, and associative values do the
    same (only one level deep).
    """

    options = copy.deepcopy(config.get(DEFAULT_SITE, {}))
    new_options = config.get(site, {})
    for key, value in list(new_options.iteritems()):
        if isinstance(value, dict):
            new_value = options.get(key, {})
            new_value.update(value)
            options[key] = new_value
        else:
            options[key] = value

    return options

def main():
    """
    Main entry point.
    """

    args = parse_args()
    logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s',
                        level=getattr(logging, args.log.upper(), None))

    with open('settings.yml') as settings_file:
        config = yaml.load(settings_file)

    if args.sites:
        logging.info('Sites: %s', ', '.join(args.sites))
        # pylint: disable=no-member
        for site, key in itertools.zip_longest(args.sites, args.keys):
            options = get_options(config, site)
            if key is not None:
                options['key'] = key

            run(args, site, options)
    else:
        sites = [site for site in config.keys() if site != DEFAULT_SITE]
        logging.info('Sites: %s', ', '.join(sites))
        for site in sites:
            options = get_options(config, site)
            run(args, site, options)

if __name__ == '__main__':
    main()
