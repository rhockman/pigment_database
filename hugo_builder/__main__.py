import datetime
import json
import sqlite3

import os
import shutil
from jinja2 import Environment, PackageLoader, select_autoescape
from slugify import slugify


class HugoBuilder:
    def __init__(self):
        pass

    # noinspection SqlWithoutWhere
    def import_json(self, paints):
        with open(paints, "r") as fin:
            paints_json = json.load(fin)

        db = sqlite3.connect("pigments.sqlite3")

        cursor = db.cursor()
        cursor.execute('''DELETE FROM manufacturers''')
        cursor.execute('''DELETE FROM sqlite_sequence where name = 'manufacturers' ''')
        cursor.execute('''DELETE FROM paints''')
        cursor.execute('''DELETE FROM sqlite_sequence where name = 'paints' ''')
        cursor.execute('''DELETE FROM pigments''')
        cursor.execute('''DELETE FROM sqlite_sequence where name = 'pigments' ''')
        cursor.execute('''DELETE FROM pigments_to_paint''')
        cursor.execute('''DELETE FROM sqlite_sequence where name = 'pigments_to_paint' ''')
        db.commit()

        for manufacturer in paints_json.keys():
            execute_result = cursor.execute('''INSERT INTO manufacturers(name) values (?)''', (manufacturer,))

            manufacturer_id = execute_result.lastrowid

            for paint_name, pigments in paints_json[manufacturer][0].items():
                cursor.execute('''insert into paints(manufacturer_id, name) VALUES (?,?)''',
                               (manufacturer_id, paint_name))
                paint_id = cursor.lastrowid

                for pigment_detail in pigments:
                    pigment_code, pigment_name = pigment_detail

                    cursor.execute('''select id from pigments where pigments.code=? and pigments.name=? ''',
                                   (pigment_code, pigment_name))
                    pigment_result = cursor.fetchone()

                    if pigment_result:
                        pigment_id = pigment_result[0]
                        cursor.execute('''insert into pigments_to_paint(paint_id, pigment_id) values(?, ?)''',
                                       (paint_id, pigment_id))
                    else:
                        cursor.execute('''insert into pigments(code, name) VALUES (?, ?)''',
                                       (pigment_code, pigment_name))
                        pigment_id = cursor.lastrowid
                        cursor.execute('''insert into pigments_to_paint(paint_id, pigment_id) values(?, ?)''',
                                       (paint_id, pigment_id))

            db.commit()

        db.commit()
        db.close()

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

        db = sqlite3.connect("pigments.sqlite3")
        cursor = db.cursor()

        manufacturers_result = cursor.execute('''select id, name from manufacturers order by name''').fetchall()
        manufacturers = []

        for (manufacturer_id, manufacturer) in manufacturers_result:
            man_slug = slugify(manufacturer)
            os.makedirs(os.path.join("build", "paints", man_slug), exist_ok=True)
            manufacturers.append([manufacturer, man_slug])

            paints = []

            paint_results = cursor.execute('''select name from paints where manufacturer_id=? order by name''',
                                           (manufacturer_id,)).fetchall()

            for (paint_name,) in paint_results:
                paints.append([paint_name, slugify(paint_name)])
            paint_result = paint_index_template.render(manufacturer=manufacturer, paints=paints, man_slug=man_slug)
            with open(os.path.join("build", "paints", man_slug, "index.html"), "w+") as fout:
                fout.writelines(paint_result)

        man_index = manufacturer_index_template.render(manufacturers=manufacturers)
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
                                           pigments=pigments, paint_name=name, man_slug=man_slug)
            with open(os.path.join("build", "paints", man_slug, paint_file), "w+") as fout:
                fout.writelines(result)

        pigments_result = cursor.execute('''select id, code, name from pigments order by code, name''').fetchall()
        for (pigment_id, pigment_code, pigment_name) in pigments_result:
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
                    [manufacturer_name + " - " + paint_name, "/paints/{}/{}.html".format(slugify(manufacturer_name), slugify(paint_name))])

            for (manufacturer_name, paint_name, pigment_count) in multiple_paint_summary:
                multiple.append(
                    [manufacturer_name + " - " + paint_name, "/paints/{}/{}.html".format(slugify(manufacturer_name), slugify(paint_name)),
                     pigment_count])

            result = pigment_template.render(pigment_code=pigment_code, pigment_name=pigment_name, single=single,
                                             multiple=multiple)

            with open(os.path.join("build", "pigments", pigment_url), "w+") as fout:
                fout.writelines(result)

        db.close()


if __name__ == "__main__":
    hb = HugoBuilder()
    hb.build()
