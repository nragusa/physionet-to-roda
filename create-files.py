#!/usr/bin/env python

import json
import requests
from bs4 import BeautifulSoup
import yaml


class PhysioNetDB(object):
    def __init__(self, database_id, name, description):
        self.database_id = database_id
        self.name = name
        self.description = description


base_url = 'https://physionet.org'
physionet_database_list_url = requests.get(base_url + '/about/database')
soup = BeautifulSoup(physionet_database_list_url.content, 'html.parser')


def parseDatabasePage(href):
    databasePage = requests.get(base_url + href, allow_redirects=True)
    databasePageSoup = BeautifulSoup(databasePage.content, 'html.parser')
    # look for the schema.org metadata
    metaData = databasePageSoup.find('script', type='application/ld+json')
    metaDataJson = json.loads(metaData.string)
    createOpenDataRegistryYaml(metaDataJson)


def createOpenDataRegistryYaml(metaDataJson):
    openDataRegistryJson = []
    openDataRegistryJson['Name'] = metaDataJson['name']
    openDataRegistryJson['Description'] = metaDataJson['description']
    openDataRegistryJson['License'] = metaDataJson['license']


# look for open databases header
open_database_header = soup.find('h2', id='open')
open_databases = []
for element in open_database_header.next_siblings:
    if element.name == 'ul':
        # go through all subsequent open database items
        for entry in element.find_all('li'):
            # get the database page link
            print(entry)
            href = entry.find('a')['href']
            open_databases.append(
                PhysioNetDB('fake_id', 'name', 'description')
            )
