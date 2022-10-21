This directory contains generic variants of the configuration files
required for an OrderPortal instance.

When installing the OrderPortal system, make a copy of this directory
and its contents for use with your instance. That directory will not
be changed when and if you decide to upgrade the OrderPortal source
code when new releases become available.

```
$ cd ~/OrderPortal
$ cp -r site_template site
```

## settings.yaml

The main configuration file. Must be modified for your site.

## static

Contains any site-specific icons or CSS files which are referred to from
the `settings.yaml` file.

## account_messages.yaml

Contains the messages used for emails concerning account actions, such as
registration and password reset.

## order_messages.yaml

Contains the messages used for emails for when the status of an order has changed.

## country_codes.yaml

List of the countries known to the system. Used for account registration.

## swedish_universities.yaml

List of universities to provide a list of standard affiliation values.

## subject_terms.yaml

List of standard terms for declaration of subject of interest for an account.

## orderportal.nginx.conf

An example configuration file for NGINX as a reverse proxy for the OrderPortal process.
