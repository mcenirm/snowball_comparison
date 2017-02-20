#!/usr/bin/env python3

"""http://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html"""


_DEFAULT_AWS_PRICING_START_URL = 'https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json'
_DEFAULT_AWS_SERVICES_ALIASES = {
    's3': 'AmazonS3',
    'snowball': 'IngestionServiceSnowball',
}


class Offers():
    def __init__(
        self,
        start=_DEFAULT_AWS_PRICING_START_URL,
        aliases=_DEFAULT_AWS_SERVICES_ALIASES,
        urlgetter=None,
    ):
        self.start = start
        self.aliases = aliases
        self.urlgetter = _default_urlgetter(urlgetter=urlgetter)
        self.index = None

    def get_offer(
        self,
        service_name,
    ):
        """Get the offer details for the named service."""
        import urllib.parse

        if self.index is None:
            self.index = self.urlgetter.get(self.start).json()
        offer_code = self.aliases.get(service_name, service_name)
        offer_ref = self.index['offers'][offer_code]
        offer = OfferFile(
            url=urllib.parse.urljoin(self.start, offer_ref['currentVersionUrl']),
            code=offer_code,
            urlgetter=self.urlgetter
        )
        return offer


_DEFAULT_AWS_PRICING_CACHE_DIR = 'cache/awspricing'


def _default_urlgetter(
    cache_dir=_DEFAULT_AWS_PRICING_CACHE_DIR,
    urlgetter=None,
):
    if urlgetter is None:
        from requests import Session
        from cachecontrol import CacheControl
        from cachecontrol.caches.file_cache import FileCache

        urlgetter = CacheControl(
            Session(),
            cache=FileCache(cache_dir),
        )
    return urlgetter


class OfferFile():
    def __init__(self, url, code, urlgetter=None):
        self.url = url
        self.code = code
        self.urlgetter = _default_urlgetter(urlgetter=urlgetter)
        self._offer_file = None
        self._product_families = None

    @property
    def offer_file(self):
        if self._offer_file is None:
            self._offer_file = self.urlgetter.get(self.url).json()
            format_version = self._offer_file['formatVersion']
            if format_version != 'v1.0':
                raise Exception('Unsupported formatVersion: {}'.format(format_version))
        return self._offer_file

    @property
    def products(self):
        return self.offer_file['products']

    @property
    def product_families(self):
        if self._product_families is None:
            from collections import defaultdict

            self._product_families = defaultdict(dict)
            products = self.offer_file['products']
            for key, product in products.items():
                family = product['productFamily']
                self._product_families[family][key] = product
        return self._product_families

    @property
    def terms(self):
        return self.offer_file['terms']

    def products_in_region(self, region_id):
        matching_products = {}
        for sku, product in self.products.items():
            attributes = product['attributes']
            if is_transfer_in_region(attributes, region_id):
                matching_products[sku] = product
            elif is_nontransfer_in_region(attributes, region_id):
                matching_products[sku] = product
        return matching_products


def is_transfer(product_attributes):
    return 'toLocationType' in attributes or 'fromLocationType' in product_attributes


#def is_transfer_in_region(product_attributes, region_id):
#    from_location = product_attributes


def _parse_arguments(arguments=None):
    """Parse command line arguments"""
    from argparse import ArgumentParser
    import sys

    if arguments is None:
        arguments = sys.argv[1:]

    parser = ArgumentParser(
            description='Get AWS pricing offers.',
        )
    parser.add_argument(
            '--start',
            help='URL for offer index file',
            default=_DEFAULT_AWS_PRICING_START_URL,
        )
    parser.add_argument(
            '--cache',
            help='Directory to hold cached offer files',
            default=_DEFAULT_AWS_PRICING_CACHE_DIR,
        )
    #parser.add_argument('service')
    #parser.add_argument('region')
    return parser.parse_args(arguments)


def main():
    """Get AWS pricing offers."""
    args = _parse_arguments()
    urlgetter = _default_urlgetter(cache_dir=args.cache)
    offers = Offers(
        start=args.start,
        urlgetter=urlgetter,
    )
    argsv = vars(args)
    service = argsv.get('service', 's3')
    region = argsv.get('region', 'us-east-1')
    offer = offers.get_offer(service)
    terms = offer.get_terms(region)
    print(terms)


if __name__ == '__main__':
    import logging
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    main()
