import json

def getCreateServiceModel():
    with open('rancher_gitlab_deploy/models/createService.json') as data_file:
        return json.load(data_file)