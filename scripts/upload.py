"""
Script that uploads compose files to applications on BigBoat instances.

Copyright 2017-2020 ICTU
Copyright 2017-2022 Leiden University

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from argparse import ArgumentParser, Namespace
import copy
import logging
import os.path
from pathlib import Path
import time
from typing import overload, Dict, Iterable, Optional, Union
import yaml
from bigboat import Client_v1, Client_v2

PathLike = Union[str, os.PathLike]
Option = Union[str, Dict[str, str]]
Options = Dict[str, Option]
Config = Dict[str, Options]

def parse_args() -> Namespace:
    """
    Parse command line arguments.
    """

    log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

    parser = ArgumentParser(description='Upload compose files')
    parser.add_argument('sites', nargs='*',
                        help='URLs to update to, or default to site settings')
    parser.add_argument('--keys', nargs='*', default=[],
                        help='API keys to use, or default to site settings')
    parser.add_argument('--name', default='gros-data-gathering-agent',
                        help='Name of the application')
    parser.add_argument('--version', default='2',
                        help='Version number of the application')
    parser.add_argument('--instance', help='Name of the instance')
    parser.add_argument('--log', choices=log_levels, default='INFO',
                        help='Log level (info by default)')
    parser.add_argument('--start', action='store_true', default=False,
                        help='(Re)start an instance after updating the app')
    parser.add_argument('--no-stop', action='store_false', dest='stop',
                        default=True, help='Skip stopping an existing instance')
    parser.add_argument('--compose', help='Directory holding the compose files')
    parser.add_argument('--settings', default='settings.yml',
                        help='Path to the file with site settings')

    return parser.parse_args()

class Uploader:
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

    def __init__(self, site: str, site_keys: Dict[str, Optional[str]],
                 **options: Option) -> None:
        self._site = site
        self._site_keys = site_keys
        self._options = options

        if 'remote_site' in self._options:
            self._remote_site = str(self._options['remote_site'])
        else:
            self._remote_site = self._site

        self._api: Optional[Union[Client_v1, Client_v2]] = None

    @overload
    def _get_key(self, default: str, site: Optional[str] = None) -> str:
        ...
    @overload
    def _get_key(self, default: None = None,
                 site: Optional[str] = None) -> Optional[str]:
        ...
    def _get_key(self, default: Optional[str] = None,
                 site: Optional[str] = None) -> Optional[str]:
        if site is None:
            site = self._site

        if site in self._site_keys and self._site_keys[site] is not None:
            return self._site_keys[site]

        return default

    @property
    def api(self) -> Union[Client_v1, Client_v2]:
        """
        Retrieve an API instance for the given site URL. If possible, the API
        is instantiated as a v2 Client with the API key or one from the provided
        configuration. If the key and the configuration object/section/option
        is not available, or the section is marked as v1, then a Client_v1
        object is given.
        """

        if self._api is not None:
            return self._api

        logging.info('Setting up API for %s', self._remote_site)
        key = self._get_key(site=self._remote_site)

        if key is None:
            self._api = Client_v1(self._remote_site)
        else:
            self._api = Client_v2(self._remote_site, api_key=key)

        return self._api

    def upload(self, name: str, version: str,
               path: Optional[PathLike] = None) -> None:
        """
        Upload the compose files to a specific site.
        """

        if isinstance(self.api, Client_v1):
            raise RuntimeError(f'API for {self._remote_site} cannot upload compose files')

        application = self.api.get_app(name, version)
        if application is None:
            logging.warning('Application %s version %s is not on %s, creating.',
                            name, version, self._remote_site)
            if self.api.update_app(name, version) is None:
                raise RuntimeError(f'Cannot register application on {self._remote_site}')

        for filename, api_filename in self.FILES:
            if path is not None:
                filename = str(Path(path) / filename)

            with open(filename, 'r', encoding='utf-8') as compose_file:
                if not self.api.update_compose(name, version, api_filename,
                                               compose_file.read()):
                    raise RuntimeError(f'Cannot update compose file on {self._remote_site}')

    def start(self, name: str, version: str,
              instance_name: Optional[str] = None, stop: bool = True) -> None:
        """
        Request that the instance for the application is (re)started.
        """

        if instance_name is None:
            instance_name = str(self._options.get('instance', name))

        parameters = {
            "BIGBOAT_HOST": self._site,
            "BIGBOAT_KEY": self._get_key(default='-')
        }
        params = self._options.get('params', {})
        if isinstance(params, dict):
            parameters.update(params)

        if stop:
            first = True
            while self.api.get_instance(name):
                if first:
                    self.api.delete_instance(name)
                    logging.info('Waiting for old instance to be removed...')

                time.sleep(self.RESTART_POLL)
                first = False

        instance = self.api.update_instance(instance_name, name, version,
                                            parameters=parameters)
        if instance is None:
            raise RuntimeError(f'Could not start instance on {self._remote_site}')

        logging.info('Started application %s version %s on %s', name, version,
                     self._remote_site)

def run(args: Namespace, site: str, options: Options,
        site_keys: Dict[str, Optional[str]]) -> None:
    """
    Perform the upload for a single site.
    """

    uploader = Uploader(site, site_keys, **options)
    uploader.upload(args.name, args.version, path=args.compose)
    if args.start:
        uploader.start(args.name, args.version, instance_name=args.instance,
                       stop=args.stop)

DEFAULT_SITE = 'default'

def get_options(config: Config, site: str) -> Options:
    """
    Create an options dictionary based on configuration for a site as well as
    a default configuration.

    The two configurations are merged such that the site-specific values
    override default values if they are simple, and associative values do the
    same (only one level deep).
    """

    options = copy.deepcopy(config.get(DEFAULT_SITE, {}))
    new_options = config.get(site, {})
    for key, value in list(new_options.items()):
        if isinstance(value, dict):
            new_value = options.get(key, {})
            if isinstance(new_value, dict):
                new_value.update(value)
                options[key] = new_value
        else:
            options[key] = value

    return options

def main() -> None:
    """
    Main entry point.
    """

    args = parse_args()
    logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s',
                        level=getattr(logging, args.log.upper(), None))

    with open(args.settings, 'r', encoding='utf-8') as settings_file:
        config: Config = yaml.safe_load(settings_file)

    site_keys = dict(
        (site, str(options['key']) if 'key' in options and 'v1' not in options
         else None)
        for site, options in config.items() if site != DEFAULT_SITE
    )
    if args.sites:
        site_keys.update(zip(args.sites, args.keys))
        sites: Iterable[str] = args.sites
    else:
        sites = site_keys.keys()

    for site in sites:
        options = get_options(config, site)
        run(args, site, options, site_keys)

if __name__ == '__main__':
    main()
