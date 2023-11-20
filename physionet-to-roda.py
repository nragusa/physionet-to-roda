#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""This crude script is intended to generate the requisite
    Registry of Open Data YAML files for the databases listed
    on PhysioNet's website. There is no API to query today,
    so we rely on parsing their HTML pages. This is intended to
    create a skeleton form of the YAML files, with a human to review
    all the files generated before submitting them.

    RODA file format:
    https://github.com/awslabs/open-data-registry#how-are-datasets-added-to-the-registry

    MIT PhysioNet databases:
    https://physionet.org/about/database/
"""

import argparse
import csv
import os
import re
import requests
import sys
import yaml
from bs4 import BeautifulSoup
from markdownify import markdownify as md

"""
CONFIGURATION
"""
# Defines how many database entries to create. Set END = 0 for all
START = 0
END = 0
BASE_URL = 'https://physionet.org'  # Where to get this data from
CONTACT_URL = 'https://physionet.org/about/#contact'
UPDATE_FREQUENCY = 'Not updated'
DEFAULT_DESCRIPTION = 'No description provided.'
DEFAULT_MANAGED_BY = '[MIT Laboratory for Computational Physiology](http://lcp.mit.edu/)'
DEFAULT_LICENSE = 'https://physionet.org/content/adfecgdb/view-license/1.0.0/'
DEFAULT_S3_BUCKET = 'physionet-pds'
DEFAULT_RESOURCE_DESCRIPTION = 'Project data files'
SINGLE_ENTRY_NAME = 'PhysioNet Open Datasets'
SINGLE_ENTRY_DESCRIPTION = "A collection of datasets provided by the [MIT Laboratory for Computational Physiology](http://lcp.mit.edu/)"
SINGLE_ENTRY_DOCUMENTATION = 'https://physionet.org/about/database/'
SINGLE_ENTRY_TAGS = ['aws-pds', 'life sciences']
STANDARD_CITATION = (' Please include the standard citation for PhysioNet: '
                     'Goldberger, A., Amaral, L., Glass, L., Hausdorff, J., Ivanov, P. C., '
                     'Mark, R., ... & Stanley, H. E. (2000). PhysioBank, PhysioToolkit, '
                     'and PhysioNet: Components of a new research resource for complex '
                     'physiologic signals. Circulation [Online]. 101 (23), pp. e215–e220.')

# Command line arguments
parser = argparse.ArgumentParser(description='Generates the Registry of Open '
                                 'Data YAML formatted files for PhysioNet datasets')
parser.add_argument('-f', '--format', dest='format', nargs='?',
                    action='store', type=str, default='separate',
                    help=('Specify "single" to create a single RODA file, '
                          'or "separate" to create a RODA file per dataset'))
parser.add_argument('-t', '--db-type', dest='db_type', nargs='?',
                    action='store', type=str, default='open',
                    choices=['open', 'restricted', 'credentialed'],
                    help=('Specify "single" to create a single RODA file, '
                          'or "separate" to create a RODA file per dataset'))
parser.add_argument('-c', '--csv', dest='csv', action='store_true',
                    help='Optionally create a CSV file of this data for debugging')
args = parser.parse_args()


class PhysioNetDB(object):
    """Represents a single PhysioNet dataset and the properties
    required in order to create a valid Registry of Open Data
    entry
    """

    def __init__(self, entry_id, url, name, short_description):
        self.entry_id = entry_id
        self.url = BASE_URL + url
        self.name = name
        self.short_description = short_description
        self.description = ''
        self.data_license = ''
        self.tags = ['aws-pds', 'life sciences']
        self.contact = CONTACT_URL
        self.documentation = self.url
        self.managed_by = DEFAULT_MANAGED_BY
        self.update_frequency = UPDATE_FREQUENCY
        self.resources = [
            dict(
                Description=DEFAULT_RESOURCE_DESCRIPTION,
                ARN=f'arn:aws:s3:::{DEFAULT_S3_BUCKET}/{self.entry_id}',
                Region='us-east-1',
                Type='S3 Bucket'
            )
        ]

    def extract_description(self, html):
        """Extracts the long form description of the dataset
        Parameters
        ----------
        html : bs4.BeautifulSoup
            BeautifulSoup object that represents the entire HTML page

        Returns
        ----------
        String
            A string representation of the dataset's description
        """
        if abstract_header := html.find('h3', string='Abstract'):
            self.description = md(str(abstract_header.find_next('p')))
        elif abstract_header := html.find('h2', string='Abstract'):
            self.description = md(str(abstract_header.find_next('p')))
        elif intro_header := html.find('h3', string='Introduction'):
            self.description = md(str(intro_header.find_next('p')))
        elif data_description_header := html.find('h3', string='Data Description'):
            self.description = md(str(data_description_header.find_next('p')))
        elif data_collection_header := html.find('h3', string='Data Collection'):
            self.description = md(str(data_collection_header.find_next('p')))
        else:
            self.description = DEFAULT_DESCRIPTION

    def extract_tags(self, html):
        """Extracts the tags of a dataset
        Parameters
        ----------
        html : bs4.BeautifulSoup
            BeautifulSoup object that represents the entire HTML page

        Returns
        ----------
        List
            List of a dataset's specified tags
        """
        tags = html.find_all('span', class_='badge badge-pn')
        if tags:
            for tag in tags:
                self.tags.append(tag.get_text())

    def extract_license(self, html):
        """Extracts the license of a dataset
        Parameters
        ----------
        html : bs4.BeautifulSoup
            BeautifulSoup object that represents the entire HTML page

        Returns
        ----------
        String
            License of the dataset
        """
        if data_license_header := html.find(
                'strong', string='License (for files):'):
            self.data_license = BASE_URL + \
                data_license_header.find_next('a').attrs['href']

    def extract_citation(self, html):
        """Extracts the license of a dataset
        Parameters
        ----------
        html : bs4.BeautifulSoup
            BeautifulSoup object that represents the entire HTML page

        Returns
        ----------
        String
            The contents of the alert at the top of the page which
            contains the appropriate citations with the original
            publication
        """
        if citation_alert := html.find('div', class_='alert alert-secondary'):
            if original_publication := html.find('strong', string='When using this resource, please cite the original publication:'):
                self.description += (' When using this resource, please cite '
                                     'the original publication: ' + md(
                                         str(original_publication.find_next('p'))
                                     )
                                     )
            elif please_cite := html.find('strong', string=re.compile('When using this resource, please cite')):
                # gross
                self.description += (' When using this resource, please cite: ' +
                                     md(
                                         str(please_cite.find_next(
                                             'span')).replace('<span>', '').replace('</span>', '')
                                     )
                                     )
            else:
                self.description += STANDARD_CITATION
        else:
            pass

    def generate_separate_roda(self):
        """Generates a representation of the dataset that is meant
        to be used in an individual RODA file
        https://github.com/awslabs/open-data-registry#how-are-datasets-added-to-the-registry

        Returns
        ----------
        Dict
            A dictionary formatted properly to be dumped to a file in YAML format
        """
        entry = dict(
            Name=self.name,
            Description=self.description,
            Documentation=self.documentation,
            Contact=self.contact,
            ManagedBy=self.managed_by,
            UpdateFrequency=self.update_frequency,
            Tags=self.tags,
            License=self.data_license,
            Resources=self.resources
        )
        return entry

    def generate_single_roda(self):
        """Generates a representation of the dataset that is meant
        to be used a single RODA file, with each individual dataset
        represented as a separate resource
        https://github.com/awslabs/open-data-registry#how-are-datasets-added-to-the-registry

        Returns
        ----------
        Dict
            Extracts the resource information from this entry and returns it
            with just the short description
        """
        entry = self.resources[0]
        entry['Description'] = self.short_description
        return entry

    def as_csv(self):
        """Mostly for debug purposes, this will generate a CSV file of all the datasets
        which could be helpful when examining the outputs created by this script

        Returns
        ----------
        List
            A list the dataset's attributes to be outputted into a CSV
        """
        return [self.name, self.contact, self.managed_by,
                self.data_license, self.documentation, self.update_frequency,
                ' '.join(self.tags), self.short_description.replace(',', '')
                ]

    def __str__(self):
        return f'{self.name} : {self.description}'


# Query the page that has all of the datasets listed on them
physionet_database_list_url = requests.get(BASE_URL + '/about/database')
soup = BeautifulSoup(physionet_database_list_url.content, 'html.parser')
open_databases = []

# Look for open databases header
databases_header = soup.find('h2', id=args.db_type)
databases_ul = databases_header.find_next_sibling()

# Create a list of all of the open databases
for item in databases_ul:
    if item.name == 'li':
        entry_id = item.a.attrs['href'].split('/')[2]
        url = item.a.attrs['href']
        name = item.a.get_text()
        description = item.a.next_sibling.replace(
            ':', '').strip().replace('\n', '')
        open_databases.append(
            PhysioNetDB(entry_id, url, name, description)
        )
if END == 0:
    END = len(open_databases)

# Create the output directory if it doesn't exist
if not os.path.isdir('output'):
    os.mkdir('output')

# Iterate over each database and get details from their respective pages
for database in open_databases[START:END]:
    # Get the database's full details page
    database_details = requests.get(database.url, allow_redirects=True)
    database_details_html = BeautifulSoup(
        database_details.content, 'html.parser')

    # Update the database entry with a full description
    database.extract_description(database_details_html)

    # Get the tags if available
    database.extract_tags(database_details_html)

    # Get the license if available
    database.extract_license(database_details_html)

    # Get citation information
    database.extract_citation(database_details_html)

# If in separate file mode, generate a separate YAML file for each dataset
if args.format == 'separate':
    for database in open_databases[START:END]:
        with open(f'output/{database.entry_id}.yaml', 'w') as f:
            yaml.dump(database.generate_separate_roda(), f)
# If in single file mode, generate a single YAML file with multiple resources
elif args.format == 'single':
    entry = dict(
        Name=SINGLE_ENTRY_NAME,
        Description=SINGLE_ENTRY_DESCRIPTION,
        Documentation=SINGLE_ENTRY_DOCUMENTATION,
        Contact=CONTACT_URL,
        ManagedBy=DEFAULT_MANAGED_BY,
        UpdateFrequency=UPDATE_FREQUENCY,
        Tags=SINGLE_ENTRY_TAGS,
        License=DEFAULT_LICENSE,
        Resources=[]
    )
    for database in open_databases[START:END]:
        entry['Resources'].append(database.generate_single_roda())
        for tag in database.tags:
            if tag not in entry['Tags']:
                entry['Tags'].append(tag)
    with open('output/single.yaml', 'w') as f:
        yaml.dump(entry, f)
# Not sure how we got here?
else:
    print('Unknown YAML format specified')
    sys.exit(1)

# Optionally write all of the data to a CSV file to quickly look at the data
if args.csv:
    with open('output/databases.csv', 'w') as f:
        output = csv.writer(f)
        output.writerow(
            ['name', 'contact', 'managed_by', 'license', 'documentation',
             'update_frequency', 'tags', 'description']
        )
        for database in open_databases:
            output.writerow(database.as_csv())

sys.exit(0)
