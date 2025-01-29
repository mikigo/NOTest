import click

from notest.__version__ import __version__ as version

@click.group()
@click.help_option("-h", "--help", help="查看帮助信息")
@click.version_option(version, "-v", "--version", prog_name="NOTest", help="查看版本号")
def cli(): ...