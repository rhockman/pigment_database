import sqlite3

import os
import shutil
from jinja2 import Environment, PackageLoader, select_autoescape
from slugify import slugify


class HtmlBuilder:
    def __init__(self):
        pass

    def build(self, root_path = ''):
        shutil.rmtree("build", ignore_errors=True)
        shutil.copytree(os.path.join("html_builder", "css"), os.path.join("build"))

        os.makedirs("build", exist_ok=True)
        os.makedirs(os.path.join("build", "paints"), exist_ok=True)
        os.makedirs(os.path.join("build", "pigments"), exist_ok=True)

        env = Environment(
            loader=PackageLoader('html_builder', 'templates'),
            autoescape=select_autoescape(['html', 'xml', 'md'])
        )

        paint_template = env.get_template('paint.html')
        pigment_template = env.get_template('pigment.html')
        manufacturer_index_template = env.get_template('man_index.html')
        paint_index_template = env.get_template('paint_index.html')
        pigment_index_template = env.get_template('pigment_index.html')

        db = sqlite3.connect("pigments.sqlite3")
        cursor = db.cursor()

        # Generate Nav bar variables
        nav_pigments_result = cursor.execute('''select code, name from pigments order by code, name''').fetchall()
        nav_pigments = [(pigment_code, pigment_name, slugify(pigment_code), slugify(pigment_name)) for
                        (pigment_code, pigment_name) in nav_pigments_result]

        # Generate Pigment Index
        pigment_result = pigment_index_template.render(nav_pigments=nav_pigments, root_path=root_path)
        with open(os.path.join("build", "pigments", "index.html"), "w+") as fout:
            fout.writelines(pigment_result)

        manufacturers_result = cursor.execute('''select manufacturers.id, manufacturers.name, count() 
        from manufacturers 
        inner join paints p on manufacturers.id = p.manufacturer_id 
        group by manufacturers.id, manufacturers.name
        order by manufacturers.name''').fetchall()
        manufacturers = []

        for (manufacturer_id, manufacturer, paint_count) in manufacturers_result:
            man_slug = slugify(manufacturer)
            os.makedirs(os.path.join("build", "paints", man_slug), exist_ok=True)
            manufacturers.append([manufacturer, man_slug, paint_count])

            paints = []

            paint_results = cursor.execute('''
            select p.name, count()
            from paints as p 
            inner join pigments_to_paint ptp on p.id = ptp.paint_id
            where p.manufacturer_id=? 
            group by p.name
            order by name''',
                                           (manufacturer_id,)).fetchall()

            for (paint_name, pigment_count) in paint_results:
                paints.append([paint_name, slugify(paint_name), pigment_count])
            paint_result = paint_index_template.render(manufacturer=manufacturer, paints=paints, man_slug=man_slug, root_path=root_path)
            with open(os.path.join("build", "paints", man_slug, "index.html"), "w+") as fout:
                fout.writelines(paint_result)

        man_index = manufacturer_index_template.render(manufacturers=manufacturers, root_path=root_path)
        with open(os.path.join("build", "index.html"), "w+") as fout:
            fout.writelines(man_index)

        paints = cursor.execute('''select p.id, m.name, p.name 
        from paints as p 
        inner join manufacturers m on p.manufacturer_id = m.id''').fetchall()

        for (paint_id, manufacturer_name, name) in paints:
            pigments = []
            pigments_result = cursor.execute(
                '''select p.code, p.name 
                from pigments_to_paint as ptp 
                inner join pigments as p 
                on ptp.pigment_id = p.id 
                where ptp.paint_id=?
                order by p.code, p.name''', (paint_id,)).fetchall()
            man_slug = slugify(manufacturer_name)
            paint_file = "{}.html".format(slugify(name))

            for (pigment_code, pigment_name) in pigments_result:
                pigment_url = "{}-{}.html".format(slugify(pigment_code), slugify(pigment_name))
                pigments.append([pigment_code, pigment_name, pigment_url])

            result = paint_template.render(manufacturer=manufacturer_name,
                                           pigments=pigments, paint_name=name, man_slug=man_slug, root_path=root_path)
            with open(os.path.join("build", "paints", man_slug, paint_file), "w+") as fout:
                fout.writelines(result)

        # Pigment Info Page
        pigments_result = cursor.execute(
            '''select id, code, name, description from pigments order by code, name''').fetchall()
        for (pigment_id, pigment_code, pigment_name, pigment_description) in pigments_result:
            pigment_url = "{}-{}.html".format(slugify(pigment_code), slugify(pigment_name))
            single = []
            multiple = []

            single_paint_summary = cursor.execute('''
            select m.name as manufacturer_name, p.name as paint_name, pc.cnt from
            pigments_to_paint as ptp inner join paints p on ptp.paint_id = p.id
            inner join manufacturers m on p.manufacturer_id = m.id
            inner join (select count(*) as cnt, paint_id 
                        from pigments_to_paint group by paint_id) as pc on pc.paint_id = p.id
            where ptp.pigment_id=? and pc.cnt=1
            ''', (pigment_id,)).fetchall()

            multiple_paint_summary = cursor.execute('''
            select m.name as manufacturer_name, p.name as paint_name, pc.cnt from
            pigments_to_paint as ptp inner join paints p on ptp.paint_id = p.id
            inner join manufacturers m on p.manufacturer_id = m.id
            inner join (select count(*) as cnt, paint_id 
                        from pigments_to_paint group by paint_id) as pc on pc.paint_id = p.id
            where ptp.pigment_id=? and pc.cnt>1
            ''', (pigment_id,)).fetchall()

            for (manufacturer_name, paint_name, paint_count) in single_paint_summary:
                single.append(
                    [manufacturer_name + " - " + paint_name,
                     "{}/paints/{}/{}.html".format(root_path, slugify(manufacturer_name), slugify(paint_name))])

            for (manufacturer_name, paint_name, pigment_count) in multiple_paint_summary:
                multiple.append(
                    [manufacturer_name + " - " + paint_name,
                     "{}/paints/{}/{}.html".format(root_path, slugify(manufacturer_name), slugify(paint_name)),
                     pigment_count])

            pigment_link_result = cursor.execute('''select source, url from pigment_links where pigment_id=?''',
                                                 (pigment_id,)).fetchall()

            result = pigment_template.render(pigment_code=pigment_code, pigment_name=pigment_name, single=single,
                                             multiple=multiple, pigment_description=pigment_description,
                                             pigment_links=pigment_link_result,
                                             root_path=root_path
                                             )

            with open(os.path.join("build", "pigments", pigment_url), "w+") as fout:
                fout.writelines(result)

        db.close()


if __name__ == "__main__":
    hb = HtmlBuilder()
    hb.build(root_path='/pigments')
