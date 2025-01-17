from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from configparser import ConfigParser
from csv import QUOTE_NONE, writer
from datetime import datetime
from json import loads
from sys import exit

from halo import Halo
from requests import get, exceptions


# Parse arguments from CLI arguments
def arg_parse() -> iter:
    parser = ArgumentParser(
        description='Export watched movie history from Tautulli in Letterboxd CSV format',
        formatter_class=ArgumentDefaultsHelpFormatter)
    # The *.ini file to read from
    parser.add_argument('-i', '--ini', default='config.ini',
                        help='config file to read from')
    # The *.csv file to output data to
    parser.add_argument('-o', '--csv', default='output.csv',
                        help='*.csv file to output data to')
    # The username/email to get history from
    parser.add_argument('-u', '--user', required=True,
                        help='the username/email to get history from')
    return parser.parse_args()


# Construct the argument parser
ARGS = arg_parse()

# Construct the config parser
CFG = ConfigParser()
CFG.read(ARGS.ini)

# Credentials specified in the *.ini file and the CLI arguments
BASE_URL = CFG['HOST']['base_url'] + '/api/v2'
TOKEN = CFG['AUTH']['token']
USER = ARGS.user
FILE_NAME = ARGS.csv


# Handles the Tautulli API
def api_handler(params: dict) -> dict:
    try:
        # Append apikey to params
        params['apikey'] = TOKEN
        response = get(BASE_URL, headers={'Content-Type': 'application/json'}, params=params)
        return loads(response.text)
    except exceptions.ConnectionError as e:
        exit(str(e) + '\n' + 'Base URL invalid, please try again')


# Handles the rating set by the user for any given movie
def rating_handler(rating: str) -> None or int:
    json_data = api_handler(params={'cmd': 'get_metadata', 'rating_key': rating})
    for _ in json_data:
        # If root is empty, return
        if not json_data['response']['data']:
            return
        # Else, return user set rating
        else:
            return json_data['response']['data']['user_rating']


# Used to get the full length of a list to parse
def get_length() -> int:
    json_data = api_handler(params={'cmd': 'get_history', 'media_type': 'movie', 'search': USER})
    for _ in json_data:
        try:
            # Return the total count of movies to parse
            return int(json_data['response']['data']['recordsFiltered'])
        except KeyError:
            exit('API key invalid, please try again')


# Handles parsing the JSON from the API output
def json_parser() -> tuple:
    movies = []
    # Gets the total count of entries recorded and assigns it to an integer
    total_count = get_length()
    # Sends the params to the api_handler
    json_data = api_handler(params={'cmd': 'get_history', 'media_type': 'movie', 'search': USER, 'length': total_count})
    # Loading animation
    loading = Halo(spinner='bouncingBar')
    print(f'Exporting movies to {FILE_NAME} for user {USER}: ')
    try:
        for _ in json_data:
            # Value to be incremented through each loop pass
            count = 0
            # While the recordsFiltered doesn't equal our count value, continue
            while count <= total_count:
                # String either 1 or 0 that indicates if it has been watched before
                watched_status = json_data['response']['data']['data'][count]['watched_status']
                # Filters only content that has been watched
                if watched_status == 1:
                    # Gets the movie name
                    name = str(json_data['response']['data']['data'][count]['title'])
                    # Checks if the movie has a comma (,) in it, encapsulates title in quotes "" if true, returns title
                    # if false
                    title = '"%s"' % ' '.join([a.strip() for a in name.split('\n') if a]) if ',' in name else name
                    # Gets the release year
                    year = str(json_data['response']['data']['data'][count]['year'])
                    # Gets the user_rating from the rating_handler and returns a value if it exists
                    rating10 = rating_handler(str(json_data['response']['data']['data'][count]['rating_key']))
                    # Gets the date watched then puts it in YYYY-MM-DD format
                    watched_date = datetime.fromtimestamp(int(json_data['response']['data']['data'][count]['date'])). \
                        strftime('%Y-%m-%d')
                    row = f'{title},{year},{rating10},{watched_date}'
                    # Append the movie entries to the list and drop the duplicates if any exist
                    movies.append(row) if row not in movies else None
                    # Start the loading animation
                    loading.start(text=f'{str(len(movies))} -> {title}')
                count += 1
                # When the count variable equals the total recordsFiltered, stop and return the movies list
                if count == total_count:
                    # Stop the loading animation
                    loading.stop()
                    return movies, len(movies)
    except IndexError as e:
        exit(str(e) + '\n' + 'Index Error, please check your configuration and try again')


# Handles outputting the JSON values into the Letterboxd CSV format
def to_csv() -> None:
    try:
        # Get the movies list and its length
        movies, movies_length = json_parser()
        with open(FILE_NAME, 'w', encoding='utf-8') as data_file:
            # Create the CSV writer object
            csv_writer = writer(data_file, quoting=QUOTE_NONE, quotechar=None, delimiter='\n')
            # Write the header that is specified by Letterboxd
            csv_writer.writerow(['Title,Year,Rating10,WatchedDate'])
            # Write the list
            csv_writer.writerow(movies)
        print(f'Exported {movies_length} filtered movies to {FILE_NAME}.')
    except TypeError as e:
        exit(str(e) + '\n' + 'Invalid user, please check your configuration and try again')
    except KeyboardInterrupt:
        exit('\n' + f'Exporting movies to {FILE_NAME} has been halted.')


def main() -> None:
    # Write the collected data to the specified CSV file
    to_csv()
