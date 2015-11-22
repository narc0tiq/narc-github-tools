#!/usr/bin/env python
from __future__ import division
import requests
import logging
import datetime
import argparse


logger = logging.getLogger()
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.WARNING)


parser = argparse.ArgumentParser(description="Counts release downloads for a given github project.")
parser.add_argument('-D', '--dry-run', action='store_true', dest='dry_run',
                    help="Don't actually connect to network servers, but print debugging information (implies -v).")
parser.add_argument('-f', '--force', action='store_true', dest='force',
                    help="Ignore rate limits and try the connection anyway. Probably shouldn't do this by default.")
parser.add_argument('-v', '--verbose', action='store_true', dest='verbose',
                    help="Print URLs and additional debug information.")
parser.add_argument('-t', '--only-totals', action='store_true', dest='only_totals',
                    help="Show only the total downloads (omit latest release stats).")
parser.add_argument('projects', metavar='PROJECT', nargs='+',
                    help="Which github project(s) to look at. May be specified multiple times.")



sess = requests.Session()


def get_rate_limit():
    req = requests.Request('GET', 'https://api.github.com/rate_limit')
    prepped = sess.prepare_request(req)

    if args.verbose:
        logger.info('"{p.method}" "{p.url}"'.format(p=prepped))
    r = sess.send(prepped, timeout=10)
    core_limits = r.json()['resources']['core']
    core_limits['reset_date'] = datetime.datetime.fromtimestamp(core_limits['reset'])

    if args.verbose:
        logger.info('{l[remaining]}/{l[limit]} requests remaining until {l[reset_date]}'.format(l=core_limits))
    return core_limits


def get_project_release_data(project):
    req = requests.Request('GET', 'https://api.github.com/repos/%s/releases' % project)
    prepped = sess.prepare_request(req)

    if args.verbose:
        logger.info('"{p.method}" "{p.url}"'.format(p=prepped))
    if args.dry_run:
        logger.info('Dry run: returning no data.')
        return {}

    r = sess.send(prepped, timeout=10)
    r.raise_for_status()
    return r.json()


def print_release_stats(project, releases):
    latest = None
    total_downloads = 0
    for release in releases:
        if not latest:
            latest = release

        for asset in release['assets']:
            total_downloads += asset['download_count']

    print '%s:' % project
    if not latest:
        print '\tNo releases.'
        return

    if not args.only_totals:
        print '\tLatest: %s at %s' % (latest['name'], latest['html_url'])
        if len(latest['assets']) < 1:
            print '\t\tNo assets associated.'
        else:
            for asset in latest['assets']:
                print '\t\t%s: %d download%s of %s' % (asset['name'], asset['download_count'], '' if asset['download_count'] == 1 else 's', asset['browser_download_url'])

    print '\tTotal: %d download%s' % (total_downloads, '' if total_downloads == 1 else 's')


def main():
    global args
    args = parser.parse_args()

    if args.dry_run:
        args.verbose = True
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    rate_limit = get_rate_limit()
    remain_ratio = rate_limit['remaining'] / rate_limit['limit']

    if remain_ratio < 0.1:
        logging.error('Less than 10%% of your Github API rate limit ({r[remaining]}/{r[limit]}) remains.'.format(r=rate_limit))
        if not args.force:
            logging.error('Aborting (use "--force" to override this automatic limit).')
            return
    elif remain_ratio < 0.25:
        logging.warn('Less than 25%% of your Github API rate limit ({r[remaining]}/{r[limit]}) remains.'.format(r=rate_limit))


    for proj in args.projects:
        try:
            j = get_project_release_data(proj)
            print_release_stats(proj, j)
        except requests.exceptions.RequestException:
            logging.exception('Unable to retrieve release data for project %s' % proj)


if __name__ == '__main__':
    main()
