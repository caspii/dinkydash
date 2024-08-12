import os
import shutil
from jinja2 import Environment, FileSystemLoader
import markdown
import yaml

# Set up Jinja2 environment
env = Environment(loader=FileSystemLoader('templates'))

# Set output directory to '../docs'
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docs'))


def read_markdown(filename):
    with open(filename, 'r') as file:
        content = file.read().split('---', 2)
        if len(content) > 2:
            front_matter = yaml.safe_load(content[1])
            markdown_content = content[2]
        else:
            front_matter = {}
            markdown_content = content[0]
        return front_matter, markdown.markdown(markdown_content)


def copy_images():
    if os.path.exists('images'):
        output_image_dir = os.path.join(OUTPUT_DIR, 'images')
        if os.path.exists(output_image_dir):
            shutil.rmtree(output_image_dir)
        shutil.copytree('images', output_image_dir)


def generate_pages():
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for root, dirs, files in os.walk('content'):
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                front_matter, content = read_markdown(file_path)

                template_name = front_matter.get('template', 'page.html')
                template = env.get_template(template_name)

                output = template.render(content=content, **front_matter)

                # Determine output path
                rel_path = os.path.relpath(file_path, 'content')
                base_name = os.path.splitext(rel_path)[0]

                if base_name == 'index':
                    # For index.md, keep it at the root of its directory
                    output_path = os.path.join(OUTPUT_DIR, os.path.dirname(rel_path), 'index.html')
                else:
                    # For other files, create a subdirectory
                    output_path = os.path.join(OUTPUT_DIR, base_name, 'index.html')

                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # Write output
                with open(output_path, 'w') as f:
                    f.write(output)


def preserve_cname():
    cname_path = os.path.join(OUTPUT_DIR, 'CNAME')
    if os.path.exists(cname_path):
        with open(cname_path, 'r') as f:
            cname_content = f.read()
        return cname_content
    return None


def restore_cname(cname_content):
    if cname_content:
        cname_path = os.path.join(OUTPUT_DIR, 'CNAME')
        with open(cname_path, 'w') as f:
            f.write(cname_content)


if __name__ == '__main__':
    # Preserve CNAME content
    cname_content = preserve_cname()

    # Clear the output directory if it exists
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)

    generate_pages()
    copy_images()

    # Restore CNAME file
    restore_cname(cname_content)

    print(f"Site generated in {OUTPUT_DIR}")