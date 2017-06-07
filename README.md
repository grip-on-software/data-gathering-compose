Compose files and scripts for data gathering
============================================

This repository holds organization-specific configuration files for creating and 
starting Docker instances based on Docker Compose. It also holds some scripts 
to update the applications of these instances through the BigBoat API.

## Requirements

- [BigBoat](https://pypi.python.org/pypi/bigboat)
- [PyYAML](http://pyyaml.org/wiki/PyYAMLDocumentation)

Use `pip install bigboat pyyaml` to install the dependencies.

## Configuration

Add a file `settings.yml` with blocks that look like the following:

```
http://BIG_BOAT/:
  key: API_KEY
```

Fill in the `BIG_BOAT` domain name (such that it is your dashboard's base URL) 
and the `API_KEY` (obtainable from the dashboard's configuration when logged in 
or replace the like with `v1: true` to use the old API).

Edit `docker-compose.yml` and `bigboat-compose.yml` to alter or add generic 
configuration of the Docker instances. Environment variables are used by the 
scraper (startup) scripts within Docker and by the configuration scripts in it, 
thus the environment variable names matter. Use parameters enclosed by double 
curly brackets to make the compose file parameterized such that it can be 
configured per-site at activation time. This is useful for e.g. credentials 
which are not stored *in plain sight*.
