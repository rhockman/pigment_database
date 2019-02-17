import datetime
import json
import sys

import os
import shutil
from jinja2 import Environment, PackageLoader, select_autoescape
from slugify import slugify


class HugoBuilder:
    def __init__(self, paints):
        with open(paints, "r") as fin:
            self.paints = json.load(fin)

    def import_json(self):
        pass

    def build(self):
        shutil.rmtree("build", ignore_errors=True)
        shutil.copytree(os.path.join("hugo_builder", "css"), os.path.join("build"))

        os.makedirs("build", exist_ok=True)
        os.makedirs(os.path.join("build", "paints"), exist_ok=True)
        os.makedirs(os.path.join("build", "pigments"), exist_ok=True)

        render_date = datetime.datetime.now()

        env = Environment(
            loader=PackageLoader('hugo_builder', 'templates'),
            autoescape=select_autoescape(['html', 'xml', 'md'])
        )

        paint_template = env.get_template('paint.html')
        pigment_template = env.get_template('pigment.html')
        manufacturer_index_template = env.get_template('man_index.html')
        paint_index_template = env.get_template('paint_index.html')

        pigments_ref = {}

        manufacturers = []

        for manufacturer in self.paints.keys():
            man_slug = slugify(manufacturer)
            manufacturers.append([manufacturer, man_slug])
            os.makedirs(os.path.join("build", "paints", man_slug))
            details = self.paints[manufacturer][0]

            paints = []

            for paint_name, pigments in details.items():
                long_name = "{} - {}".format(manufacturer, paint_name)
                for pigment_details in pigments:
                    pigment_details.append(slugify(pigment_details[0]))
                result = paint_template.render(manufacturer=manufacturer, date=render_date.isoformat(),
                                               pigments=pigments, paint_name=paint_name, man_slug=man_slug)
                paint_slug = slugify(paint_name)
                paints.append([paint_name, paint_slug])

                paint_file = "{}.html".format(paint_slug)
                paint_url = "/paints/{}/{}.html".format(man_slug, paint_slug)

                for pigment in pigments:
                    pid, pigment_name, pigment_slug = pigment
                    single_pigment = len(pigments) == 1
                    if pid not in pigments_ref:
                        pigments_ref[pid] = {"single": [], "multiple": [], "name": pigment_name}

                    if single_pigment:
                        if [long_name, paint_url] not in pigments_ref[pid]["single"]:
                            pigments_ref[pid]["single"].append([long_name, paint_url])
                    else:
                        if [long_name, paint_url] not in pigments_ref[pid]["multiple"]:
                            pigments_ref[pid]["multiple"].append([long_name, paint_url])

                with open(os.path.join("build", "paints", man_slug, paint_file), "w+") as fout:
                    fout.writelines(result)

            with open(os.path.join("build", "paints", man_slug, "index.html"), "w+") as fout:
                fout.writelines(
                    paint_index_template.render(man_slug=man_slug, paints=paints, manufacturer=manufacturer))

        man_index = manufacturer_index_template.render(manufacturers=manufacturers)
        with open(os.path.join("build", "index.html"), "w+") as fout:
            fout.writelines(man_index)

        for pigment, details in pigments_ref.items():
            pigment_file = "{}.html".format(slugify(pigment))
            result = pigment_template.render(pigment_id=pigment, pigment_name=details["name"], single=details["single"],
                                             multiple=details["multiple"])

            with open(os.path.join("build", "pigments", pigment_file), "w+") as fout:
                fout.writelines(result)


if __name__ == "__main__":
    hb = HugoBuilder(sys.argv[1])
    hb.build()
