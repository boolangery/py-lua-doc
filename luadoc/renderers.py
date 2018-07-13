import jinja2
import os
from enum import Enum
from luadoc.model import *
from shutil import copyfile


# Capture our current directory
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')


class HtmlTemplate(Enum):
    DEFAULT = 1


class HtmlRenderer:
    def __init__(self):
        pass

    def render(self, model, template: HtmlTemplate, output_dir: str):
        # create output dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        if not os.path.exists(output_dir + '/js'):
            os.makedirs(output_dir + '/js')
        if not os.path.exists(output_dir + '/css'):
            os.makedirs(output_dir + '/css')

        if template == HtmlTemplate.DEFAULT:
            self._render_default(model, output_dir)

    def _render_default(self, model, output_dir:str):
        loader = jinja2.FileSystemLoader(searchpath=TEMPLATE_DIR + '/default/')
        env = jinja2.Environment(loader=loader)

        index = env.get_template('index.html')

        for module in model:
            template = env.get_template('module.html')
            content = template.render(model=module)

            self._create_file(content, output_dir, module.name)

        # copy static files
        self._install_js('vendor/bootstrap/js/bootstrap.bundle.min.js', output_dir)
        self._install_js('vendor/jquery/jquery.min.js', output_dir)
        self._install_css('vendor/bootstrap/css/bootstrap.min.css', output_dir)
        self._install_css('default/simple-sidebar.css', output_dir)


    def _install_js(self, js_file, output_dir):
        path, filename = os.path.split(js_file)
        copyfile(os.path.join(TEMPLATE_DIR, js_file), os.path.join(output_dir, 'js', filename))

    def _install_css(self, css_file, output_dir):
        path, filename = os.path.split(css_file)
        copyfile(os.path.join(TEMPLATE_DIR, css_file), os.path.join(output_dir, 'css', filename))

    def _create_file(self, content, output_dir, name):
        with open(os.path.join(output_dir, name) + '.html', "w+") as file:
            file.write(content)
