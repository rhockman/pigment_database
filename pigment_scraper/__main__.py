from bs4 import BeautifulSoup
import requests
import json
from jq import jq
import logging
import sys


class PigmentScraper:
    def __init__(self):
        """Do things"""

    def run(self):

        pigment_dict = {}
        logging.basicConfig(format='%(asctime)s %(message)s', level='DEBUG', stream=sys.stdout)

        root_url = "https://www.dickblick.com/categories/watercolors/"

        logging.info("Retrieving master collection of artist grade watercolors from '{}'".format(root_url))
        r = requests.get(root_url)

        soup = BeautifulSoup(r.text, features="html.parser")

        paw = soup.find("a", attrs={"name": "professionalartistwatercolors"})

        b = paw.parent.parent.next_sibling.next_sibling

        links = b.find_all("li")

        manufacturers = {}

        for link in links:
            link_anchor = link.find("a")
            link_href = link_anchor['href']
            manufacturers[link_anchor.text] = link_href

        logging.info("Found {} manufacturers".format(len(manufacturers)))

        for m, u in manufacturers.items():
            pigment_dict[m] = []

            logging.info("Getting details for {}".format(m))

            r = requests.get("https://www.dickblick.com" + u)

            soup = BeautifulSoup(r.text, features="html.parser")

            page_id = soup.find("input", type="hidden", id="BlickPageId")['value']

            r = requests.get(
                "https://www.dickblick.com/DesktopModules/ProductServices/API/ProductServices/GetProductSkuList?itemId={}&skuId=0".format(
                    page_id))

            items = jq(".UserData.SkuList[] | {ItemId: .ItemId, SkuCode: .SkuCode}").transform(r.json(),
                                                                                               multiple_output=True)
            item_dict = {}

            for item in items:
                item_path = "https://www.dickblick.com/items/{item_id}-{sku_code}".format(item_id=item["ItemId"],
                                                                                          sku_code=item["SkuCode"])

                r = requests.get(item_path)

                pigments = []

                item_soup = BeautifulSoup(r.text, features="html.parser")
                paint_name = str(item_soup.find(class_="skutitle").text).strip().split(sep="—", maxsplit=2)[-1].strip()
                logging.info("Paint name: {}".format(paint_name))
                item_dict[paint_name] = pigments

                try:
                    pigments_tag = item_soup.find(class_="pigmentCIEDetailList").find_all("a")

                    for pigment_tag in pigments_tag:
                        pigment = str(pigment_tag.text).strip().split("—")
                        pigments.append(pigment)
                except:
                    logging.warning("Could not find pigment info for {}".format(paint_name))

            pigment_dict[m].append(item_dict)

            with open("pigments.json", "w+") as fout:
                json.dump(pigment_dict, fout, sort_keys=True, indent=2)


if __name__ == "__main__":
    ps = PigmentScraper()
    ps.run()
