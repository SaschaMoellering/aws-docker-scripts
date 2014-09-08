import requests


def search_images_in_registry(registry, image_name):
    resp = requests.get('http://' + registry + '/v1/search?q=' + image_name)

    image_list = []
    json_resp = resp.json()
    for result in json_resp['results']:
        name = result['name'].replace("library/", "")
        image_list.append(name)

    return image_list





