import argparse
from datetime import (
    date,
    datetime,
)
from pathlib import Path
import re
import sys


from bs4 import BeautifulSoup
from PyPDF2 import PdfFileMerger
import requests


URI_BASE = (
    'https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/'
    'dafd/search/'
)
AFD_URI_RE = re.compile('http://aeronav.faa.gov/afd/')


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'name',
        help='Name of flight',
    )
    parser.add_argument(
        'route',
        nargs='+',
        help='Flight route',
    )
    return parser.parse_args()


def most_recent_cycle():
    res = requests.get(URI_BASE)
    soup = BeautifulSoup(res.text, 'html.parser')
    today = date.today()
    dates = {}
    for option in soup.find(id='cycle').find_all('option'):
        first_date = option.text.strip().split(' - ')[0]
        m = re.match(r'[A-Za-z]{3} \d{2}(, \d{4})', first_date)
        format_str = '%b %d'
        if m:
            format_str += ', %Y'
        option_date = datetime.strptime(first_date, format_str).date()
        if m is None:
            option_date = option_date.replace(year=today.year)
        dates[option['value']] = option_date

    return sorted(dates, key=lambda d: d[1])[-1]


def get_afd(waypoint, cycle):
    res = requests.get(
        URI_BASE + 'results/',
        params={
            'cycle': cycle,
            'ident': waypoint,
            'navaid': '',
        },
    )
    if 'No results found.' in res.text:
        return None

    soup = BeautifulSoup(res.text, 'html.parser')
    last = soup.find_all('a', href=AFD_URI_RE)[-1]
    return last['href']


def main():
    args = parse_args()

    output_path = Path('output')
    output_path.mkdir(exist_ok=True)

    cycle = most_recent_cycle()

    urls = []
    for waypoint in args.route:
        url = get_afd(waypoint, cycle)
        if url is None:
            print('Unable to find A/FD page for {}'.format(waypoint))
            return False

        urls.append(url)

    pdfs = []
    for url in urls:
        r = requests.get(url, stream=True)

        write_path = output_path / Path(url.rsplit('/', 1)[1])
        pdfs.append(write_path)
        if write_path.exists():
            continue

        with write_path.open('wb') as pdf:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    pdf.write(chunk)

    merger = PdfFileMerger()
    for pdf in pdfs:
        merger.append(pdf.open('rb'))

    merged_path = Path('{}.pdf'.format(args.name))
    with merged_path.open('wb') as out:
        merger.write(out)

    return True


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
