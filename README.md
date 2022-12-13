Compose files and scripts for data gathering
============================================

This repository holds organization-specific configuration files for creating 
and starting Docker instances based on Docker Compose. It also holds some 
scripts to update the applications of these instances through the BigBoat API.

## Requirements

- [BigBoat](https://pypi.python.org/pypi/bigboat)
- [PyYAML](http://pyyaml.org/wiki/PyYAMLDocumentation)

Use `pip install bigboat pyyaml` to install the dependencies.

## Configuration

Add a file `settings.yml` with blocks that look like the following:

```
default:
  params:
    ENV_PARAM: value
http://BIG_BOAT/:
  key: API_KEY
```

Fill in the `BIG_BOAT` domain name (such that it is your dashboard's base URL) 
and the `API_KEY` (obtainable from the dashboard's configuration when logged in 
or replace the whole key option line with `v1: true` to use the old API). 
Environment parameters to be passed when starting the instance can be passed in 
a `params` object field, which is merged with the default object. Additional 
settings are `remote_site`, in order to set up on another BigBoat instance 
rather than the dashboard that is being monitored, and `instance` to give the 
Docker instance another name.

You can add multiple sites in your settings, all of which are considered by 
default unless you specify specific ones when running `scripts/upload.py`. 
Ensure you leave no empty lines between the blocks. Comments are allowed, 
though. 

Edit `docker-compose.yml` and `bigboat-compose.yml` to alter or add generic 
configuration of the Docker instances. Environment variables are used by the 
scraper (startup) scripts within Docker and by the configuration scripts in it, 
thus the environment variable names matter. Use parameters enclosed by double 
curly brackets to make the compose file parameterized such that it can be 
configured per-site at activation time. This is useful for e.g. credentials 
which are not stored *in plain sight*.

The upload script can also start an instance for the application on the site 
that was just updated. The parameter values can be specified in `settings.yml` 
with a `params` associative value. It is common practice to set unused values 
to a dash character, but make sure it is quoted in the YAML file.

A setting block for a site called `default` may provide global parameters. The 
key-value pairs in the default block are overridden (for simple values) or 
augmented (for associative values) with preference for the site-specific block. 
Note that API keys and API versions are not overridden in this way, although 
one can alter the API key through command line arguments.
